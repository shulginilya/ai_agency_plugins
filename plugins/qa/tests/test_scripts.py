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
import review_link  # noqa: E402

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

    def test_an_unchecked_criterion_rejects_and_is_suggested_for_blocking(self):
        for status in ("unchecked", "blocked"):
            v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", status, note="no env")))
            self.assertEqual((v["verdict"], v["unproven"], v["move_to"]), ("reject", ["AC2"], "In progress"))
            self.assertEqual(v["suggest_block"], [{"ac": "AC2", "why": "no env"}])

    def test_only_two_verdicts_and_where_each_moves_the_ticket(self):
        accept = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "pass")))
        self.assertEqual((accept["verdict"], accept["move_to"]), ("accept", "Ready for Merge"))
        self.assertEqual(qa_report.MOVE_TO, {"accept": "Ready for Merge", "reject": "In progress"})

    def test_a_pass_without_evidence_counts_as_not_run(self):
        v = self.verdict(results(case("AC1-1", "AC1", "pass"), case("AC2-1", "AC2", "pass", evidence="")))
        self.assertEqual(v["verdict"], "reject")

    def test_the_comment_says_what_fails_and_carries_the_verdict_marker(self):
        data = results(case("AC1-1", "AC1", "fail", note="the filter shows warnings too", steps="open /logs, pick Errors"),
                       case("AC2-1", "AC2", "unchecked", note="no staging data"))
        data.update(review_link="https://71-feat-qa.my-app.review.com", commit="abc1234")
        text = qa_report.render(qa_report.judge(qa_report.load(data)))
        self.assertIn("Tested on the review link https://71-feat-qa.my-app.review.com, commit `abc1234`.", text)
        self.assertIn("Moving the ticket to **In progress**.", text)
        self.assertIn("- AC1-1 (happy, fail): the filter shows warnings too Steps: open /logs, pick Errors.", text)
        self.assertIn("Suggest blocking (QA does not block; the Captain decides):\n- AC2 could not be checked: "
                      "no staging data", text)
        marker = review_link.verdict_of(text)
        self.assertEqual(marker, {"verdict": "reject", "link": "https://71-feat-qa.my-app.review.com",
                                  "commit": "abc1234"})

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


def comment(body, at):
    return {"body": body, "created_at": at, "url": "https://github.com/me/app/issues/7#c-" + at}


class ReviewLinkTest(unittest.TestCase):
    def test_only_links_shaped_name_dot_slug_dot_review_dot_com_count(self):
        text = ("Review: https://71-feat-qa-link.my-app.review.com/login?next=1, also "
                "feat_x.shop.REVIEW.com and (https://a.b.review.com). Not: https://review.com, "
                "https://my-app.review.com, https://a.b.c.review.com, https://a.b.review.company, "
                "https://a.b.reviews.com, https://example.com/review")
        self.assertEqual(review_link.links_in(text), [
            "https://71-feat-qa-link.my-app.review.com/login?next=1",
            "https://feat_x.shop.review.com",
            "https://a.b.review.com",
        ])

    def test_no_link_means_test_as_before(self):
        d = review_link.decide("no link here", [comment("still none", "2026-10-25T01:00:00Z")])
        self.assertEqual((d["action"], d["link"]), ("none", None))

    def test_the_newest_link_wins_and_the_first_one_is_tested(self):
        d = review_link.decide("see https://old.app.review.com",
                               [comment("new build: https://new.app.review.com", "2026-10-25T01:00:00Z")])
        self.assertEqual((d["action"], d["link"]), ("test", "https://new.app.review.com"))
        self.assertTrue(d["source"].endswith("2026-10-25T01:00:00Z"))

    def verdict_comment(self, link, commit="abc1234", at="2026-10-25T02:00:00Z"):
        return comment("QA verdict: **REJECT**\n\n<!-- qa:verdict verdict=reject link=%s commit=%s -->"
                       % (link, commit), at)

    def test_a_link_after_the_verdict_means_retest(self):
        d = review_link.decide("https://a.app.review.com", [
            self.verdict_comment("https://a.app.review.com"),
            comment("fixed, same link: https://a.app.review.com", "2026-10-25T03:00:00Z")])
        self.assertEqual(d["action"], "retest")

    def test_the_verdict_comment_is_never_read_as_a_new_link(self):
        d = review_link.decide("https://a.app.review.com", [self.verdict_comment("https://a.app.review.com")])
        self.assertEqual(d["action"], "up-to-date")
        self.assertEqual(d["last_verdict"]["verdict"], "reject")

    def test_a_different_link_or_commit_than_the_verdict_tested_means_retest(self):
        d = review_link.decide("https://b.app.review.com", [self.verdict_comment("none")])
        self.assertEqual(d["action"], "retest")
        d = review_link.decide("https://a.app.review.com", [self.verdict_comment("https://a.app.review.com")],
                               commit="def5678")
        self.assertEqual(d["action"], "retest")
        d = review_link.decide("https://a.app.review.com", [self.verdict_comment("https://a.app.review.com")],
                               commit="abc1234ffff")
        self.assertEqual(d["action"], "up-to-date", "a longer form of the same commit is the same commit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
