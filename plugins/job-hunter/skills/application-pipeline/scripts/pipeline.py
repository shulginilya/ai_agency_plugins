#!/usr/bin/env python3
"""Track opportunities in a markdown table, with follow-ups that come due.

Usage:
    python scripts/pipeline.py init
    python scripts/pipeline.py list [--stage applied] [--track contract]
    python scripts/pipeline.py add --company Acme --role "Senior AI Engineer" \
        --track contract --source freelancermap --link https://... [--next "send proposal" --due 2026-09-10]
    python scripts/pipeline.py move Acme --to screening [--next "prep call" --due 2026-09-12]
    python scripts/pipeline.py due [--as-of 2026-09-06] [--stale-days 10]

The file is a plain markdown table so it stays readable and diffable in a repo.
Dates are ISO and compared as dates, never guessed from prose: "next week" is
not a due date this script will invent for you.

Every write backs the file up to <file>.bak first and refuses to touch a file
whose table it cannot parse — a tracker that silently eats an entry is worse
than no tracker.

Exit codes:
    0   ok, and for `due`: nothing is overdue
    1   `due` found something that needs action today
    2   unusable: no pipeline file, malformed table, or bad arguments
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path(".jobhunt/pipeline.md")
STAGES = ["sourced", "applied", "screening", "interview", "offer", "closed"]
COLUMNS = ["Company", "Role", "Track", "Stage", "Source", "Updated", "Next action", "Due", "Link"]

HEADER = (
    "# Pipeline\n\n"
    "Stages: " + " → ".join(STAGES) + "\n\n"
    "| " + " | ".join(COLUMNS) + " |\n"
    "| " + " | ".join(["---"] * len(COLUMNS)) + " |\n"
)


def today() -> dt.date:
    return dt.date.today()


def parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("%s must be an ISO date like 2026-09-10, got %r" % (field, value))


def split_row(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError("no pipeline at %s — run `pipeline.py init` first" % path)
    rows: List[Dict[str, str]] = []
    seen_header = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip().startswith("|"):
            continue
        cells = split_row(line)
        if not seen_header:
            if [c.lower() for c in cells] != [c.lower() for c in COLUMNS]:
                raise ValueError(
                    "line %d: table header is %s, expected %s" % (number, cells, COLUMNS)
                )
            seen_header = True
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        if len(cells) != len(COLUMNS):
            raise ValueError(
                "line %d: %d columns, expected %d — fix the row or the table is unreliable"
                % (number, len(cells), len(COLUMNS))
            )
        rows.append(dict(zip(COLUMNS, cells)))
    if not seen_header:
        raise ValueError("%s has no pipeline table" % path)
    return rows


def write(path: Path, rows: List[Dict[str, str]]) -> None:
    if path.is_file():
        shutil.copyfile(str(path), str(path) + ".bak")
    body = "".join(
        "| " + " | ".join((row.get(column, "") or "").replace("|", "\\|") for column in COLUMNS) + " |\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + body, encoding="utf-8")


def find(rows: List[Dict[str, str]], needle: str) -> List[int]:
    lowered = needle.strip().lower()
    exact = [i for i, row in enumerate(rows) if row["Company"].lower() == lowered]
    if exact:
        return exact
    return [i for i, row in enumerate(rows) if lowered in (row["Company"] + " " + row["Role"]).lower()]


def cmd_init(args, path: Path) -> int:
    if path.is_file():
        sys.stderr.write("%s already exists\n" % path)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER, encoding="utf-8")
    print("wrote %s" % path)
    return 0


def cmd_list(args, path: Path) -> int:
    rows = read(path)
    if args.stage:
        rows = [r for r in rows if r["Stage"].lower() == args.stage.lower()]
    if args.track:
        rows = [r for r in rows if r["Track"].lower() == args.track.lower()]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("nothing in the pipeline matches")
        return 0
    width = max(len(r["Company"]) for r in rows)
    for row in rows:
        print("%-*s  %-10s  %-10s  %s" % (
            width, row["Company"], row["Stage"], row["Due"] or "-", row["Next action"] or "-"))
    return 0


def cmd_add(args, path: Path) -> int:
    rows = read(path)
    if find(rows, args.company) and not args.allow_duplicate:
        sys.stderr.write(
            "%s is already in the pipeline; use `move`, or pass --allow-duplicate\n" % args.company
        )
        return 2
    if args.due:
        parse_date(args.due, "--due")
    rows.append({
        "Company": args.company, "Role": args.role, "Track": args.track,
        "Stage": args.stage, "Source": args.source or "", "Updated": today().isoformat(),
        "Next action": args.next or "", "Due": args.due or "", "Link": args.link or "",
    })
    write(path, rows)
    print("added %s — %s (%s)" % (args.company, args.role, args.stage))
    return 0


def cmd_move(args, path: Path) -> int:
    rows = read(path)
    matches = find(rows, args.company)
    if not matches:
        sys.stderr.write("no entry matching %r\n" % args.company)
        return 2
    if len(matches) > 1:
        sys.stderr.write(
            "%r matches %d entries: %s — be more specific\n"
            % (args.company, len(matches), ", ".join(rows[i]["Company"] for i in matches))
        )
        return 2
    if args.to not in STAGES:
        sys.stderr.write("unknown stage %r; choose one of %s\n" % (args.to, ", ".join(STAGES)))
        return 2
    if args.due:
        parse_date(args.due, "--due")
    row = rows[matches[0]]
    was = row["Stage"]
    row["Stage"] = args.to
    row["Updated"] = today().isoformat()
    if args.next is not None:
        row["Next action"] = args.next
    if args.due is not None:
        row["Due"] = args.due
    if args.to == "closed" and args.next is None:
        row["Next action"] = ""
        row["Due"] = ""
    write(path, rows)
    print("%s: %s -> %s" % (row["Company"], was, args.to))
    return 0


def due_report(rows: List[Dict[str, str]], as_of: dt.date, stale_days: int = 10,
               within: int = 3) -> Dict[str, Any]:
    """Bucket open rows by what they need. The single home for this rule: the
    CLI, the SessionStart hook and the MCP server all call it rather than each
    deciding for itself what 'stale' means."""
    overdue, upcoming, stale, undated = [], [], [], []

    for row in rows:
        if row["Stage"].lower() == "closed":
            continue
        if row["Due"]:
            try:
                due = parse_date(row["Due"], "Due")
            except ValueError:
                undated.append(dict(row, Why="due date is not an ISO date"))
                continue
            if due <= as_of:
                overdue.append(dict(row, Why="due %s" % row["Due"]))
            elif (due - as_of).days <= within:
                upcoming.append(dict(row, Why="due %s" % row["Due"]))
            continue
        if not row["Next action"]:
            # An open row with neither a next action nor a due date is exactly the
            # one that rots quietly. Surface it rather than letting it age out.
            undated.append(dict(row, Why="no next action set"))
            continue
        if row["Updated"]:
            try:
                moved = parse_date(row["Updated"], "Updated")
            except ValueError:
                undated.append(dict(row, Why="updated date is not an ISO date"))
                continue
            if (as_of - moved).days >= stale_days:
                stale.append(dict(row, Why="no movement in %d days" % (as_of - moved).days))
        else:
            undated.append(dict(row, Why="never updated"))

    return {"as_of": as_of.isoformat(), "overdue": overdue, "upcoming": upcoming,
            "stale": stale, "needs_attention": undated,
            "action_needed": bool(overdue or stale or undated)}


def cmd_due(args, path: Path) -> int:
    rows = read(path)
    as_of = parse_date(args.as_of, "--as-of") if args.as_of else today()
    report = due_report(rows, as_of, args.stale_days, args.within)
    overdue, stale = report["overdue"], report["stale"]
    undated, upcoming = report["needs_attention"], report["upcoming"]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for label, group in (("OVERDUE", overdue), ("stale", stale),
                             ("needs a date", undated), ("upcoming", upcoming)):
            for row in group:
                print("%-12s %-22s %-10s %s — %s" % (
                    label, row["Company"][:22], row["Stage"], row["Next action"] or "(no next action)", row["Why"]))
        if not (overdue or stale or undated or upcoming):
            print("nothing due as of %s" % as_of.isoformat())
    return 1 if report["action_needed"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="pipeline file (default: .jobhunt/pipeline.md)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init")

    p_list = sub.add_parser("list")
    p_list.add_argument("--stage")
    p_list.add_argument("--track")

    p_add = sub.add_parser("add")
    p_add.add_argument("--company", required=True)
    p_add.add_argument("--role", required=True)
    p_add.add_argument("--track", default="contract")
    p_add.add_argument("--stage", default="sourced", choices=STAGES)
    p_add.add_argument("--source")
    p_add.add_argument("--link")
    p_add.add_argument("--next")
    p_add.add_argument("--due")
    p_add.add_argument("--allow-duplicate", action="store_true")

    p_move = sub.add_parser("move")
    p_move.add_argument("company")
    p_move.add_argument("--to", required=True)
    p_move.add_argument("--next")
    p_move.add_argument("--due")

    p_due = sub.add_parser("due")
    p_due.add_argument("--as-of", help="treat this ISO date as today")
    p_due.add_argument("--stale-days", type=int, default=10)
    p_due.add_argument("--within", type=int, default=3, help="days ahead to call upcoming")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2

    path = Path(args.file) if args.file else DEFAULT_PATH
    handlers = {"init": cmd_init, "list": cmd_list, "add": cmd_add, "move": cmd_move, "due": cmd_due}
    try:
        return handlers[args.command](args, path)
    except (OSError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
