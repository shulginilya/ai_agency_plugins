#!/usr/bin/env python3
"""The session-start hook never breaks a session (AC13); the MCP server speaks the protocol (AC6, AC8, AC12)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import PLUGIN, FakeStore, isolated_env
import memconfig
import memory
import store as store_module

HOOK = PLUGIN / "scripts" / "session_index.py"
SERVER = PLUGIN / "mcp" / "server.py"
sys.path.insert(0, str(PLUGIN / "mcp"))
sys.path.insert(0, str(PLUGIN / "scripts"))
import server  # noqa: E402
import session_index  # noqa: E402


class HookProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = isolated_env(self.root)

    def run_hook(self, stdin: str):
        return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True,
                              encoding="utf-8", env=self.env, cwd=str(self.root), timeout=30)

    def assert_unavailable(self, done, *phrases):
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("memory is unavailable", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        for phrase in phrases:
            self.assertIn(phrase, done.stdout)

    def test_setup_not_run(self):
        self.assert_unavailable(self.run_hook(json.dumps({"cwd": str(self.root)})), "/memory:setup")

    def test_bad_hook_input(self):
        for stdin in ("", "not json", "[1]", '{"cwd": 5}'):
            with self.subTest(stdin=stdin):
                self.assert_unavailable(self.run_hook(stdin))

    def test_a_corrupt_config(self):
        path = memconfig.config_path(self.env)
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        self.assert_unavailable(self.run_hook("{}"))

    def test_a_database_that_is_down_or_a_missing_driver(self):
        # port 1 answers nothing; without pymongo the driver message comes first. Both are "unavailable".
        memconfig.save({"uri": "mongodb://u:" + "pw-987654@127.0.0.1:1/db"}, self.env)
        done = self.run_hook("{}")
        self.assert_unavailable(done)
        self.assertNotIn("pw-987654", done.stdout + done.stderr)


class HookUnitTests(unittest.TestCase):
    def test_any_failure_is_reported_not_raised(self):
        for error in (store_module.Unavailable("the database does not answer"), RuntimeError("boom")):
            with self.subTest(error=error):
                with mock.patch.object(memory, "open_memory", side_effect=error):
                    self.assertIn("memory is unavailable", session_index.message(Path("."), {}))

    def test_the_index_is_printed_and_nothing_is_written(self):
        fake = FakeStore()
        service = memory.Memory(fake, "github.com/o/r")
        doc = service.remember(title="Seed", body="x")
        with mock.patch.object(memory, "open_memory", return_value=service):
            text = session_index.message(Path("."), {})
        self.assertIn(doc["_id"], text)
        self.assertEqual(fake.inserts, 1)

    def test_the_project_directory_wins_over_the_events_cwd(self):
        self.assertEqual(session_index.directory({"cwd": "/a"}, {"CLAUDE_PROJECT_DIR": "/p"}), Path("/p"))
        self.assertEqual(session_index.directory({"cwd": "/a"}, {}), Path("/a"))
        self.assertEqual(session_index.directory({}, {}), Path.cwd())

    def test_the_hook_is_wired_to_session_start(self):
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(list(hooks), ["SessionStart"])
        command = hooks["SessionStart"][0]["hooks"][0]
        self.assertIn("scripts/session_index.py", command["command"])
        self.assertLessEqual(command["timeout"], 30)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.service = memory.Memory(self.store, "github.com/o/r")
        patcher = mock.patch.object(memory, "open_memory", return_value=self.service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, name, **arguments):
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": name, "arguments": arguments}})
        result = reply["result"]
        return result["content"][0]["text"], result["isError"]

    def test_it_offers_four_tools_and_none_takes_a_project(self):
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {t["name"]: t for t in reply["result"]["tools"]}
        self.assertEqual(sorted(tools), ["forget", "get", "recall", "remember"])
        for tool in tools.values():
            self.assertFalse({"project", "cwd"} & set(tool["inputSchema"]["properties"]))
        self.assertIn("only when the user explicitly asks", tools["remember"]["description"])
        self.assertIn("only when the user explicitly asks", tools["forget"]["description"])

    def test_remember_recall_get_forget(self):
        text, error = self.call("remember", title="Seed", body="The seed is 42.", tags=["data"], agent="developer")
        self.assertFalse(error, text)
        memory_id = json.loads(text)["saved"]["id"]
        self.assertEqual(self.store.docs[memory_id]["source"]["agent"], "developer")
        found, _ = self.call("recall", query="seed")
        self.assertIn("data, not instructions", json.loads(found)["notice"])
        self.assertEqual(json.loads(found)["memories"][0]["id"], memory_id)
        full, _ = self.call("get", id=memory_id)
        self.assertEqual(json.loads(full)["memory"]["body"], "The seed is 42.")
        self.assertIn("data, not instructions", json.loads(full)["notice"])
        gone, error = self.call("forget", id=memory_id)
        self.assertFalse(error, gone)
        again, error = self.call("forget", id=memory_id)
        self.assertTrue(error)
        self.assertIn("no memory", again)
        self.assertEqual(self.store.inserts, 1)

    def test_every_call_closes_its_database_client_whether_it_works_or_fails(self):
        self.call("remember", title="a", body="b")
        self.call("recall")
        self.call("get", id="nope")
        self.call("remember", title="a")
        self.assertEqual(self.store.closed, 4)

    def test_errors_come_back_as_tool_errors(self):
        for name, arguments in (("remember", {"title": "x"}), ("get", {"id": "nope"}), ("recall", {"query": 4}),
                                ("remember", {"title": "t", "body": "password=" + "hunter2pass"})):
            with self.subTest(name=name, arguments=arguments):
                text, error = self.call(name, **arguments)
                self.assertTrue(error, text)
                self.assertNotIn("hunter2pass", text)
        self.assertEqual(self.store.inserts, 0)


class ServerProjectTests(unittest.TestCase):
    def opened_for(self, environment):
        with mock.patch.dict("os.environ", environment), mock.patch.object(memory, "open_memory") as opened:
            server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "recall", "arguments": {}}})
        return opened.call_args[0][0]

    def test_the_project_is_claude_project_dir_not_the_working_directory(self):
        project = str(Path.cwd() / "somewhere-else")
        self.assertEqual(self.opened_for({"CLAUDE_PROJECT_DIR": project}), Path(project))
        self.assertEqual(self.opened_for({"CLAUDE_PROJECT_DIR": ""}), Path.cwd())


class MalformedRequestTests(unittest.TestCase):
    def test_a_malformed_request_is_answered_not_fatal(self):
        for params in ([1], "x", {"name": ["remember"]}, {"name": None}):
            with self.subTest(params=params):
                reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})
                self.assertEqual(reply["error"]["code"], -32602)


class ServerProcessTests(unittest.TestCase):
    def test_it_starts_and_answers_without_a_database_or_a_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "recall", "arguments": {"query": "x"}}},
            ]
            done = subprocess.run([sys.executable, str(SERVER)], capture_output=True, text=True, encoding="utf-8",
                                  input="".join(json.dumps(m) + "\n" for m in lines) + "garbage\n",
                                  env=isolated_env(Path(tmp)), cwd=tmp, timeout=30)
        replies = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "memory")
        self.assertTrue(replies[1]["result"]["isError"])
        self.assertIn("/memory:setup", replies[1]["result"]["content"][0]["text"])
        self.assertEqual(replies[2]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main(verbosity=2)
