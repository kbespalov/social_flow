from app.db import database_task, get_database_provider

db = get_database_provider().db


@database_task
async def insert_deactivated_users(users: list):
    await db.deactivated.insert({'id': user['id']} for user in users)


@database_task
async def clean_tokens():
    await db.tokens.remove()


@database_task
async def insert_instagram_users(users: list):
    await db.instagram_user.insert({'id': user['id'], 'inst': user['instagram']} for user in users)


@database_task
async def save_tokens(access: list):
    await db.tokens.insert(access)


async def load_tokens():
    cursor = db.tokens.find({}, {'_id': 0})
    tokens = []
    while await cursor.fetch_next:
        tokens.append(cursor.next_object())
    return tokens
