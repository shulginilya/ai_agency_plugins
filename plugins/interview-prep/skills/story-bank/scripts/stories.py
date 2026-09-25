#!/usr/bin/env python3
"""The story bank: what you can actually say about work you actually did.

Usage:
    python scripts/stories.py init
    python scripts/stories.py add --title "Cut checkout LCP in half" \
        --competencies delivery,technical-decision \
        --situation "..." --task "..." --action "..." --result "..." --metric "LCP 4.1s -> 1.9s"
    python scripts/stories.py list --competency conflict
    python scripts/stories.py check
    python scripts/stories.py render

A bank with twelve stories about the same project covers one competency twelve
times. `check` reports coverage against the competencies interviewers actually
ask about, and it reports *thin* separately from *missing* -- a story with no
outcome and no first-person verb is not a story you have, it is a story you
think you have.

Exit codes for `check`:
    0   covered    every competency has at least one story that would survive probing
    1   gaps       a competency has no story at all
    2   unusable   no bank, or a file that is not a story bank
    3   thin       every competency is covered, but some stories fail a quality rule
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
DEFAULT_PATH = DEFAULT_DIR / "stories.json"
DEFAULT_RENDER = DEFAULT_DIR / "stories.md"
KIND = "interview-stories"

COMPETENCIES = [
    "delivery",              # shipped something hard, on a deadline
    "technical-decision",    # chose an architecture or a tool and owned the consequence
    "failure",               # broke something, or was wrong, and what followed
    "conflict",              # disagreed with a peer, a manager or a stakeholder
    "influence",             # changed what a team did without authority to order it
    "mentoring",             # grew someone else's capability
    "ambiguity",             # acted without a spec
    "incident",              # production went wrong and you were on it
    "scope",                 # cut, pushed back, or renegotiated what was being built
    "cross-functional",      # worked with product, design or the business
]

MIN_ACTION_CHARS = 120
OUTCOME_WORDS = (
    "reduced", "increased", "cut", "shipped", "saved", "grew", "dropped", "raised",
    "eliminated", "migrated", "recovered", "halved", "doubled", "adopted", "rolled out",
)
FIRST_PERSON = re.compile(r"\b(i|my)\b", re.I)
HAS_NUMBER = re.compile(r"\d")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "untitled"


def empty_bank() -> Dict[str, Any]:
    return {"kind": KIND, "version": 1, "competencies": list(COMPETENCIES), "stories": []}


def read(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError("no story bank at %s -- run `stories.py init` first" % path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("%s is not valid JSON (%s)" % (path, exc))
    if not isinstance(data, dict) or data.get("kind") != KIND:
        raise ValueError("%s is not a story bank -- refusing to overwrite it" % path)
    data.setdefault("stories", [])
    data.setdefault("competencies", list(COMPETENCIES))
    return data


def write(path: Path, bank: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copyfile(str(path), str(path) + ".bak")
    path.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def weaknesses(story: Dict[str, Any]) -> List[str]:
    """Why this story would fall apart under a follow-up question."""
    problems = []
    action = story.get("action", "")
    result = " ".join([story.get("result", ""), story.get("metric", "")]).strip()
    if not story.get("situation", "").strip():
        problems.append("no situation -- the interviewer cannot tell what was at stake")
    if len(action.strip()) < MIN_ACTION_CHARS:
        problems.append("the action is %d characters; too thin to probe" % len(action.strip()))
    if action.strip() and not FIRST_PERSON.search(action):
        problems.append("the action never says 'I' -- your own part is unclear")
    if not result:
        problems.append("no result -- a story without an outcome is an anecdote")
    elif not HAS_NUMBER.search(result) and not any(w in result.lower() for w in OUTCOME_WORDS):
        problems.append("the result names neither a number nor a concrete change")
    if not story.get("competencies"):
        problems.append("no competency tagged -- it cannot be matched to a question")
    return problems


def coverage(bank: Dict[str, Any]) -> Dict[str, Any]:
    per_competency: Dict[str, Dict[str, List[str]]] = {
        c: {"solid": [], "thin": []} for c in bank["competencies"]
    }
    thin_stories = []
    for story in bank["stories"]:
        problems = weaknesses(story)
        if problems:
            thin_stories.append({"title": story["title"], "problems": problems})
        for competency in story.get("competencies", []):
            bucket = per_competency.setdefault(competency, {"solid": [], "thin": []})
            bucket["thin" if problems else "solid"].append(story["title"])

    missing = [c for c in bank["competencies"] if not per_competency[c]["solid"] and not per_competency[c]["thin"]]
    only_thin = [c for c in bank["competencies"] if not per_competency[c]["solid"] and per_competency[c]["thin"]]

    if missing:
        verdict, code = "gaps", 1
    elif thin_stories:
        verdict, code = "thin", 3
    else:
        verdict, code = "covered", 0
    return {
        "verdict": verdict,
        "exit_code": code,
        "stories": len(bank["stories"]),
        "missing": missing,
        "covered_only_by_thin_stories": only_thin,
        "thin_stories": thin_stories,
        "per_competency": {k: v for k, v in sorted(per_competency.items())},
    }


def render_check(report: Dict[str, Any]) -> str:
    lines = ["%s -- %d story/stories in the bank" % (report["verdict"].upper(), report["stories"])]
    if report["missing"]:
        lines += ["", "No story at all for:"]
        lines += ["  - %s" % c for c in report["missing"]]
    if report["covered_only_by_thin_stories"]:
        lines += ["", "Covered only by a story that would not survive a follow-up:"]
        lines += ["  - %s" % c for c in report["covered_only_by_thin_stories"]]
    if report["thin_stories"]:
        lines += ["", "Stories to fix:"]
        for story in report["thin_stories"]:
            lines.append("  %s" % story["title"])
            lines += ["    - %s" % p for p in story["problems"]]
    if report["verdict"] == "covered":
        lines += ["", "Every competency has a story that holds up. Rehearse, do not rewrite."]
    return "\n".join(lines)


def render_bank(bank: Dict[str, Any]) -> str:
    lines = ["# Story bank", "", "Generated from stories.json -- do not edit by hand.", ""]
    for competency in bank["competencies"]:
        titles = [s["title"] for s in bank["stories"] if competency in s.get("competencies", [])]
        lines.append("- **%s**: %s" % (competency, ", ".join(titles) or "_nothing yet_"))
    for story in bank["stories"]:
        lines += ["", "## %s" % story["title"], "", "_%s_" % ", ".join(story.get("competencies", [])) ]
        for field in ("situation", "task", "action", "result"):
            if story.get(field):
                lines += ["", "**%s.** %s" % (field.capitalize(), story[field])]
        if story.get("metric"):
            lines += ["", "**Metric.** %s" % story["metric"]]
        problems = weaknesses(story)
        if problems:
            lines += ["", "> Needs work: %s" % "; ".join(problems)]
    return "\n".join(lines) + "\n"


def cmd_init(args) -> int:
    path = Path(args.file)
    if path.is_file():
        read(path)
        print("%s already exists" % path)
        return 0
    write(path, empty_bank())
    print("wrote %s with %d competencies" % (path, len(COMPETENCIES)))
    return 0


def cmd_add(args) -> int:
    path = Path(args.file)
    bank = read(path)
    slug = slugify(args.title)
    if any(s["slug"] == slug for s in bank["stories"]):
        raise ValueError("a story called %r is already in the bank" % args.title)
    competencies = [c.strip().lower() for c in (args.competencies or "").split(",") if c.strip()]
    unknown = [c for c in competencies if c not in bank["competencies"]]
    if unknown:
        raise ValueError("unknown competency %s -- one of: %s"
                         % (", ".join(unknown), ", ".join(bank["competencies"])))
    story = {
        "slug": slug,
        "title": args.title.strip(),
        "competencies": competencies,
        "situation": (args.situation or "").strip(),
        "task": (args.task or "").strip(),
        "action": (args.action or "").strip(),
        "result": (args.result or "").strip(),
        "metric": (args.metric or "").strip(),
        "added": dt.date.today().isoformat(),
    }
    bank["stories"].append(story)
    write(path, bank)
    problems = weaknesses(story)
    print("added %r" % story["title"])
    for problem in problems:
        print("  needs work: %s" % problem)
    return 0


def cmd_list(args) -> int:
    bank = read(Path(args.file))
    stories = bank["stories"]
    if args.competency:
        stories = [s for s in stories if args.competency.lower() in s.get("competencies", [])]
    if not stories:
        print("no stories match")
        return 0
    for story in stories:
        flag = "thin" if weaknesses(story) else "ok"
        print("[%s] %s -- %s" % (flag, story["title"], ", ".join(story.get("competencies", [])) or "untagged"))
    return 0


def cmd_check(args) -> int:
    bank = read(Path(args.file))
    report = coverage(bank)
    print(json.dumps(report, indent=2) if args.json else render_check(report))
    return int(report["exit_code"])


def cmd_render(args) -> int:
    bank = read(Path(args.file))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        shutil.copyfile(str(out), str(out) + ".bak")
    out.write_text(render_bank(bank), encoding="utf-8")
    print("wrote %s" % out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keep and check the STAR story bank.")
    parser.add_argument("--file", default=str(DEFAULT_PATH), help="bank file. Default .interview/stories.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the bank").set_defaults(func=cmd_init)

    add = sub.add_parser("add", help="add one story")
    add.add_argument("--title", required=True)
    add.add_argument("--competencies", help="comma-separated: %s" % ", ".join(COMPETENCIES))
    add.add_argument("--situation")
    add.add_argument("--task")
    add.add_argument("--action")
    add.add_argument("--result")
    add.add_argument("--metric")
    add.set_defaults(func=cmd_add)

    listing = sub.add_parser("list", help="list stories")
    listing.add_argument("--competency")
    listing.set_defaults(func=cmd_list)

    check = sub.add_parser("check", help="coverage and quality")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=cmd_check)

    render = sub.add_parser("render", help="write the markdown bank")
    render.add_argument("--out", default=str(DEFAULT_RENDER))
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
