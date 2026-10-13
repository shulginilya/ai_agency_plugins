#!/usr/bin/env python3
"""Smoke tests for the scripts the designer plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "ux-review" / "scripts"
CONTRAST = SCRIPTS / "contrast.py"
INVENTORY = SCRIPTS / "ui_inventory.py"

sys.path.insert(0, str(SCRIPTS))
import contrast  # noqa: E402
import ui_inventory  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, check=False)


class ContrastTest(unittest.TestCase):
    def test_known_wcag_ratios(self):
        # Reference values from the WCAG definition of relative luminance.
        self.assertAlmostEqual(contrast.ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)
        self.assertAlmostEqual(contrast.ratio((255, 255, 255), (255, 255, 255)), 1.0, places=2)
        self.assertEqual(round(contrast.ratio(contrast.parse_color("#767676"), (255, 255, 255)), 2), 4.54)

    def test_marks_use_the_unrounded_ratio(self):
        row = contrast.assess("#777777", "#ffffff")  # 4.48:1
        self.assertFalse(row["aa_normal"])
        self.assertTrue(row["aa_large"])
        self.assertTrue(row["aa_ui"])
        self.assertFalse(row["aaa_large"])

    def test_color_formats(self):
        self.assertEqual(contrast.parse_color("#abc"), (170, 187, 204))
        self.assertEqual(contrast.parse_color("rgb(10, 20, 30)"), (10, 20, 30))
        self.assertEqual(contrast.parse_color("#000000ff"), (0, 0, 0))
        self.assertEqual(contrast.parse_color("White"), (255, 255, 255))
        for bad in ("#12", "teal-ish", "#ffffff80", "rgba(0,0,0,0.5)", "rgb(300,0,0)"):
            with self.assertRaises(contrast.ColorError, msg=bad):
                contrast.parse_color(bad)

    def test_pairs_file_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairs = Path(tmp) / "pairs.txt"
            pairs.write_text("// body text\n#1c2330 #ffffff body\nrgb(119, 119, 119) #fff muted caption\n")
            result = run(CONTRAST, "--pairs", pairs, "--json")
            self.assertEqual(result.returncode, 1, "one pair fails AA normal")
            rows = json.loads(result.stdout)
            self.assertEqual([r["label"] for r in rows], ["body", "muted caption"])
        self.assertEqual(run(CONTRAST, "#000", "#fff").returncode, 0)
        self.assertEqual(run(CONTRAST, "#000").returncode, 2)


class InventoryTest(unittest.TestCase):
    def test_finds_stack_tokens_components_pages_and_theming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps(
                {"dependencies": {"next": "16", "react": "19", "tailwindcss": "4"}}))
            (root / "components.json").write_text("{}")
            (root / "app" / "sessions").mkdir(parents=True)
            (root / "app" / "page.tsx").write_text("export default function Home() {}")
            (root / "app" / "sessions" / "page.tsx").write_text("export default function S() {}")
            (root / "app" / "globals.css").write_text(
                ":root{--bg:#fff;--fg:#000;--muted:#666;--accent:#06c;--line:#ddd}\n"
                "@media (prefers-color-scheme: dark){:root{--bg:#000}}\n")
            (root / "components" / "ui").mkdir(parents=True)
            (root / "components" / "ui" / "button.tsx").write_text("export function Button() {}")
            (root / "node_modules" / "x" / "components").mkdir(parents=True)
            (root / "node_modules" / "x" / "components" / "y.tsx").write_text("")
            report = ui_inventory.inventory(root)
            self.assertEqual(report["stack"]["framework"], ["Next.js", "React"])
            self.assertIn("Tailwind CSS", report["stack"]["styling"])
            self.assertIn("shadcn/ui (components.json)", report["stack"]["library"])
            self.assertEqual(sorted(report["pages"]), ["app/page.tsx", "app/sessions/page.tsx"])
            self.assertEqual(report["components"], ["components/ui"])
            self.assertTrue(any(t.startswith("app/globals.css") for t in report["tokens"]), report["tokens"])
            self.assertIn("prefers-color-scheme media query", report["theming"])
            self.assertFalse(any("node_modules" in c for c in report["components"]))

    def test_a_repo_without_ui_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("print('hi')\n")
            result = run(INVENTORY, "--root", tmp)
            self.assertEqual(result.returncode, 2)
            self.assertIn("no UI found", result.stderr)

    def test_missing_root_is_bad_input(self):
        self.assertEqual(run(INVENTORY, "--root", "/no/such/dir").returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
