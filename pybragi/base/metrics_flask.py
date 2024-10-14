#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import time
import prometheus_client as pc
from flask import Flask, request, jsonify, Blueprint
from werkzeug.wrappers import Response
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# http://172.20.20.5:5302/metrics 参考test-chat-core服务


class MetricsManager:
    def __init__(self, name: str):
        # 最长30秒
        latency_buckets = [200, 500, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 9000, 10000, 11000,
                           12000, 14000, 16000, 18000, 20000, 22000, 24000, 26000, 28000, 30000, float("inf")]

        server_labels = ['service', 'uri']
        self.server_name = name
        self.request_qps = pc.Counter('metrics_httpsrv_qps', 'http接口请求量', server_labels)
        self.request_value = pc.Gauge('metrics_httpsrv_latency_gauge', 'http接口瞬时请求时延', server_labels)
        self.request_histogram = pc.Histogram('metrics_httpsrv_latency_histogram', 'http接口请求时延', server_labels,
                                              buckets=latency_buckets)
        
        task_queue_labels = ['service', 'queue_type']# ['priority', 'normal', 'batch',]
        self.task_queue_length = pc.Gauge('metrics_task_queue_length', '任务队列长度', task_queue_labels)

        task_process_labels = ['process'] # ['step1', 'step2', 'step3']
        task_latency_buckets = [200, 400, 600, 800, 1000, 1200, 1200, 1600, 1800, 2000,
                            3000, 4000, 5000, 6000, 8000, 9000, 10000, float("inf"),] # 最长10秒
        self.task_process_ms = pc.Histogram('metrics_task_latency_histogram', '任务处理时延', task_process_labels,
                                                    buckets=task_latency_buckets)

        task_total_buckets = [i*1000 for i in range(30)] + [float("inf")]
        self.total_request_ms = pc.Histogram('metrics_request_ms_histogram', '请求整体处理时间', [],
                                                    buckets=task_total_buckets)
        




metrics_manager: MetricsManager
def get_metrics_manager():
    global metrics_manager
    return metrics_manager


metrics_handler = Blueprint('metrics', __name__)
@metrics_handler.route("/metrics_shutdown", methods=['GET'])
def shutdown():
    # https://stackoverflow.com/questions/68885585/wait-for-value-then-stop-server-after-werkzeug-server-shutdown-is-deprecated
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func is None:
        raise RuntimeError('Not running werkzeug')
    shutdown_func()
    return


# 不要使用Blueprint注册 只会在当前blueprint生效
def register_metrics(app: Flask, name: str):
    global metrics_manager
    metrics_manager = MetricsManager(name)

    # Register middleware to record metrics
    @app.before_request
    def before_request():
        metrics_manager.request_qps.labels(name, request.path).inc()
        request.environ['prometheus_request_start_time'] = time.time()

    @app.after_request
    def after_request(response):
        start_time = request.environ.get('prometheus_request_start_time')
        if start_time is not None:
            latency = (time.time() - start_time) * 1000  # millisecond
            metrics_manager.request_value.labels(name, request.path).set(latency)
            metrics_manager.request_histogram.labels(name, request.path).observe(latency)
        return response

    @app.route('/metrics')
    def metrics():
        return Response(pc.generate_latest(), mimetype=pc.CONTENT_TYPE_LATEST)


