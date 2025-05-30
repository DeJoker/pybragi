
from pybragi.base import time_utils
from typing import Any
from contextlib import contextmanager
import heapq
from threading import Lock, Thread
import time

class ModelWrapper:
    def __init__(self, model: Any):
        self.model = model
        self.last_used = time.time()
    
    def __lt__(self, other):
        # Reverse comparison for max heap (most recent first)
        return self.last_used > other.last_used

class LRUCacheModelQueue:
    def __init__(self, device: Any, name="hubert", time_to_live=600, min_reverse_length=2):
        self.heap = []  # Priority queue using heapq
        self.lock = Lock()
        self.device = device
        self.name = name
        self.time_to_live = time_to_live
        self.min_reverse_length = min_reverse_length

        # Start cleanup thread
        self.cleanup_thread = Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def add_model(self, model):
        with self.lock, time_utils.ElapseCtx("add_model", gt=0.01):
            wrapper = ModelWrapper(model)
            # wrapper.model.to(self.device)
            heapq.heappush(self.heap, wrapper)
    

    def model_length(self):
        with self.lock, time_utils.ElapseCtx("model_length", gt=0.01):
            return len(self.heap)
        
    
    @contextmanager
    def get_model(self):
        with self.lock, time_utils.ElapseCtx("get_model", gt=0.01):
            if not self.heap:
                # todo: add model
                raise TimeoutError(f"{self.name} No models available")
            wrapper = heapq.heappop(self.heap)

        # wrapper.model.to(self.device)
        try:
            yield wrapper.model
        finally:
            with self.lock, time_utils.ElapseCtx("get_model", gt=0.01):
                # wrapper.model.to("cpu")
                wrapper.last_used = time.time()
                heapq.heappush(self.heap, wrapper)
    
    def hold_model(self):
        with self.lock, time_utils.ElapseCtx("hold_model", gt=0.01):
            if not self.heap:
                # todo: add model
                raise TimeoutError(f"{self.name} No models available")
            wrapper = heapq.heappop(self.heap)
        
        return wrapper.model
    
    def _cleanup_loop(self):
        while True:
            time.sleep(1)
            self._cleanup()
    
    def _cleanup(self):
        current_time = time.time()
        with self.lock, time_utils.ElapseCtx("cleanup", gt=0.01):
            if len(self.heap) <= self.min_reverse_length:
                return

            sorted_models = sorted(self.heap, key=lambda w: w.last_used, reverse=True)

            active_models = [w for w in sorted_models if current_time - w.last_used <= self.time_to_live]
            
            if len(active_models) >= self.min_reverse_length:
                self.heap = active_models
            else:
                # Otherwise, keep the min_reverse_length most recently used models
                self.heap = sorted_models[:self.min_reverse_length]

            heapq.heapify(self.heap)


if __name__ == "__main__":
    import logging
    import torch
    cache = LRUCacheModelQueue(device="cpu", name="hubert", time_to_live=600, min_reverse_length=2)
    cache.add_model(torch.randn(1, 100))
    with cache.get_model() as model:
        logging.info(cache.lock.locked())
        logging.info(cache.model_length())
