#!/usr/bin/env python3
"""Smoke tests: the review command takes a PR link as well as a PR number."""

from __future__ import annotations

import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
COMMAND = PLUGIN / "commands" / "review.md"
SKILL = PLUGIN / "skills" / "typescript-review" / "SKILL.md"
README = PLUGIN / "README.md"
URL = "https://github.com/<owner>/<repo>/pull/<N>"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def header(key: str) -> str:
    for line in read(COMMAND).split("---", 2)[1].splitlines():
        if line.startswith(key + ":"):
            return line
    raise AssertionError(key)


def step(n: int) -> str:
    text = read(COMMAND)
    return flat(text[text.index("\n%d. " % n):text.index("\n%d. " % (n + 1))])


class PrLinkTests(unittest.TestCase):
    def test_the_hint_and_description_name_the_pr_link(self):
        self.assertIn("PR link", header("argument_hint"))
        self.assertIn("PR link", header("description"))

    def test_step_one_reads_a_pr_url_and_reduces_it_to_its_number(self):
        one = step(1)
        self.assertIn(URL, one)
        self.assertIn("a PR link", one)
        self.assertIn("number", one)

    def test_a_link_to_another_repository_stops_before_any_checkout(self):
        one = step(1)
        self.assertIn("gh repo view --json nameWithOwner", one)
        self.assertIn("another repository", one)
        self.assertLess(one.index("another repository"), one.index("gh pr checkout"))

    def test_a_link_that_is_not_a_pr_is_never_taken_for_a_base_ref(self):
        one = step(1)
        self.assertIn("any other URL", one)
        self.assertIn("not a base ref", one)

    def test_post_applies_to_a_link_as_to_a_number(self):
        self.assertIn("PR number or link", step(1))
        self.assertIn("PR number or link", step(6))

    def test_the_skill_and_readme_say_a_link_works(self):
        self.assertIn("PR link", flat(read(SKILL)))
        self.assertIn("PR link", flat(read(README)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
