
import logging
from datetime import datetime
from pybragi.base import mongo_base
from pybragi.base import time_utils


server_table = "servers"


def register_server(ipv4: str, port: int, name: str, type: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    query = {"ipv4": ipv4, "port": port, "name": name, "type": type}
    
    update = {
        "$set": {"status": "online", "datetime": now}, 
        "$push": {
            "history": {
                "$each": [{ "status": "online", "datetime": now }],
                "$slice": -10  # 只保留最近的10条记录
            }
        }
    }
    mongo_base.update_item(server_table, query, update, upsert=True)


def unregister_server(ipv4: str, port: int, name: str, status: str = "offline", type: str = ""):
    if status == "online":
        status = "offline" # online is forbid for unregister

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    query = {"ipv4": ipv4, "port": port, "name": name, "type": type}
    logging.info(f"{query}")
    mongo_base.update_item(server_table, query, {
                "$set": { "status": status, "datetime": now },
                "$push": { 
                    "history": {
                          "$each": [{ "status": status, "datetime": now }],
                          "$slice": -10  # 只保留最近的10条记录
                    }
                }
            }
        )

def check_self(ipv4: str, port: int, name: str, type: str = ""):
    query = {"ipv4": ipv4, "port": port, "name": name, "status": "online", "type": type}
    items = mongo_base.get_items(server_table, query)
    if len(items) > 0:
        return True
    return False

# @cache_server_status
# @time_utils.elapsed_time # mongo only use 1ms
def get_server_online(name: str, type: str = "") -> list[dict]:
    query = {"name": name, "status": "online", "type": type}
    return mongo_base.get_items(server_table, query)


def remove_server(ipv4: str, port: int, name: str, type: str = ""):
    try:
        unregister_server(ipv4, port, name, type)
    except Exception as e:
        logging.error(f"remove_server error: {e}")


def get_all_server(type: str = "", online: bool = True) -> list[dict]:
    query = {"type": type}
    if online:
        query["status"] = "online"
    return mongo_base.get_items(server_table, query)
