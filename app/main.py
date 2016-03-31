import asyncio

from app.services import social_mapper


async def start():
    # from_id = input('from id: ')
    # to_id = input('to id: ')
    await social_mapper(range(1, 1000000))


asyncio.ensure_future(start())
asyncio.get_event_loop().run_forever()
