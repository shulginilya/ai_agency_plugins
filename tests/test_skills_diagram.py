#!/usr/bin/env python3
"""The skills diagram must follow the plugins: a new skill shows up, and drift fails --strict."""

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


class FakeRepoTest(unittest.TestCase):
    def run_on(self, files: dict, *args):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, files)
            write(root, {"deploy.sh": "crew_plugins=(dev)\n"})
            return generate("--plugins", str(root / "plugins"), "--deploy", str(root / "deploy.sh"),
                            "--dispatch", str(root / "none.json"), *args)

    BASE = {
        "plugins/dev/plugin.json": {"name": "dev", "version": "1.0.0", "shared_skills": ["tickets"]},
        "plugins/dev/skills/build/SKILL.md": skill("build", "Hand the ticket to the `tickets` skill."),
        "plugins/dev/commands/build.md": command("Follow the `build` skill."),
        "plugins/dev/agents/helper.md": "---\nname: helper\nmodel: claude-opus-5-5\neffort: high\n---\nHelp.\n",
        "plugins/_shared/skills/tickets/SKILL.md": skill("tickets"),
    }

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
