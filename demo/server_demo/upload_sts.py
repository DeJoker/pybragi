
import logging
import requests
import tornado, json

from pybragi.base.metrics import PrometheusMixIn
from pybragi.base.base_handler import CORSBaseHandler
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor


class UploadSts(PrometheusMixIn, CORSBaseHandler):
    executor = ThreadPoolExecutor(2)

    @run_on_executor
    def get(self):
        credential = {"key": "1234567890", "secret": "1234567890"}
        self.write({"ret": 1, "credential": credential})


class Echo2(PrometheusMixIn):
    executor = ThreadPoolExecutor(2)

    @run_on_executor
    def post(self):
        request_body = json.loads(self.request.body)
        return self.write(request_body)
    
    @run_on_executor
    def get(self):
        return self.write(str(self.request.arguments))
