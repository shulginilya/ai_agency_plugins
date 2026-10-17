#!/usr/bin/env python3
"""The shared ticket-management skill: built into developer and scrum-master only, scripts that refuse safely."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _helpers  # noqa: F401
from tools.apkit.build import build
from tools.apkit.model import SourceError, load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "_shared" / "skills" / "ticket-management"
SCRIPTS = SKILL / "scripts"
CREW = ("developer", "scrum-master", "qa")  # the crew plugins that carry ticket-management
NO_TICKETS = ("designer",)

sys.path.insert(0, str(SCRIPTS))
import board  # noqa: E402
import tickets  # noqa: E402


def run(*args, **kwargs):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          check=False, **kwargs)


def write_plugin(root: Path, name: str, manifest_extra: dict, local_skill: str = "") -> Path:
    plugin = root / "plugins" / name
    plugin.mkdir(parents=True)
    manifest = {"name": name, "version": "0.1.0", "license": "MIT",
                "description": "Demo. Use when testing shared skills."}
    manifest.update(manifest_extra)
    (plugin / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    if local_skill:
        skill = plugin / "skills" / local_skill
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: %s\ndescription: x\n---\nBody.\n" % local_skill)
    return plugin


def write_shared(root: Path, name: str) -> None:
    skill = root / "plugins" / "_shared" / "skills" / name
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: %s\ndescription: Shared.\n---\nShared body.\n" % name)
    (skill / "scripts" / "tool.py").write_text("print('hi')\n")


class SharedSkillLoadingTest(unittest.TestCase):
    def test_listed_shared_skill_is_loaded_from_the_shared_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_shared(root, "common")
            plugin = load_plugin(write_plugin(root, "demo", {"shared_skills": ["common"]}, "own"))
            self.assertEqual([s.name for s in plugin.skills], ["own", "common"])
            self.assertEqual(plugin.skills[1].path, (root / "plugins" / "_shared" / "skills" / "common").resolve())

    def test_unknown_shared_skill_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(SourceError, "not found"):
                load_plugin(write_plugin(root, "demo", {"shared_skills": ["missing"]}, "own"))

    def test_shared_skill_may_not_shadow_a_local_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_shared(root, "own")
            with self.assertRaisesRegex(SourceError, "clashes"):
                load_plugin(write_plugin(root, "demo", {"shared_skills": ["own"]}, "own"))

    def test_shared_skills_must_be_a_list_of_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SourceError, "list of skill names"):
                load_plugin(write_plugin(Path(tmp), "demo", {"shared_skills": "common"}, "own"))


class CrewBundlesTest(unittest.TestCase):
    def test_every_crew_plugin_ships_ticket_management_with_its_scripts(self):
        target = {t.id: t for t in load_targets(ROOT / "targets")}["claude-code"]
        with tempfile.TemporaryDirectory() as tmp:
            for name in CREW:
                plugin = load_plugin(ROOT / "plugins" / name)
                self.assertIn("ticket-management", [s.name for s in plugin.skills], name)
                build(plugin, target, Path(tmp))
                bundle = Path(tmp) / "claude-code" / name / "skills" / "ticket-management"
                for script in ("tickets.py", "board.py"):
                    self.assertTrue((bundle / "scripts" / script).is_file(), "%s lacks %s" % (name, script))
                manifest = json.loads((Path(tmp) / "claude-code" / name / ".claude-plugin" / "plugin.json").read_text())
                self.assertNotIn("shared_skills", manifest, "source-only key must not reach the harness")

    def test_other_crew_plugins_do_not_manage_tickets(self):
        for name in NO_TICKETS:
            plugin = load_plugin(ROOT / "plugins" / name)
            self.assertNotIn("ticket-management", [s.name for s in plugin.skills], name)

    def test_developer_has_no_board_script_of_its_own(self):
        self.assertFalse((ROOT / "plugins" / "developer" / "skills" / "ship-change" / "scripts" / "board.py").exists())


class PlanTest(unittest.TestCase):
    PLAN = {"issues": [
        {"key": "epic", "title": "Session timeline view", "body": "x", "labels": ["epic"]},
        {"key": "turns", "title": "Timeline of conversation turns", "parent": "epic"},
    ]}

    def test_valid_plan_keeps_order_and_parents(self):
        items = tickets.load_plan(self.PLAN)
        self.assertEqual([i["key"] for i in items], ["epic", "turns"])
        self.assertEqual(items[1]["parent"], "epic")

    def test_parent_must_come_first(self):
        plan = {"issues": list(reversed(self.PLAN["issues"]))}
        with self.assertRaisesRegex(tickets.InputError, "earlier issue"):
            tickets.load_plan(plan)

    def test_duplicate_keys_titles_and_unknown_fields_are_refused(self):
        for bad, pattern in (
            ({"issues": [{"key": "a", "title": "A"}, {"key": "a", "title": "B"}]}, "reuses key"),
            ({"issues": [{"key": "a", "title": "A"}, {"key": "b", "title": "A"}]}, "repeats the title"),
            ({"issues": [{"key": "a", "title": "A", "assignee": "me"}]}, "unknown keys"),
            ({"issues": []}, "at least one"),
        ):
            with self.assertRaisesRegex(tickets.InputError, pattern):
                tickets.load_plan(bad)

    def test_assignees_are_a_list_of_logins(self):
        items = tickets.load_plan({"issues": [{"key": "a", "title": "A", "assignees": ["@me"]}]})
        self.assertEqual(items[0]["assignees"], ["@me"])
        with self.assertRaisesRegex(tickets.InputError, "assignees"):
            tickets.load_plan({"issues": [{"key": "a", "title": "A", "assignees": "@me"}]})

    def test_create_passes_each_assignee_to_gh(self):
        with mock.patch.object(tickets, "gh", return_value="https://github.com/me/app/issues/9\n") as gh:
            made = tickets.create_issue("T", "B", ["bug"], ["@me", "pal"])
        self.assertEqual(made["number"], 9)
        args = gh.call_args[0]
        self.assertEqual([args[i + 1] for i, a in enumerate(args) if a == "--assignee"], ["@me", "pal"])

    def test_rerun_skips_titles_that_already_exist(self):
        actions = tickets.plan_actions(tickets.load_plan(self.PLAN), {"Session timeline view": 12})
        self.assertEqual([(a["action"], a["number"]) for a in actions], [("exists", 12), ("create", None)])


class DeleteGuardTest(unittest.TestCase):
    def test_delete_needs_the_number_repeated(self):
        with self.assertRaises(tickets.InputError):
            tickets.check_delete(12, None)
        with self.assertRaises(tickets.InputError):
            tickets.check_delete(12, 13)
        tickets.check_delete(12, 12)

    def test_cli_refuses_before_touching_github(self):
        # With PATH emptied, any gh call would fail with exit 1; the guard must answer first.
        result = run(SCRIPTS / "tickets.py", "delete", "--issue", "5", env={**os.environ, "PATH": ""})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("cannot be undone", result.stderr)

    def test_status_without_project_is_bad_input(self):
        result = run(SCRIPTS / "tickets.py", "create", "--title", "x", "--status", "Backlog")
        self.assertEqual(result.returncode, 2)


class LabelTest(unittest.TestCase):
    def test_missing_labels_are_created_and_existing_ones_left_alone(self):
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args[:1] == ("api",) and len(args) == 2 and args[1].endswith("/labels/QA%20testing"):
                raise board.BoardError("gh: Not Found (HTTP 404)")
            return "{}"

        with mock.patch.dict(os.environ, {"GH_REPO": "me/app"}), mock.patch.object(tickets, "gh", fake_gh):
            created = tickets.ensure_labels(["bug", "QA testing"])
        self.assertEqual(created, ["QA testing"])
        posts = [c for c in calls if "-X" in c]
        self.assertEqual(len(posts), 1)
        self.assertIn("name=QA testing", posts[0])
        self.assertTrue(any(c[1].endswith("/labels/bug") for c in calls if len(c) == 2))

    def test_other_errors_are_not_mistaken_for_a_missing_label(self):
        with mock.patch.dict(os.environ, {"GH_REPO": "me/app"}), \
             mock.patch.object(tickets, "gh", side_effect=board.BoardError("HTTP 401: Bad credentials")):
            with self.assertRaises(board.BoardError):
                tickets.ensure_labels(["QA testing"])


class BoardTest(unittest.TestCase):
    OPTIONS = [{"id": "1", "name": "Backlog"}, {"id": "2", "name": "In progress"},
               {"id": "3", "name": "In review"}, {"id": "4", "name": "Done"}]

    def test_branch_name_from_a_conventional_title(self):
        self.assertEqual(board.branch_name(21, "feat(firstmate): install every plugin, keep the crew"),
                         "21-feat-firstmate-install-every-plugin")

    def test_branch_name_without_a_type_prefix(self):
        self.assertEqual(board.branch_name(7, "Login button is Broken!"), "7-login-button-is-broken")

    def test_status_matches_case_insensitively_then_by_substring(self):
        self.assertEqual(board.match_option(self.OPTIONS, "in REVIEW")["id"], "3")
        self.assertEqual(board.match_option(self.OPTIONS, "review")["id"], "3")

    def test_unknown_or_ambiguous_status_is_an_input_error(self):
        with self.assertRaises(board.InputError):
            board.match_option(self.OPTIONS, "qa")
        with self.assertRaises(board.InputError):
            board.match_option(self.OPTIONS, "o")  # Backlog, In progress, Done

    def test_branch_with_explicit_title_needs_no_network(self):
        result = run(SCRIPTS / "board.py", "branch", "--issue", "3", "--title", "fix: flaky login test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["branch"], "3-fix-flaky-login-test")

    def test_gh_repo_names_the_repo_without_asking_gh(self):
        with mock.patch.dict(os.environ, {"GH_REPO": "me/notes-target"}), \
             mock.patch.object(board, "gh", side_effect=AssertionError("gh must not be called")):
            self.assertEqual(board.current_repo(), {"owner": "me", "name": "notes-target"})
        with mock.patch.dict(os.environ, {"GH_REPO": "github.com/me/x"}):
            self.assertEqual(board.current_repo(), {"owner": "me", "name": "x"})
        with mock.patch.dict(os.environ, {"GH_REPO": "nonsense"}):
            with self.assertRaises(board.InputError):
                board.current_repo()

    def test_missing_gh_is_a_clean_failure(self):
        result = run(SCRIPTS / "board.py", "boards", env={**os.environ, "PATH": ""})
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh is not installed", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
