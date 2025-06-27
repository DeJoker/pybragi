import queue
import threading
import logging

from typing import Optional

class PriorityQueue:
    def __init__(self, size=800):
        self.priority_queue = queue.Queue(size)
        self.normal_queue = queue.Queue(size*2)
        self.event = threading.Event()

    def empty(self):
        return self.priority_queue.empty() and self.normal_queue.empty()
    
    def put(self, item, priority=False):
        if priority:
            self.priority_queue.put(item)
        else:
            self.normal_queue.put(item)
        self.event.set()

    # 不抛queue.Empty异常 空队列返回None
    def get(self, timeout=0.2):
        self.event.wait(timeout)
        # if not self.event.is_set():
        #     raise queue.Empty

        item = None
        try:
            item = self.priority_queue.get(block=False)
        except queue.Empty:
            pass

        if item is None:
            try:
                item = self.normal_queue.get(timeout=0.2)
            except queue.Empty:
                self.event.clear()
        
        return item
    
    def statistics(self):
        priority = self.priority_queue.qsize()
        normal = self.normal_queue.qsize()
        if priority != 0 or normal != 0:
            logging.info(f"priority size:{priority} normal size:{normal}")
        return priority, normal


class BatchQueue:
    def __init__(self, size=800, batch_nums=[1, 8]):
        self.queue = queue.Queue(size)
        self.lock = threading.Lock()
        self.batch_nums = sorted(batch_nums, reverse=True)

    def put(self, item):
        self.queue.put(item)
    
    def empty(self):
        return self.queue.empty()

    # 多消费队列 如果单消费者可以不使用lock
    # 不抛queue.Empty异常 空队列返回None
    def get(self, timeout=0.2):
        with self.lock:
            size = self.queue.qsize()
            for n in self.batch_nums:
                if size >= n:
                    batch = []
                    for i in range(n):
                        batch.append(self.queue.get())
                    return batch

        # 否则一定一个一个取
        try:
            item = self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
        return [item]
    
    def statistics(self):
        size = self.queue.qsize()
        if size != 0:
            logging.info(f"queue size:{size}")
        return size


# 初始化&get方法二合一
g_batch_queue :BatchQueue
def global_batch_queue(task_queue :Optional[BatchQueue] = None):
    global g_batch_queue
    if task_queue:
        g_batch_queue = task_queue
    return g_batch_queue



# 初始化&get方法二合一
g_priority_queue :PriorityQueue
def global_priority_queue(task_queue :Optional[PriorityQueue] = None):
    global g_priority_queue
    if task_queue:
        g_priority_queue = task_queue
    return g_priority_queue


# temporary backward compatibility
from pybragi.base.shutdown import global_exit_event
g_exit_event = global_exit_event()

