from multiprocessing import Lock

lock = Lock()
counters = {}

def inc_int(key= ""):
    global counters
    with lock:
        if key in counters:
            counters[key] += 1
        else:
            counters[key] = 1
        return counters[key]

