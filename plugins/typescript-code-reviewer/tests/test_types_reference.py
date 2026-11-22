#!/usr/bin/env python3
"""Smoke tests for the types reference: Cursor's TypeScript best practices as checks, and the earlier checks kept."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REVIEW = PLUGIN / "skills" / "typescript-review"
TYPES = REVIEW / "references" / "types.md"
SOURCE = "https://github.com/cursor/plugins/tree/main/pstack/skills/typescript-best-practices"
BASE = "https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/"
PATTERNS = "references/patterns.md#"
CITE = re.compile(r"\[`([a-z-]+)`\]\((" + re.escape(BASE) + r"[^)]*)\)")
RULES = "How a practice becomes a finding"
NOT_FINDINGS = "Not findings"
BULLET = re.compile(r"^\s*([-*+]|\d+\.)\s")

# The guide's 16 rules (the SKILL.md table) and where each is explained, so none is dropped silently
# and each link goes to its own section. `real-tests` and `structured-telemetry` have no patterns section.
GUIDE = {
    "discriminated-unions": PATTERNS + "discriminated-unions",
    "branded-types": PATTERNS + "branded-types",
    "constructive-modeling": PATTERNS + "constructive-modeling",
    "simplest-total-type": PATTERNS + "simplest-total-type",
    "unknown-over-any": PATTERNS + "unknown-over-any",
    "schemas-before-guards": PATTERNS + "schemas-before-hand-rolled-guards",
    "no-as-casts": PATTERNS + "no-as-casts",
    "narrowing-hierarchy": PATTERNS + "narrowing-hierarchy",
    "type-guards": PATTERNS + "type-guards",
    "exhaustiveness": PATTERNS + "exhaustiveness",
    "satisfies-over-as": PATTERNS + "satisfies-over-as",
    "boundary-validation": PATTERNS + "boundary-validation",
    "schema-derived-types": PATTERNS + "schema-derived-types",
    "object-args": PATTERNS + "object-args",
    "real-tests": "SKILL.md",
    "structured-telemetry": "SKILL.md",
}

# The checks the earlier types.md carried: one phrase per check, found in that check only.
KEPT = (
    "`await res.json() as User`", "`as` casts and `as unknown as`", "**Non-null `!`.**", "**`any` leaking.**",
    "**Type guards that lie.**", "`@ts-ignore` / `@ts-expect-error`", "**Declaration files.**",
    "a member added later falls through silently", "narrowed on the wrong field", "`status === 'canceled'`",
    "`Partial<T>` passed where `T` is expected", "explicit `undefined` wipes the default",
    "`record[key]` is `T`, never", "`Object.keys(obj)` is `string[]`", "`Array.prototype.find`, `.at()`, `.pop()`",
    "Numeric `enum`s accept any number", "without `import type`", "ESM vs CommonJS", "Path aliases (`@/x`)",
    "A changed exported type, interface or function signature is a contract",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def frontmatter(text: str) -> dict:
    out = {}
    for line in text.split("---", 2)[1].splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def sections(text: str) -> dict:
    out = {}
    for chunk in text.split("\n## ")[1:]:
        title, _, body = chunk.partition("\n")
        out[title.strip()] = body
    return out


def bullets(body: str) -> list:
    """The list items of a section body, each with its wrapped continuation lines joined."""
    items = []
    for line in body.splitlines():
        if BULLET.match(line):
            items.append(line)
        elif items and line.strip():
            items[-1] += " " + line.strip()
    return items


def check_lines(text: str) -> list:
    """Every check: a list item outside the rules and not-findings sections."""
    return [item for title, body in sections(text).items() if title not in (RULES, NOT_FINDINGS)
            for item in bullets(body)]


def check_for(text: str, rule: str) -> str:
    found = [line for line in check_lines(text) if "[`%s`]" % rule in line]
    assert len(found) == 1, (rule, len(found))
    return flat(found[0])


def cited(text: str) -> set:
    return {m.group(1) for m in CITE.finditer(text)}


class TypesReferenceTests(unittest.TestCase):
    def setUp(self):
        self.text = read(TYPES)

    def test_the_guide_its_author_and_its_license_are_credited_up_front(self):
        intro = self.text.split("\n## ", 1)[0]
        for phrase in (SOURCE, "Cursor", "Lauren Tan", "MIT"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, intro)

    def test_a_citation_links_to_the_section_of_the_rule_it_names(self):
        found = list(CITE.finditer(self.text))
        self.assertGreaterEqual(len(found), 16)
        for m in found:
            with self.subTest(rule=m.group(1)):
                self.assertIn(m.group(1), GUIDE)
                self.assertEqual(m.group(2), BASE + GUIDE[m.group(1)])

    def test_every_link_into_the_guide_is_a_citation_the_tests_can_read(self):
        self.assertEqual(self.text.count(BASE), len(CITE.findall(self.text)))

    def test_every_rule_of_the_guide_is_a_check_or_not_a_finding_never_both(self):
        checked = cited("\n".join(check_lines(self.text)))
        dropped = cited(sections(self.text)[NOT_FINDINGS])
        self.assertEqual(sorted(set(GUIDE) - checked - dropped), [], "rules left out")
        self.assertEqual(sorted(checked & dropped), [], "rules both checked and not findings")

    def test_only_the_check_sections_cite_rules(self):
        self.assertNotIn(BASE, self.text.split("\n## ", 1)[0])
        self.assertNotIn(BASE, sections(self.text)[RULES])

    def test_the_earlier_checks_are_all_kept_each_once(self):
        body = flat(self.text)
        for phrase in KEPT:
            with self.subTest(check=phrase):
                self.assertEqual(body.count(phrase), 1)

    def test_the_bar_for_a_finding_is_the_bug_not_the_preference(self):
        rules = flat(sections(self.text)[RULES])
        for phrase in ("failure scenario", "A design preference is never a finding", "the repository's own schema library",
                       "never ask for a new dependency", "TypeScript 4.9", "package.json", "blocker", "major", "minor"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules)

    def test_the_report_example_of_the_earlier_file_is_kept(self):
        self.assertIn("`/api/user` returns `{ user: null }` for a deleted account", flat(self.text))


class AccuracyTests(unittest.TestCase):
    """Checks whose plain wording would have filed false findings or demanded the wrong fix."""

    def setUp(self):
        self.text = read(TYPES)

    def test_a_forged_brand_is_the_finding_not_the_absence_of_one(self):
        check = check_for(self.text, "branded-types")
        self.assertIn("input as AgentId", check)
        self.assertIn("verifies", check)
        self.assertIn("a call that swaps them", check)

    def test_a_non_empty_type_is_not_requested_where_every_operation_is_total(self):
        check = check_for(self.text, "simplest-total-type")
        self.assertIn("[T, ...T[]]", check)
        self.assertIn("every operation on it is total", check)

    def test_the_schema_check_asks_for_no_new_dependency(self):
        check = check_for(self.text, "schemas-before-guards")
        self.assertIn("`z.infer`", check)
        self.assertIn("`z.ZodType<User>`", check)
        self.assertIn("do not ask for a new dependency", check)

    def test_a_type_that_merely_could_be_derived_is_not_a_finding(self):
        self.assertIn("merely could be derived is not a finding", check_for(self.text, "schema-derived-types"))

    def test_satisfies_is_gated_on_the_typescript_version(self):
        check = check_for(self.text, "satisfies-over-as")
        self.assertIn("4.9", check)
        self.assertIn("`config.cols` is `undefined` at run time", check)

    def test_exhaustiveness_names_the_never_idiom_and_what_silently_happens(self):
        check = check_for(self.text, "exhaustiveness")
        self.assertIn("const _exhaustive: never = x", check)
        self.assertIn("statement `switch`", check)

    def test_persisted_data_is_versioned_and_parsed_defensively(self):
        check = check_for(self.text, "boundary-validation")
        self.assertIn("try/catch", check)
        self.assertIn("Version the stored blob", check)

    def test_mocks_that_replace_the_unit_under_test_are_a_check(self):
        check = check_for(self.text, "real-tests")
        self.assertIn("as unknown as", check)
        self.assertIn("Mock what cannot run locally", check)

    def test_a_console_log_is_not_a_finding_but_a_leak_is(self):
        item = next(i for i in bullets(sections(self.text)[NOT_FINDINGS]) if "structured-telemetry" in i)
        flat_line = flat(item)
        self.assertIn("not a finding", flat_line)
        self.assertIn("secret", flat_line)

    def test_the_tests_pass_points_at_the_mock_checks(self):
        text = flat(read(REVIEW / "SKILL.md"))
        self.assertRegex(text, r"\*\*Tests\.\*\*.*references/types\.md.*[Mm]ocks")


class WiringTests(unittest.TestCase):
    def test_the_types_pass_still_loads_types_md(self):
        self.assertIn("[references/types.md](references/types.md)", read(REVIEW / "SKILL.md"))

    def test_the_review_description_stays_under_its_cap(self):
        self.assertLessEqual(len(frontmatter(read(REVIEW / "SKILL.md"))["description"]), 1024)

    def test_the_manifest_description_stays_under_its_cap(self):
        import json
        self.assertLessEqual(len(json.loads(read(PLUGIN / "plugin.json"))["description"]), 500)

    def test_the_readme_describes_the_new_types_pass(self):
        readme = flat(read(PLUGIN / "README.md"))
        self.assertIn("TypeScript best practices", readme)
        self.assertIn("pstack", readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
