from io import BytesIO
import logging
import os
import time
import requests
from typing import Union
import json
import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import urllib.request
import urllib.parse
import uuid

class ComfyClient:
    def connect(self,
                listen: str = '127.0.0.1',
                port: Union[str, int] = 8189,
                client_id: str = str(uuid.uuid4()),
                timeout = 10.0,
                workflow_name=""
                ):
        self.workflow_name = workflow_name
        self.client_id = client_id
        self.server_address = f"{listen}:{port}"
        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))
        ws.settimeout(timeout)
        self.ws = ws

    def queue_prompt(self, prompt, workflow_name):
        p = {"prompt": prompt, "client_id": self.client_id, "extra_data":{"workflow_name": workflow_name}}
        url_addr = "http://{}/prompt".format(self.server_address)
        resp = requests.post(url=url_addr, json=p)
        if resp.ok:
            out_json = json.loads(resp.text)
            return out_json['prompt_id']
        else:
            logging.error(f"{resp.status_code} {resp.text}")
        return ""


    def get_history(self, prompt_id):
        while True:
            try:
                with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id), timeout=0.5) as response:
                    history_dict = json.loads(response.read())
                    history = history_dict[prompt_id]
                    return history
            except:
                time.sleep(0.1)
                continue
            

    def get_images(self, graph, save_image_node: str):
        output_images = {}
        prompt_id = self.queue_prompt(graph, self.workflow_name)
        if prompt_id == "":
            prompt_id = self.queue_prompt(graph, self.workflow_name)
        if prompt_id == "":
            return output_images
        logging.info(f"queue prompt_id:{prompt_id}")
        while True:
            try:
                out = self.ws.recv()
            except:
                logging.warning(f"{prompt_id} timeout")
                break
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        logging.info(f"rev prompt_id:{message}")
                        break
            else:
                continue

        image_paths = []
        history = self.get_history(prompt_id)
        try:
            for output in history['outputs'][save_image_node]['images']:
                fpath = os.path.join("/data2/rwy/wangxiang_ComfyUI/output", output["subfolder"], output['filename'])
                image_paths.append(fpath)

            if len(image_paths) == 0 or image_paths[0] == 0:
                raise Exception("generate error")
        except:
            logging.warning(f"history={history} message={message}")
        return image_paths

