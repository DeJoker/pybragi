import asyncio
import threading
import time
import logging
from pybragi.base.async_manager import (
    AsyncManagerContext, get_all_async_objects_from_manager, init_async_manager, 
    get_async_object_from_manager, _bind_async_object_to_manager, run_coro_with_manager
)

logging.getLogger().setLevel(logging.DEBUG)

class MockAsyncRAG:
    def __init__(self):
        self.name = f"rag_{id(self)}"
    
    async def ainsert(self, contents, ids=None, workspace=None, file_paths=None):
        logging.info(f"{self.name} start insert...")
        await asyncio.sleep(0.1)
        logging.info(f"{self.name} insert done")
        return f"insert done: {contents}"

async def create_mock_rag():
    """创建模拟的异步对象"""
    return MockAsyncRAG()


#####################################################################################################
#  best usage

def test_run_coro_with_manager():
    group_name = "test_rag_coro"
    print("=== test run_coro_with_manager ===")
    
    init_async_manager(group_name, 2, create_mock_rag)
    
    rag, loop = get_async_object_from_manager(group_name)
    rag: MockAsyncRAG
    logging.info(f"get async object: {rag.name}")
    
    def return_object_callback(future):
        aa = future.result()
        logging.info(f"result: {aa}")
        all_async_objects = get_all_async_objects_from_manager(group_name)
        logging.info(f"all async objects: {len(all_async_objects)}")
    
    run_coro_with_manager(rag.ainsert("test content with callback"), 
                          group_name=group_name, async_obj=rag, loop=loop, callback=return_object_callback
                    )
    
    
    logging.info("async task submitted, no need to wait")












#####################################################################################################
# other test

def test_basic_async_object_context():
    print("=== test basic AsyncManagerContext ===")
    
    init_async_manager("test_rag", 1, create_mock_rag)
    
    with AsyncManagerContext("test_rag") as (rag, loop):
        logging.info(f"get async object: {rag.name}")
        
        future = asyncio.run_coroutine_threadsafe(
            rag.ainsert("test content", ids=["1", "2"], workspace="test_session"),
            loop
        )
        result = future.result()
        logging.info(f"result: {result}")


#################################################################################
# other test


def test_async_with_callback():
    print("\n=== test async with callback ===")
    
    init_async_manager("test_rag2", 1, create_mock_rag)
    
    rag, loop = get_async_object_from_manager("test_rag2")
    logging.info(f"get async object: {rag.name}")
    
    def return_object_callback(future):
        try:
            result = future.result()
            logging.info(f"async done, result: {result}")
        except Exception as e:
            logging.info(f"async failed: {e}")
        finally:
            _bind_async_object_to_manager("test_rag2", rag, loop)
            logging.info(f"async object {rag.name} returned to queue")
    
    future = asyncio.run_coroutine_threadsafe(
        rag.ainsert("test content with callback"),
        loop
    )
    future.add_done_callback(return_object_callback)
    
    logging.info("async task submitted, no need to wait")



###############################################################################



###############################################################################


class AsyncObjectContextWithCallback:
    
    def __init__(self, group_name: str):
        self.group_name = group_name
        self._async_obj = None
        self._loop = None
        self._manual_return = False
    
    def __enter__(self):
        result = get_async_object_from_manager(self.group_name)
        if result is None:
            raise RuntimeError(f"队列 '{self.group_name}' 中没有可用的异步对象")
        
        self._async_obj, self._loop = result
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._manual_return and self._async_obj is not None:
            _bind_async_object_to_manager(self.group_name, self._async_obj, self._loop)
            logging.info(f"async object {self._async_obj.name} returned to queue")
    
    def run_with_callback(self, coro, callback=None):
        def done_callback(future):
            try:
                if callback:
                    callback(future)
            finally:
                _bind_async_object_to_manager(self.group_name, self._async_obj, self._loop)
                logging.info(f"async object {self._async_obj.name} returned to queue")
                self._manual_return = True
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.add_done_callback(done_callback)
        return future
    
    @property
    def async_obj(self):
        return self._async_obj
    
    @property
    def loop(self):
        return self._loop

def test_improved_context():
    print("\n=== test improved context ===")
    
    init_async_manager("test_rag3", 1, create_mock_rag)
    
    def result_callback(future):
        try:
            result = future.result()
            logging.info(f"improved callback result: {result}")
        except Exception as e:
            logging.info(f"improved callback error: {e}")
        
        all_async_objects = get_all_async_objects_from_manager("test_rag3")
        logging.info(f"all async objects: {len(all_async_objects)}")
    
    with AsyncObjectContextWithCallback("test_rag3") as ctx:
        logging.info(f"get async object: {ctx.async_obj.name}")
        
        future = ctx.run_with_callback(
            ctx.async_obj.ainsert("improved test content"),
            result_callback
        )
        
        logging.info("async task submitted, no need to wait")

if __name__ == "__main__":
    # best usage
    test_run_coro_with_manager()
    time.sleep(1)

    # other test
    test_basic_async_object_context()
    time.sleep(1)
    test_async_with_callback()
    time.sleep(1)
    test_improved_context()
    time.sleep(1)
    
    logging.info("\n=== all tests done ===")
    
