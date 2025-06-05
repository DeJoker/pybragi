import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from tornado.concurrent import run_on_executor

from pybragi.base.metrics import PrometheusMixIn, StreamMetrics

from pybragi.server import dao_server_discovery
from pybragi.server.loadbalance import roundrobin, hash_balance



class Models(PrometheusMixIn):
    executor = ThreadPoolExecutor(5)

    def initialize(self, openai_type: str, get_models: Callable):
        self.openai_type = openai_type
        self.get_models = get_models
    
    @run_on_executor
    def get(self):
        ret = {
            "object": "list",
            "data": []
        }
        ret["data"] = self.get_models()

        # lists = dao_server_discovery.get_all_server(self.openai_type)
        # list_names = [item["name"] for item in lists if item["status"] == "online"]
        # for name in set(list_names):
        #     ret["data"].append({
        #         "id": name,
        #         "object": "model",
        #     })

        self.write(ret)
        return
