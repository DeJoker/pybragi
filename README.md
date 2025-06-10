
# pybragi is web server framework
- tronado http&websocket impl
  - flask way
  - fastapi way
- service-discovery and service-register
  - mongo way
  - consul way
- graceful shutdown
- prometheus metrics
- benchmark tools for openai_api and http_api
- kafka producer and consumer
  - sliding window 



## commandline

```bash
# simple server
python -m pybragi.base.base_handler --port=1122      

# system info     eth0 ipv4/disk/memory/gpu
python -m pybragi.base.ps

```

```bash
# http prof
python -m pybragi.bench.http_prof --url http://10.121.0.11:18000/healthcheck --num=100 --qps=40
python -m pybragi.bench.http_prof --url http://10.121.0.11:19000/v1/chat/completions --method=POST -H "Content-Type: application/json" --body='{"model": "Qwen3-235B-A22B", "messages": [{"role": "user", "content": "你好"}], "stream": false}' --num=10 --qps=3


# llm openai
python -m pybragi.bench.llm_openai --qps=2 --url=http://localhost:30000 --api-key=aaabbb --jsonl-file=https://xxx.com/queue-2025-05-12.jsonl --num=10 --model=qwen3_235b_0419_25k  --metrics-dir='/home/cxj/self/py3_server/output'

python -m pybragi.bench.llm_openai --show-metrics-pkl='/output/llm_openai_2025-05-12T15-48-27.pkl'


| 统计类型 | prompt_len | output_len | 端到端 | ttft | itl |
|---------|-----------|-----------|-------|------|-----|
| 平均值 | 8172.300 | 235.500 | 5170.644 | 306.232 | 95.763 |
| 中位数 | 8327.000 | 237.500 | 5211.785 | 305.749 | 89.392 |
| 99分位 | 9312.820 | 270.640 | 6036.196 | 339.780 | 125.736 |
| 最大值 | 9331.000 | 271.000 | 6069.074 | 340.317 | 127.126 |



# server dao_server_discovery

python -m pybragi.server.dao_server_discovery --mongo-url "mongodb://aa:bb@127.0.0.1:3717/?authSource=llm&retryWrites=true" --mongo-db=llm --action=show_type --model-type=openai

# --mongo-db=llm --action=show --model-type=openai # openai同步流式调用

# --mongo-db=llm --action=show_type_online # api+回调
# --mongo-db=llm --action=show_type_online --model-type=openai # openai同步流式调用

# --mongo-db=llm --action=show_type # api+回调
# --mongo-db=llm --action=show_type --model-type=openai # openai同步流式调用

# --mongo-db=llm --action=show_all_online # 完全所有
# --mongo-db=llm --action=show_all # 完全所有



```