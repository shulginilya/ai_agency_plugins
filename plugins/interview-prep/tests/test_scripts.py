#!/usr/bin/env python3
"""Smoke tests for the scripts, hook and MCP server the interview-prep plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
LOOP_DIR = PLUGIN / "skills" / "loop-mapping" / "scripts"
PREP_DIR = PLUGIN / "skills" / "prep-tracker" / "scripts"
STORY_DIR = PLUGIN / "skills" / "story-bank" / "scripts"
JD_SCAN = LOOP_DIR / "jd_scan.py"
PREP = PREP_DIR / "prep.py"
STORIES = STORY_DIR / "stories.py"
HOOK = PLUGIN / "scripts" / "round_watch.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

MAPPED = (
    "Senior AI Engineer, Berlin, hybrid. We are a Series B scale-up building LLM products. "
    "You will own the architecture of our retrieval augmented generation platform: TypeScript "
    "and Python services, React frontends, AWS Lambda, DynamoDB, evals and guardrails for our "
    "agentic workflows. You will mentor engineers, work cross-functional with product and set "
    "the standard for code review and incident response. Our interview process: an intro call, "
    "a technical screen with live coding, a system design interview, and a values interview."
)
UNCLEAR = (
    "Senior Frontend Engineer. You will build and own our design system in React and TypeScript, "
    "work on SSR and Core Web Vitals, run code review for the team and mentor two engineers. "
    "We use Next.js, Node and AWS. The role is hybrid in Berlin and reports to the team lead. "
    "We care about accessibility and about shipping regularly to production without drama."
)
THIN = (
    "We are looking for a rockstar developer to join our amazing journey. You will work in a "
    "dynamic team and wear many hats. Competitive salary, great culture, free fruit and the "
    "chance to make a real impact every single day in our lovely office in the city centre."
)

GOOD_STORY = dict(
    title="Halved checkout LCP",
    competencies="delivery,technical-decision",
    situation="Checkout was the slowest page in the funnel and conversion was falling.",
    task="I owned the performance work for the quarter.",
    action=(
        "I profiled the bundle, moved the payment widget behind an intersection observer, "
        "switched the page from client-side rendering to ISR, and negotiated a smaller hero "
        "image with design. I added a Core Web Vitals budget to CI so it could not regress."
    ),
    result="LCP went from 4.1s to 1.9s and checkout conversion rose 6%.",
    metric="LCP 4.1s -> 1.9s",
)
THIN_STORY = dict(
    title="A disagreement",
    competencies="conflict",
    situation="There was a disagreement about the approach.",
    task="Resolve it.",
    action="We talked about it.",
    result="It was fine afterwards.",
    metric="",
)


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def prep(root: Path, *args):
    return run([sys.executable, str(PREP), *args], cwd=root)


def stories(root: Path, *args):
    return run([sys.executable, str(STORIES), *args], cwd=root)


def add_story(root: Path, story) -> subprocess.CompletedProcess:
    args = ["add", "--title", story["title"], "--competencies", story["competencies"]]
    for field in ("situation", "task", "action", "result", "metric"):
        if story[field]:
            args += ["--" + field, story[field]]
    return stories(root, *args)


class JdScanTest(unittest.TestCase):
    def _scan(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "jd.txt"
            target.write_text(text, encoding="utf-8")
            result = run([sys.executable, str(JD_SCAN), str(target), "--json"])
            return result.returncode, json.loads(result.stdout or "{}")

    def test_the_four_verdicts_have_distinct_exit_codes(self):
        code, report = self._scan(MAPPED)
        self.assertEqual((code, report["verdict"]), (0, "mapped"))
        self.assertIn("system-design", report["round_signals"])

        code, report = self._scan(UNCLEAR)
        self.assertEqual((code, report["verdict"]), (3, "unclear"))
        self.assertTrue(any("process" in u for u in report["unknown"]))

        code, report = self._scan(THIN)
        self.assertEqual((code, report["verdict"]), (1, "thin"))

        code, report = self._scan("too short")
        self.assertEqual((code, report["verdict"]), (2, "unusable"))

    def test_terms_are_word_bounded(self):
        _, report = self._scan(MAPPED)
        # "own the architecture" must not be read as the title "architect"
        self.assertNotIn("architect", report["seniority_terms"])
        self.assertIn("senior", report["seniority_terms"])

    def test_leadership_and_archetype_are_reported(self):
        _, report = self._scan(MAPPED)
        self.assertEqual(report["archetype"], "scale-up")
        self.assertEqual(report["leadership_weight"], "high")

    def test_missing_file_is_unusable_not_a_traceback(self):
        result = run([sys.executable, str(JD_SCAN), "nope.txt"])
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


class PrepTest(unittest.TestCase):
    def _loop(self, root: Path):
        prep(root, "init")
        prep(root, "add", "--company", "Acme", "--role", "Senior AI Engineer",
             "--rounds", "recruiter-screen,system-design")

    def test_status_reports_undeclared_before_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            prep(root, "round", "--company", "Acme", "--round", "system-design",
                 "--date", "2026-09-21")
            # a scheduled round with no prep and no mock: cannot judge readiness
            result = prep(root, "status", "--as-of", "2026-09-19", "--json")
            self.assertEqual(result.returncode, 3)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "undeclared")
            self.assertIn("system-design", report["loops"][0]["unprepped_rounds"])

            # once something is prepared, the overdue item is the answer
            prep(root, "item", "--company", "Acme", "--add", "cost model",
                 "--risk", "high", "--round", "system-design", "--due", "2026-09-18")
            result = prep(root, "status", "--as-of", "2026-09-19", "--json")
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "action")
            self.assertTrue(report["loops"][0]["overdue_prep"])

    def test_status_is_clear_when_nothing_is_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prep(root, "init")
            result = prep(root, "status", "--json")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["verdict"], "clear")

    def test_missing_state_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prep(Path(tmp), "status")
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)

    def test_relative_dates_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            result = prep(root, "item", "--company", "Acme", "--add", "x", "--due", "next week")
            self.assertEqual(result.returncode, 2)
            self.assertIn("ISO date", result.stderr)

    def test_a_foreign_json_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "notes.json"
            target.write_text('{"kind": "something-else", "keep": true}', encoding="utf-8")
            result = prep(root, "--file", str(target), "add", "--company", "A", "--role", "B")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["keep"], True)

    def test_writes_back_up_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            self.assertTrue((root / ".interview" / "state.json.bak").is_file())

    def test_a_weak_mock_must_name_a_weak_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            result = prep(root, "mock", "--company", "Acme", "--round", "system-design",
                          "--grade", "weak")
            self.assertEqual(result.returncode, 2)
            ok = prep(root, "mock", "--company", "Acme", "--round", "system-design",
                      "--grade", "weak", "--weak", "no cost model;no evals")
            self.assertEqual(ok.returncode, 0)

    def test_a_debrief_without_questions_is_refused_and_closes_the_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            bad = prep(root, "debrief", "--company", "Acme", "--round", "system-design")
            self.assertEqual(bad.returncode, 2)
            good = prep(root, "debrief", "--company", "Acme", "--round", "system-design",
                        "--asked", "design multi-tenant RAG", "--outcome", "advanced")
            self.assertEqual(good.returncode, 0)
            state = json.loads((root / ".interview" / "state.json").read_text(encoding="utf-8"))
            rounds = {r["name"]: r["status"] for r in state["loops"][0]["rounds"]}
            self.assertEqual(rounds["system-design"], "done")

    def test_unknown_round_names_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            result = prep(root, "round", "--company", "Acme", "--round", "vibes-check")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown round", result.stderr)

    def test_render_writes_the_brief_from_the_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loop(root)
            prep(root, "mock", "--company", "Acme", "--round", "system-design",
                 "--grade", "mixed", "--weak", "no cost model")
            self.assertEqual(prep(root, "render").returncode, 0)
            brief = (root / ".interview" / "brief.md").read_text(encoding="utf-8")
            self.assertIn("Acme", brief)
            self.assertIn("no cost model", brief)


class StoriesTest(unittest.TestCase):
    def test_the_four_verdicts_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(stories(root, "check").returncode, 2)

            stories(root, "init")
            self.assertEqual(stories(root, "check").returncode, 1)  # nothing at all

            add_story(root, GOOD_STORY)
            add_story(root, THIN_STORY)
            self.assertEqual(stories(root, "check").returncode, 1)  # still gaps

    def test_thin_is_separate_from_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories(root, "init")
            bank = root / ".interview" / "stories.json"
            data = json.loads(bank.read_text(encoding="utf-8"))
            data["competencies"] = ["delivery", "technical-decision", "conflict"]
            bank.write_text(json.dumps(data), encoding="utf-8")

            add_story(root, GOOD_STORY)
            add_story(root, THIN_STORY)
            result = stories(root, "check", "--json")
            self.assertEqual(result.returncode, 3)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "thin")
            self.assertEqual(report["missing"], [])
            self.assertIn("conflict", report["covered_only_by_thin_stories"])

    def test_covered_needs_every_story_to_hold_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories(root, "init")
            bank = root / ".interview" / "stories.json"
            data = json.loads(bank.read_text(encoding="utf-8"))
            data["competencies"] = ["delivery", "technical-decision"]
            bank.write_text(json.dumps(data), encoding="utf-8")
            add_story(root, GOOD_STORY)
            self.assertEqual(stories(root, "check").returncode, 0)

    def test_the_quality_rules_are_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories(root, "init")
            add_story(root, THIN_STORY)
            report = json.loads(stories(root, "check", "--json").stdout)
            problems = " ".join(report["thin_stories"][0]["problems"])
            self.assertIn("too thin to probe", problems)
            self.assertIn("'I'", problems)

    def test_unknown_competencies_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories(root, "init")
            story = dict(GOOD_STORY, competencies="vibes")
            self.assertEqual(add_story(root, story).returncode, 2)

    def test_a_foreign_json_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "notes.json"
            target.write_text('{"kind": "something-else", "keep": true}', encoding="utf-8")
            result = stories(root, "--file", str(target), "check")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["keep"], True)


class HookTest(unittest.TestCase):
    def _hook(self, root: Path):
        return run([sys.executable, str(HOOK)], cwd=root, input="{}")

    def test_silent_without_a_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._hook(Path(tmp))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_silent_when_nothing_is_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prep(root, "init")
            result = self._hook(root)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_speaks_when_a_round_has_nothing_prepared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prep(root, "init")
            prep(root, "add", "--company", "Acme", "--role", "Senior AI Engineer",
                 "--rounds", "system-design")
            prep(root, "round", "--company", "Acme", "--round", "system-design",
                 "--date", "2099-01-01")
            result = self._hook(root)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Acme", result.stdout)
            self.assertIn("nothing prepared", result.stdout)

    def test_never_blocks_on_a_broken_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".interview").mkdir()
            (root / ".interview" / "state.json").write_text("{not json", encoding="utf-8")
            result = self._hook(root)
            self.assertEqual(result.returncode, 0)
            self.assertIn("unreadable", result.stdout)


class McpServerTest(unittest.TestCase):
    def _talk(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_lists_its_four_tools(self):
        replies = self._talk([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        names = {t["name"] for t in replies[0]["result"]["tools"]}
        self.assertEqual(names, {"prep_status", "scan_jd", "story_coverage", "interview_playbook"})

    def test_playbook_returns_a_reference(self):
        replies = self._talk([{
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "interview_playbook", "arguments": {"topic": "round-formats"}},
        }])
        result = replies[0]["result"]
        self.assertFalse(result["isError"])
        self.assertIn("System design", result["content"][0]["text"])

    def test_scan_jd_matches_the_script(self):
        replies = self._talk([{
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "scan_jd", "arguments": {"description": MAPPED}},
        }])
        report = json.loads(replies[0]["result"]["content"][0]["text"])
        self.assertEqual(report["verdict"], "mapped")

    def test_a_bad_argument_is_an_error_not_a_crash(self):
        replies = self._talk([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "prep_status", "arguments": {"file": "nope.json"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "nonsense", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        ])
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn("error", replies[1])
        self.assertIn("tools", replies[2]["result"])  # still alive


if __name__ == "__main__":
    unittest.main()
