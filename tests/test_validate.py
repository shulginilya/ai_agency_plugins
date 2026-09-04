#!/usr/bin/env python3
"""Validation must catch the mistakes that actually break a harness."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit.model import load_plugin
from tools.apkit.validate import validate_plugin

ROOT = Path(__file__).resolve().parent.parent

GOOD_DESCRIPTION = (
    "Does a specific, describable thing to a specific kind of input. "
    "Use when the user asks for exactly that."
)


def write_plugin(root: Path, name: str, skill_meta: str, skill_body: str = "Body\n") -> Path:
    plugin = root / name
    (plugin / "skills" / "demo-skill").mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": "0.1.0",
                "description": GOOD_DESCRIPTION,
                "license": "MIT",
            }
        )
    )
    (plugin / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\n%s\n---\n\n%s" % (skill_meta, skill_body)
    )
    return plugin


class ShippedPluginsTest(unittest.TestCase):
    def test_code_review_validates_strictly(self):
        plugin = load_plugin(ROOT / "plugins" / "code-review")
        report = validate_plugin(plugin, strict=True)
        self.assertTrue(
            report.ok(strict=True),
            "the reference plugin must pass --strict:\n%s"
            % "\n".join(str(f) for f in report.findings),
        )

    def test_template_has_no_errors(self):
        plugin = load_plugin(ROOT / "plugins" / "_template")
        report = validate_plugin(plugin)
        blocking = [f for f in report.errors if "name" not in f.message]
        self.assertEqual(blocking, [], "\n".join(str(f) for f in blocking))


class SkillRulesTest(unittest.TestCase):
    def _report(self, skill_meta: str, body: str = "Body\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plugin = write_plugin(Path(tmp.name), "demo-plugin", skill_meta, body)
        return validate_plugin(load_plugin(plugin))

    def test_name_must_match_directory(self):
        report = self._report("name: wrong-name\ndescription: %s" % GOOD_DESCRIPTION)
        self.assertTrue(any("must match its directory" in f.message for f in report.errors))

    def test_uppercase_name_is_rejected(self):
        report = self._report("name: Demo-Skill\ndescription: %s" % GOOD_DESCRIPTION)
        self.assertTrue(any("lowercase" in f.message for f in report.errors))

    def test_missing_description_is_an_error(self):
        report = self._report("name: demo-skill")
        self.assertTrue(any("description" in f.message for f in report.errors))

    def test_overlong_description_is_an_error(self):
        report = self._report("name: demo-skill\ndescription: %s" % ("x" * 1100))
        self.assertTrue(any("max is 1024" in f.message for f in report.errors))

    def test_non_spec_frontmatter_is_a_warning_not_an_error(self):
        report = self._report(
            "name: demo-skill\ndescription: %s\nmodel: sonnet" % GOOD_DESCRIPTION
        )
        self.assertEqual(report.errors, [])
        self.assertTrue(any("non-spec frontmatter" in f.message for f in report.warnings))

    def test_broken_relative_reference_is_an_error(self):
        report = self._report(
            "name: demo-skill\ndescription: %s" % GOOD_DESCRIPTION,
            body="See [the guide](references/MISSING.md).\n",
        )
        self.assertTrue(any("broken relative reference" in f.message for f in report.errors))

    def test_missing_trigger_clause_is_a_warning(self):
        report = self._report(
            "name: demo-skill\ndescription: A perfectly long description that "
            "nonetheless never says when to reach for it at all."
        )
        self.assertTrue(any("trigger clause" in f.message for f in report.warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
