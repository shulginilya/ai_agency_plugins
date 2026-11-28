#!/usr/bin/env python3
"""remember, recall, get and forget the memories of one project.

    memory.py [--dir DIR] status
    memory.py [--dir DIR] index
    memory.py [--dir DIR] recall [QUERY] [--limit N]
    memory.py [--dir DIR] get ID
    memory.py [--dir DIR] remember --title T --body B|- [--type TYPE] [--tag T]... [--agent A]
    memory.py [--dir DIR] forget ID

DIR picks the project (default: CLAUDE_PROJECT_DIR, else the current directory).
Run remember and forget only when the user explicitly asks.

Exit status: 0 done, 1 memory is unavailable or there is no such memory, 2 bad input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import memconfig  # noqa: E402
import memproject  # noqa: E402
import records  # noqa: E402
import store as store_module  # noqa: E402

ID_RE = re.compile(r"^[0-9a-f]{16}$")
SKILL_DIR = Path(__file__).resolve().parent.parent
INDEX_FETCH = 200
RECALL_MAX = 50


class NotFound(Exception):
    def __init__(self) -> None:
        super().__init__("no memory with that id in this project")


class Memory:
    def __init__(self, store: Any, project: str, commit: Optional[str] = None):
        self.store = store
        self.project = project
        self.commit = commit

    def remember(self, title: Any = None, body: Any = None, type: Any = None, tags: Any = None,
                 agent: Any = None, session: Any = None) -> Dict[str, Any]:
        doc = records.build(self.project, title, body, type=type or "fact", tags=tags, owner=agent or "user",
                            source={"agent": agent, "session": session, "commit": self.commit})
        self.store.insert(doc)
        return doc

    def recall(self, query: Any = None, limit: Any = 10) -> List[Dict[str, Any]]:
        if query is not None and not isinstance(query, str):
            raise records.RecordError("the query must be text")
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise records.RecordError("the limit must be a whole number")
        limit = max(1, min(limit, RECALL_MAX))
        if not query or not query.strip():
            return self.store.recent(self.project, limit)
        return self.store.search(self.project, query, limit)

    def _id(self, memory_id: Any) -> str:
        if not isinstance(memory_id, str) or not ID_RE.match(memory_id):
            raise NotFound()
        return memory_id

    def get(self, memory_id: Any) -> Dict[str, Any]:
        doc = self.store.get(self.project, self._id(memory_id))
        if doc is None:
            raise NotFound()
        self.store.mark_used(self.project, memory_id, dt.datetime.now(dt.timezone.utc))
        return doc

    def forget(self, memory_id: Any) -> None:
        if not self.store.delete(self.project, self._id(memory_id)):
            raise NotFound()

    def close(self) -> None:
        self.store.close()

    def count(self) -> int:
        return self.store.count(self.project)

    def index(self) -> str:
        return records.index_text(self.project, self.store.recent(self.project, INDEX_FETCH), self.count())


def open_memory(directory: Path, env: Mapping[str, str] = os.environ) -> Memory:
    try:
        uri = memconfig.uri(env)
    except memconfig.ConfigError as exc:
        raise store_module.Unavailable(str(exc))
    if not uri:
        raise store_module.Unavailable("setup has not run: run /memory:setup")
    memconfig.add_driver_path(env)
    store = store_module.MongoStore(uri)
    return Memory(store, memproject.identify(directory), commit=memproject.head_commit(directory))


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", default=os.environ.get("CLAUDE_PROJECT_DIR"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("index")
    recall = commands.add_parser("recall")
    recall.add_argument("query", nargs="?")
    recall.add_argument("--limit", type=int, default=10)
    for name in ("get", "forget"):
        commands.add_parser(name).add_argument("id")
    remember = commands.add_parser("remember")
    remember.add_argument("--title", required=True)
    remember.add_argument("--body", required=True, help="the text, or - to read it from standard input")
    remember.add_argument("--type", choices=records.TYPES)
    remember.add_argument("--tag", action="append")
    remember.add_argument("--agent")
    args = parser.parse_args(argv)
    args.dir = args.dir or os.getcwd()
    # checked however it was chosen: the documented --dir "$PWD" is the skill's own directory after a cd into it
    chosen = Path(args.dir).resolve()
    if SKILL_DIR in (chosen, *chosen.parents):
        print("memory: that directory is inside the memory skill, which is not your project: run from the "
              "project and pass its directory with --dir", file=sys.stderr)
        return 2
    try:
        service = open_memory(Path(args.dir))
        if args.command == "status":
            count = service.count()
            source = memconfig.ENV_URI if os.environ.get(memconfig.ENV_URI) else memconfig.config_path()
            print("database: answers\nproject: %s\nmemories: %d\nconnection string: from %s"
                  % (service.project, count, source))
        elif args.command == "index":
            print(service.index())
        elif args.command == "recall":
            found = service.recall(args.query, limit=args.limit)
            print(records.result_json(memories=[records.summary(d) for d in found]))
        elif args.command == "get":
            print(records.result_json(memory=records.full(service.get(args.id))))
        elif args.command == "forget":
            service.forget(args.id)
            print("forgotten: %s" % args.id)
        else:
            body = sys.stdin.read() if args.body == "-" else args.body
            doc = service.remember(title=args.title, body=body, type=args.type, tags=args.tag, agent=args.agent)
            print(records.result_json(saved=records.summary(doc)))
    except records.RecordError as exc:
        print("memory: %s" % exc, file=sys.stderr)
        return 2
    except (store_module.Unavailable, NotFound) as exc:
        prefix = "memory is unavailable: " if isinstance(exc, store_module.Unavailable) else ""
        print("memory: %s%s" % (prefix, exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
