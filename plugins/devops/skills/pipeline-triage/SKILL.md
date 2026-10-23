---
name: pipeline-triage
description: Triages a failing GitHub Actions run — finds the failed job and step, cuts the step's log down to the lines that carry the failure, names the cause (a failing test, a build, lint or dependency error, the workflow itself, or the runner and network) and who owns it, then fixes what belongs to the pipeline and hands code failures to the developer with the evidence. Use when CI is red, a check is failing on a PR, a workflow or deploy failed, a run is flaky or timed out, or asked why a pipeline broke.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Pipeline triage

A red check is either the code's fault or the pipeline's. Say which, with the
log lines that prove it, before touching anything.

```bash
python scripts/triage.py --pr 42          # every failed run of PR 42's head commit
python scripts/triage.py --run <run-id>   # one run
python scripts/triage.py --log job.log    # a saved log, offline
```

## 1. Look at the right run

- **Only the head commit counts.** `--pr` looks at runs of the PR's current
  head, so a red ✗ next to an old commit that a later push already fixed is
  not reported. If someone says "CI is failing", check this before anything
  else, and say what you checked.
- `startup_failure`, or a run with no jobs, means the workflow file itself is
  broken (syntax, an unknown action). Run `actionlint` on it.

## 2. Read the category

| Category | Owner | What to do |
| --- | --- | --- |
| `test` | developer | Hand over the failing test names and assertion lines. A test that only fails in CI (other OS, Python or Node version) is still the developer's: say which matrix leg fails and which passes. |
| `build`, `lint` | developer | Hand over the first error, with file and line. |
| `dependency` | devops | A lockfile out of date, a version that doesn't resolve, a registry error. Fix the install step or the lockfile, or hand the version conflict to the developer. |
| `workflow` | devops | A missing secret or input, a token permission (`Resource not accessible by integration`), an unknown action or a syntax error. Fix the workflow. A missing secret goes to the repository owner as a `gh secret set NAME` line. |
| `infra` | devops | A runner shutdown, a network error, a rate limit or a timeout. Rerun once (`gh run rerun <id> --failed`). If it fails the same way twice, it isn't flaky: look for the cause, such as a slow test or a missing cache. |
| `unknown` | devops | Read the excerpt and the full log (`gh run view <id> --log-failed`), then name the cause yourself. |

## 3. Rules

- **Don't make a check green by weakening it.** No `continue-on-error`, no
  skipped or deleted tests, no `|| true`, no lowered coverage threshold. If a
  check is wrong, say why and propose the change. Don't slip it in.
- **One rerun at most** before you call something flaky, and say that you
  reran it.
- **Never print secrets to debug a run.** Check that a secret exists with
  `gh secret list`, which shows names only. Never echo its value, even
  masked.

## Report

```
Run:      <workflow> <run link> (commit <sha>)
Failed:   <job> / <step> -> <category>, for <owner>
Evidence: <the lines from the log>
Action:   <fixed in <commit>, rerun <link> green> | <handed to developer: …> | <owner to add secret NAME>
```
