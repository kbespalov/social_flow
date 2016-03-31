import asyncio
import json
import re

from app import db
from app import config
from app.db import api
from vk.auth import auth
from vk.executors import AsyncRequestsExecutor
from vk.requests import UsersGet, InstaGet, AccessToken, BasicRequest, basic_vk_callback
import logging


class CoreProvider:
    # todo: remove core provider instead make get_executor()
    def __init__(self, db_provider, app_list, app_scope, accounts, exec_workers_pool=50):
        self.app_list = app_list
        self.scope = app_scope
        self.accounts = accounts
        self.exec_workers_pool = exec_workers_pool
        self.access_tokens = asyncio.PriorityQueue()
        self.database_provider = db_provider
        self.executor = AsyncRequestsExecutor(self.exec_workers_pool, tokens=self.access_tokens)

    def get_loading(self):
        return {'exec_tasks': self.executor.exec_tasks.qsize(),
                'proc_tasks': self.executor.proc_tasks.qsize(),
                'db_tasks': api.get_database_provider().tasks_queue.qsize()}

    async def authorize_accounts(self):
        stored_tokens = await api.load_tokens()
        new_tokens = []
        login_set = set()

        for token_dict in stored_tokens:
            login_set.add(token_dict['login'])
            token = AccessToken(**token_dict)
            await self.access_tokens.put((token.last_access, token))

        for login, password in self.accounts.items():
            if login not in login_set:
                tokens = auth(login, password, self.app_list, self.scope)
                for token_dict in tokens:
                    new_tokens.append(token_dict.to_dict())
                    await self.access_tokens.put((token_dict.last_access, token_dict))
            logging.info(" [ auth stage ]: user {} is OK ".format(login))
        if new_tokens:
            await api.save_tokens(new_tokens)


_core_provider = None
_services_catalog = {}


async def get_core_provider():
    global _core_provider
    if not _core_provider:
        accounts = json.load(open(config.accounts_path))
        applications = json.load(open(config.apps_path))
        db_provider = db.get_database_provider()
        _core_provider = CoreProvider(app_list=applications['apps_ids'],
                                      app_scope=applications['scope'],
                                      accounts=accounts,
                                      exec_workers_pool=config.executor_workers_pool,
                                      db_provider=db_provider)
        await _core_provider.authorize_accounts()

        def loading_printer(delay=5):
            print(_core_provider.get_loading())
            asyncio.get_event_loop().call_later(delay, loading_printer)

        asyncio.get_event_loop().call_later(5, loading_printer)
    return _core_provider


def service(f):
    async def wrapper(*args, **kwargs):
        executor = (await get_core_provider()).executor
        wrapper.is_running = True
        return await f(executor, *args, **kwargs)

    return wrapper


@service
async def social_mapper(executor, ids):
    profile_instagram_less = []

    async def extract_id(request, response):
        if response.status == 200:
            html = await response.text()
            match = re.findall(r'<meta property="instapp:owner_user_id" content="(.+)"', html)
            if match:
                await api.insert_instagram_users([{'id': request.context.owner_id, 'instagram': match[0]}])
            else:
                print('error')
                # todo make context object for storing current state of execution, callbacks and etc
                pass
        elif response.status == 404:
            if request.context.links:
                request.url = request.context.links.pop()
                await executor.submit(request)

    @basic_vk_callback
    async def wall_filter(request, data):
        response = data['response'][0]
        instagram_links = response['photos']
        links = [link for link in instagram_links if link]
        if links:
            req = BasicRequest(url=links.pop(), callback=extract_id)
            req.context.links = links
            req.context.owner_id = response['owner_id']
            await executor.submit(req)

    @basic_vk_callback
    async def profile_filter(request, data):
        nonlocal profile_instagram_less
        response = data['response']
        deactivated_users = []
        instagram_users = []
        for user in response:
            if 'deactivated' in user:
                deactivated_users.append(user)
            elif 'instagram' in user:
                instagram_users.append(user)
            else:
                profile_instagram_less.append(user['id'])
                if len(profile_instagram_less) == 20:
                    _request = InstaGet(user_ids=profile_instagram_less,
                                        callback=wall_filter)
                    profile_instagram_less = []
                    await executor.submit(_request)
        await api.insert_instagram_users(instagram_users)
        await api.insert_deactivated_users(deactivated_users)

    uids_temp = []
    for uid in ids:
        uids_temp.append(uid)
        if len(uids_temp) == 1000:
            request = UsersGet(user_ids=uids_temp,
                               fields=['connections'],
                               callback=profile_filter,
                               need_auth=True)
            uids_temp = []
            await executor.submit(request)
