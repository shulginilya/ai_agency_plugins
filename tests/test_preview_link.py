#!/usr/bin/env python3
"""The shared preview-link skill: a PR's link is current only when deployed from its head commit."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "_shared" / "skills" / "preview-link"
sys.path.insert(0, str(SKILL / "scripts"))
import preview_link  # noqa: E402

HEAD, OLD = "a" * 40, "b" * 40
PR = {"number": 7, "head_sha": HEAD, "head_ref": "7-feat-x", "state": "open"}


def deployment(id, sha, env="preview-pr-7", created="2026-10-23T10:00:00Z", production=False):
    return {"id": id, "sha": sha, "environment": env, "created_at": created, "production_environment": production}


def status(state, url=None, **extra):
    return dict({"state": state, "environment_url": url}, **extra)


class ChooseTest(unittest.TestCase):
    def choose(self, deployments, statuses, pr=PR):
        return preview_link.choose(pr, deployments, statuses)

    def test_the_head_commits_success_is_current(self):
        result = self.choose([deployment(1, OLD, created="2026-10-22T00:00:00Z"), deployment(2, HEAD)],
                             {1: status("success", "https://old"), 2: status("success", "https://pr-7.x.pages.dev")})
        self.assertEqual((result["state"], result["url"]), ("current", "https://pr-7.x.pages.dev"))

    def test_an_older_commits_preview_is_stale_not_the_link(self):
        result = self.choose([deployment(1, OLD)], {1: status("success", "https://old")})
        self.assertEqual(result["state"], "stale")
        self.assertIn("not the head commit", result["reason"])

    def test_deploying_and_failed_heads(self):
        self.assertEqual(self.choose([deployment(2, HEAD)], {2: status("in_progress")})["state"], "pending")
        self.assertEqual(self.choose([deployment(2, HEAD)], {2: None})["state"], "pending")
        failed = self.choose([deployment(2, HEAD)], {2: status("failure", log_url="https://run/1")})
        self.assertEqual(failed["state"], "failed")
        self.assertIn("https://run/1", failed["reason"])

    def test_renders_own_environment_counts_but_production_does_not(self):
        render = self.choose([deployment(3, HEAD, env="shop-pr-7")],
                             {3: status("success", "https://shop-pr-7.onrender.com")})
        self.assertEqual(render["state"], "current")
        prod = self.choose([deployment(4, HEAD, env="production"), deployment(5, HEAD, env="live", production=True)],
                           {4: status("success", "https://shop.com"), 5: status("success", "https://shop.com")})
        self.assertEqual(prod["state"], "none")

    def test_no_deployment_and_closed_pr(self):
        self.assertIn("no deployment", self.choose([], {})["reason"])
        closed = self.choose([deployment(2, HEAD)], {2: status("inactive", "https://x")}, dict(PR, state="merged"))
        self.assertEqual(closed["state"], "none")
        self.assertIn("merged", closed["reason"])


class BundleTest(unittest.TestCase):
    def test_skill_is_spec_shaped(self):
        head = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
        self.assertIn("name: preview-link", head)
        description = next(l for l in head.splitlines() if l.startswith("description:"))
        self.assertLessEqual(len(description) - len("description: "), 1024)

    def test_devops_and_qa_ship_it_with_its_script(self):
        target = {t.id: t for t in load_targets(ROOT / "targets")}["claude-code"]
        for name in ("devops", "qa"):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                plugin = load_plugin(ROOT / "plugins" / name)
                self.assertIn("preview-link", [s.name for s in plugin.skills])
                build(plugin, target, Path(tmp))
                bundle = Path(tmp) / "claude-code" / name / "skills" / "preview-link"
                self.assertTrue((bundle / "scripts" / "preview_link.py").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
