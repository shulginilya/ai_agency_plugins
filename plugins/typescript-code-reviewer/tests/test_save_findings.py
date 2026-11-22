#!/usr/bin/env python3
"""Smoke tests: a request-changes verdict is saved, with its findings, as JSON under ~/Documents/code_reviews."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REVIEW = PLUGIN / "skills" / "typescript-review"
REPORT = REVIEW / "scripts" / "review_report.py"
ENV = "TS_REVIEW_SAVE_DIR"
DEFAULT_DIR = "~/Documents/code_reviews"


def item(severity, **extra):
    return dict({"severity": severity, "pass": "types", "file": "src/a.ts", "line": 12, "claim": "the cast drops null",
                 "why": "w", "failure": "res.json() returns {user: null} -> TypeError", "fix": "parse"}, **extra)


def data(*items, target="PR #43"):
    return {"target": target, "commit": "abc1234def", "passes": ["types", "correctness", "tests"],
            "checks": [], "findings": list(items)}


def run(payload, save_dir=None, *args, home=None):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "findings.json"
        src.write_text(json.dumps(payload), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != ENV}
        if save_dir is not None:
            env[ENV] = str(save_dir)
        if home is not None:
            env["HOME"] = env["USERPROFILE"] = str(home)
        return subprocess.run([sys.executable, str(REPORT), str(src), *args], capture_output=True, text=True,
                              env=env, check=False)


class SaveTests(unittest.TestCase):
    def test_request_changes_saves_the_verdict_and_every_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reviews"  # created when missing
            done = run(data(item("blocker"), item("minor"), item("nit", failure="")), out)
            self.assertEqual(done.returncode, 1, done.stderr)
            files = list(out.glob("*.json"))
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(saved["verdict"], "request-changes")
            self.assertEqual(saved["commit"], "abc1234def")
            self.assertEqual(saved["target"], "PR #43")
            self.assertEqual([f["severity"] for f in saved["findings"]], ["blocker", "minor", "nit"])
            self.assertEqual(saved["findings"][0]["failure"], "res.json() returns {user: null} -> TypeError")
            self.assertIn(str(files[0]), done.stderr)  # says where it went; stdout stays the report

    def test_the_default_folder_is_documents_code_reviews_in_the_home_directory(self):
        with tempfile.TemporaryDirectory() as home:
            done = run(data(item("major")), None, home=home)
            self.assertEqual(done.returncode, 1, done.stderr)
            self.assertEqual(len(list((Path(home) / "Documents" / "code_reviews").glob("*.json"))), 1)

    def test_an_approve_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = run(data(item("minor")), Path(tmp) / "reviews")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse((Path(tmp) / "reviews").exists())

    def test_bad_input_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = run(data(item("blocker", failure="")), Path(tmp) / "reviews")
            self.assertEqual(done.returncode, 2)
            self.assertFalse((Path(tmp) / "reviews").exists())

    def test_two_reviews_of_one_target_keep_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reviews"
            first = data(item("blocker"))
            second = dict(first, commit="fff9999")
            run(first, out)
            run(second, out)
            run(second, out)  # the same commit again overwrites its own file
            self.assertEqual(len(list(out.glob("*.json"))), 2)

    def test_a_target_with_odd_characters_still_makes_a_plain_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reviews"
            run(data(item("blocker"), target="feat/x vs ../../etc: main"), out)
            (file,) = out.glob("*.json")
            self.assertEqual(file.parent, out)
            self.assertRegex(file.name, r"^[A-Za-z0-9._-]+$")

    def test_a_save_that_fails_never_loses_the_report_or_the_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "file"
            blocker.write_text("not a folder", encoding="utf-8")
            done = run(data(item("blocker")), blocker / "reviews")
            self.assertEqual(done.returncode, 1)
            self.assertIn("REQUEST CHANGES", done.stdout)
            self.assertIn("not saved", done.stderr)


class WiringTests(unittest.TestCase):
    def test_the_skill_says_where_a_request_changes_review_is_saved(self):
        text = " ".join((REVIEW / "SKILL.md").read_text(encoding="utf-8").split())
        self.assertIn(DEFAULT_DIR, text)
        self.assertIn(ENV, text)

    def test_the_command_and_readme_report_the_saved_file(self):
        command = " ".join((PLUGIN / "commands" / "review.md").read_text(encoding="utf-8").split())
        self.assertIn(DEFAULT_DIR, command)
        self.assertIn(DEFAULT_DIR, " ".join((PLUGIN / "README.md").read_text(encoding="utf-8").split()))

    def test_the_command_may_still_not_edit_code_or_tickets(self):
        command = (PLUGIN / "commands" / "review.md").read_text(encoding="utf-8")
        self.assertIn("never edit, commit or push code", command.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
