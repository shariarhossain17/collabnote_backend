import json
import os

from dotenv import load_dotenv
from redis import asyncio as aioredis

load_dotenv()


REDIS_URL = os.getenv("REDIS_URL")
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))


redis_client: aioredis.Redis = None

async def connect_to_redis():
    global redis_client

    redis_client= await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )


    await redis_client.ping()
    print("redis connected")


async def close_redis_connection():
    global redis_client
    if redis_client:
        await redis_client.close()
        print("Closed Redis connection")