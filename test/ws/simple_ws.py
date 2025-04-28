import random
import time
from pybragi.base import log
import logging
from tornado.websocket import WebSocketHandler
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor

import json
import proto_ws
from datetime import datetime
from pybragi.base import metrics
from pybragi.base.base_handler import make_tornado_web, run_tornado_app

class WSHandler(metrics.PrometheusMixIn, WebSocketHandler):
    executor = ThreadPoolExecutor(30)
    clients = set()
    client_tasks = {}
    
    async def open(self):
        logging.info(f"connected from {self.request.remote_ip}")
        WSHandler.clients.add(self)
        super().open()
    
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

        header = proto_ws.Header(event="result-generated", task_id=task_id,)
        payload = proto_ws.AudioGenerated(audio_size=len(data), audio_duration="00:00:05.23")
        request = proto_ws.Request(header=header, payload=payload)
        # self.write_message(request.model_dump_json())

        # self.write_message(data)
        return request.model_dump_json(), data

    @run_on_executor
    def send_task_finished(self, task_id):
        time.sleep(random.randint(100, 300)/1000)

        header = proto_ws.Header(event="task-finished", task_id=task_id,)
        payload = proto_ws.TaskFinished(source_audio_url="http://source.wav", target_audio_url="http://target.wav")
        request = proto_ws.Request(header=header, payload=payload)
        # self.write_message(request.model_dump_json())
        return request.model_dump_json()


    def send_message(self, message, binary=False):
        self.write_message(message, binary=binary)

    async def on_message(self, message):
        # logging.info(f"received: {type(message).__name__} length: {len(message) if message else 0}")
        
        try:
            if isinstance(message, str):
                data = json.loads(message)
                header = proto_ws.Header(**data["header"])
                if header.action == "run-task":
                    payload = proto_ws.RunTask(**data["payload"])
                    logging.info(f"run-task: {payload}")
                    self.set_task_id(header.task_id)
                elif header.action == "append-audio":
                    payload = proto_ws.AudioGenerated(**data["payload"])
                    logging.info(f"append-audio: {payload}")
                elif header.action == "finish-task":
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
    
    


if __name__ == "__main__":
    app = make_tornado_web("ws_test")
    app.add_handlers(
        ".*$",
        [
            (r"/ws", WSHandler),
        ],
    )
    run_tornado_app(app)
