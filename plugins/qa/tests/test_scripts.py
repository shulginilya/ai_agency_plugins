#!/usr/bin/env python3
"""Smoke tests for the scripts the qa plugin ships."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
CRITERIA = PLUGIN / "skills" / "test-planning" / "scripts" / "criteria.py"
REPORT = PLUGIN / "skills" / "acceptance-testing" / "scripts" / "qa_report.py"
sys.path.insert(0, str(CRITERIA.parent))
sys.path.insert(0, str(REPORT.parent))
import criteria  # noqa: E402
import qa_report  # noqa: E402

TICKET = """## Problem
Uploads fail silently.

## Acceptance criteria
- [ ] Given no sessions, when I open the list, then it shows "No sessions yet"
- [x] A file over 10 MB is refused with an error naming the limit
- [ ] The page loads fast

## Notes
- [ ] not a criterion, it is under another heading
"""


def run(*args, stdin=None, env=None):
    return subprocess.run([sys.executable, *map(str, args)], input=stdin, capture_output=True, text=True,
                          check=False, env=env)


class CriteriaTest(unittest.TestCase):
    def test_reads_only_the_acceptance_criteria_section(self):
        items = criteria.extract(TICKET)
        self.assertEqual([i["id"] for i in items], ["AC1", "AC2", "AC3"])
        self.assertEqual(items[0]["then"], 'it shows "No sessions yet"')
        self.assertNotIn("given", items[1])

    def test_flags_vague_and_unobservable_criteria(self):
        items = criteria.extract(TICKET)
        self.assertEqual(items[0]["problems"], [])
        self.assertEqual(items[1]["problems"], [])
        self.assertTrue(any("vague: fast" in p for p in items[2]["problems"]))

    def test_without_a_heading_every_checkbox_counts(self):
        items = criteria.extract("- [ ] export returns a CSV\n- [ ] import refuses a bad header\n")
        self.assertEqual(len(items), 2)

    def test_no_criteria_is_exit_two(self):
        result = run(CRITERIA, stdin="just prose, no checkboxes\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no acceptance criteria", result.stderr)

    def test_missing_gh_is_exit_one(self):
        result = run(CRITERIA, "--issue", "1", env={**os.environ, "PATH": ""})
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh is not installed", result.stderr)

    def test_plan_skeleton_lists_each_criterion(self):
        result = run(CRITERIA, stdin=TICKET)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("| AC3 |", result.stdout)
        self.assertIn("AC1-1", result.stdout)


def results(*cases, criteria_ids=("AC1", "AC2")):
    return {"ticket": "#42", "change": "PR #43",
            "criteria": [{"id": c, "text": "criterion %s" % c} for c in criteria_ids],
            "cases": list(cases)}


def case(cid, ac, status, evidence="seen", **kw):
    return dict({"id": cid, "ac": ac, "kind": "happy", "status": status, "evidence": evidence}, **kw)


class VerdictTest(unittest.TestCase):
    def verdict(self, data):
        return qa_report.judge(qa_report.load(data))

    def test_accept_needs_a_passing_case_per_criterion(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "pass")))
        self.assertEqual(v["verdict"], "accept")

    def test_any_failure_rejects(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC1-2", "AC1", "fail"),
                                 case("AC2-1", "AC2", "pass")))
        self.assertEqual((v["verdict"], v["failed"]), ("reject", ["AC1"]))

    def test_a_criterion_without_cases_rejects(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass")))
        self.assertEqual((v["verdict"], v["uncovered"]), ("reject", ["AC2"]))

    def test_blocked_is_not_a_pass(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "blocked", note="no env")))
        self.assertEqual((v["verdict"], v["unproven"]), ("blocked", ["AC2"]))

    def test_a_pass_without_evidence_counts_as_not_run(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "pass", evidence="")))
        self.assertEqual(v["verdict"], "blocked")

    def test_bad_input_is_refused(self):
        for bad in ({}, {"criteria": [], "cases": []},
                    results(case("X-1", "AC9", "pass")),
                    results(case("AC1-1", "AC1", "maybe"))):
            with self.assertRaises(qa_report.ReportError):
                qa_report.load(bad)

    def test_cli_exit_codes_follow_the_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "pass"))),
                            encoding="utf-8")
            self.assertEqual(run(REPORT, path).returncode, 0)
            path.write_text(json.dumps(results(case("AC1-1", "AC1", "fail"))), encoding="utf-8")
            result = run(REPORT, path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("REJECT", result.stdout)
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(run(REPORT, path).returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
