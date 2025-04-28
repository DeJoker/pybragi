from pybragi.base import log
import logging
from tornado.websocket import WebSocketHandler
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor

import json
from datetime import datetime
from pybragi.base import metrics
from pybragi.base.base_handler import make_tornado_web, run_tornado_app

class WSHandler(metrics.PrometheusMixIn, WebSocketHandler):
    executor = ThreadPoolExecutor(30)
    clients = set()
    
    @run_on_executor
    def open(self):
        logging.info(f"connected from {self.request.remote_ip}")
        WSHandler.clients.add(self)
        super().open()
    
    def check_origin(self, origin):
        # logging.info(f"connect from {origin}")
        return True
    
    @run_on_executor
    def on_message(self, message):
        logging.info(f"received: {type(message).__name__} length: {len(message) if message else 0}")
        
        try:
            if isinstance(message, str):
                data = json.loads(message)
                logging.info(f"received json message: {data}")
                
                response = {
                    "type": "json_response",
                    "received_data": data,
                    "timestamp": datetime.now().timestamp()
                }
                self.write_message(json.dumps(response))
            else:
                logging.info(f"received binary message, size: {len(message)} bytes")
                
                response = {
                    "type": "binary_received",
                    "size": len(message),
                    "timestamp": datetime.now().timestamp()
                }
                self.write_message(json.dumps(response))
                
        except Exception as e:
            logging.error(f"error: {str(e)}")
            self.write_message(json.dumps({"error": str(e)}))
    
    @run_on_executor
    def on_close(self):
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
