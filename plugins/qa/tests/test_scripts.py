#!/usr/bin/env python3
"""Smoke tests for the scripts the qa plugin ships."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent
CRITERIA = PLUGIN / "skills" / "test-planning" / "scripts" / "criteria.py"
REPORT = PLUGIN / "skills" / "acceptance-testing" / "scripts" / "qa_report.py"
REVIEW = REPORT.parent / "review_link.py"
sys.path.insert(0, str(CRITERIA.parent))
sys.path.insert(0, str(REPORT.parent))
import criteria  # noqa: E402
import pr_base  # noqa: E402
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
    def test_comment_pages_are_decoded_even_when_a_body_holds_brackets(self):
        out = '[{"body": "see [1][2]"}, {"body": "x]\\n[y"}]\n[{"body": "page two"}]'
        self.assertEqual([c["body"] for c in review_link.concat_pages(out)], ["see [1][2]", "x]\n[y", "page two"])
        self.assertEqual(review_link.concat_pages(""), [])

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


    # --- the devops comment: one per ticket, edited on every deploy ----------

    def devops_comment(self, commit, created="2026-10-25T01:00:00Z", updated=None, state="live",
                       link="https://79-feat-x.app.review.com"):
        c = comment("<!-- devops:review-link link=%s commit=%s pr=43 state=%s -->\n**Review link:** %s"
                    % (link, commit, state, link), created)
        c["updated_at"] = updated or created
        return c

    def test_the_devops_comment_says_which_commit_the_link_serves(self):
        d = review_link.decide("", [self.devops_comment("abc1234")], commit="abc1234ffff")
        self.assertEqual((d["action"], d["link"], d["serves"]), ("test", "https://79-feat-x.app.review.com", "abc1234"))

    def test_an_older_build_on_the_link_means_wait_not_test(self):
        d = review_link.decide("", [self.devops_comment("abc1234")], commit="def5678")
        self.assertEqual(d["action"], "wait")
        self.assertIn("abc1234", d["reason"])

    def test_an_edited_devops_comment_counts_as_new_as_of_its_edit(self):
        pasted = comment("try https://old.app.review.com", "2026-10-25T02:00:00Z")
        edited = self.devops_comment("def5678", created="2026-10-25T01:00:00Z", updated="2026-10-25T03:00:00Z")
        d = review_link.decide("", [edited, pasted], commit="def5678")
        self.assertEqual(d["link"], "https://79-feat-x.app.review.com", "the edit came after the pasted link")
        unedited = self.devops_comment("def5678", created="2026-10-25T01:00:00Z")
        d = review_link.decide("", [unedited, pasted])
        self.assertEqual(d["link"], "https://old.app.review.com")

    def test_a_new_deploy_after_the_verdict_means_retest_and_a_rerun_does_not(self):
        verdict = self.verdict_comment("https://79-feat-x.app.review.com", commit="abc1234")
        same = self.devops_comment("abc1234", updated="2026-10-25T05:00:00Z")
        d = review_link.decide("", [same, verdict], commit="abc1234")
        self.assertEqual(d["action"], "up-to-date", "a re-run that deployed the same commit is nothing new")
        newer = self.devops_comment("def5678", updated="2026-10-25T05:00:00Z")
        d = review_link.decide("", [newer, verdict], commit="def5678")
        self.assertEqual(d["action"], "retest")
        d = review_link.decide("", [newer, verdict])
        self.assertEqual(d["action"], "retest", "without --commit, the commit the link serves is what gets tested")

    # --- --local: review links are paused, QA tests the PR head locally -------

    def test_local_ignores_every_review_link(self):
        d = review_link.decide("https://a.app.review.com", [self.devops_comment("abc1234")],
                               commit="def5678", local=True)
        self.assertEqual((d["action"], d["link"]), ("test", None), "an older build on a link is no reason to wait")

    def test_local_with_no_verdict_means_test(self):
        d = review_link.decide("no link", [], commit="abc1234", local=True)
        self.assertEqual(d["action"], "test")

    def test_local_decides_on_the_commit_alone(self):
        verdict = self.verdict_comment("none", commit="abc1234")
        d = review_link.decide("", [verdict], commit="abc1234ffff", local=True)
        self.assertEqual(d["action"], "up-to-date", "a longer form of the same commit is the same commit")
        d = review_link.decide("", [verdict], commit="def5678", local=True)
        self.assertEqual(d["action"], "retest")
        self.assertIn("abc1234", d["reason"])

    def test_local_reads_verdicts_given_on_a_review_link_too(self):
        verdict = self.verdict_comment("https://a.app.review.com", commit="abc1234")
        later = comment("new link: https://b.app.review.com", "2026-10-25T09:00:00Z")
        d = review_link.decide("", [verdict, later], commit="abc1234", local=True)
        self.assertEqual(d["action"], "up-to-date", "a link posted after the verdict changes nothing locally")

    def test_local_without_a_commit_is_test(self):
        d = review_link.decide("", [self.verdict_comment("none")], local=True)
        self.assertEqual(d["action"], "test", "with no commit to compare, test rather than skip")

    def test_local_the_newest_verdict_wins(self):
        older = self.verdict_comment("none", commit="abc1234", at="2026-10-25T02:00:00Z")
        newer = self.verdict_comment("none", commit="def5678", at="2026-10-25T04:00:00Z")
        for comments in ([older, newer], [newer, older]):
            d = review_link.decide("", comments, commit="def5678", local=True)
            self.assertEqual(d["action"], "up-to-date", "the newest verdict tested def5678")
            d = review_link.decide("", comments, commit="abc1234", local=True)
            self.assertEqual(d["action"], "retest", "abc1234 is only the older verdict's commit")

    def test_local_cli_never_reads_the_review_domain_or_prints_a_link(self):
        calls = []
        link_comment = self.devops_comment("abc1234")
        link_comment.update(html_url="https://github.com/me/app/issues/7#c1")

        def fake_gh(*args):
            calls.append(args)
            path = next((a for a in args if a.startswith("repos/") or a == "graphql"), "")
            if "REVIEW_DOMAIN" in path:
                raise AssertionError("--local must not look up REVIEW_DOMAIN")
            if path.startswith("repos/me/app/pulls/8"):
                return json.dumps({"head": {"sha": "def5678"}})
            if "/comments" in path:
                return json.dumps([link_comment])
            if path == "graphql":
                return json.dumps({"data": {"repository": {"issue": {"projectItems": {"nodes": [
                    {"project": {"number": 1, "title": "Board"}, "fieldValueByName": {"name": "QA"}}]}}}}})
            return json.dumps({"title": "t", "body": "see https://a.app.review.com", "html_url": "u"})

        out = io.StringIO()
        with mock.patch.object(review_link, "gh", fake_gh), contextlib.redirect_stdout(out):
            code = review_link.main(["--issue", "7", "--repo", "me/app", "--pr", "8", "--local"])
        self.assertEqual(code, 0)
        self.assertFalse(any("REVIEW_DOMAIN" in " ".join(c) for c in calls))
        text = out.getvalue()
        self.assertIn("me/app#7: test", text)
        self.assertNotIn("review link:", text)
        self.assertIn("board #1 Board: QA", text)

    def test_a_link_taken_down_is_no_link(self):
        d = review_link.decide("", [self.devops_comment("abc1234", state="down")])
        self.assertEqual(d["action"], "none")

    def test_the_review_domain_is_configurable(self):
        text = "https://feat.app.review.example.dev and https://feat.app.review.com"
        self.assertEqual(review_link.links_in(text, "review.example.dev"), ["https://feat.app.review.example.dev"])
        self.assertEqual(review_link.links_in(text), ["https://feat.app.review.com"])
        self.assertEqual(review_link.links_in("https://a.b.c.review.example.dev", "review.example.dev"), [])

    def test_the_cli_takes_the_domain_and_refuses_a_bad_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, str(REVIEW), "--issue", "1", "--repo", "me/app",
                                   "--domain", "not a domain"], capture_output=True, text=True,
                                  env=dict(os.environ, PATH=tmp))
        self.assertEqual(done.returncode, 2, done.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class PrBaseTest(unittest.TestCase):
    """QA never accepts a PR whose base is not the default branch: its merge would land in a dead branch."""

    def run_main(self, base, state="open", *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(pr_base, "current_repo", return_value="acme/app"), \
                mock.patch.object(pr_base, "default_branch", return_value="main"), \
                mock.patch.object(pr_base, "pr_info", return_value={"base": base, "state": state}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pr_base.main(["--pr", "38", *args])
        return code, out.getvalue(), err.getvalue()

    def test_a_stacked_pr_is_refused_with_both_branches_named(self):
        code, out, err = self.run_main("feat/33-code-style")
        self.assertEqual(code, 3)
        self.assertIn("base is not main", err)
        self.assertIn("feat/33-code-style", err)
        self.assertEqual(out, "", "nothing on stdout reads as a go-ahead")

    def test_a_pr_into_the_default_branch_passes(self):
        code, out, _ = self.run_main("main")
        self.assertEqual(code, 0)
        self.assertIn("targets main", out)

    def test_the_problem_text_is_none_for_the_default(self):
        self.assertIsNone(pr_base.base_problem("main", "main"))
        self.assertIn("base is not main", pr_base.base_problem("dev", "main"))

    def test_verify_and_the_skill_run_pr_base_first_and_stop_on_a_wrong_base(self):
        command = (PLUGIN / "commands" / "verify.md").read_text(encoding="utf-8")
        skill = (PLUGIN / "skills" / "acceptance-testing" / "SKILL.md").read_text(encoding="utf-8")
        for text in (command, skill):
            self.assertIn("pr_base.py", text)
            self.assertIn("base is not <default>", text)
        self.assertLess(command.index("pr_base.py"), command.index("criteria.py"), "before any testing")
        self.assertIn("move no card", command)
