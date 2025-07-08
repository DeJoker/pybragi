import asyncio
from contextlib import ContextDecorator
import logging

import threading
import time
from typing import Any, Callable, Tuple, Optional


async_object_group_map = {}
def _bind_async_object_to_manager(group_name: str, async_object: Any, loop: asyncio.AbstractEventLoop):
    global async_object_group_map
    if group_name not in async_object_group_map:
        async_object_group_map[group_name] = []
    async_object_group_map[group_name].append((async_object, loop))
    logging.debug(f"bound to queue {group_name} length: {len(async_object_group_map[group_name])}")


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

    while len(get_all_async_objects_from_manager(group_name)) < thread_count:
        time.sleep(0.1)
    logging.info(f"async {group_name} in subthraed, run count: {thread_count}")


def get_async_object_from_manager(group_name: str) -> Tuple[Any, asyncio.AbstractEventLoop]:
    global async_object_group_map
    if group_name not in async_object_group_map:
        return None
    
    if len(async_object_group_map[group_name]) == 0:
        return None
    
    async_object, loop = async_object_group_map[group_name].pop(0)
    return async_object, loop


def get_all_async_objects_from_manager(group_name: str):
    global async_object_group_map
    if group_name not in async_object_group_map:
        return []
    return async_object_group_map[group_name]






def run_coro_with_manager(coro, *, group_name: str, async_obj: Any, loop: asyncio.AbstractEventLoop, callback=None):
    def done_callback(future):
        try:
            if callback:
                callback(future)
        finally:
            _bind_async_object_to_manager(group_name, async_obj, loop)
            logging.debug(f"Asynchronous object {id(async_obj)} returned to queue via callback.")
    
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.add_done_callback(done_callback)
    return future


class AsyncManagerContext(ContextDecorator):
    
    def __init__(self, group_name: str):
        self.group_name = group_name
        self._async_obj: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._manual_return = False

    def __enter__(self) -> Tuple[Any, asyncio.AbstractEventLoop]:
        result = get_async_object_from_manager(self.group_name)
        if result is None:
            raise RuntimeError(f"No available asynchronous object in group '{self.group_name}'. Please ensure it has been initialized and bound using init_and_bind_async_in_thread.")
        self._async_obj, self._loop = result
        logging.debug(f"Asynchronous object {id(self._async_obj)} and event loop {id(self._loop)} obtained from queue '{self.group_name}'.")
        return self._async_obj, self._loop

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._manual_return and self._async_obj is not None and self._loop is not None:
            _bind_async_object_to_manager(self.group_name, self._async_obj, self._loop)
            logging.debug(f"Asynchronous object {id(self._async_obj)} and event loop {id(self._loop)} returned to queue '{self.group_name}'.")
        else:
            logging.warning(f"Attempting to return an empty asynchronous object or event loop to queue '{self.group_name}'. This may indicate a logical error.")
        self._async_obj = None
        self._loop = None
    
