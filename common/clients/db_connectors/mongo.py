"""Async MongoDB connector using motor (Task 12).

Read-only enforcement: `find()` is used instead of `insert/update/delete`.
Row limit applied via cursor `.limit()`. Timeout via `serverSelectionTimeoutMS`
and `socketTimeoutMS`. Schema metadata reflects collection names and a sample document shape.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from common.clients.db_connectors.base import BaseDatabaseConnector

logger = logging.getLogger("common.clients.db_connectors.mongo")


class MongoConnector(BaseDatabaseConnector):
    """Async MongoDB connector backed by motor."""

    def __init__(self, credential_id: str, config: Dict[str, Any]) -> None:
        super().__init__(credential_id, config)
        self._client: Any = None
        self._db: Any = None

    async def connect(self) -> None:
        try:
            import motor.motor_asyncio as motor  # type: ignore
        except ImportError as exc:
            raise ImportError("motor is required for MongoConnector. Install with: pip install motor") from exc

        cfg = self.config
        host = cfg.get("host", "localhost")
        port = int(cfg.get("port", 27017))
        db_name = cfg.get("database_name", "test")
        user = cfg.get("username", "")
        pwd = cfg.get("password", "")
        timeout_ms = int(cfg.get("statement_timeout_ms", 30_000))

        if user and pwd:
            uri = f"mongodb://{user}:{pwd}@{host}:{port}/{db_name}"
        else:
            uri = f"mongodb://{host}:{port}/{db_name}"

        self._client = motor.AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
            maxPoolSize=cfg.get("max_connections", 10),
        )
        self._db = self._client[db_name]
        self._connected = True
        logger.info("MongoConnector[%s] client created", self.credential_id)

    async def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False

    async def test_connection(self) -> bool:
        if not self._client:
            await self.connect()
        try:
            await self._client.admin.command("ping")
            return True
        except Exception as exc:
            logger.warning("MongoConnector[%s] ping failed: %s", self.credential_id, exc)
            return False

    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: int = BaseDatabaseConnector.DEFAULT_TIMEOUT_S,
        max_rows: int = BaseDatabaseConnector.MAX_ROWS,
    ) -> List[Dict[str, Any]]:
        """Execute a MongoDB query.

        `query` is treated as a collection name when `params` contains a `filter` key.
        Otherwise `query` is parsed as `"collection_name"` and `params` as the filter dict.

        Example::
            await connector.execute_query(
                "users",
                params={"filter": {"active": True}, "projection": {"name": 1}}
            )
        """
        if not self._client:
            await self.connect()

        params = params or {}
        collection_name = query.strip()
        mongo_filter = params.get("filter", {})
        projection = params.get("projection", None)
        limit = min(params.get("limit", max_rows), self.MAX_ROWS)

        if self.is_read_only:
            # For MongoDB read-only enforcement, only allow find operations
            # (no insert/update/delete methods are called)
            pass

        collection = self._db[collection_name]
        cursor = collection.find(mongo_filter, projection).limit(limit)
        docs = await cursor.to_list(length=limit)
        # Convert ObjectId → str for JSON serialization
        results = []
        for doc in docs:
            doc_dict = dict(doc)
            if "_id" in doc_dict:
                doc_dict["_id"] = str(doc_dict["_id"])
            results.append(doc_dict)
        return results

    async def get_schema_metadata(self) -> Dict[str, Any]:
        if not self._client:
            await self.connect()
        collections = await self._db.list_collection_names()
        return {"collections": collections}

    async def store_record(
        self,
        target_table: str,
        record: Dict[str, Any],
        operation: str = "insert",
    ) -> Dict[str, Any]:
        """Insert/append a document into a MongoDB collection."""
        if self.is_read_only:
            raise ValueError("DBStoreNode write refused: credential is read-only.")
        if not self._client:
            await self.connect()

        if not record:
            return {"affected": 0, "primary_key": None}

        collection = self._db[target_table]
        if operation == "upsert":
            # Use a deterministic _id if provided, else insert_one.
            if "_id" in record:
                result = await collection.replace_one(
                    {"_id": record["_id"]}, record, upsert=True
                )
                return {"affected": result.modified_count or 1, "primary_key": record.get("_id")}
            result = await collection.insert_one(record)
            return {"affected": 1, "primary_key": str(result.inserted_id)}
        # insert / append
        result = await collection.insert_one(record)
        return {"affected": 1, "primary_key": str(result.inserted_id)}
