
import sys, os
os.environ["PROJECT_ENV"] = "test"
sys.path.append(os.path.abspath('.')) # loads the current directory to Python path
# sys.path.append(os.getcwd())

from pybragi.base import log
import logging


import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=37000, help="port")
args = parser.parse_args()

from config import Config
Config.Name = "rvc_infer"
Config.Port = args.port
logging.info(f"Config: {vars(Config)}")


import upload_sts
import forward_transmit

from pybragi.base import base_handler, ps
from pybragi.base.species_queue import (
    global_exit_event
)
from pybragi.server.dao_server_discovery import register_server, unregister_server

global_exit_event()

import signal, threading
from tornado import web, ioloop
from tornado.httpserver import HTTPServer
import asyncio
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor
from pybragi.base.base_handler import CORSBaseHandler

def handle_exit_signal(signum, frame):
    logging.info("Received exit signal. Setting exit event.")
    if Config.Online:
        unregister_server(ps.get_ipv4(), Config.Port, Config.Name)
    # 退出web server线程 先关闭生产线程
    tornado_ioloop = ioloop.IOLoop.current()
    tornado_ioloop.add_callback_from_signal(tornado_ioloop.stop)

    global_exit_event().set()  # 再用信号退出消费线程


signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)


def run_tornado_app(app: web.Application, port=37000):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    server1 = HTTPServer(app)
    server1.listen(port)

    if Config.Online:
        register_server(ps.get_ipv4(), Config.Port, Config.Name)

    ioloop.IOLoop.current().start()


class RootHandler(CORSBaseHandler):
    executor = ThreadPoolExecutor(4)
    
    def _log(self):
        return

    def log_request(self):
        return
    
    @run_on_executor
    def get(self):
        self.write("hello world")


if __name__ == "__main__":
    app = base_handler.make_tornado_web(Config.Name)

    app.add_handlers(
        ".*$",
        [
            (r"/api/upload_sts", upload_sts.UploadSts),
            (r"/api/echo2", upload_sts.Echo2),

            (r"/v1/rvc/get_model_list", forward_transmit.ForwardTransmit),
            (r"/v1/rvc/load_model", forward_transmit.ForwardTransmit),
            (r"/v1/rvc/infer_rvc", forward_transmit.ForwardTransmit),
        ],
    )
    logging.info(f"server start, port:{Config.Port}")
    run_tornado_app(app, Config.Port)

    logging.info(f"server exit")
