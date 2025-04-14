
import logging
import requests
import tornado, json
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor

from pybragi.server.loadbalance import roundrobin, hash_balance
from pybragi.server.dao_server_discovery import get_server_online
from pybragi.base.metrics import PrometheusMixIn
from pybragi.base.hash import djb2_hash
from pybragi.base.base_handler import CORSBaseHandler


rvc_name = "rvc_infer"
seed_name = "seed_infer"


class ForwardTransmit(PrometheusMixIn, CORSBaseHandler):
    executor = ThreadPoolExecutor(40)

    @run_on_executor
    def get(self):
        path = self.request.path
        if path == "/v1/rvc/get_model_list":
            servers = get_server_online(rvc_name)
            host = roundrobin(servers)
            resp = requests.get(f"{host}/api/get_model_list", timeout=1)
            return self.write(resp.json())
        elif path == "/v1/seed/get_model_list":
            servers = get_server_online(seed_name)
            host = roundrobin(servers)
            resp = requests.get(f"{host}/api/get_model_list", timeout=1)
            return self.write(resp.json())
        return self.write({"ret": -1, "msg": "invalid request path"})

    @run_on_executor
    def post(self):
        path = self.request.path
        logging.info(f"{path} request:{self.request.body}")
        task = json.loads(self.request.body)
        mid = task.get("mid", "0")

        if "rvc" in path:
            servers = get_server_online(rvc_name)
            host = hash_balance(servers, mid)
        elif "seed" in path:
            servers = get_server_online(seed_name)
            host = hash_balance(servers, mid)
        else:
            return self.write({"ret": -1, "msg": "invalid request path"})
        

        if path == "/v1/rvc/load_model":
            resp = requests.post(f"{host}/api/load_model", json=task, timeout=10)
        elif path == "/v1/rvc/infer_rvc":
            resp = requests.post(f"{host}/api/infer_rvc", json=task, timeout=10)
        elif path == "/v1/seed/reference_audio":
            resp = requests.post(f"{host}/api/reference_audio", json=task, timeout=10)
        elif path == "/v1/seed/infer_seed":
            resp = requests.post(f"{host}/api/infer_seed", json=task, timeout=10)
        else:
            return self.write({"ret": -1, "msg": "invalid request path"})
        
        return self.write(resp.json())
        
