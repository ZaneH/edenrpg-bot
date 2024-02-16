from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, Field
from models.pyobjectid import PyObjectId
from db.database import Database
from utils.level_calculator import current_level


COLLECTION_NAME = "users"


class UserInventoryItem(BaseModel):
    """
    Represents an arbitrary `amount` of items in the user's inventory.
    Any additional information could be added to `data` but nothing is
    making use of it yet.
    """
    amount: int
    data: Optional[Any] = None


class UserModel(BaseModel):
    """
    Represents a user in the database. This model is used to interact with
    the database and should only be used to interact with the database. This model
    is not used to interact with the user in the bot.
    """
    id: PyObjectId = Field(default_factory=PyObjectId, alias='_id')
    discord_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    balance: int = 0
    inventory: Dict[str, UserInventoryItem] = {}
    stats: Dict[str, int | float | Any] = {}

    @classmethod
    async def find_by_discord_id(cls, discord_id):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        doc = await collection.find_one({
            "discord_id": str(discord_id)
        })

        return cls(**doc) if doc else None

    @classmethod
    async def give_items(cls, discord_id, items, cost=0):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        result = await collection.update_one(
            {
                "discord_id": str(discord_id)
            },
            {
                "$inc": {
                    "balance": -cost,
                    **{
                        f"inventory.{item}.amount": amount
                        for item, amount in items.items()
                    }
                },
            },
        )

        return result.modified_count > 0

    @classmethod
    async def give_item(cls, discord_id, item, amount, cost=0):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        result = await collection.update_one(
            {
                "discord_id": str(discord_id),
                "balance": {"$gte": cost}
            },
            {
                "$inc": {
                    f"inventory.{item}.amount": amount,
                    "balance": -cost
                },
            },
        )

        return result.modified_count > 0

    @classmethod
    async def remove_item(cls, discord_id, item, amount, compensation=0):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        result = await collection.update_one(
            {
                "discord_id": str(discord_id),
                f"inventory.{item}.amount": {"$gte": amount}
            },
            {
                "$inc": {
                    f"inventory.{item}.amount": -amount,
                    "balance": compensation
                },
            },
        )

        return result.modified_count > 0

    @classmethod
    async def inc_stat(cls, discord_id, stat, amount=1):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        result = await collection.update_one(
            {
                "discord_id": str(discord_id),
            },
            {
                "$inc": {
                    f"stats.{stat}": amount
                },
            },
        )

        return result.modified_count > 0

    @classmethod
    async def inc_stats(cls, discord_id, stats):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        result = await collection.update_one(
            {
                "discord_id": str(discord_id),
            },
            {
                "$inc": {
                    f"stats.{stat}": amount
                    for stat, amount in stats.items()
                },
            },
        )

        return result.modified_count > 0

    async def save(self):
        collection = Database.get_instance().get_collection(COLLECTION_NAME)
        await collection.replace_one({"_id": self.id}, self.model_dump(), upsert=True)

    @property
    def current_level(self):
        return current_level(self.stats.get("xp", 0))

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True
        json_encoders = {
            ObjectId: str
        }
