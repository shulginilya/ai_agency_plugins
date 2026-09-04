#!/usr/bin/env python3
"""Every plugin gets at least a smoke test. `apkit test` runs test_*.py here."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "skills" / "example-skill" / "scripts" / "example.py"


class ExampleScriptTest(unittest.TestCase):
    def test_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--name", "test"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hello, test", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
