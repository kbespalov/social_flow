import asyncio
import functools

from motor.motor_asyncio import AsyncIOMotorClient
from app import config

_db_provider = None


class DatabaseProvider:
    def __init__(self, conn_url, db_name, db_workers_pool=50):
        self.db_workers_pool = db_workers_pool
        self.tasks_queue = asyncio.Queue(db_workers_pool)
        self.workers = [self._db_worker() for _ in range(db_workers_pool)]
        self.async_client = AsyncIOMotorClient(conn_url)
        self.db = self.async_client[db_name]
        asyncio.ensure_future(self._prepare_database())
        asyncio.ensure_future(asyncio.wait(self.workers))

    async def _prepare_database(self):
        if 'tokens' not in (await self.db.collection_names()):
            await self.db.tokens.create_index("expireAt", expireAfterSeconds=0)

    async def _db_worker(self):
        while True:
            task = await self.tasks_queue.get()
            await task()
            self.tasks_queue.task_done()

    async def submit_task(self, task):
        return await self.tasks_queue.put(task)


def get_database_provider():
    global _db_provider, db
    if not _db_provider:
        _db_provider = DatabaseProvider(config.db_url,
                                        config.database_name,
                                        config.database_workers_pool)
        db = _db_provider.db
    return _db_provider


def database_task(function):
    async def wrapper(*args, **kwargs):
        await get_database_provider().submit_task(functools.partial(function, *args, **kwargs))

    return wrapper
