#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import json
import logging
import time
import prometheus_client as pc
from tornado import web
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor


class MetricsManager:
    latency_buckets = (
        [round(0.025*i, 3) for i in range(40)] +
        [round(0.1*i, 3) for i in range(10, 51)]
    )
    big_latency_buckets = (
        latency_buckets + 
        [2*i for i in range(3, 16)] +
        [3*i for i in range(11, 20)]
    )

    speed_buects = (
        [3*i for i in range(50)]
    )

    service_label = ["service"]
    server_labels = [*service_label, "uri", "status"]
    task_queue_labels = [*service_label, "queue_type"] # ['priority', 'normal', 'batch',]
    speed_labels = [ "backend", ]  # ['vllm', 'sglang', 'transformer',]

    def __init__(self, name: str, big_latency=False, kafka=False):
        if big_latency:
            latency_buckets = MetricsManager.big_latency_buckets
        else:
            latency_buckets = MetricsManager.latency_buckets
        
        self.server_name = name
        self.request_qps = pc.Counter("metrics_httpsrv_qps", "http接口请求量", MetricsManager.server_labels)
        self.request_histogram = pc.Histogram(
            "metrics_httpsrv_latency_histogram",
            "http接口请求时延",
            MetricsManager.server_labels,
            buckets=latency_buckets,
        )

        self.task_queue_length = pc.Gauge(
            "metrics_task_queue_length", "任务队列长度", MetricsManager.task_queue_labels
        )

        self.caller_histogram = pc.Histogram(
            "caller_request_latency_histogram",
            "请求外部接口时延",
            [*MetricsManager.service_label, "url"],
            buckets=latency_buckets,
        )

        self.task_latency_histogram = pc.Histogram(
            "metrics_task_latency_histogram",
            "任务处理时延",
            [*MetricsManager.service_label, "task"],
            buckets=latency_buckets,
        )

        task_total_buckets = [i for i in range(30)]
        self.total_request_lantency = pc.Histogram(
            "metrics_request_sec_histogram",
            "请求整体处理时间",
            MetricsManager.service_label,
            buckets=task_total_buckets,
        )

        self.batch_process = pc.Histogram(
            "metrics_batch_process", "批处理数量", MetricsManager.task_queue_labels, buckets=[1, 2, 4, 6, 8]
        )

        self.token_speed = pc.Histogram(
            "metrics_infer_speed", "infer speed token/s", MetricsManager.speed_labels, buckets=MetricsManager.speed_buects
        )
        self.ttft_latency = pc.Histogram(
            "metrics_ttft_latency", "ttft latency", MetricsManager.speed_labels, buckets=MetricsManager.latency_buckets
        )
        self.tpot_latency = pc.Histogram(
            "metrics_tpot_latency", "tpot latency", MetricsManager.speed_labels, buckets=MetricsManager.latency_buckets
        )
        

        if kafka:
            kafka_labels = [
                "topic",
                "partition",
            ]
            self.kafka_lag = pc.Gauge(
                "kafka_lag", "lag", kafka_labels
            )

            batch_buckets = [1] + [i * 4 for i in range(1, 26)]
            self.kafka_consume_batch = pc.Histogram(
                "kafka_batch", "batch", ["topic"], buckets=batch_buckets
            )

            self.batch_process_latency = pc.Histogram("batch_process_latency", "批任务-处理时延", ["topic"], buckets=latency_buckets)

            self.task_get_latency = pc.Histogram("task_total_latency", "获取任务-时延", ["topic"], buckets=latency_buckets)

        self.triton_down = pc.Gauge("triton_down", "triton服务down", ["endpoint"])
        self.remote_down = pc.Gauge("remote_down", "远端服务down", [*MetricsManager.service_label, "endpoint"])

        self.except_cnt = pc.Counter("except_cnt", "异常数量", ["type", "except"])
        self.drop_cnt = pc.Counter("drop_cnt", "丢弃请求数量", ["topic"])

        self.status = pc.Gauge(
            "status", "状态值", ["type"]
        )



metrics_manager: MetricsManager


def get_metrics_manager():
    global metrics_manager
    return metrics_manager


def register_metrics(name: str, big_latency=False, kafka=False):
    global metrics_manager
    metrics_manager = MetricsManager(name, big_latency, kafka)


class MetricsHandler(web.RequestHandler):
    executor = ThreadPoolExecutor(1)
    def _log(self):
        return

    @run_on_executor
    def get(self):
        self.set_header("Content-Type", pc.CONTENT_TYPE_LATEST)
        self.write(pc.generate_latest())


pass_path = ["/healthcheck", "/metrics"]
class PrometheusMixIn(web.RequestHandler):
    def prepare(self):
        if self.request.method != "POST":
            return
        
        if len(self.request.body) < 500:
            logging.info(f"{self.request.path} body: {self.request.body}")
        elif self.request.headers.get('Content-Type') == "application/json":
            body = json.loads(self.request.body)
            try:
                print_kv = {k: v for k, v in body.items() if len(str(v)) < 200}
                logging.info(f"{self.request.path} part body: {print_kv}")
            except Exception as e:
                pass

    def on_finish(self):
        path = self.request.path
        method = self.request.method
        request_time = self.request.request_time()
        status = self.get_status()

        mgr = get_metrics_manager()

        mgr.request_histogram.labels(
            mgr.server_name, path, status
        ).observe(request_time)
        mgr.request_qps.labels(
            mgr.server_name, path, status
        ).inc()
    
    def write(self, chunk):
        if self.request.path not in pass_path:
            if isinstance(chunk, dict):
                print_kv = {k: v for k, v in chunk.items() if len(str(v)) < 200}
                logging.info(f"{self.request.path} part response: {print_kv}")
        super().write(chunk)


class StreamMetrics:
    def __init__(self, request_id, timestamp2, prompt_len) -> None:
        self.request_id = request_id
        self.timestamp2 = timestamp2
        self.prompt_len = prompt_len

        self.start = time.time()
        self.start_perf = time.perf_counter()
        self.last_token_time = 0
        self.max_token_delta = 0
        self.output_token_count = 0

    def output_token(self):
        current = time.perf_counter()
        
        if self.output_token_count == 0:
           self.ttft = current - self.start_perf
        else:
            self.max_token_delta = max(self.max_token_delta, current-self.last_token_time)
        self.output_token_count += 1
        self.last_token_time = current
        return
    
    def finish_infer(self, token_len=0):
        current = time.perf_counter()
        if token_len:
            self.output_token_count = token_len
            
        self.output_speed = self.output_token_count/(current-self.start_perf)
        self.infer_total = current-self.start_perf
        self.delta_streaming = self.infer_total-self.ttft

    def dict(self):
        return {
            "request_id": self.request_id,
            "prompt_len": self.prompt_len,
            "output_token_count": self.output_token_count,
            "produce_at": self.timestamp2,
            "infer_start_delta": self.start-self.timestamp2,
            "ttft": self.ttft,
            "tpot": self.max_token_delta,
            "speed": self.output_speed,
            "infer_total": self.infer_total,
            "delta_streaming": self.delta_streaming,
            "from_request_total": time.time()-self.timestamp2,
        }

    def __str__(self):
        str = f"request_id={self.request_id} prompt_len:{self.prompt_len} output_token_count:{self.output_token_count} produce_at:{self.timestamp2:.3f} " \
            f"infer_start_delta:{self.start-self.timestamp2:.3f} " \
            f"ttft:{self.ttft:.3f} tpot:{self.max_token_delta:.3f} speed:{self.output_speed:.3f} token/s " \
            f"infer_total:{self.infer_total:.3f} delta_streaming:{self.delta_streaming:.3f} from_request_total:{time.time()-self.timestamp2:.3f}"
        return str



if __name__ == "__main__":
    def test_metrics():
        import random
        met = StreamMetrics(request_id="123", timestamp2=time.time(), prompt_len=100)
        for _ in range(10):
            time.sleep(random.randint(1, 50)*0.001)
            met.output_token()
        met.finish_infer()
        print(f"{met}")

    test_metrics()

    # print(MetricsManager.latency_buckets)
    # print(MetricsManager.big_latency_buckets)
    # test_for_valid_bucket = pc.Histogram("test", "xxx", ["hhh"], buckets=MetricsManager.big_latency_buckets)
    # test_for_valid_bucket = pc.Histogram("test", "xxx", ["hhh"], buckets=[0,1,1.1,1]) # Buckets not in sorted order
    # test_for_valid_bucket = pc.Histogram("test", "xxx", ["hhh"], buckets=[0,1,1]) # Duplicated timeseries in CollectorRegistry
    print("end")


