import random
import time
from pybragi.base import log
import logging
import signal
from tornado import ioloop
from tornado.websocket import WebSocketHandler
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor

import json
import proto_ws
from datetime import datetime
from pybragi.base import metrics
from pybragi.base.base_handler import make_tornado_web, run_tornado_app
from pybragi.zy.signature import ZyTicket

class WSHandler(metrics.PrometheusMixIn, WebSocketHandler):
    executor = ThreadPoolExecutor(30)
    clients = set()
    client_tasks = {}
    
    async def open(self):
        logging.info(f"connected from {self.request.remote_ip}")

        ticker_str = self.get_query_argument("ticker", default=None)
        if not ticker_str:
            logging.warning(f"Connection attempt from {self.request.remote_ip} without ticker. Closing.")
            self.close(code=1008, reason="Missing authentication ticker") # 1008: Policy Violation
            return
        
        try:
            ticket = ZyTicket(proto_ws.ticket_salt)
            ticket.decode(ticker_str)
            ok, msg = ticket.allow()
            if ok:
                logging.info(f"Authenticated connection from {self.request.remote_ip}, {ticket}")
                WSHandler.clients.add(self)
                super().open()
            else:
                logging.warning(f"Authentication failed for {self.request.remote_ip}. error:{msg}. Closing.")
                self.close(code=1008, reason=f"Invalid authentication ticker, error: {msg}")

        except Exception as e:
            logging.error(f"Error during authentication for {self.request.remote_ip}: {e}. Closing.")
            self.close(code=1011, reason="Internal server error during authentication") # 1011: Internal Error
        
        WSHandler.clients.add(self)
        super().open()
        return
    
    def check_origin(self, origin):
        # logging.info(f"connect from {origin}")
        return True
    
    def set_task_id(self, task_id):
        task_id = task_id.strip()
        if task_id:
            if WSHandler.client_tasks.get(self) is None:
                logging.info(f"Binding connection {self} to task_id: {task_id}")
                WSHandler.client_tasks[self] = task_id
                return True
        return False

    @run_on_executor
    def send_result_generated(self, task_id, data):
        time.sleep(random.randint(100, 300)/1000)

        header = proto_ws.Header(event=proto_ws.result_generated_event, task_id=task_id,)
        payload = proto_ws.AudioInfo(audio_size=len(data), audio_duration="00:00:05.23")
        request = proto_ws.Request(header=header, payload=payload)

        return request.model_dump_json(), data

    @run_on_executor
    def send_task_finished(self, task_id):
        time.sleep(random.randint(100, 300)/1000)

        header = proto_ws.Header(event=proto_ws.task_finished_event, task_id=task_id,)
        payload = proto_ws.TaskFinished(source_audio_url="http://source.wav", target_audio_url="http://target.wav")
        request = proto_ws.Request(header=header, payload=payload)
        return request.model_dump_json()

    @run_on_executor
    def send_audio_received(self, task_id, data):
        time.sleep(random.randint(100, 300)/1000)

        header = proto_ws.Header(event=proto_ws.audio_received_event, task_id=task_id,)
        payload = proto_ws.AudioInfo(audio_size=len(data), audio_duration="00:00:05.23")
        request = proto_ws.Request(header=header, payload=payload)
        return request.model_dump_json()

    def send_message(self, message, binary=False):
        self.write_message(message, binary=binary)

    async def on_message(self, message):
        # logging.info(f"received: {type(message).__name__} length: {len(message) if message else 0}")
        
        try:
            if isinstance(message, str):
                data = json.loads(message)
                header = proto_ws.Header(**data["header"])
                if header.action == proto_ws.run_task_action:
                    payload = proto_ws.RunTask(**data["payload"])
                    logging.info(f"run-task: {payload}")
                    self.set_task_id(header.task_id)

                    task_started_header = proto_ws.Header(event=proto_ws.task_started_event, task_id=header.task_id)
                    message = proto_ws.Request(header=task_started_header, payload={}).model_dump_json()
                    self.send_message(message)
                elif header.action == proto_ws.append_audio_action:
                    payload = proto_ws.AudioInfo(**data["payload"])
                    logging.info(f"append-audio: {payload}")
                elif header.action == proto_ws.finish_task_action:
                    json_message = await self.send_task_finished(self.client_tasks[self])
                    self.send_message(json_message)
                else:
                    logging.info(f"unknown action: {header}")
                    return
            else:
                logging.info(f"received binary message, size: {len(message)} bytes")
                json_message, binary_data = await self.send_result_generated(self.client_tasks[self], message)
                self.send_message(json_message)
                self.send_message(binary_data, binary=True)
                
        except Exception as e:
            logging.error(f"error: {str(e)}")
            self.write_message(json.dumps({"error": str(e)}))
    
    async def on_close(self):
        logging.info(f"closed: {self.request.remote_ip}")
        WebSocketHandler.clients.remove(self)
    
    @classmethod
    def broadcast(cls, message, binary=False):
        for client in cls.clients:
            try:
                client.write_message(message, binary=binary)
            except Exception as e:
                logging.error(f"error: {str(e)}")
    
    @classmethod
    async def send_json_to_all(cls, data):
        message = json.dumps(data)
        cls.broadcast(message)
    
    @classmethod
    async def send_file_to_all(cls, file_path):
        try:
            with open(file_path, 'rb') as file:
                data = file.read()
                cls.broadcast(data, binary=True)
                return True
        except Exception as e:
            logging.error(f"error: {str(e)}")
            return False
    
def handle_exit_signal(signum, frame):
    logging.info("Received exit signal. Setting exit event.")
    tornado_ioloop = ioloop.IOLoop.current()
    tornado_ioloop.add_callback_from_signal(tornado_ioloop.stop)


signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)


if __name__ == "__main__":
    app = make_tornado_web("ws_test")
    app.add_handlers(
        ".*$",
        [
            (r"/ws", WSHandler),
        ],
    )
    run_tornado_app(app)
