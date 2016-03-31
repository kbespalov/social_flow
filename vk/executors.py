import asyncio
from aiohttp import ClientSession, TCPConnector
from vk.exceptions import VkDatabaseError, InvalidAccessToken, TooManyConnections
from vk.requests import Request


class AsyncRequestsExecutor(object):
    def __init__(self, workers, tokens=None, tasks_queue=None):
        self.workers_count = workers
        self.execute_workers = []
        self.process_workers = []
        self.exec_tasks = tasks_queue or asyncio.Queue()
        self.proc_tasks = asyncio.Queue()
        self.tokens = tokens or asyncio.PriorityQueue()
        self.is_run = False
        self.client = ClientSession(connector=TCPConnector(use_dns_cache=True, limit=1000))

    def start(self):
        self.is_run = True

        self.execute_workers = [self._exec_worker() for _ in range(self.workers_count)]
        self.process_workers = [self._proc_worker() for _ in range(self.workers_count)]

        asyncio.ensure_future(asyncio.wait(self.process_workers))
        asyncio.ensure_future(asyncio.wait(self.execute_workers))

    async def submit(self, request):
        if not self.is_run:
            self.start()
        await self.exec_tasks.put(request)

    async def _execute_request(self, request):
        verb = self.client.post if request.verb == 'POST' else self.client.get
        async with verb(request.url, data=request.params) as response:
            await response.read()
            await self.proc_tasks.put((request, response))

    async def _proc_worker(self):
        while self.is_run:
            request, response = await self.proc_tasks.get()
            if request.callback:
                try:
                    await request.callback(request, response)
                except (VkDatabaseError, TooManyConnections):
                    await asyncio.sleep(5)
                    await self.exec_tasks.put(request)

    async def _exec_worker(self):
        while self.is_run:
            request = await self.exec_tasks.get()
            if isinstance(request, Request) and request.need_auth:
                token = (await self.tokens.get())[1]
                await token.ready_for_use()
                request.access_token(token)
                await self.tokens.put((token.last_access, token))
            try:
                await self._execute_request(request)
            except InvalidAccessToken as e:
                print(e)
