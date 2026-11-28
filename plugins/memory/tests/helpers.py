"""Shared test setup: the import path, a store that lives in memory, and an environment that never touches HOME."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "memory-keeping" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def isolated_env(root: Path, **extra) -> dict:
    """A copy of the environment whose config and data directories are under root."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_AGENCY_MEMORY") and k != "CLAUDE_PROJECT_DIR"}
    env["XDG_CONFIG_HOME"] = str(root / "config")
    env["XDG_DATA_HOME"] = str(root / "data")
    env.update(extra)
    return env


class FakeStore:
    """The store's contract without a database: word matching instead of a text index."""

    def __init__(self):
        self.docs = {}
        self.inserts = 0
        self.closed = 0

    def close(self):
        self.closed += 1

    def insert(self, doc):
        self.inserts += 1
        self.docs[doc["_id"]] = dict(doc)

    def get(self, project, memory_id):
        doc = self.docs.get(memory_id)
        return dict(doc) if doc and doc["project"] == project else None

    def recent(self, project, limit):
        mine = [d for d in self.docs.values() if d["project"] == project]
        mine.sort(key=lambda d: (d["pinned"], d["confirmedAt"]), reverse=True)
        return [dict(d) for d in mine[:limit]]

    def search(self, project, query, limit):
        words = query.lower().split()
        found = []
        for doc in self.recent(project, len(self.docs)):
            text = " ".join([doc["title"], doc["body"]] + doc["tags"]).lower()
            if any(w in text for w in words):
                found.append(doc)
        return found[:limit]

    def count(self, project):
        return sum(1 for d in self.docs.values() if d["project"] == project)

    def delete(self, project, memory_id):
        if self.get(project, memory_id) is None:
            return False
        del self.docs[memory_id]
        return True

    def mark_used(self, project, memory_id, when):
        if self.get(project, memory_id) is not None:
            self.docs[memory_id]["usedAt"] = when
