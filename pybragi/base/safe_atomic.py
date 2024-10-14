from multiprocessing import Lock

lock = Lock()
counter = 0

def inc_int():
    global counter
    with lock:
        counter += 1
        return counter

