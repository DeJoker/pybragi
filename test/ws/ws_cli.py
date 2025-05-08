# -*- coding: utf-8 -*-
import random
import uuid

import requests
from pybragi.base import log
import logging
import json
import threading
import time
import websocket # pip install websocket-client==1.8.0
import proto_ws
from datetime import datetime
from pybragi.zy.signature import ZyTicket # pip install pybragi==0.0.13.post2

def parse_event(message: dict):
    header = message['header']
    payload = message['payload']

    header = proto_ws.Header(**header)

    if header.event == proto_ws.task_started_event:
        logging.info(f"{header.event}: {header}")
    elif header.event == proto_ws.result_generated_event:
        result = proto_ws.ResultGenerated(**payload)
        logging.info(f"{header.event}: {header} {result}")
    elif header.event == proto_ws.task_finished_event:
        finished = proto_ws.TaskFinished(**payload)
        logging.info(f"{header.event}: {header} {finished}")
    elif header.event == proto_ws.task_failed_event:
        logging.info(f"{header.event}: {header} {payload}")
    elif header.event == proto_ws.audio_received_event:
        audio_info = proto_ws.AudioInfo(**payload)
        logging.info(f"{header.event}: {header} {audio_info}")
    else:
        logging.info(f"unknown event: {header}")



class WebSocketClient:
    def __init__(self, host):
        self.host = host
        self.ws = None
        self.connected = False

    def on_message(self, ws, message):
        if isinstance(message, bytes):
            logging.info(f"binary message, length: {len(message)} bytes")
        else:
            try:
                data = json.loads(message)
                logging.info(f"json message: {json.dumps(data, ensure_ascii=False, indent=2)}")
            except json.JSONDecodeError:
                logging.info(f"message: {message}")

    def on_error(self, ws, error):
        logging.info(f"error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.info(f"disconnected (status: {close_status_code}, msg: {close_msg})")
        self.connected = False

    def on_open(self, ws):
        logging.info(f"connected to {self.url}")
        self.connected = True

    def connect(self):
        # websocket.enableTrace(True)
        
        ticket = ZyTicket(proto_ws.ticket_salt)
        ticket.access_token = "1234567890"
        ticket.randomString = "test"
        # ticket.milli_timestamp = hex(int(time.time() * 1000))[2:]
        ticket.milli_timestamp = int(time.time() * 1000)
        # ticket.milli_timestamp = int(time.time() * 1000) - 500 * 1000 #$ expired in 5 minutes
        ticket.user_id = "1234567890"
        ticket.platform_id = 1
        self.ticket = ticket

        self.url = f"{self.host}?ticker={self.ticket.encode()}"
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.client_thread = threading.Thread(target=self.ws.run_forever)
        self.client_thread.daemon = True
        self.client_thread.start()
        
        timeout = 5
        start_time = time.perf_counter()
        while not self.connected and time.perf_counter() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            logging.info(f"timeout {timeout}s: cannot connect to {self.url}")
            return False
        return True

    def disconnect(self):
        if self.ws:
            self.ws.close()
        logging.info("disconnected")

    def send_json(self, data: dict):
        if not self.connected:
            logging.info("error: not connected")
            return False
        
        try:
            message = json.dumps(data)
            
            logging.info(f"send: {message}")
            self.ws.send(message)
            return True
        except Exception as e:
            logging.info(f"error: {e}")
            return False

    def send_file(self, data):
        if not self.connected:
            logging.info("error: not connected")
            return False
        
        try:
            logging.info(f"send file: {len(data)} bytes")
            self.ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
            return True
        except Exception as e:
            logging.info(f"error: {e}")
            return False

    def send_audio(self, audio_url):
        # 1. 发送 run-task 指令
        task_id = f"{int(time.time())}-{uuid.uuid4()}"
        run_task_header = proto_ws.Header(action=proto_ws.run_task_action, task_id=task_id, attributes={"a": 1, "b": "222"})
        run_task_payload = proto_ws.RunTask(task="echo", parameters={
            "rvc_name": "shengongbao-rvc",
            "seed_name": "whisper_small",
            'mid': '1744881157294',  
            'cascaded_use_rvc': True, 
            'f0_method': 'rmvpe', 
            'rms_mix_rate': 0.33,
            'protect': 0.33, 
            'diffusion_steps': 50,
            'length_adjust': 1,
            'inference_cfg_rate': 0.7
        })

        run_task_request = proto_ws.Request(header=run_task_header, payload=run_task_payload)
        self.send_json(run_task_request.model_dump())

        # 2. 发送音频
        resp = requests.get(audio_url)
        logging.info(f"audio_url: {audio_url} {len(resp.content)}")
        send_times = 4
        send_bytes = int(len(resp.content)/send_times) + 1
        for i in range(send_times):
            # append-audio指令
            send_data = resp.content[i*send_bytes:(i+1)*send_bytes]
            append_audio_header = proto_ws.Header(action=proto_ws.append_audio_action, task_id=task_id,)
            append_audio_payload = proto_ws.AudioInfo(audio_size=len(send_data), audio_duration="00:00:05.23")
            append_audio_request = proto_ws.Request(header=append_audio_header, payload=append_audio_payload)
            self.send_json(append_audio_request.model_dump())

            # 发送音频
            self.send_file(send_data)
            time.sleep(random.randint(100, 300)/1000)

        # 3. 发送结束指令
        finish_task_header = proto_ws.Header(action=proto_ws.finish_task_action, task_id=task_id,)
        finish_task_request = proto_ws.Request(header=finish_task_header, payload=None)
        self.send_json(finish_task_request.model_dump())


def mock_json():
    return {
        "name": "test",
        "request_id": f"{int(time.time())}-{uuid.uuid4()}",
        "data": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}-{uuid.uuid4()}"
    }


def main(audio_urls=[]):
    # host = "ws://14.103.229.186:50004/ws"
    host = "ws://localhost:50005/ws"
    client = WebSocketClient(host)
    client.connect()
    while client.connected:
        # client.send_json(mock_json())
        # time.sleep(random.randint(100, 300)/1000)

        client.send_audio(audio_urls[random.randint(0, len(audio_urls) - 1)])
        time.sleep(10)


    


if __name__ == "__main__":
    audio_urls = [
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_002_amiya_cn_025.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_002_amiya_cn_033.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_009_12fce_cn_017.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_009_12fce_cn_033.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_1027_greyy2_cn_044.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_102_texas_cn_007.wav",
        "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/model/gpt/audio/20250227test/char_1032_excu2_cn_043.wav",
    ]
    
    main(audio_urls=audio_urls)
