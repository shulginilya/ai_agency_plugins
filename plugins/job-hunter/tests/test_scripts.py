#!/usr/bin/env python3
"""Smoke tests for the scripts, hook and MCP server the job-hunter plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
TRIAGE = PLUGIN / "skills" / "opportunity-triage" / "scripts"
PIPELINE_DIR = PLUGIN / "skills" / "application-pipeline" / "scripts"
FIT = TRIAGE / "fit.py"
PIPELINE = PIPELINE_DIR / "pipeline.py"
HOOK = PLUGIN / "scripts" / "pipeline_status.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

sys.path.insert(0, str(TRIAGE))
sys.path.insert(0, str(PIPELINE_DIR))

PROFILE = {
    "titles": ["Senior AI Engineer"],
    "must_have": ["typescript", "react", "node"],
    "nice_to_have": ["aws"],
    "markets": {"onsite": ["Berlin"], "remote": ["eu"]},
    "tracks": ["contract"],
    "deal_breakers": ["relocation required"],
    "min_must_have_ratio": 0.6,
}

GOOD = "Senior AI Engineer, contract, fully remote within the EU. TypeScript, React, Node. AWS a plus. EUR 700/day."
BREAKER = "Senior AI Engineer, contract, remote EU. TypeScript, React, Node. Relocation required."
THIN = "PHP developer wanted, permanent, on-site in Munich."
VAGUE = "We want an engineer. TypeScript, React and Node are the stack."


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def workspace(tmp: str) -> Path:
    root = Path(tmp)
    (root / ".jobhunt").mkdir(parents=True, exist_ok=True)
    (root / ".jobhunt" / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
    return root


class FitTest(unittest.TestCase):
    def _verdict(self, root: Path, posting: str):
        target = root / "posting.txt"
        target.write_text(posting, encoding="utf-8")
        result = run([sys.executable, str(FIT), str(target), "--json"], cwd=root)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}

    def test_the_four_verdicts_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)

            code, report = self._verdict(root, GOOD)
            self.assertEqual((code, report["verdict"]), (0, "pursue"))

            code, report = self._verdict(root, BREAKER)
            self.assertEqual((code, report["verdict"]), (1, "skip"))
            self.assertIn("relocation required", report["deal_breakers_hit"])

            code, report = self._verdict(root, THIN)
            self.assertEqual((code, report["verdict"]), (1, "skip"))

            code, report = self._verdict(root, VAGUE)
            self.assertEqual((code, report["verdict"]), (3, "unclear"),
                             "a posting that omits track and location is unclear, not a fit")

    def test_a_missing_profile_is_exit_two_not_a_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            posting = Path(tmp) / "p.txt"
            posting.write_text(GOOD, encoding="utf-8")
            result = run([sys.executable, str(FIT), str(posting)], cwd=tmp)
            self.assertEqual(result.returncode, 2)
            self.assertIn("no profile", result.stderr)

    def test_an_empty_posting_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            (root / "empty.txt").write_text("   \n", encoding="utf-8")
            result = run([sys.executable, str(FIT), str(root / "empty.txt")], cwd=root)
            self.assertEqual(result.returncode, 2)

    def test_short_terms_are_word_bounded(self):
        import fit

        profile = dict(PROFILE, must_have=["go"], min_must_have_ratio=1.0)
        report = fit.assess("We use Django and Node here. Contract, remote EU.", profile)
        self.assertEqual(report["must_have"]["present"], [],
                         "'go' must not match inside 'Django'")


class PipelineTest(unittest.TestCase):
    def _run(self, root: Path, *args):
        return run([sys.executable, str(PIPELINE)] + list(args), cwd=root)

    def _seed(self, root: Path):
        self._run(root, "init")
        self._run(root, "add", "--company", "Acme", "--role", "Senior AI Engineer",
                  "--next", "send proposal", "--due", "2026-09-04")
        self._run(root, "add", "--company", "Globex", "--role", "AI Engineer",
                  "--stage", "applied", "--next", "follow up", "--due", "2026-09-20")

    def test_add_move_and_list_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            moved = self._run(root, "move", "Acme", "--to", "screening", "--next", "prep call",
                              "--due", "2026-09-11")
            self.assertEqual(moved.returncode, 0, moved.stderr)

            listed = self._run(root, "--json", "list")
            rows = {r["Company"]: r for r in json.loads(listed.stdout)}
            self.assertEqual(rows["Acme"]["Stage"], "screening")
            self.assertEqual(rows["Acme"]["Due"], "2026-09-11")
            self.assertEqual(rows["Globex"]["Stage"], "applied")

    def test_due_separates_overdue_from_missing_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            self._run(root, "add", "--company", "Initech", "--role", "Platform", "--stage", "applied")

            result = self._run(root, "--json", "due", "--as-of", "2026-09-06")
            self.assertEqual(result.returncode, 1, "something needs action, so this must exit 1")
            report = json.loads(result.stdout)
            self.assertEqual([r["Company"] for r in report["overdue"]], ["Acme"])
            self.assertEqual([r["Company"] for r in report["needs_attention"]], ["Initech"])
            self.assertEqual([r["Company"] for r in report["upcoming"]], [])

    def test_nothing_due_exits_zero_and_closed_rows_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run(root, "init")
            self._run(root, "add", "--company", "Acme", "--role", "R",
                      "--next", "chase", "--due", "2026-12-31")
            result = self._run(root, "due", "--as-of", "2026-09-06")
            self.assertEqual(result.returncode, 0)

            self._run(root, "add", "--company", "Dead", "--role", "R")
            self._run(root, "move", "Dead", "--to", "closed")
            result = self._run(root, "--json", "due", "--as-of", "2026-09-06")
            report = json.loads(result.stdout)
            self.assertNotIn("Dead", [r["Company"] for r in report["needs_attention"]])

    def test_a_malformed_table_is_refused_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = root / "broken.md"
            original = "| Company | Role |\n| --- | --- |\n| Acme | Dev |\n"
            broken.write_text(original, encoding="utf-8")
            result = self._run(root, "--file", str(broken), "list")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(broken.read_text(encoding="utf-8"), original,
                             "a table it cannot parse must be left exactly as found")

    def test_a_non_iso_due_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run(root, "init")
            result = self._run(root, "add", "--company", "Acme", "--role", "R", "--due", "next week")
            self.assertEqual(result.returncode, 2)
            self.assertIn("ISO date", result.stderr)

    def test_duplicates_are_refused_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            again = self._run(root, "add", "--company", "Acme", "--role", "Other")
            self.assertEqual(again.returncode, 2)


class HookTest(unittest.TestCase):
    def test_speaks_only_when_something_needs_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run([sys.executable, str(PIPELINE), "init"], cwd=root)
            run([sys.executable, str(PIPELINE), "add", "--company", "Acme", "--role", "R",
                 "--next", "chase", "--due", "2020-01-01"], cwd=root)
            result = run([sys.executable, str(HOOK)], input="{}", cwd=root)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Acme", result.stdout)

    def test_silent_with_no_pipeline_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(HOOK)], input="{}", cwd=tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

            result = run([sys.executable, str(HOOK)], input="not json", cwd=tmp)
            self.assertEqual(result.returncode, 0)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_and_list_tools(self):
        responses = self._rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "job-hunter")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"pipeline_status", "score_fit", "hunt_playbook"})

    def test_score_fit_uses_the_skills_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            responses = self._rpc([{
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "score_fit", "arguments": {"posting": BREAKER}},
            }], cwd=root)
            result = responses[0]["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(json.loads(result["content"][0]["text"])["verdict"], "skip")

    def test_playbook_returns_a_reference(self):
        responses = self._rpc([{
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "hunt_playbook", "arguments": {"topic": "cadence"}},
        }])
        self.assertIn("Follow-up cadence", responses[0]["result"]["content"][0]["text"])

    def test_a_bad_file_is_a_tool_error_and_the_server_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._rpc([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "pipeline_status", "arguments": {"file": "nope.md"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "ping"},
            ], cwd=tmp)
            self.assertTrue(responses[0]["result"]["isError"])
            self.assertEqual(responses[1]["result"], {}, "the server must still be alive")

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
