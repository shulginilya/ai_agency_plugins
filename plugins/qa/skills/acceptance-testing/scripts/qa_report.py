#!/usr/bin/env python3
"""Turn recorded test results into a QA verdict, accept or reject, and the ticket comment that says so.

    qa_report.py results.json [--link URL] [--commit SHA] [--json]

results.json:

    {"ticket": "#42", "change": "PR #43", "review_link": "https://...review.com", "commit": "abc1234",
     "criteria": [{"id": "AC1", "text": "..."}, ...],
     "cases": [{"id": "AC1-1", "ac": "AC1", "kind": "happy", "steps": "...",
                "status": "pass|fail|unchecked|skipped", "evidence": "...", "note": "..."}]}

`unchecked` means the check could not be made (no environment, the data can't
be created); `blocked` is still read as `unchecked`. `--link` and `--commit`
override the file's review_link and commit.

The verdict follows fixed rules, so it cannot be argued into a pass:

    accept   every criterion has at least one passing case and nothing failed
    reject   anything else: a case failed, a criterion has no case, or a
             criterion has no passing case because its cases were unchecked or
             skipped; those are listed as "suggest blocking", never a verdict

The printed text is the ticket comment. It ends with a `<!-- qa:verdict ... -->`
marker naming the verdict, the review link and the commit, which
review_link.py reads to decide whether a later link needs a re-test. An
accepted ticket moves to Ready for Merge, a rejected one back to In progress.

A pass without evidence counts as not run. Standard library only.
Exit status: 0 accept, 1 reject, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

STATUSES = ("pass", "fail", "unchecked", "skipped")
ALIASES = {"blocked": "unchecked"}
MOVE_TO = {"accept": "Ready for Merge", "reject": "In progress"}
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
        if isinstance(case, dict) and case.get("status") in ALIASES:
            case["status"] = ALIASES[case["status"]]
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
    verdict = "reject" if failed or uncovered or unproven else "accept"
    suggest_block = [{"ac": row["id"], "why": "; ".join(str(c.get("note") or c["status"]).strip() for c in row["cases"])}
                     for row in rows if row["id"] in unproven]
    return {"ticket": data.get("ticket"), "change": data.get("change"), "verdict": verdict,
            "move_to": MOVE_TO[verdict], "review_link": data.get("review_link"), "commit": data.get("commit"),
            "failed": failed, "uncovered": uncovered, "unproven": unproven, "suggest_block": suggest_block,
            "criteria": rows}


def render(result: Dict[str, Any]) -> str:
    head = "QA verdict: **%s**" % result["verdict"].upper()
    subject = " · ".join(x for x in (result.get("ticket"), result.get("change")) if x)
    lines = [head + (" — %s" % subject if subject else ""), ""]
    lines.append("Tested on %s, commit `%s`." % (
        "the review link %s" % result["review_link"] if result.get("review_link") else "a local run",
        result.get("commit") or "unknown"))
    lines.append("Moving the ticket to **%s**." % result["move_to"])
    lines.append("")
    if result["failed"]:
        lines.append("Failing criteria: %s" % ", ".join(result["failed"]))
    if result["uncovered"]:
        lines.append("Criteria with no test case: %s" % ", ".join(result["uncovered"]))
    if result["unproven"]:
        lines.append("Criteria not proven (could not be checked, or skipped): %s" % ", ".join(result["unproven"]))
    lines += ["", "| AC | Criterion | Result | Cases |", "| --- | --- | --- | --- |"]
    for row in result["criteria"]:
        cases = "; ".join("%s %s" % (c["id"], c["status"]) for c in row["cases"]) or "—"
        lines.append("| %s | %s | %s | %s |" % (row["id"], str(row["text"]).replace("|", "\\|"), row["state"], cases))
    problems = [c for row in result["criteria"] for c in row["cases"] if c["status"] != "pass"]
    if problems:
        lines += ["", "What fails, and how to see it:"]
        for c in problems:
            detail = c.get("note") or c.get("evidence") or ""
            steps = " Steps: %s." % str(c["steps"]).strip().rstrip(".") if c.get("steps") else ""
            lines.append("- %s (%s, %s): %s%s" % (c["id"], c.get("kind", "case"), c["status"],
                                                  str(detail).strip(), steps))
    if result["suggest_block"]:
        lines += ["", "Suggest blocking (QA does not block; the Captain decides):"]
        lines += ["- %s could not be checked: %s" % (s["ac"], s["why"]) for s in result["suggest_block"]]
    marker = {"verdict": result["verdict"], "link": result.get("review_link") or "none",
              "commit": result.get("commit") or "unknown"}
    lines += ["", "<!-- qa:verdict %s -->" % " ".join("%s=%s" % kv for kv in marker.items())]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results")
    parser.add_argument("--link", help="the review link tested; overrides results.json review_link")
    parser.add_argument("--commit", help="the commit tested; overrides results.json commit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.results, encoding="utf-8") as handle:
            data = load(json.load(handle))
        if args.link:
            data["review_link"] = args.link
        if args.commit:
            data["commit"] = args.commit
    except (OSError, ValueError, ReportError) as exc:
        print("qa_report: %s" % exc, file=sys.stderr)
        return 2
    result = judge(data)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result), end="" if not args.json else "\n")
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    sys.exit(main())
