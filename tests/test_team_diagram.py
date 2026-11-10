#!/usr/bin/env python3
"""The crew diagram must follow the crew: roster from team.json, routing from the crew-workflow skill."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CREW = ROOT / "integrations" / "crew"
SCRIPT = CREW / "team_diagram.py"
sys.path.insert(0, str(CREW))
import team_diagram as td  # noqa: E402


def generate(*args):
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run([sys.executable, str(SCRIPT), "--out", tmp, *args], capture_output=True, text=True,
                                check=False)
        drawio = Path(tmp) / "team.drawio"
        return result, drawio.read_text(encoding="utf-8") if drawio.is_file() else ""


class InSyncTest(unittest.TestCase):
    def test_the_repo_crew_has_no_drift_and_only_the_captain_leads(self):
        result, drawio = generate("--strict")
        self.assertEqual(result.returncode, 0, "fix team.json or the crew-workflow skill:\n" + result.stderr)
        self.assertIn("Crew workflow", drawio)
        self.assertNotIn("delivery contract", drawio)
        team = json.loads((CREW / "team.json").read_text(encoding="utf-8"))
        for p in team["crew"].values():
            self.assertIn(p["role"], drawio)

    def test_the_crew_is_the_crew_keys_of_team_json(self):
        team = json.loads((CREW / "team.json").read_text(encoding="utf-8"))
        self.assertEqual(td.crew_plugin_names(CREW / "team.json"), list(team["crew"]))

    def test_team_json_has_only_the_captain_above_the_crew(self):
        team = json.loads((CREW / "team.json").read_text(encoding="utf-8"))
        self.assertEqual([lead["id"] for lead in team["leads"]], ["captain"])
        roles = {"captain"} | set(team["crew"])
        self.assertLessEqual(set(team["raci"]["columns"]), roles)
        self.assertLessEqual(set(team["scenario"]["lanes"]), roles)
        self.assertLessEqual({s["lane"] for s in team["scenario"]["steps"]}, roles)
        for row in team["raci"]["rows"]:
            self.assertLessEqual(set(row) - {"activity"}, roles, row["activity"])


class RoutingTest(unittest.TestCase):
    SKILL = ("# Crew workflow\n\n## Routing\n\n"
             "- Feature, ticket or change: `/developer:implement`. Build it test-first.\n"
             "- Code review: after `/developer:ship`, `/code-reviewer:review <PR>` reads the PR.\n\n"
             "## Who moves which card\n\n- Not routing: `/qa:verify`.\n")

    def test_routing_comes_from_the_skills_routing_section_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_text(self.SKILL, encoding="utf-8")
            routes = td.routing(path)
        self.assertEqual(routes["developer"], ["Feature, ticket or change", "Code review"])
        self.assertEqual(routes["code-reviewer"], ["Code review"])
        self.assertNotIn("qa", routes)

    def test_every_crew_role_is_routed_by_the_real_skill(self):
        routes = td.routing(td.CREW_SKILL)
        team = json.loads((CREW / "team.json").read_text(encoding="utf-8"))
        for name in team["crew"]:
            self.assertTrue(routes.get(name), f"crew-workflow routes no work to {name}")


if __name__ == "__main__":
    unittest.main()
