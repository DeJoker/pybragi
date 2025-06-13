from datetime import datetime
from pybragi.base import time_utils
from typing import Any, Optional, Callable
from contextlib import contextmanager
import heapq
from threading import Lock, Thread
import time
import logging
import weakref


def move_model_to_device(model: Any, device: str):
    model = model.to(device)
    
    if not hasattr(model, "parameters"):
        return model

    for param in model.parameters():
        param.data = param.data.to(device)
    if device == "cpu":
        if not hasattr(model, "buffers"):
            return model
        
        for buffer in model.buffers():
            buffer.data = buffer.data.to(device)
    
    # torch.cuda.synchronize()
    return model

def check_model_device(model: Any):
    # torch.Tensor
    if hasattr(model, "device"):
        return str(model.device)
    
    # torch.nn.Module
    if not hasattr(model, "parameters"):
        return "cpu" 

    return str(next(model.parameters()).device)

class ModelWrapper:
    def __init__(self, model: Any):
        self.model = model
        self.last_used = time.time()
    
    def __lt__(self, other):
        # Reverse comparison for max heap (most recent first)
        return self.last_used > other.last_used
    
class LRUCacheModelQueue:
    _weakref_queue = weakref.WeakSet()
    _cleanup_thread: Optional[Thread] = None

    def __init__(self, device: Any, name="hubert", move_to_cpu=100, time_to_live=600, min_reverse_length=2):
        self.heap = []  # Priority queue using heapq
        self.lock = Lock()
        self.device = device
        self.name = name
        self.move_to_cpu = move_to_cpu
        self.time_to_live = time_to_live
        self.min_reverse_length = min_reverse_length

        LRUCacheModelQueue._weakref_queue.add(self)
        logging.info(f"{self}")

        # Start cleanup thread
        if LRUCacheModelQueue._cleanup_thread is None:
            LRUCacheModelQueue._cleanup_thread = Thread(target=LRUCacheModelQueue._cleanup_loop, daemon=True)
            LRUCacheModelQueue._cleanup_thread.start()
    

    def __str__(self):
        return f"LRUCacheModelQueue(device={self.device}, name={self.name}, move_to_cpu={self.move_to_cpu}, time_to_live={self.time_to_live}, min_reverse_length={self.min_reverse_length})"

    def add_model(self, model):
        with self.lock, time_utils.ElapseCtx("add_model", gt=0.01):
            wrapper = ModelWrapper(model)
            heapq.heappush(self.heap, wrapper)
    

    def model_length(self):
        with self.lock, time_utils.ElapseCtx("model_length", gt=0.01):
            return len(self.heap)

    @contextmanager
    def get_model(self, final_func: Optional[Callable] = None):
        with self.lock, time_utils.ElapseCtx("get_model", gt=0.01):
            if not self.heap:
                # todo: add model
                raise TimeoutError(f"{self.name} No models available")
            wrapper = heapq.heappop(self.heap)

        wrapper.model = move_model_to_device(wrapper.model, self.device)
        try:
            yield wrapper.model
        finally:
            if final_func:
                final_func()
            with self.lock, time_utils.ElapseCtx("get_model", gt=0.01):
                # wrapper.model = move_model_to_device(wrapper.model, "cpu")
                wrapper.last_used = time.time()
                heapq.heappush(self.heap, wrapper)
    
    def hold_model(self):
        with self.lock, time_utils.ElapseCtx("hold_model", gt=0.01):
            if not self.heap:
                raise TimeoutError(f"{self.name} No models available")
            wrapper = heapq.heappop(self.heap)
        
        return wrapper.model
    
    @classmethod
    def _cleanup_loop(cls):
        while True:
            for cache in cls._weakref_queue:
                cache._cleanup()
            time.sleep(1)
    
    def _cleanup(self):
        current_time = time.time()
        with self.lock, time_utils.ElapseCtx("cleanup", gt=0.09): # cleanup cost: 0.093s
            sorted_models = sorted(self.heap, key=lambda w: w.last_used, reverse=True)

            move_to_cpu_models = [w for w in sorted_models if current_time - w.last_used > self.move_to_cpu and check_model_device(w.model) != "cpu"]
            for model in move_to_cpu_models:
                model: ModelWrapper
                pretty_time = datetime.fromtimestamp(model.last_used).strftime('%Y-%m-%d %H:%M:%S.%f')
                model.model = move_model_to_device(model.model, "cpu")
                logging.info(f"move {self.name} model to cpu, last_used: {pretty_time}")
            
            if len(self.heap) <= self.min_reverse_length:
                return
            
            active_models = [w for w in sorted_models if current_time - w.last_used <= self.time_to_live]
            if len(active_models) >= self.min_reverse_length:
                self.heap = active_models
                if len(sorted_models) != len(active_models):
                    logging.info(f"keep {self.name} models, length: {len(self.heap)}, removed length: {len(sorted_models) - len(active_models)}")
            else:
                # keep the min_reverse_length most recently used models
                self.heap = sorted_models[:self.min_reverse_length]

            heapq.heapify(self.heap)


if __name__ == "__main__":
    import torch
    cache = LRUCacheModelQueue(device="cuda:0", name="hubert", move_to_cpu=6, time_to_live=10, min_reverse_length=2)
    for i in range(6):
        cache.add_model(torch.randn(1, 100).to("cuda:0"))
        time.sleep(0.5)
    
    with cache.get_model() as model:
        logging.info(cache.lock.locked())
        logging.info(cache.model_length())

    time.sleep(1e5)
