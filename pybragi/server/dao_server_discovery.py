
import logging
import time
from functools import wraps
from pybragi.base import mongo_base
from pybragi.base import time_utils


server_table = "servers"


def register_server(ipv4: str, port: int, name: str):
    now = round(time.time(), 4)
    query = {"ipv4": ipv4, "port": port, "name": name,}
    update = {
        "$set": {"status": "online", "timestamp": now}, 
        "$push": {"history": {"status": "online", "timestamp": now}}
    }
    mongo_base.update_item(server_table, query, update, upsert=True)


def unregister_server(ipv4: str, port: int, name: str, status: str = "offline"):
    if status == "online":
        status = "offline" # online is forbid for unregister

    now = round(time.time(), 4)
    query = {"ipv4": ipv4, "port": port, "name": name,}
    logging.info(f"{query}")
    mongo_base.update_item(server_table, query, {
                "$set": { "status": status, "timestamp": now },
                "$push": { 
                    "history": {
                          "$each": [{ "status": status, "timestamp": now }],
                          "$slice": -10  # 只保留最近的10条记录
                    }
                }
            }
        )

# @cache_server_status
# @time_utils.elapsed_time # mongo only use 1ms
def get_server_online(name) -> list[dict]:
    query = {"name": name, "status": "online"}
    return mongo_base.get_items(server_table, query)


def remove_server(ipv4: str, port: int, name: str):
    try:
        # _remove_server_from_cache(ipv4, port, name)
        unregister_server(ipv4, port, name)
    except Exception as e:
        logging.error(f"remove_server error: {e}")

