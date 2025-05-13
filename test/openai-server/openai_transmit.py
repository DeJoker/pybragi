import os
import socket
from pybragi.base import ps

class ConfigOnline(object):
    Name = "openai_transmit"
    Port = 8293
    OpenAIPort = 19000
    MaxRunningCount = 50
    Backend = "sglang-openai"
    ApiKey = "zy-C49X29cophDG5y3UQTeXElwik4dF2ETUCwHv"


Config = ConfigOnline

openai_type = "openai"
ipv4 = ps.get_ipv4()

def is_port_available(port):
    """Return whether a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", port))
            s.listen(1)
            return True
        except socket.error:
            return False
        except OverflowError:
            return False



def server_port_available(range_start=18000, range_end=18100, backlog=128):
    for port in range(range_start, range_end):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", port))
            s.listen(backlog)
            return port, s
        except (socket.error, OverflowError):
            s.close()
    raise Exception("No available port")


