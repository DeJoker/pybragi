
import requests
import traceback
import logging

from pybragi.version import __version__
from pybragi.base import hash
from pybragi.server import dao_server_discovery


health_api_path = "/health"

class LoadBalanceStatus:
    roundrobin_cnt = 0
    weighted_roundrobin_cnt = 0
    hash_balance_cnt = 0
    boardcast_cnt = 0


def boardcast(servers) -> list:
    hosts = []
    for server in servers:
        hosts.append(f"http://{server['ipv4']}:{server['port']}")
    LoadBalanceStatus.boardcast_cnt += 1
    return hosts


def roundrobin(servers, api_path: str = health_api_path) -> str:
    for _ in range(len(servers)):
        server = servers[LoadBalanceStatus.roundrobin_cnt % len(servers)]
        LoadBalanceStatus.roundrobin_cnt += 1
        host = f"http://{server['ipv4']}:{server['port']}"
        try:
            resp = requests.get(f"{host}{api_path}", timeout=0.1)
            if resp.ok:
                return host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
    raise Exception("No healthy server found")


def weighted_roundrobin(servers, api_path: str = health_api_path) -> str:
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
        
        host = f"http://{server['ipv4']}:{server['port']}"
        try:
            resp = requests.get(f"{host}{api_path}", timeout=0.1)
            if resp.ok:
                return host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
    
    raise Exception("No healthy server found")


def hash_balance(servers: list, key: str, api_path: str = health_api_path) -> str:
    """哈希负载均衡算法"""
    if not servers:
        raise Exception("No servers available")
    
    hash_value = hash.djb2_hash(key)
    
    retry_cnt, max_retry_cnt = 0, len(servers)
    while retry_cnt < max_retry_cnt:
        server_index = hash_value % len(servers)
        idx = server_index % len(servers)
        server = servers[idx]
        host = f"http://{server['ipv4']}:{server['port']}"
        try:
            resp = requests.get(f"{host}{api_path}", timeout=0.1)
            if resp.ok:
                LoadBalanceStatus.hash_balance_cnt += 1
                return host
        except Exception as e:
            traceback.print_exc()
            dao_server_discovery.unregister_server(server['ipv4'], server['port'], server['name'], status="offline_unhealthy", type=server['type'])
            servers = servers[1:] # remove the unhealthy server
            logging.error(f"{api_path} failed, unregister server: {server['ipv4']}:{server['port']}")
            continue
        retry_cnt += 1
    
    raise Exception("No healthy server found")

