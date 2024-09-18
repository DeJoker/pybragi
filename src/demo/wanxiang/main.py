import os
from wanxiang.logic.config import Config
from base import consul_reg, log
import logging
logging.info(f"start")

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--srv_host", type=str, default="127.0.0.1")
parser.add_argument("--srv_port", type=int, default=0, help="srv_port")
parser.add_argument("--graph_file", type=str, default=f"{os.path.dirname(__file__)}/workflow/0830workflow_api-sdxl-lora.json",
                    help="graph_file")
parser.add_argument("--port", type=int, default=50010,
                        help="port")
args = parser.parse_args()

if not args.srv_port:
    args.srv_port = args.port-20000
Config.Port = args.port

from base import time_utils, errcode, base_handler
from base.species_queue import (
    PriorityQueue,
    set_global_priority_queue,
    global_exit_event,
    set_global_exit_event
)
set_global_priority_queue(PriorityQueue(800))
set_global_exit_event()

import signal, threading
from tornado import web, ioloop
from tornado.httpserver import HTTPServer
import asyncio

from wanxiang.logic import infer # 如果使用 from logic import infer 那么里面的g_engine在别的地方导入会有意想不到的not defined问题
from wanxiang.handlers import generate_sdxl

def handle_exit_signal(signum, frame):
    logging.info("Received exit signal. Setting exit event.")
    # consul_reg.delconsul2(Config.Name, Config.LocalHost, Config.Port)
    # 退出web server线程 先关闭生产线程
    tornado_ioloop = ioloop.IOLoop.current()
    tornado_ioloop.add_callback_from_signal(tornado_ioloop.stop)

    global_exit_event().set()  # 再用信号退出消费线程

signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)


def run_tornado_app(app: web.Application, port=8888):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    server1 = HTTPServer(app)
    server1.listen(port)

    ioloop.IOLoop.current().start()

if __name__ == "__main__":
    app = base_handler.make_tornado_web(Config.Name)

    # 初始化模型和comfyUI 并warmup
    engine = infer.Engine(args.srv_host, args.srv_port, args.graph_file)
    infer.init_engine(engine)
    infer.process_task({"prompt": "impasto,nijisusan, 1gril, masterpiece"})

    # 再启动队列消费
    process_thread = threading.Thread(target=infer.collect_and_process, args=())
    process_thread.start()

    app.add_handlers(
        ".*$",
        [
           (r"/generate_sdxl", generate_sdxl.Generator),
        ],
    )
    logging.info(f"server start, port:{args.port}")
    run_tornado_app(app, args.port)

    logging.info(f"server exit")
    process_thread.join()
