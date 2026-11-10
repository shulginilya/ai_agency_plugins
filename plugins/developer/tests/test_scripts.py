#!/usr/bin/env python3
"""Smoke tests for the scripts and MCP server the developer plugin ships."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
VERIFY = PLUGIN / "skills" / "feature-implementation" / "scripts" / "verify.py"
CALLERS = PLUGIN / "skills" / "safe-refactoring" / "scripts" / "callers.py"
DEV_CONTEXT = PLUGIN / "scripts" / "dev_context.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def git_init(repo: Path) -> None:
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.email", "t@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Test"], cwd=repo)


class VerifyTest(unittest.TestCase):
    def _checks(self, repo: Path):
        result = run([sys.executable, str(VERIFY), "--root", str(repo), "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_node_scripts_use_the_lockfile_package_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                json.dumps({"scripts": {"build": "x", "test": "x", "lint": "x", "typecheck": "x"}})
            )
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0\n")
            checks = self._checks(repo)
            self.assertEqual(
                [c["kind"] for c in checks], ["typecheck", "lint", "test", "build"],
                "checks must be ordered fastest feedback first",
            )
            self.assertTrue(all(c["command"].startswith("pnpm run ") for c in checks), checks)

    def test_npm_is_the_fallback_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
            self.assertEqual(self._checks(repo)[0]["command"], "npm run test")

    def test_python_tooling_is_read_from_pyproject(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
            (repo / "tests").mkdir()
            commands = {c["command"] for c in self._checks(repo)}
            self.assertIn("ruff check .", commands)
            self.assertIn("pytest", commands)
            self.assertNotIn("mypy .", commands, "must not invent tooling the repo does not declare")

    def test_no_manifest_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(VERIFY), "--root", tmp])
            self.assertEqual(result.returncode, 2, "nothing to verify is not the same as all green")

    @unittest.skipUnless(shutil.which("make"), "make is not installed")
    def test_run_stops_at_the_first_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "Makefile").write_text("lint:\n\t@exit 1\n\ntest:\n\t@echo unreachable\n")
            result = run([sys.executable, str(VERIFY), "--root", str(repo), "--run"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAILED at lint", result.stdout)
            self.assertNotIn("unreachable", result.stdout)


class CallersTest(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "node_modules").mkdir()
        (root / "src" / "widget.py").write_text("def build_widget(x):\n    return x\n")
        (root / "src" / "page.py").write_text(
            "from .widget import build_widget\n\nprint(build_widget(1))\n"
        )
        (root / "tests" / "test_widget.py").write_text("build_widget(2)\n")
        (root / "node_modules" / "junk.py").write_text("build_widget(3)\n")

    def test_groups_definitions_call_sites_and_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._tree(root)
            result = run([sys.executable, str(CALLERS), "build_widget", "--root", tmp, "--json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            hits = json.loads(result.stdout)
            kinds = [h["kind"] for h in hits]
            self.assertEqual(kinds.count("definition"), 1)
            self.assertTrue(any(h["test"] for h in hits), "test call sites must be visible")
            self.assertFalse(
                any("node_modules" in h["path"] for h in hits), "vendored trees must be skipped"
            )

    def test_extension_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._tree(root)
            (root / "src" / "page.ts").write_text("build_widget()\n")
            result = run(
                [sys.executable, str(CALLERS), "build_widget", "--root", tmp, "--ext", ".ts", "--json"]
            )
            hits = json.loads(result.stdout)
            self.assertTrue(hits and all(h["path"].endswith(".ts") for h in hits))

    def test_unused_symbol_is_a_result_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(CALLERS), "nothing_here", "--root", tmp])
            self.assertEqual(result.returncode, 0)
            self.assertIn("no references", result.stdout)

    def test_missing_root_exits_two(self):
        result = run([sys.executable, str(CALLERS), "x", "--root", os.path.join("no", "such", "dir")])
        self.assertEqual(result.returncode, 2)


class SessionHookTest(unittest.TestCase):
    def _run_hook(self, cwd: str) -> subprocess.CompletedProcess:
        return run([sys.executable, str(DEV_CONTEXT)], input=json.dumps({"cwd": cwd}))

    def test_reports_branch_and_checks_inside_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git_init(repo)
            (repo / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
            run(["git", "add", "."], cwd=repo)
            run(["git", "commit", "-qm", "init"], cwd=repo)
            result = self._run_hook(tmp)
            self.assertEqual(result.returncode, 0)
            self.assertIn("developer: branch:", result.stdout)
            self.assertIn("npm run test", result.stdout)

    def test_silent_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_hook(tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_malformed_event_never_fails(self):
        result = run([sys.executable, str(DEV_CONTEXT)], input="not json")
        self.assertEqual(result.returncode, 0, "the hook must never break a session")


class ShipExistingTicketTest(unittest.TestCase):
    """Shipping work for an existing ticket must reuse it, never file a duplicate."""

    def test_the_command_and_the_skill_reuse_a_named_ticket(self):
        command = (PLUGIN / "commands" / "ship.md").read_text(encoding="utf-8")
        skill = (PLUGIN / "skills" / "ship-change" / "SKILL.md").read_text(encoding="utf-8")
        for text in (command, skill):
            self.assertIn("board.py add", text)
            self.assertIn("Never file a second ticket", text)
        self.assertIn("#N to ship for an existing ticket", command)
        for text in (command, skill):  # the ticket's own board, not the most used one
            self.assertIn("board.py where --issue", text)
        self.assertIn("gh issue view", skill)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def _call(self, name, arguments, cwd=None):
        responses = self._rpc(
            [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": arguments}}],
            cwd=cwd,
        )
        return responses[0]["result"]

    def test_initialize_and_list_tools(self):
        responses = self._rpc(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "developer")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"verify_commands", "find_callers", "dev_playbook", "repro_command", "change_history", "bug_playbook"})

    def test_verify_commands_reads_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
            result = self._call("verify_commands", {"cwd": tmp})
            self.assertFalse(result["isError"])
            self.assertIn("npm run test", result["content"][0]["text"])

    def test_find_callers_requires_a_symbol(self):
        result = self._call("find_callers", {})
        self.assertTrue(result["isError"])

    def test_playbook_returns_a_reference_document(self):
        result = self._call("dev_playbook", {"topic": "handoff"})
        self.assertFalse(result["isError"])
        self.assertIn("Self-review before handoff", result["content"][0]["text"])

    def test_unknown_playbook_topic_is_a_tool_error_not_a_crash(self):
        self.assertTrue(self._call("dev_playbook", {"topic": "nope"})["isError"])

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
