import asyncio
from contextlib import ContextDecorator
import logging
from pybragi.base.hash import djb2_hash
import threading
import time
from typing import Any, Callable, Tuple, Optional


async_object_group_map = {}
async_object_group_semaphore = {}

def _bind_async_object_to_manager(group_name: str, async_object: Any, loop: asyncio.AbstractEventLoop, notify: bool = False):
    global async_object_group_map
    
    if group_name not in async_object_group_map:
        async_object_group_map[group_name] = []
    async_object_group_map[group_name].append((async_object, loop))
    logging.debug(f"bound to queue {group_name} length: {len(async_object_group_map[group_name])}")
    if notify:
        global async_object_group_semaphore
        semaphore: threading.Semaphore = async_object_group_semaphore[group_name]
        semaphore.release()


def _new_loop_bind_async_to_manager(group_name: str, initialize_async_object: Callable):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # !!!!!!!!!!   asyncio.run   ONLY use in main thread     !!!!!!
    # asyncio.run(): create new event loop, run coroutine, then close event loop.

    # loop.run_until_complete(): run coroutine in the event loop, not destroy the current event loop

    async_object = loop.run_until_complete(initialize_async_object())
    logging.debug(f"{id(async_object)} in ev: {id(loop)} {id(asyncio.get_event_loop())}")
    _bind_async_object_to_manager(group_name, async_object, loop)
    loop.run_forever()


def init_async_manager(group_name: str, thread_count: int, initialize_async_object: Callable):
    for _ in range(thread_count):
        thread = threading.Thread(target=_new_loop_bind_async_to_manager, args=(group_name, initialize_async_object), daemon=True)
        thread.start()

    global async_object_group_semaphore
    async_object_group_semaphore[group_name] = threading.Semaphore(thread_count)

    while len(get_all_async_objects_from_manager(group_name)) < thread_count:
        time.sleep(0.1)
    logging.info(f"async {group_name} in subthraed, run count: {thread_count}")


def pop_async_object_from_manager(group_name: str) -> Tuple[Any, asyncio.AbstractEventLoop]:
    global async_object_group_map
    if group_name not in async_object_group_map:
        return None, None
    
    if len(async_object_group_map[group_name]) == 0:
        return None, None
    
    async_object, loop = async_object_group_map[group_name].pop(0)
    return async_object, loop

def wait_pop_async_object_from_manager(group_name: str, timeout: Optional[float] = None) -> Tuple[Any, asyncio.AbstractEventLoop]:
    global async_object_group_map, async_object_group_semaphore
    
    if group_name not in async_object_group_map:
        return None, None
    
    semaphore: threading.Semaphore = async_object_group_semaphore[group_name]
    
    with semaphore:
        async_object, loop = async_object_group_map[group_name].pop(0)
        logging.debug(f"get async object: {group_name}, remaining: {len(async_object_group_map[group_name])}")
        return async_object, loop


def hash_async_object_from_manager(group_name: str, key=None) -> Tuple[Any, asyncio.AbstractEventLoop]:
    global async_object_group_map
    if group_name not in async_object_group_map:
        return None, None
    
    if len(async_object_group_map[group_name]) == 0:
        return None, None
    
    index = djb2_hash(key) % len(async_object_group_map[group_name])
    
    async_object, loop = async_object_group_map[group_name][index]
    return async_object, loop


def get_all_async_objects_from_manager(group_name: str):
    global async_object_group_map
    if group_name not in async_object_group_map:
        return []
    return async_object_group_map[group_name]


def get_async_length_from_manager(group_name: str):
    global async_object_group_map
    if group_name not in async_object_group_map:
        return 0
    return len(async_object_group_map[group_name])




def run_coro_with_manager(coro, *, group_name: str, async_obj: Any, loop: asyncio.AbstractEventLoop, callback=None, return_to_manager: bool = False):
    def done_callback(future):
        try:
            if callback:
                callback(future)
        finally:
            if return_to_manager:
                _bind_async_object_to_manager(group_name, async_obj, loop)
                logging.debug(f"Asynchronous object {id(async_obj)} returned to queue via callback.")
    
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.add_done_callback(done_callback)
    return future

# unique and exclusive for static async_manager, use in async_object not has asyncio.Lock
class PopPushAsyncManagerContext(ContextDecorator):
    def __init__(self, group_name: str, timeout: Optional[float] = None):
        self.group_name = group_name
        self.semaphore: threading.Semaphore = async_object_group_semaphore[group_name]
        self.timeout = timeout
        self._async_obj: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def __enter__(self) -> Tuple[Any, asyncio.AbstractEventLoop]:
        logging.debug(f"Acquiring semaphore for group '{self.group_name}'...")
        self.semaphore.acquire()
        logging.debug(f"Semaphore acquired for group '{self.group_name}'")
        # 直接使用不带信号量的 pop 方法，避免双重获取
        self._async_obj, self._loop = pop_async_object_from_manager(self.group_name)
        if self._async_obj is None:
            # 如果没有可用对象，需要释放信号量并报错
            self.semaphore.release()
            raise RuntimeError(f"cannot get async object: '{self.group_name}' timeout: {self.timeout}")
        logging.debug(f"Asynchronous object {id(self._async_obj)} and event loop {id(self._loop)} obtained from queue '{self.group_name}'.")
        return self._async_obj, self._loop

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.debug(f"Entering __exit__ for group '{self.group_name}', obj: {id(self._async_obj) if self._async_obj else None}")
        if self._async_obj is not None and self._loop is not None:
            # 避免双重释放：设置 notify=False，手动释放信号量
            _bind_async_object_to_manager(self.group_name, self._async_obj, self._loop, notify=False)
            logging.debug(f"Asynchronous object {id(self._async_obj)} and event loop {id(self._loop)} returned to queue '{self.group_name}'.")
        else:
            logging.warning(f"Attempting to return an empty asynchronous object or event loop to queue '{self.group_name}'. This may indicate a logical error.")
        
        # 在最后释放信号量
        logging.debug(f"Releasing semaphore for group '{self.group_name}'...")
        self.semaphore.release()
        logging.debug(f"Semaphore released for group '{self.group_name}'")
        self._async_obj = None
        self._loop = None


# shared for static async_manager, safe for async_object has own asyncio.Lock.
# multi coroutine may use the same async_object and same lock
class HashAsyncManagerContext(ContextDecorator):
    def __init__(self, group_name: str, hash_key: str):
        self.group_name = group_name
        self.hash_key = hash_key
        self._async_obj: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def __enter__(self) -> Tuple[Any, asyncio.AbstractEventLoop]:
        self._async_obj, self._loop = hash_async_object_from_manager(self.group_name, self.hash_key)

        if self._async_obj is None:
            raise RuntimeError(f"No available asynchronous object in group '{self.group_name}'")
        logging.debug(f"Asynchronous object {id(self._async_obj)} and event loop {id(self._loop)} obtained from queue '{self.group_name}'.")
        return self._async_obj, self._loop

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._async_obj = None
        self._loop = None
