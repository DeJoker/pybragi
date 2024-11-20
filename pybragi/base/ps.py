from pathlib import Path
import shutil
from typing import Tuple, Union
import psutil
import torch
import os

def system_memory_usage() -> Tuple[float, float]:
    memory = psutil.virtual_memory()
    
    total_gb = round(memory.total / (1024**3), 2)
    available_gb = round(memory.available / (1024**3), 2)
    
    return total_gb, available_gb

def process_memory_usage() -> float:
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    return memory_mb

def system_gpu_memory():
    allocated = 0
    cached = 0
    total = None

    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            total = gpu.memoryTotal
            allocated = gpu.memoryUsed
    except ImportError:
        pass
    return allocated, cached, total

def process_gpu_memory():
    if hasattr(torch, 'cuda') and torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024 / 1024
        cached = torch.cuda.memory_reserved() / 1024 / 1024
    elif hasattr(torch, 'hip') and torch.hip.is_available():
        # ROCm PyTorch supports AMD GPU
        allocated = torch.hip.memory_allocated() / 1024 / 1024  
        cached = torch.hip.memory_reserved() / 1024 / 1024
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


if __name__ == "__main__":
    print(system_memory_usage())
    print(process_memory_usage())

    print(system_gpu_memory())
    print(process_gpu_memory())
    
    print(get_disk_usage("."))