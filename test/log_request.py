from pybragi.server.log_request import log_request_to_file
import os
log_file = f"{os.path.abspath(os.path.dirname(__file__))}/xxx"

log_request_to_file("test", {"a": 1}, log_file)
log_request_to_file("test", {"a": 2}, log_file)
log_request_to_file("test", {"a": 3}, log_file)
