
from contextlib import contextmanager
from datetime import datetime
import logging
import time
from typing import Dict, Generator
from readerwriterlock import rwlock
from pybragi.base import time_utils

global_lock_dict = {}

def init_rwlock(model_name: str):
    global global_lock_dict
    if model_name not in global_lock_dict:
        global_lock_dict[model_name] = rwlock.RWLockFair()
    # 不要缓存 gen_rlock() 和 gen_wlock() 否则会创建多个锁访问器
    # 每个锁访问器内部存储了自己的锁定状态 v_locked，而不是从底层锁对象查询状态

@contextmanager
def get_model_for_read(model_name: str, models_dict: Dict, uuid: str = ""):
    global global_lock_dict
    start_time = time.perf_counter()
    lock: rwlock.RWLockFair._aReader  = global_lock_dict[model_name].gen_rlock()
    try:
        if lock.locked():
            logging.warning(f"lock.locked(): {lock.locked()}")
        
        with time_utils.ElapseCtx(f"rlock.acquire for {model_name} {uuid}", gt=0.01):
            res = lock.acquire(timeout=10.5)
        if res:
            yield models_dict[model_name]
    finally:
        duration = time.perf_counter() - start_time
        # logging.info(f"{lock.c_rw_lock.v_read_count} {uuid}")
        if duration > 0.001:
            logging.warning(
                f"Slow read for model {model_name} {uuid}: {duration:.3f}s"
            )
        if res:
            lock.release()
        else:
            logging.warning(f"lock.locked(): {lock.locked()}")
        # logging.info(f"{lock.c_rw_lock.v_read_count} {uuid}")

@contextmanager
def get_model_for_write(model_name: str, models_dict: Dict, uuid: str = "") -> Generator[Dict, None, None]:
    global global_lock_dict
    start_time = time.perf_counter()
    lock: rwlock.RWLockFair._aWriter = global_lock_dict[model_name].gen_wlock()
    try:
        if lock.locked():
            logging.warning(f"lock.locked(): {lock.locked()}")
        
        with time_utils.ElapseCtx(f"wlock.acquire for {model_name} {uuid}", gt=0.01):
            res = lock.acquire(timeout=8)
        if res:
            yield models_dict[model_name]
    finally:
        duration = time.perf_counter() - start_time
        if duration > 0.01:
            logging.warning(
                f"Slow write for model {model_name} {uuid}: {duration:.3f}s"
            )
        if res:
            lock.release()
        else:
            logging.warning(f"lock.locked(): {lock.locked()}")


if __name__ == "__main__":
    import random
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=10)

    test_models_dict = {
        "hubert": {
            "xx": 1,
            "size": 0
        },
        "whisper": {
            "xx": 2,
            "size": 0
        },
    }
    for model_name in test_models_dict.keys():
        init_rwlock(model_name)

    def load_model(seed_name: str):
        seed_model = None
        with get_model_for_read(seed_name, test_models_dict, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model:
            tmp = model

        seed_model = { k: v for k, v in tmp.items() if k not in ["rLock", "wLock"]}
        # fake load model
        time.sleep(4)

        if seed_model:
            with get_model_for_write(seed_name, test_models_dict, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model_info:
                model_info["size"] += 1
    
    def infer(model_name: str):
        future = None
        with get_model_for_read(model_name, test_models_dict, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model, time_utils.ElapseCtx(f"infer1 {model_name}", gt=0.01):
            logging.info(model)

            if model["size"] <= 0:
                future = executor.submit(load_model, model_name) # wait
            elif model["size"] < 3:
                executor.submit(load_model, model_name) # no wait
            else:
                logging.info(f"enough, model {model_name} size: {model['size']}")
        
        if future:
            future.result() # wait outside of lock

        with get_model_for_read(model_name, test_models_dict, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model, time_utils.ElapseCtx(f"infer2 {model_name}", gt=0.01):
            logging.info(model)
        time.sleep(2.3)

    for key in test_models_dict.keys():
        load_model(key)

    for _ in range(10):
        random_model = random.choice(list(test_models_dict.keys()))
        executor.submit(load_model, random_model)
        infer(random_model)

    
    

