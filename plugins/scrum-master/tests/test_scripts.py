#!/usr/bin/env python3
"""Smoke tests for the scripts and MCP server the scrum-master plugin ships."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent
REFINEMENT_SCRIPTS = PLUGIN / "skills" / "backlog-refinement" / "scripts"
READY = REFINEMENT_SCRIPTS / "ready.py"
BACKLOG = REFINEMENT_SCRIPTS / "backlog.py"
CAPACITY = PLUGIN / "skills" / "sprint-planning" / "scripts" / "capacity.py"
SPRINT_CONTEXT = PLUGIN / "scripts" / "sprint_context.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"
CREATE_BOARD = PLUGIN.parent / "_shared" / "skills" / "board-setup" / "scripts" / "create_board.py"

sys.path.insert(0, str(REFINEMENT_SCRIPTS))
sys.path.insert(0, str(CAPACITY.parent))
import capacity  # noqa: E402
import ready  # noqa: E402

sys.path.insert(0, str(CREATE_BOARD.parent))
import create_board  # noqa: E402

READY_STORY = """As a merchant, I want to issue a partial refund so that support
stops handling them by hand.

## Acceptance criteria
- [ ] Given a settled order, when I refund 5.00 of a 20.00 order, then the
      customer is refunded 5.00 and the order shows 15.00 remaining
- [ ] Given a refund larger than the remaining balance, when I submit it, then
      it is rejected with a message naming the remaining balance
- [ ] Given an unsettled order, when I open it, then partial refund is disabled

## Out of scope
- Refunds past the 30-day window

## Notes
- Depends on: none
- Estimate: 5
"""


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


class ReadinessTest(unittest.TestCase):
    def test_a_complete_story_is_ready(self):
        report = ready.evaluate(READY_STORY, title="Partial refunds")
        self.assertTrue(report["ready"], report["gaps"])
        self.assertGreaterEqual(report["signals"]["criteria"], 3)

    def test_size_may_come_from_a_label_instead_of_the_body(self):
        without_estimate = READY_STORY.replace("- Estimate: 5\n", "")
        self.assertFalse(ready.evaluate(without_estimate)["ready"])
        self.assertTrue(ready.evaluate(without_estimate, labels=["size/M"])["ready"])

    def test_names_every_missing_piece_of_a_one_liner(self):
        report = ready.evaluate("Make search faster.", title="Search")
        codes = {gap["code"] for gap in report["gaps"]}
        self.assertFalse(report["ready"])
        self.assertEqual(codes, {"value", "criteria", "size"})
        self.assertTrue(all(gap["fix"] for gap in report["gaps"]))

    def test_an_empty_body_is_one_gap_not_five(self):
        report = ready.evaluate("   ")
        self.assertFalse(report["ready"])
        self.assertEqual([gap["code"] for gap in report["gaps"]], ["empty"])

    def test_a_tbd_blocks_readiness(self):
        report = ready.evaluate(READY_STORY + "\n- Rate limit: TBD\n")
        self.assertFalse(report["ready"])
        self.assertIn("unresolved", {gap["code"] for gap in report["gaps"]})

    def test_split_and_vagueness_signals_warn_but_do_not_block(self):
        report = ready.evaluate(READY_STORY, title="Partial refunds and refund reports")
        self.assertTrue(report["ready"], "a clumsy title is not a readiness gap")
        self.assertIn("too-big", {w["code"] for w in report["warnings"]})

        vague = ready.evaluate(READY_STORY + "\n- Make the UI more intuitive.\n")
        self.assertIn("vague", {w["code"] for w in vague["warnings"]})

    def test_cli_reads_stdin_and_emits_json(self):
        result = run([sys.executable, str(READY), "--json"], input=READY_STORY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ready"])

    def test_cli_missing_file_exits_two(self):
        result = run([sys.executable, str(READY), "--file", "/no/such/file.md"])
        self.assertEqual(result.returncode, 2)


class BacklogTest(unittest.TestCase):
    ISSUES = [
        {
            "number": 42,
            "title": "Partial refunds",
            "body": READY_STORY,
            "labels": [{"name": "feature"}],
            "milestone": {"title": "Sprint 12"},
            "assignees": [{"login": "ilya"}],
            "url": "https://example.invalid/42",
        },
        {
            "number": 43,
            "title": "Make search better",
            "body": "It should be faster.",
            "labels": [],
            "milestone": None,
            "assignees": [],
            "url": "https://example.invalid/43",
        },
    ]

    def _payload(self, directory):
        path = Path(directory) / "issues.json"
        path.write_text(json.dumps(self.ISSUES), encoding="utf-8")
        return path

    def test_assesses_each_issue_and_flattens_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                [sys.executable, str(BACKLOG), "--from-json", str(self._payload(tmp)), "--json"]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {row["number"]: row for row in json.loads(result.stdout)}
            self.assertTrue(rows[42]["ready"])
            self.assertEqual(rows[42]["labels"], ["feature"])
            self.assertEqual(rows[42]["milestone"], "Sprint 12")
            self.assertFalse(rows[43]["ready"])
            self.assertTrue(rows[43]["gaps"])

    def test_not_ready_filters_to_the_blocking_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                [
                    sys.executable, str(BACKLOG), "--from-json", str(self._payload(tmp)),
                    "--not-ready", "--json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([row["number"] for row in json.loads(result.stdout)], [43])

    def test_missing_gh_is_a_clear_exit_two_not_a_traceback(self):
        env = dict(os.environ, PATH=str(Path(sys.executable).parent))
        result = run([sys.executable, str(BACKLOG)], env=env)
        if result.returncode == 0:
            self.skipTest("gh is reachable in this environment")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(result.stderr.strip().startswith("backlog:"))

    def test_malformed_payload_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            result = run([sys.executable, str(BACKLOG), "--from-json", str(path)])
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)


class CapacityTest(unittest.TestCase):
    def test_person_day_arithmetic(self):
        result = capacity.compute(
            people=4, days=10, focus=0.7, absence={"ilya": 3, "ana": 1}, ceremonies=False
        )
        self.assertEqual(result["days"]["gross"], 40)
        self.assertEqual(result["days"]["net"], 36)
        self.assertAlmostEqual(result["days"]["focused"], 25.2, places=2)
        self.assertAlmostEqual(result["days"]["commit"], 20.16, places=2)

    def test_ceremonies_are_subtracted_by_default(self):
        result = capacity.compute(people=4, days=10)
        self.assertEqual(result["days"]["ceremonies"], 2.0)
        self.assertEqual(result["days"]["net"], 38.0)

    def test_velocity_range_is_conservative(self):
        result = capacity.compute(velocity=[21, 25, 19])
        velocity = result["velocity"]
        self.assertAlmostEqual(velocity["mean"], 21.67, places=2)
        self.assertEqual(velocity["median"], 21)
        self.assertAlmostEqual(velocity["commit_low"], 15.2, places=2)
        self.assertEqual(velocity["commit_high"], velocity["mean"])
        self.assertEqual(result["basis"], "velocity")

    def test_thin_history_and_high_focus_are_warned_about(self):
        self.assertTrue(
            any("not enough" in w for w in capacity.compute(velocity=[20])["warnings"])
        )
        self.assertTrue(
            any("focus factor" in w for w in capacity.compute(people=2, focus=0.95)["warnings"])
        )

    def test_impossible_inputs_are_errors(self):
        with self.assertRaises(capacity.CapacityError):
            capacity.compute()
        with self.assertRaises(capacity.CapacityError):
            capacity.compute(people=1, days=10, absence={"ilya": 99})
        with self.assertRaises(capacity.CapacityError):
            capacity.parse_absence("ilya-3")
        with self.assertRaises(capacity.CapacityError):
            capacity.parse_velocity("21,many")

    def test_cli_emits_json_and_reports_bad_input_as_exit_two(self):
        result = run([sys.executable, str(CAPACITY), "--velocity", "21,25,19", "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("velocity", json.loads(result.stdout))

        result = run([sys.executable, str(CAPACITY), "--days", "10"])
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


class SprintContextHookTest(unittest.TestCase):
    def test_outside_a_repository_it_is_silent_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                [sys.executable, str(SPRINT_CONTEXT)], input='{"hook_event_name":"SessionStart"}',
                cwd=tmp,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_a_malformed_event_never_fails_the_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(SPRINT_CONTEXT)], input="not json", cwd=tmp)
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)

    def test_milestone_choice_prefers_the_nearest_due_date(self):
        sys.path.insert(0, str(SPRINT_CONTEXT.parent))
        import sprint_context  # noqa: WPS433

        chosen = sprint_context.pick_milestone(
            [
                {"title": "Later", "due_on": "2026-12-01T00:00:00Z"},
                {"title": "Sooner", "due_on": "2026-09-18T00:00:00Z"},
            ]
        )
        self.assertEqual(chosen["title"], "Sooner")
        self.assertEqual(
            sprint_context.pick_milestone([{"title": "Undated"}])["title"], "Undated"
        )
        self.assertIsNone(sprint_context.pick_milestone([]))


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_and_list_tools(self):
        responses = self._rpc(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "scrum-master")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"backlog", "readiness_check", "scrum_checklist"})

    def test_readiness_check_shares_the_skill_rules(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {
                        "name": "readiness_check",
                        "arguments": {"body": READY_STORY, "title": "Partial refunds"},
                    },
                }
            ]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"], result["content"][0]["text"])
        self.assertTrue(json.loads(result["content"][0]["text"])["ready"])

    def test_readiness_check_without_a_body_is_a_tool_error(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "readiness_check", "arguments": {}},
                }
            ]
        )
        self.assertTrue(responses[0]["result"]["isError"])

    def test_checklist_tool_returns_content(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "scrum_checklist", "arguments": {"topic": "splitting"}},
                }
            ]
        )
        result = responses[0]["result"]
        self.assertFalse(result["isError"])
        self.assertIn("Splitting stories", result["content"][0]["text"])

    def test_unknown_topic_is_a_tool_error_not_a_crash(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "scrum_checklist", "arguments": {"topic": "nope"}},
                }
            ]
        )
        self.assertTrue(responses[0]["result"]["isError"])

    def test_unknown_tool_and_unknown_method_are_distinct_errors(self):
        responses = self._rpc(
            [
                {
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "does_not_exist", "arguments": {}},
                },
                {"jsonrpc": "2.0", "id": 2, "method": "does/not/exist"},
            ]
        )
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertEqual(responses[1]["error"]["code"], -32601)


class CreateBoardTest(unittest.TestCase):
    def test_default_columns_are_the_team_flow(self):
        self.assertEqual(create_board.parse_columns(None),
                         ["In Definition", "Backlog", "Ready", "In progress", "In review", "Ready for Merge", "Done"])
        self.assertEqual([o["color"] for o in create_board.column_options(create_board.parse_columns(None))],
                         ["GRAY", "GRAY", "BLUE", "YELLOW", "PURPLE", "ORANGE", "GREEN"])

    def test_github_starting_columns_keep_their_ids_on_the_new_board(self):
        self.assertEqual(create_board.keep_starting(create_board.parse_columns(None)),
                         {"Done": "Done", "Todo": "Backlog", "In Progress": "In progress"})
        self.assertEqual(create_board.keep_starting(["Todo", "Doing", "Shipped"]),
                         {"Done": "Shipped", "Todo": "Todo", "In Progress": "Doing"})
        self.assertEqual(create_board.keep_starting(["Ideas", "Building"]), {"Done": "Building", "Todo": "Ideas"})
        self.assertEqual(create_board.keep_starting(["Backlog", "Done"], ["Todo", "Done"]),
                         {"Done": "Done", "Todo": "Backlog"})

    def test_create_sends_the_starting_ids_and_reports_workflows_that_are_off(self):
        calls = []

        def fake_graphql(query, **variables):
            calls.append(query)
            if "createProjectV2" in query:
                return {"createProjectV2": {"projectV2": {"id": "P", "number": 9, "url": "https://x/9", "field": {
                    "id": "F", "options": [{"id": "t1", "name": "Todo"}, {"id": "p1", "name": "In Progress"},
                                           {"id": "d1", "name": "Done"}]}}}}
            if "updateProjectV2Field" in query:
                return {}
            return {"node": {"field": {"options": [{"name": n} for n in create_board.DEFAULT_COLUMNS]},
                             "workflows": {"nodes": [{"name": "Item closed", "enabled": True},
                                                     {"name": "Pull request merged", "enabled": False}]}}}

        with mock.patch.object(create_board, "current_repo", return_value={"owner": "me", "name": "app"}), \
             mock.patch.object(create_board, "owner_and_repo",
                               return_value={"owner_id": "O", "repo_id": "R", "boards": []}), \
             mock.patch.object(create_board, "graphql", fake_graphql):
            result = create_board.create("Demo", list(create_board.DEFAULT_COLUMNS), link=False)
        update = next(q for q in calls if "updateProjectV2Field" in q)
        self.assertIn('{id:"t1",name:"Backlog"', update)
        self.assertIn('{id:"p1",name:"In progress"', update)
        self.assertIn('{id:"d1",name:"Done"', update)
        self.assertIn('{name:"Ready",', update)
        self.assertEqual(result["workflows_off"], ["Pull request merged"])
        self.assertIn("Workflows, and enable: Pull request merged", result["to_do"])

    def test_custom_columns_keep_order_and_trim(self):
        self.assertEqual(create_board.parse_columns(" Todo , Doing,Done "), ["Todo", "Doing", "Done"])

    def test_bad_columns_are_input_errors(self):
        for text in ("Backlog,,Done", "Done,done", "Only", "A," + "x" * 60):
            with self.assertRaises(create_board.InputError, msg=text):
                create_board.parse_columns(text)

    def test_colors_follow_meaning_and_unknown_columns_are_gray(self):
        options = {o["name"]: o["color"] for o in create_board.column_options(["Ready", "In review", "Done", "Parking"])}
        self.assertEqual(options, {"Ready": "BLUE", "In review": "PURPLE", "Done": "GREEN", "Parking": "GRAY"})

    def test_an_open_board_with_the_same_title_is_a_duplicate(self):
        boards = [{"number": 1, "title": "Old", "closed": True}, {"number": 2, "title": "AI Projects", "closed": False}]
        self.assertEqual(create_board.find_duplicate(boards, "ai projects ")["number"], 2)
        self.assertIsNone(create_board.find_duplicate(boards, "old"))

    def test_dry_run_needs_no_network(self):
        result = subprocess.run([sys.executable, str(CREATE_BOARD), "--title", "Demo", "--dry-run"],
                                capture_output=True, text=True, env={**os.environ, "PATH": ""}, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["columns"]), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
