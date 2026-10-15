#!/usr/bin/env python3
"""Turn recorded test results into a QA verdict: accept, or reject with the reasons.

    qa_report.py results.json [--json]

results.json:

    {"ticket": "#42", "change": "PR #43",
     "criteria": [{"id": "AC1", "text": "..."}, ...],
     "cases": [{"id": "AC1-1", "ac": "AC1", "kind": "happy", "steps": "...",
                "status": "pass|fail|blocked|skipped", "evidence": "...", "note": "..."}]}

The verdict follows fixed rules, so it cannot be argued into a pass:

    reject   any case failed, or a criterion has no case at all
    blocked  nothing failed, but a criterion has no passing case because its
             cases were blocked or skipped (the check could not be made)
    accept   every criterion has at least one passing case and nothing failed

A pass without evidence counts as not run. Standard library only.
Exit status: 0 accept, 1 reject or blocked, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

STATUSES = ("pass", "fail", "blocked", "skipped")
KINDS = ("happy", "edge", "boundary", "negative", "regression", "accessibility", "exploratory")


class ReportError(Exception):
    pass


def load(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ReportError("results must be a JSON object")
    criteria = data.get("criteria")
    cases = data.get("cases")
    if not isinstance(criteria, list) or not criteria:
        raise ReportError("results need a non-empty 'criteria' list")
    if not isinstance(cases, list):
        raise ReportError("results need a 'cases' list")
    ids = [c.get("id") for c in criteria if isinstance(c, dict)]
    if len(ids) != len(criteria) or not all(ids) or len(set(ids)) != len(ids):
        raise ReportError("every criterion needs a unique 'id'")
    for case in cases:
        if not isinstance(case, dict) or not case.get("id") or case.get("ac") not in ids:
            raise ReportError("case %r must have an 'id' and an 'ac' naming a listed criterion" % case)
        if case.get("status") not in STATUSES:
            raise ReportError("case %s: status must be one of %s" % (case["id"], ", ".join(STATUSES)))
    return data


def judge(data: Dict[str, Any]) -> Dict[str, Any]:
    by_ac: Dict[str, List[Dict[str, Any]]] = {c["id"]: [] for c in data["criteria"]}
    for case in data["cases"]:
        status = case["status"]
        if status == "pass" and not str(case.get("evidence") or "").strip():
            status = "skipped"  # a pass nobody can check is not a pass
            case = dict(case, status=status, note=(case.get("note") or "") + " (no evidence: counted as not run)")
        by_ac[case["ac"]].append(case)
    rows, failed, uncovered, unproven = [], [], [], []
    for crit in data["criteria"]:
        cases = by_ac[crit["id"]]
        statuses = [c["status"] for c in cases]
        if not cases:
            state = "no cases"
            uncovered.append(crit["id"])
        elif "fail" in statuses:
            state = "fail"
            failed.append(crit["id"])
        elif "pass" in statuses:
            state = "pass"
        else:
            state = "not proven"
            unproven.append(crit["id"])
        rows.append({"id": crit["id"], "text": crit.get("text", ""), "state": state, "cases": cases})
    if failed or uncovered:
        verdict = "reject"
    elif unproven:
        verdict = "blocked"
    else:
        verdict = "accept"
    return {"ticket": data.get("ticket"), "change": data.get("change"), "verdict": verdict,
            "failed": failed, "uncovered": uncovered, "unproven": unproven, "criteria": rows}


def render(result: Dict[str, Any]) -> str:
    head = "QA verdict: **%s**" % result["verdict"].upper()
    subject = " · ".join(x for x in (result.get("ticket"), result.get("change")) if x)
    lines = [head + (" — %s" % subject if subject else ""), ""]
    if result["failed"]:
        lines.append("Failing criteria: %s" % ", ".join(result["failed"]))
    if result["uncovered"]:
        lines.append("Criteria with no test case: %s" % ", ".join(result["uncovered"]))
    if result["unproven"]:
        lines.append("Criteria not proven (cases blocked or skipped): %s" % ", ".join(result["unproven"]))
    lines += ["", "| AC | Criterion | Result | Cases |", "| --- | --- | --- | --- |"]
    for row in result["criteria"]:
        cases = "; ".join("%s %s" % (c["id"], c["status"]) for c in row["cases"]) or "—"
        lines.append("| %s | %s | %s | %s |" % (row["id"], str(row["text"]).replace("|", "\\|"), row["state"], cases))
    problems = [c for row in result["criteria"] for c in row["cases"] if c["status"] != "pass"]
    if problems:
        lines += ["", "Not passing:"]
        for c in problems:
            detail = c.get("note") or c.get("evidence") or ""
            lines.append("- %s (%s, %s): %s" % (c["id"], c.get("kind", "case"), c["status"], str(detail).strip()))
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.results, encoding="utf-8") as handle:
            data = load(json.load(handle))
    except (OSError, ValueError, ReportError) as exc:
        print("qa_report: %s" % exc, file=sys.stderr)
        return 2
    result = judge(data)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result), end="" if not args.json else "\n")
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    sys.exit(main())
