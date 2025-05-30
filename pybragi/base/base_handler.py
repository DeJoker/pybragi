import signal

import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tornado import web, gen, ioloop
from tornado.concurrent import run_on_executor

import asyncio
from datetime import datetime
from pybragi.base import metrics


class Echo(metrics.PrometheusMixIn):
    def post(self):
        # logging.info(f"{self.request.body.decode('unicode_escape')}")
        return self.write(self.request.body)
    
    def get(self):
        # logging.info(f"{str(self.request)}")
        return self.write(str(self.request.arguments))


class HealthCheckHandler(metrics.PrometheusMixIn):
    executor = ThreadPoolExecutor(5)

    # https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.initialize
    def initialize(self, name=""):
        self.name = name

    def _log(self):
        # logging.info(f"{self.request.request_time()}")
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

    @run_on_executor
    def get(self):
        res = self.current()
        self.write(res)

    @run_on_executor
    def post(self):
        res = self.current()
        self.write(res)

class CORSBaseHandler(web.RequestHandler):
    origin="*"
    headers="x-requested-with, content-type, authorization, x-user-id, x-token"
    methods="GET, POST, PUT, DELETE, OPTIONS"
    
    def initialize(self, *args, **kwargs):
        logging.info(f"initialize: {args} {kwargs}, this after set_default_headers so not work")

    # set_default_headers 在 initialize 之前调用
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
    app.listen(port)

    from pybragi.base import ps
    ipv4 = ps.get_ipv4()
    logging.info(f"Tornado app started on port http://{ipv4}:{port}")
    ioloop.IOLoop.current().start()


def base_handle_exit_signal(signum, frame):
    logging.info("Received exit signal. Setting exit event.")
    tornado_ioloop = ioloop.IOLoop.current()
    tornado_ioloop.add_callback_from_signal(tornado_ioloop.stop)



# python -m service.base.base_handler --origin="127.0.0.1"
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--origin", type=str, default="*")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, base_handle_exit_signal)
    signal.signal(signal.SIGTERM, base_handle_exit_signal)

    class RootHandler(CORSBaseHandler):
        def get(self):
            self.write("hello world")

    CORSBaseHandler.origin = args.origin # 这里可以修改 origin

    app = make_tornado_web(__file__)
    app.add_handlers(".*$",
    [
        (r"/", RootHandler, dict(methods="GET")), # 在这里 init 不生效  可以 curl 请求发现
    ])

    run_tornado_app(app, args.port)

