import asyncio
import random
import time
import traceback

async def worker(task_id):
    print(f"task {task_id}: running...")
    await asyncio.sleep(random.uniform(0.5, 3.0))
    print(f"task {task_id}: done.")
    return f"task {task_id} result"

async def concurrent_executor(total_tasks=10000, max_concurrent_loops=40, min_active_loops=30):
    task_queue = asyncio.Queue()
    results = []
    active_tasks = set()

    for i in range(1, total_tasks + 1):
        await task_queue.put(i)

    print(f"total {total_tasks} tasks waiting to be executed.")

    while not task_queue.empty() or active_tasks:
        for task in list(active_tasks):
            if task.done():
                active_tasks.discard(task)
                try:
                    result = task.result()
                    results.append(result)
                except Exception as e:
                    traceback.print_exc()

        while len(active_tasks) < min_active_loops and not task_queue.empty():
            task_id = await task_queue.get()
            print(f"current active tasks: {len(active_tasks)}, get task {task_id} and start.")
            
            # "fire and forget" run task in background
            new_task = asyncio.create_task(worker(task_id))
            active_tasks.add(new_task)

            await asyncio.sleep(0.01) 

        _, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
        print(f"current active tasks: {len(active_tasks)}, wait for one task to complete.")
        active_tasks = pending # refresh active tasks

        if not active_tasks and not task_queue.empty():
            await asyncio.sleep(0.1) # avoid empty loop

    print("\nall tasks done.")
    print(f"total {len(results)} tasks done.")
    return results

async def main():
    start_time = time.time()
    await concurrent_executor(total_tasks=10000, max_concurrent_loops=40, min_active_loops=30)
    end_time = time.time()
    print(f"total time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())