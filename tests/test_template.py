#!/usr/bin/env python3
"""The template is skipped by discovery, so it needs its own guard against rot."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "plugins" / "_template"


class TemplateTest(unittest.TestCase):
    def test_builds_for_every_target(self):
        plugin = load_plugin(TEMPLATE)
        with tempfile.TemporaryDirectory() as tmp:
            for target in load_targets(ROOT / "targets"):
                with self.subTest(target=target.id):
                    result = build(plugin, target, Path(tmp))
                    self.assertTrue(
                        (result.root / "skills" / "example-skill" / "SKILL.md").is_file()
                    )

    def test_its_example_script_runs(self):
        script = TEMPLATE / "skills" / "example-skill" / "scripts" / "example.py"
        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hello", result.stdout)

    def test_its_hook_never_blocks(self):
        script = TEMPLATE / "scripts" / "example_hook.py"
        for payload in ("{}", "not json", '{"tool_input": {"file_path": "/nope"}}'):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [sys.executable, str(script)],
                    input=payload,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)

    def test_documents_every_component_directory(self):
        readme = (TEMPLATE / "README.md").read_text()
        for component in ("skills/", "commands/", "agents/", "hooks/", "mcp/", "tests/"):
            self.assertIn(component, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
