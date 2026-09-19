#!/usr/bin/env python3
"""The state of every interview loop: rounds, prep items, mock results, debriefs.

Usage:
    python scripts/prep.py init
    python scripts/prep.py add --company Acme --role "Senior AI Engineer" \
        --source jd/acme.txt --rounds recruiter-screen,live-coding,system-design
    python scripts/prep.py round --company Acme --round system-design --date 2026-09-29
    python scripts/prep.py item --company Acme --add "RAG eval story with numbers" \
        --risk high --round system-design --due 2026-09-25
    python scripts/prep.py item --company Acme --done "RAG eval"
    python scripts/prep.py mock --company Acme --round system-design --grade mixed \
        --weak "cost/latency tradeoffs;no eval plan" --strong "clear data model"
    python scripts/prep.py debrief --company Acme --round live-coding \
        --asked "LRU cache;debounce hook" --gap "froze on the follow-up" --outcome advanced
    python scripts/prep.py status
    python scripts/prep.py render

`.interview/state.json` is the source of truth and `.interview/brief.md` is
rendered from it, one way only. A journal parsed back out of prose loses an
entry eventually; a rendered one cannot.

Exit codes for `status`:
    0   clear        nothing needs action today
    1   action       something is due, overdue, or a round has passed undebriefed
    2   unusable     no state file, or a file that is not an interview-prep state
    3   undeclared   a round is scheduled with nothing prepared and no mock run --
                     readiness cannot be judged, which is a question, not a pass
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

DEFAULT_DIR = Path(".interview")
DEFAULT_PATH = DEFAULT_DIR / "state.json"
DEFAULT_BRIEF = DEFAULT_DIR / "brief.md"
KIND = "interview-prep"
IMMINENT_DAYS = 3

ROUND_TYPES = [
    "recruiter-screen", "hiring-manager", "live-coding", "take-home",
    "system-design", "behavioral", "panel", "leadership",
]
RISKS = ["high", "medium", "low"]
GRADES = ["strong", "mixed", "weak"]
ROUND_STATUS = ["scheduled", "done", "cancelled"]
OUTCOMES = ["advanced", "rejected", "waiting"]

RELATIVE = re.compile(r"(today|tomorrow|next|this)\s|\bin \d+ (day|week)", re.I)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "unnamed"


def parse_date(value: str, field: str) -> dt.date:
    value = (value or "").strip()
    if RELATIVE.search(value):
        raise ValueError(
            "%s must be an ISO date the user agreed to, not %r -- convert it and say which date you used"
            % (field, value)
        )
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("%s must be YYYY-MM-DD, got %r" % (field, value))


def split_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;\n]", value) if part.strip()]


def empty_state() -> Dict[str, Any]:
    return {"kind": KIND, "version": 1, "loops": []}


def read(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError("no state at %s -- run `prep.py init` first" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("%s is not valid JSON (%s)" % (path, exc))
    if not isinstance(data, dict) or data.get("kind") != KIND:
        raise ValueError(
            "%s is not an interview-prep state file -- refusing to overwrite it" % path
        )
    data.setdefault("loops", [])
    return data


def write(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copyfile(str(path), str(path) + ".bak")
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_loop(state: Dict[str, Any], company: str) -> Dict[str, Any]:
    wanted = slugify(company)
    for loop in state["loops"]:
        if loop["slug"] == wanted or wanted in loop["slug"]:
            return loop
    known = ", ".join(l["company"] for l in state["loops"]) or "none"
    raise ValueError("no loop for %r -- known loops: %s" % (company, known))


def new_loop(company: str, role: str, source: Optional[str], archetype: Optional[str],
             rounds: List[str], today: dt.date) -> Dict[str, Any]:
    return {
        "slug": slugify(company),
        "company": company.strip(),
        "role": role.strip(),
        "source": source or "",
        "archetype": archetype or "",
        "created": today.isoformat(),
        "rounds": [{"name": r, "date": "", "status": "scheduled", "notes": ""} for r in rounds],
        "prep": [],
        "mocks": [],
        "debriefs": [],
    }


def validate_round_name(name: str) -> str:
    name = name.strip().lower()
    if name not in ROUND_TYPES:
        raise ValueError("unknown round %r -- one of: %s" % (name, ", ".join(ROUND_TYPES)))
    return name


def _one_of(value: str, allowed: List[str], field: str) -> str:
    value = (value or "").strip().lower()
    if value not in allowed:
        raise ValueError("%s must be one of %s, got %r" % (field, ", ".join(allowed), value))
    return value


def loop_status(loop: Dict[str, Any], as_of: dt.date) -> Dict[str, Any]:
    imminent, undated, passed, unprepped = [], [], [], []
    for entry in loop["rounds"]:
        if entry["status"] != "scheduled":
            continue
        if not entry["date"]:
            undated.append(entry["name"])
            continue
        when = parse_date(entry["date"], "round date")
        delta = (when - as_of).days
        if delta < 0:
            debriefed = any(d["round"] == entry["name"] for d in loop["debriefs"])
            if not debriefed:
                passed.append("%s on %s -- debrief it or mark it done" % (entry["name"], entry["date"]))
            continue
        if delta <= IMMINENT_DAYS:
            imminent.append("%s in %d day(s), %s" % (entry["name"], delta, entry["date"]))
        mocked = any(m["round"] == entry["name"] for m in loop["mocks"])
        prepared = any(p["round"] == entry["name"] for p in loop["prep"])
        if not mocked and not prepared:
            unprepped.append(entry["name"])

    overdue, upcoming, undatedprep = [], [], []
    for item in loop["prep"]:
        if item["status"] != "open":
            continue
        if not item["due"]:
            undatedprep.append(item["item"])
            continue
        due = parse_date(item["due"], "prep due")
        delta = (due - as_of).days
        if delta < 0:
            overdue.append("%s (%s, due %s)" % (item["item"], item["risk"], item["due"]))
        elif delta <= IMMINENT_DAYS:
            upcoming.append("%s (due %s)" % (item["item"], item["due"]))

    weak = []
    for mock in loop["mocks"]:
        for point in mock["weak"]:
            weak.append("%s: %s" % (mock["round"], point))

    return {
        "company": loop["company"],
        "role": loop["role"],
        "imminent_rounds": imminent,
        "undated_rounds": undated,
        "passed_rounds": passed,
        "unprepped_rounds": unprepped,
        "overdue_prep": overdue,
        "upcoming_prep": upcoming,
        "prep_without_a_date": undatedprep,
        "open_weaknesses": weak,
        "rounds_mocked": sorted({m["round"] for m in loop["mocks"]}),
        "rounds_total": len([r for r in loop["rounds"] if r["status"] != "cancelled"]),
    }


def status_report(state: Dict[str, Any], as_of: dt.date, company: Optional[str] = None) -> Dict[str, Any]:
    loops = [find_loop(state, company)] if company else state["loops"]
    reports = [loop_status(loop, as_of) for loop in loops]
    action = any(
        r["imminent_rounds"] or r["passed_rounds"] or r["overdue_prep"]
        or r["undated_rounds"] or r["prep_without_a_date"]
        for r in reports
    )
    undeclared = [r["company"] for r in reports if r["unprepped_rounds"]]
    if undeclared:
        verdict, code = "undeclared", 3
    elif action:
        verdict, code = "action", 1
    else:
        verdict, code = "clear", 0
    return {
        "as_of": as_of.isoformat(),
        "verdict": verdict,
        "exit_code": code,
        "action_needed": action,
        "loops": reports,
    }


def render_status(report: Dict[str, Any]) -> str:
    lines = ["%s -- as of %s" % (report["verdict"].upper(), report["as_of"])]
    if not report["loops"]:
        lines.append("No loops tracked. `prep.py add --company X --role Y` starts one.")
        return "\n".join(lines)
    buckets = [
        ("passed_rounds", "Happened, not debriefed"),
        ("overdue_prep", "Overdue prep"),
        ("imminent_rounds", "Rounds within %d days" % IMMINENT_DAYS),
        ("unprepped_rounds", "Scheduled with nothing prepared and no mock"),
        ("undated_rounds", "Rounds with no date"),
        ("prep_without_a_date", "Prep with no date"),
        ("upcoming_prep", "Prep due soon"),
        ("open_weaknesses", "Weak points from mocks, still open"),
    ]
    for loop in report["loops"]:
        lines.append("")
        lines.append("## %s -- %s" % (loop["company"], loop["role"]))
        lines.append("   mocked %d of %d rounds: %s"
                     % (len(loop["rounds_mocked"]), loop["rounds_total"],
                        ", ".join(loop["rounds_mocked"]) or "none"))
        for key, label in buckets:
            for entry in loop[key]:
                lines.append("   [%s] %s" % (label, entry))
    return "\n".join(lines)


def render_brief(state: Dict[str, Any], as_of: dt.date) -> str:
    lines = ["# Interview prep", "", "Generated %s from state.json -- do not edit by hand." % as_of.isoformat()]
    for loop in state["loops"]:
        lines += ["", "## %s -- %s" % (loop["company"], loop["role"])]
        if loop["source"]:
            lines.append("Source: `%s`" % loop["source"])
        if loop["archetype"]:
            lines.append("Company type: %s" % loop["archetype"])
        lines += ["", "| Round | Date | Status | Mocked |", "| --- | --- | --- | --- |"]
        for entry in loop["rounds"]:
            mocks = [m["grade"] for m in loop["mocks"] if m["round"] == entry["name"]]
            lines.append("| %s | %s | %s | %s |" % (
                entry["name"], entry["date"] or "--", entry["status"], ", ".join(mocks) or "--"))
        open_items = [p for p in loop["prep"] if p["status"] == "open"]
        if open_items:
            lines += ["", "### Open prep"]
            for item in sorted(open_items, key=lambda p: RISKS.index(p["risk"])):
                lines.append("- **%s** %s%s%s" % (
                    item["risk"], item["item"],
                    " (%s)" % item["round"] if item["round"] else "",
                    " -- due %s" % item["due"] if item["due"] else " -- no date"))
        if loop["mocks"]:
            lines += ["", "### Mocks"]
            for mock in loop["mocks"]:
                lines.append("- %s %s -- **%s**" % (mock["date"], mock["round"], mock["grade"]))
                for point in mock["weak"]:
                    lines.append("  - weak: %s" % point)
                for point in mock["strong"]:
                    lines.append("  - strong: %s" % point)
        if loop["debriefs"]:
            lines += ["", "### Debriefs"]
            for entry in loop["debriefs"]:
                lines.append("- %s %s -- %s" % (entry["date"], entry["round"], entry["outcome"]))
                for asked in entry["asked"]:
                    lines.append("  - asked: %s" % asked)
                for gap in entry["gaps"]:
                    lines.append("  - gap: %s" % gap)
    return "\n".join(lines) + "\n"


def cmd_init(args) -> int:
    path = Path(args.file)
    if path.is_file():
        read(path)
        print("%s already exists" % path)
        return 0
    write(path, empty_state())
    print("wrote %s" % path)
    return 0


def cmd_add(args) -> int:
    path = Path(args.file)
    state = read(path)
    slug = slugify(args.company)
    if any(l["slug"] == slug for l in state["loops"]):
        raise ValueError("a loop for %s already exists -- use `round` or `item` to change it" % args.company)
    rounds = [validate_round_name(r) for r in (args.rounds or "").split(",") if r.strip()]
    state["loops"].append(new_loop(args.company, args.role, args.source, args.archetype, rounds, dt.date.today()))
    write(path, state)
    print("added %s -- %s with %d round(s)" % (args.company, args.role, len(rounds)))
    return 0


def cmd_round(args) -> int:
    path = Path(args.file)
    state = read(path)
    loop = find_loop(state, args.company)
    name = validate_round_name(args.round)
    entry = next((r for r in loop["rounds"] if r["name"] == name), None)
    if entry is None:
        entry = {"name": name, "date": "", "status": "scheduled", "notes": ""}
        loop["rounds"].append(entry)
    if args.date:
        entry["date"] = parse_date(args.date, "--date").isoformat()
    if args.status:
        entry["status"] = _one_of(args.status, ROUND_STATUS, "--status")
    if args.notes:
        entry["notes"] = args.notes
    write(path, state)
    print("%s / %s: %s %s" % (loop["company"], name, entry["status"], entry["date"] or "(no date)"))
    return 0


def cmd_item(args) -> int:
    path = Path(args.file)
    state = read(path)
    loop = find_loop(state, args.company)
    if args.done:
        needle = args.done.lower()
        hits = [p for p in loop["prep"] if needle in p["item"].lower() and p["status"] == "open"]
        if not hits:
            raise ValueError("no open prep item matching %r" % args.done)
        if len(hits) > 1:
            raise ValueError("%r matches %d open items -- be more specific" % (args.done, len(hits)))
        hits[0]["status"] = "done"
        write(path, state)
        print("done: %s" % hits[0]["item"])
        return 0
    if not args.add:
        raise ValueError("give --add <text> or --done <text>")
    item = {
        "item": args.add.strip(),
        "risk": _one_of(args.risk or "medium", RISKS, "--risk"),
        "round": validate_round_name(args.round) if args.round else "",
        "due": parse_date(args.due, "--due").isoformat() if args.due else "",
        "status": "open",
        "added": dt.date.today().isoformat(),
    }
    loop["prep"].append(item)
    write(path, state)
    print("added %s prep item to %s%s" % (item["risk"], loop["company"],
                                          " (due %s)" % item["due"] if item["due"] else " -- no date yet"))
    return 0


def cmd_mock(args) -> int:
    path = Path(args.file)
    state = read(path)
    loop = find_loop(state, args.company)
    mock = {
        "date": parse_date(args.date, "--date").isoformat() if args.date else dt.date.today().isoformat(),
        "round": validate_round_name(args.round),
        "grade": _one_of(args.grade, GRADES, "--grade"),
        "weak": split_list(args.weak),
        "strong": split_list(args.strong),
    }
    if mock["grade"] != "strong" and not mock["weak"]:
        raise ValueError("a mock graded %s must name at least one weak point (--weak)" % mock["grade"])
    loop["mocks"].append(mock)
    write(path, state)
    print("recorded %s mock for %s: %s" % (mock["round"], loop["company"], mock["grade"]))
    return 0


def cmd_debrief(args) -> int:
    path = Path(args.file)
    state = read(path)
    loop = find_loop(state, args.company)
    entry = {
        "date": parse_date(args.date, "--date").isoformat() if args.date else dt.date.today().isoformat(),
        "round": validate_round_name(args.round),
        "asked": split_list(args.asked),
        "gaps": split_list(args.gap),
        "outcome": _one_of(args.outcome or "waiting", OUTCOMES, "--outcome"),
    }
    if not entry["asked"]:
        raise ValueError("a debrief with no questions recorded teaches nothing -- pass --asked")
    loop["debriefs"].append(entry)
    for round_entry in loop["rounds"]:
        if round_entry["name"] == entry["round"] and round_entry["status"] == "scheduled":
            round_entry["status"] = "done"
    write(path, state)
    print("debriefed %s / %s: %s, %d question(s), %d gap(s)"
          % (loop["company"], entry["round"], entry["outcome"], len(entry["asked"]), len(entry["gaps"])))
    return 0


def cmd_status(args) -> int:
    path = Path(args.file)
    state = read(path)
    as_of = parse_date(args.as_of, "--as-of") if args.as_of else dt.date.today()
    report = status_report(state, as_of, args.company)
    print(json.dumps(report, indent=2) if args.json else render_status(report))
    return int(report["exit_code"])


def cmd_render(args) -> int:
    path = Path(args.file)
    state = read(path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        shutil.copyfile(str(out), str(out) + ".bak")
    out.write_text(render_brief(state, dt.date.today()), encoding="utf-8")
    print("wrote %s" % out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track interview loops, prep, mocks and debriefs.")
    parser.add_argument("--file", default=str(DEFAULT_PATH), help="state file. Default .interview/state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the state file").set_defaults(func=cmd_init)

    add = sub.add_parser("add", help="start a loop for one company")
    add.add_argument("--company", required=True)
    add.add_argument("--role", required=True)
    add.add_argument("--source", help="path or URL the description came from")
    add.add_argument("--archetype", help="big-tech, scale-up, early-startup, agency, enterprise")
    add.add_argument("--rounds", help="comma-separated round names")
    add.set_defaults(func=cmd_add)

    rnd = sub.add_parser("round", help="add or change one round")
    rnd.add_argument("--company", required=True)
    rnd.add_argument("--round", required=True)
    rnd.add_argument("--date")
    rnd.add_argument("--status", help="|".join(ROUND_STATUS))
    rnd.add_argument("--notes")
    rnd.set_defaults(func=cmd_round)

    item = sub.add_parser("item", help="add or close a prep item")
    item.add_argument("--company", required=True)
    item.add_argument("--add")
    item.add_argument("--done")
    item.add_argument("--risk", help="|".join(RISKS))
    item.add_argument("--round")
    item.add_argument("--due")
    item.set_defaults(func=cmd_item)

    mock = sub.add_parser("mock", help="record a mock round result")
    mock.add_argument("--company", required=True)
    mock.add_argument("--round", required=True)
    mock.add_argument("--grade", required=True, help="|".join(GRADES))
    mock.add_argument("--weak", help="semicolon-separated")
    mock.add_argument("--strong", help="semicolon-separated")
    mock.add_argument("--date")
    mock.set_defaults(func=cmd_mock)

    deb = sub.add_parser("debrief", help="record what a real round asked")
    deb.add_argument("--company", required=True)
    deb.add_argument("--round", required=True)
    deb.add_argument("--asked", help="semicolon-separated questions actually asked")
    deb.add_argument("--gap", help="semicolon-separated things that went badly")
    deb.add_argument("--outcome", help="|".join(OUTCOMES))
    deb.add_argument("--date")
    deb.set_defaults(func=cmd_debrief)

    status = sub.add_parser("status", help="what needs action today")
    status.add_argument("--company")
    status.add_argument("--as-of", dest="as_of")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    render = sub.add_parser("render", help="write the markdown brief")
    render.add_argument("--out", default=str(DEFAULT_BRIEF))
    render.set_defaults(func=cmd_render)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print("unusable: %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
