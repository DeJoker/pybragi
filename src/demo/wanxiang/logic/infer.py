from functools import partial
from io import BytesIO
import json
import logging
import os
import random
import telnetlib
import threading
import time
from copy import deepcopy
import traceback

from PIL import Image
import cv2
import numpy as np

from wanxiang.logic.config import Config
from logic.comfy_client import ComfyClient

import concurrent.futures
from typing import Callable

from base import consul_reg, errcode, time_utils
from base.metrics import get_metrics_manager
from base.species_queue import global_exit_event, global_priority_queue

from wanxiang.logic import upload_oss


class Engine:
    def __init__(self, addr: str, port: int, graph_file: str = ""):
        logging.info(f"start with {addr}:{port}, {graph_file}")
        self.addr = addr
        self.port = port
    
        self.detect_alive()
        self.comfy_client = self.start_client()
        # consul_reg.regconsul2(Config.Name, Config.LocalHost, Config.Port)
        self.comfyui_valid = True
        
        default_graph_file = graph_file
        with open(default_graph_file, 'r') as file:
            default_graph = json.loads(file.read())
        self.comfy_graph = default_graph

        # 预热

    def detect_alive(self):
        start_time = time.time()

        reConnect = False
        while True:
            try:
                if global_exit_event().is_set():
                    return False
                # 尝试连接
                tn = telnetlib.Telnet(self.addr, self.port, timeout=10)
                tn.close()  # 关闭连接
                if reConnect:
                    logging.error(f"重连间隔为: {round(time.time()-start_time, 3)}")
                get_metrics_manager().triton_down.labels(f"{self.addr}:{self.port}").set(0)
                return reConnect
            except Exception as e:
                self.comfyui_valid = False
                get_metrics_manager().triton_down.labels(f"{self.addr}:{self.port}").set(1)
                # 连接失败 关闭
                if not reConnect: # 输出一次
                    # consul_reg.delconsul2(Config.Name, Config.LocalHost, Config.Port)
                    logging.error(f"无法连接到 {self.addr}:{self.port} 错误信息：{e}")
                reConnect = True

            time.sleep(1)

    def ensure_alive(self):
        with threading.Lock():
            reConnect = self.detect_alive()
            if reConnect: # 重连才需要再注册
                timeout = 120.0
                self.comfy_client = self.start_client(timeout)
                filename = "/aigc-nas01/cyj/input/2378794341.png"
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    try:
                        future = executor.submit(self.generate_by_img, filename, 2378794341,
                                        )
                        future.result(timeout=timeout)
                    except:
                        logging.warning(f"restart comfyui timeout")
                
                # consul_reg.regconsul2(Config.Name, Config.LocalHost, Config.Port)
                self.comfyui_valid = True
            
            self.comfy_client = self.start_client()
            return reConnect
    
    def start_client(self, timeout=6):
        comfy_client = ComfyClient()
        n_tries = 5
        for i in range(n_tries):
            try:
                comfy_client.connect(listen=self.addr, port=self.port, timeout=timeout)
            except ConnectionRefusedError as e:
                logging.info(e)
                logging.info(f"({i + 1}/{n_tries}) Retrying...")
            else:
                break
            time.sleep(0.5)
        return comfy_client

    def generate_by_img(self, prompt="", neg_prompt="", batch_size=1, lora_config={}):
        self.ensure_alive()

        seed = random.randint(1, 2**63-1)

        comfy_graph = deepcopy(self.comfy_graph)
        comfy_graph["6"]["inputs"]["text"] = prompt
        comfy_graph["3"]["inputs"]["seed"] = seed
        comfy_graph["156"]["inputs"]['batch_size'] = batch_size
        comfy_graph["52"]["inputs"]['filename_prefix'] = f"susan-{seed}"
    
        if neg_prompt:
            comfy_graph["7"]["inputs"]["text"] = neg_prompt
        if lora_config:
            comfy_graph["154"]["inputs"].update(lora_config)

        images = self.comfy_client.get_images(comfy_graph, save_image_node="52")
        return images

g_engine: Engine
def init_engine(engine: Engine):
    global g_engine
    g_engine = engine

def get_engine():
    global g_engine
    return g_engine


def task_process_metrics(latency):
    service = get_metrics_manager().server_name
    get_metrics_manager().task_process_ms.labels(service).observe(latency*1000)


@time_utils.elapsed_time_callback(task_process_metrics)
def process_task(task):
    def metrics_record(name, et):
        get_metrics_manager().task_process_ms.labels(name).observe(et*1000)

    request_id = task.get("request_id", "")
    prompt = task.get("prompt", "")
    neg_prompt = task.get("neg_prompt", "")
    batch_size = task.get("num_image_per_prompt", 1)
    lora_paths = task.get("lora_paths", {})

    with time_utils.ElapseCtx(f"{request_id} comfyui generate", callback=partial(metrics_record, f"comfyui generate")):
        outputs = get_engine().generate_by_img(prompt, neg_prompt, batch_size, lora_paths)
    with time_utils.ElapseCtx(f"uplaod", callback=partial(metrics_record, "uplaod")):
        output_urls = []
        for output in outputs:
            ok, url = upload_oss.upload2(output)
            if ok:
                output_urls.append(url)
        
    logging.info(f"{request_id} to {output_urls}")
    return output_urls
        
def process_one(task = {}):
    try:
        get_engine().ensure_alive()
        return process_task(task)
    except Exception as e:
        logging.error(traceback.format_exc())
        reason = f"{task['request_id']} reason:{str(e)}"
        logging.error(reason)
        return reason
    except:
        logging.error(traceback.format_exc())
        reason = f"{task['request_id']} unknow error"
        logging.error(reason)
        return reason
    else:
        pass


executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
def collect_and_process():
    task_queue = global_priority_queue()
    loop = 0

    while True:
        task = {}
        try:
            # 优雅退出逻辑
            if global_exit_event().is_set() and task_queue.empty():
                logging.info(f"consumer exit")
                # sys.exit(1)
                break
            loop += 1
            if loop % 5 == 0:
                s1, s2 = task_queue.statistics()
                get_metrics_manager().task_queue_length.labels(Config.Name, 'priority').set(s1)
                get_metrics_manager().task_queue_length.labels(Config.Name, 'normal').set(s2)
            
            get_engine().ensure_alive()

            task = task_queue.get(timeout=0.1)
            if task is None:
                continue

            future = executor.submit(process_task, task)
            result = future.result(timeout=20) # 设置超时等待结果
        except Exception as e:
            logging.error(traceback.format_exc())
            if task:
                logging.error(f"{task['img_id']} reason:{str(e)}")
        except:
            logging.error(traceback.format_exc())
            if task:
                logging.error(f"{task['img_id']}")
        else:
            pass

    
