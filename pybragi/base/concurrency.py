import threading
from typing import Callable

class ThreadManager:
    def __init__(self, target:Callable, args=(), count=1):
        self.target = target
        self.args = args
        self.threads = []
        self._create_and_start_threads(count)

    def _create_and_start_threads(self, count):
        for _ in range(count):
            thread = threading.Thread(target=self.target, args=self.args)
            thread.start()
            self.threads.append(thread)
    
    def join(self):
        for thread in self.threads:
            thread.join()

    def add_threads(self, count=1):
        self._create_and_start_threads(count)
    
    def reduce_threads(self, count=1):
        # 简单的减少线程方法，不推荐在实际项目中使用，因为这可能会导致线程被强制关闭
        # 实际应用中应根据线程执行的任务类型来优雅地关闭线程
        to_remove = self.threads[:count]
        for thread in to_remove:
            if thread.is_alive():
                thread.join()  # 等待线程自然结束
            self.threads.remove(thread)
    
    def get_active_thread_count(self):
        return len([t for t in self.threads if t.is_alive()])
