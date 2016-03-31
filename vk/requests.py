import threading
import time

import asyncio
from _md5 import md5
from urllib.parse import urlencode

import ujson

from vk.exceptions import ApiError, VkDatabaseError, TooManyConnections
from vk.utils import empty_context

api_endpoint = "https://api.vk.com/method/%s?"


class AccessToken:
    def __init__(self, value, login, secret, user_id, expireAt, app_id, access_delay=0.3):
        self.app_id = app_id
        self.login = login
        self.user_id = user_id
        self.secret = secret
        self.expireAt = expireAt
        self.value = value
        self.access_delay = access_delay
        self.last_access = time.time()

    async def ready_for_use(self, block=True):
        if block:
            delay = time.time() - self.last_access
            if delay < 0.5:
                await asyncio.sleep(0.5 - delay)
        self.last_access = time.time()
        return self.value

    def to_dict(self):
        return {'value': self.value,
                'login': self.login,
                'secret': self.secret,
                'user_id': self.user_id,
                'expireAt': self.expireAt,
                'app_id': self.app_id}


class BasicRequest(object):
    def __init__(self, url, params=None, callback=None, verb="GET"):
        self.url = url
        self._params = params
        self.callback = callback
        self.verb = verb
        self.context = empty_context()

    @property
    def params(self):
        return self._params


def basic_vk_callback(callback):
    async def wrapper(request, response):
        if response.status == 200:
            data = await response.json(loads=ujson.loads)
            if 'error' in data:
                if data['error']['error_code'] == 6:
                    raise TooManyConnections(data)
                else:
                    raise ApiError(data)
            elif 'response' not in data:
                raise VkDatabaseError(data)
            else:
                return await callback(request, data)
        else:
            # todo: check this brunch
            raise Exception(response.status)

    return wrapper


class Request(BasicRequest):
    def __init__(self, method, version, callback=None, need_auth=False):
        super().__init__(url=api_endpoint % method,
                         params=dict(v=version),
                         callback=callback,
                         verb="POST")
        self.need_auth = need_auth
        self.version = version
        self.method = method

    def access_token(self, token: AccessToken):
        self._params['access_token'] = token.value
        if token.secret:
            self.secret = token.secret

    @property
    def params(self):
        assert not (self.need_auth is None) or self.access_token, "trying to exec the request without a access token"
        # todo: implement request signing for nohttps mode. current problem - empty response body
        # params = urlencode(self._params)
        # if self.secret:
        #     params = urlencode(self._params)
        #     sig = md5(("{}?".format(self.method) + params + self.secret).encode('utf-8')).hexdigest()
        #     params += "&sig={}".format(sig)
        return self._params


class IterRequest(Request):
    def __init__(self, method, version, callback, items_per_request, need_auth=False):

        def handler_wrapper(request, response):
            if not response:
                request.stop_iteration = True
            else:
                if callback:
                    callback(request, response)

        super().__init__(method, version, need_auth, handler_wrapper)
        self.items_per_request = items_per_request
        self._params['offset'] = -items_per_request
        self.stop_iteration = False

    def __next__(self):
        if not self.stop_iteration:
            self._params['offset'] += self.items_per_request
            return self
        else:
            raise StopIteration

    def __iter__(self):
        return self


class UsersGet(Request):
    def __init__(self, user_ids, version=5.44, fields=None, callback=None, **kwargs):
        super().__init__('users.get', version, callback, **kwargs)
        self._params['user_ids'] = ','.join(str(x) for x in user_ids)
        self._params['fields'] = ','.join(fields)


class CountriesGet(IterRequest):
    def __init__(self, callback, need_all=1):
        super().__init__('database.getCountries', '5.44', callback, 1000)
        self._params['need_all'] = need_all
        self._params['count'] = 1000


class CitiesGet(IterRequest):
    def __init__(self, country_id, callback, need_all=1):
        super().__init__('database.getCities', '5.44', callback, 1000)
        self._params['need_all'] = need_all
        self._params['count'] = 1000
        self._params['country_id'] = country_id


class InstaGet(Request):
    def __init__(self, user_ids: list, callback=None):
        super().__init__('execute.instaGet', '5.44', callback, need_auth=True)
        self._params['uids'] = ','.join(str(x) for x in user_ids)
