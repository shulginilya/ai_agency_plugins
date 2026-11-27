#!/usr/bin/env python3
"""The same promises against a real, throwaway MongoDB (AC6, AC7, AC8, AC10).

Runs when AI_AGENCY_MEMORY_TEST_URI names the server (no database in the path)
and pymongo is importable; otherwise every test is reported as skipped. With
AI_AGENCY_MEMORY_TEST_REQUIRED set, as in the CI database job, a skip is a failure.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from helpers import PLUGIN, isolated_env
import memory
import records
import store as store_module

SERVER_URI = os.environ.get("AI_AGENCY_MEMORY_TEST_URI")
REQUIRED = bool(os.environ.get("AI_AGENCY_MEMORY_TEST_REQUIRED"))


def why_not():
    if not SERVER_URI:
        return "AI_AGENCY_MEMORY_TEST_URI is not set"
    try:
        import pymongo  # noqa: F401
    except ImportError:
        return "pymongo is not installed"
    return None


REASON = why_not()


class PreconditionTests(unittest.TestCase):
    def test_the_database_tests_are_not_silently_skipped_where_required(self):
        if REQUIRED:
            self.assertIsNone(REASON)


@unittest.skipIf(REASON is not None, "database tests skipped: %s" % REASON)
class MongoTests(unittest.TestCase):
    def setUp(self):
        self.database = "agent_memory_test_" + secrets.token_hex(4)
        parts = urlsplit(SERVER_URI)
        self.uri = urlunsplit((parts.scheme, parts.netloc, "/" + self.database, parts.query, ""))
        self.store = store_module.MongoStore(self.uri)
        self.addCleanup(self.store.close)
        self.addCleanup(lambda: self.store.database.client.drop_database(self.database))
        self.assertTrue(self.store.ensure_indexes())
        self.mine = memory.Memory(self.store, "github.com/o/mine")
        self.other = memory.Memory(self.store, "github.com/o/other")

    def test_indexes_are_created_once(self):
        self.assertFalse(self.store.ensure_indexes())
        self.store.check()

    def test_save_search_read_delete(self):
        a = self.mine.remember(title="Deploy window", body="Fridays are frozen.", tags=["release"])
        b = self.mine.remember(title="Other", body="The deploy script needs VPN.")
        self.assertEqual([d["_id"] for d in self.mine.recall("deploy")], [a["_id"], b["_id"]])  # title ranks first
        self.assertEqual([d["_id"] for d in self.mine.recall("release")], [a["_id"]])
        self.assertEqual([d["_id"] for d in self.mine.recall("frozen")], [a["_id"]])
        self.assertEqual(self.mine.recall("zebra"), [])
        for odd in ('"', "-deploy", "--", '-"x"', "$ne", "{}"):
            with self.subTest(query=odd):
                self.mine.recall(odd)  # operators and braces are plain words, never an error
        self.assertEqual({d["_id"] for d in self.mine.recall("-deploy")}, {a["_id"], b["_id"]})
        self.assertNotIn("score", self.mine.recall("deploy")[0])
        got = self.mine.get(a["_id"])
        self.assertEqual(got["body"], "Fridays are frozen.")
        records.result_json(memory=records.full(got))  # dates read back serialise
        self.assertIsNotNone(self.store.get("github.com/o/mine", a["_id"])["usedAt"])
        self.assertEqual(self.mine.count(), 2)
        self.assertIn(a["_id"], self.mine.index())
        self.mine.forget(a["_id"])
        self.assertEqual(self.mine.count(), 1)
        with self.assertRaises(memory.NotFound):
            self.mine.get(a["_id"])

    def test_the_newest_and_the_pinned_come_first(self):
        first = self.mine.remember(title="first", body="x")
        second = self.mine.remember(title="second", body="x")
        # two saves can land in the same millisecond, MongoDB's precision, so the older one is dated back
        self.store.database["memories"].update_one(
            {"_id": first["_id"]}, {"$set": {"confirmedAt": second["confirmedAt"] - dt.timedelta(minutes=1)}})
        self.assertEqual([d["_id"] for d in self.mine.recall("")], [second["_id"], first["_id"]])
        self.store.database["memories"].update_one({"_id": first["_id"]}, {"$set": {"pinned": True}})
        self.assertEqual(self.mine.recall("")[0]["_id"], first["_id"])

    def test_projects_do_not_see_each_other(self):
        doc = self.mine.remember(title="Private fact", body="only here")
        self.assertEqual(self.other.recall("private"), [])
        self.assertEqual(self.other.recall(""), [])
        self.assertEqual(self.other.count(), 0)
        self.assertNotIn(doc["_id"], self.other.index())
        for action in (self.other.get, self.other.forget):
            with self.assertRaises(memory.NotFound):
                action(doc["_id"])
        self.assertEqual(self.mine.count(), 1)

    def test_a_wrong_password_is_a_login_failure_not_a_crash(self):
        parts = urlsplit(self.uri)
        host = parts.netloc.rsplit("@", 1)[-1]
        bad = urlunsplit((parts.scheme, "nobody:wrong-pw-1@" + host, parts.path, "authSource=admin", ""))
        with self.assertRaises(store_module.AuthFailed) as caught:
            with contextlib.closing(store_module.MongoStore(bad)) as store:
                store.check()
        self.assertNotIn("wrong-pw-1", str(caught.exception))

    def test_the_hook_gives_up_on_a_down_database_well_inside_its_timeout(self):
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        allowed = hooks["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
        with tempfile.TemporaryDirectory() as tmp:
            env = isolated_env(Path(tmp), AI_AGENCY_MEMORY_URI="mongodb://u:p@127.0.0.1:1/x",
                               CLAUDE_PROJECT_DIR=tmp)
            started = time.monotonic()
            done = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "session_index.py")], env=env, cwd=tmp,
                                  input="{}", capture_output=True, text=True, encoding="utf-8", timeout=120)
            took = time.monotonic() - started
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("memory is unavailable (the database does not answer)", done.stdout)
        self.assertLess(took, allowed / 2)

    def test_a_database_that_is_down(self):
        with self.assertRaises(store_module.Unavailable) as caught:
            with contextlib.closing(store_module.MongoStore("mongodb://127.0.0.1:1/x")) as store:
                store.check()
        self.assertIn("does not answer", str(caught.exception))

    def test_one_session_saves_and_the_next_one_lists_and_reads_it(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            # the processes start in another directory: only CLAUDE_PROJECT_DIR says which project this is
            env = isolated_env(Path(tmp), AI_AGENCY_MEMORY_URI=self.uri, CLAUDE_PROJECT_DIR=tmp,
                               PYTHONPATH=os.pathsep.join(p for p in sys.path if p))

            def server(name, **arguments):
                request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}
                done = subprocess.run([sys.executable, str(PLUGIN / "mcp" / "server.py")], env=env, cwd=elsewhere,
                                      input=json.dumps(request) + "\n", capture_output=True, text=True,
                                      encoding="utf-8", timeout=60)
                result = json.loads(done.stdout)["result"]
                self.assertFalse(result["isError"], result)
                return result["content"][0]["text"]

            saved = json.loads(server("remember", title="Seed is 42", body="Set SEED=42."))["saved"]["id"]
            hook = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "session_index.py")], env=env,
                                  cwd=elsewhere,
                                  input="{}", capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(hook.returncode, 0, hook.stderr)
            self.assertIn("[%s] (fact) Seed is 42" % saved, hook.stdout)
            self.assertEqual(json.loads(server("get", id=saved))["memory"]["body"], "Set SEED=42.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
