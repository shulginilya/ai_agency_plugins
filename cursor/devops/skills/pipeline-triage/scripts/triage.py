#!/usr/bin/env python3
"""Say why a GitHub Actions run failed, and whose problem it is.

    triage.py --pr 42                 the failed runs of PR 42's head commit
    triage.py --run 39782599200       one run
    triage.py --log job.log           a saved job log (offline)
    ... --repo owner/name --json

For each failed job it finds the step that failed, cuts that step's part of the
log, pulls out the lines that carry the failure, and names a category:

    test        a test ran and failed                       -> developer
    build       compile, type or bundling error             -> developer
    lint        a linter or formatter refused the code      -> developer
    dependency  install or resolution failed                -> devops
    workflow    the workflow itself: syntax, an action, a missing secret,
                a token permission                          -> devops
    infra       runner, network, rate limit or timeout      -> devops (rerun once first)
    unknown     no known signature: read the excerpt         -> devops

Standard library only; needs an authenticated `gh` (any version with `gh api`).
Exit status: 0 nothing failed, 1 failures were triaged, 2 bad input or gh failed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OWNER = {"test": "developer", "build": "developer", "lint": "developer", "dependency": "devops",
         "workflow": "devops", "infra": "devops", "unknown": "devops"}
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
STEP = re.compile(r"^##\[group\]Run (.+)$")
EXCERPT_LINES = 12

# Checked in this order: the first category with a matching line wins, so the
# specific causes (a missing secret, a resolution error, a lint report) beat the
# generic ones (a failure count, an exit code) they also produce.
SIGNATURES: List[Tuple[str, List[str]]] = [
    ("workflow", [r"Invalid workflow file", r"Unable to resolve action", r"Unrecognized named-value",
                  r"Input required and not supplied", r"Resource not accessible by integration",
                  r"secret .* (is )?not (set|found|defined)", r"Authentication error \[code: 10000\]",
                  r"Required property is missing", r"Can't find 'action\.ya?ml'"]),
    ("infra", [r"The runner has received a shutdown signal", r"The operation was canceled",
               r"exceeded the maximum execution time", r"\bETIMEDOUT\b", r"\bECONNRESET\b", r"\bEAI_AGAIN\b",
               r"API rate limit exceeded", r"No space left on device", r"\b50[234] (Bad Gateway|Service|Gateway)",
               r"lost communication with the server"]),
    ("dependency", [r"npm (ERR!|error) (code )?(ERESOLVE|E404|ETARGET|ENOTFOUND)", r"ERR_PNPM_",
                    r"lockfile.*(needs to be updated|out of date|not up to date)", r"frozen-lockfile",
                    r"`npm ci` can only install packages when your package\.json and package-lock\.json",
                    r"ResolutionImpossible", r"No matching distribution found", r"Could not find a version",
                    r"error: failed to (download|resolve)"]),
    ("lint", [r"\d+ problems? \(\d+ errors?", r"^\s*\d+:\d+\s+error\s", r"Found \d+ errors?\.",
              r"would reformat", r"Code style issues found", r"[A-Z]+\d{3,4} .*\[\*\]"]),
    ("test", [r"^FAIL(ED)?[: ]", r"^\s*FAILED ", r"AssertionError", r"^E\s+assert ", r"Tests?:\s+\d+ failed",
              r"^\s*(✖|✗|×) (?!\d+ problems?)", r"--- FAIL:", r"\d+ (failed|failing)\b", r"expect\(received\)"]),
    ("build", [r"error TS\d+", r"SyntaxError", r"Module not found", r"Cannot find module",
               r"Could not resolve", r"Build failed", r"\berror\[E\d+\]", r"cannot find symbol",
               r"ModuleNotFoundError", r"ImportError"]),
]


# --- pure helpers (unit-tested) ---------------------------------------------


def clean(log: str) -> List[str]:
    return [TIMESTAMP.sub("", line.rstrip("\r")) for line in log.splitlines()]


def failed_section(lines: List[str]) -> Tuple[Optional[str], List[str]]:
    """The step that raised the first ##[error], and its lines."""
    start, name = 0, None
    for i, line in enumerate(lines):
        match = STEP.match(line)
        if match:
            start, name = i, match.group(1).strip()
        elif line.startswith("##[error]"):
            end = next((j for j in range(i + 1, len(lines)) if STEP.match(lines[j])), len(lines))
            return name, lines[start:end]
    return name, lines[start:]


def classify(lines: List[str]) -> Dict[str, Any]:
    body = [l for l in lines if not l.startswith("##[group]") and not l.startswith("##[endgroup]")
            and not re.search(r"\.\.\. ok$", l)]
    for category, patterns in SIGNATURES:
        regex = re.compile("|".join("(?:%s)" % p for p in patterns))
        hits = [l.strip() for l in body if regex.search(l)]
        if hits:
            return {"category": category, "owner": OWNER[category], "evidence": dedupe(hits)[:EXCERPT_LINES]}
    errors = [l.replace("##[error]", "").strip() for l in body if l.startswith("##[error]")]
    tail = [l.strip() for l in body if l.strip() and not l.startswith("##[")][-EXCERPT_LINES:]
    return {"category": "unknown", "owner": OWNER["unknown"], "evidence": dedupe(errors + tail)[:EXCERPT_LINES]}


def dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def triage_log(log: str) -> Dict[str, Any]:
    step, section = failed_section(clean(log))
    result = classify(section)
    result["step"] = step
    return result


# --- gh plumbing -------------------------------------------------------------


class TriageError(Exception):
    pass


def gh(path: str, raw: bool = False) -> Any:
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise TriageError("gh is not installed")
    if out.returncode != 0:
        raise TriageError("gh api %s: %s" % (path, (out.stderr or out.stdout).strip()))
    return out.stdout if raw else json.loads(out.stdout or "null")


def current_repo() -> str:
    out = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0 or not out.stdout.strip():
        raise TriageError("cannot tell the repository; pass --repo owner/name")
    return out.stdout.strip()


def runs_for_pr(repo: str, pr: int) -> List[Dict[str, Any]]:
    head = gh("repos/%s/pulls/%d" % (repo, pr))["head"]["sha"]
    runs = gh("repos/%s/actions/runs?head_sha=%s&per_page=50" % (repo, head))["workflow_runs"]
    return [r for r in runs if r.get("conclusion") in ("failure", "timed_out", "startup_failure")]


def triage_run(repo: str, run: Dict[str, Any]) -> Dict[str, Any]:
    jobs = gh("repos/%s/actions/runs/%d/jobs?per_page=100" % (repo, run["id"]))["jobs"]
    out = {"run": run["id"], "workflow": run.get("name"), "url": run.get("html_url"),
           "sha": (run.get("head_sha") or "")[:7], "conclusion": run.get("conclusion"), "jobs": []}
    if run.get("conclusion") == "startup_failure" or not jobs:
        out["jobs"].append({"job": None, "step": None, "category": "workflow", "owner": "devops",
                            "evidence": ["the run never started a job: the workflow file is invalid or "
                                         "an action it uses can't be resolved"]})
        return out
    for job in jobs:
        if job.get("conclusion") not in ("failure", "timed_out"):
            continue
        failed_step = next((s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"), None)
        if job.get("conclusion") == "timed_out":
            result = {"category": "infra", "owner": "devops", "evidence": ["the job hit its timeout-minutes"]}
        else:
            try:
                result = triage_log(gh("repos/%s/actions/jobs/%d/logs" % (repo, job["id"]), raw=True))
            except TriageError as err:
                result = {"category": "unknown", "owner": "devops", "evidence": ["log unavailable: %s" % err]}
        result["step"] = failed_step or result.get("step")
        result.update(job=job["name"], url=job.get("html_url"))
        out["jobs"].append(result)
    return out


# --- CLI ---------------------------------------------------------------------


def render(runs: List[Dict[str, Any]]) -> str:
    if not runs:
        return "No failed runs."
    lines = []
    for run in runs:
        lines.append("Run %s %s (%s, commit %s) %s" % (run["run"], run["workflow"], run["conclusion"], run["sha"],
                                                       run["url"] or ""))
        for job in run["jobs"]:
            lines.append("  %s / step: %s -> %s, for %s" % (job["job"], job["step"], job["category"], job["owner"]))
            lines += ["      %s" % e for e in job["evidence"]]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pr", type=int)
    source.add_argument("--run", type=int)
    source.add_argument("--log", help="a saved job log, triaged offline")
    parser.add_argument("--repo")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.log:
            result = triage_log(Path(args.log).read_text(encoding="utf-8", errors="replace"))
            result.update(job=Path(args.log).name, url=None)
            runs = [{"run": None, "workflow": None, "url": None, "sha": "?", "conclusion": "failure",
                     "jobs": [result]}]
        else:
            repo = args.repo or current_repo()
            found = runs_for_pr(repo, args.pr) if args.pr else [gh("repos/%s/actions/runs/%d" % (repo, args.run))]
            runs = [triage_run(repo, r) for r in found
                    if r.get("conclusion") in ("failure", "timed_out", "startup_failure")]
    except (TriageError, OSError) as err:
        print("triage: %s" % err, file=sys.stderr)
        return 2
    print(json.dumps(runs, indent=2) if args.json else render(runs))
    return 1 if any(r["jobs"] for r in runs) else 0


if __name__ == "__main__":
    sys.exit(main())
