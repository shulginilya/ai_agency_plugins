#!/usr/bin/env python3
"""The published index must point at bundles a consumer can actually fetch.

dist/ is gitignored, so a path source resolves only on the machine that built
it. Anything published has to name a repository and a ref instead.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit import marketplace
from tools.apkit.cli import build_parser, main
from tools.apkit.model import load_plugin

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/shulginilya/ai_agency_plugins.git"


class PluginSourceTest(unittest.TestCase):
    def test_path_mode_stays_relative_to_the_marketplace_root(self):
        self.assertEqual(
            marketplace.plugin_source("scrum-master", publish="path"),
            "./dist/claude-code/scrum-master",
        )

    def test_git_subdir_names_repo_path_and_ref(self):
        source = marketplace.plugin_source("scrum-master", publish="git-subdir", repo=REPO)
        self.assertEqual(
            source,
            {
                "source": "git-subdir",
                "url": REPO,
                "path": "claude-code/scrum-master",
                "ref": "dist",
            },
        )

    def test_git_subdir_path_carries_no_leading_dot_slash(self):
        source = marketplace.plugin_source(
            "scrum-master", publish="git-subdir", repo=REPO, source_root="./claude-code/"
        )
        self.assertEqual(source["path"], "claude-code/scrum-master")

    def test_git_subdir_without_a_repo_is_refused(self):
        with self.assertRaises(ValueError):
            marketplace.plugin_source("scrum-master", publish="git-subdir")

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            marketplace.plugin_source("scrum-master", publish="tarball")


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.plugins = [load_plugin(ROOT / "plugins" / "scrum-master")]

    def index(self, **kwargs):
        return marketplace.build_index(
            self.plugins,
            owner={"name": "Ilya Shulgin"},
            name="ai-agency",
            description="Harness-agnostic agent plugins.",
            **kwargs,
        )

    def test_entry_carries_description_and_version(self):
        entry = self.index(publish="git-subdir", repo=REPO)["plugins"][0]
        self.assertEqual(entry["name"], "scrum-master")
        self.assertTrue(entry["description"])
        self.assertTrue(entry["version"])

    def test_cli_default_mode_is_publishable(self):
        # The CLI default must be the form that survives leaving this machine:
        # a regenerated index that silently reverts to dist/ paths is the bug
        # this whole mechanism exists to prevent.
        args = build_parser().parse_args(["marketplace"])
        self.assertEqual(args.publish, "git-subdir")
        self.assertTrue(args.repo)
        entry = self.index(publish=args.publish, repo=args.repo, ref=args.ref)["plugins"][0]
        self.assertIsInstance(entry["source"], dict)
        self.assertEqual(entry["source"]["ref"], "dist")


class CommittedIndexTest(unittest.TestCase):
    """The file in the tree is what a consumer adding this repo gets."""

    def setUp(self):
        path = ROOT / marketplace.MARKETPLACE_PATH
        if not path.exists():
            self.skipTest("no committed marketplace index")
        self.index = json.loads(path.read_text(encoding="utf-8"))

    def test_no_entry_points_into_gitignored_dist(self):
        for entry in self.index["plugins"]:
            source = entry["source"]
            path = source if isinstance(source, str) else source.get("path", "")
            self.assertNotIn(
                "dist/", path, "%s points into gitignored build output" % entry["name"]
            )

    def test_every_entry_names_a_repo_and_ref(self):
        for entry in self.index["plugins"]:
            source = entry["source"]
            self.assertIsInstance(source, dict, "%s is not a fetchable source" % entry["name"])
            self.assertTrue(source.get("url"), entry["name"])
            self.assertTrue(source.get("ref"), entry["name"])


class CliTest(unittest.TestCase):
    def test_cli_writes_an_index_with_every_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            # --root writes into the real tree, so generate beside it and compare
            # against the plugin count rather than rewriting the repo's own file.
            out = Path(tmp)
            (out / ".claude-plugin").mkdir(parents=True)
            index = marketplace.build_index(
                [load_plugin(p) for p in sorted((ROOT / "plugins").iterdir())
                 if (p / "plugin.json").is_file() and p.name != "_template"],
                owner={"name": "Ilya Shulgin"},
                name="ai-agency",
                description="Harness-agnostic agent plugins.",
                publish="git-subdir",
                repo=REPO,
            )
            written = marketplace.write_index(out, index)
            reread = json.loads(written.read_text(encoding="utf-8"))
        self.assertEqual(len(reread["plugins"]), len(index["plugins"]))
        self.assertGreater(len(reread["plugins"]), 0)

    def test_marketplace_rejects_a_plugin_filter(self):
        self.assertEqual(main(["marketplace", "--plugin", "scrum-master"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
