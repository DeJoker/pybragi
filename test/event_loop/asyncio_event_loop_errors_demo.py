#!/usr/bin/env python3

import asyncio
import threading
import time

print("🎯 asyncio 'different event loop' ")
print("=" * 60)

class StrictLock:
    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._locked = False
        self._waiters = []
    
    def _get_loop(self):
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
            
        if self._loop is not current_loop:
            raise RuntimeError(f'{self!r} is bound to a different event loop')
        return current_loop
    
    async def acquire(self):
        loop = self._get_loop()
        if self._locked:
            fut = loop.create_future()
            self._waiters.append(fut)
            try:
                await fut
            except:
                self._waiters.remove(fut)
                raise
        self._locked = True
    
    def release(self):
        if not self._locked:
            raise RuntimeError('Lock is not acquired')
        self._locked = False
        if self._waiters:
            fut = self._waiters.pop(0)
            if not fut.cancelled():
                fut.set_result(None)
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    # def __repr__(self):
    #     status = 'locked' if self._locked else 'unlocked'
    #     return f'<StrictLock object at {hex(id(self))} [{status}]>'

# 全局锁对象
lock = None

async def create_lock():
    global lock
    lock = StrictLock()
    print("✅ lock created")
    print(f"    lock bound event loop: {lock._loop}")

async def use_lock():
    current_loop = asyncio.get_running_loop()
    print(f"    current event loop: {current_loop}")
    print(f"    lock bound event loop: {lock._loop}")
    print(f"    event loop is same: {current_loop is lock._loop}")
    
    try:
        async with lock:
            print("✅ lock acquired")
    except RuntimeError as e:
        print(f"❌ error: {e}")

def run_in_thread_1():
    print("\n📍 thread 1: create event loop and create lock")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(create_lock())
    finally:
        loop.close()

def run_in_thread_2():
    print("\n📍 thread 2: create new event loop and try to use lock")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(use_lock())
    finally:
        loop.close()

def demo_1_standard_asyncio():
    print("\n🔹 demo 1: standard asyncio.Lock")
    
    global lock
    
    async def create_standard_lock():
        global lock
        lock = asyncio.Lock()
        print("✅ standard lock created")
    
    async def use_standard_lock():
        try:
            async with lock:
                print("✅ standard lock used")
        except RuntimeError as e:
            print(f"❌ standard lock error: {e}")
    
    asyncio.run(create_standard_lock())
    asyncio.run(use_standard_lock())

def demo_2_strict_lock():
    print("\n🔹 demo 2: strict lock (simulate Python 3.10+ behavior)")
    
    thread1 = threading.Thread(target=run_in_thread_1)
    thread2 = threading.Thread(target=run_in_thread_2)
    
    thread1.start()
    thread1.join()
    
    time.sleep(0.1)
    
    thread2.start()
    thread2.join()

def demo_3_same_thread_different_loops():
    print("\n🔹 demo 3: same thread different event loops")
    
    global lock
    
    async def create():
        global lock
        lock = StrictLock()
        print("✅ lock created in first event loop")
    
    async def use():
        try:
            async with lock:
                print("✅ lock used in second event loop")
        except RuntimeError as e:
            print(f"❌ error: {e}")
    
    loop1 = asyncio.new_event_loop()
    asyncio.set_event_loop(loop1)
    loop1.run_until_complete(create())
    loop1.close()
    
    loop2 = asyncio.new_event_loop()
    asyncio.set_event_loop(loop2)
    loop2.run_until_complete(use())
    loop2.close()

if __name__ == "__main__":
    demo_1_standard_asyncio()
    demo_2_strict_lock()
    demo_3_same_thread_different_loops()
    
    # 🎯 summary:
    #  1. standard asyncio.Lock behavior is different in different Python versions
    # 2. When using asyncio in multi-threaded environments, be careful about the scope of locks
    # 3. solution: create independent lock objects in each event loop
    print("end")