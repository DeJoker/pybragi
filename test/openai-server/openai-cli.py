from pybragi.base import time_utils
import logging
import time
from openai import OpenAI

# url = "http://llm-gateway.character.xunlei.com"
url = "http://127.0.0.1:8888"

client = OpenAI(
    base_url=f"{url}/v1",
    api_key="zy-fqwefqwef",
    max_retries=3,
    timeout=2
)

# curl localhost:50001/v1/models | jq .
res = client.models.list()
logging.info(res)

completion = client.chat.completions.create(
  model="qwen3_235b_cpt_0419_25k_2",
  messages=[
    {"role": "user", "content": "你是谁啊"}
  ],
  frequency_penalty=0.0,
  temperature=0.8,
  top_p=0.9,
  max_tokens=512,
  extra_body={
    "repetition_penalty": 1.05,
    "min_tokens": 100,
    "top_k": 10,
    "mid": 135201,
    "timstamp": int(time.time()),
    "timstamp2": time.time(),
  },
  stream=True,
)

trim_cnt = 1000
for chunk in completion:
    if chunk.choices[0].delta.content:
        logging.info(chunk.choices[0].delta.content)
        trim_cnt -= 1
        if trim_cnt <= 0:
            break
completion.close()
print("done")

# curl localhost:9900/configure_logging -H 'Content-Type: application/json' -d '{"log_requests":true, "log_requests_level":1, "dump_requests_threshold": 100}'



