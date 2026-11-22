#!/usr/bin/env python3
"""Turn recorded TypeScript review findings into a verdict, approve or request changes, and the report that says so.

    review_report.py findings.json [--commit SHA] [--json]

findings.json:

    {"target": "PR #43", "commit": "abc1234",
     "passes": ["types", "correctness", "tests", "react"],
     "checks": [{"name": "typecheck", "command": "pnpm run typecheck", "result": "pass|fail|not run"}],
     "findings": [{"severity": "blocker|major|minor|nit", "pass": "types", "file": "src/a.ts", "line": 12,
                   "claim": "...", "why": "...", "failure": "...", "fix": "..."}]}

`passes` names the review passes that ran. Types, correctness and tests always
run, so all three must be listed; react and node run when the change touches
them. Every blocker, major and minor finding needs a `failure`: concrete inputs
or state and the wrong result they produce. A finding without one is a hunch,
and the file is refused. Nits need no failure and never change the verdict.
`checks` is optional; a check whose result is fail must also appear as a
blocker finding. `--commit` overrides the file's commit.

The verdict follows fixed rules, so it cannot be argued into an approve:

    approve          no blocker and no major finding
    request-changes  at least one blocker or major finding

The printed text is the report, also the PR comment body when it is posted. It
ends with a `<!-- typescript-review:verdict ... -->` marker naming the verdict
and the reviewed commit.

A request-changes verdict is also saved: the verdict, counts and every finding go to
`<target>-<commit>.json` in ~/Documents/code_reviews (the folder is created; set
TS_REVIEW_SAVE_DIR to use another). The path is printed on stderr. A save that fails prints
"not saved" there and changes neither the report nor the exit status. An approve saves nothing.

Standard library only. Exit status: 0 approve, 1 request changes, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

SEVERITIES = ("blocker", "major", "minor", "nit")
BLOCKING = ("blocker", "major")
PASSES = ("types", "correctness", "tests", "react", "node")
REQUIRED_PASSES = ("types", "correctness", "tests")
CHECK_RESULTS = ("pass", "fail", "not run")
EXIT = {"approve": 0, "request-changes": 1}
MARKER_RE = re.compile(r"<!--\s*typescript-review:verdict\b([^>]*)-->")
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


class ReportError(Exception):
    pass


def verdict_of(body: str) -> Optional[Dict[str, str]]:
    """The attributes of a report's verdict marker, e.g. verdict=approve commit=abc1234."""
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
        raise ReportError("the %s pass always runs: add it to 'passes'" % ", ".join(missing))
    checks = data.get("checks", [])
    if not isinstance(checks, list):
        raise ReportError("'checks' must be a list")
    for i, check in enumerate(checks, 1):
        if not isinstance(check, dict) or not str(check.get("name") or "").strip():
            raise ReportError("check %d needs a 'name'" % i)
        if check.get("result") not in CHECK_RESULTS:
            raise ReportError("check %d (%s): result must be one of %s"
                              % (i, check["name"], ", ".join(CHECK_RESULTS)))
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ReportError("findings need a 'findings' list (empty when the review found nothing)")
    for i, f in enumerate(findings, 1):
        if not isinstance(f, dict):
            raise ReportError("finding %d must be an object" % i)
        if f.get("severity") not in SEVERITIES:
            raise ReportError("finding %d: severity must be one of %s" % (i, ", ".join(SEVERITIES)))
        if f.get("pass") is not None and f["pass"] not in PASSES:
            raise ReportError("finding %d: unknown pass %r" % (i, f["pass"]))
        if not str(f.get("file") or "").strip() or not str(f.get("claim") or "").strip():
            raise ReportError("finding %d needs a 'file' and a 'claim'" % i)
        if f["severity"] != "nit" and not str(f.get("failure") or "").strip():
            raise ReportError("finding %d (%s %s): no 'failure' scenario, so it is a hunch, not a finding; "
                              "prove it or drop it" % (i, f["severity"], f["file"]))
    failed = [c["name"] for c in checks if c["result"] == "fail"]
    if failed and not any(f["severity"] == "blocker" for f in findings):
        raise ReportError("check %s failed: a red check is a blocker finding, with the failing command "
                          "and its first errors as the failure" % ", ".join(failed))
    return data


def judge(data: Dict[str, Any]) -> Dict[str, Any]:
    order = {s: n for n, s in enumerate(SEVERITIES)}
    findings = sorted(data["findings"], key=lambda f: order[f["severity"]])
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    verdict = "request-changes" if any(counts[s] for s in BLOCKING) else "approve"
    return {"target": data.get("target"), "commit": data.get("commit"), "passes": list(data["passes"]),
            "checks": list(data.get("checks", [])), "verdict": verdict, "counts": counts, "findings": findings}


def save_dir() -> str:
    return os.environ.get("TS_REVIEW_SAVE_DIR") or os.path.join(os.path.expanduser("~"), "Documents", "code_reviews")


def save(result: Dict[str, Any]) -> str:
    """Write a request-changes result as JSON and return its path; the name is the target and the commit."""
    plain = lambda s: re.sub(r"[^A-Za-z0-9._-]+", "-", str(s or "")).strip("-.")  # noqa: E731
    name = "%s-%s.json" % (plain(result.get("target")) or "review", plain(str(result.get("commit") or "")[:7]) or "unknown")
    folder = save_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def where(f: Dict[str, Any]) -> str:
    return "%s:%s" % (f["file"], f["line"]) if f.get("line") else f["file"]


def render(result: Dict[str, Any]) -> str:
    label = {"approve": "APPROVE", "request-changes": "REQUEST CHANGES"}[result["verdict"]]
    lines = ["TypeScript review: **%s**" % label + (" — %s" % result["target"] if result.get("target") else ""), ""]
    lines.append("Reviewed commit `%s`; passes: %s." % (result.get("commit") or "unknown", ", ".join(result["passes"])))
    if result["checks"]:
        lines.append("Checks: %s." % "; ".join(
            "%s %s" % (c["name"], c["result"]) + (" (`%s`)" % c["command"] if c.get("command") else "")
            for c in result["checks"]))
    if result["verdict"] == "request-changes":
        lines.append("Fix the blockers and majors below; the minors are worth fixing in the same change.")
    real = [f for f in result["findings"] if f["severity"] != "nit"]
    nits = [f for f in result["findings"] if f["severity"] == "nit"]
    if not real:
        lines += ["", "No findings that would break: nothing a concrete input turns into a wrong result."]
    for f in real:
        tag = " (%s)" % f["pass"] if f.get("pass") else ""
        lines += ["", "**%s**%s `%s` — %s" % (f["severity"], tag, where(f), str(f["claim"]).strip())]
        for key, name in (("why", "Why"), ("failure", "Failure"), ("fix", "Fix")):
            if str(f.get(key) or "").strip():
                lines.append("- %s: %s" % (name, str(f[key]).strip()))
    if nits:
        lines += ["", "Nits (optional, never blocking): " + "; ".join(
            "`%s` %s" % (where(f), str(f["claim"]).strip()) for f in nits)]
    marker = {"verdict": result["verdict"], "commit": result.get("commit") or "unknown"}
    lines += ["", "<!-- typescript-review:verdict %s -->" % " ".join("%s=%s" % kv for kv in marker.items())]
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
    if result["verdict"] == "request-changes":
        try:
            print("review_report: saved %s" % save(result), file=sys.stderr)
        except OSError as exc:
            print("review_report: not saved (%s)" % exc, file=sys.stderr)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render(result), end="")
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
