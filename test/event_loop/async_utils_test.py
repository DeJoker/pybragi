import asyncio
import threading
import time
import logging
from pybragi.base.async_utils import AsyncObjectContext, init_and_bind_async_in_thread, get_single_async_object, _bind_async_object_to_thread

# 设置日志
logging.getLogger().setLevel(logging.DEBUG)

# 模拟一个异步对象
class MockAsyncRAG:
    def __init__(self):
        self.name = f"rag_{id(self)}"
    
    async def ainsert(self, contents, ids=None, workspace=None, file_paths=None):
        print(f"{self.name} 开始处理插入操作...")
        await asyncio.sleep(0.1)  # 模拟异步操作
        print(f"{self.name} 插入操作完成")
        return f"插入完成: {contents}"

async def create_mock_rag():
    """创建模拟的异步对象"""
    return MockAsyncRAG()


#####################################################################################################

def test_basic_async_object_context():
    """测试基本的AsyncObjectContext使用"""
    print("=== 测试基本的AsyncObjectContext使用 ===")
    
    # 在单独线程中初始化异步对象
    def init_thread():
        init_and_bind_async_in_thread("test_rag", create_mock_rag)
    
    thread = threading.Thread(target=init_thread, daemon=True)
    thread.start()
    time.sleep(0.1)  # 等待初始化完成
    
    # 使用上下文管理器
    with AsyncObjectContext("test_rag") as (rag, loop):
        print(f"获取到异步对象: {rag.name}")
        
        # 同步等待异步操作完成
        future = asyncio.run_coroutine_threadsafe(
            rag.ainsert("测试内容", ids=["1", "2"], workspace="test_session"),
            loop
        )
        result = future.result()  # 等待完成
        print(f"操作结果: {result}")


#################################################################################


def test_async_with_callback():
    """测试使用回调函数归还异步对象的方式"""
    print("\n=== 测试带回调的异步操作 ===")
    
    def init_thread2():
        init_and_bind_async_in_thread("test_rag2", create_mock_rag)
    
    thread = threading.Thread(target=init_thread2, daemon=True)
    thread.start()
    time.sleep(0.1)
    
    # 获取异步对象但不使用上下文管理器
    rag, loop = get_single_async_object("test_rag2")
    print(f"手动获取异步对象: {rag.name}")
    
    def return_object_callback(future):
        """异步操作完成后的回调函数"""
        try:
            result = future.result()
            print(f"异步操作完成，结果: {result}")
        except Exception as e:
            print(f"异步操作失败: {e}")
        finally:
            # 归还异步对象
            _bind_async_object_to_thread("test_rag2", rag, loop)
            print(f"异步对象 {rag.name} 已归还到队列")
    
    # 提交异步任务并添加回调
    future = asyncio.run_coroutine_threadsafe(
        rag.ainsert("带回调的测试内容"),
        loop
    )
    future.add_done_callback(return_object_callback)
    
    # 这里可以立即返回，不需要等待
    print("异步任务已提交，无需等待...")
    time.sleep(0.1)  # 等待回调执行



###############################################################################



class AsyncObjectContextWithCallback:
    """支持回调的异步对象上下文管理器"""
    
    def __init__(self, group_name: str):
        self.group_name = group_name
        self._async_obj = None
        self._loop = None
        self._manual_return = False
    
    def __enter__(self):
        result = get_single_async_object(self.group_name)
        if result is None:
            raise RuntimeError(f"队列 '{self.group_name}' 中没有可用的异步对象")
        
        self._async_obj, self._loop = result
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._manual_return and self._async_obj is not None:
            _bind_async_object_to_thread(self.group_name, self._async_obj, self._loop)
            print(f"自动归还异步对象 {self._async_obj.name}")
    
    def run_with_callback(self, coro, callback=None):
        """运行协程并在完成时通过回调归还对象"""
        def done_callback(future):
            try:
                if callback:
                    callback(future)
            finally:
                _bind_async_object_to_thread(self.group_name, self._async_obj, self._loop)
                print(f"通过回调归还异步对象 {self._async_obj.name}")
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
    """测试改进的上下文管理器"""
    print("\n=== 测试改进的上下文管理器 ===")
    
    def init_thread3():
        init_and_bind_async_in_thread("test_rag3", create_mock_rag)
    
    thread = threading.Thread(target=init_thread3, daemon=True)
    thread.start()
    time.sleep(0.1)
    
    def result_callback(future):
        try:
            result = future.result()
            print(f"改进版回调收到结果: {result}")
        except Exception as e:
            print(f"改进版回调收到错误: {e}")
    
    with AsyncObjectContextWithCallback("test_rag3") as ctx:
        print(f"使用改进版上下文管理器获取: {ctx.async_obj.name}")
        
        # 提交异步任务，无需等待
        future = ctx.run_with_callback(
            ctx.async_obj.ainsert("改进版测试内容"),
            result_callback
        )
        
        print("任务已提交，可以立即返回...")

if __name__ == "__main__":
    # 运行所有测试
    test_basic_async_object_context()
    test_async_with_callback() 
    test_improved_context()
    
    print("\n=== 所有测试完成 ===")
    
