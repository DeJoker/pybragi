import time
import logging

from pybragi.base import mongo_base
from pybragi.base import time_utils

server_table = "servers"

def register_server(ipv4: str, port: int, name: str):
    now = round(time.time(), 4)
    query = {"ipv4": ipv4, "port": port, "name": name,}
    update = {
        "$set": {"status": "online", "timestamp": now}, 
        "$push": {
            "history": {
                "$each": [{ "status": "online", "timestamp": now }],
                "$slice": -10  # 只保留最近的10条记录
            }
        }
    }
    mongo_base.update_item(server_table, query, update, upsert=True)

def unregister_server(ipv4: str, port: int, name: str):
    now = round(time.time(), 4)
    query = {"ipv4": ipv4, "port": port, "name": name,}
    mongo_base.update_item(server_table, query, {
                "$set": { "status": "offline", "timestamp": now },
                "$push": { 
                    "history": {
                          "$each": [{ "status": "offline", "timestamp": now }],
                          "$slice": -10  # 只保留最近的10条记录
                    }
                }
            }
        )

@time_utils.elapsed_time_limit(0.005)
def get_server_online(name) -> list[dict]:
    query = {"name": name, "status": "online"}
    return mongo_base.get_items(server_table, query)


def remove_server(ipv4: str, port: int, name: str):
    try:
        # _remove_server_from_cache(ipv4, port, name)
        unregister_server(ipv4, port, name)
    except Exception as e:
        logging.error(f"remove_server error: {e}")

