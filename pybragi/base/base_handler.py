from pybragi.base import log
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
    executor = ThreadPoolExecutor(1)

    # https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.initialize
    def initialize(self, name=""):
        self.name = name

    def _log(self):
        return

    def log_request(self):
        return

    @run_on_executor
    def current(self):
        now = datetime.now()
        res = {
            "ret": 1,
            "errcode": 1,
            "data": {
                "name": self.name,
                "timestamp": int(now.timestamp()),
                "timestamp-str": now.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
        return res

    @gen.coroutine
    def get(self):
        res = yield self.current()
        self.write(res)

    @gen.coroutine
    def post(self):
        self.get()

class CORSBaseHandler(web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with, content-type, authorization")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        
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
            (r"/metrics", metrics.MetricsHandler),
        ]
    )
    return app

def run_tornado_app(app: web.Application, port=8888):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.listen(port)
    ioloop.IOLoop.current().start()


# python -m service.base.base_handler
if __name__ == "__main__":
    app = make_tornado_web(__file__)
    run_tornado_app(app)

