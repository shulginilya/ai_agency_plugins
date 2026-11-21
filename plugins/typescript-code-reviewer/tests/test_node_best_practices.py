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
CITE = re.compile(r"\[(\d+)\.(\d+)\]\((" + re.escape(SOURCE) + r"[^)]*)\)")
SECTION_DIRS = {"1": "projectstructre", "2": "errorhandling", "3": "codestylepractices", "4": "testingandquality",
                "5": "production", "6": "security", "7": "performance", "8": "docker"}
BULLET = re.compile(r"^\s*([-*+]|\d+\.)\s")
TESTS_ROUTING = re.compile(r"tests pass[^.]*Testing section", re.S)


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
    """Every list item under a '## ' section before 'Not findings', whatever its marker or indent."""
    body = text.split("## Not findings", 1)[0].split("\n## ", 1)[1]
    return [line for line in body.splitlines() if BULLET.match(line)]


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
                intro = text.split("\n## ", 1)[0]  # the credit, not the links in the checks
                self.assertIn(SOURCE, intro)
                self.assertIn("CC BY-SA 4.0", intro)
                self.assertIn("Yoni Goldberg", intro)

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

    def test_a_cited_number_links_to_its_own_section_of_the_guide(self):
        for m in CITE.finditer(self.text):
            with self.subTest(practice="%s.%s" % m.group(1, 2)):
                url = m.group(3)
                if "/sections/" in url:
                    self.assertIn("/sections/%s/" % SECTION_DIRS[m.group(1)], url)
                else:
                    self.assertTrue(url.endswith("#readme"), url)

    def test_any_list_marker_counts_as_a_check(self):
        text = "# t\n\n## A\n\n- one\n* two\n  - three\n1. four\nprose\n\n## Not findings\n- x\n"
        self.assertEqual(len(checks(text)), 4)

    def test_lockfile_and_docker_checks_look_at_every_changed_path(self):
        for practice in ("5.4", "8.2"):
            line = next(l for l in checks(self.text) if "[%s]" % practice in l)
            with self.subTest(practice=practice):
                self.assertIn("all changed paths", line)

    def test_every_section_of_the_guide_that_shows_in_code_is_covered(self):
        sections = {m.group(1) for line in checks(self.text) for m in CITE.finditer(line)}
        self.assertTrue({"2", "3", "4", "5", "6", "7", "8"} <= sections, sections)

    def test_practices_that_a_diff_cannot_show_are_listed_as_not_findings(self):
        self.assertIn("## Not findings", self.text)
        rest = self.text.split("## Not findings", 1)[1]
        cited = {"%s.%s" % m.group(1, 2) for m in CITE.finditer(rest)}
        self.assertTrue({"3.3", "3.6", "6.21"} <= cited, cited)

    def test_a_practice_is_never_both_a_check_and_not_a_finding(self):
        body, rest = self.text.split("## Not findings", 1)
        checked = {"%s.%s" % m.group(1, 2) for m in CITE.finditer(body)}
        dropped = {"%s.%s" % m.group(1, 2) for m in CITE.finditer(rest)}
        self.assertFalse(checked & dropped, checked & dropped)


class WiringTests(unittest.TestCase):
    def test_the_review_skill_sends_the_node_and_tests_passes_to_it(self):
        text = read(PLUGIN / "skills" / "typescript-review" / "SKILL.md")
        self.assertIn("node-best-practices", text)
        self.assertRegex(text, TESTS_ROUTING)
        self.assertIn("all changed paths", text)  # the node pass sees lockfiles and Dockerfiles too

    def test_the_reviewer_agent_reads_the_checklist(self):
        text = read(PLUGIN / "agents" / "typescript-reviewer.md")
        self.assertIn("skills/node-best-practices/references/checklist.md", text)
        self.assertRegex(text, TESTS_ROUTING)
        self.assertIn("all changed paths", text)

    def test_the_command_hands_the_node_pass_every_changed_path(self):
        self.assertIn("all changed paths", read(PLUGIN / "commands" / "review.md"))

    def test_the_node_checklist_points_at_it(self):
        self.assertIn("node-best-practices", read(PLUGIN / "skills" / "typescript-review" / "references" / "node.md"))

    def test_the_readme_lists_it(self):
        self.assertIn("node-best-practices", read(PLUGIN / "README.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
