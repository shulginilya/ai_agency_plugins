#!/usr/bin/env python3
"""Smoke tests for the Node.js best practices reference and how the review reaches it."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REVIEW = PLUGIN / "skills" / "typescript-review"
SKILL = REVIEW / "SKILL.md"
REFERENCE = REVIEW / "references" / "node-best-practices.md"
NODE = REVIEW / "references" / "node.md"
AGENT = PLUGIN / "agents" / "typescript-reviewer.md"
COMMAND = PLUGIN / "commands" / "review.md"
README = PLUGIN / "README.md"
SOURCE = "https://github.com/goldbergyoni/nodebestpractices"
CITE = re.compile(r"\[(\d+)\.(\d+)\]\((" + re.escape(SOURCE) + r"[^)]*)\)")
SECTION_DIRS = {"1": "projectstructre", "2": "errorhandling", "3": "codestylepractices", "4": "testingandquality",
                "5": "production", "6": "security", "7": "performance", "8": "docker"}
BULLET = re.compile(r"^\s*([-*+]|\d+\.)\s")
RULES = "How a practice becomes a finding"
NOT_FINDINGS = "Not findings"
CHANGED_PATHS = "git ls-files --others --exclude-standard"  # untracked files count, as in ts_scope.py
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


def sections(text: str) -> dict:
    """{'## ' heading: its body}, the preamble left out."""
    out = {}
    for chunk in text.split("\n## ")[1:]:
        title, _, body = chunk.partition("\n")
        out[title.strip()] = body
    return out


def checks(text: str) -> list:
    """Every list item in every section but the rules and the not-findings, whatever its marker or indent."""
    return [line for title, body in sections(text).items() if title not in (RULES, NOT_FINDINGS)
            for line in body.splitlines() if BULLET.match(line)]


def flat(text: str) -> str:
    """The text with its line wraps and indents collapsed to single spaces."""
    return " ".join(text.split())


def command_step(n: int) -> str:
    """Step n of the review command, flattened."""
    text = read(COMMAND)
    return flat(text[text.index("\n%d. " % n):text.index("\n%d. " % (n + 1))])


def cited(text: str) -> set:
    return {"%s.%s" % m.group(1, 2) for m in CITE.finditer(text)}


class CleanupTests(unittest.TestCase):
    def test_the_standalone_skill_is_gone_and_the_plugin_has_one_skill(self):
        self.assertFalse((PLUGIN / "skills" / "node-best-practices").exists())
        self.assertEqual(sorted(p.name for p in (PLUGIN / "skills").iterdir() if p.is_dir()), ["typescript-review"])

    def test_nothing_points_at_the_old_skill(self):
        scanned = set()
        for path in PLUGIN.rglob("*"):
            rel = path.relative_to(PLUGIN)  # only the plugin's own tests/ is skipped, wherever the repo lives
            if not path.is_file() or path.suffix not in (".md", ".json") or rel.parts[0] == "tests":
                continue
            scanned.add(rel.as_posix())
            with self.subTest(path=rel.as_posix()):
                text = read(path)
                self.assertNotIn("skills/node-best-practices", text)
                self.assertNotIn("references/checklist.md", text)
                self.assertNotIn("`node-best-practices`", text)  # the skill's name; the reference is node-best-practices.md
        self.assertTrue({"README.md", "plugin.json", "agents/typescript-reviewer.md", "commands/review.md",
                         "skills/typescript-review/SKILL.md"} <= scanned, scanned)

    def test_the_readme_lists_one_skill(self):
        rows = [line for line in read(README).splitlines() if line.startswith("| Skill |")]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("`typescript-review`", rows[0])


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.text = read(REFERENCE)

    def test_the_source_its_author_and_its_license_are_credited_up_front(self):
        intro = self.text.split("\n## ", 1)[0]  # the credit, not the links in the checks
        self.assertIn(SOURCE, intro)
        self.assertIn("Yoni Goldberg", intro)
        self.assertIn("CC BY-SA 4.0", intro)

    def test_only_the_check_sections_cite_practices(self):
        # a check written in the preamble or the rules section would escape every check test
        self.assertFalse(CITE.search(self.text.split("\n## ", 1)[0]))
        self.assertFalse(CITE.search(sections(self.text)[RULES]))

    def test_the_change_rule_puts_all_of_existing_code_in_scope_when_there_is_no_change(self):
        rule = next(b for b in sections(self.text)[RULES].split("\n- ") if "The change, not the codebase" in b)
        self.assertIn("every gap in the code named is in scope", " ".join(rule.split()))  # line wraps aside
        self.assertIn("Node.js best practices only", self.text.split("\n## ", 1)[0])

    def test_the_rules_that_turn_a_practice_into_a_finding_came_along(self):
        rules = sections(self.text)[RULES]
        for phrase in ("failure scenario", "blocker", "major", "minor", "The change, not the codebase",
                       "The guide lags the runtime"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules)

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

    def test_any_list_marker_counts_as_a_check_outside_the_rules_and_not_findings(self):
        text = ("# t\n\n- preamble\n\n## %s\n\n- rule\n\n## A\n\n- one\n* two\n  - three\n1. four\nprose\n\n"
                "## %s\n- x\n" % (RULES, NOT_FINDINGS))
        self.assertEqual(len(checks(text)), 4)

    def test_every_section_of_the_guide_that_shows_in_code_is_covered(self):
        numbers = {m.group(1) for line in checks(self.text) for m in CITE.finditer(line)}
        self.assertTrue({"2", "3", "4", "5", "6", "7", "8"} <= numbers, numbers)

    def test_practices_that_a_diff_cannot_show_are_listed_as_not_findings(self):
        self.assertTrue({"3.3", "3.6", "6.21"} <= cited(sections(self.text)[NOT_FINDINGS]))

    def test_a_practice_is_never_both_a_check_and_not_a_finding(self):
        checked = cited("\n".join(checks(self.text)))
        dropped = cited(sections(self.text)[NOT_FINDINGS])
        self.assertFalse(checked & dropped, checked & dropped)

    def test_lockfile_and_docker_checks_look_at_every_changed_path(self):
        for practice in ("5.4", "8.2"):
            line = next(l for l in checks(self.text) if "[%s]" % practice in l)
            with self.subTest(practice=practice):
                self.assertIn("all changed paths", line)

    def test_the_shell_form_check_flags_debian_and_clears_alpine(self):
        line = next(l for l in checks(self.text) if "[8.2]" in l)
        self.assertRegex(line, r"Debian[^.]*dash, which stays PID 1")
        self.assertRegex(line, r"Alpine[^.]*not a finding")


class WiringTests(unittest.TestCase):
    def test_the_review_skill_sends_the_node_and_tests_passes_to_it(self):
        text = read(SKILL)
        self.assertIn("references/node-best-practices.md", text)
        self.assertRegex(text, TESTS_ROUTING)
        self.assertIn("all changed paths", text)  # the node pass sees lockfiles and Dockerfiles too

    def test_a_best_practices_check_on_its_own_still_reaches_the_review_skill(self):
        description = frontmatter(read(SKILL))["description"]
        self.assertLessEqual(len(description), 1024)
        self.assertIn("Node.js best practices", description)
        self.assertIn("Node.js best practices only", read(SKILL))

    def test_a_dockerfile_only_change_of_a_node_app_is_reviewed_not_dropped(self):
        skill = read(SKILL)
        nothing = flat(skill[skill.index('"nothing to review" means'):].split("\n\n", 1)[0])
        self.assertIn("Dockerfile", nothing)
        self.assertIn("of a Node app", nothing)  # a Go service's Dockerfile is not ours to review
        self.assertIn("Node.js best practices only", nothing)
        step2 = command_step(2)
        self.assertIn("Dockerfile", step2)
        self.assertIn("of a Node app", step2)
        self.assertIn("best practices only", step2)

    def test_the_best_practices_mode_writes_its_own_report_and_skips_review_report(self):
        mode = flat(read(SKILL).split("**Node.js best practices only.**", 1)[1].split("\n\n", 1)[0])
        self.assertIn("Write the report yourself: `review_report.py` refuses", mode)
        self.assertIn("verdict", mode)
        step2 = command_step(2)
        self.assertIn("yourself", step2)
        self.assertIn("continue at step 6", step2)  # past step 5, where review_report.py would refuse it
        self.assertIn("review_report.py", command_step(5))

    def test_the_node_checklist_points_at_it(self):
        self.assertIn("(node-best-practices.md)", read(NODE))

    def test_the_reviewer_agent_reads_it(self):
        text = read(AGENT)
        self.assertIn("skills/typescript-review/references/node-best-practices.md", text)
        self.assertRegex(text, TESTS_ROUTING)
        self.assertRegex(text, r"For the node pass:\*\* the base ref and all changed paths")
        self.assertIn(CHANGED_PATHS, text)

    def test_the_command_hands_the_node_pass_every_changed_path(self):
        text = read(COMMAND)
        self.assertIn("all changed paths", text)
        self.assertIn("node-best-practices.md", text)

    def test_all_changed_paths_means_since_the_merge_base_plus_untracked_files(self):
        for path in (REFERENCE, SKILL, COMMAND, AGENT):
            with self.subTest(path=path.name):
                text = read(path)
                self.assertNotIn("git diff --name-only <base>", text)
                self.assertIn("git merge-base", text)
                self.assertIn(CHANGED_PATHS, text)

    def test_the_readme_lists_it_with_the_other_references(self):
        self.assertIn("`node-best-practices.md`", read(README))


if __name__ == "__main__":
    unittest.main(verbosity=2)
