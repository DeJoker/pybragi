from concurrent.futures import ThreadPoolExecutor
import time
import pycurl
from io import BytesIO
import sys
from pydantic import BaseModel
import numpy as np
from pybragi.base.counter import RunningStatus
from tqdm import tqdm

class RequestLatency(BaseModel):
    success: bool = True
    namelookup_time: float = 0.0
    connect_time: float = 0.0
    pretransfer_time: float = 0.0
    starttransfer_time: float = 0.0
    setup_and_send_preparation_time: float = 0.0
    waiting_for_server_response_time: float = 0.0
    content_download_time: float = 0.0
    total_time: float = 0.0


latencySt_list = []
running_status = RunningStatus()

@running_status.running_decorator
def make_http_request(url, method="GET", headers=None, body=None, print_log=True, verbose=False):
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)

    if headers:
        c.setopt(pycurl.HTTPHEADER, headers)

    if method.upper() == "POST":
        c.setopt(pycurl.POST, 1)
        if body:
            c.setopt(pycurl.POSTFIELDS, body.encode('utf-8'))
        else:
            c.setopt(pycurl.POSTFIELDS, "") # Ensure POSTFIELDS is set for POST even if body is empty
    elif method.upper() == "GET":
        c.setopt(pycurl.HTTPGET, 1)
    # Add other methods here if needed in the future

    # verbose log
    if verbose:
        c.setopt(c.VERBOSE, True)
        c.setopt(c.DEBUGFUNCTION, lambda type, data: print(data.decode('utf-8', 'ignore'), end='', file=sys.stderr))

    latencySt = RequestLatency()
    try:
        c.perform()

        # 获取计时信息 毫秒
        latencySt.namelookup_time = c.getinfo(pycurl.NAMELOOKUP_TIME) * 1000
        latencySt.connect_time = c.getinfo(pycurl.CONNECT_TIME) * 1000 # 从开始到TCP连接建立完成
        latencySt.pretransfer_time = c.getinfo(pycurl.PRETRANSFER_TIME) * 1000 # 从开始到准备传输(所有协商完成)
        latencySt.starttransfer_time = c.getinfo(pycurl.STARTTRANSFER_TIME) * 1000 # 从开始到接收到第一个字节 (TTFB)
        latencySt.total_time = c.getinfo(pycurl.TOTAL_TIME) * 1000 # 总时间

        http_code = c.getinfo(pycurl.HTTP_CODE)

        # 计算您关心的阶段
        # 阶段1: 连接建立和请求准备时间 (Setup and Request Preparation)
        # 这包括 DNS, TCP连接, (SSL/TLS握手 if HTTPS), 以及curl准备并发送请求的时间。
        # "Request Sent" 的精确度不如 httpie, 但 pretransfer_time 涵盖了所有传输前的准备工作。
        latencySt.setup_and_send_preparation_time = latencySt.pretransfer_time

        # 阶段2: 服务端响应等待时间 (Waiting for Server Response / TTFB)
        latencySt.waiting_for_server_response_time = latencySt.starttransfer_time - latencySt.pretransfer_time

        # 阶段3: 内容下载时间 (Content Download)
        latencySt.content_download_time = latencySt.total_time - latencySt.starttransfer_time

        if print_log:
            print(f"HTTP 状态码: {http_code}")
            try:
                response_body_str = buffer.getvalue().decode('utf-8')
                print(f"HTTP response: {response_body_str}")
            except UnicodeDecodeError:
                print(f"HTTP response (raw bytes): {buffer.getvalue()}")
            
            print(f"--- 请求耗时分解 ---")
            print(f"1. 连接建立与请求准备: {latencySt.setup_and_send_preparation_time:.3f}ms")
            print(f"2. 服务端响应等待 (TTFB): {latencySt.waiting_for_server_response_time:.3f}ms")
            print(f"3. 内容下载: {latencySt.content_download_time:.3f}ms")
            print(f"----------------------")
            print(f"总耗时: {latencySt.total_time:.3f}ms")

        if verbose:
            print(f"\n--- Curl 详细计时 (从开始计算的累计时间) ---")
            print(f"DNS 解析耗时: {latencySt.namelookup_time:.3f}ms")
            print(f"TCP 连接耗时 (累计): {latencySt.connect_time:.3f}ms")
            print(f"预传输耗时 (累计): {latencySt.pretransfer_time:.3f}ms")
            print(f"首字节到达耗时 (累计 TTFB): {latencySt.starttransfer_time:.3f}ms")

    except pycurl.error as e:
        latencySt.success = False
        errno, errstr = e.args
        print(f"PycURL 错误:")
        print(f"  错误号: {errno}")
        print(f"  错误信息: {errstr}")
    finally:
        c.close()
    
    latencySt_list.append(latencySt)
    return latencySt


def concurrent_make_http_request(url, method, headers, body, num, qps, verbose=False):
    print(f"Request URL: {url}")
    print(f"Method: {method}")
    if headers:
        print(f"Headers: {headers}")
    if body and method.upper() == "POST":
        print(f"Body: {body}")
    
    # Make one initial request to print full details if needed
    make_http_request(url, method=method, headers=headers, body=body, print_log=True, verbose=verbose)

    # Reset latency list for the concurrent run, keeping the first one if it was successful (or handle as needed)
    # For simplicity here, we clear it assuming analyze_latency_st_list processes all including the first.
    # If the first request's stats are crucial and distinct, manage latencySt_list accordingly.
    # For now, the first request's stats will be part of the overall analysis.

    with ThreadPoolExecutor(max_workers=num+2) as executor:
        for _ in tqdm(range(num -1 if num > 0 else 0), "Sending requests"): # num-1 because one already sent
            executor.submit(make_http_request, url, method, headers, body, False, verbose)
            time.sleep(1/qps)

    while running_status.get_running_count() > 0:
        time.sleep(0.1)


def analyze_latency_st_list():
    latencySt_list_success = [latencySt for latencySt in latencySt_list if latencySt.success]
    print(f"总请求：{len(latencySt_list)} 失败请求数: {len(latencySt_list) - len(latencySt_list_success)}")

    request_sent = np.array([latencySt.setup_and_send_preparation_time for latencySt in latencySt_list_success])
    ttfb = np.array([latencySt.waiting_for_server_response_time for latencySt in latencySt_list_success])
    content_download = np.array([latencySt.content_download_time for latencySt in latencySt_list_success])
    total = np.array([latencySt.total_time for latencySt in latencySt_list_success])


    print(f"1. 连接建立与请求准备      mean:{np.mean(request_sent):.3f}ms P50:{np.percentile(request_sent, 50):.3f}ms P90:{np.percentile(request_sent, 90):.3f}ms max:{np.max(request_sent):.3f}ms")
    print(f"2. 服务端响应等待 (TTFB):      mean:{np.mean(ttfb):.3f}ms P50:{np.percentile(ttfb, 50):.3f}ms P90:{np.percentile(ttfb, 90):.3f}ms max:{np.max(ttfb):.3f}ms")
    print(f"3. 内容下载      mean:{np.mean(content_download):.3f}ms P50:{np.percentile(content_download, 50):.3f}ms P90:{np.percentile(content_download, 90):.3f}ms max:{np.max(content_download):.3f}ms")
    print(f"4. 总耗时      mean:{np.mean(total):.3f}ms P50:{np.percentile(total, 50):.3f}ms P90:{np.percentile(total, 90):.3f}ms max:{np.max(total):.3f}ms")



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--method", type=str, default="GET")
    parser.add_argument("-H", "--header", dest="headers", action="append", default=[], help="Add custom header. Repeat for multiple headers (e.g., -H 'Content-Type: application/json').")
    parser.add_argument("--body", type=str, default="")
    
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--qps", type=float, default=1.0)

    args = parser.parse_args()
    concurrent_make_http_request(args.url, args.method, args.headers, args.body, args.num, args.qps, args.verbose)
    analyze_latency_st_list()

