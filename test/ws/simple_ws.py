import asyncio
import queue
import random
import time
import traceback
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
    clients = {} # client -> ticket and ip
    client_to_task = {} # client -> task_id
    taskid_to_client = {} # task_id -> client

    def initialize(self):
        self.ioloop = ioloop.IOLoop.current()

    def on_close(self):
        logging.info(f"closed: {self.request.remote_ip}")
        task_id = WSHandler.client_to_task.pop(self)
        WSHandler.taskid_to_client.pop(task_id)
        WSHandler.clients.pop(self)
    
    async def open(self):
        logging.info(f"connected from {self.request.remote_ip}")

        ticker_str = self.get_query_argument("ticker", default=None)
        logging.info(f"ticker_str: {ticker_str}")
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
                WSHandler.clients[self] = {"ticket": ticket, "ip": self.request.remote_ip}
                super().open()
            else:
                logging.warning(f"Authentication failed for {self.request.remote_ip}. {ticket} error:{msg}. Closing.")
                self.close(code=1008, reason=f"Invalid authentication ticker, error: {msg}")
        except Exception as e:
            logging.error(f"Error during authentication for {self.request.remote_ip}: {e}. Closing.")
            self.close(code=1011, reason="Internal server error during authentication") # 1011: Internal Error
        return
    
    def check_origin(self, origin):
        # logging.info(f"connect from {origin}")
        return True
    
    def set_task_id(self, task_id):
        task_id = task_id.strip()
        if not task_id:
            logging.warning(f"task_id is empty")
            return False
        
        if WSHandler.client_to_task.get(self):
            logging.warning(f"task_id {task_id} already exists")
            return False
        
        logging.info(f"Binding connection {self} to task_id: {task_id}")
        WSHandler.client_to_task[self] = task_id
        WSHandler.taskid_to_client[task_id] = {
            "client": self,
            "ticket": WSHandler.clients[self]["ticket"],
            "ip": WSHandler.clients[self]["ip"],
            "send_buffer": queue.Queue(),
            "recv_buffer": queue.Queue(),
            "client_task_done": False,
            "vc_task_done": False,
        }
        # self.ioloop.add_callback(self._result_generated, task_id)
        self._result_generated(task_id)
        return True
        
    @run_on_executor
    def send_result_generated(self, task_id, data):
        header = proto_ws.Header(event=proto_ws.result_generated_event, task_id=task_id,)
        payload = proto_ws.AudioInfo(audio_size=len(data), audio_duration="00:00:05.23")
        request = proto_ws.Request(header=header, payload=payload)


        WSHandler.taskid_to_client[task_id]["send_buffer"].put((request.model_dump_json(), False))
        WSHandler.taskid_to_client[task_id]["send_buffer"].put((data, True))
        if WSHandler.taskid_to_client[task_id]["client_task_done"]:
            WSHandler.taskid_to_client[task_id]["vc_task_done"] = True

        time.sleep(random.randint(100, 300)/1000)

        # 将数据准备和写入操作都放在主事件循环中执行
        # self.ioloop.add_callback(
        #     self._result_generated, task_id, request.model_dump_json(), data
        # )
        return

    @run_on_executor
    def _result_generated(self, task_id):
        if task_id not in WSHandler.taskid_to_client:
            logging.warning(f"Task {task_id} not found")
            return
        
        send_buffer_queue: queue.Queue = WSHandler.taskid_to_client[task_id]["send_buffer"]
        while not WSHandler.taskid_to_client[task_id]["vc_task_done"] or not send_buffer_queue.empty():
            send_data, binary = send_buffer_queue.get()
            self.ioloop.add_callback(self.write_message, send_data, binary=binary)
            if binary:
                logging.info(f"Sent binary data for task {task_id}, size={len(send_data)} bytes")
            else:
                logging.info(f"Sent json data for task {task_id}, json={send_data}")


    @run_on_executor
    def send_task_finished(self, task_id):
        header = proto_ws.Header(event=proto_ws.task_finished_event, task_id=task_id,)
        payload = proto_ws.TaskFinished(source_audio_url="http://source.wav", target_audio_url="http://target.wav")
        request = proto_ws.Request(header=header, payload=payload)
        time.sleep(random.randint(100, 300)/1000)
        self.ioloop.add_callback(self.write_message, request.model_dump_json())
        return 

    @run_on_executor
    def send_audio_received(self, task_id, data):
        time.sleep(random.randint(100, 300)/1000)

        header = proto_ws.Header(event=proto_ws.audio_received_event, task_id=task_id,)
        payload = proto_ws.AudioInfo(audio_size=len(data), audio_duration="00:00:05.23")
        request = proto_ws.Request(header=header, payload=payload)
        # self.ioloop.add_callback(self.write_message, request.model_dump_json())
        return

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
                    task_started_message = proto_ws.Request(header=task_started_header, payload={}).model_dump_json()
                    self.write_message(task_started_message)
                elif header.action == proto_ws.append_audio_action:
                    payload = proto_ws.AudioInfo(**data["payload"])
                    logging.info(f"append-audio: {payload}")
                elif header.action == proto_ws.finish_task_action:
                    task_id = WSHandler.client_to_task[self]
                    WSHandler.taskid_to_client[task_id]["client_task_done"] = True
                    self.send_task_finished(task_id)
                else:
                    logging.info(f"unknown action: {header}")
                    return
            else:
                logging.info(f"received binary message, size: {len(message)} bytes")
                # json_message, binary_data = await self.send_result_generated(self.client_to_task[self], message)
                # self.write_message(json_message)
                # self.write_message(binary_data, binary=True)

                self.send_result_generated(self.client_to_task[self], message)
                
        except Exception as e:
            traceback.print_exc()
            ticker: ZyTicket = WSHandler.clients[self].get("ticket", ZyTicket(""))
            ip: str = WSHandler.clients[self].get("ip", "unknown")

            logging.error(f"user_id: {ticker.user_id}, ip: {ip}, error: {str(e)}")
            self.write_message(json.dumps({"error": str(e), "ip": ip}))
    
    
    
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50004)
    args = parser.parse_args()

    app = make_tornado_web("ws_test")
    app.add_handlers(
        ".*$",
        [
            (r"/ws", WSHandler),
        ],
    )
    run_tornado_app(app, args.port)
