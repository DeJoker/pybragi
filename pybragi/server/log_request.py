import logging
import json
import os
import datetime
import fcntl  # filelock
from pybragi.base import time_utils

total_log_count = 0
last_log_file = ""


# not strict threading lock, but it's ok for static log_dir

@time_utils.elapsed_time_limit(0.05) # about 50ms to nas
def log_request_to_file(name, request_json, log_dir="/cano_nas01/cyj/request", max_lines=1e6):
    global total_log_count, last_log_file
    try:
        os.makedirs(log_dir, exist_ok=True)

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        filename = f"{name}-{today}.jsonl"
        filepath = os.path.join(log_dir, filename)

        if last_log_file == filepath and total_log_count > max_lines:
            return
        
        with open(filepath, 'a+') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                # ensure global variables update in filelock
                # f.seek(0)
                # total_log_count = sum(1 for _ in f) # accurate but slow

                total_log_count += 1 # only calculate self-increment
                last_log_file = filepath

                f.seek(0, 2)  # move to end
                f.write(json.dumps(request_json) + '\n')
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logging.error(f"Error logging request: {e}")

