"""MongoDB helper for SafariNewsletter."""

from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from src.configs.config import settings


class MongoDB:
    """Thin wrapper around PyMongo for this project."""

    def __init__(self, uri: str = settings.MONGO_URI, db_name: str = settings.MONGO_DB_NAME) -> None:
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_collection(self, name: str = settings.ARTICLES_COLLECTION) -> Collection:
        return self.db[name]

    def insert_many(self, collection: str, documents: List[Dict[str, Any]]) -> Any:
        coll = self.get_collection(collection)
        if not documents:
            return None
        return coll.insert_many(documents)

    def find(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        coll = self.get_collection(collection)
        cursor = coll.find(query or {})
        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def delete_many(self, collection: str, query: Optional[Dict[str, Any]] = None) -> Any:
        coll = self.get_collection(collection)
        return coll.delete_many(query or {})

    def drop_collection(self, collection: str) -> None:
        self.db.drop_collection(collection)
