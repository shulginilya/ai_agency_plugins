#!/usr/bin/env python3
"""Smoke tests for the node-best-practices skill and how the review reaches it."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SKILL_DIR = PLUGIN / "skills" / "node-best-practices"
SKILL = SKILL_DIR / "SKILL.md"
CHECKLIST = SKILL_DIR / "references" / "checklist.md"
SOURCE = "https://github.com/goldbergyoni/nodebestpractices"
CITE = re.compile(r"\[(\d+)\.(\d+)\]\(" + re.escape(SOURCE) + r"[^)]*\)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict:
    head = text.split("---", 2)[1]
    out = {}
    for line in head.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def checks(text: str) -> list:
    """Each check is a top-level bullet under a '## ' section, before the 'Not findings' section."""
    body = text.split("## Not findings", 1)[0]
    return [line for line in body.splitlines() if line.startswith("- ")]


class SkillTests(unittest.TestCase):
    def test_the_skill_is_named_for_its_directory_and_says_when_to_use_it(self):
        meta = frontmatter(read(SKILL))
        self.assertEqual(meta["name"], "node-best-practices")
        self.assertLessEqual(len(meta["description"]), 1024)
        self.assertIn("Use when", meta["description"])

    def test_the_source_and_its_license_are_credited(self):
        for path in (SKILL, CHECKLIST):
            with self.subTest(path=path.name):
                text = read(path)
                self.assertIn(SOURCE, text)
                self.assertIn("CC BY-SA 4.0", text)

    def test_the_skill_keeps_the_reviewers_bar(self):
        text = read(SKILL)
        self.assertIn("failure scenario", text)
        self.assertIn("references/checklist.md", text)


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.text = read(CHECKLIST)

    def test_every_check_cites_a_practice_with_a_link_to_the_source(self):
        found = checks(self.text)
        self.assertGreater(len(found), 30)
        for line in found:
            with self.subTest(check=line[:60]):
                self.assertRegex(line, CITE)

    def test_every_section_of_the_guide_that_shows_in_code_is_covered(self):
        sections = {m.group(1) for line in checks(self.text) for m in CITE.finditer(line)}
        self.assertTrue({"2", "3", "4", "5", "6", "7", "8"} <= sections, sections)

    def test_practices_that_a_diff_cannot_show_are_listed_as_not_findings(self):
        self.assertIn("## Not findings", self.text)
        rest = self.text.split("## Not findings", 1)[1]
        cited = {"%s.%s" % m.groups() for m in CITE.finditer(rest)}
        self.assertTrue({"3.3", "3.6", "6.21"} <= cited, cited)

    def test_a_practice_is_never_both_a_check_and_not_a_finding(self):
        body, rest = self.text.split("## Not findings", 1)
        checked = {"%s.%s" % m.groups() for m in CITE.finditer(body)}
        dropped = {"%s.%s" % m.groups() for m in CITE.finditer(rest)}
        self.assertFalse(checked & dropped, checked & dropped)


class WiringTests(unittest.TestCase):
    def test_the_review_skill_sends_the_node_and_tests_passes_to_it(self):
        text = read(PLUGIN / "skills" / "typescript-review" / "SKILL.md")
        self.assertIn("node-best-practices", text)

    def test_the_reviewer_agent_reads_the_checklist(self):
        text = read(PLUGIN / "agents" / "typescript-reviewer.md")
        self.assertIn("skills/node-best-practices/references/checklist.md", text)

    def test_the_node_checklist_points_at_it(self):
        self.assertIn("node-best-practices", read(PLUGIN / "skills" / "typescript-review" / "references" / "node.md"))

    def test_the_readme_lists_it(self):
        self.assertIn("node-best-practices", read(PLUGIN / "README.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
