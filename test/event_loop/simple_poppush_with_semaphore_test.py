import asyncio
import logging
import time

from pybragi.base.async_manager import (
    PopPushAsyncManagerContext, 
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
        with PopPushAsyncManagerContext(group_name="test_group") as (async_obj, loop):
            logging.info(f"Task {self.task_id} acquired context: obj={id(async_obj)}, loop={id(loop)}")
            
            future = asyncio.run_coroutine_threadsafe(self._actual_work(), loop)
            # await asyncio.wrap_future(future)
            future.result()

            logging.info(f"Task {self.task_id} completed!")

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