import asyncio
import threading
import time
import logging
from pybragi.base.thread_bind_async_manager import (
    PopPushAsyncManagerContext, HashAsyncManagerContext, 
    get_all_async_objects_from_manager, get_async_length_from_manager, init_async_manager, 
    _bind_async_object_to_manager, run_coro_with_manager,
    pop_async_object_from_manager, hash_async_object_from_manager,
)

# logging.getLogger().setLevel(logging.DEBUG)

class MockAsyncRAG:
    def __init__(self):
        self.name = f"rag_{id(self)}"
    
    async def ainsert(self, contents, ids=None, workspace=None, file_paths=None):
        logging.info(f"{self.name} start insert...")
        await asyncio.sleep(0.1)
        logging.info(f"{self.name} insert done")
        return f"insert done: {contents}"

async def create_mock_rag():
    return MockAsyncRAG()

global_lock = asyncio.Lock()

class MockAsyncLockRAG:
    def __init__(self):
        self.name = f"rag_{id(self)}"
        
    
    async def lock_insert(self, contents, ids=None, workspace=None, file_paths=None):
        async with global_lock:
            logging.info(f"{self.name} start")
            await asyncio.sleep(0.1)
            logging.info(f"{self.name} done")
            return f"lock insert done: {contents}"

async def create_mock_lock_rag():
    return MockAsyncLockRAG()

# 新增：带有严格事件循环检查的RAG类
class StrictEventLoopRAG:
    """
    一个严格检查事件循环的RAG类，模拟 Python 3.10+ 的行为
    """
    
    def __init__(self):
        self.name = f"strict_rag_{id(self)}"
        self._loop = asyncio.get_running_loop()
        self._internal_lock = asyncio.Lock()
        logging.info(f"🔒 {self.name} 创建在事件循环: {id(self._loop)}")
    
    def _check_event_loop(self):
        """检查当前事件循环是否与RAG绑定的循环一致"""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(f"{self.name} 没有运行中的事件循环")
            
        if self._loop is not current_loop:
            raise RuntimeError(f'{self.name} is bound to a different event loop - 创建于:{id(self._loop)}, 当前:{id(current_loop)}')
        return current_loop
    
    async def strict_insert(self, contents, ids=None, workspace=None, file_paths=None):
        """执行插入操作 - 这里会检查事件循环"""
        loop = self._check_event_loop()  # 触发错误的关键点
        
        async with self._internal_lock:
            logging.info(f"✅ {self.name} 开始插入 (loop: {id(loop)})")
            await asyncio.sleep(0.1)
            logging.info(f"✅ {self.name} 插入完成")
            return f"strict insert done: {contents}"
    
    async def check_only(self):
        """仅检查事件循环，不执行其他操作"""
        loop = self._check_event_loop()
        logging.info(f"✅ {self.name} 事件循环检查通过 (loop: {id(loop)})")
        return "event loop check passed"

async def create_strict_rag():
    return StrictEventLoopRAG()

#####################################################################################################
# 新增：复现"different event loop"错误的测试

def test_different_event_loop_error():
    """测试在不同事件循环中使用异步对象时的错误"""
    print("\n=== 🎯 测试 'different event loop' 错误 ===")
    
    group_name = "test_strict_rag"
    init_async_manager(group_name, 2, create_strict_rag)
    
    # 等待初始化完成
    time.sleep(0.2)
    
    print("\n1️⃣ 测试 PopPushAsyncManagerContext:")
    test_pop_push_with_different_loop(group_name)
    
    print("\n2️⃣ 测试 HashAsyncManagerContext:")
    test_hash_with_different_loop(group_name)

def test_concurrent_context_differences():
    """测试两种context在并发访问时的行为差异"""
    print("\n=== 🔄 测试并发访问差异 ===")
    
    group_name = "test_concurrent"
    init_async_manager(group_name, 2, create_strict_rag)
    time.sleep(0.2)
    
    print("\n🔹 测试 PopPushAsyncManagerContext 并发行为:")
    test_pop_push_concurrent_behavior(group_name)
    
    time.sleep(1)
    
    print("\n🔹 测试 HashAsyncManagerContext 并发行为:")
    test_hash_concurrent_behavior(group_name)

def test_pop_push_concurrent_behavior(group_name):
    """测试PopPushAsyncManagerContext的并发行为 - 队列轮转"""
    results = []
    
    def concurrent_pop_push(session_id):
        try:
            with PopPushAsyncManagerContext(group_name) as (rag, loop):
                logging.info(f"🔄 PopPush[{session_id}]: 获取到 {rag.name}")
                
                future = asyncio.run_coroutine_threadsafe(
                    rag.strict_insert(f"data from session {session_id}"),
                    loop
                )
                result = future.result(timeout=5)
                results.append(f"PopPush[{session_id}]: {rag.name} -> {result}")
                logging.info(f"✅ PopPush[{session_id}]: 完成")
                
        except Exception as e:
            results.append(f"PopPush[{session_id}]: ERROR - {e}")
            logging.error(f"❌ PopPush[{session_id}]: {e}")
    
    # 并发启动多个任务
    threads = []
    for i in range(5):
        thread = threading.Thread(target=concurrent_pop_push, args=(f"session_{i}",))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print("PopPush 并发结果:")
    for result in results:
        print(f"  {result}")

def test_hash_concurrent_behavior(group_name):
    """测试HashAsyncManagerContext的并发行为 - 基于hash分配"""
    results = []
    
    def concurrent_hash(session_id):
        try:
            with HashAsyncManagerContext(group_name, session_id) as (rag, loop):
                logging.info(f"🔄 Hash[{session_id}]: 获取到 {rag.name}")
                
                future = asyncio.run_coroutine_threadsafe(
                    rag.strict_insert(f"data from session {session_id}"),
                    loop
                )
                result = future.result(timeout=5)
                results.append(f"Hash[{session_id}]: {rag.name} -> {result}")
                logging.info(f"✅ Hash[{session_id}]: 完成")
                
        except Exception as e:
            results.append(f"Hash[{session_id}]: ERROR - {e}")
            logging.error(f"❌ Hash[{session_id}]: {e}")
    
    # 并发启动多个任务，使用相同的session_id来测试hash一致性
    threads = []
    
    # 测试相同session_id应该获得相同的RAG对象
    for i in range(3):
        thread = threading.Thread(target=concurrent_hash, args=("same_session",))
        threads.append(thread)
        thread.start()
    
    # 测试不同session_id获得不同的RAG对象
    for i in range(2):
        thread = threading.Thread(target=concurrent_hash, args=(f"different_session_{i}",))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print("Hash 并发结果:")
    for result in results:
        print(f"  {result}")

def test_resource_exhaustion_differences():
    """测试资源耗尽时两种context的不同行为"""
    print("\n=== 🚨 测试资源耗尽时的行为差异 ===")
    
    group_name = "test_exhaustion"
    init_async_manager(group_name, 1, create_strict_rag)  # 只有1个对象
    time.sleep(0.2)
    
    print("\n🔹 测试 PopPushAsyncManagerContext 资源耗尽:")
    test_pop_push_exhaustion(group_name)
    
    print("\n🔹 测试 HashAsyncManagerContext 资源耗尽:")
    test_hash_exhaustion(group_name)

def test_pop_push_exhaustion(group_name):
    """测试PopPush在资源耗尽时的行为"""
    results = []
    
    def try_get_resource(task_id):
        try:
            with PopPushAsyncManagerContext(group_name) as (rag, loop):
                logging.info(f"🎯 PopPush[{task_id}]: 成功获取 {rag.name}")
                time.sleep(2)  # 占用资源较长时间
                results.append(f"PopPush[{task_id}]: SUCCESS with {rag.name}")
        except Exception as e:
            results.append(f"PopPush[{task_id}]: FAILED - {e}")
            logging.error(f"❌ PopPush[{task_id}]: {e}")
    
    # 并发启动3个任务，但只有1个资源
    threads = []
    for i in range(3):
        thread = threading.Thread(target=try_get_resource, args=(f"task_{i}",))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # 错开启动时间
    
    for thread in threads:
        thread.join()
    
    print("PopPush 资源耗尽结果:")
    for result in results:
        print(f"  {result}")

def test_hash_exhaustion(group_name):
    """测试Hash在资源耗尽时的行为"""
    results = []
    
    def try_get_resource(task_id, session_id):
        try:
            with HashAsyncManagerContext(group_name, session_id) as (rag, loop):
                logging.info(f"🎯 Hash[{task_id}]: 成功获取 {rag.name}")
                time.sleep(2)  # 占用资源较长时间
                results.append(f"Hash[{task_id}]: SUCCESS with {rag.name}")
        except Exception as e:
            results.append(f"Hash[{task_id}]: FAILED - {e}")
            logging.error(f"❌ Hash[{task_id}]: {e}")
    
    # 并发启动3个任务，使用相同的session_id（应该都尝试获取同一个资源）
    threads = []
    for i in range(3):
        thread = threading.Thread(target=try_get_resource, args=(f"task_{i}", "same_session"))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # 错开启动时间
    
    for thread in threads:
        thread.join()
    
    print("Hash 资源耗尽结果:")
    for result in results:
        print(f"  {result}")

def test_pop_push_with_different_loop(group_name):
    """测试PopPushAsyncManagerContext在不同事件循环中的行为"""
    
    def run_in_new_event_loop():
        """在新的事件循环中运行测试"""
        # 创建新的事件循环
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        
        try:
            logging.info(f"🔄 PopPush: 在新事件循环中运行 (loop: {id(new_loop)})")
            
            with PopPushAsyncManagerContext(group_name) as (rag, original_loop):
                logging.info(f"📦 PopPush: 获取到 {rag.name}, 原事件循环: {id(original_loop)}")
                
                # 尝试在新事件循环中使用原事件循环的对象
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        rag.strict_insert("test from new loop"),
                        original_loop  # 使用原来的事件循环
                    )
                    result = future.result(timeout=5)
                    logging.info(f"✅ PopPush: 成功 - {result}")
                except Exception as e:
                    logging.error(f"❌ PopPush: 失败 - {e}")
                
        except Exception as e:
            logging.error(f"❌ PopPush: 上下文错误 - {e}")
        finally:
            new_loop.close()
    
    # 在新线程中运行
    thread = threading.Thread(target=run_in_new_event_loop)
    thread.start()
    thread.join()

def test_hash_with_different_loop(group_name):
    """测试HashAsyncManagerContext在不同事件循环中的行为"""
    
    def run_in_new_event_loop():
        """在新的事件循环中运行测试"""
        # 创建新的事件循环
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        
        try:
            logging.info(f"🔄 Hash: 在新事件循环中运行 (loop: {id(new_loop)})")
            
            with HashAsyncManagerContext(group_name, "test_session") as (rag, original_loop):
                logging.info(f"📦 Hash: 获取到 {rag.name}, 原事件循环: {id(original_loop)}")
                
                # 尝试在新事件循环中使用原事件循环的对象
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        rag.strict_insert("test from new loop"),
                        original_loop  # 使用原来的事件循环
                    )
                    result = future.result(timeout=5)
                    logging.info(f"✅ Hash: 成功 - {result}")
                except Exception as e:
                    logging.error(f"❌ Hash: 失败 - {e}")
                
        except Exception as e:
            logging.error(f"❌ Hash: 上下文错误 - {e}")
        finally:
            new_loop.close()
    
    # 在新线程中运行  
    thread = threading.Thread(target=run_in_new_event_loop)
    thread.start()
    thread.join()

def test_cross_loop_direct_usage():
    """测试直接跨事件循环使用异步对象（会触发错误）"""
    print("\n=== 🚨 测试直接跨事件循环使用（应该报错）===")
    
    group_name = "test_cross_loop"
    init_async_manager(group_name, 1, create_strict_rag)
    time.sleep(0.2)
    
    def run_wrong_usage():
        # 创建新的事件循环
        wrong_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(wrong_loop)
        
        try:
            logging.info(f"🔄 错误用法: 在错误的事件循环中运行 (loop: {id(wrong_loop)})")
            
            # 获取对象但在错误的循环中运行
            with PopPushAsyncManagerContext(group_name) as (rag, correct_loop):
                logging.info(f"📦 获取到 {rag.name}, 正确事件循环: {id(correct_loop)}")
                logging.info(f"🚨 当前事件循环: {id(wrong_loop)}")
                
                # 尝试在错误的事件循环中直接运行 - 这应该会报错
                try:
                    result = wrong_loop.run_until_complete(rag.check_only())
                    logging.info(f"❓ 意外成功: {result}")
                except Exception as e:
                    logging.error(f"✅ 预期错误: {e}")
                    
        except Exception as e:
            logging.error(f"❌ 意外错误: {e}")
        finally:
            wrong_loop.close()
    
    thread = threading.Thread(target=run_wrong_usage)
    thread.start()
    thread.join()

#####################################################################################################
#  best usage

def test_run_coro_with_manager():
    group_name = "test_rag_coro"
    print("=== test run_coro_with_manager ===")
    
    init_async_manager(group_name, 2, create_mock_rag)
    
    rag, loop = pop_async_object_from_manager(group_name)
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




def test_basic_async_object_context():
    print("=== test basic AsyncManagerContext ===")

    group_name = "test_rag"
    init_async_manager(group_name, 1, create_mock_rag)
    
    with PopPushAsyncManagerContext(group_name) as (rag, loop):
        logging.info(f"get async object: {rag.name}")
        
        future = asyncio.run_coroutine_threadsafe(
            rag.ainsert("test content", ids=["1", "2"], workspace="test_session"),
            loop
        )
        result = future.result()
        logging.info(f"result: {result}")


def test_large_async_request_exception():
    print("=== test basic AsyncManagerContext ===")

    group_name = "test_rag_exception"
    init_async_manager(group_name, 1, create_mock_rag)
    
    async_length = get_async_length_from_manager(group_name)
    logging.info(f"async length: {async_length}")

    async_object, loop = pop_async_object_from_manager(group_name)
    logging.info(f"get async object: {async_object.name}")

    async_length = get_async_length_from_manager(group_name)
    logging.info(f"async length: {async_length}")

    with PopPushAsyncManagerContext(group_name) as (rag, loop):
        logging.info(f"get async object: {rag.name}")
        
        future = asyncio.run_coroutine_threadsafe(
            rag.ainsert("test content", ids=["1", "2"], workspace="test_session"),
            loop
        )
        result = future.result()
        logging.info(f"result: {result}")

def test_hash_async_object_context():
    print("=== test hash AsyncManagerContext ===")

    group_name = "test_rag_hash"
    session_name = "test_session"
    init_async_manager(group_name, 2, create_mock_lock_rag)

    for i in range(5):
        with HashAsyncManagerContext(group_name, session_name) as (rag, loop):
            logging.info(f"get async object: {rag.name}")
            rag: MockAsyncLockRAG
            
            future = asyncio.run_coroutine_threadsafe(
                rag.lock_insert("test content", ids=["1", "2"], workspace=session_name),
                loop
            )
            result = future.result()
            logging.info(f"result: {result}")

    print("="*100)
    print('\n'*5)
    print("PopPushAsyncManagerContext for lock")
    for i in range(3):
        with PopPushAsyncManagerContext(group_name) as (rag, loop):
            logging.info(f"get async object: {rag.name}")
            rag: MockAsyncLockRAG
            
            future = asyncio.run_coroutine_threadsafe(
                rag.lock_insert("test content", ids=["1", "2"], workspace="test_session2"),
                loop
            )
            # result = future.result()
            logging.info(f"result: {result}")


#################################################################################
# other test


def test_async_with_callback():
    print("\n=== test async with callback ===")
    
    init_async_manager("test_rag2", 1, create_mock_rag)
    
    rag, loop = pop_async_object_from_manager("test_rag2")
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
        result = pop_async_object_from_manager(self.group_name)
        if result is None:
            raise RuntimeError(f"queue '{self.group_name}' has no available async object")
        
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
    # 新增的主要测试
    test_different_event_loop_error()
    time.sleep(2)
    
    test_cross_loop_direct_usage()
    time.sleep(2)
    
    # 测试并发行为差异
    test_concurrent_context_differences()
    time.sleep(2)
    

    print("="*100)
    
    # best usage
    # test_run_coro_with_manager()
    # time.sleep(1)
    # print("="*100)

    # test_basic_async_object_context()
    # time.sleep(1)
    # print("="*100)

    # test_hash_async_object_context()
    # time.sleep(1)
    # print("="*100)

    # try:
    #     test_large_async_request_exception()
    # except Exception as e:
    #     logging.error(f"test_large_async_request_exception failed: {e}")
    # time.sleep(1)

    # other test
    # test_async_with_callback()
    # time.sleep(1)
    # test_improved_context()
    # time.sleep(1)
    
    logging.info("\n=== all tests done ===")
    
