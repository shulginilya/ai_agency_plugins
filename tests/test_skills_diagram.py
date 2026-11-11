#!/usr/bin/env python3
"""The skills diagram must follow the plugins: a new skill shows up, and drift fails --strict."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CREW = ROOT / "integrations" / "crew"
SCRIPT = CREW / "skills_diagram.py"


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


class InSyncTest(unittest.TestCase):
    def test_the_repo_has_no_drift_and_every_skill_is_drawn(self):
        result, drawio = generate("--strict")
        self.assertEqual(result.returncode, 0, "fix the plugin files:\n" + result.stderr)
        for path in (ROOT / "plugins").glob("*/skills/*/SKILL.md"):
            if path.parent.parent.parent.name != "_template":
                self.assertIn(path.parent.name, drawio)
        self.assertIn("Models and effort", drawio)
        self.assertNotIn("dispatch profiles", drawio)

    def test_it_reads_no_deploy_script_or_dispatch_file(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        for flag in ("--deploy", "--dispatch"):
            self.assertNotIn(flag, result.stdout)

    def test_every_crew_plugin_in_team_json_is_drawn_as_crew(self):
        team = json.loads((CREW / "team.json").read_text(encoding="utf-8"))
        _, drawio = generate()
        for name in team["crew"]:
            self.assertRegex(drawio, rf"{re.escape(name)} v[0-9.]+ · Crew")


class FakeRepoTest(unittest.TestCase):
    def run_on(self, files: dict, *args):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, files)
            if "team.json" not in files:
                write(root, {"team.json": {"crew": {"dev": {"role": "Developer"}}}})
            return generate("--plugins", str(root / "plugins"), "--team", str(root / "team.json"), *args)

    BASE = {
        "plugins/dev/plugin.json": {"name": "dev", "version": "1.0.0", "shared_skills": ["tickets"]},
        "plugins/dev/skills/build/SKILL.md": skill("build", "Hand the ticket to the `tickets` skill."),
        "plugins/dev/commands/build.md": command("Follow the `build` skill."),
        "plugins/dev/agents/helper.md": "---\nname: helper\nmodel: claude-opus-5-5\neffort: high\n---\nHelp.\n",
        "plugins/_shared/skills/tickets/SKILL.md": skill("tickets"),
    }

    def test_the_crew_comes_from_team_json(self):
        files = dict(self.BASE)
        files["plugins/ops/plugin.json"] = {"name": "ops", "version": "1.0.0"}
        files["team.json"] = {"crew": {"ops": {"role": "Ops"}}}
        result, drawio = self.run_on(files)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(drawio, r"Ops · ops v1\.0\.0 · Crew")
        self.assertRegex(drawio, r"dev v1\.0\.0 · Captain-only")

    def test_a_clean_repo_draws_skills_commands_subagents_and_their_models(self):
        result, drawio = self.run_on(self.BASE, "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ("/dev:build", "build", "tickets", "helper", "Sonnet 5.5 · medium", "Opus 5.5 · high",
                     "bundled into: dev"):
            self.assertIn(text, drawio)

    def test_drift_fails_strict_and_is_drawn_red(self):
        files = dict(self.BASE)
        files["plugins/dev/plugin.json"] = {"name": "dev", "version": "1.0.0", "shared_skills": ["gone"]}
        files["plugins/dev/commands/stray.md"] = command("Do something.", model="")
        result, drawio = self.run_on(files, "--strict")
        self.assertEqual(result.returncode, 1)
        for msg in ("/dev:stray names no skill or subagent", "/dev:stray pins no model",
                    "lists shared skill 'gone'", "uses shared skill 'tickets', which dev/plugin.json does not list"):
            self.assertIn(msg, result.stderr)
        self.assertIn("Drift", drawio)

    def test_a_script_named_by_a_command_links_it_to_the_skill_that_holds_it(self):
        files = dict(self.BASE)
        files["plugins/dev/skills/report/SKILL.md"] = skill("report")
        files["plugins/dev/skills/report/scripts/report.py"] = "print('x')\n"
        files["plugins/dev/commands/report.md"] = command("Run `python scripts/report.py --json`.")
        result, _ = self.run_on(files, "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
