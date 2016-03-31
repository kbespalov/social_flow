import asyncio

from vk.exceptions import VkDatabaseError


def validate_response(f):
    def validate(data):
        if 'response' not in data:
            print(data)
            raise VkDatabaseError
        elif 'error' in data:
            print(data)
            raise VkDatabaseError

    def handler(request, data):
        validate(data)
        return f(request, data)

    async def async_handler(request, data):
        validate(data)
        return await f(request, data)

    return async_handler if asyncio.iscoroutinefunction(f) else handler
