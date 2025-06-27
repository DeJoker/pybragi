
import threading


g_exit_event = None
def global_exit_event():
    global g_exit_event
    if not g_exit_event:
        g_exit_event = threading.Event()
    return g_exit_event
