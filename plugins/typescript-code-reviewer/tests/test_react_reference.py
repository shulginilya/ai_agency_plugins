#!/usr/bin/env python3
"""Smoke tests for the React reference: Vercel's React best practices as checks, and the correctness checks kept."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REVIEW = PLUGIN / "skills" / "typescript-review"
REACT = REVIEW / "references" / "react.md"
SOURCE = "https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices"
RULE_URL = "https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/"
CITE = re.compile(r"\[`([a-z0-9-]+)`\]\((" + re.escape(RULE_URL) + r"[^)]*)\)")
RULES = "How a practice becomes a finding"
NOT_FINDINGS = "Not findings"
BULLET = re.compile(r"^\s*([-*+]|\d+\.)\s")

# Every rule of the guide (rules/*.md at the version this file was built from), so none is dropped silently.
GUIDE = """
advanced-effect-event-deps advanced-event-handler-refs advanced-init-once advanced-use-latest
async-api-routes async-cheap-condition-before-await async-defer-await async-dependencies async-parallel
async-suspense-boundaries bundle-analyzable-paths bundle-barrel-imports bundle-conditional
bundle-defer-third-party bundle-dynamic-imports bundle-preload client-event-listeners
client-localstorage-schema client-passive-event-listeners client-swr-dedup js-batch-dom-css
js-cache-function-results js-cache-property-access js-cache-storage js-combine-iterations js-early-exit
js-flatmap-filter js-hoist-regexp js-index-maps js-length-check-first js-min-max-loop
js-request-idle-callback js-set-map-lookups js-tosorted-immutable rendering-activity
rendering-animate-svg-wrapper rendering-conditional-render rendering-content-visibility rendering-hoist-jsx
rendering-hydration-no-flicker rendering-hydration-suppress-warning rendering-resource-hints
rendering-script-defer-async rendering-svg-precision rendering-usetransition-loading rerender-defer-reads
rerender-dependencies rerender-derived-state-no-effect rerender-derived-state rerender-functional-setstate
rerender-lazy-state-init rerender-memo-with-default-value rerender-memo rerender-move-effect-to-event
rerender-no-inline-components rerender-simple-expression-in-memo rerender-split-combined-hooks
rerender-transitions rerender-use-deferred-value rerender-use-ref-transient-values server-after-nonblocking
server-auth-actions server-cache-lru server-cache-react server-dedup-props server-hoist-static-io
server-no-shared-module-state server-parallel-fetching server-parallel-nested-fetching server-serialization
""".split()

# The correctness and security checks the earlier react.md carried, which the guide does not cover: one phrase
# per check, found in that check only, so deleting the check fails the test.
KEPT = ("Rules of hooks.", "the first render's value forever (stale closure)", "Missing cleanup.", "Async races.",
        "`state.items.push(x); setState(state)`", "Props copied into state.", "Controlled to uncontrolled.",
        "Index keys on a list", "Hydration mismatch.", "Server-only code in the client bundle.",
        "without a sanitizer: stored XSS", "`javascript:` URLs run script", "Spreading untrusted objects into props",
        "no error boundary above it", "A `Suspense` boundary missing above a component that suspends",
        "submits twice on double click", "An icon-only button with no accessible name", "A clickable `div` with no role",
        "An input with no label", "Focus lost after a modal closes")


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


def checks(text: str) -> str:
    """Every list item outside the rules and not-findings sections, joined."""
    return "\n".join(line for title, body in sections(text).items() if title not in (RULES, NOT_FINDINGS)
                     for line in body.splitlines() if BULLET.match(line))


def check_lines(text: str) -> list:
    return [line for line in checks(text).splitlines()]


def check_for(text: str, rule: str) -> str:
    """The one check that cites a rule, flattened."""
    found = [line for line in check_lines(text) if "[`%s`]" % rule in line]
    assert len(found) == 1, (rule, found)
    return flat(found[0])


def cited(text: str) -> set:
    return {m.group(1) for m in CITE.finditer(text)}


class ReactReferenceTests(unittest.TestCase):
    def setUp(self):
        self.text = read(REACT)

    def test_the_guide_is_credited_up_front(self):
        intro = self.text.split("\n## ", 1)[0]
        for phrase in (SOURCE, "Vercel", "MIT"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, intro)

    def test_a_citation_links_to_the_rule_it_names(self):
        found = list(CITE.finditer(self.text))
        self.assertGreater(len(found), 40)
        for m in found:
            with self.subTest(rule=m.group(1)):
                self.assertEqual(m.group(2), RULE_URL + m.group(1) + ".md")
                self.assertIn(m.group(1), GUIDE)

    def test_every_rule_of_the_guide_is_a_check_or_not_a_finding_never_both(self):
        checked, dropped = cited(checks(self.text)), cited(sections(self.text)[NOT_FINDINGS])
        self.assertEqual(sorted(set(GUIDE) - checked - dropped), [], "rules left out")
        self.assertEqual(sorted(checked & dropped), [], "rules both checked and not findings")

    def test_only_the_check_sections_cite_rules(self):
        # any link into the guide's rules, backticked or not
        self.assertNotIn(RULE_URL, self.text.split("\n## ", 1)[0])
        self.assertNotIn(RULE_URL, sections(self.text)[RULES])

    def test_every_link_into_the_guide_is_a_citation_the_tests_can_read(self):
        self.assertEqual(self.text.count(RULE_URL), len(CITE.findall(self.text)))

    def test_the_correctness_and_security_checks_are_kept_each_in_its_own_check(self):
        lines = [flat(line) for line in check_lines(self.text)]
        for phrase in KEPT:
            with self.subTest(check=phrase):
                self.assertEqual(sum(phrase in line for line in lines), 1)

    def test_the_security_rules_of_the_guide_are_checks(self):
        body = checks(self.text)
        for rule in ("server-auth-actions", "server-no-shared-module-state", "server-serialization",
                     "client-localstorage-schema"):
            with self.subTest(rule=rule):
                self.assertIn(rule, cited(body))

    def test_the_bar_for_a_performance_finding_is_an_estimate(self):
        rules = flat(sections(self.text)[RULES])
        for phrase in ("failure scenario", "order-of-magnitude", "A rule broken with nothing measurable at stake is "
                       "not a finding.", "blocker", "data loss or corruption", "major", "a broken contract", "minor",
                       "package.json", "The change, not the codebase"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules)


class AccuracyTests(unittest.TestCase):
    """Checks whose first wording would have filed false findings."""

    def setUp(self):
        self.text = read(REACT)

    def test_barrel_imports_count_nexts_built_in_list(self):
        check = check_for(self.text, "bundle-barrel-imports")
        for phrase in ("Next.js 13.5", "built-in list", "`lucide-react`", "`@mui/material`", "`react-icons/*`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, check)

    def test_passive_listeners_leave_out_react_props_and_the_document(self):
        check = check_for(self.text, "client-passive-event-listeners")
        self.assertIn("addEventListener", check)
        self.assertIn("`onWheel` props are already passive", check)
        self.assertIn("`document`", check)

    def test_the_state_plus_effect_check_names_the_real_failure(self):
        check = check_for(self.text, "rerender-move-effect-to-event")
        self.assertNotIn("StrictMode", check)
        self.assertIn("another dependency of the effect changes", check)

    def test_a_route_loading_file_counts_as_a_suspense_boundary(self):
        self.assertIn("`loading.tsx`", check_for(self.text, "async-suspense-boundaries"))

    def test_repeated_fetches_in_one_render_are_already_deduplicated(self):
        check = check_for(self.text, "server-cache-react")
        self.assertIn("GET `fetch` calls", check)
        self.assertIn("already deduplicated", check)

    def test_non_blocking_work_uses_after_or_wait_until_not_a_dangling_promise(self):
        check = check_for(self.text, "server-after-nonblocking")
        self.assertIn("`waitUntil`", check)
        self.assertIn("long-lived server", check)
        self.assertNotIn("start them without awaiting", check)


class WiringTests(unittest.TestCase):
    def test_the_react_pass_still_loads_react_md(self):
        self.assertIn("[references/react.md](references/react.md)", read(REVIEW / "SKILL.md"))

    def test_the_review_description_names_react_performance(self):
        description = frontmatter(read(REVIEW / "SKILL.md"))["description"]
        self.assertLessEqual(len(description), 1024)
        self.assertIn("React and Next.js performance", description)

    def test_the_readme_describes_the_new_react_pass(self):
        readme = flat(read(PLUGIN / "README.md"))
        self.assertIn("Vercel", readme)
        self.assertIn("react-best-practices", readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
