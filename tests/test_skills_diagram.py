#!/usr/bin/env python3
"""The skills diagram must follow the plugins: a new skill shows up, its links are drawn, and drift fails --strict."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
FM = ROOT / "integrations" / "firstmate"
SCRIPT = FM / "skills_diagram.py"
sys.path.insert(0, str(FM))
import skills_diagram as sd  # noqa: E402

unittest.util._MAX_LENGTH = 200  # a failed assertIn on a whole .drawio stays readable


def generate(*args):
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run([sys.executable, str(SCRIPT), "--out", tmp, *args], capture_output=True, text=True,
                                check=False)
        drawio = Path(tmp) / "skills.drawio"
        return result, drawio.read_text(encoding="utf-8") if drawio.is_file() else ""


def write(root: Path, files: dict) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf-8")


def skill(name: str, text: str = "") -> str:
    return f"---\nname: {name}\ndescription: Does {name}.\n---\n\n# {name}\n\n{text}\n"


def command(text: str, model: str = "claude-sonnet-5-5", effort: str = "medium") -> str:
    pins = (f"model: {model}\n" if model else "") + (f"effort: {effort}\n" if effort else "")
    return f"---\ndescription: A command.\n{pins}---\n\n{text}\n"


def agent(name: str, model: str = "claude-opus-5-5", effort: str = "high") -> str:
    pins = (f"model: {model}\n" if model else "") + (f"effort: {effort}\n" if effort else "")
    return f"---\nname: {name}\n{pins}---\n\nHelp.\n"


def edge(kind: str, src: str, dst: str) -> str:
    """The cell id drawio_page gives an edge of plugin 'dev' on page 1 (kind e: command->skill,
    ea: skill->subagent, ed: command->subagent)."""
    return f'id="p1_dev_{kind}_dev_{src}_dev_{dst}"'


# commands sort by file name (build c0, consult c1, follow c2); skills by the first command that loads them
BASE = {
    "plugins/dev/plugin.json": {"name": "dev", "version": "1.0.0", "shared_skills": ["tickets"]},
    "plugins/dev/skills/build/SKILL.md": skill("build", "Hand the ticket to the `tickets` skill. Spawn the `helper` "
                                                        "subagent, then the checker subagent."),
    "plugins/dev/commands/build.md": command("Follow the `build` skill."),
    "plugins/dev/agents/helper.md": agent("helper"),
    "plugins/qa/plugin.json": {"name": "qa", "version": "1.0.0"},
    "plugins/qa/agents/checker.md": agent("checker", "claude-sonnet-5-5", "medium"),
    "plugins/_shared/skills/tickets/SKILL.md": skill("tickets"),
}


class InSyncTest(unittest.TestCase):
    def test_the_repo_has_no_drift_and_every_skill_is_drawn(self):
        result, drawio = generate("--strict")
        self.assertEqual(result.returncode, 0, "fix the plugin files:\n" + result.stderr)
        for path in (ROOT / "plugins").glob("*/skills/*/SKILL.md"):
            if path.parent.parent.parent.name != "_template":
                self.assertIn(path.parent.name, drawio)
        self.assertIn("Models and effort", drawio)
        self.assertIn("crew dispatch profiles", drawio)


class CiTest(unittest.TestCase):
    def test_ci_regenerates_the_diagram_on_main_and_keeps_it_off_branches(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        main_job = ci.split("\n  marketplace:")[1].split("\n  generated-files:")[0]
        self.assertIn("run: python integrations/firstmate/skills_diagram.py", main_job)
        self.assertIn("git add docs/firstmate/skills.drawio", main_job)
        guard = ci.split("\n  generated-files:")[1].split("\n  publish:")[0]
        self.assertIn("docs/firstmate/skills.drawio", guard)


class MentionsTest(unittest.TestCase):
    def test_a_name_inside_a_longer_hyphenated_name_is_not_a_mention(self):
        self.assertEqual(sd.mentions("Run the code-reviewer agent on it.", ["reviewer"]), [])
        self.assertEqual(sd.mentions("Run the reviewer agent on it.", ["reviewer"]), ["reviewer"])


class FakeRepoTest(unittest.TestCase):
    def run_on(self, extra: dict, *args):
        files = dict(BASE, **extra)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, files)
            write(root, {"deploy.sh": "crew_plugins=(dev)\n"})
            return generate("--plugins", str(root / "plugins"), "--deploy", str(root / "deploy.sh"),
                            "--dispatch", str(root / "dispatch.json"), "--strict", *args)

    def test_skills_commands_subagents_their_models_and_every_link_are_drawn(self):
        result, drawio = self.run_on({
            "plugins/dev/commands/consult.md": command("Ask the `helper` subagent."),
            "plugins/dev/commands/follow.md": command("Follow the build skill."),
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ("/dev:build", "tickets", "helper", "Sonnet 5.5 · medium", "Opus 5.5 · high",
                     "bundled into: dev", "subagent from another plugin: checker (qa)"):
            self.assertIn(text, drawio)
        self.assertIn(edge("e", "c0", "s0"), drawio, "command -> the skill it loads")
        self.assertIn(edge("ea", "s0", "a0"), drawio, "skill -> the subagent it spawns")
        self.assertIn(edge("e", "c2", "s0"), drawio, "'the build skill' names it too")
        # helper is already reached through the build skill, so consult's arrow is the only command -> subagent one
        self.assertNotIn("_ed_", drawio)
        result, drawio = self.run_on({"plugins/dev/skills/build/SKILL.md": skill("build", "Use `tickets` skill."),
                                      "plugins/dev/commands/consult.md": command("Ask the `helper` subagent.")})
        self.assertIn(edge("ed", "c1", "a0"), drawio, "command -> the subagent it spawns directly")

    def test_each_kind_of_drift_fails_strict_and_is_drawn_red(self):
        result, drawio = self.run_on({
            "plugins/dev/plugin.json": {"name": "dev", "version": "1.0.0", "shared_skills": ["gone"]},
            "plugins/dev/commands/stray.md": command("Do something.", model=""),
            "plugins/dev/commands/typo.md": command("Follow the `build` skill.", effort="hihg"),
            "plugins/dev/agents/loose.md": agent("loose", model=""),
        })
        self.assertEqual(result.returncode, 1)
        for msg in ("/dev:stray names no skill or subagent", "/dev:stray pins no model",
                    "subagent dev:loose pins no model", "/dev:typo pins effort 'hihg'",
                    "lists shared skill 'gone'", "uses shared skill 'tickets', which dev/plugin.json does not list"):
            self.assertIn(msg, result.stderr)
        self.assertIn("Drift", drawio)
        self.assertIn("hihg", drawio.split('name="Models and effort"')[1], "an unknown effort is still drawn")

    def test_a_script_named_by_a_command_links_only_the_skill_that_holds_it(self):
        result, drawio = self.run_on({
            "plugins/dev/skills/report/SKILL.md": skill("report"),
            "plugins/dev/skills/report/scripts/report.py": "print('x')\n",
            "plugins/dev/skills/other/SKILL.md": skill("other"),
            "plugins/dev/skills/other/scripts/other.py": "print('y')\n",
            "plugins/dev/commands/report.md": command("Run `python scripts/report.py --json`."),
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        # skills: build s0, report s1 (loaded by c1), other s2 (loaded by nothing)
        self.assertIn(edge("e", "c1", "s1"), drawio)
        self.assertNotIn(edge("e", "c1", "s2"), drawio)

    def test_a_shared_skill_used_only_through_its_script_must_be_listed(self):
        result, _ = self.run_on({
            "plugins/_shared/skills/board/SKILL.md": skill("board"),
            "plugins/_shared/skills/board/scripts/board.py": "print('z')\n",
            "plugins/dev/skills/build/SKILL.md": skill("build", "Hand it to `tickets`. Run "
                                                                "`python ../board/scripts/board.py move`."),
        })
        self.assertEqual(result.returncode, 1)
        self.assertIn("build (dev) uses shared skill 'board'", result.stderr)

    def test_what_a_bundled_shared_skill_hands_off_to_must_be_listed_too(self):
        result, _ = self.run_on({
            "plugins/_shared/skills/tickets/SKILL.md": skill("tickets", "File cards with the `cards` skill."),
            "plugins/_shared/skills/cards/SKILL.md": skill("cards"),
        })
        self.assertEqual(result.returncode, 1)
        self.assertIn("shared skill tickets (dev) uses shared skill 'cards'", result.stderr)

    def test_a_dispatch_rule_naming_a_missing_command_fails_and_profiles_are_drawn(self):
        rules = {"rules": [{"when": "Run /dev:gone or /dev:build.", "use": {"model": "claude-opus-5-5",
                                                                           "effort": "high"}}],
                 "default": {"model": "claude-sonnet-5-5", "effort": "medium"}}
        result, drawio = self.run_on({"dispatch.json": rules})
        self.assertEqual(result.returncode, 1)
        self.assertIn("crew-dispatch.json names /dev:gone", result.stderr)
        self.assertNotIn("names /dev:build", result.stderr)
        self.assertIn("crew dispatch profiles", drawio)
        self.assertIn("names: /dev:gone, /dev:build", drawio)


if __name__ == "__main__":
    unittest.main()
