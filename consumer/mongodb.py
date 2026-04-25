import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")

mongodb_client: AsyncIOMotorClient = None
mongodb_db = None


async def connect_to_mongodb():
    global mongodb_client, mongodb_db
    mongodb_client = AsyncIOMotorClient(MONGODB_URL)
    mongodb_db = mongodb_client[MONGODB_DB_NAME]

    await mongodb_client.admin.command('ping')
    print(f"Consumer connected to MongoDB: {MONGODB_DB_NAME}")

    return mongodb_db


def get_mongodb():
    return mongodb_db

