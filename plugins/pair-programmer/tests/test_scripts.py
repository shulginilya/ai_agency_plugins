#!/usr/bin/env python3
"""Smoke tests for the scripts, hooks and MCP server the pair-programmer plugin ships."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SESSION_DIR = PLUGIN / "skills" / "pair-session" / "scripts"
TDD_DIR = PLUGIN / "skills" / "tdd-ping-pong" / "scripts"
DRIFT_DIR = PLUGIN / "skills" / "pair-navigating" / "scripts"
SESSION = SESSION_DIR / "session.py"
TDD = TDD_DIR / "tdd.py"
DRIFT = DRIFT_DIR / "drift.py"
RESUME_HOOK = PLUGIN / "scripts" / "resume_session.py"
TURN_HOOK = PLUGIN / "scripts" / "turn_check.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

for directory in (SESSION_DIR, TDD_DIR, DRIFT_DIR):
    sys.path.insert(0, str(directory))


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def session(root: Path, *args):
    return run([sys.executable, str(SESSION)] + list(args), cwd=root)


def start(root: Path, *extra):
    args = ["start", "--goal", "make the webhook retry safely", "--scope", "src/webhooks"]
    return session(root, *(args + list(extra)))


def git(root: Path, *args):
    return run(["git"] + list(args), cwd=root)


def git_repo(root: Path) -> bool:
    """A throwaway repo with one commit, or False when git is unavailable."""
    if git(root, "init", "-q").returncode != 0:
        return False
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "seed.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    return git(root, "commit", "-q", "-m", "seed").returncode == 0


class SessionTest(unittest.TestCase):
    def test_start_then_status_is_clean_except_for_the_missing_next_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(start(root).returncode, 0)
            self.assertTrue((root / ".pair" / "session.json").is_file())
            # no next step yet: that is the "needs attention" answer, not a pass
            self.assertEqual(session(root, "status").returncode, 1)
            self.assertEqual(session(root, "next", "extract the backoff policy").returncode, 0)
            self.assertEqual(session(root, "status").returncode, 0)

    def test_a_second_start_is_refused_rather_than_clobbering_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "decide", "queue it", "--because", "restarts")
            again = start(root)
            self.assertEqual(again.returncode, 2)
            self.assertIn("already open", again.stderr)
            state = json.loads((root / ".pair" / "session.json").read_text())
            self.assertEqual(len(state["entries"]), 1)

    def test_restart_archives_the_previous_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            result = start(root, "--restart")
            self.assertEqual(result.returncode, 0)
            archived = list((root / ".pair").glob("session-*.json"))
            self.assertEqual(len(archived), 1)

    def test_a_decision_without_a_reason_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            bare = session(root, "decide", "use a queue")
            self.assertEqual(bare.returncode, 2)
            self.assertIn("--because", bare.stderr)
            self.assertEqual(
                session(root, "decide", "use a queue", "--because", "restarts").returncode, 0
            )

    def test_an_unparseable_session_is_refused_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".pair").mkdir()
            corrupt = root / ".pair" / "session.json"
            corrupt.write_text("{not json", encoding="utf-8")
            result = session(root, "status")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(corrupt.read_text(), "{not json")
            # and `start` will not write over it either
            self.assertEqual(start(root).returncode, 2)
            self.assertEqual(corrupt.read_text(), "{not json")

    def test_a_json_file_that_is_not_a_session_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".pair").mkdir()
            other = root / ".pair" / "session.json"
            other.write_text('{"unrelated": true}', encoding="utf-8")
            result = session(root, "status")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(other.read_text()), {"unrelated": True})

    def test_writes_back_up_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "note", "first")
            session(root, "note", "second")
            backup = root / ".pair" / "session.json.bak"
            self.assertTrue(backup.is_file())
            self.assertEqual(len(json.loads(backup.read_text())["entries"]), 1)

    def test_open_questions_hold_status_at_needs_attention_until_answered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "next", "extract the backoff policy")
            asked = session(root, "ask", "is the webhook idempotent?")
            self.assertEqual(asked.returncode, 0)
            # entry numbers are stable across kinds, so read the one it reported
            number = asked.stdout.split("]")[0].lstrip("[")
            self.assertEqual(session(root, "status").returncode, 1)
            self.assertEqual(session(root, "answer", number, "yes, keyed on event id").returncode, 0)
            self.assertEqual(session(root, "status").returncode, 0)
            self.assertEqual(session(root, "answer", number, "again").returncode, 2)
            self.assertEqual(session(root, "answer", "99", "nope").returncode, 2)

    def test_pingpong_without_a_test_command_is_refused_at_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = start(root, "--mode", "pingpong")
            self.assertEqual(result.returncode, 2)
            self.assertIn("--test-command", result.stderr)
            self.assertFalse((root / ".pair" / "session.json").exists())

    def test_handoff_names_the_reasons_and_the_open_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "decide", "queue the retries", "--because", "must survive a restart")
            session(root, "reject", "cron", "--because", "five minute floor")
            session(root, "ask", "is the webhook idempotent?")
            session(root, "next", "extract the backoff policy")
            result = session(root, "handoff")
            self.assertEqual(result.returncode, 0)
            text = (root / ".pair" / "handoff.md").read_text(encoding="utf-8")
            self.assertIn("must survive a restart", text)
            self.assertIn("five minute floor", text)
            self.assertIn("is the webhook idempotent?", text)
            self.assertIn("extract the backoff policy", text)
            self.assertIn("still open", result.stdout)

    def test_a_handoff_without_a_next_step_says_so_rather_than_inventing_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "handoff")
            text = (root / ".pair" / "handoff.md").read_text(encoding="utf-8")
            self.assertIn("Not recorded", text)

    def test_close_is_idempotent_and_silences_the_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            self.assertEqual(session(root, "close").returncode, 0)
            self.assertEqual(session(root, "close").returncode, 0)
            self.assertEqual(session(root, "status").returncode, 0)


class TddStateTest(unittest.TestCase):
    """The four states are the point: RED and ERRORED must not collapse together."""

    def setUp(self):
        import tdd

        self.tdd = tdd

    def test_a_passing_command_is_green(self):
        self.assertEqual(self.tdd.classify_state(0, "3 passed in 0.1s")["state"], "GREEN")

    def test_a_failed_assertion_is_red(self):
        self.assertEqual(self.tdd.classify_state(1, "1 failed, 2 passed")["state"], "RED")

    def test_a_green_run_that_collected_nothing_is_errored_not_green(self):
        for output in ("no tests ran in 0.01s", "collected 0 items", "Ran 0 tests in 0.000s"):
            self.assertEqual(self.tdd.classify_state(0, output)["state"], "ERRORED", output)

    def test_an_import_error_is_errored_not_red(self):
        result = self.tdd.classify_state(1, "ImportError: cannot import name 'retry'")
        self.assertEqual(result["state"], "ERRORED")

    def test_a_missing_command_is_unusable(self):
        self.assertEqual(self.tdd.classify_state(127, "sh: pytest: command not found")["state"], "UNUSABLE")

    def test_an_unrecognised_exit_code_is_errored(self):
        self.assertEqual(self.tdd.classify_state(5, "")["state"], "ERRORED")

    def test_no_declared_command_is_unusable(self):
        self.assertEqual(self.tdd.run_suite("")["state"], "UNUSABLE")

    def test_the_four_states_run_end_to_end(self):
        cases = [
            ('%s -c "import sys; sys.exit(0)"' % sys.executable, "GREEN", 0),
            ('%s -c "print(\'1 failed\'); import sys; sys.exit(1)"' % sys.executable, "RED", 1),
            ('%s -c "import sys; sys.stderr.write(\'ImportError: x\'); sys.exit(1)"' % sys.executable,
             "ERRORED", 3),
        ]
        for command, expected, code in cases:
            result = self.tdd.run_suite(command)
            self.assertEqual(result["state"], expected, result)
            self.assertEqual(self.tdd.EXIT[result["state"]], code)


class TddGateTest(unittest.TestCase):
    def setUp(self):
        import tdd

        self.tdd = tdd

    def test_the_test_turn_only_hands_over_on_red(self):
        self.assertTrue(self.tdd.gate("write-failing-test", "RED")["allowed"])
        refused = self.tdd.gate("write-failing-test", "GREEN")
        self.assertFalse(refused["allowed"])
        self.assertIn("not being collected", refused["reason"])

    def test_an_errored_suite_is_refused_with_its_own_reason(self):
        refused = self.tdd.gate("write-failing-test", "ERRORED")
        self.assertFalse(refused["allowed"])
        self.assertIn("not a red test", refused["reason"])
        self.assertEqual(refused["code"], 3)

    def test_the_implementation_turn_only_hands_over_on_green(self):
        self.assertTrue(self.tdd.gate("make-it-pass", "GREEN")["allowed"])
        self.assertFalse(self.tdd.gate("make-it-pass", "RED")["allowed"])

    def test_a_refactor_that_goes_red_is_told_to_revert(self):
        self.assertIn("revert", self.tdd.gate("refactor", "RED")["reason"].lower())

    def test_an_unusable_suite_gates_nothing_and_says_so(self):
        verdict = self.tdd.gate("make-it-pass", "UNUSABLE")
        self.assertFalse(verdict["allowed"])
        self.assertEqual(verdict["code"], 2)

    def test_the_cycle_is_a_cycle(self):
        import session as session_mod

        turn = "write-failing-test"
        for _ in range(3):
            turn = session_mod.NEXT_TURN[turn]
        self.assertEqual(turn, "write-failing-test")

    def test_advance_writes_the_next_turn_only_when_the_suite_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            red = '%s -c "print(\'1 failed\'); raise SystemExit(1)"' % sys.executable
            start(root, "--mode", "pingpong", "--test-command", red)
            advanced = run([sys.executable, str(TDD), "advance"], cwd=root)
            self.assertEqual(advanced.returncode, 0)
            state = json.loads((root / ".pair" / "session.json").read_text())
            self.assertEqual(state["turn"], "make-it-pass")
            # still red, and make-it-pass owes green: refused, turn unchanged
            refused = run([sys.executable, str(TDD), "advance"], cwd=root)
            self.assertEqual(refused.returncode, 1)
            state = json.loads((root / ".pair" / "session.json").read_text())
            self.assertEqual(state["turn"], "make-it-pass")

    def test_classify_reads_the_sessions_own_globs(self):
        self.assertTrue(self.tdd.is_test_path("tests/test_retry.py", ["test_*.py", "tests/*"]))
        self.assertTrue(self.tdd.is_test_path("src/webhooks/retry.spec.ts", ["*.spec.*"]))
        self.assertFalse(self.tdd.is_test_path("src/webhooks/retry.py", ["test_*.py", "tests/*"]))


class DriftTest(unittest.TestCase):
    def setUp(self):
        import drift

        self.drift = drift

    def test_a_pattern_without_a_glob_covers_the_directory(self):
        self.assertTrue(self.drift.matches("src/webhooks/retry.py", ["src/webhooks"]))
        self.assertFalse(self.drift.matches("src/webhooksly.py", ["src/webhooks"]))
        self.assertTrue(self.drift.matches("src/a/b.py", ["src/**"]))

    def test_no_scope_is_cannot_tell_not_on_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if not git_repo(root):
                self.skipTest("git unavailable")
            head = git(root, "rev-parse", "HEAD").stdout.strip()
            report = self.drift.assess([], head, 400, cwd=str(root))
            self.assertEqual(report["verdict"], "unclear")
            self.assertIn("no scope", report["reason"])

    def test_outside_the_repository_it_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.drift.assess(["src"], "HEAD", 400, cwd=tmp)
            if report["verdict"] != "unusable":
                self.skipTest("the temp dir is inside a git repository")
            self.assertEqual(report["verdict"], "unusable")

    def test_a_file_outside_the_scope_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if not git_repo(root):
                self.skipTest("git unavailable")
            head = git(root, "rev-parse", "HEAD").stdout.strip()
            (root / "src" / "webhooks").mkdir(parents=True)
            (root / "src" / "webhooks" / "retry.py").write_text("def retry():\n    pass\n", encoding="utf-8")
            clean = self.drift.assess(["src/webhooks"], head, 400, cwd=str(root))
            self.assertEqual(clean["verdict"], "on-scope", clean)

            (root / "docs").mkdir()
            (root / "docs" / "notes.md").write_text("stray\n", encoding="utf-8")
            drifted = self.drift.assess(["src/webhooks"], head, 400, cwd=str(root))
            self.assertEqual(drifted["verdict"], "drift")
            self.assertIn("docs/notes.md", drifted["out_of_scope"])

    def test_churn_past_the_budget_is_drift_even_inside_the_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if not git_repo(root):
                self.skipTest("git unavailable")
            head = git(root, "rev-parse", "HEAD").stdout.strip()
            (root / "src" / "big.py").write_text("x = 1\n" * 50, encoding="utf-8")
            report = self.drift.assess(["src"], head, 10, cwd=str(root))
            self.assertEqual(report["verdict"], "drift")
            self.assertIn("budget", report["reason"])

    def test_a_missing_base_commit_is_cannot_tell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if not git_repo(root):
                self.skipTest("git unavailable")
            report = self.drift.assess(["src"], "0" * 40, 400, cwd=str(root))
            self.assertEqual(report["verdict"], "unclear")


class HookTest(unittest.TestCase):
    def _hook(self, script: Path, root: Path, event: dict):
        return run([sys.executable, str(script)], cwd=root, input=json.dumps(event))

    def test_the_session_hook_is_silent_with_no_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._hook(RESUME_HOOK, Path(tmp), {})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_the_session_hook_is_silent_once_the_session_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "close")
            result = self._hook(RESUME_HOOK, root, {})
            self.assertEqual(result.stdout.strip(), "")

    def test_the_session_hook_reports_an_open_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            session(root, "next", "extract the backoff policy")
            result = self._hook(RESUME_HOOK, root, {})
            self.assertEqual(result.returncode, 0)
            self.assertIn("make the webhook retry safely", result.stdout)
            self.assertIn("extract the backoff policy", result.stdout)

    def test_the_turn_hook_is_silent_outside_pingpong(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            result = self._hook(
                TURN_HOOK, root, {"tool_input": {"file_path": "src/webhooks/retry.py"}}
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_the_turn_hook_flags_production_code_on_the_test_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root, "--mode", "pingpong", "--test-command", "true")
            noisy = self._hook(
                TURN_HOOK, root, {"tool_input": {"file_path": "src/webhooks/retry.py"}}
            )
            self.assertEqual(noisy.returncode, 0)
            self.assertIn("production code", noisy.stdout)
            quiet = self._hook(
                TURN_HOOK, root, {"tool_input": {"file_path": "tests/test_retry.py"}}
            )
            self.assertEqual(quiet.stdout.strip(), "")

    def test_the_turn_hook_flags_a_test_edit_on_the_implementation_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root, "--mode", "pingpong", "--test-command", "true")
            session(root, "turn", "--to", "make-it-pass")
            noisy = self._hook(
                TURN_HOOK, root, {"tool_input": {"file_path": "tests/test_retry.py"}}
            )
            self.assertIn("hand back", noisy.stdout)

    def test_neither_hook_fails_on_junk_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root, "--mode", "pingpong", "--test-command", "true")
            for script in (RESUME_HOOK, TURN_HOOK):
                result = run([sys.executable, str(script)], cwd=root, input="not json at all")
                self.assertEqual(result.returncode, 0, script)


class McpServerTest(unittest.TestCase):
    def _call(self, root: Path, messages):
        payload = "".join(json.dumps(m) + "\n" for m in messages)
        result = run([sys.executable, str(MCP_SERVER)], cwd=root, input=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_it_lists_its_three_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._call(Path(tmp), [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
            names = {tool["name"] for tool in responses[0]["result"]["tools"]}
            self.assertEqual(names, {"session_status", "drift_check", "pair_playbook"})

    def test_initialize_and_ping(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._call(Path(tmp), [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "ping"},
            ])
            self.assertEqual(len(responses), 2)
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "pair-programmer")

    def test_session_status_reports_the_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start(root)
            responses = self._call(root, [{
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "session_status", "arguments": {}},
            }])
            result = responses[0]["result"]
            self.assertFalse(result["isError"])
            self.assertIn("make the webhook retry safely", result["content"][0]["text"])

    def test_a_missing_session_is_an_error_result_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._call(Path(tmp), [{
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "session_status", "arguments": {}},
            }])
            self.assertTrue(responses[0]["result"]["isError"])

    def test_the_playbook_returns_a_reference_and_rejects_an_unknown_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good, bad = self._call(root, [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "pair_playbook", "arguments": {"topic": "ping-pong"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "pair_playbook", "arguments": {"topic": "nonsense"}}},
            ])
            self.assertIn("Writing the failing test", good["result"]["content"][0]["text"])
            self.assertTrue(bad["result"]["isError"])

    def test_an_unknown_tool_and_a_bad_line_are_handled(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(MCP_SERVER)], cwd=tmp,
                         input='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"nope"}}\nnot json\n')
            self.assertEqual(result.returncode, 0)
            lines = [json.loads(l) for l in result.stdout.splitlines() if l.strip()]
            self.assertEqual(lines[0]["error"]["code"], -32602)
            self.assertEqual(lines[1]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main(verbosity=1)
