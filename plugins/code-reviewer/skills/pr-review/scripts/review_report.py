#!/usr/bin/env python3
"""Turn recorded review findings into a verdict, approve or request changes, and the PR review body that says so.

    review_report.py findings.json [--commit SHA] [--round N] [--captain LOGIN] [--skip-approval] [--json]

findings.json:

    {"pr": 43, "ticket": "#42", "commit": "abc1234", "skip_approval": false, "round": 1, "captain": "octocat",
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
    stop             round 3 or later, and any blocker, major or minor left

`round` is the review round pr_scope.py printed (1 for the first review
after an approve, a stop, or none yet). On a stop the review loop ends: the body opens
with an @mention of the Captain (`captain`, from pr_scope.py) and a summary of
what is still open, and every closing ticket moves to Ready for the Captain to
pick up.

The printed text is the PR review body. It ends with a
`<!-- code-review:verdict ... -->` marker naming the verdict, the PR and the
reviewed commit, which pr_scope.py reads to tell a re-review from an
up-to-date one. An approved ticket moves to In approval, for the Captain's own
code review, or straight to QA when it is labelled skip_approval
(`--skip-approval`, or "skip_approval": true in the file); a
ticket with changes requested moves back to In progress.

Standard library only. Exit status: 0 approve, 1 request changes, 2 bad input, 3 stop.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

SEVERITIES = ("blocker", "major", "minor", "nit")
BLOCKING = ("blocker", "major")
OPEN = ("blocker", "major", "minor")
MAX_ROUNDS = 3
REQUIRED_PASSES = ("correctness", "tests")
PASSES = ("correctness", "security", "performance", "accessibility", "tests")
SKIP_APPROVAL = "skip_approval"
MOVE_TO = {"approve": "In approval", "request-changes": "In progress", "stop": "Ready"}
EXIT = {"approve": 0, "request-changes": 1, "stop": 3}
MARKER_RE = re.compile(r"<!--\s*code-review:verdict\b([^>]*)-->")
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


class ReportError(Exception):
    pass


def move_to(verdict: str, labels: Optional[List[str]] = None) -> str:
    """The column a ticket moves to on this verdict: an approve skips In approval for QA when it carries the label."""
    if verdict == "approve" and SKIP_APPROVAL in (labels or []):
        return "QA"
    return MOVE_TO[verdict]


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
    rnd = data.get("round", 1)
    if isinstance(rnd, bool) or not isinstance(rnd, int) or rnd < 1:
        raise ReportError("'round' is the review round, a whole number from 1, not %r" % (rnd,))
    captain = data.get("captain")
    if captain is not None and not re.match(r"^[A-Za-z0-9-]+$", str(captain)):
        raise ReportError("'captain' is a GitHub login, not %r" % (captain,))
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
    rnd = data.get("round", 1)
    if rnd >= MAX_ROUNDS and any(counts[s] for s in OPEN):
        verdict = "stop"
    elif any(counts[s] for s in BLOCKING):
        verdict = "request-changes"
    else:
        verdict = "approve"
    return {"pr": data.get("pr"), "ticket": data.get("ticket"), "commit": data.get("commit"),
            "round": rnd, "captain": data.get("captain"), "passes": list(data["passes"]), "verdict": verdict,
            "move_to": move_to(verdict, [SKIP_APPROVAL] if data.get("skip_approval") else []),
            "counts": counts, "findings": findings}


def where(f: Dict[str, Any]) -> str:
    return "%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"]


def summary(result: Dict[str, Any]) -> str:
    """The stop's hand-off to the Captain: who, how many rounds, and what is still open."""
    counts = result["counts"]
    left = ", ".join("%d %s" % (counts[s], s) for s in OPEN if counts[s])
    who = "@%s " % result["captain"] if result.get("captain") else ""
    return ("%s**Review stopped after %d rounds**: %s still open on `%s`. The ticket goes back to **Ready** "
            "and the crew stops working on it; decide whether to fix, accept or split what is listed below."
            % (who, result["round"], left, result.get("commit") or "unknown"))


def render(result: Dict[str, Any]) -> str:
    label = {"approve": "APPROVE", "request-changes": "REQUEST CHANGES", "stop": "STOP"}[result["verdict"]]
    subject = " · ".join(str(x) for x in (
        "PR #%s" % result["pr"] if result.get("pr") else None, result.get("ticket")) if x)
    lines = []
    if result["verdict"] == "stop":
        lines += [summary(result), ""]
    lines += ["Code review: **%s**" % label + (" — %s" % subject if subject else ""), ""]
    lines.append("Reviewed commit `%s` (round %d); passes: %s."
                 % (result.get("commit") or "unknown", result["round"], ", ".join(result["passes"])))
    if result["verdict"] == "stop":
        lines.append("Moving the ticket to **Ready**. The review loop stops here until the Captain picks it up.")
    elif result["verdict"] == "request-changes":
        lines.append("Moving the ticket to **%s**: fix the blockers and majors below, push to this PR, "
                     "and it is reviewed again." % result["move_to"])
    elif result["move_to"] == "QA":
        lines.append("Moving the ticket to **QA**: it is labelled `%s`, so it skips the Captain's review."
                     % SKIP_APPROVAL)
    else:
        lines.append("Moving the ticket to **In approval**, for the Captain's code review before QA.")
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
              "commit": result.get("commit") or "unknown", "round": result["round"]}
    lines += ["", "<!-- code-review:verdict %s -->" % " ".join("%s=%s" % kv for kv in marker.items())]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("findings")
    parser.add_argument("--commit", help="the commit reviewed; overrides findings.json commit")
    parser.add_argument("--round", type=int, help="the review round pr_scope.py printed; overrides findings.json round")
    parser.add_argument("--captain", help="the Captain's GitHub login, @mentioned on a stop; overrides findings.json captain")
    parser.add_argument("--skip-approval", action="store_true",
                        help="the ticket is labelled %s: an approve moves it to QA" % SKIP_APPROVAL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.findings, encoding="utf-8") as handle:
            data = load(json.load(handle))
        if args.commit:
            data["commit"] = args.commit
        if args.round is not None:
            data["round"] = args.round
        if args.captain:
            data["captain"] = args.captain.lstrip("@")
        data = load(data)
        if args.skip_approval:
            data["skip_approval"] = True
    except (OSError, ValueError, ReportError) as exc:
        print("review_report: %s" % exc, file=sys.stderr)
        return 2
    result = judge(data)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result), end="" if not args.json else "\n")
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
