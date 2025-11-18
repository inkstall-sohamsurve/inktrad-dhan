"""
MongoDB database connection and collection management.
Uses Motor for async operations.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Optional
from app.core.config import settings


class Database:
    """MongoDB database manager using Motor (async driver)."""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect_db(cls):
        """Establish connection to MongoDB."""
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000  # 5 second timeout
            )
            cls.db = cls.client[settings.DATABASE_NAME]
            
            # Test connection
            await cls.client.admin.command('ping')
            
            # Create indexes for better performance
            await cls._create_indexes()
            
            print(f"✅ Connected to MongoDB: {settings.DATABASE_NAME}")
        except Exception as e:
            print(f"⚠️  MongoDB connection failed: {str(e)}")
            print("⚠️  Server will start without database features")
            print("⚠️  Live feed and demo endpoints will still work")
            cls.client = None
            cls.db = None
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            print("✅ MongoDB connection closed")
    
    @classmethod
    async def _create_indexes(cls):
        """Create database indexes for optimized queries."""
        # Users collection indexes
        users_collection = cls.get_collection("users")
        await users_collection.create_index("username", unique=True)
        await users_collection.create_index("email", unique=True)
        
        # Orders log collection indexes
        orders_collection = cls.get_collection("orders_log")
        await orders_collection.create_index("user_id")
        await orders_collection.create_index("dhan_order_id")
        await orders_collection.create_index([("user_id", 1), ("timestamp", -1)])

        # Trades collection indexes (used by trading dashboard)
        trades_collection = cls.get_collection("trades")
        await trades_collection.create_index("user_id")
        await trades_collection.create_index("trade_id", unique=True)
        await trades_collection.create_index([("user_id", 1), ("entry_time", -1)])
        
        # Watchlists collection indexes
        watchlists_collection = cls.get_collection("watchlists")
        await watchlists_collection.create_index("user_id")
        await watchlists_collection.create_index([("user_id", 1), ("name", 1)])
    
    @classmethod
    def get_collection(cls, collection_name: str) -> AsyncIOMotorCollection:
        """
        Get a MongoDB collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            AsyncIOMotorCollection instance
        """
        if cls.db is None:
            raise RuntimeError("Database not connected. Call connect_db() first.")
        return cls.db[collection_name]
    
    @classmethod
    def get_users_collection(cls) -> AsyncIOMotorCollection:
        """Get the users collection."""
        return cls.get_collection("users")
    
    @classmethod
    def get_watchlists_collection(cls) -> AsyncIOMotorCollection:
        """Get the watchlists collection."""
        return cls.get_collection("watchlists")
    
    @classmethod
    def get_orders_log_collection(cls) -> AsyncIOMotorCollection:
        """Get the orders_log collection."""
        return cls.get_collection("orders_log")

    @classmethod
    def get_trades_collection(cls) -> AsyncIOMotorCollection:
        """Get the trades collection used for storing executed trades."""
        return cls.get_collection("trades")


# Convenience function to get database instance
def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance."""
    if Database.db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return Database.db
