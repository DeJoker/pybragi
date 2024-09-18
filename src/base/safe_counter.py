import threading
from contextlib import ContextDecorator

class ThreadSafeCounter: # 线程安全 多进程不安全
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def inc(self):
        with self.lock:
            self.value += 1

    def dec(self):
        with self.lock:
            self.value -= 1

    def get_value(self):
        with self.lock:
            return self.value
        

g_safe_counter = None
def global_safe_counter():
    global g_safe_counter
    if not g_safe_counter:
        g_safe_counter = ThreadSafeCounter()
    return g_safe_counter

