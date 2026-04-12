from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId
from typing import Optional

from app.config import settings

# Module-level client — set once at startup
_client: Optional[AsyncIOMotorClient] = None


# ---------- Lifecycle ----------

async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()


def _get_collection():
    if _client is None:
        raise RuntimeError("Database is not connected. Call connect_db() first.")
    return _client[settings.db_name]["clones"]


# ---------- Helpers ----------

def _serialize(doc: dict) -> dict:
    """Convert ObjectId to string for JSON serialisation."""
    doc["_id"] = str(doc["_id"])
    return doc


# ---------- CRUD ----------

async def insert_clone(data: dict) -> str:
    """Insert a clone document and return its string ID."""
    collection = _get_collection()
    result = await collection.insert_one(data)
    return str(result.inserted_id)


async def fetch_all_clones() -> list[dict]:
    collection = _get_collection()
    return [_serialize(doc) async for doc in collection.find()]


async def fetch_clone_by_id(clone_id: str) -> Optional[dict]:
    collection = _get_collection()
    try:
        doc = await collection.find_one({"_id": ObjectId(clone_id)})
    except InvalidId:
        return None
    return _serialize(doc) if doc else None


async def update_clone_fields(clone_id: str, fields: dict) -> bool:
    """Patch arbitrary fields on an existing clone record."""
    collection = _get_collection()
    try:
        result = await collection.update_one(
            {"_id": ObjectId(clone_id)}, {"$set": fields}
        )
    except InvalidId:
        return False
    return result.matched_count == 1


async def delete_clone_by_id(clone_id: str) -> bool:
    """Delete a clone record. Returns True when a document was deleted."""
    collection = _get_collection()
    try:
        result = await collection.delete_one({"_id": ObjectId(clone_id)})
    except InvalidId:
        return False
    return result.deleted_count == 1
