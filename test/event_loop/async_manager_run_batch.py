
import asyncio
import time

from pybragi.base.async_manager import (
    PopPushAsyncManagerContext, HashAsyncManagerContext, 
    get_all_async_objects_from_manager, get_async_length_from_manager, init_async_manager, 
    _bind_async_object_to_manager, run_coro_with_manager,
    pop_async_object_from_manager, hash_async_object_from_manager,
)
import logging


class OneLongTask:
    def __init__(self):
        self.name = f"one_long_task_{id(self)}"

    async def run(self):
        with PopPushAsyncManagerContext(group_name="one_long_task"):
            logging.info(f"{self.name} start")
            await asyncio.sleep(0.3)
            logging.info(f"{self.name} done")

async def init_one_long_task():
    await asyncio.sleep(0.01)
    return OneLongTask()



class NestAsyncTask:
    def __init__(self):
        self.name = f"nest_async_task_{id(self)}"
        self.sub_task = OneLongTask()
    
    async def run(self):
        await self.sub_task.run()

        # await asyncio.sleep(1)
        


async def run_batch():
    loop = asyncio.get_event_loop()
    active_tasks = []

    for i in range(10):
        task = loop.create_task(NestAsyncTask().run())
        active_tasks.append(task)

    while active_tasks:
        done, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
        active_tasks = pending

if __name__ == "__main__":
    init_async_manager(group_name="one_long_task", thread_count=3, initialize_async_object=init_one_long_task)

    asyncio.run(run_batch())