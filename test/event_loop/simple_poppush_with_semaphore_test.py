import asyncio
import logging
import time
import traceback

from pybragi.base.thread_bind_async_manager import (
    AsyncManagerError,
    PopPushAsyncManagerContext,
    get_running_coros, 
    init_async_manager,
)
# logging.getLogger().setLevel(logging.DEBUG)

class SimpleTask:
    def __init__(self, task_id):
        self.task_id = task_id

    async def _actual_work(self):
        logging.info(f"actual {self.task_id} start")
        await asyncio.sleep(0.3)
        logging.info(f"actual {self.task_id} done")

    async def run(self):
        logging.info(f"Task {self.task_id} trying to acquire context...")
        

        ttt = 0.2 # larger than 0.3 not issue AsyncManagerError
        while True:
            try:
                async with PopPushAsyncManagerContext(group_name="test_group", timeout=ttt) as (async_obj, loop):
                    logging.info(f"Task {self.task_id} acquired context: obj={id(async_obj)}, loop={id(loop)}")

                    logging.info(f"running coros: {get_running_coros()}")
                    
                    future = asyncio.run_coroutine_threadsafe(self._actual_work(), loop)
                    await asyncio.wrap_future(future)
                    # future.result() # block in MainThread.    async should use await way

                    logging.info(f"Task {self.task_id} completed!")
                    break
                    
            except AsyncManagerError as e:
                logging.info(f"Task {self.task_id} waiting for resources...")
                await asyncio.sleep(0.01)
                continue
            except:
                traceback.print_exc()

async def init_dummy_object():
    await asyncio.sleep(0.01)
    return f"dummy_object_{id(object())}"

async def main():
    logging.info("Starting simple test...")
    
    # 创建3个任务，但只有2个async objects
    tasks = []
    for i in range(3):
        task = asyncio.create_task(SimpleTask(i).run())
        tasks.append(task)
    
    start_time = time.time()
    await asyncio.gather(*tasks)
    end_time = time.time()
    
    logging.info(f"All tasks completed in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    # 初始化2个async objects
    init_async_manager(group_name="test_group", thread_count=2, initialize_async_object=init_dummy_object)
    
    asyncio.run(main()) 