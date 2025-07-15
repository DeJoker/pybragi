import asyncio
from pathlib import Path
from pybragi.base import time_utils
from pybragi.base.async_utils import (
    async_download_file,
    wait_batch,
    pbar_wait,
)





async def test_async_download_file():
    url = "https://www.google.com"
    save_path = Path("test.html")
    await async_download_file(url, save_path)
    assert save_path.exists()

async def test_wait_batch():
    async def task_func(i):
        await asyncio.sleep(0.1*i)
        return i
    
    tasks = [asyncio.create_task(task_func(i)) for i in range(10)]
    with time_utils.ElapseCtx("wait_batch"):
        await wait_batch(tasks)


    semaphore = asyncio.Semaphore(5)
    async def limited_wrapper(i):
        async with semaphore:
            return await task_func(i)

    tasks2 = [asyncio.create_task(limited_wrapper(i)) for i in range(10)]
    # sleep 0.4 + 0.9  =  1.3s
    with time_utils.ElapseCtx("pbar_wait"):
        await pbar_wait(tasks2, desc=f"pbar_wait")


if __name__ == "__main__":
    # asyncio.run(test_async_download_file())
    asyncio.run(test_wait_batch())