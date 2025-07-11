import asyncio
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)

async def simple_coro():
    logging.info("Coroutine started")
    await asyncio.sleep(0.5)
    logging.info("Coroutine finished")
    return "result"

async def test_wrap_future():
    # 创建一个新的事件循环在子线程中
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    
    # 等待线程启动
    time.sleep(0.1)
    
    # 获取子线程的事件循环
    all_loops = []
    for task in threading.enumerate():
        if hasattr(task, '_target') and task.daemon:
            # 这里简化处理，实际应该有更好的方式获取子线程的loop
            break
    
    # 简化测试：直接在当前线程创建loop
    child_loop = asyncio.new_event_loop()
    
    def run_child_loop():
        asyncio.set_event_loop(child_loop)
        child_loop.run_forever()
    
    child_thread = threading.Thread(target=run_child_loop, daemon=True)
    child_thread.start()
    
    time.sleep(0.1)  # 等待线程启动
    
    # 在子线程的事件循环中执行协程
    future = asyncio.run_coroutine_threadsafe(simple_coro(), child_loop)
    
    logging.info("About to wrap future...")
    try:
        # 测试 wrap_future
        result = await asyncio.wrap_future(future)
        logging.info(f"wrap_future succeeded: {result}")
    except Exception as e:
        logging.error(f"wrap_future failed: {e}")
    
    # 关闭子线程的事件循环
    child_loop.call_soon_threadsafe(child_loop.stop)

async def main():
    await test_wrap_future()

if __name__ == "__main__":
    asyncio.run(main()) 