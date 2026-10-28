#!/usr/bin/env python3
"""Turn recorded review findings into a verdict, approve or request changes, and the PR review body that says so.

    review_report.py findings.json [--commit SHA] [--json]

findings.json:

    {"pr": 43, "ticket": "#42", "commit": "abc1234",
     "passes": ["correctness", "tests", "security"],
     "findings": [{"severity": "blocker|major|minor|nit", "file": "src/a.py", "line": 12,
                   "claim": "...", "why": "...", "failure": "...", "fix": "..."}]}

`passes` names the review passes that ran; correctness and tests always run,
so both must be listed. Every blocker, major and minor finding needs a
`failure`: concrete inputs or state and the wrong result they produce. A
finding without one is a hunch, and the file is refused. Nits need no
failure and never change the verdict. `--commit` overrides the file's commit.

The verdict follows fixed rules, so it cannot be argued into an approve:

    approve          no blocker and no major finding
    request-changes  at least one blocker or major finding

The printed text is the PR review body. It ends with a
`<!-- code-review:verdict ... -->` marker naming the verdict, the PR and the
reviewed commit, which pr_scope.py reads to tell a re-review from an
up-to-date one. An approved ticket stays in In review for QA; a ticket with
changes requested moves back to In progress.

Standard library only. Exit status: 0 approve, 1 request changes, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

SEVERITIES = ("blocker", "major", "minor", "nit")
BLOCKING = ("blocker", "major")
REQUIRED_PASSES = ("correctness", "tests")
PASSES = ("correctness", "security", "performance", "accessibility", "tests")
MOVE_TO = {"approve": None, "request-changes": "In progress"}
MARKER_RE = re.compile(r"<!--\s*code-review:verdict\b([^>]*)-->")
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


class ReportError(Exception):
    pass


def verdict_of(body: str) -> Optional[Dict[str, str]]:
    """The attributes of a review verdict marker, e.g. verdict=approve pr=43 commit=abc1234."""
    m = MARKER_RE.search(body or "")
    if not m:
        return None
    return {k: v.strip('"') for k, v in ATTR_RE.findall(m.group(1))}


def load(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ReportError("findings must be a JSON object")
    passes = data.get("passes")
    if not isinstance(passes, list) or not passes:
        raise ReportError("findings need a non-empty 'passes' list")
    for name in passes:
        if name not in PASSES:
            raise ReportError("unknown pass %r: passes are %s" % (name, ", ".join(PASSES)))
    missing = [p for p in REQUIRED_PASSES if p not in passes]
    if missing:
        raise ReportError("the %s pass always runs: add it to 'passes'" % " and ".join(missing))
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ReportError("findings need a 'findings' list (empty when the review found nothing)")
    for i, f in enumerate(findings, 1):
        if not isinstance(f, dict):
            raise ReportError("finding %d must be an object" % i)
        if f.get("severity") not in SEVERITIES:
            raise ReportError("finding %d: severity must be one of %s" % (i, ", ".join(SEVERITIES)))
        if not str(f.get("file") or "").strip() or not str(f.get("claim") or "").strip():
            raise ReportError("finding %d needs a 'file' and a 'claim'" % i)
        if f["severity"] != "nit" and not str(f.get("failure") or "").strip():
            raise ReportError("finding %d (%s %s): no 'failure' scenario, so it is a hunch, not a finding; "
                              "prove it or drop it" % (i, f["severity"], f["file"]))
    return data


def judge(data: Dict[str, Any]) -> Dict[str, Any]:
    order = {s: n for n, s in enumerate(SEVERITIES)}
    findings = sorted(data["findings"], key=lambda f: order[f["severity"]])
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    verdict = "request-changes" if any(counts[s] for s in BLOCKING) else "approve"
    return {"pr": data.get("pr"), "ticket": data.get("ticket"), "commit": data.get("commit"),
            "passes": list(data["passes"]), "verdict": verdict, "move_to": MOVE_TO[verdict],
            "counts": counts, "findings": findings}


def where(f: Dict[str, Any]) -> str:
    return "%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"]


def render(result: Dict[str, Any]) -> str:
    label = {"approve": "APPROVE", "request-changes": "REQUEST CHANGES"}[result["verdict"]]
    subject = " · ".join(str(x) for x in (
        "PR #%s" % result["pr"] if result.get("pr") else None, result.get("ticket")) if x)
    lines = ["Code review: **%s**" % label + (" — %s" % subject if subject else ""), ""]
    lines.append("Reviewed commit `%s`; passes: %s." % (result.get("commit") or "unknown", ", ".join(result["passes"])))
    if result["move_to"]:
        lines.append("Moving the ticket to **%s**: fix the blockers and majors below, push to this PR, "
                     "and it is reviewed again." % result["move_to"])
    else:
        lines.append("The ticket stays in **In review** for QA.")
    real = [f for f in result["findings"] if f["severity"] != "nit"]
    nits = [f for f in result["findings"] if f["severity"] == "nit"]
    if not real:
        lines += ["", "No findings that would break: nothing a concrete input turns into a wrong result."]
    for f in real:
        lines += ["", "**%s** `%s` — %s" % (f["severity"], where(f), str(f["claim"]).strip())]
        for key, name in (("why", "Why"), ("failure", "Failure"), ("fix", "Fix")):
            if str(f.get(key) or "").strip():
                lines.append("- %s: %s" % (name, str(f[key]).strip()))
    if nits:
        lines += ["", "Nits (optional, never blocking): " + "; ".join(
            "`%s` %s" % (where(f), str(f["claim"]).strip()) for f in nits)]
    marker = {"verdict": result["verdict"], "pr": result.get("pr") or "unknown",
              "commit": result.get("commit") or "unknown"}
    lines += ["", "<!-- code-review:verdict %s -->" % " ".join("%s=%s" % kv for kv in marker.items())]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("findings")
    parser.add_argument("--commit", help="the commit reviewed; overrides findings.json commit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.findings, encoding="utf-8") as handle:
            data = load(json.load(handle))
        if args.commit:
            data["commit"] = args.commit
    except (OSError, ValueError, ReportError) as exc:
        print("review_report: %s" % exc, file=sys.stderr)
        return 2
    result = judge(data)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result), end="" if not args.json else "\n")
    return 0 if result["verdict"] == "approve" else 1


if __name__ == "__main__":
    sys.exit(main())
