import asyncio
import logging
from typing import Optional
from pathlib import Path
import aiohttp
import tqdm

async def wait_batch(tasks: list[asyncio.Task]):
    loop = asyncio.get_running_loop()

    while tasks:
        # done, pending = await asyncio.wait(tasks, timeout=0.1)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        tasks = pending



async def pbar_wait(tasks: list[asyncio.Task], *, desc: str = "Waiting for tasks"):
    loop = asyncio.get_running_loop()
    pbar = tqdm.tqdm(total=len(tasks), desc=desc)

    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        pbar.update(len(done))
        tasks = pending
    
    pbar.close()



# vllm/vllm/connections.py
async def async_download_file(
        url: str,
        save_path: Path,
        *,
        timeout: Optional[float] = None,
        chunk_size: int = 64*1024,
    ) -> Path:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as r:
                r.raise_for_status()

                with save_path.open("wb") as f:
                    async for chunk in r.content.iter_chunked(chunk_size):
                        f.write(chunk)

        return save_path


