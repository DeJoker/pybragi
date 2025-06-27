
import requests
import traceback
import logging

from pybragi.bragi_config import BragiConfig
from pybragi.server import dao_server_discovery
from pybragi.base import hash

health_api_path = "/health"

class LoadBalanceStatus:
    roundrobin_cnt = 0
    weighted_roundrobin_cnt = 0
    hash_balance_cnt = 0
    boardcast_cnt = 0


def boardcast(servers, use_http: bool = True) -> list:
    hosts = []
    for server in servers:
        host = f"{server['ipv4']}:{server['port']}"
        if use_http:
            host = f"http://{host}"
        
        hosts.append(host)
    LoadBalanceStatus.boardcast_cnt += 1
    return hosts

#  health 超时请求最可能的问题是 对端服务阻塞 所以应该检查服务方ioloop等
def roundrobin(servers, api_path: str = health_api_path, use_http: bool = True, timeout=0.1) -> str:
    for _ in range(len(servers)):
        server = servers[LoadBalanceStatus.roundrobin_cnt % len(servers)]
        LoadBalanceStatus.roundrobin_cnt += 1
        host = f"{server['ipv4']}:{server['port']}"
        ret_host = f"http://{host}" if use_http else host
        if not BragiConfig.LBCheck:
            return ret_host
        
        try:
            resp = requests.get(f"http://{host}{api_path}", timeout=timeout)
            if resp.ok:
                return ret_host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
    raise Exception("No healthy server found")


def weighted_roundrobin(servers, api_path: str = health_api_path, use_http: bool = True, timeout=0.1) -> str:
    """加权轮询负载均衡算法"""
    weights = []
    total_weight = 0
    
    # 获取每个服务器的权重，默认为1
    for server in servers:
        weight = server.get('weight', 1)
        weights.append(weight)
        total_weight += weight
    
    if total_weight == 0:
        return roundrobin(servers, api_path)
    
    for _ in range(len(servers)):
        pos = LoadBalanceStatus.weighted_roundrobin_cnt % total_weight
        LoadBalanceStatus.weighted_roundrobin_cnt += 1
        
        for i, weight in enumerate(weights):
            if pos < weight:
                server = servers[i]
                break
            pos -= weight
        
        host = f"{server['ipv4']}:{server['port']}"
        ret_host = f"http://{host}" if use_http else host
        if not BragiConfig.LBCheck:
            return ret_host
        
        try:
            resp = requests.get(f"http://{host}{api_path}", timeout=timeout)
            if resp.ok:
                return ret_host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
    
    raise Exception("No healthy server found")


def hash_balance(servers: list, key: str, api_path: str = health_api_path, use_http: bool = True, timeout=0.1) -> str:
    """哈希负载均衡算法"""
    if not servers:
        raise Exception("No servers available")
    
    hash_value = hash.djb2_hash(key)
    
    retry_cnt, max_retry_cnt = 0, len(servers)
    while retry_cnt < max_retry_cnt:
        server_index = hash_value % len(servers)
        idx = server_index % len(servers)
        server = servers[idx]
        host = f"{server['ipv4']}:{server['port']}"
        ret_host = f"http://{host}" if use_http else host
        if not BragiConfig.LBCheck:
            return ret_host


        try:
            resp = requests.get(f"http://{host}{api_path}", timeout=timeout)
            if resp.ok:
                LoadBalanceStatus.hash_balance_cnt += 1
                return ret_host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            servers = servers[1:] # remove the unhealthy server
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
        retry_cnt += 1
    
    raise Exception("No healthy server found")

