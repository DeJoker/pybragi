
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


def get_all_server(type, online: bool = True) -> list[dict]:
    if type is None:
        query = {}
    else:
        query = {"type": type}

    if online:
        query["status"] = "online"
    return mongo_base.get_items(server_table, query)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", type=str, choices=["register", "unregister", "show_type", "show_type_online", "show_all", "show_all_online"], help="action")
    parser.add_argument("--model", type=str, help="model")
    parser.add_argument("--model-type", type=str, default="", help="model type")
    parser.add_argument("--mongo-url", type=str, help="mongo url")
    parser.add_argument("--mongo-db", type=str, help="mongo db name")
    parser.add_argument("--mongo-max-pool-size", type=int, default=4, help="mongo max pool size")
    parser.add_argument("--port", type=int, help="port")
    args = parser.parse_args()

    from pybragi.base import mongo_base
    from pybragi.base import ps
    from pybragi.server import dao_server_discovery

    mongo_base.new_store(args.mongo_url, args.mongo_db, args.mongo_max_pool_size)

    ipv4 = ps.get_ipv4()
    if args.action == "register":
        dao_server_discovery.register_server(ipv4, args.port, args.model, args.model_type)
    elif args.action == "unregister":
        dao_server_discovery.unregister_server(ipv4, args.port, args.model, args.model_type)
    elif args.action == "show_type_online":
        if args.model:
            res = dao_server_discovery.get_server_online(args.model, args.model_type)
        else:
            res = dao_server_discovery.get_all_server(args.model_type, online=True)
        print(mongo_base.pretty_print(res))
    elif args.action == "show_type":
        res = dao_server_discovery.get_all_server(args.model_type, online=False)
        print(mongo_base.pretty_print(res))
    elif args.action == "show_all":
        res = dao_server_discovery.get_all_server(None, online=False)
        print(mongo_base.pretty_print(res))
    elif args.action == "show_all_online":
        res = dao_server_discovery.get_all_server(None, online=True)
        print(mongo_base.pretty_print(res))
    else:
        print("Invalid action")
    
