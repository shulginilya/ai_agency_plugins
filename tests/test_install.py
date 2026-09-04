#!/usr/bin/env python3
"""Installing must land files where the harness looks, and never clobber config."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit import install
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent


class InstallTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.dist = base / "dist"
        self.project = base / "project"
        self.project.mkdir()
        self.plugin = load_plugin(ROOT / "plugins" / "code-review")
        self.targets = {t.id: t for t in load_targets(ROOT / "targets")}

    def bundle(self, target_id: str) -> Path:
        return build(self.plugin, self.targets[target_id], self.dist).root

    def install(self, target_id: str, scope: str = "project"):
        target = self.targets[target_id]
        actions = install.plan(
            target, self.plugin.name, self.bundle(target_id), scope, self.project
        )
        install.apply(actions)
        return actions


class ProjectScopeTest(InstallTestCase):
    def test_generic_target_lands_in_dot_agents(self):
        self.install("agents")
        skill = self.project / ".agents" / "skills" / "code-review" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertTrue(
            (self.project / ".agents" / "skills" / "reviewer" / "SKILL.md").is_file()
        )

    def test_cursor_project_install_covers_skills_commands_and_mcp(self):
        self.install("cursor")
        self.assertTrue((self.project / ".cursor" / "skills" / "code-review").is_dir())
        self.assertTrue((self.project / ".cursor" / "commands" / "review.md").is_file())
        config = json.loads((self.project / ".cursor" / "mcp.json").read_text())
        self.assertIn("code-review", config["mcpServers"])

    def test_claude_project_install_places_bare_skill_directories(self):
        self.install("claude-code")
        self.assertTrue((self.project / ".claude" / "skills" / "pr-audit" / "SKILL.md").is_file())
        self.assertTrue((self.project / ".claude" / "commands" / "review.md").is_file())

    def test_reinstall_is_idempotent(self):
        self.install("agents")
        first = sorted(p.name for p in (self.project / ".agents" / "skills").iterdir())
        self.install("agents")
        second = sorted(p.name for p in (self.project / ".agents" / "skills").iterdir())
        self.assertEqual(first, second)


class MergeJsonTest(InstallTestCase):
    def test_existing_config_keys_survive_and_are_backed_up(self):
        config_path = self.project / ".cursor" / "mcp.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps({"mcpServers": {"existing": {"command": "keep-me"}}, "other": True})
        )

        self.install("cursor")

        merged = json.loads(config_path.read_text())
        self.assertEqual(merged["mcpServers"]["existing"]["command"], "keep-me")
        self.assertIn("code-review", merged["mcpServers"])
        self.assertTrue(merged["other"])
        self.assertTrue(config_path.with_suffix(".json.apkit.bak").is_file())

    def test_malformed_config_is_refused_not_overwritten(self):
        config_path = self.project / ".cursor" / "mcp.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("{ this is not json")
        with self.assertRaises(install.InstallError):
            self.install("cursor")
        self.assertEqual(config_path.read_text(), "{ this is not json")


class PlanTest(InstallTestCase):
    def test_dry_run_writes_nothing(self):
        target = self.targets["agents"]
        actions = install.plan(
            target, self.plugin.name, self.bundle("agents"), "project", self.project
        )
        install.apply(actions, dry_run=True)
        self.assertFalse((self.project / ".agents").exists())

    def test_unknown_scope_is_rejected_with_the_available_ones(self):
        with self.assertRaises(install.InstallError) as caught:
            install.plan(
                self.targets["agents"], "code-review", self.bundle("agents"), "nope", self.project
            )
        self.assertIn("user", str(caught.exception))

    def test_user_scope_destinations_are_absolute(self):
        actions = install.plan(
            self.targets["codex"], "code-review", self.bundle("codex"), "user", self.project
        )
        self.assertTrue(actions)
        for action in actions:
            self.assertTrue(action.dest.is_absolute())
            self.assertNotIn("~", str(action.dest))


class LedgerTest(InstallTestCase):
    def test_uninstall_removes_what_install_recorded(self):
        ledger_root = self.project
        actions = self.install("agents")
        install.record(ledger_root, "code-review", "agents", "project", actions)

        skills = self.project / ".agents" / "skills"
        self.assertTrue(any(skills.iterdir()))

        removed = install.uninstall(ledger_root, "code-review")
        self.assertTrue(removed)
        self.assertFalse(any(skills.iterdir()))
        self.assertEqual(install.read_ledger(ledger_root)["installs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
