


class BaseServerDiscoveryStore:
    def __init__(self, url: str, database: str, max_pool_size: int):
        self.url = url
        self.database = database
        self.max_pool_size = max_pool_size

    def get_db(self):
        return self.db
    
