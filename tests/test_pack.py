#!/usr/bin/env python3
"""An archive is only useful if the harness recognises what is inside it.

The failure this guards against is silent: a host app handed an archive whose
manifest is one directory down ignores it without saying why.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit import pack
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent


class PackTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.dist = base / "dist"
        self.out = base / "out"
        self.plugin = load_plugin(ROOT / "plugins" / "code-review")
        self.targets = {t.id: t for t in load_targets(ROOT / "targets")}

    def pack(self, target_id: str) -> pack.PackResult:
        target = self.targets[target_id]
        bundle = build(self.plugin, target, self.dist).root
        return pack.pack_bundle(bundle, target, self.plugin.name, self.plugin.version, self.out)


class ArchiveLayoutTest(PackTestCase):
    def test_contents_sit_at_the_archive_root(self):
        members = pack.archive_members(self.pack("claude-code").path)
        self.assertIn(".claude-plugin/plugin.json", members)
        for member in members:
            self.assertFalse(
                member.startswith("code-review/"),
                "archive wraps its contents in a directory: %s" % member,
            )

    def test_skills_and_agents_survive_the_round_trip(self):
        members = pack.archive_members(self.pack("claude-code").path)
        self.assertTrue(any(m.startswith("skills/") for m in members))
        self.assertTrue(any(m.startswith("agents/") for m in members))

    def test_junk_files_are_left_out(self):
        target = self.targets["claude-code"]
        bundle = build(self.plugin, target, self.dist).root
        (bundle / ".DS_Store").write_text("junk", encoding="utf-8")
        (bundle / "__pycache__").mkdir(exist_ok=True)
        (bundle / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
        result = pack.pack_bundle(bundle, target, self.plugin.name, self.plugin.version, self.out)
        members = pack.archive_members(result.path)
        self.assertNotIn(".DS_Store", members)
        self.assertFalse(any(m.startswith("__pycache__/") for m in members))


class NamingTest(PackTestCase):
    def test_claude_code_gets_the_plugin_extension(self):
        self.assertTrue(self.pack("claude-code").path.name.endswith(".plugin"))

    def test_other_harnesses_get_a_plain_zip(self):
        self.assertTrue(self.pack("cursor").path.name.endswith(".zip"))

    def test_name_carries_plugin_and_version(self):
        result = self.pack("claude-code")
        self.assertEqual(
            result.path.name, "code-review-%s.plugin" % self.plugin.version
        )

    def test_archives_land_under_the_requested_directory(self):
        self.assertEqual(self.pack("claude-code").path.parent, self.out)


class RefusalTest(PackTestCase):
    def test_unbuilt_bundle_is_refused_with_the_path_it_looked_at(self):
        target = self.targets["claude-code"]
        with self.assertRaises(pack.PackError) as caught:
            pack.pack_bundle(self.dist / "nope", target, "nope", "0.1.0", self.out)
        self.assertIn("nope", str(caught.exception))

    def test_missing_manifest_is_refused_rather_than_shipped(self):
        target = self.targets["claude-code"]
        bundle = build(self.plugin, target, self.dist).root
        (bundle / ".claude-plugin" / "plugin.json").unlink()
        with self.assertRaises(pack.PackError):
            pack.pack_bundle(bundle, target, self.plugin.name, self.plugin.version, self.out)

    def test_empty_bundle_is_refused(self):
        target = self.targets["claude-code"]
        empty = self.dist / "empty"
        empty.mkdir(parents=True)
        with self.assertRaises(pack.PackError):
            pack.pack_bundle(empty, target, "empty", "0.1.0", self.out)


class TargetMetadataTest(unittest.TestCase):
    def test_every_target_declares_an_archive_suffix(self):
        for target in load_targets(ROOT / "targets"):
            self.assertTrue(target.archive_suffix.startswith("."), target.id)

    def test_every_target_says_what_to_do_with_the_archive(self):
        for target in load_targets(ROOT / "targets"):
            self.assertTrue(target.archive_note, "%s has no archive note" % target.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
