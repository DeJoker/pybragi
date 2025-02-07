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
import netifaces


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

def system_gpu_memory():
    # return bytes
    allocated_bytes = 0
    cached_bytes = 0
    total_bytes = 0

    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            total_bytes = gpu.memoryTotal
            allocated_bytes = gpu.memoryUsed
    except ImportError:
        pass
    return allocated_bytes, cached_bytes, total_bytes

def process_gpu_memory():
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
    try:
        addrs = netifaces.ifaddresses(card_name)
        if netifaces.AF_INET in addrs:
            return addrs[netifaces.AF_INET][0]['addr']
        return "127.0.0.1"  # fallback to localhost if no IPv4 found
    except ValueError:  # eth0 not found
        return "127.0.0.1"

if __name__ == "__main__":
    print(system_memory_usage())
    print(process_memory_usage())

    print(system_gpu_memory())
    print(process_gpu_memory())
    
    print(get_disk_usage("."))