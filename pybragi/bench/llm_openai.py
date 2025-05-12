import logging
from pybragi.base.counter import RunningStatus
from concurrent.futures import ThreadPoolExecutor
import pickle
import json
import os
import time
import uuid
import tqdm
from openai import OpenAI
from pybragi.base.metrics import StreamMetrics



def prepare_jsons(args):
    jsons = []
    if args.jsonl_file.startswith(('http://', 'https://')):
        import requests
        with requests.get(args.jsonl_file, stream=True) as resp:
            if resp.status_code != 200:
                logging.error(f"下载JSONL文件失败: {resp.status_code} {resp.reason}")
                raise Exception(f"downlaod jsonl-file failed: {resp.status_code} {resp.reason}")
            
            line_buffer = ""
            for chunk in resp.iter_content(chunk_size=8192, decode_unicode=True):
                if not chunk:
                    continue
                
                # read chunk to buffer
                if isinstance(chunk, bytes):
                    chunk = chunk.decode('utf-8')
                
                line_buffer += chunk
                
                lines = line_buffer.split('\n')
                line_buffer = lines.pop()
                
                for line in lines:
                    if line.strip():
                        data = json.loads(line)
                        jsons.append(data)
                        if args.num > 0 and len(jsons) >= args.num:
                            return jsons

    with open(args.jsonl_file, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                jsons.append(data)
                if len(jsons) >= args.num:
                    return jsons
    return jsons


def warmup(args, jsons):
    if args.warmup_strategy == "none":
        return
    
    if args.warmup_strategy == "count":
        warmup_jsons = jsons[:args.warmup_count]
    elif args.warmup_strategy == "prefill_history":
        warmup_jsons = jsons
    else:
        warmup_jsons = jsons

    client = OpenAI(
        base_url=f"{args.url}/v1",
        api_key=args.api_key,
        max_retries=1,
        timeout=60
    )

    for item in tqdm.tqdm(warmup_jsons, "warmup"):
        messages = item.get("messages", [])
        if not messages:
            messages = json.loads(item["raw_prompt"])
        
        if args.warmup_strategy == "prefill_history":
            messages = messages[:-1] # no_last_message   for kv cache

        completion = client.chat.completions.create(
            model=args.model,
            messages=messages,
            temperature=0.8,
            top_p=0.8,
            max_tokens=1, # for kv cache
            extra_body={
                "repetition_penalty": 1.05,
                "top_k": 40,
                "request_id": item.get("request_id", f"{int(time.time())}-{uuid.uuid4()}"),
                "mid": 135201,
                "timstamp": int(time.time()),
                "timstamp2": time.time(),
            },
            stream=True,
        )
        for chunk in completion:
            continue
        completion.close()
    

metrics_list = []
running_status = RunningStatus()

@running_status.running_decorator
def infer(args, item):
    client = OpenAI(
        base_url=f"{args.url}/v1",
        api_key=args.api_key,
        max_retries=1,
        timeout=60
    )

    messages = json.loads(item["raw_prompt"])
    
    now = time.time()
    request_id = item.get("request_id", f"{int(now)}-{uuid.uuid4()}")
    try:
        metrics = StreamMetrics(request_id, now, len(item["raw_prompt"]))
        completion = client.chat.completions.create(
            model=args.model,
            messages=messages,
            frequency_penalty=item.get("frequency_penalty", 0.0),
            temperature=item.get("temperature", 0.8),
            top_p=item.get("top_p", 0.8),
            max_tokens=item.get("max_new_tokens", 1024),
            extra_body={
                "repetition_penalty": item.get("repetition_penalty", 1.05),
                "top_k": item.get("top_k", 40),
                "mid": item.get("mid", 135201),
                "timstamp": int(now),
                "timstamp2": now,
                "request_id": request_id,
            },
            stream=True,
        )

        resp = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                metrics.output_token()
                resp += chunk.choices[0].delta.content
        completion.close()
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

    metrics.finish_infer()
    logging.info(resp)
    logging.info(f"{item['request_id']}: {metrics}")
    metrics_list.append(metrics)


def produce_task(args, jsons):
    with ThreadPoolExecutor(max_workers=args.num) as executor:
        for item in tqdm.tqdm(jsons, "produce_task"):
            executor.submit(infer, args, item)
            time.sleep(1 / args.qps)

def save_metrics(file_dir = ""):
    if not file_dir:
        return
    
    # filename = f"{os.path.dirname(__file__)}/triton_vllm_server-{time.strftime('%Y-%m-%dT%H-%M-%S')}.pkl"
    # filename = f"{os.path.dirname(__file__)}/vllm_server-{time.strftime('%Y-%m-%dT%H-%M-%S')}.pkl"
    # filename = f"{os.path.dirname(__file__)}/sglang_server-{time.strftime('%Y-%m-%dT%H-%M-%S')}.pkl"
    filename = os.path.join(file_dir, f"llm_openai_{time.strftime('%Y-%m-%dT%H-%M-%S')}.pkl")

    with open(filename, "wb") as f:
        pickle.dump(metrics_list, f)

def analyze():
    import numpy as np

    # change to ms
    prompt_len_list = np.array([metrics.prompt_len for metrics in metrics_list])
    output_len_list = np.array([metrics.output_token_count for metrics in metrics_list])
    e2e_list = np.array([metrics.infer_total for metrics in metrics_list]) * 1000
    ttft_list = np.array([metrics.ttft for metrics in metrics_list]) * 1000
    itl_list = np.array([metrics.max_token_delta for metrics in metrics_list]) * 1000

    prompt_mean = np.mean(prompt_len_list)
    prompt_median = np.percentile(prompt_len_list, [50])[0]
    prompt_p99 = np.percentile(prompt_len_list, [99])[0]
    prompt_max = np.max(prompt_len_list)
    
    output_mean = np.mean(output_len_list)
    output_median = np.percentile(output_len_list, [50])[0]
    output_p99 = np.percentile(output_len_list, [99])[0]
    output_max = np.max(output_len_list)
    
    e2e_mean = np.mean(e2e_list)
    e2e_median = np.percentile(e2e_list, [50])[0]
    e2e_p99 = np.percentile(e2e_list, [99])[0]
    e2e_max = np.max(e2e_list)
    
    ttft_mean = np.mean(ttft_list)
    ttft_median = np.percentile(ttft_list, [50])[0]
    ttft_p99 = np.percentile(ttft_list, [99])[0]
    ttft_max = np.max(ttft_list)
    
    itl_mean = np.mean(itl_list)
    itl_median = np.percentile(itl_list, [50])[0]
    itl_p99 = np.percentile(itl_list, [99])[0]
    itl_max = np.max(itl_list)

    
    row_table = """
## 性能指标表格 单位毫秒ms 行式

| 指标类型 | 平均值 | 中位数 | 99分位 | 最大值 |
|---------|-------|-------|-------|-------|
| prompt_len | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| output_len | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| 端到端 | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| ttft | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| itl | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
""".format(
        prompt_mean, prompt_median, prompt_p99, prompt_max,
        output_mean, output_median, output_p99, output_max,
        e2e_mean, e2e_median, e2e_p99, e2e_max,
        ttft_mean, ttft_median, ttft_p99, ttft_max,
        itl_mean, itl_median, itl_p99, itl_max
    )
    
    col_table = """
## 性能指标表格 单位毫秒ms 列式

| 统计类型 | prompt_len | output_len | 端到端 | ttft | itl |
|---------|-----------|-----------|-------|------|-----|
| 平均值 | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| 中位数 | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| 99分位 | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
| 最大值 | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
""".format(
        prompt_mean, output_mean, e2e_mean, ttft_mean, itl_mean,
        prompt_median, output_median, e2e_median, ttft_median, itl_median,
        prompt_p99, output_p99, e2e_p99, ttft_p99, itl_p99,
        prompt_max, output_max, e2e_max, ttft_max, itl_max
    )
    
    # 打印markdown表格
    print(row_table)
    print("\n\n")
    print(col_table)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-metrics-pkl", type=str, default="")
    parser.add_argument("--qps", type=int, default=2)
    parser.add_argument("--url", type=str, default="http://localhost:8000")
    parser.add_argument("--model", type=str, default="qwen3_235b_0228_18k")
    parser.add_argument("--api-key", type=str, default="")
    parser.add_argument("--jsonl-file", type=str, default="")
    parser.add_argument("--num", type=int, default=0)
    parser.add_argument("--metrics-dir", type=str, default="")
    parser.add_argument("--warmup-strategy", type=str, choices=["none", "prefill_history", "count"], default="prefill_history")
    parser.add_argument("--warmup-count", type=int, default=0)
    args = parser.parse_args()

    if args.show_metrics_pkl:
        with open(args.show_metrics_pkl, "rb") as f:
            metrics_list = pickle.load(f)
        analyze()
        exit()

    jsons = prepare_jsons(args)
    warmup(args, jsons)
    produce_task(args, jsons)
    while running_status.get_running_count() > 0:
        time.sleep(0.1)

    save_metrics(args.metrics_dir)
    analyze()

logging.info("end")
