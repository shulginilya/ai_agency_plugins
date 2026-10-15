#!/usr/bin/env python3
"""The build must produce what each harness actually reads — and say what it dropped."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit import frontmatter
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent


class BuildTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dist = Path(cls._tmp.name)
        cls.plugin = load_plugin(ROOT / "plugins" / "scrum-master")
        cls.targets = {t.id: t for t in load_targets(ROOT / "targets")}
        cls.results = {
            target_id: build(cls.plugin, target, cls.dist)
            for target_id, target in cls.targets.items()
        }

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def out(self, target_id: str) -> Path:
        return self.results[target_id].root


class EveryTargetTest(BuildTestCase):
    def test_every_target_gets_every_skill(self):
        for target_id in self.targets:
            with self.subTest(target=target_id):
                skills = self.out(target_id) / "skills"
                self.assertTrue((skills / "backlog-refinement" / "SKILL.md").is_file())
                self.assertTrue((skills / "sprint-planning" / "SKILL.md").is_file())

    def test_skill_scripts_travel_with_the_skill(self):
        for target_id in self.targets:
            with self.subTest(target=target_id):
                script = (
                    self.out(target_id)
                    / "skills"
                    / "backlog-refinement"
                    / "scripts"
                    / "ready.py"
                )
                self.assertTrue(script.is_file(), "a skill's own scripts must ship everywhere")

    def test_emitted_skills_keep_only_spec_frontmatter(self):
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        for target_id in self.targets:
            with self.subTest(target=target_id):
                text = (self.out(target_id) / "skills" / "backlog-refinement" / "SKILL.md").read_text()
                meta, _ = frontmatter.parse(text)
                self.assertEqual(set(meta) - allowed, set())

    def test_no_portable_placeholder_survives_the_build(self):
        for target_id in self.targets:
            for path in self.out(target_id).rglob("*"):
                if not path.is_file() or path.suffix not in (".md", ".json", ".toml"):
                    continue
                if path.name == "INSTALL.md":
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for token in ("{{ARGS}}", "{{PLUGIN_ROOT}}", "{{SOURCE}}"):
                    self.assertNotIn(token, text, "%s left %s in %s" % (target_id, token, path))


class ClaudeCodeTest(BuildTestCase):
    def test_bundle_is_a_complete_plugin(self):
        out = self.out("claude-code")
        manifest = json.loads((out / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "scrum-master")
        self.assertEqual(manifest["hooks"], "./hooks/hooks.json")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertTrue((out / "hooks" / "hooks.json").is_file())
        self.assertTrue((out / "agents" / "story-splitter.md").is_file())
        self.assertTrue((out / "commands" / "refine.md").is_file())
        self.assertTrue((out / "scripts" / "sprint_context.py").is_file())

    def test_mcp_server_ships_with_the_bundle_it_points_at(self):
        out = self.out("claude-code")
        config = json.loads((out / ".mcp.json").read_text())
        args = config["mcpServers"]["scrum-master"]["args"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", args[-1])
        self.assertTrue(
            (out / "mcp" / "server.py").is_file(),
            "the bundle declares an MCP server, so it must contain one",
        )

    def test_commands_use_the_claude_argument_placeholder(self):
        text = (self.out("claude-code") / "commands" / "refine.md").read_text()
        self.assertIn("$ARGUMENTS", text)


class DegradationTest(BuildTestCase):
    def test_agents_become_skills_where_subagents_do_not_exist(self):
        for target_id in ("codex", "cursor", "gemini-cli", "agents"):
            with self.subTest(target=target_id):
                skill = self.out(target_id) / "skills" / "story-splitter" / "SKILL.md"
                self.assertTrue(skill.is_file())
                self.assertIn("no subagent format", skill.read_text())

    def test_opencode_keeps_agents_as_agents(self):
        self.assertTrue((self.out("opencode") / "agent" / "story-splitter.md").is_file())
        self.assertFalse((self.out("opencode") / "skills" / "story-splitter").exists())

    def test_hooks_are_dropped_loudly_not_silently(self):
        for target_id in ("codex", "cursor", "gemini-cli", "opencode", "agents"):
            with self.subTest(target=target_id):
                skipped = dict(self.results[target_id].skipped)
                self.assertIn("hooks", skipped)
                self.assertTrue(skipped["hooks"].strip())
                self.assertIn("hooks", (self.out(target_id) / "INSTALL.md").read_text())

    def test_generic_target_drops_commands(self):
        self.assertIn("commands", dict(self.results["agents"].skipped))
        self.assertFalse((self.out("agents") / "commands").exists())


class McpDialectTest(BuildTestCase):
    def test_cursor_uses_the_standard_shape(self):
        config = json.loads((self.out("cursor") / "mcp.json").read_text())
        self.assertIn("scrum-master", config["mcpServers"])

    def test_opencode_uses_its_own_shape(self):
        config = json.loads((self.out("opencode") / "opencode.json").read_text())
        entry = config["mcp"]["scrum-master"]
        self.assertEqual(entry["type"], "local")
        self.assertIsInstance(entry["command"], list)
        self.assertTrue(entry["enabled"])

    def test_codex_gets_a_toml_snippet_to_merge(self):
        text = (self.out("codex") / "mcp" / "codex.config.toml").read_text()
        self.assertIn("[mcp_servers.scrum-master]", text)
        self.assertIn("Merge into", text)

    def test_loose_targets_point_at_a_server_that_exists(self):
        config = json.loads((self.out("cursor") / "mcp.json").read_text())
        server = Path(config["mcpServers"]["scrum-master"]["args"][-1])
        self.assertTrue(server.is_file(), "loose targets must reference the real source path")


class CommandDialectTest(BuildTestCase):
    def test_gemini_commands_are_toml_with_its_placeholder(self):
        text = (self.out("gemini-cli") / "commands" / "refine.toml").read_text()
        self.assertTrue(text.startswith("description = "))
        self.assertIn('prompt = """', text)
        self.assertIn("{{args}}", text)

    def test_codex_prompts_are_plain_markdown(self):
        text = (self.out("codex") / "prompts" / "refine.md").read_text()
        self.assertFalse(text.startswith("---"), "Codex prompts carry no frontmatter here")
        self.assertIn("$ARGUMENTS", text)

    def test_opencode_commands_keep_frontmatter(self):
        meta, _ = frontmatter.parse((self.out("opencode") / "command" / "refine.md").read_text())
        self.assertIn("description", meta)


class RebuildTest(BuildTestCase):
    def test_rebuilding_removes_stale_artifacts(self):
        out = self.out("cursor")
        stale = out / "skills" / "ghost-skill"
        stale.mkdir(parents=True, exist_ok=True)
        (stale / "SKILL.md").write_text("---\nname: ghost-skill\n---\n")
        build(self.plugin, self.targets["cursor"], self.dist)
        self.assertFalse(stale.exists(), "a rebuild must not leave deleted skills behind")


if __name__ == "__main__":
    unittest.main(verbosity=2)
