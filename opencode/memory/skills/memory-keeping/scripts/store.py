"""The MongoDB side: the only module that imports the driver."""

from __future__ import annotations

import contextlib
from typing import Any, Dict, Iterator, List, Optional

import memconfig

DATABASE = "agent_memory"
COLLECTION = "memories"
AUTH_CODES = (13, 18)  # Unauthorized, AuthenticationFailed


class Unavailable(Exception):
    """Memory cannot be used right now. The message is safe to show."""


class AuthFailed(Unavailable):
    pass


class MongoStore:
    def __init__(self, uri: str, database: Optional[str] = None):
        try:
            import pymongo
        except ImportError:
            raise Unavailable("the MongoDB driver is not installed: run /memory:setup")
        self._pymongo = pymongo
        self._uri = uri
        with self._errors():
            self._client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000,
                                               socketTimeoutMS=5000, tz_aware=True)
            db = self._client[database] if database else self._client.get_default_database(default=DATABASE)
            self.database = db
            self._memories = db[COLLECTION]

    @contextlib.contextmanager
    def _errors(self) -> Iterator[None]:
        errors = self._pymongo.errors
        try:
            yield
        except errors.ServerSelectionTimeoutError:
            raise Unavailable("the database does not answer")
        except errors.OperationFailure as exc:
            if exc.code in AUTH_CODES:
                raise AuthFailed("the database refused the login")
            raise Unavailable("the database returned error %s" % exc.code)
        except errors.ConnectionFailure:
            raise Unavailable("the database does not answer")
        except (errors.PyMongoError, ValueError) as exc:
            raise Unavailable("the database cannot be used: %s"
                              % memconfig.redact(str(exc), self._uri)[:200])

    def close(self) -> None:
        self._client.close()

    def check(self) -> None:
        """Raise unless the database answers and this login may read the memories."""
        with self._errors():
            self._memories.find_one({}, {"_id": 1})

    def ensure_indexes(self) -> bool:
        """Create the indexes; True when one was missing."""
        with self._errors():
            before = set(self._memories.index_information())
            # project comes first in both, so a query is always inside one project
            self._memories.create_index(
                [("project", 1), ("title", "text"), ("body", "text"), ("tags", "text")],
                name="project_text", weights={"title": 10, "tags": 5, "body": 1})
            self._memories.create_index([("project", 1), ("pinned", -1), ("confirmedAt", -1)], name="project_recent")
            return set(self._memories.index_information()) != before

    def insert(self, doc: Dict[str, Any]) -> None:
        with self._errors():
            self._memories.insert_one(dict(doc))

    def get(self, project: str, memory_id: str) -> Optional[Dict[str, Any]]:
        with self._errors():
            return self._memories.find_one({"_id": memory_id, "project": project})

    def recent(self, project: str, limit: int) -> List[Dict[str, Any]]:
        with self._errors():
            return list(self._memories.find({"project": project})
                        .sort([("pinned", -1), ("confirmedAt", -1)]).limit(limit))

    def search(self, project: str, query: str, limit: int) -> List[Dict[str, Any]]:
        # plain words only: quotes and a leading minus are search operators to $text
        words = [word.lstrip("-") for word in query.replace('"', " ").split()]
        words = [word for word in words if word]
        if not words:
            return []
        score = {"$meta": "textScore"}
        with self._errors():
            found = self._memories.find({"project": project, "$text": {"$search": " ".join(words)}},
                                        {"score": score}).sort([("score", score)]).limit(limit)
            return [{key: value for key, value in doc.items() if key != "score"} for doc in found]

    def count(self, project: str) -> int:
        with self._errors():
            return self._memories.count_documents({"project": project})

    def delete(self, project: str, memory_id: str) -> bool:
        with self._errors():
            return self._memories.delete_one({"_id": memory_id, "project": project}).deleted_count == 1

    def mark_used(self, project: str, memory_id: str, when: Any) -> None:
        with self._errors():
            self._memories.update_one({"_id": memory_id, "project": project}, {"$set": {"usedAt": when}})
