#!/usr/bin/env python3
"""Smoke tests for check.py: tree comparison, versions, git sync, notes and the report."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "skills" / "plugin-freshness" / "scripts" / "check.py"
sys.path.insert(0, str(SCRIPT.parent))
import check  # noqa: E402

PLUGIN_LIST = """Synced from claude.ai:

  ❯ developer@synced
    Version: 0.1.1
    Path: /x/developer
    Status: ✘ disabled

  ❯ notes@synced
    Version: 9.0.0
    Status: ✘ disabled

  ❯ other@synced
    Version: 0.1.0
    Status: ✔ loaded

Skills-directory plugins (.claude/skills/*):

  ❯ alpha@skills-dir
    Version: 1.0.0
    Status: ✔ loaded
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


class Fixture:
    """A fake plugins repo, its build output and a skills dir holding exact copies."""

    def __init__(self, root: Path, names=("alpha", "beta")) -> None:
        self.repo = root / "repo"
        self.build = root / "build"
        self.skills = root / "skills"
        (self.repo / "tools" / "apkit").mkdir(parents=True)
        write(self.repo / "plugins" / "_template" / "plugin.json", json.dumps({"name": "_template", "version": "0.0.1"}))
        for name in names:
            write(self.repo / "plugins" / name / "plugin.json", json.dumps({"name": name, "version": "1.0.0"}))
            built = self.build / name
            write(built / ".claude-plugin" / "plugin.json", json.dumps({"name": name, "version": "1.0.0"}))
            write(built / "skills" / name / "SKILL.md", "# %s\n" % name)
            shutil.copytree(str(built), str(self.skills / name))

    def run(self, *extra: str):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = check.main([
                "--repo", str(self.repo), "--skills-dir", str(self.skills),
                "--build-dir", str(self.build), "--no-fetch", "--plugin-list-file", os.devnull, *extra,
            ])
        return code, buf.getvalue()


class TreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.a, self.b = self.tmp / "a", self.tmp / "b"
        write(self.a / "x.md", "same")
        write(self.b / "x.md", "same")

    def tearDown(self) -> None:
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_identical_trees_have_no_differences(self) -> None:
        self.assertEqual(check.compare_trees(self.a, self.b), [])

    def test_pycache_and_pyc_are_ignored(self) -> None:
        write(self.b / "scripts" / "__pycache__" / "m.cpython-310.pyc", "bytes")
        write(self.b / "stray.pyc", "bytes")
        self.assertEqual(check.compare_trees(self.a, self.b), [])

    def test_changed_extra_and_missing_files_are_listed_sorted(self) -> None:
        write(self.b / "x.md", "changed")
        write(self.b / "only_installed.md", "x")
        write(self.a / "only_built.md", "x")
        self.assertEqual(check.compare_trees(self.a, self.b), ["only_built.md", "only_installed.md", "x.md"])

    def test_paths_use_forward_slashes(self) -> None:
        write(self.a / "skills" / "s" / "SKILL.md", "a")
        write(self.b / "skills" / "s" / "SKILL.md", "b")
        self.assertEqual(check.compare_trees(self.a, self.b), ["skills/s/SKILL.md"])


class PluginListTests(unittest.TestCase):
    def test_parses_name_source_and_version(self) -> None:
        got = check.parse_plugin_list(PLUGIN_LIST)
        self.assertIn(("developer", "synced", "0.1.1"), got)
        self.assertIn(("alpha", "skills-dir", "1.0.0"), got)
        self.assertEqual(len(got), 4)

    def test_empty_output_parses_to_nothing(self) -> None:
        self.assertEqual(check.parse_plugin_list(""), [])

    def test_version_ordering(self) -> None:
        self.assertLess(check.version_key("0.1.1"), check.version_key("0.7.1"))
        self.assertLess(check.version_key("0.9.0"), check.version_key("0.10.0"))


class GitSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "--bare", str(origin))
        self.clone = self.tmp / "clone"
        other = self.tmp / "other"
        for d in (self.clone, other):
            d.mkdir()
        git(other, "init")
        write(other / "f", "1")
        git(other, "add", "f")
        git(other, "commit", "-m", "one")
        git(other, "push", str(origin), "HEAD:main")
        git(self.tmp, "clone", str(origin), str(self.clone))
        write(other / "f", "2")
        git(other, "commit", "-am", "two")
        git(other, "push", str(origin), "HEAD:main")

    def tearDown(self) -> None:
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_behind_is_counted_after_fetch(self) -> None:
        sync = check.git_sync(self.clone, fetch=True)
        self.assertEqual((sync["default"], sync["behind"], sync["ahead"]), ("main", 1, 0))

    def test_in_sync_after_pull(self) -> None:
        git(self.clone, "pull", "-q")
        sync = check.git_sync(self.clone, fetch=False)
        self.assertEqual((sync["behind"], sync["ahead"]), (0, 0))
        self.assertEqual(sync["branch"], "main")

    def test_not_a_git_repo_gives_none(self) -> None:
        self.assertIsNone(check.git_sync(self.tmp / "nowhere", fetch=False))


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.fx = Fixture(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_all_up_to_date_gives_a_table_and_verdict(self) -> None:
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertIn("| Plugin | Installed | Source | Files | Status |", out)
        self.assertIn("| alpha | 1.0.0 | 1.0.0 | identical | up to date |", out)
        self.assertIn("| beta | 1.0.0 | 1.0.0 | identical | up to date |", out)
        self.assertIn("All 2 up to date.", out)
        self.assertNotIn("_template", out)

    def test_one_plugin_installed_gives_one_row(self) -> None:
        shutil.rmtree(str(self.fx.skills / "beta"))
        code, out = self.fx.run()
        self.assertEqual(code, 0, out)
        self.assertIn("All 1 up to date.", out)
        self.assertNotIn("| beta |", out)

    def test_differing_files_make_the_plugin_stale_and_are_listed(self) -> None:
        write(self.fx.skills / "beta" / "skills" / "beta" / "SKILL.md", "edited\n")
        code, out = self.fx.run()
        self.assertEqual(code, 1, out)
        self.assertIn("| beta | 1.0.0 | 1.0.0 | differs | stale |", out)
        self.assertIn("1 of 2 stale: beta.", out)
        self.assertIn("skills/beta/SKILL.md", out)

    def test_at_most_eight_differing_files_are_listed(self) -> None:
        for i in range(10):
            write(self.fx.skills / "beta" / ("extra%d.md" % i), "x")
        _, out = self.fx.run()
        self.assertIn("extra7.md", out)
        self.assertNotIn("extra8.md", out)
        self.assertIn("and 2 more", out)

    def test_version_mismatch_shows_both_versions(self) -> None:
        write(self.fx.skills / "alpha" / ".claude-plugin" / "plugin.json", json.dumps({"name": "alpha", "version": "0.9.0"}))
        code, out = self.fx.run()
        self.assertEqual(code, 1, out)
        self.assertIn("| alpha | 0.9.0 | 1.0.0 | differs | stale |", out)

    def test_missing_installed_manifest_shows_unknown_version(self) -> None:
        os.remove(str(self.fx.skills / "alpha" / ".claude-plugin" / "plugin.json"))
        code, out = self.fx.run()
        self.assertEqual(code, 1, out)
        self.assertIn("| alpha | ? | 1.0.0 | differs | stale |", out)

    def test_not_installed_and_other_source_copies_go_under_notes(self) -> None:
        shutil.rmtree(str(self.fx.skills / "beta"))
        write(self.fx.repo / "plugins" / "developer" / "plugin.json", json.dumps({"name": "developer", "version": "0.7.1"}))
        listing = self.tmp / "list.txt"
        listing.write_text(PLUGIN_LIST, encoding="utf-8")
        _, out = self.fx.run("--plugin-list-file", str(listing))
        notes = out.split("Notes:", 1)[1]
        table = out.split("Notes:", 1)[0]
        self.assertIn("beta: in the source (1.0.0) but not installed", notes)
        self.assertIn("developer: in the source (0.7.1) but not installed", notes)
        self.assertIn("developer@synced 0.1.1 is older than the source (0.7.1)", notes)
        self.assertNotIn("other@synced", out)  # not a source plugin
        self.assertNotIn("alpha@skills-dir", out)  # the copy being checked
        self.assertNotIn("| developer |", table)

    def test_outside_the_plugins_repo_stops_without_a_table(self) -> None:
        shutil.rmtree(str(self.fx.repo / "tools"))
        code, out = self.fx.run()
        self.assertEqual(code, 2)
        self.assertIn("run it from the plugins repo", out)
        self.assertNotIn("| Plugin |", out)

    def test_out_of_sync_source_is_reported_before_the_table(self) -> None:
        sync = {"branch": "main", "default": "main", "behind": 3, "ahead": 1, "head": "abc1234"}
        out = check.render_sync(sync)
        self.assertIn("3 behind, 1 ahead of origin/main", out)
        _, full = self.fx.run()
        self.assertLess(full.index("Source:"), full.index("| Plugin |"))

    def test_other_branch_is_called_out(self) -> None:
        sync = {"branch": "feature", "default": "main", "behind": 0, "ahead": 0, "head": "abc1234"}
        self.assertIn("not main", check.render_sync(sync))

    def test_uncommitted_plugin_changes_are_called_out(self) -> None:
        sync = {"branch": "main", "default": "main", "behind": 0, "ahead": 0, "head": "abc1234", "dirty": True}
        self.assertIn("uncommitted changes under plugins/", check.render_sync(sync))
        self.assertFalse(check.sync_ok(sync))

    def test_read_only(self) -> None:
        def snapshot(root: Path):
            return sorted((str(p.relative_to(root)), p.read_bytes()) for p in root.rglob("*") if p.is_file())
        before = (snapshot(self.fx.repo), snapshot(self.fx.skills))
        self.fx.run()
        self.assertEqual(before, (snapshot(self.fx.repo), snapshot(self.fx.skills)))


if __name__ == "__main__":
    unittest.main()
