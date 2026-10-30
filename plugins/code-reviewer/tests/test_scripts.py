#!/usr/bin/env python3
"""Smoke tests for the scripts the code-reviewer plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "pr-review" / "scripts"
REPORT = SCRIPTS / "review_report.py"
sys.path.insert(0, str(SCRIPTS))
import pr_scope  # noqa: E402
import review_report  # noqa: E402


def finding(severity, failure="empty list -> IndexError", **extra):
    return dict({"severity": severity, "file": "src/a.py", "line": 12, "claim": "drops the error",
                 "why": "the caller assumes a value", "failure": failure, "fix": "guard the empty case"}, **extra)


def findings(*items, passes=("correctness", "tests")):
    return {"pr": 43, "ticket": "#42", "commit": "abc1234", "passes": list(passes), "findings": list(items)}


def run_report(data, *args):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return subprocess.run([sys.executable, str(REPORT), str(path), *args], capture_output=True, text=True,
                              check=False)


class VerdictTest(unittest.TestCase):
    def test_any_blocker_or_major_requests_changes(self):
        for severity in ("blocker", "major"):
            result = review_report.judge(review_report.load(findings(finding("minor"), finding(severity))))
            self.assertEqual(result["verdict"], "request-changes", severity)
            self.assertEqual(result["move_to"], "In progress")
            self.assertEqual(result["findings"][0]["severity"], severity, "most severe first")

    def test_minor_and_nit_approve_into_in_approval(self):
        result = review_report.judge(review_report.load(findings(finding("minor"), finding("nit", failure=""))))
        self.assertEqual(result["verdict"], "approve")
        self.assertEqual(result["move_to"], "In approval")
        self.assertIn("Moving the ticket to **In approval**", review_report.render(result))

    def test_skip_human_approval_sends_an_approve_straight_to_qa(self):
        data = dict(findings(), skip_human_approval=True)
        result = review_report.judge(review_report.load(data))
        self.assertEqual(result["move_to"], "QA")
        self.assertIn("skip_human_approval", review_report.render(result))
        self.assertEqual(review_report.move_to("approve", ["bug", "skip_human_approval"]), "QA")
        self.assertEqual(review_report.move_to("approve", ["bug"]), "In approval")
        self.assertEqual(review_report.move_to("request-changes", ["skip_human_approval"]), "In progress")
        done = run_report(findings(), "--skip-human-approval", "--json")
        self.assertEqual(json.loads(done.stdout)["move_to"], "QA")

    def test_no_findings_is_an_approve(self):
        self.assertEqual(review_report.judge(review_report.load(findings()))["verdict"], "approve")

    def test_a_finding_without_a_failure_scenario_is_refused(self):
        with self.assertRaisesRegex(review_report.ReportError, "hunch"):
            review_report.load(findings(finding("major", failure="  ")))

    def test_correctness_and_tests_passes_are_required(self):
        with self.assertRaisesRegex(review_report.ReportError, "tests"):
            review_report.load(findings(passes=("correctness", "security")))
        with self.assertRaisesRegex(review_report.ReportError, "unknown pass"):
            review_report.load(findings(passes=("correctness", "tests", "vibes")))

    def test_body_ends_with_the_marker_for_the_reviewed_commit(self):
        result = run_report(findings(finding("blocker")), "--commit", "def5678")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("REQUEST CHANGES", result.stdout)
        self.assertIn("Failure: empty list -> IndexError", result.stdout)
        marker = review_report.verdict_of(result.stdout)
        self.assertEqual(marker, {"verdict": "request-changes", "pr": "43", "commit": "def5678"})

    def test_exit_codes(self):
        self.assertEqual(run_report(findings()).returncode, 0)
        self.assertEqual(run_report({"findings": []}).returncode, 2)


class ScopeTest(unittest.TestCase):
    MARK = "Code review: **APPROVE**\n<!-- code-review:verdict verdict=%s pr=43 commit=%s -->"

    def review(self, verdict, commit, at):
        return {"body": self.MARK % (verdict, commit), "submitted_at": at, "url": "u"}

    def test_no_verdict_yet_means_review(self):
        plain = {"body": "LGTM", "submitted_at": "2026-10-01T00:00:00Z"}
        self.assertEqual(pr_scope.decide("abc1234ffff", [plain])["action"], "review")

    def test_same_head_is_up_to_date_and_a_new_head_is_a_re_review(self):
        reviews = [self.review("request-changes", "1111111", "2026-10-01T00:00:00Z"),
                   self.review("approve", "abc1234", "2026-10-02T00:00:00Z")]
        self.assertEqual(pr_scope.decide("abc1234ffff", reviews)["action"], "up-to-date")
        decided = pr_scope.decide("9999999aaaa", reviews)
        self.assertEqual(decided["action"], "re-review")
        self.assertEqual(decided["last"]["verdict"], "approve", "the newest verdict counts")

    def test_closed_pr_has_nothing_to_review(self):
        self.assertEqual(pr_scope.decide("abc", [], state="merged")["action"], "closed")

    def test_pages_are_decoded_even_when_a_patch_holds_brackets(self):
        out = '[{"patch": "a][b"}]\n[{"patch": "c"}]'
        self.assertEqual([p["patch"] for p in pr_scope.concat_pages(out)], ["a][b", "c"])
        self.assertEqual(pr_scope.concat_pages(""), [])


if __name__ == "__main__":
    unittest.main()
