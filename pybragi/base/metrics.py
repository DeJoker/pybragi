#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import logging
import time
import prometheus_client as pc
from tornado import web
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
# http://172.20.20.5:5302/metrics 参考test-chat-core服务


class MetricsManager:
    def __init__(self, name: str):
        latency_buckets = (
            [i * 100 for i in range(1, 10)]
            + [i * 1000 for i in range(1, 11)]
            + [i * 2000 for i in range(6, 16)]
        )
        big_latency_buckets = (
            latency_buckets + 
            [i * 3000 for i in range(11, 20)]
        )

        server_labels = ["service", "uri"]
        self.server_name = name
        self.request_qps = pc.Counter("metrics_httpsrv_qps", "http接口请求量", server_labels)
        self.request_value = pc.Gauge(
            "metrics_httpsrv_latency_gauge", "http接口瞬时请求时延", server_labels
        )
        self.request_histogram = pc.Histogram(
            "metrics_httpsrv_latency_histogram",
            "http接口请求时延",
            server_labels,
            buckets=latency_buckets,
        )

        task_queue_labels = [
            "service",
            "queue_type",
        ]  # ['priority', 'normal', 'batch',]
        self.task_queue_length = pc.Gauge(
            "metrics_task_queue_length", "任务队列长度", task_queue_labels
        )

        service_label = ["service"]

        self.caller_histogram = pc.Histogram(
            "caller_request_latency_histogram",
            "请求外部接口时延",
            [*service_label, "url"],
            buckets=latency_buckets,
        )

        self.task_latency_histogram = pc.Histogram(
            "metrics_task_latency_histogram",
            "任务处理时延",
            [*service_label, "task"],
            buckets=latency_buckets,
        )

        task_total_buckets = [i for i in range(30)]
        self.total_request_ms = pc.Histogram(
            "metrics_request_sec_histogram",
            "请求整体处理时间",
            service_label,
            buckets=task_total_buckets,
        )

        batch_buckets = [1] + [i * 2 for i in range(1, 20)]
        self.batch_process = pc.Histogram(
            "metrics_batch_process", "批处理数量", service_label, buckets=[1, 2, 4, 6, 8]
        )

        speed_labels = [
            "service",
            "backend",
        ]  # ['vllm-LLM', 'gptq', 'AutoModelForCausalLM',]
        self.token_speed = pc.Gauge(
            "metrics_infer_speed", "infer speed token/s", speed_labels
        )

        kafka_labels = [
            "topic",
            "partition",
        ]
        self.kafka_lag = pc.Gauge(
            "kafka_lag", "lag", kafka_labels
        )
        self.kafka_consume_batch = pc.Histogram(
            "kafka_batch", "batch", ["topic"], buckets=batch_buckets
        )
        self.batch_process_latency = pc.Histogram("batch_process_latency", "批任务-处理时延", ["topic"], buckets=big_latency_buckets)
        self.pretask_latency = pc.Histogram("pretask_latency", "单任务-时延", ["topic"], buckets=latency_buckets)

        self.task_get_latency = pc.Histogram("task_total_latency", "获取任务-时延", ["topic"], buckets=big_latency_buckets)
        self.triton_down = pc.Gauge("triton_down", "triton服务down", ["endpoint"])
        # self.task_total_latency = pc.Gauge("task_total_latency", "整体时延", ["topic"])
        self.remote_down = pc.Gauge("remote_down", "远端服务down", [*service_label, "endpoint"])

        self.except_cnt = pc.Counter("except_cnt", "异常数量", ["type", "except"])
        self.drop_cnt = pc.Counter("drop_cnt", "丢弃请求数量", ["topic"])



        


metrics_manager: MetricsManager


def get_metrics_manager():
    global metrics_manager
    return metrics_manager


def register_metrics(name: str):
    global metrics_manager
    metrics_manager = MetricsManager(name)


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
    def on_finish(self):
        path = self.request.path
        method = self.request.method
        request_time = self.request.request_time()
        status = self.get_status()

        get_metrics_manager().request_histogram.labels(
            metrics_manager.server_name, path
        ).observe(request_time)
        get_metrics_manager().request_qps.labels(
            metrics_manager.server_name, path
        ).inc()
    
    def write(self, chunk):
        if self.request.path not in pass_path:
            logging.info(f"{chunk}")
        super().write(chunk)


class StreamMtrics(BaseModel):
    # init var
    RequestId: str = ""
    FromKafkaTime: float = 0.0
    ArrivalTime: float = 0.0

    # temp inner var
    LastTokenTime: float = 0.0
    TokenCount: int = 0

    # performance metrics var
    TTFT: float = 0.0
    TPOT: float = 0.0
    OutputSpeed: float = 0.0
    InferTotal: float = 0.0
    DeltaStreaming: float = 0.0

    def output_token(self):
        current = time.perf_counter()
        
        if self.TokenCount == 0:
           self.TTFT = current - self.ArrivalTime
        else:
            self.TPOT = max(self.TPOT, current-self.LastTokenTime)
        self.TokenCount += 1
        self.LastTokenTime = current
        return
    
    def finish_infer(self, token_len=0):
        current = time.perf_counter()
        if token_len:
            self.TokenCount = token_len
            
        self.OutputSpeed = self.TokenCount/(current-self.ArrivalTime)
        self.InferTotal = current-self.ArrivalTime
        self.DeltaStreaming = self.InferTotal-self.TTFT

    def format_log(self):
        logging.info(f"{self.TTFT:.3f} {self.TPOT:.3f} {self.OutputSpeed:.3f} {self.InferTotal:.3f} {self.DeltaStreaming:.3f} " \
                     f"from_kafka_to_end: tokens:{self.TokenCount} request_id:{self.RequestId}")


