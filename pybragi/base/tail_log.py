import os
from pybragi.base import time_utils
import traceback
import logging

@time_utils.elapsed_time_limit(0.005)
def _tail_line_log(logfile_path: str, tail: int) -> str:
    with open(logfile_path, "rb") as io:
        io.seek(0, 2)  # move to the end
        lines_found = 0
        block_size = 64 * 1024
        blocks = []

        while io.tell() > 0 and lines_found <= tail:
            io.seek(max(io.tell() - block_size, 0))
            block = io.read(block_size)
            blocks.append(block)
            lines_found += block.count(b"\n")
            
            io.seek(-len(block), 1) 
        
        all_read_bytes = b"".join(reversed(blocks))
        lines = all_read_bytes.splitlines()

        if tail >= len(lines):
            decoded_content = all_read_bytes.decode(errors='ignore')
        else:
            last_lines_bytes = b"\n".join(lines[-tail:])
            decoded_content = last_lines_bytes.decode(errors='ignore')

        return decoded_content


def safe_read_tail_log(logfile_path: str, tail: int) -> str:
    try:
        if not os.path.exists(logfile_path):
            logging.error(f"Log file not found: {logfile_path}")
            return ""
        return _tail_line_log(logfile_path, tail)
    except Exception as e:
        traceback.print_exc()
        logging.error(f"Error reading log file: {e}")
        return ""

if __name__ == "__main__":
    logfile = "/cano_nas01/workspace/online/llm_infer/logs/onetime_kafka/shve-aigc-gpt-H20-0002/dep#qwen2572_18k_8card_5#aigc_qwen_queue#vllm_triton_kafka-18001.log.3"
    data = safe_read_tail_log(logfile_path=logfile, tail=3000)
    # print(data)

