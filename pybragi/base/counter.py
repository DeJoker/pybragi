from datetime import datetime
import threading
from contextlib import contextmanager
from functools import wraps


class RunningStatus:
    def __init__(self, tracking_name="request_id"):
        self.running_count = 0
        self.lock = threading.RLock() # 可重入
        self.active_tasks = [] # 用于追踪活动任务的附加信息
        self.tracking_name = tracking_name

    #  运行一段时间后出现 count 只增不减  -1 没有正确调用
    @contextmanager
    def mark_running(self, tracking_id=""):
        with self.lock:
            self.running_count += 1
            self.active_tasks.append(tracking_id)
        
        try:
            yield
        finally:
            with self.lock:
                self.running_count -= 1
                self.active_tasks.remove(tracking_id)
    
    def get_running_count(self):
        with self.lock:
            return self.running_count
        
    def get_active_tasks(self):
        with self.lock:
            return self.active_tasks

    def running_decorator(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracking_id = kwargs.get(self.tracking_name) 
            if tracking_id is None:
                tracking_id = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            
            with self.mark_running(tracking_id):
                return func(*args, **kwargs)
        return wrapper



if __name__ == "__main__":
    import logging
    import time, sys
    import random, uuid
    from concurrent.futures import ThreadPoolExecutor

    running_status = RunningStatus()

    # decorators are applied from bottom to top
    # 所以应该在executor内执行    如果相反代表counter仅作用于executor.submit 就释放了running_decorator 
    @running_status.running_decorator
    def test_running_status(request_id=""):
        logging.info("running")
        rand = random.randint(0, 10) 
        time.sleep(rand / 10)
        if rand > 8:
            logging.info(f"rand > 8: {rand}")
            raise Exception("rand > 8")
        

    executor = ThreadPoolExecutor(max_workers=11)
    for _ in range(10):
        executor.submit(test_running_status, request_id=str(uuid.uuid4()))

    def continue_running():
        for _ in range(20):
            logging.info(f"running_count: {running_status.get_running_count()}")
            logging.info(f"active_tasks: {running_status.get_active_tasks()}")
            time.sleep(0.1)
    
    executor.submit(continue_running)
    time.sleep(2)
    executor.shutdown(wait=False, cancel_futures=True)
