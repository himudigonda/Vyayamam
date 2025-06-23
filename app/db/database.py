# app/db/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.core.logging_config import log


class DataBase:
    client: AsyncIOMotorClient = None


db = DataBase()


async def connect_to_mongo():
    log.info("💾 DATABASE: Attempting to connect to MongoDB...")
    try:
        db.client = AsyncIOMotorClient(
            settings.MONGO_URI, serverSelectionTimeoutMS=5000
        )
        await db.client.server_info()  # Tries to connect and raises an exception on failure
        log.info("✅ SUCCESS: MongoDB connection established.")
    except Exception as e:
        log.error(f"❌ ERROR: Could not connect to MongoDB. Details: {e}")
        raise


async def close_mongo_connection():
    log.info("💾 DATABASE: Closing MongoDB connection.")
    db.client.close()


def get_db():
    if db.client is None:
        log.error("❌ ERROR: Database client not initialized.")
        raise Exception("Database client not initialized.")
    return db.client[settings.DB_NAME]
