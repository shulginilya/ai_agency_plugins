#!/usr/bin/env python3
"""Discovery is lenient, validation is strict, and the index is never scoped.

Both rules exist because of one incident: erroring on a stale cache directory
broke every unscoped command, which pushed callers to `--plugin`, and
`marketplace --plugin` silently writes an index that omits everything unnamed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401  (puts the repo root on sys.path)

from tools.apkit import cli
from tools.apkit.model import SourceError, discover, unmanifested

MANIFEST = {
    "name": "demo",
    "version": "0.1.0",
    "description": "A demo plugin. Use when exercising discovery in the tests.",
}


def make_repo(tmp: str) -> Path:
    root = Path(tmp)
    (root / "plugins" / "demo").mkdir(parents=True)
    (root / "plugins" / "demo" / "plugin.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (root / "targets").mkdir()
    return root


def add_cache_residue(root: Path, name: str) -> Path:
    """What switching branches leaves behind: caches and nothing else."""
    path = root / "plugins" / name / "tests" / "__pycache__"
    path.mkdir(parents=True)
    (path / "test_x.cpython-312.pyc").write_bytes(b"\x00")
    return root / "plugins" / name


def add_unfinished_plugin(root: Path, name: str) -> Path:
    """Real content, no manifest — somebody forgot a step."""
    path = root / "plugins" / name / "skills" / "thing"
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("---\nname: thing\ndescription: x\n---\nBody.\n", encoding="utf-8")
    return root / "plugins" / name


class DiscoveryTest(unittest.TestCase):
    def test_cache_residue_does_not_break_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            add_cache_residue(root, "debugger")
            found = [p.name for p in discover(root / "plugins")]
            self.assertEqual(found, ["demo"], "a leftover __pycache__ must not raise")

    def test_a_directory_missing_its_manifest_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            add_cache_residue(root, "debugger")
            add_unfinished_plugin(root, "forgot")

            self.assertEqual([p.name for p in discover(root / "plugins")], ["demo"])
            strays = [p.name for p in unmanifested(root / "plugins")]
            self.assertEqual(strays, ["forgot"], "cache-only dirs are residue; this one is a mistake")

    def test_the_template_is_still_skipped_unless_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            (root / "plugins" / "_template").mkdir()
            (root / "plugins" / "_template" / "plugin.json").write_text(
                json.dumps(dict(MANIFEST, name="_template")), encoding="utf-8"
            )
            self.assertEqual([p.name for p in discover(root / "plugins")], ["demo"])
            named = discover(root / "plugins", only=["_template"])
            self.assertEqual([p.name for p in named], ["_template"])


class MarketplaceScopeTest(unittest.TestCase):
    def test_marketplace_refuses_plugin_scoping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            (root / "plugins" / "other").mkdir()
            (root / "plugins" / "other" / "plugin.json").write_text(
                json.dumps(dict(MANIFEST, name="other")), encoding="utf-8"
            )
            args = cli.build_parser().parse_args(
                ["--root", str(root), "marketplace", "--plugin", "demo"]
            )
            with self.assertRaises(SourceError) as caught:
                args.func(args)
            self.assertIn("--plugin", str(caught.exception))
            self.assertFalse(
                (root / ".claude-plugin" / "marketplace.json").exists(),
                "a rejected run must not have written a partial index",
            )

    def test_unscoped_marketplace_writes_every_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            (root / "plugins" / "other").mkdir()
            (root / "plugins" / "other" / "plugin.json").write_text(
                json.dumps(dict(MANIFEST, name="other")), encoding="utf-8"
            )
            add_cache_residue(root, "debugger")
            self.assertEqual(cli.main(["--root", str(root), "marketplace"]), 0)
            index = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(p["name"] for p in index["plugins"]), ["demo", "other"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
