#!/usr/bin/env python3
"""Smoke tests for the scripts, hook and MCP server the debugger plugin ships."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
RCA = PLUGIN / "skills" / "root-cause-analysis" / "scripts"
TRIAGE = PLUGIN / "skills" / "regression-triage" / "scripts"
REPRO = RCA / "repro.py"
SUPPRESSION = RCA / "suppression.py"
BISECT = TRIAGE / "bisect.py"
HISTORY = TRIAGE / "history.py"
HOOK = PLUGIN / "scripts" / "symptom_suppression_check.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

sys.path.insert(0, str(RCA))


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def init_repo(path: Path) -> None:
    run(["git", "init", "-q"], cwd=path)
    run(["git", "config", "user.email", "t@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test"], cwd=path)


def commit(path: Path, message: str) -> str:
    run(["git", "add", "-A"], cwd=path)
    run(["git", "commit", "-qm", message], cwd=path)
    return run(["git", "rev-parse", "HEAD"], cwd=path).stdout.strip()


def quoted(*parts: str) -> str:
    return " ".join('"%s"' % part for part in parts)


class DiscoveryTest(unittest.TestCase):
    def test_reads_package_json_and_lockfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run", "lint": "eslint ."}}), encoding="utf-8"
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")

            result = run([sys.executable, str(REPRO), "--cwd", str(root), "--discover", "--json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            found = json.loads(result.stdout)
            self.assertEqual(found["package_manager"], "pnpm")
            self.assertEqual(found["framework"], "vitest")
            self.assertIn("pnpm run test", [c["command"] for c in found["commands"]])

    def test_single_test_command_uses_the_framework_selector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
            result = run(
                [sys.executable, str(REPRO), "--cwd", str(root), "--test", "order total", "--print"]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'pytest -x -q -k "order total"')

    def test_no_declared_checks_is_exit_two_not_a_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(REPRO), "--cwd", tmp, "--discover"])
            self.assertEqual(result.returncode, 2)
            self.assertIn("no checks declared", result.stdout)


class ReproRunTest(unittest.TestCase):
    def _run_cmd(self, command: str, times: int, cwd: str):
        return run(
            [sys.executable, str(REPRO), "--cwd", cwd, "--cmd", command, "--times", str(times), "--json"]
        )

    def test_deterministic_pass_and_fail_have_different_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = self._run_cmd(quoted(sys.executable, "-c", "pass"), 3, tmp)
            self.assertEqual(ok.returncode, 0)
            self.assertEqual(json.loads(ok.stdout)["verdict"], "deterministic-pass")

            bad = self._run_cmd(quoted(sys.executable, "-c", "raise SystemExit(1)"), 3, tmp)
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(json.loads(bad.stdout)["verdict"], "deterministic-fail")

    def test_intermittent_failure_is_reported_as_its_own_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            counter = Path(tmp) / "count.txt"
            flaky = Path(tmp) / "flaky.py"
            flaky.write_text(
                "import pathlib, sys\n"
                "p = pathlib.Path(%r)\n"
                "n = int(p.read_text()) if p.exists() else 0\n"
                "p.write_text(str(n + 1))\n"
                "sys.exit(n %% 2)\n" % str(counter),
                encoding="utf-8",
            )
            result = self._run_cmd(quoted(sys.executable, str(flaky)), 4, tmp)
            self.assertEqual(result.returncode, 3, "mixed results must not look like a clean pass")
            self.assertEqual(json.loads(result.stdout)["verdict"], "intermittent")


class SuppressionTest(unittest.TestCase):
    def test_flags_swallowed_failures_and_stays_quiet_on_clean_code(self):
        import suppression

        self.assertTrue(suppression.scan("try { charge() } catch (e) {}\n"))
        self.assertTrue(suppression.scan("try:\n    charge()\nexcept Exception:\n    pass\n"))
        self.assertTrue(suppression.scan("it.skip('totals', () => {})\n"))
        self.assertEqual(suppression.scan("export const add = (a, b) => a + b\n"), [])
        self.assertEqual(
            suppression.scan("try:\n    charge()\nexcept ValueError:\n    log.warning('retry')\n"), []
        )


class HookTest(unittest.TestCase):
    def _hook(self, filename: str, contents: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.write_text(contents, encoding="utf-8")
            event = json.dumps({"tool_input": {"file_path": str(path)}})
            result = run([sys.executable, str(HOOK)], input=event)
            self.assertEqual(result.returncode, 0, "the hook must never block an edit")
            return result.stdout

    def test_notices_a_symptom_fix(self):
        self.assertIn("empty catch", self._hook("cart.ts", "try { charge() } catch (e) {}\n"))

    def test_quiet_on_clean_code_and_non_code(self):
        self.assertEqual(self._hook("cart.ts", "export const add = (a, b) => a + b\n").strip(), "")
        self.assertEqual(self._hook("notes.md", "try { x() } catch (e) {}\n").strip(), "")

    def test_malformed_event_is_ignored(self):
        result = run([sys.executable, str(HOOK)], input="not json")
        self.assertEqual(result.returncode, 0)


class HistoryTest(unittest.TestCase):
    def test_reports_commits_and_blame_for_a_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "total.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
            commit(repo, "first")
            (repo / "total.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
            commit(repo, "second")

            result = run(
                [sys.executable, str(HISTORY), "total.py", "--cwd", str(repo), "--lines", "1-3", "--json"]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["commits"]), 2)
            self.assertEqual({"first", "second"}, {c["subject"] for c in report["commits"]})
            self.assertEqual(sum(entry["lines"] for entry in report["blame"]), 3)
            self.assertTrue(any(c["added"] for c in report["commits"]), "numstat must attach to its own commit")

    def test_untracked_path_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / "a.txt").write_text("x\n", encoding="utf-8")
            commit(repo, "first")
            result = run([sys.executable, str(HISTORY), "nope.txt", "--cwd", str(repo)])
            self.assertEqual(result.returncode, 2)


class BisectTest(unittest.TestCase):
    def _repo_with_a_regression(self, tmp: str):
        repo = Path(tmp)
        init_repo(repo)
        (repo / "value.txt").write_text("ok\n", encoding="utf-8")
        good = commit(repo, "c0")
        for index in range(1, 6):
            (repo / ("note%d.txt" % index)).write_text("n\n", encoding="utf-8")
            if index == 3:
                (repo / "value.txt").write_text("bug\n", encoding="utf-8")
            commit(repo, "c%d" % index)

        verdict = repo / "verdict.py"
        verdict.write_text(
            "import pathlib, sys\n"
            "text = pathlib.Path('value.txt').read_text()\n"
            "sys.exit(1 if 'bug' in text else 0)\n",
            encoding="utf-8",
        )
        # keep the verdict script out of the bisected history
        (repo / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text("verdict.py\n", encoding="utf-8")
        return repo, good, quoted(sys.executable, str(verdict))

    def test_plan_does_not_touch_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, good, command = self._repo_with_a_regression(tmp)
            head_before = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout

            result = run(
                [sys.executable, str(BISECT), "--cwd", str(repo), "--good", good, "--cmd", command, "--json"]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["commits"], 5)
            self.assertFalse(plan["blocking"])
            self.assertEqual(head_before, run(["git", "rev-parse", "HEAD"], cwd=repo).stdout)

    def test_finds_the_first_bad_commit_and_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, good, command = self._repo_with_a_regression(tmp)
            result = run(
                [sys.executable, str(BISECT), "--cwd", str(repo), "--good", good,
                 "--cmd", command, "--run", "--json"]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            culprit = json.loads(result.stdout)["culprit"]
            self.assertTrue(culprit, "bisect should have identified a commit")
            subject = run(["git", "show", "-s", "--format=%s", culprit], cwd=repo).stdout.strip()
            self.assertEqual(subject, "c3")
            self.assertFalse(
                (repo / ".git" / "BISECT_START").exists(), "the repo must not be left mid-bisect"
            )

    def test_refuses_a_dirty_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, good, command = self._repo_with_a_regression(tmp)
            (repo / "value.txt").write_text("dirty\n", encoding="utf-8")
            result = run(
                [sys.executable, str(BISECT), "--cwd", str(repo), "--good", good, "--cmd", command, "--run"]
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("dirty", result.stderr)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
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
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "debugger")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"repro_command", "change_history", "bug_playbook"})

    def test_playbook_returns_the_skill_reference(self):
        responses = self._rpc(
            [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "bug_playbook", "arguments": {"topic": "bug-classes"}}}]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        self.assertIn("symptom to mechanism", result["content"][0]["text"])

    def test_unknown_topic_is_a_tool_error_not_a_crash(self):
        responses = self._rpc(
            [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "bug_playbook", "arguments": {"topic": "nope"}}}]
        )
        self.assertTrue(responses[0]["result"]["isError"])

    def test_git_failure_inside_a_tool_does_not_kill_the_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._rpc(
                [
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                     "params": {"name": "change_history", "arguments": {"path": "nope.txt", "cwd": tmp}}},
                    {"jsonrpc": "2.0", "id": 2, "method": "ping"},
                ],
                cwd=tmp,
            )
            self.assertTrue(responses[0]["result"]["isError"])
            self.assertEqual(responses[1]["result"], {}, "the server must still be alive")

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
