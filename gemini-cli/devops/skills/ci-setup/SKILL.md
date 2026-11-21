---
name: ci-setup
description: Sets up or repairs continuous integration for a repository on GitHub Actions — reads how the repo is actually built, tested and linted, writes a workflow that runs exactly those commands with least-privilege permissions, caching, a concurrency group and a timeout, and proves it with a green run on a real pull request. Also covers deploy workflows and Dockerfiles. Use when asked to set up CI, CI/CD, GitHub Actions or a pipeline for a repo, add checks to pull requests, fix or harden a workflow file, add a deploy step, or containerize an app.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# CI setup

A pipeline runs the commands the repository already declares, on every pull
request, and fails for the same reasons a developer's machine would. It is
done when a real PR has a green run, not when the YAML looks right.

```bash
python scripts/stack_scan.py .              # what the repo declares; exit 3 if it can't tell
python scripts/scaffold.py ci --dry-run     # the workflow it would write
python scripts/scaffold.py ci               # write .github/workflows/ci.yml
```

## 1. Read the repo

- Run `stack_scan.py`. It reports the language, package manager, toolchain
  version, the install, lint, typecheck, test and build commands the repo
  declares, the build output, and the workflows that already exist.
- Settle every `UNKNOWN` line by reading the repo (README, Makefile,
  `package.json`, `pyproject.toml`, existing workflows) or by asking. Pass the
  answer as `--install`, `--test`, `--build` and so on. Never invent a command
  the repo doesn't run.
- **An existing workflow wins.** If `.github/workflows/` already has CI, fix
  or extend it; don't add a second one that runs the same checks. `scaffold.py`
  never overwrites a file without `--force`.

## 2. Write the workflow

`scaffold.py ci` writes one job that installs and then runs lint, typecheck,
test and build, each only if the repo declares it. Whatever you write by hand
follows the same rules:

- **Triggers:** `pull_request`, and `push` to the default branch only.
- **`permissions: contents: read`** at the top. Grant a job more only when a
  step needs it, and say which step.
- **Never `pull_request_target`** to build or run PR code. It runs with
  secrets and a write token on code from anyone who opens a PR.
- **Pin actions to a major version** (`actions/checkout@v7`). Check the
  current one before writing: `gh api repos/actions/checkout/releases/latest --jq .tag_name`.
  The versions `scaffold.py` uses are in its `ACTIONS` table.
- **A concurrency group** per ref with `cancel-in-progress`, and
  `timeout-minutes` on every job.
- **Cache through the setup action** (`cache: npm`, `cache: pip`), from the
  lockfile. No lockfile means `npm install`, and the build is not
  reproducible: say so in the report.
- **The toolchain version comes from the repo** (`.nvmrc`, `.python-version`,
  `engines`, `requires-python`), not from the latest release.
- **Secrets by name only:** `${{ secrets.NAME }}`. See *Secrets* below.

When `actionlint` is installed, run it on every workflow you write and fix
everything it reports.

## 3. Prove it

1. Commit the workflow on a branch and open a PR (the `ship-change` skill, or
   the repo's own process).
2. Watch the run: `gh run watch` or `gh run list --branch <branch>`.
3. Red: run the `pipeline-triage` skill. A failure in the code is the
   developer's. A failure in the pipeline is yours, so fix it and push again.
4. Done means a green run on that PR, linked in the report.

## Deploys and Dockerfiles

- **A deploy job** runs on `push` to the default branch, or on a release,
  never on `pull_request`. Put it behind a GitHub Environment (`environment:
  production`) so it can carry its own secrets and required reviewers.
- **A Dockerfile** is multi-stage, from an official slim base pinned to a
  version, with the lockfile copied before the source so the install layer
  caches. It runs as a non-root user and listens on `$PORT`. Add a
  `.dockerignore` (`.git`, `node_modules`, `.env*`). Prove it with
  `docker build` and `docker run`, not by reading it.
- **Out of scope for now:** Terraform, Kubernetes and cloud provisioning. Say
  so, and propose a ticket instead.

## Secrets

You never see, ask for, print or write a secret's value. The repository owner
adds it:

```bash
gh secret set NAME -R <owner>/<repo>      # prompts for the value; nothing is echoed
```

- List the secret names a workflow needs, with where to create each value
  (which dashboard, which permission), and stop until they exist:
  `gh secret list -R <owner>/<repo>` shows names only.
- Never put a value in a workflow, a file, a commit, a command line or a
  report. If you find one committed, report it as an incident (rotate it,
  then remove it) rather than quietly deleting the line.

## Report

```
Repo:      <owner/repo> @ <branch>
Scan:      <kind, language, framework; unknowns and how they were settled>
Wrote:     <files>  (actionlint: clean | not installed)
Secrets:   <names the owner must add, or none>
Proof:     <PR link> — run <link> <green | red: triage summary>
Not done:  <anything left, and why>
```
