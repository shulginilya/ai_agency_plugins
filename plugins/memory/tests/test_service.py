#!/usr/bin/env python3
"""remember, recall, get, forget and the index over a store (AC6-8, AC10)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, FakeStore, isolated_env
import memconfig
import memory
import records
import store as store_module


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.mine = memory.Memory(self.store, "github.com/o/mine")
        self.other = memory.Memory(self.store, "github.com/o/other")

    def test_what_is_remembered_is_in_a_new_services_index_and_get_returns_it(self):
        doc = self.mine.remember(title="Database first", body="Run make db-up.\nThen test.")
        later = memory.Memory(self.store, "github.com/o/mine")
        self.assertIn(doc["_id"], later.index())
        self.assertEqual(later.get(doc["_id"])["body"], "Run make db-up.\nThen test.")

    def test_get_records_the_use_and_nothing_else_writes(self):
        doc = self.mine.remember(title="a", body="b")
        self.assertIsNone(self.store.docs[doc["_id"]]["usedAt"])
        self.mine.index()
        self.mine.recall("a")
        self.mine.recall("")
        self.mine.count()
        self.assertIsNone(self.store.docs[doc["_id"]]["usedAt"])
        self.mine.get(doc["_id"])
        self.assertIsNotNone(self.store.docs[doc["_id"]]["usedAt"])
        self.assertEqual(self.store.inserts, 1)

    def test_recall_matches_title_and_body_and_an_empty_query_lists_the_recent(self):
        a = self.mine.remember(title="Deploy window", body="Fridays are frozen.")
        b = self.mine.remember(title="Other", body="The deploy script needs VPN.")
        self.assertEqual({d["_id"] for d in self.mine.recall("deploy")}, {a["_id"], b["_id"]})
        self.assertEqual(self.mine.recall("zebra"), [])
        self.assertEqual(len(self.mine.recall("")), 2)
        self.assertEqual(len(self.mine.recall(None, limit=1)), 1)

    def test_the_recall_limit_is_clamped_and_arguments_are_typed(self):
        for i in range(60):
            self.mine.remember(title="note %d" % i, body="x")
        self.assertEqual(len(self.mine.recall("note", limit=1000)), 50)
        self.assertEqual(len(self.mine.recall("note", limit=-3)), 1)
        for bad in ({"query": {"$ne": ""}}, {"query": "x", "limit": "ten"}, {"query": "x", "limit": True}):
            with self.subTest(bad=bad):
                with self.assertRaises(records.RecordError):
                    self.mine.recall(**bad)

    def test_another_project_sees_nothing_of_mine(self):
        doc = self.mine.remember(title="Private fact", body="only here")
        self.assertEqual(self.other.recall("private"), [])
        self.assertEqual(self.other.recall(""), [])
        self.assertNotIn(doc["_id"], self.other.index())
        with self.assertRaises(memory.NotFound):
            self.other.get(doc["_id"])
        with self.assertRaises(memory.NotFound):
            self.other.forget(doc["_id"])
        self.assertEqual(self.mine.get(doc["_id"])["title"], "Private fact")

    def test_forget_deletes_one_memory_for_good(self):
        gone = self.mine.remember(title="wrong", body="wrong")
        kept = self.mine.remember(title="right", body="right")
        self.mine.forget(gone["_id"])
        self.assertEqual([d["_id"] for d in self.mine.recall("")], [kept["_id"]])
        self.assertNotIn(gone["_id"], self.mine.index())
        with self.assertRaises(memory.NotFound):
            self.mine.get(gone["_id"])
        with self.assertRaises(memory.NotFound):
            self.mine.forget(gone["_id"])

    def test_a_malformed_id_never_reaches_the_store(self):
        kept = self.mine.remember(title="a", body="b")
        for bad in ({"$ne": None}, None, "", "nope", kept["_id"] + "0", 7, [kept["_id"]]):
            with self.subTest(bad=bad):
                with self.assertRaises(memory.NotFound):
                    self.mine.forget(bad)
                with self.assertRaises(memory.NotFound):
                    self.mine.get(bad)
        self.assertEqual(self.mine.count(), 1)

    def test_a_secret_stores_nothing(self):
        with self.assertRaises(records.SecretFound):
            self.mine.remember(title="db", body="password=" + "hunter2pass")
        self.assertEqual(self.store.inserts, 0)

    def test_the_index_counts_what_it_left_out(self):
        for i in range(250):
            self.mine.remember(title="fact %d %s" % (i, "t" * 100), body="x")
        text = self.mine.index()
        shown = sum(1 for line in text.splitlines() if line.startswith("- ["))
        self.assertIn("%d more left out" % (250 - shown), text)


class CommandLineProjectTests(unittest.TestCase):
    def run_cli(self, cwd, *args, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            return subprocess.run([sys.executable, str(SCRIPTS / "memory.py"), *args], cwd=str(cwd),
                                  env=isolated_env(Path(tmp), **extra), capture_output=True, text=True,
                                  encoding="utf-8", timeout=30)

    def test_run_from_inside_the_skill_without_a_project_it_refuses(self):
        for cwd in (SCRIPTS, SCRIPTS.parent):
            with self.subTest(cwd=cwd.name):
                done = self.run_cli(cwd, "status")
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("--dir", done.stderr)

    def test_a_named_project_is_used_wherever_it_runs_from(self):
        for args, extra in ((("--dir", str(SCRIPTS), "status"), {}),
                            (("status",), {"CLAUDE_PROJECT_DIR": str(SCRIPTS)})):
            with self.subTest(args=args):
                done = self.run_cli(SCRIPTS.parent, *args, **extra)
                self.assertEqual(done.returncode, 1, done.stderr)  # reaches "setup has not run"
                self.assertIn("/memory:setup", done.stderr)


class OpenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = isolated_env(Path(self.tmp.name))

    def test_without_setup_it_says_so(self):
        with self.assertRaises(store_module.Unavailable) as caught:
            memory.open_memory(Path(self.tmp.name), self.env)
        self.assertIn("/memory:setup", str(caught.exception))

    def test_a_corrupt_config_is_unavailable_not_a_crash(self):
        path = memconfig.config_path(self.env)
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(store_module.Unavailable):
            memory.open_memory(Path(self.tmp.name), self.env)


if __name__ == "__main__":
    unittest.main(verbosity=2)
