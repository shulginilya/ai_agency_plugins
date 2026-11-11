#!/usr/bin/env python3
"""The ticket lifecycle diagram must follow the board: a new column or card move without lifecycle.json fails here."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
FM = ROOT / "integrations" / "crew"
SCRIPT = FM / "lifecycle_diagram.py"
sys.path.insert(0, str(FM))
import lifecycle_diagram as lc  # noqa: E402

COLUMNS = ["Backlog", "In progress", "In review", "Done"]
MOVERS = {"captain": "Captain", "developer": "Developer", "qa": "QA Engineer", "github": "GitHub"}


def life(**columns_extra):
    cols = {c: {"meaning": c, "while_here": []} for c in COLUMNS}
    cols.update(columns_extra)
    return {"columns": cols, "transitions": [
        {"from": None, "to": "Backlog", "by": ["captain"]},
        {"from": "Backlog", "to": "In progress", "by": ["developer"]},
        {"from": "In progress", "to": "In review", "by": ["developer"]},
        {"from": "In review", "to": "In progress", "by": ["qa"], "back": True},
        {"from": "In review", "to": "Done", "by": ["captain", "github"]},
    ]}


def generate(*args):
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run([sys.executable, str(SCRIPT), "--out", tmp, *args], capture_output=True, text=True,
                                check=False)
        drawio = Path(tmp) / "lifecycle.drawio"
        return result, drawio.read_text(encoding="utf-8") if drawio.is_file() else ""


class InSyncTest(unittest.TestCase):
    def test_the_repo_lifecycle_has_no_drift(self):
        result, drawio = generate("--strict")
        self.assertEqual(result.returncode, 0, "update integrations/crew/lifecycle.json:\n" + result.stderr)
        for column in lc.board_columns():
            self.assertIn(column, drawio)

    def test_a_drifted_lifecycle_fails_strict_and_is_drawn_red(self):
        data = json.loads((FM / "lifecycle.json").read_text(encoding="utf-8"))
        del data["columns"]["Ready"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lifecycle.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result, drawio = generate("--strict", "--lifecycle", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("column 'Ready'", result.stderr)
        self.assertIn("Not described in lifecycle.json", drawio)


class DriftTest(unittest.TestCase):
    def setUp(self):
        lc.warnings.clear()

    def test_a_new_board_column_must_be_described(self):
        lc.check(life(), COLUMNS + ["Blocked"], {}, MOVERS)
        self.assertTrue(any("'Blocked'" in w and "does not describe" in w for w in lc.warnings), lc.warnings)

    def test_a_removed_column_must_leave_lifecycle_json(self):
        lc.check(life(Staging={"meaning": "x"}), COLUMNS, {}, MOVERS)
        self.assertTrue(any("'Staging'" in w and "no longer creates" in w for w in lc.warnings), lc.warnings)

    def test_a_card_move_a_command_makes_needs_a_transition(self):
        lc.check(life(), COLUMNS, {("qa", "Done"): ["/qa:verify"]}, MOVERS)
        self.assertTrue(any("/qa:verify" in w and "'Done' by qa" in w for w in lc.warnings), lc.warnings)

    def test_a_described_move_is_not_drift(self):
        lc.check(life(), COLUMNS, {("qa", "In progress"): ["/qa:verify"], ("developer", "In review"): ["/d:ship"]},
                 MOVERS)
        self.assertEqual(lc.warnings, [])

    def test_unknown_movers_and_columns_in_transitions(self):
        data = life()
        data["transitions"] += [{"from": "In review", "to": "Shipped", "by": ["qa"]},
                                {"from": "Backlog", "to": "In progress", "by": ["intern"]}]
        drawable = lc.check(data, COLUMNS, {}, MOVERS)
        self.assertTrue(any("Shipped" in w for w in lc.warnings))
        self.assertTrue(any("unknown mover 'intern'" in w for w in lc.warnings))
        self.assertNotIn("Shipped", [t["to"] for t in drawable])

    def test_a_pending_column_needs_no_way_in_or_out(self):
        lc.check(life(Staging={"meaning": "x", "workflow_pending": True}), COLUMNS[:-1] + ["Staging", "Done"], {},
                 MOVERS)
        self.assertEqual(lc.warnings, [])
        lc.check(life(Staging={"meaning": "x"}), COLUMNS[:-1] + ["Staging", "Done"], {}, MOVERS)
        self.assertIn("nothing moves a card into 'Staging'", lc.warnings)

    def test_a_column_nothing_reaches_or_leaves(self):
        data = life()
        data["transitions"] = [t for t in data["transitions"] if t["to"] != "Done"]
        lc.check(data, COLUMNS, {}, MOVERS)
        self.assertIn("nothing moves a card into 'Done'", lc.warnings)
        self.assertIn("nothing moves a card forward out of 'In review'", lc.warnings, "a way back is not a way on")


class MovesTest(unittest.TestCase):
    def test_moves_are_read_from_command_lines(self):
        text = "\n".join([
            "1. Then run `board.py move` to put the card in In review.",
            '   - accept: `python x/board.py move --project <N> --issue <n> --status "Ready for Merge" --create-column`',
            "   `tickets.py create --title T --project N --status Backlog`",
            "   `tickets.py create --title T --project N`",
            "   `board.py move --project <B> --issue <I> --status <S>`",
        ])
        self.assertEqual(lc.moves_in(text, "In review"), ["In review", "Ready for Merge", "Backlog"])

    def test_the_bare_move_default_comes_from_board_py(self):
        self.assertEqual(lc.default_move_column(), "In review")


class CiTest(unittest.TestCase):
    def test_ci_regenerates_the_diagram_on_main_and_keeps_it_off_branches(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        guard = ci.split("generated-files:")[1].split("publish:")[0]
        for name in ("team", "lifecycle", "skills"):
            self.assertIn(f"python integrations/crew/{name}_diagram.py", ci)
            self.assertIn(f"git add docs/crew/{name}.drawio", ci)
            # a diagram main does not have yet is untracked after regeneration: it must still be committed
            self.assertIn(f"git ls-files --others --exclude-standard -- docs/crew/{name}.drawio", ci)
            self.assertIn(f"docs/crew/{name}.drawio", guard)


if __name__ == "__main__":
    unittest.main()
