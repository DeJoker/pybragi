#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from concurrent.futures import ThreadPoolExecutor, _base
import logging
import time
from contextlib import ContextDecorator
from datetime import datetime
import inspect
from functools import wraps, partial
import traceback
from typing import Callable, Optional

# old deprecate use elapsed_time_limit instead
def elapsed_time(func):
    @wraps(func)
    def inner(*args, **kwargs):
        start = time.perf_counter()
        res = func(*args, **kwargs)
        end = time.perf_counter()

        module_name = func.__module__
        if '.' in module_name:
            module_name = module_name.split('.')[-1]

        # logging.info(f'func: {func.__name__} took: {end-start:2.4f} sec')
        # logging.info('{} cost {}s'.format(func.__name__, end-start))
        logging.info(f'{func.__module__}.{func.__name__} cost {end-start:.3f}s')
        return res
    return inner


# old deprecate use elapsed_time_limit instead
def elapsed_time_callback(callback: Optional[Callable] = None):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            start = time.perf_counter()
            res = func(*args, **kwargs)
            end = time.perf_counter()

            # logging.info(f'func: {func.__name__} took: {end-start:2.4f} sec')
            # logging.info('{} cost {}s'.format(func.__name__, end-start))
            logging.info(f'{func.__module__}.{func.__name__} cost {end-start:.3f}s')
            if callback:
                callback(end-start)
            return res
        return inner
    return decorator

# callback: Callable | None = None
def elapsed_time_limit(limit, callback: Optional[Callable] = None):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            start = time.perf_counter()
            res = func(*args, **kwargs)
            end = time.perf_counter()

            if end-start > limit:
                logging.warning(f'{func.__module__}.{func.__name__} cost {end-start:.3f} sec')
            
            if callback:
                callback(end-start) 
            return res
        return inner
    return decorator


executor_timeout = ThreadPoolExecutor(max_workers=1)
def timeout_limit(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            future = executor_timeout.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except _base.TimeoutError:
                logging.warning(f"'{func.__module__}.{func.__name__}' timed out after {timeout} seconds.")
            except:
                traceback.print_exc()
        return wrapper
    return decorator


class ElapseCtx(ContextDecorator):
    # context manager
    # 用上下文管理器计时
    # https://stackoverflow.com/questions/70059794/get-function-name-when-contextdecorator-is-used-as-a-decorator
    # https://stackoverflow.com/questions/54539337/getting-line-number-of-return-statement
    def __init__(self, label: str = "", gt=0.0, callback=None):
        self.label = label
        self.gt = gt
        self.callback = callback

    def __call__(self, func):
        if not self.label:  # Label was not provided
            self.label = func.__name__  # Use function's name.
        return super().__call__(func)

    def __enter__(self):
        self.t0 = time.perf_counter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapse = round(time.perf_counter()-self.t0, 3)
        if elapse >= self.gt:
            logging.info(f'{self.label} cost: {elapse:.3f}s')
        if self.callback:
            self.callback(elapse)



#######################################################################
import datetime

def pretty_delta(total_seconds=0):
    delta = datetime.timedelta(seconds=total_seconds)
    
    from_ts = int(time.time()) - total_seconds
    from_dt = datetime.datetime.fromtimestamp(from_ts)
    
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    delta_ts = f"{delta.days} day {hours}:{minutes}:{seconds}"
    if delta.days <= 0:
        delta_ts = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
    return delta.days, delta_ts, from_dt.strftime("%Y-%m-%d %H:%M:%S")

