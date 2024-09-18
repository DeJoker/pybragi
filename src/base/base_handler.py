from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging
from tornado import web, gen, ioloop
from tornado.concurrent import run_on_executor

import json
from datetime import datetime
# from . import metrics
import metrics


class Echo(metrics.PrometheusMixIn):
    def post(self):
        logging.info(f"{self.request.body.decode('unicode_escape')}")
        return self.write(self.request.body)
    
    def get(self):
        logging.info(f"{str(self.request)}")
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


def make_tornado_web(service=""):
    metrics.register_metrics(name=service)
    app = web.Application(
        [
            (r"/echo", Echo),
            (r"/healthcheck", HealthCheckHandler, dict(name=service)),
            (r"/metrics", metrics.MetricsHandler),
        ]
    )
    # app.add_handlers(r"/metrics", metrics.MetricsHandler)
    return app

# python -m service.base.base_handler
if __name__ == "__main__":
    import asyncio
    from tornado.httpserver import HTTPServer

    def run_tornado_app(app: web.Application, port=8888):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        server1 = HTTPServer(app)
        server1.listen(port)
        ioloop.IOLoop.current().start()
    
    app = make_tornado_web(__file__)
    run_tornado_app(app)

