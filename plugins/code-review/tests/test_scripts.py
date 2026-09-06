#!/usr/bin/env python3
"""Smoke tests for the scripts and MCP server the code-review plugin ships."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
CHANGED_FILES = PLUGIN / "skills" / "code-review" / "scripts" / "changed_files.py"
POST_EDIT = PLUGIN / "scripts" / "post_edit_check.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def _clear_readonly(func, path, _info):
    """rmtree error handler: git marks its object files read-only, and on Windows
    a read-only file cannot be deleted at all. Clear the bit and retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


@contextlib.contextmanager
def temp_dir():
    """A temporary directory that also deletes cleanly when it holds a git repo.

    tempfile.TemporaryDirectory cannot: its cleanup is a plain shutil.rmtree, which
    raises PermissionError on Windows the moment it reaches .git/objects.
    """
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_clear_readonly)
        else:
            shutil.rmtree(path, onerror=_clear_readonly)


class ChangedFilesTest(unittest.TestCase):
    def test_reports_tracked_and_untracked_changes(self):
        with temp_dir() as tmp:
            repo = Path(tmp)
            run(["git", "init", "-q"], cwd=repo)
            run(["git", "config", "user.email", "t@example.com"], cwd=repo)
            run(["git", "config", "user.name", "Test"], cwd=repo)
            (repo / "a.txt").write_text("one\n")
            run(["git", "add", "."], cwd=repo)
            run(["git", "commit", "-qm", "init"], cwd=repo)

            (repo / "a.txt").write_text("one\ntwo\n")
            (repo / "b.py").write_text("print('new')\n")

            result = run(
                [sys.executable, str(CHANGED_FILES), "--json"], cwd=repo
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = {entry["path"]: entry for entry in json.loads(result.stdout)}
            self.assertIn("a.txt", payload)
            self.assertIn("b.py", payload, "untracked files must be reviewable")
            self.assertEqual(payload["a.txt"]["added"], 1)

    def test_clean_tree_is_not_an_error(self):
        with temp_dir() as tmp:
            repo = Path(tmp)
            run(["git", "init", "-q"], cwd=repo)
            run(["git", "config", "user.email", "t@example.com"], cwd=repo)
            run(["git", "config", "user.name", "Test"], cwd=repo)
            (repo / "a.txt").write_text("one\n")
            run(["git", "add", "."], cwd=repo)
            run(["git", "commit", "-qm", "init"], cwd=repo)

            result = run([sys.executable, str(CHANGED_FILES)], cwd=repo)
            self.assertEqual(result.returncode, 0)
            self.assertIn("no reviewable changes", result.stdout)

    def test_outside_a_repository_exits_two(self):
        with temp_dir() as tmp:
            result = run([sys.executable, str(CHANGED_FILES)], cwd=tmp)
            self.assertEqual(result.returncode, 2)


class PostEditHookTest(unittest.TestCase):
    def _run_hook(self, filename: str, contents: str) -> str:
        with temp_dir() as tmp:
            path = Path(tmp) / filename
            path.write_text(contents)
            event = json.dumps({"tool_input": {"file_path": str(path)}})
            result = run([sys.executable, str(POST_EDIT)], input=event)
            self.assertEqual(result.returncode, 0, "the hook must never block an edit")
            return result.stdout

    def test_flags_debris(self):
        out = self._run_hook("x.ts", "export function f() {\n  console.log('x')\n}\n")
        self.assertIn("console logging", out)

    def test_quiet_on_clean_code(self):
        out = self._run_hook("x.ts", "export const f = () => 1\n")
        self.assertEqual(out.strip(), "")

    def test_ignores_non_code_and_malformed_events(self):
        self.assertEqual(self._run_hook("notes.md", "console.log('x')\n").strip(), "")
        result = run([sys.executable, str(POST_EDIT)], input="not json")
        self.assertEqual(result.returncode, 0)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_and_list_tools(self):
        responses = self._rpc(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "code-review")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"changed_files", "review_checklist"})

    def test_checklist_tool_returns_content(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "review_checklist", "arguments": {"dimension": "audit"}},
                }
            ]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        self.assertIn("Audit checklist", result["content"][0]["text"])

    def test_unknown_dimension_is_a_tool_error_not_a_crash(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "review_checklist", "arguments": {"dimension": "nope"}},
                }
            ]
        )
        self.assertTrue(responses[0]["result"]["isError"])

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
