#!/usr/bin/env python3
"""Work out how much fits in a sprint, from absence and focus, from velocity, or both.

    python capacity.py --people 4 --days 10 --focus 0.7
    python capacity.py --people 4 --days 10 --absence "ilya:3,ana:1" --velocity 21,25,19
    python capacity.py --velocity 21,25,19,23 --json

With --velocity it reports the commitment range history supports; without it,
focused person-days. Both are printed at the 80% commitment line, because a
sprint planned to 100% of capacity reliably finishes below 80% of it.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

COMMIT_RATIO = 0.8
DEFAULT_FOCUS = 0.7
DEFAULT_SPRINT_DAYS = 10.0
CEREMONY_DAYS_PER_PERSON = 0.5


class CapacityError(Exception):
    """The inputs do not describe a sprint."""


def parse_absence(raw: Optional[str]) -> Dict[str, float]:
    """'ilya:3,ana:1.5' -> {'ilya': 3.0, 'ana': 1.5}."""
    if not raw:
        return {}
    absence: Dict[str, float] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise CapacityError("absence entry %r must look like name:days" % chunk)
        name, _, days = chunk.partition(":")
        try:
            value = float(days)
        except ValueError:
            raise CapacityError("absence for %r is not a number: %r" % (name.strip(), days))
        if value < 0:
            raise CapacityError("absence for %r is negative" % name.strip())
        absence[name.strip()] = absence.get(name.strip(), 0.0) + value
    return absence


def parse_velocity(raw: Optional[str]) -> List[float]:
    if not raw:
        return []
    values: List[float] = []
    for chunk in raw.replace(" ", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = float(chunk)
        except ValueError:
            raise CapacityError("velocity entry %r is not a number" % chunk)
        if value < 0:
            raise CapacityError("velocity entry %r is negative" % chunk)
        values.append(value)
    return values


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def compute(
    people: int = 0,
    days: float = DEFAULT_SPRINT_DAYS,
    focus: float = DEFAULT_FOCUS,
    absence: Optional[Dict[str, float]] = None,
    holidays: float = 0.0,
    oncall: float = 0.0,
    velocity: Optional[Sequence[float]] = None,
    ceremonies: bool = True,
) -> Dict[str, Any]:
    absence = absence or {}
    velocity = list(velocity or [])

    if people < 0 or days < 0:
        raise CapacityError("people and days cannot be negative")
    if not 0 < focus <= 1:
        raise CapacityError("focus factor must be greater than 0 and at most 1")
    if not people and not velocity:
        raise CapacityError("give --people and --days, or --velocity, or both")

    result: Dict[str, Any] = {"warnings": []}

    if focus > 0.8:
        result["warnings"].append(
            "focus factor %.2f is higher than any sustained team achieves; 0.65-0.75 is realistic"
            % focus
        )

    if people:
        gross = people * days
        absent = sum(absence.values())
        ceremony = people * CEREMONY_DAYS_PER_PERSON if ceremonies else 0.0
        net = gross - absent - holidays - oncall - ceremony
        if net < 0:
            raise CapacityError(
                "deductions (%.1f days) exceed gross capacity (%.1f days)" % (gross - net, gross)
            )
        focused = net * focus
        result["days"] = {
            "gross": round(gross, 2),
            "absence": round(absent, 2),
            "holidays": round(holidays, 2),
            "oncall": round(oncall, 2),
            "ceremonies": round(ceremony, 2),
            "net": round(net, 2),
            "focus": focus,
            "focused": round(focused, 2),
            "commit": round(focused * COMMIT_RATIO, 2),
        }
        if absent > gross * 0.3:
            result["warnings"].append(
                "absence removes %.0f%% of the sprint; plan a smaller goal, not a busier one"
                % (100.0 * absent / gross)
            )

    if velocity:
        mean = sum(velocity) / len(velocity)
        result["velocity"] = {
            "samples": [round(v, 2) for v in velocity],
            "mean": round(mean, 2),
            "median": round(_median(velocity), 2),
            "low": round(min(velocity), 2),
            "high": round(max(velocity), 2),
            "commit_low": round(min(velocity) * COMMIT_RATIO, 2),
            "commit_high": round(mean, 2),
        }
        if len(velocity) < 3:
            result["warnings"].append(
                "%d sprint(s) of history is not enough to plan from; use focused person-days "
                "until there are three" % len(velocity)
            )
        elif max(velocity) - min(velocity) > mean * 0.5:
            result["warnings"].append(
                "velocity swings by more than half the mean; the estimates or the "
                "Definition of Done are inconsistent, so plan to the low end"
            )

    result["basis"] = "velocity" if velocity else "person-days"
    return result


def format_report(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    days = result.get("days")
    if days:
        lines.append("Person-days")
        lines.append("  gross                 %6.1f" % days["gross"])
        for key, label in (
            ("absence", "planned absence"),
            ("holidays", "holidays"),
            ("oncall", "on-call"),
            ("ceremonies", "ceremonies"),
        ):
            if days[key]:
                lines.append("  - %-19s %6.1f" % (label, days[key]))
        lines.append("  net                   %6.1f" % days["net"])
        lines.append("  x focus %.2f           %6.1f" % (days["focus"], days["focused"]))
        lines.append("  commit at 80%%         %6.1f focused person-days" % days["commit"])

    velocity = result.get("velocity")
    if velocity:
        if lines:
            lines.append("")
        lines.append("Velocity")
        lines.append("  samples               %s" % ", ".join("%g" % v for v in velocity["samples"]))
        lines.append("  mean / median         %g / %g" % (velocity["mean"], velocity["median"]))
        lines.append("  range                 %g - %g" % (velocity["low"], velocity["high"]))
        lines.append("  commit                %g - %g points"
                     % (velocity["commit_low"], velocity["commit_high"]))

    if result["warnings"]:
        lines.append("")
        for warning in result["warnings"]:
            lines.append("warn: %s" % warning)

    lines.append("")
    lines.append("Plan to the %s figure; leave the remaining 20%% for interruptions." % result["basis"])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--people", type=int, default=0, help="people on the team")
    parser.add_argument("--days", type=float, default=DEFAULT_SPRINT_DAYS,
                        help="working days in the sprint (default %d)" % DEFAULT_SPRINT_DAYS)
    parser.add_argument("--focus", type=float, default=DEFAULT_FOCUS,
                        help="fraction of a day that reaches sprint work (default %.2f)" % DEFAULT_FOCUS)
    parser.add_argument("--absence", help="planned leave, as 'name:days,name:days'")
    parser.add_argument("--holidays", type=float, default=0.0, help="public-holiday person-days")
    parser.add_argument("--oncall", type=float, default=0.0, help="person-days lost to on-call")
    parser.add_argument("--no-ceremonies", action="store_true",
                        help="do not subtract the standard half-day per person for ceremonies")
    parser.add_argument("--velocity", help="points completed in past sprints, e.g. 21,25,19")
    parser.add_argument("--json", action="store_true", help="emit the numbers as JSON")
    args = parser.parse_args(argv)

    try:
        result = compute(
            people=args.people,
            days=args.days,
            focus=args.focus,
            absence=parse_absence(args.absence),
            holidays=args.holidays,
            oncall=args.oncall,
            velocity=parse_velocity(args.velocity),
            ceremonies=not args.no_ceremonies,
        )
    except CapacityError as exc:
        sys.stderr.write("capacity: %s\n" % exc)
        return 2

    print(json.dumps(result, indent=2) if args.json else format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
