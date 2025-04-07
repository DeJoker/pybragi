import inspect
import logging
from pathlib import Path
import shutil
from typing import Tuple, Union
import psutil
import torch
import os, gc
import contextlib
from typing import Dict


def log_gpu_memory(tag=""):
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**2
        reserved = torch.cuda.memory_reserved() / 1024**2
        logging.info(f"[{tag}] - Allocated: {allocated:.2f}MB, Reserved: {reserved:.2f}MB")


class MemoryTracker:
    def __init__(self):
        self.tensor_counts: Dict[str, int] = {}
        
    @contextlib.contextmanager
    def track_memory(self, tag: str):
        # 记录初始状态
        torch.cuda.synchronize()
        used_start = torch.cuda.memory_allocated()
        tensors_start = len([obj for obj in gc.get_objects() 
                           if torch.is_tensor(obj) and obj.device.type == 'cuda'])
        
        yield
        
        # 记录结束状态
        torch.cuda.synchronize() 
        used_end = torch.cuda.memory_allocated()
        tensors_end = len([obj for obj in gc.get_objects()
                          if torch.is_tensor(obj) and obj.device.type == 'cuda'])
        
        # 打印详细信息
        print(f"\n=== Memory Track: {tag} ===")
        print(f"GPU Memory change: {(used_end-used_start)/1024**2:.2f}MB")
        print(f"CUDA Tensor count change: {tensors_end-tensors_start}")
        
        # 如果发现内存增长,打印所有存活的张量
        if used_end > used_start:
            print("\nActive CUDA Tensors:")
            for obj in gc.get_objects():
                if torch.is_tensor(obj) and obj.device.type == 'cuda' and obj.numel() > 1024**2:
                    print(f"- {obj.shape}, {obj.dtype}, "
                          f"{obj.numel() / 1024**2:.2f}MB")


import torch.nn as nn

# 无操作上下文管理器 用于占位 替换其他profile防止重新换行
class NoOpContext:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self  
    def __exit__(self, *args): pass


class EnhancedMemoryTracker:
    def __init__(self):
        self.tensor_counts = {}
        self.hooks = []
        
    def _add_module_hooks(self, module: nn.Module, prefix=""):
        """为模块添加前向传播钩子来跟踪张量创建"""
        def hook_fn(module, input, output):
            if isinstance(output, torch.Tensor):
                module_name = prefix + "/" + module.__class__.__name__
                size_mb = output.element_size() * output.nelement() / 1024**2
                print(f"Module {module_name} output: {output.shape}, {size_mb:.2f}MB")
                
        for name, child in module.named_children():
            child_prefix = f"{prefix}/{name}" if prefix else name
            hook = child.register_forward_hook(hook_fn)
            self.hooks.append(hook)
            self._add_module_hooks(child, child_prefix)

    def _remove_hooks(self):
        """移除所有钩子"""
        for hook in self.hooks:
            hook.remove()
        self.hooks.clear()

    @contextlib.contextmanager
    def track_memory(self, tag: str, model=None):
        torch.cuda.synchronize()
        used_start = torch.cuda.memory_allocated()
        
        # 记录初始张量和添加钩子
        initial_tensors = {id(obj): obj for obj in gc.get_objects() 
                          if torch.is_tensor(obj) and obj.device.type == 'cuda'}
        
        if model is not None:
            self._add_module_hooks(model)
        
        try:
            yield
        finally:
            torch.cuda.synchronize()
            used_end = torch.cuda.memory_allocated()
            
            # 找出新创建的张量
            current_tensors = {id(obj): obj for obj in gc.get_objects() 
                              if torch.is_tensor(obj) and obj.device.type == 'cuda'}
            new_tensors = {id_: tensor for id_, tensor in current_tensors.items() 
                          if id_ not in initial_tensors}
            
            print(f"\n=== Memory Track: {tag} ===")
            print(f"GPU Memory change: {(used_end-used_start)/1024**2:.2f}MB")
            print(f"New CUDA Tensors: {len(new_tensors)}")
            
            if new_tensors:
                print("\nNew Tensors Created:")
                for tensor_id, tensor in new_tensors.items():
                    # 尝试从模型结构推断张量来源
                    shape_str = str(tensor.shape)
                    if shape_str == "[1, 2, 3690, 3690]":
                        source = "Possible Attention Matrix"
                    elif any(x in shape_str for x in ["1152", "384", "192"]):
                        source = "Possible Conv Layer Output"
                    else:
                        source = "Unknown Source"
                        
                    size_mb = tensor.element_size() * tensor.nelement() / 1024**2
                    print(f"- {source}: {tensor.shape}, {tensor.dtype}, {size_mb:.2f}MB")
            
            # 移除钩子
            self._remove_hooks()

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


###########################################

from subprocess import Popen, PIPE
import os
import platform



class GPU:
    def __init__(self, ID, uuid, load, memoryTotal, memoryUsed, memoryFree, driver, gpu_name, serial, display_mode, display_active, temp_gpu):
        self.id = ID
        self.uuid = uuid
        self.load = load
        self.memoryUtil = float(memoryUsed)/float(memoryTotal)
        self.memoryTotal = memoryTotal
        self.memoryUsed = memoryUsed
        self.memoryFree = memoryFree
        self.driver = driver
        self.name = gpu_name
        self.serial = serial
        self.display_mode = display_mode
        self.display_active = display_active
        self.temperature = temp_gpu

def safeFloatCast(strNumber):
    try:
        number = float(strNumber)
    except ValueError:
        number = float('nan')
    return number

def getGPUs():
    creationflags = 0
    if platform.system() == "Windows":
        from subprocess import CREATE_NO_WINDOW
        creationflags = CREATE_NO_WINDOW
        
        # If the platform is Windows and nvidia-smi 
        # could not be found from the environment path, 
        # try to find it from system drive with default installation path
        nvidia_smi = shutil.which('nvidia-smi')
        if nvidia_smi is None:
            nvidia_smi = "%s\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe" % os.environ['systemdrive']
    else:
        nvidia_smi = "nvidia-smi"
	
    # Get ID, processing and memory utilization for all GPUs
    try:
        p = Popen([nvidia_smi,"--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu", "--format=csv,noheader,nounits"], 
                  stdout=PIPE, creationflags=creationflags)
        stdout, stderror = p.communicate()
    except:
        return []
    output = stdout.decode('UTF-8')
    # output = output[2:-1] # Remove b' and ' from string added by python
    #print(output)
    ## Parse output
    # Split on line break
    lines = output.split(os.linesep)
    #print(lines)
    numDevices = len(lines)-1
    GPUs = []
    for g in range(numDevices):
        line = lines[g]
        #print(line)
        vals = line.split(', ')
        #print(vals)
        for i in range(12):
            # print(vals[i])
            if (i == 0):
                deviceIds = int(vals[i])
            elif (i == 1):
                uuid = vals[i]
            elif (i == 2):
                gpuUtil = safeFloatCast(vals[i])/100
            elif (i == 3):
                memTotal = safeFloatCast(vals[i])
            elif (i == 4):
                memUsed = safeFloatCast(vals[i])
            elif (i == 5):
                memFree = safeFloatCast(vals[i])
            elif (i == 6):
                driver = vals[i]
            elif (i == 7):
                gpu_name = vals[i]
            elif (i == 8):
                serial = vals[i]
            elif (i == 9):
                display_active = vals[i]
            elif (i == 10):
                display_mode = vals[i]
            elif (i == 11):
                temp_gpu = safeFloatCast(vals[i]);
        GPUs.append(GPU(deviceIds, uuid, gpuUtil, memTotal, memUsed, memFree, driver, gpu_name, serial, display_mode, display_active, temp_gpu))
    return GPUs  # (deviceIds, gpuUtil, memUtil)



##########################################


def system_gpu_memory():
    # return bytes
    allocated_bytes = 0
    cached_bytes = 0
    total_bytes = 0

    try:
        gpus = getGPUs()
        if gpus:
            gpu = gpus[0]
            total_bytes = gpu.memoryTotal
            allocated_bytes = gpu.memoryUsed
    except ImportError:
        pass
    return allocated_bytes, cached_bytes, total_bytes

def process_gpu_memory():
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
    print(get_ipv4())
    print(system_memory_usage())
    print(process_memory_usage())

    while True:
        print(system_gpu_memory())
    print(process_gpu_memory())
    
    print(get_disk_usage("."))