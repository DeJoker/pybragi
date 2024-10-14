import threading
import time
import pynvml # pip install nvidia-ml-py
import logging
from collections import deque

import requests
from responses import target

def get_free_memory():
    free_mb = []
    pynvml.nvmlInit()
    deviceCount = pynvml.nvmlDeviceGetCount()
    for i in range(deviceCount):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        name = pynvml.nvmlDeviceGetName(handle)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        logging.info(f"GPU {i} ({name}): {info.free // 1024**2} MB free out of {info.total // 1024**2} MB")
        free_mb.append(info.free // 1024**2)

    pynvml.nvmlShutdown()
    return free_mb


def valid_memory_card(mb: int):
    free_mb = get_free_memory()
    for i, free in enumerate(free_mb):
        if free > mb:
            return i, free_mb
    return -1, free_mb


def record_gpu_utilty():
    time_range = 3 * 60  # 5 minutes
    sample_interval = 3  # 5 seconds
    pynvml.nvmlInit()
    deviceCount = pynvml.nvmlDeviceGetCount()
    gpu_util_deques = [deque(maxlen=time_range // sample_interval)] * deviceCount

    while True:
        try:
            for i in range(deviceCount):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                util_rate = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util_deques[i].append(util_rate.gpu)

                average_gpu_util = sum(gpu_util_deques[i]) / len(gpu_util_deques[i])
                print(f"Average GPU Utilization {i} over the last {len(gpu_util_deques[i])*3 / 60} minutes: {average_gpu_util:.2f}%")

                time.sleep(sample_interval)

        except KeyboardInterrupt:
            print("Stopped by User")

    pynvml.nvmlShutdown()


threading.Thread(target=record_gpu_utilty, daemon=True).start()
time.sleep(9)

def get_gpu_utilty_prometheus():
    PROMETHEUS = "http://192.168.220.223:9090"
    end_time = int(time.time())
    # 注释掉的部分返回的是每个时间点的结果
    # query = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{host="beijing-aigc-gpt-gpu02"}}[{start_time}s:{end_time}s])'
    query = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{host="beijing-aigc-gpt-gpu02"}}[5m])'

    # url = f"{PROMETHEUS}/api/v1/query_range"
    url = f"{PROMETHEUS}/api/v1/query"
    params = {
        "query": query,
        # "start": end_time - 5 * 60,
        # "end": end_time,
        # "step": "15",  # 以15秒为步长进行采样
        "time": end_time,
    }

    # 发送请求
    response = requests.get(url, params=params)
    if response.ok:
        logging.info(f"{response.url} {response.text}")
    else:
        logging.info(f"{response.url} {response.status_code} {response.text}")

if __name__ == '__main__':
    from service.base import log
    get_gpu_utilty_prometheus()
    
    print("asdas")
    time.sleep(1)
    print("asdas end")
