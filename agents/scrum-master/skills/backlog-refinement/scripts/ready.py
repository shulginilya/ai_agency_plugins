#!/usr/bin/env python3
"""Apply the mechanical half of a Definition of Ready to one backlog item.

The judgement calls stay with the reader; this only catches what a regular
expression can honestly catch — a missing value statement, fewer than two
acceptance criteria, no size, an unresolved "TBD", wording nothing can be
tested against, and the size signals that mean "split this first".

Use it as a module::

    import ready
    report = ready.evaluate(body, title=title, labels=["size/M"])

or from a shell::

    python ready.py --file issue.md --title "Add partial refunds"
    gh issue view 42 --json body --jq .body | python ready.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

# "As a merchant, I want ... so that ..." and the plainer forms people write.
VALUE_PATTERNS = [
    re.compile(r"\bas\s+an?\s+.{2,60}?\bi\s+want\b", re.I | re.S),
    re.compile(r"^\s*(value|benefit|outcome|so that|in order to)\s*[:\-]", re.I | re.M),
    re.compile(r"\bso\s+that\b", re.I),
]

CRITERIA_HEADING = re.compile(
    r"^\s{0,3}#{1,6}\s*(acceptance\s+criteria|acceptance|definition\s+of\s+done|ac)\b",
    re.I | re.M,
)
CHECKBOX = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s*\S", re.M)
BULLET = re.compile(r"^\s*[-*]\s+\S", re.M)
GIVEN_WHEN = re.compile(r"\bgiven\b.*\bwhen\b", re.I)
NUMBERED = re.compile(r"^\s*\d+[.)]\s+\S", re.M)

SIZE_LABEL = re.compile(r"^(size|sp|points?|estimate)[/:\-]", re.I)
SIZE_IN_BODY = re.compile(
    r"^[ \t]*(?:[-*+][ \t]*)?(?:estimate|size|story\s*points?|points?)[ \t]*[:\-][ \t]*\S",
    re.I | re.M,
)

UNRESOLVED = [
    (re.compile(r"\bTBD\b", re.I), "a TBD"),
    (re.compile(r"\?\?\?"), "an unanswered question (???)"),
    (re.compile(r"\bFIXME\b"), "a FIXME"),
]

# "Depends on: none" and "Open questions: n/a" are answers, not gaps — so these
# capture the rest of the line and the tail decides.
TAILED = [
    (
        re.compile(
            r"\b(?:blocked\s+by|depends\s+on|waiting\s+(?:on|for))\b"
            r"[ \t]*[:\-]?[ \t]*(?P<tail>[^\n]*)",
            re.I,
        ),
        "an unresolved dependency",
    ),
    (
        re.compile(
            r"^[ \t]*(?:[-*+][ \t]*)?(?:#{1,6}[ \t]*)?"
            r"(?:open\s+questions?|questions?)[ \t]*[:\-][ \t]*(?P<tail>[^\n]*)",
            re.I | re.M,
        ),
        "an open question",
    ),
]

RESOLVED_TAIL = re.compile(r"^(?:none|n/?a|nothing|no|-+|\u2014|\.)?\s*\.?$", re.I)


def _unresolved_label(body):
    """The first genuinely unresolved marker in the body, or None."""
    for pattern, label in UNRESOLVED:
        if pattern.search(body):
            return label
    for pattern, label in TAILED:
        for match in pattern.finditer(body):
            tail = (match.group("tail") or "").strip()
            if tail and not RESOLVED_TAIL.match(tail):
                return label
    return None


VAGUE = [
    (re.compile(r"\b(improve|optimi[sz]e|enhance|streamline|clean\s*up|refactor)\b(?![^.\n]*\b(by|to|under|below|from)\b[^.\n]*\d)", re.I),
     "an improvement with no measurable target"),
    (re.compile(r"\b(intuitive|user[- ]friendly|seamless|robust|scalable|modern|better|nice)\b", re.I),
     "an adjective nothing can be tested against"),
    (re.compile(r"\b(etc\.?|and so on|various|several other|as needed)\b", re.I),
     "an open-ended list (etc./various)"),
    (re.compile(r"\b(handle|support)\s+(all\s+)?edge\s+cases\b", re.I),
     "\"edge cases\" with no case named"),
]

TITLE_CONJUNCTION = re.compile(r"\s+(and|,|\+|&|/)\s+", re.I)

BODY_WORDS_TOO_BIG = 400
CRITERIA_TOO_MANY = 8


def _criteria_count(body: str) -> int:
    """Count acceptance criteria, preferring an explicit AC section."""
    section = body
    match = CRITERIA_HEADING.search(body)
    if match:
        rest = body[match.end():]
        nxt = re.search(r"^\s{0,3}#{1,6}\s+\S", rest, re.M)
        section = rest[: nxt.start()] if nxt else rest
    count = len(CHECKBOX.findall(section))
    if count:
        return count
    count = len(GIVEN_WHEN.findall(section))
    if count:
        return count
    if match:
        return len(BULLET.findall(section)) + len(NUMBERED.findall(section))
    return 0


def _has_size(body: str, labels: Sequence[str]) -> bool:
    for label in labels:
        if SIZE_LABEL.match(str(label).strip()):
            return True
    return bool(SIZE_IN_BODY.search(body))


def evaluate(
    body: str,
    title: str = "",
    labels: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Return {'ready': bool, 'gaps': [...], 'warnings': [...], 'signals': {...}}."""
    body = body or ""
    labels = list(labels or [])
    stripped = body.strip()

    gaps: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    def gap(code: str, message: str, fix: str) -> None:
        gaps.append({"code": code, "message": message, "fix": fix})

    def warn(code: str, message: str, fix: str) -> None:
        warnings.append({"code": code, "message": message, "fix": fix})

    if not stripped:
        gap("empty", "the item has no body at all",
            "write the value statement and at least two acceptance criteria")
        return {
            "ready": False,
            "gaps": gaps,
            "warnings": warnings,
            "signals": {"criteria": 0, "words": 0, "has_size": _has_size("", labels)},
        }

    if not any(p.search(body) for p in VALUE_PATTERNS):
        gap("value", "no statement of who wants this or what they get",
            "add 'As a <role>, I want <capability> so that <outcome>'")

    criteria = _criteria_count(body)
    if criteria == 0:
        gap("criteria", "no acceptance criteria",
            "add at least two: happy path, one failure path, one boundary")
    elif criteria == 1:
        gap("criteria", "only one acceptance criterion",
            "add a failure path and a boundary case")

    if not _has_size(body, labels):
        gap("size", "no estimate or size label",
            "add a size/* label, or 'Estimate: <points>' in the body")

    unresolved = _unresolved_label(body)
    if unresolved:
        gap("unresolved", "the body still contains %s" % unresolved,
            "resolve it in refinement, or leave the item out of the sprint")

    for pattern, label in VAGUE:
        if pattern.search(body):
            warn("vague", "wording that cannot be verified: %s" % label,
                 "replace it with a number, a named case, or a visible behaviour")
            break

    words = len(stripped.split())
    if words > BODY_WORDS_TOO_BIG:
        warn("too-big", "the body is %d words" % words,
             "long descriptions usually hide two items; check the splitting patterns")
    if criteria > CRITERIA_TOO_MANY:
        warn("too-big", "%d acceptance criteria" % criteria,
             "more than %d criteria is normally two stories" % CRITERIA_TOO_MANY)
    if title and TITLE_CONJUNCTION.search(title.strip()):
        warn("too-big", "the title joins two things ('and', '+', '/')",
             "split it, or rename it if the title is just clumsy")

    return {
        "ready": not gaps,
        "gaps": gaps,
        "warnings": warnings,
        "signals": {
            "criteria": criteria,
            "words": words,
            "has_size": _has_size(body, labels),
        },
    }


def format_report(report: Dict[str, Any], title: str = "") -> str:
    lines: List[str] = []
    heading = title.strip() or "item"
    if report["ready"]:
        lines.append("READY  %s" % heading)
    else:
        lines.append("NOT READY  %s" % heading)
    for entry in report["gaps"]:
        lines.append("  gap   %s" % entry["message"])
        lines.append("        -> %s" % entry["fix"])
    for entry in report["warnings"]:
        lines.append("  warn  %s" % entry["message"])
        lines.append("        -> %s" % entry["fix"])
    if report["ready"] and not report["warnings"]:
        lines.append("  %d acceptance criteria, size present." % report["signals"]["criteria"])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", help="read the item body from this file (default: stdin)")
    parser.add_argument("--title", default="", help="the item title, checked for split signals")
    parser.add_argument("--label", action="append", default=[], help="a label; repeatable")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as handle:
                body = handle.read()
        except OSError as exc:
            sys.stderr.write("cannot read %s: %s\n" % (args.file, exc))
            return 2
    else:
        body = sys.stdin.read()

    report = evaluate(body, title=args.title, labels=args.label)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report, args.title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
