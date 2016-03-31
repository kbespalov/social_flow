import re
import requests
from time import time
from urllib.parse import parse_qs

from vk.requests import AccessToken


class AuthException(BaseException):
    pass


def _base_auth(login, password, session):
    resp = session.ready_for_use('https://m.vk.com/').text
    form_action = re.findall(r'<form(?= ).* action="(.+)"', resp)
    if form_action:
        data = {'email': login, 'pass': password}
        session.post(form_action[0], data)
        if 'p' not in session.cookies:
            raise AuthException('incorrect login or password')
    else:
        raise AuthException('login form action is not found.')


def _oauth(login, app, scope, session):
    url = "https://oauth.vk.com/authorize"
    params = {'client_id': app, 'scope': scope, 'response_type': 'token'}
    resp = session.post(url, params)
    if 'access_token' not in resp.url:
        form_action = re.findall(r'<form(?= ).* action="(.+)"', resp.text)[0]
        resp = session.post(form_action)
        if 'access_token' not in resp.url:
            raise AuthException('Grant accessing to app failure')
    data = parse_qs(resp.url.split('#')[1])
    secret = data.get('secret', None)
    return AccessToken(value=data['access_token'][0],
                       login=login,
                       user_id=data['user_id'][0],
                       secret=secret[0] if secret else None,
                       app_id=app,
                       expireAt=time() + int(data['expires_in'][0]))


def auth(login, password, app_list, scope):
    tokens = []
    with requests.Session() as session:
        _base_auth(login, password, session)
        for app in app_list:
            tokens.append(_oauth(login, app, scope, session))
    return tokens
