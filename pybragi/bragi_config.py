

class BragiConfig:
    IPv4 = "127.0.0.1"
    LBCheck = True # LoadBalanceWithHealthCheck
    ForceExitTimeout = 20.0 # seconds


class MongoConfig:
    url = "mongodb://mongo:xmsBKGGwrt@127.0.0.1:3717/?authSource=store&etryWrites=true"
    db = "store"
    max_pool_size = 4
    table = "users"
