
from pybragi.base import log
from contextlib import contextmanager
from datetime import datetime
import logging
import time
from typing import Dict, Generator
from readerwriterlock import rwlock
from pybragi.base import time_utils

models_dict = {
    "hubert": {
        "xx": 1,
        "size": 0
    },
    "whisper": {
        "xx": 2,
        "size": 0
    },
}

for model_name in models_dict:
    rwLock = rwlock.RWLockFair()
    # 不要缓存 gen_rlock() 和 gen_wlock() 否则会创建多个锁访问器
    # 每个锁访问器内部存储了自己的锁定状态 v_locked，而不是从底层锁对象查询状态。

    models_dict[model_name]["rLock"] = rwLock.gen_rlock()
    models_dict[model_name]["wLock"] = rwLock.gen_wlock()
    logging.info(f"{model_name} {models_dict[model_name]['rLock'].c_rw_lock.v_read_count}")

def model_keys():
    return models_dict.keys()


@contextmanager
def get_model_for_read(model_name: str, uuid: str = ""):
    start_time = time.perf_counter()
    lock: rwlock.RWLockFair._aReader  = models_dict[model_name]["rLock"]
    try:
        if lock.locked():
            logging.warning(f"lock.locked(): {lock.locked()}")
        
        with time_utils.ElapseCtx(f"rlock.acquire for {model_name} {uuid}", gt=0.01):
            res = lock.acquire(timeout=0.5)
            logging.info(f"rlock.acquire for {model_name}: {res}")
        # with models_dict[model_name].rLock:
        yield models_dict[model_name]
    finally:
        duration = time.perf_counter() - start_time
        logging.info(f"{lock.c_rw_lock.v_read_count} {uuid}")
        if duration > 0.001:
            logging.warning(
                f"Slow read for model {model_name} {uuid}: {duration:.3f}s"
            )
        if lock.locked():
            lock.release()
        else:
            logging.warning(f"lock.locked(): {lock.locked()}")
        logging.info(f"{lock.c_rw_lock.v_read_count} {uuid}")

@contextmanager
def get_model_for_write(model_name: str, uuid: str = "") -> Generator[Dict, None, None]:
    start_time = time.perf_counter()
    lock: rwlock.RWLockFair._aWriter = models_dict[model_name]["wLock"]
    try:
        if lock.locked():
            logging.warning(f"lock.locked(): {lock.locked()}")
        
        with time_utils.ElapseCtx(f"wlock.acquire for {model_name} {uuid}", gt=0.01):
            res = lock.acquire(timeout=8)
            logging.info(f"wlock.acquire for {model_name}: {res}")
        # with models_dict[model_name].wLock:
        yield models_dict[model_name]
    finally:
        duration = time.perf_counter() - start_time
        if duration > 0.01:
            logging.warning(
                f"Slow write for model {model_name} {uuid}: {duration:.3f}s"
            )
        if lock.locked():
            lock.release()
        else:
            logging.warning(f"lock.locked(): {lock.locked()}")


if __name__ == "__main__":
    import random
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=10)

    def load_model(seed_name: str):
        seed_model = None
        with get_model_for_read(seed_name, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model:
            tmp = model

        seed_model = { k: v for k, v in tmp.items() if k not in ["rLock", "wLock"]}
        # fake load model
        time.sleep(4)

        if seed_model:
            with get_model_for_write(seed_name, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model_info:
                model_info["size"] += 1
    
    def infer(model_name: str):
        with get_model_for_read(model_name, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model:
            logging.info(model)

            if model["size"] <= 0:
                load_model(model_name)
            
            if model["size"] < 3:
                executor.submit(load_model, model_name)
        
        with get_model_for_read(model_name, uuid=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) as model:
            logging.info(model)
        time.sleep(2.3)

    for _ in range(10):
        random_model = random.choice(list(models_dict.keys()))
        executor.submit(load_model, random_model)
        infer(random_model)

    
    

