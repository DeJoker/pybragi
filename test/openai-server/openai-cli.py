from pybragi.base import log
import logging

import time
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:8293/v1",
    api_key="zy-7788",
    max_retries=0,
    timeout=2
)

completion = client.chat.completions.create(
  model="aabb",
  messages=[
    {"role": "user", "content": "你是谁啊"}
  ],
  frequency_penalty=0.0,
  temperature=0.8,
  top_p=0.9,
  max_tokens=512,
  extra_body={
    "repetition_penalty": 1.05,
    "min_tokens": 10,
    "top_k": 10,
    "mid": 135201,
    "timstamp": int(time.time()),
    "timstamp2": time.time(),
  },
  stream=True,
)

trim_cnt = 10
for chunk in completion:
    logging.info(chunk.choices[0].delta.content)
    trim_cnt -= 1
    if trim_cnt <= 0:
        break


# sglang log
# curl localhost:9900/configure_logging -H 'Content-Type: application/json' -d '{"log_requests":true, "log_requests_level":1, "dump_requests_threshold": 100}'

