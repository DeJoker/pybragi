

import asyncio
import logging
from typing import Any, Callable


global_asyncpg_loop = None
def run_asyncpg_loop():
    global global_asyncpg_loop
    logging.info("Starting asyncpg event loop...")
    global_asyncpg_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(global_asyncpg_loop)
    logging.info("asyncpg event loop started")
    global_asyncpg_loop.run_forever()

def get_global_asyncpg_loop():
    global global_asyncpg_loop
    if global_asyncpg_loop:
        return global_asyncpg_loop
    return None


rag_to_executor_map = []
def bind_rag_to_executor(rag: Any, loop: asyncio.AbstractEventLoop):
    global rag_to_executor_map
    rag_to_executor_map.append((rag, loop))

def run_rag_in_executor(async_func: Callable):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # asyncio.run(): 创建新的事件循环，运行协程，然后关闭事件循环
    # loop.run_until_complete(): 在已设置的事件循环中运行协程，不会破坏当前的事件循环设置
    rag = loop.run_until_complete(async_func())
    logging.info(f"rag in executor {id(rag)} {id(loop)} {id(asyncio.get_event_loop())}")
    bind_rag_to_executor(rag, loop)
    loop.run_forever()


# query@postgres_impl.py:250) PostgreSQL database, error:Task <Task pending name='Task-450' coro=<PGDocStatusStorage.get_docs_by_status() 
# running at /cano_nas01/workspace/online/rag_pp/LightRAG/lightrag/kg/postgres_impl.py:1018> cb=[gather.<locals>._done_callback() at
# /home/work/miniconda3/envs/lightrag/lib/python3.10/asyncio/tasks.py:720]> 
# got Future <Future pending cb=[BaseProtocol._on_waiter_completed()]> attached to a different loop


async def get_ids(session_id: str):
    return [1, 2, 3]

async def get_ids_in_executor(session_id: str):
    asyncpg_future = asyncio.run_coroutine_threadsafe(
        get_ids(session_id),
        get_global_asyncpg_loop()
    )
    ids = await asyncio.wrap_future(asyncpg_future)



