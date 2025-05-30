import threading
from contextlib import contextmanager
from functools import wraps
from pybragi.base import time_utils

class RunningStatus:
    def __init__(self):
        self.running_count = 0
        self.lock = threading.RLock() # 可重入

    #  运行一段时间后出现 count 只增不减  -1 没有正确调用
    @contextmanager
    def mark_running(self):
        with self.lock:
            self.running_count += 1

        try:
            yield
        finally:
            with self.lock:
                self.running_count -= 1
    
    def get_running_count(self):
        with self.lock:
            return self.running_count

    def running_decorator(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.mark_running():
                return func(*args, **kwargs)
        return wrapper



if __name__ == "__main__":
    import logging
    import time, sys
    import random
    from concurrent.futures import ThreadPoolExecutor

    running_status = RunningStatus()

    # decorators are applied from bottom to top
    # 所以应该在executor内执行    如果相反代表counter仅作用于executor.submit 就释放了running_decorator 
    @running_status.running_decorator
    def test_running_status():
        logging.info("running")
        rand = random.randint(0, 10) 
        time.sleep(rand / 10)
        if rand > 8:
            logging.info(f"rand > 8: {rand}")
            raise Exception("rand > 8")
        

    executor = ThreadPoolExecutor(max_workers=11)
    for _ in range(10):
        executor.submit(test_running_status)

    def continue_running():
        for _ in range(20):
            logging.info(f"running_count: {running_status.get_running_count()}")
            time.sleep(0.1)
    
    executor.submit(continue_running)
    time.sleep(2)
    executor.shutdown(wait=False, cancel_futures=True)
