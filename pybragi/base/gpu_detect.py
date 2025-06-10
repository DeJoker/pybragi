import json
import time
import pynvml # pip install nvidia-ml-py
import logging
from collections import deque
import requests

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

def valid_memory_cards(mb: int):
    cards_tuple = []
    free_mb = get_free_memory()
    for i, free in enumerate(free_mb):
        if free > mb:
            cards_tuple.append((i, free))
    return cards_tuple

def continuous_valid_cards(mb=0, seq=2):
    items = valid_memory_cards(mb)
    cards, memroys = zip(*items)

    for i in range(len(cards)):
        if cards[i+seq-1] == cards[i]+seq-1:
            return cards[i:i+seq]
    return []

def valid_cards(mb=0, num=2):
    items = valid_memory_cards(mb)
    cards, memroys = zip(*items)

    if len(cards) >= num:
        return cards[:num]
    return []


gpu_util_deques = []
def gpu_util_queue(deviceCount=8, time_range=5*60, sample_interval=2):
    global gpu_util_deques
    if not gpu_util_deques:
        # gpu_util_deques = [deque(maxlen=time_range // sample_interval)] * deviceCount # 浅拷贝实际上是引用
        gpu_util_deques = [deque(maxlen=time_range // sample_interval) for _ in range(deviceCount)]  # 深拷贝 独立对象
    return gpu_util_deques


def record_gpu_utilty(sample_interval=2):
    pynvml.nvmlInit()
    deviceCount = pynvml.nvmlDeviceGetCount()
    gpu_util_deques = gpu_util_queue(deviceCount=deviceCount)
    print()

    while True:
        try:
            for i in range(deviceCount):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                util_rate = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util_deques[i].append(util_rate.gpu)

                average_gpu_util = sum(gpu_util_deques[i]) / len(gpu_util_deques[i])
                # print(f"Average GPU Utilization {i} over the last {len(gpu_util_deques[i])*sample_interval/60:.2f} minutes: {average_gpu_util:.2f}%")

            time.sleep(sample_interval)

        except KeyboardInterrupt:
            print("Stopped by User")


def get_gpu_utilty_prometheus(prometheus_url = "http://192.168.220.223:9090", query = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{Hostname="beijing-aigc-gpt-gpu02"}}[7d])'):
    end_time = int(time.time())

    url = f"{prometheus_url}/api/v1/query"
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
        logging.debug(f"{response.url} {response.text}")
        xx = json.loads(response.text)
        return xx
    else:
        logging.error(f"{response.url} {response.status_code} {response.text}")

if __name__ == '__main__':

    def test_local_detect():
        x = continuous_valid_cards(78000, 2)
        logging.info(x)
        x = continuous_valid_cards(78000, 3)
        logging.info(x)

        import threading
        threading.Thread(target=record_gpu_utilty, daemon=True).start()
        time.sleep(9)

        # get_gpu_utilty_prometheus()
        
        print("asdas")
        time.sleep(1)
        print("asdas end")
    
    def test_prometheus():
        get_gpu_utilty_prometheus('histogram_quantile(0.5, sum(rate(DCGM_FI_DEV_GPU_UTIL{Hostname="beijing-aigc-gpt-gpu02"}[7d])) by (gpu, le))')
    

    test_prometheus()
        
