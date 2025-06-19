from pybragi.base import mongo_base, ps
from config import Config, Mongo
from pybragi.server.dao_server_discovery import is_me_master
import logging

if __name__ == "__main__":
    mongo_base.new_store(Mongo.url, Mongo.db,  Mongo.max_pool_size)
    logging.info(f"init db {vars(Mongo)}")

    v4 = ps.get_ipv4()

    aa = is_me_master(v4, 13700, Config.Name,)
    print(aa)

    aa = is_me_master(v4, 13800, Config.Name,)
    print(aa)

    aa = is_me_master(v4, 90999, Config.Name,)
    print(aa)

