import os, signal

import logging
from datetime import datetime
import threading
from typing import Callable, Optional
from tornado import web, ioloop

import asyncio
from pybragi.base import metrics
from pybragi.bragi_config import BragiConfig
from pybragi.base.shutdown import global_exit_event


class Echo(metrics.PrometheusMixIn):
    def post(self):
        # logging.info(f"{self.request.body.decode('unicode_escape')}")
        return self.write(self.request.body)
    
    def get(self):
        # logging.info(f"{str(self.request)}")
        return self.write(str(self.request.arguments))


#  health 超时请求最可能的问题是 对端服务阻塞 所以应该检查服务方ioloop等
# 不要质疑接口的正确性 如果检查失败 说明服务有问题
class HealthCheckHandler(metrics.PrometheusMixIn):
    # https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.initialize
    def initialize(self, name=""):
        self.name = name

    def _log(self):
        if self.request.request_time() > 0.002:
            super()._log()
        return

    def log_request(self):
        return

    def current(self):
        now = datetime.now()
        res = {
            "ret": 1,
            "errcode": 1,
            "data": {
                "name": self.name,
                "timestamp": int(now.timestamp()),
                "timestamp-str": now.strftime("%Y-%m-%d %H:%M:%S.%f"),
            },
        }
        return res

    async def get(self):
        res = self.current()
        self.write(res)
        self.finish()

    async def post(self):
        res = self.current()
        self.write(res)
        self.finish()

class CORSBaseHandler(web.RequestHandler):
    origin="*"
    headers="*"
    # headers="x-requested-with, content-type, authorization, x-user-id, x-token"
    methods="GET, POST, PUT, DELETE, OPTIONS"
    
    # set_default_headers -> initialize -> prepare # set_default_headers 在 initialize 之前调用
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", self.origin)
        self.set_header("Access-Control-Allow-Headers", self.headers)
        self.set_header("Access-Control-Allow-Methods", self.methods)
        
    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()


def make_tornado_web(service: str, big_latency=False, kafka=False):
    metrics_manager = metrics.MetricsManager(service, big_latency, kafka)
    metrics.register_metrics(metrics_manager)
    app = web.Application(
        [
            (r"/echo", Echo),
            (r"/healthcheck", HealthCheckHandler, dict(name=service)),
            (r"/health", HealthCheckHandler, dict(name=service)),
            (r"/metrics", metrics.MetricsHandler),
        ]
    )
    return app

def run_tornado_app(app: web.Application, port=8888):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # asyncio.get_event_loop()
    app.listen(port)

    from pybragi.base import ps
    ipv4 = ps.get_ipv4()
    logging.info(f"Tornado app started on port http://{ipv4}:{port}")
    ioloop.IOLoop.current().start()

# 1. 无法退出可能是启动的 threading join.  失效其中一个原因是   使用了 finally: continue  否则线程无法退出
# 2. 最好在 main 结束打印一个日志 有日志就是正确退出
def handle_exit_signal(signum, frame, async_func: Optional[Callable], timeout):
    logging.info("Received exit signal. Setting exit event.")
    loop = asyncio.get_event_loop()

    async def timeout_exit(timeout):
        await asyncio.sleep(timeout)
        logging.info(f"timeout {timeout} force exit")
        os._exit(1)

    if async_func:
        loop.call_soon_threadsafe(loop.create_task, async_func())
    
    loop.call_soon_threadsafe(loop.create_task, timeout_exit(timeout))


def register_exit_handler(async_func: Optional[Callable] = None, timeout = BragiConfig.ForceExitTimeout):
    signal.signal(signal.SIGINT, lambda signum, frame: handle_exit_signal(signum, frame, async_func, timeout))
    signal.signal(signal.SIGTERM, lambda signum, frame: handle_exit_signal(signum, frame, async_func, timeout))



# python -m service.base.base_handler --origin="127.0.0.1"
if __name__ == "__main__":
    from functools import partial
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--origin", type=str, default="*")
    args = parser.parse_args()


    async def exit_func(start_time: datetime):
        global_exit_event().set()
        while metrics.active_handlers:
            for handler_type, handlers in metrics.active_handlers.items():
                logging.info(f"{handler_type} length: {len(handlers)}")
                for handler in handlers:
                    handler: metrics.PrometheusMixIn
                    logging.info(f"handler: {handler.bragi_connection_info()}")
            await asyncio.sleep(0.5)
        
        logging.info(f"server start_time: {start_time}, duration: {datetime.now() - start_time}")
        ioloop.IOLoop.current().stop()
    
    register_exit_handler(partial(exit_func, datetime.now()))

    class RootHandler(CORSBaseHandler, metrics.PrometheusMixIn):

        def bragi_connection_info(self):
            base_info = super().bragi_connection_info()
            
            user_id = self.current_user.id if self.current_user else "anonymous"
            extra_info = f"user_id:{user_id}"

            return f"{base_info} {extra_info}"
        
        async def get(self):
            self.write("hello world")
        
        async def post(self):
            await asyncio.sleep(5)
            self.write("hello world")

    CORSBaseHandler.origin = args.origin # 这里可以修改 origin

    app = make_tornado_web(__file__)
    app.add_handlers(".*$",
    [
        (r"/", RootHandler),
    ])

    run_tornado_app(app, args.port)
    logging.info("Tornado app done")

