# app/db/database.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings


class DataBase:
    client: AsyncIOMotorClient = None


db = DataBase()


async def get_database_client() -> AsyncIOMotorClient:
    """Returns the database client instance."""
    return db.client


async def connect_to_mongo():
    """Connects to the MongoDB database."""
    print("Connecting to MongoDB...")
    # We use motor for asyncio support, which is ideal for FastAPI
    db.client = AsyncIOMotorClient(settings.MONGO_URI)
    print("✅ MongoDB connection successful.")


async def close_mongo_connection():
    """Closes the MongoDB connection."""
    print("Closing MongoDB connection...")
    db.client.close()
    print("✅ MongoDB connection closed.")


def get_db():
    """
    A convenience function to get the database instance from the client.
    This will be used by our CRUD operations.
    """
    if db.client is None:
        raise Exception("Database client not initialized. Call connect_to_mongo first.")
    return db.client[settings.DB_NAME]
