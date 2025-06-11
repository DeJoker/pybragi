import asyncio
from typing import Any, Callable, Dict
import munch
from pydantic import BaseModel, Field


from threading import Lock
from pybragi.base import metrics, time_utils
import logging

import queue
import time
import traceback
import numpy as np
from tornado import ioloop
from tornado.websocket import WebSocketHandler
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor
from pybragi.model.cache import LRUCacheModelQueue

import soundfile as sf
from io import BytesIO
from pybragi.zy import upload_tos

import json
from pybragi.proto import ws_audio as proto_ws
from pybragi.model.audio_utils import load_audio_from_url, convert_int16_to_float32, convert_float32_to_int16, resample

from pybragi.base.base_handler import make_tornado_web, run_tornado_app
from pybragi.zy.signature import ZyTicker
from pybragi.model.rwlock import get_model_for_read 



models_dict = {
    "whisper_small": {
        "model_path": "whisper_small",
        "model_type": "whisper_small",
        "model_size": "small",
        "model_version": "1.0.0",
        "model_description": "whisper_small",
    }
}

class InferenceParams(BaseModel):
    reference_audio_url: str
    seed_name: str
    diffusion_steps: int
    inference_cfg_rate: int

class SeedVcInfo(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    seed_vc_name: str = ""
    seed_model_path: str = ""
    seed_config_path: str = ""
    samplarate: int = 22050

    seed_models: LRUCacheModelQueue = Field(default=None, exclude=True)

class SeedVcModel(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    overlap_wave_len: int = 4096
    max_context_window: int = 2580
    sr: int = 22050
    hop_length: int = 256

    nets: munch.Munch = Field(default=None, exclude=True) # model 
    semantic_fn: Callable = Field(default=None, exclude=True)
    vocoder_fn: Callable = Field(default=None, exclude=True)
    campplus_model: Any = Field(default=None, exclude=True) # model
    to_mel: Callable = Field(default=None, exclude=True)
    mel_fn_args: Dict[str, Any] = Field(default=None, exclude=True)

    def to(self, device: str):
        for key in self.nets:
            self.nets[key].eval()
            self.nets[key].to(device)
        self.campplus_model.to(device)
        return self

import random
class VcRealtime:
    def __init__(self, samplerate: int):
        self.samplerate = samplerate
        self.config = None
        self.block_time = 0.5
        self.audio_callback = None
        
    def start_vc(self):
        pass
    
    def audio_callback(self, model_set, chunk_audio, reference_audio, diffusion_steps, inference_cfg_rate):
        time.sleep(random.randint(100, 300) * 0.001)
        return chunk_audio


class WSHandler(metrics.PrometheusMixIn, WebSocketHandler):
    executor = ThreadPoolExecutor(30)
    client_to_task = {} # client -> task_id
    _shutdown_in_progress = False  # 添加退出标志

    def initialize(self):
        self.ioloop = ioloop.IOLoop.current()

    def connect_info(self):
        task_id = WSHandler.client_to_task.get(self)
        ip = self.remote_ip
        user_id = self.user_id
        return f"user_id: {user_id}, ip: {ip}, task_id: {task_id}"

    def on_close(self):
        logging.info(f"closed: {self.connect_info()}")
        self.exited = True
        WSHandler.client_to_task.pop(self, None)

    
    async def open(self):
        # 检查是否正在退出，如果是则拒绝新连接
        if WSHandler._shutdown_in_progress:
            logging.warning(f"Rejecting new connection from {self.request.remote_ip} - server is shutting down")
            self.close(code=proto_ws.code_shutting_down, reason="Server is shutting down")
            return

        logging.info(f"connected from {self.request.remote_ip}")
        self.remote_ip = self.request.remote_ip
        self.exited = False
        self.recv_lock = Lock()
        self.task_id = ""
        self.source_audio_url = ""
        self.target_audio_url = ""

        ticker_str = self.get_query_argument("ticker", default=None)
        logging.info(f"ticker_str: {ticker_str}")
        if not ticker_str:
            logging.warning(f"Connection attempt from {self.remote_ip} without ticker. Closing.")
            self.close(code=proto_ws.code_authentication_failed, reason="Missing authentication ticker") # 1008: Policy Violation
            return
        
        try:
            ticker = ZyTicker(proto_ws.ticker_key)
            ticker.decode(ticker_str)
            ok, msg = ticker.allow()
            if ok:
                logging.info(f"Authenticated connection from {self.remote_ip}, {ticker}")
                self.user_id = ticker.user_id
                super().open()
            else:
                logging.warning(f"Authentication failed for {self.remote_ip}. {ticker} error:{msg}. Closing.")
                self.close(code=proto_ws.code_authentication_failed, reason=f"Invalid authentication ticker, error: {msg}")
        except Exception as e:
            logging.error(f"Error during authentication for {self.remote_ip}: {e}. Closing.")
            self.close(code=proto_ws.code_authentication_failed, reason="Internal server error during authentication") # 1011: Internal Error
        return
    
    def check_origin(self, origin):
        return True
    
    def set_task_id(self, task_id):
        task_id = task_id.strip()
        if not task_id:
            logging.warning(f"task_id is empty")
            return False
        
        self.task_id = task_id
        self.send_buffer = queue.Queue()
        self.last_msg_time = time.time()
        self.audio_buffer = b''
        self.processed_buffer_len = 0
        self.audio_np = np.ndarray((0,), dtype=np.float32)
        self.client_task_done = False
        self.np_convert_done = False
        self.vc_task_done = False

        
        if WSHandler.client_to_task.get(self):
            logging.warning(f"task_id {task_id} already exists")
            return False
        
        logging.info(f"Binding connection {self} to task_id: {task_id}")
        WSHandler.client_to_task[self] = task_id

        self.send_nps = []
        self.send_audio_generated()
        self.vc_audio_loop()
        self.receive_audio_loop()

        return True
        

    def prepare_seed_model(self, request: InferenceParams):
        # load_model(request.seed_name)
        self.request = request
        self.reference_audio = load_audio_from_url(request.reference_audio_url, 16000)

        with get_model_for_read(request.seed_name, models_dict) as model_info:
            model_info: SeedVcInfo = model_info
            self.seed_models: LRUCacheModelQueue = model_info.seed_models
        
        vc = VcRealtime(model_info.samplarate)
        vc.start_vc()

        return vc



    @run_on_executor
    def receive_audio_loop(self):
        while True:
            if self.exited:
                return

            if self.processed_buffer_len == len(self.audio_buffer):
                if self.client_task_done:
                    break
                time.sleep(0.1)
                continue

            
            with time_utils.ElapseCtx("audio_buffer resample", gt=0.01):
                with self.recv_lock:
                    current_len = len(self.audio_buffer)
                    current_audio_np = resample(self.audio_buffer, np.int16, 16000, self.vc.samplerate)
                resampled_audio_np = convert_int16_to_float32(current_audio_np)
                logging.info(f"resampled_audio_np: {resampled_audio_np.shape} {resampled_audio_np.dtype} "
                            f"{resampled_audio_np.max():.3f} {resampled_audio_np.min():.3f}, duration: {len(resampled_audio_np)/self.vc.samplerate:.2f}s")
                self.audio_np = resampled_audio_np
                self.processed_buffer_len = current_len

        self.np_convert_done = True
        # self.upload_source_audio()
        return

    @run_on_executor
    def send_audio_generated(self):
        total_send_buffer = b''
        while not self.vc_task_done or not self.send_buffer.empty():
            if self.exited:
                return
            
            send_data, binary = self.send_buffer.get()
            self.ioloop.add_callback(self.write_message, send_data, binary=binary)
            if binary:
                total_send_buffer += send_data
                logging.info(f"Sent binary data for task {self.task_id}, size={len(send_data)} bytes")
            else:
                logging.info(f"Sent json data for task {self.task_id}, json={send_data}")
            self.last_msg_time = time.time()
        


    @run_on_executor
    def send_task_finished(self):
        header = proto_ws.Header(event=proto_ws.task_finished_event, task_id=self.task_id,)
        if not self.target_audio_url:
            self.upload_target_audio()
        
        payload = proto_ws.TaskFinished(source_audio_url=self.source_audio_url, target_audio_url=self.target_audio_url)
        request = proto_ws.Request(header=header, payload=payload)
        self.ioloop.add_callback(self.write_message, request.model_dump_json())
        return 

    @run_on_executor
    def vc_audio_loop(self):

        current_pos = 0
        chunk_size = int(self.vc.config.block_time * self.vc.samplerate) # 固定只能转出如此 size 的音频  多出的部分不会处理
        logging.info(f"chunk_size: {chunk_size} samplerate: {self.vc.samplerate}")

        while len(self.audio_np) == 0:
            time.sleep(0.1)
            continue

        while not self.np_convert_done or current_pos < len(self.audio_np):
            if self.exited:
                return
            
            if time.time() - self.last_msg_time > 60:
                logging.warning(f"task {self.task_id} timeout")
                self.exited = True
                # Force close the websocket connection
                self.ioloop.add_callback(self.close, code=proto_ws.code_force_close, reason="Connection timeout after 60 seconds of inactivity")
                break

            chunk_end = min(int(current_pos + chunk_size), len(self.audio_np))
            chunk_audio = self.audio_np[current_pos:chunk_end]
            current_pos = chunk_end

            if len(chunk_audio) < chunk_size:
                if not self.np_convert_done:
                    time.sleep(0.1)
                    continue

                if len(chunk_audio) < chunk_size:
                    chunk_audio = np.pad(chunk_audio, (0, chunk_size - len(chunk_audio)), mode='constant')

            with self.seed_models.get_model() as seed_model:
                seed_model: SeedVcModel = seed_model

                model_set = (
                    seed_model.nets,
                    seed_model.semantic_fn,
                    seed_model.vocoder_fn,
                    seed_model.campplus_model,
                    seed_model.to_mel,
                    seed_model.mel_fn_args,
                    seed_model.sr,
                    seed_model.hop_length,
                    seed_model.max_context_window,
                    seed_model.overlap_wave_len
                )

                outdata: np.ndarray = self.vc.audio_callback(model_set, chunk_audio, self.reference_audio, 
                                                                self.request.diffusion_steps, self.request.inference_cfg_rate)
            
            resampled = resample(outdata, np.float32, self.vc.samplerate, 16000)
            resampled = convert_float32_to_int16(resampled)
            self.send_nps.append(resampled)
            buffer = resampled.tobytes()
            self.send_buffer.put((buffer, True))

            logging.info(f"current_pos: {current_pos} output_duration: {len(resampled)/16000:.2f}s")
        
        if not self.exited:
            logging.info(f"task {self.task_id} done")
            self.ioloop.add_callback(self.send_task_finished)

    def upload_target_audio(self):
        with BytesIO() as wavf:
            audio_np = np.concatenate(self.send_nps, axis=0)
            logging.info(f"audio_np: {audio_np.shape} {audio_np.dtype} {audio_np.max()} {audio_np.min()}, duration: {len(audio_np)/16000:.2f}s")
            sf.write(wavf, audio_np, 16000, format="wav")
            wavf.seek(0)
            url, ok = upload_tos.upload_rvc(wavf, f"seed-{self.task_id}")
            if not ok:
                logging.error(f"{self.task_id} upload failed")
            else:
                logging.info(f"{self.task_id} upload success: {url}")
                self.target_audio_url = url

    async def on_message(self, message):
        if self.task_id:
            self.last_msg_time = time.time()
        
        try:
            if isinstance(message, str):
                data = json.loads(message)
                header = proto_ws.Header(**data["header"])
                if header.action == proto_ws.run_task_action:
                    payload = proto_ws.RunTask(**data["payload"])
                    try:
                        seed_vc = InferenceParams(**payload.parameters)
                        logging.info(f"run-task: {seed_vc}")
                        self.vc = self.prepare_seed_model(seed_vc)
                    except Exception as e:
                        logging.error(f"failed to parse seed_vc: {e}")
                        self.close(code=proto_ws.code_invalid_parameters, reason=f"Invalid parameters: {e}")
                        return

                    if not self.set_task_id(header.task_id):
                        logging.error(f"failed to set task_id: {header.task_id}")
                        self.close(code=proto_ws.code_invalid_parameters, reason="Not valid task_id setting") 
                        return

                    task_started_header = proto_ws.Header(event=proto_ws.task_started_event, task_id=header.task_id)
                    task_started_message = proto_ws.Request(header=task_started_header, payload={}).model_dump_json()
                    self.write_message(task_started_message)

                elif header.action == proto_ws.append_audio_action:
                    payload = proto_ws.AudioInfo(**data["payload"])
                    logging.info(f"append-audio: {payload}")
                elif header.action == proto_ws.finish_task_action:
                    self.client_task_done = True
                else:
                    logging.info(f"unknown action: {header}")
                    return
            else:
                logging.info(f"received binary message, size: {len(message)} bytes")
                with time_utils.ElapseCtx("audio_buffer to np", gt=0.01), self.recv_lock:
                    self.audio_buffer += message

                
        except Exception as e:
            traceback.print_exc()
            logging.error(f"{self.connect_info()}, error: {str(e)}")
            self.close(code=proto_ws.code_exception, reason=f"Internal server error during message processing: {str(e)}")
    
    
async def websocket_graceful_shutdown(max_wait_time = 70):
    logging.info("Waiting for active connections to complete...")
    
    # 1. 等待所有WebSocket连接处理完成
    wait_cnt = 0
    while WSHandler.client_to_task:
        if wait_cnt >= max_wait_time:
            break
        active_count = len(WSHandler.client_to_task)
        logging.info(f"Still {active_count} active connections, waiting...")
        await asyncio.sleep(1)
        wait_cnt += 1
    
    # 2. 如果还有连接，强制关闭
    if WSHandler.client_to_task:
        logging.warning(f"Forcefully closing {len(WSHandler.client_to_task)} remaining connections")
        for client in list(WSHandler.client_to_task.keys()):
            client: WSHandler
            try:
                client.close(code=proto_ws.code_force_close, reason="Server shutdown timeout")
            except Exception as e:
                logging.error(f"Error force closing client connection: {e}")
    
    # 3. wait for all requests reply to client
    await asyncio.sleep(1)
    ioloop.IOLoop.current().stop()


if __name__ == "__main__":
    from pybragi.base.base_handler import register_exit_handler
    
    register_exit_handler(websocket_graceful_shutdown)
    # load_model("whisper_small")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50000)
    args = parser.parse_args()

    app = make_tornado_web("ws_test")
    app.add_handlers(
        ".*$",
        [
            (r"/ws", WSHandler),
        ],
    )
    run_tornado_app(app, args.port)
