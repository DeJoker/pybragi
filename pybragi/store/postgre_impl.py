import logging
import traceback
from typing import Any, Optional
import asyncio
import asyncpg

class PostgreImpl:
    def __init__(self, host: str, port: int, database: str, user: str, password: str, max_pool_size: int = 10):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.max_pool_size = max_pool_size

        self.pool: Optional[asyncpg.Pool] = None

    async def initdb(self):
        try:
            self.pool = await asyncpg.create_pool(user=self.user, password=self.password,
                                        database=self.database, host=self.host,
                                        min_size=1, max_size=self.max_pool_size)
        except Exception as e:
            traceback.print_exc()
            logging.error(
                f"PostgreSQL, Failed to connect database at , Got:{e}"
            )
            raise

    async def create_table(self, table_name: str, ddl: str):
        try:
            logging.info(f"PostgreSQL, Try Creating table {table_name} in database")
            await self.execute(ddl)
            logging.info(
                f"PostgreSQL, Creation success table {table_name} in PostgreSQL database"
            )
        except Exception:
            traceback.print_exc()
            raise


    async def check_table(self, table_name: str, ddl = ""):
        try:
            await self.query(f"SELECT 1 FROM {table_name} LIMIT 1")
            logging.info(f"PostgreSQL, check table {table_name} passed")
        except Exception:
            if ddl:
                await self.create_table(table_name, ddl)
            else:
                traceback.print_exc()
    
    async def query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        multirows: bool = False,
        with_age: bool = False,
        graph_name: str | None = None,
    ) -> dict[str, Any] | None | list[dict[str, Any]]:
        async with self.pool.acquire() as connection:  # type: ignore
            if with_age and graph_name:
                await self.configure_age(connection, graph_name)  # type: ignore
            elif with_age and not graph_name:
                raise ValueError("Graph name is required when with_age is True")

            try:
                if params:
                    rows = await connection.fetch(sql, *params.values())
                else:
                    rows = await connection.fetch(sql)

                if multirows:
                    if rows:
                        columns = [col for col in rows[0].keys()]
                        data = [dict(zip(columns, row)) for row in rows]
                    else:
                        data = []
                else:
                    if rows:
                        columns = rows[0].keys()
                        data = dict(zip(columns, rows[0]))
                    else:
                        data = None

                return data
            except Exception as e:
                logging.error(f"PostgreSQL database, error:{e}")
                raise

    async def execute(
        self,
        sql: str,
        data: dict[str, Any] | None = None,
        upsert: bool = False,
        with_age: bool = False,
        graph_name: str | None = None,
    ):
        try:
            async with self.pool.acquire() as connection:  # type: ignore
                if with_age and graph_name:
                    await self.configure_age(connection, graph_name)  # type: ignore
                elif with_age and not graph_name:
                    raise ValueError("Graph name is required when with_age is True")

                if data is None:
                    await connection.execute(sql)  # type: ignore
                else:
                    await connection.execute(sql, *data.values())  # type: ignore
        except (
            asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.DuplicateTableError,
        ) as e:
            if upsert:
                # logging.info("Key value duplicate, but upsert succeeded.")
                pass
            else:
                logging.error(f"Upsert error: {e}")
        except Exception as e:
            logging.error(f"PostgreSQL database,\nsql:{sql},\ndata:{data},\nerror:{e}")
            traceback.print_exc()
            raise

class ClientManager:
    _instances: dict[str, Any] = {"db": None, "ref_count": 0}
    _lock = asyncio.Lock()

    @classmethod
    async def init_client(cls, *args, **kwargs):
        if cls._instances["db"] is None:
            db = PostgreImpl(*args, **kwargs)
            await db.initdb()
            cls._instances["db"] = db
            cls._instances["ref_count"] = 0
        else:
            db = cls._instances["db"]

    async def check_table(self, table_name: str, ddl: str):
        if self._instances["db"] is None:
            raise Exception("Client not initialized")
        await self._instances["db"].check_table(table_name, ddl)

    @classmethod
    async def get_client(cls) -> PostgreImpl:
        async with cls._lock:
            if cls._instances["db"] is None:
                raise Exception("Client not initialized")
            cls._instances["ref_count"] += 1
            return cls._instances["db"]

    @classmethod
    async def release_client(cls, db: PostgreImpl):
        async with cls._lock:
            if not db:
                return
            
            if db is cls._instances["db"]:
                cls._instances["ref_count"] -= 1
                if cls._instances["ref_count"] == 0:
                    await db.pool.close()
                    logging.info("Closed PostgreSQL database connection pool")
                    cls._instances["db"] = None
            else:
                await db.pool.close()

