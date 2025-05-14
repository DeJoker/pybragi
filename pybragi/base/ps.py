import logging
from pathlib import Path
import shutil
from typing import Tuple, Union
import psutil
import os, gc
import time
from pybragi.model.utils import getGPUs, GPU

def system_memory_usage() -> Tuple[float, float]:
    memory = psutil.virtual_memory()
    
    total_gb = round(memory.total / (1024**3), 2)
    available_gb = round(memory.available / (1024**3), 2)
    
    return total_gb, available_gb

def process_memory_usage() -> float:
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024**2)
    return memory_mb

def system_gpu_memory(id: int = 0):
    # return MiB
    allocated_mb = 0
    free_mb = 0
    total_mb = 0

    try:
        gpus: list[GPU] = getGPUs()
        if gpus:
            gpu = gpus[id]
            total_mb = gpu.memoryTotal
            free_mb = gpu.memoryFree
            allocated_mb = gpu.memoryUsed
    except ImportError:
        pass
    return allocated_mb, free_mb, total_mb

def process_gpu_memory():
    import torch
    allocated, cached = 0, 0
    if hasattr(torch, 'cuda') and torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / (1024**2)
        cached = torch.cuda.memory_reserved() / (1024**2)
    elif hasattr(torch, 'hip') and torch.hip.is_available():
        # ROCm PyTorch supports AMD GPU
        allocated = torch.hip.memory_allocated() / (1024**2)  
        cached = torch.hip.memory_reserved() / (1024**2)
    return allocated, cached


def get_disk_usage(path: Union[str, Path]) -> Tuple[float, float, float]:
    try:
        path = Path(path)
        if path.is_file():
            path = path.parent
            
        total, used, free = shutil.disk_usage(path)
        
        total_gb = round(total / (1024**3), 2)
        used_gb = round(used / (1024**3), 2)
        free_gb = round(free / (1024**3), 2)
        
        return total_gb, used_gb, free_gb
        
    except OSError as e:
        raise OSError(f"无法获取路径 {path} 的磁盘使用情况: {e}")

def get_ipv4(card_name: str = "eth0"):
    import ifaddr
    
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        if adapter.name == card_name:
            for ip in adapter.ips:
                if ip.is_IPv4: # ip: ifaddr.IP
                    return ip.ip
    return "127.0.0.1"

if __name__ == "__main__":
    logging.info(f"eth0 ipv4: {get_ipv4()}")
    total, used, free = get_disk_usage('.')
    logging.info(f"disk usage: total: {total}GB, used: {used}GB, free: {free}GB")

    while True:
        total, available = system_memory_usage()
        logging.info(f"system memory: total: {total}GB, available: {available}GB")

        used_mb = process_memory_usage()
        logging.info(f"process memory: used: {used_mb:.2f}MB")

        allocated, free, total = system_gpu_memory()
        logging.info(f"system gpu memory: allocated: {allocated:.2f}MB, free: {free:.2f}MB, total: {total:.2f}MB")

        allocated, cached = process_gpu_memory()
        logging.info(f"process gpu memory: allocated: {allocated}MB, cached: {cached}MB")
        logging.info(f"--------------------------------------")
        time.sleep(1)