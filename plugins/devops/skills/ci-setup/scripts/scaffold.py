#!/usr/bin/env python3
"""Write CI/CD files for a repository from what stack_scan.py found in it.

    scaffold.py ci      [--root .] [--branch main]                 .github/workflows/ci.yml
    scaffold.py preview [--root .] --provider cloudflare-pages --project NAME
                                                                   .github/workflows/preview.yml
    scaffold.py preview [--root .] --provider render [--name NAME] render.yaml (Render PR previews)

Common options: --dry-run prints the files instead of writing them; --force
overwrites a file that exists (otherwise it is left alone and reported);
--install/--build/--test/--lint/--typecheck/--output-dir/--start override or
fill in what the scan reported, and anything still unknown that the file needs
stops the scaffold rather than being guessed.

Every workflow runs the repo's own commands, has least-privilege
`permissions`, a concurrency group and a timeout, and never uses
`pull_request_target`. The preview workflow publishes the review link as a
GitHub Deployment `preview-pr-<N>` plus one sticky PR comment, marks it
inactive when the PR closes, and skips PRs from forks (they get no secrets).
Secrets are referenced by name only.

Standard library only. Exit status: 0 written (or printed), 1 a file exists and
was left alone, 2 bad input, 3 something the file needs is unknown.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stack_scan  # noqa: E402

# Major versions, checked 2026-10-23. Bump them here; the skill says how to check.
ACTIONS = {
    "checkout": "actions/checkout@v7",
    "setup-node": "actions/setup-node@v7",
    "setup-python": "actions/setup-python@v7",
    "github-script": "actions/github-script@v9",
    "pnpm": "pnpm/action-setup@v6",
    "uv": "astral-sh/setup-uv@v10",
    "wrangler": "cloudflare/wrangler-action@v4",
    "bun": "oven-sh/setup-bun@v2",
}
SECRETS = {"cloudflare-pages": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"], "render": []}
STEPS = ("lint", "typecheck", "test", "build")
MARKER = "<!-- devops:preview -->"


class Unknown(Exception):
    def __init__(self, missing: List[str]):
        super().__init__(", ".join(missing))
        self.missing = missing


def default_branch(root: Path) -> str:
    out = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip().split("/", 1)[-1] if out.returncode == 0 and out.stdout.strip() else "main"


def need(facts: Dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if not facts.get(k)]
    if missing:
        raise Unknown(missing)


def quote(value: str) -> str:
    return json.dumps(value)


def scalar(value: str) -> str:
    """A command as a YAML value: plain when that is safe, double-quoted when YAML would misread it."""
    if ": " in value or " #" in value or value[:1] in "[]{}&*!|>'\"%@`#,?:-" or value != value.strip():
        return quote(value)
    return value


# --- shared step blocks ------------------------------------------------------


def setup_steps(facts: Dict[str, Any]) -> List[str]:
    """Checkout, toolchain and install, as YAML lines at step indent (6 spaces)."""
    lines = ["      - uses: %s" % ACTIONS["checkout"]]
    if facts["language"] == "node":
        manager = facts.get("package_manager") or "npm"
        if manager == "pnpm":
            lines.append("      - uses: %s" % ACTIONS["pnpm"])
            if facts.get("pnpm_version"):
                lines += ["        with:", "          version: %s" % quote(facts["pnpm_version"])]
        if manager == "bun":
            lines.append("      - uses: %s" % ACTIONS["bun"])
        else:
            lines += ["      - uses: %s" % ACTIONS["setup-node"], "        with:",
                      "          node-version: %s" % quote(str(facts.get("node_version") or "lts/*"))]
            if manager in ("npm", "pnpm", "yarn") and facts.get("install") != "npm install":
                lines.append("          cache: %s" % manager)
    elif facts["language"] == "python":
        if facts.get("package_manager") == "uv":
            lines += ["      - uses: %s" % ACTIONS["uv"], "        with:", "          enable-cache: true"]
        lines += ["      - uses: %s" % ACTIONS["setup-python"], "        with:",
                  "          python-version: %s" % quote(str(facts.get("python_version") or "3.12"))]
        if facts.get("package_manager") == "pip":
            lines.append("          cache: pip")
        if facts.get("package_manager") == "poetry":
            lines.append("      - run: pipx install poetry")
    if facts.get("install"):
        lines.append("      - run: %s" % scalar(facts["install"]))
    return lines


def run_step(name: str, command: str) -> List[str]:
    return ["      - name: %s" % name.capitalize(), "        run: %s" % scalar(command)]


# --- ci.yml ------------------------------------------------------------------


def ci_workflow(facts: Dict[str, Any], branch: str) -> str:
    if facts.get("language") not in ("node", "python"):
        raise Unknown(["language (node or python)"])
    need(facts, "install")
    checks = [s for s in STEPS if facts.get(s)]
    if not any(facts.get(s) for s in ("test", "build")):
        raise Unknown(["test or build command"])
    lines = [
        "name: CI",
        "",
        "on:",
        "  pull_request:",
        "  push:",
        "    branches: [%s]" % branch,
        "",
        "permissions:",
        "  contents: read",
        "",
        "concurrency:",
        "  group: ci-${{ github.ref }}",
        "  cancel-in-progress: true",
        "",
        "jobs:",
        "  checks:",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 20",
        "    steps:",
    ]
    lines += setup_steps(facts)
    for step in checks:
        lines += run_step(step, facts[step])
    return "\n".join(lines) + "\n"


# --- preview.yml (Cloudflare Pages) -----------------------------------------


PUBLISH_JS = """\
const pr = context.payload.pull_request;
const environment = `preview-pr-${pr.number}`;
const url = process.env.PREVIEW_URL;
if (!url) { core.setFailed('the deploy step returned no URL'); return; }
const { owner, repo } = context.repo;
const run = `${context.serverUrl}/${owner}/${repo}/actions/runs/${context.runId}`;
const deployment = await github.rest.repos.createDeployment({
  owner, repo, ref: pr.head.sha, environment, auto_merge: false, required_contexts: [],
  transient_environment: true, production_environment: false,
  description: `Preview of PR #${pr.number}`,
});
await github.rest.repos.createDeploymentStatus({
  owner, repo, deployment_id: deployment.data.id, state: 'success',
  environment_url: url, log_url: run, auto_inactive: true,
});
const body = `MARKER\\n**Preview:** ${url}\\n\\nCommit \\`${pr.head.sha.slice(0, 7)}\\` · [deploy run](${run})`;
const comments = await github.paginate(github.rest.issues.listComments,
  { owner, repo, issue_number: pr.number, per_page: 100 });
const mine = comments.find(c => c.user.type === 'Bot' && c.body.startsWith('MARKER'));
if (mine) await github.rest.issues.updateComment({ owner, repo, comment_id: mine.id, body });
else await github.rest.issues.createComment({ owner, repo, issue_number: pr.number, body });
""".replace("MARKER", MARKER)

CLEANUP_JS = """\
const pr = context.payload.pull_request;
const { owner, repo } = context.repo;
const deployments = await github.paginate(github.rest.repos.listDeployments,
  { owner, repo, environment: `preview-pr-${pr.number}`, per_page: 100 });
for (const d of deployments) {
  await github.rest.repos.createDeploymentStatus({ owner, repo, deployment_id: d.id, state: 'inactive' });
}
const comments = await github.paginate(github.rest.issues.listComments,
  { owner, repo, issue_number: pr.number, per_page: 100 });
const mine = comments.find(c => c.user.type === 'Bot' && c.body.startsWith('MARKER'));
const body = `MARKER\\n**Preview:** taken down, the PR is ${pr.merged ? 'merged' : 'closed'}.`;
if (mine) await github.rest.issues.updateComment({ owner, repo, comment_id: mine.id, body });
""".replace("MARKER", MARKER)


def script_block(js: str) -> List[str]:
    return ["          script: |"] + ["            " + line if line else "" for line in js.splitlines()]


def cloudflare_workflow(facts: Dict[str, Any], project: str) -> str:
    if facts.get("kind") != "static":
        raise Unknown(["a static build (the scan says kind=%s; Cloudflare Pages serves built files only)"
                       % facts.get("kind")])
    need(facts, "install", "build", "output_dir")
    same_repo = "github.event.pull_request.head.repo.full_name == github.repository"
    lines = [
        "name: Preview",
        "",
        "# One preview per PR on Cloudflare Pages: https://pr-<N>.%s.pages.dev" % project,
        "# The review link is published as GitHub Deployment preview-pr-<N> and a sticky PR comment.",
        "# Secrets (added by the repo owner with gh secret set): %s" % ", ".join(SECRETS["cloudflare-pages"]),
        "",
        "on:",
        "  pull_request:",
        "    types: [opened, synchronize, reopened, closed]",
        "",
        "permissions:",
        "  contents: read",
        "  deployments: write",
        "  pull-requests: write",
        "",
        "concurrency:",
        "  group: preview-${{ github.event.pull_request.number }}",
        "  cancel-in-progress: true",
        "",
        "jobs:",
        "  deploy:",
        "    if: github.event.action != 'closed' && %s" % same_repo,
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 20",
        "    steps:",
    ]
    lines += setup_steps(facts)
    lines += run_step("build", facts["build"])
    lines += [
        "      - name: Deploy to Cloudflare Pages",
        "        id: deploy",
        "        uses: %s" % ACTIONS["wrangler"],
        "        with:",
        "          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}",
        "          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "          command: >-",
        "            pages deploy %s --project-name=%s" % (facts["output_dir"], project),
        "            --branch=pr-${{ github.event.pull_request.number }}",
        "            --commit-hash=${{ github.event.pull_request.head.sha }}",
        "      - name: Publish the review link",
        "        uses: %s" % ACTIONS["github-script"],
        "        env:",
        "          PREVIEW_URL: ${{ steps.deploy.outputs.pages-deployment-alias-url || "
        "steps.deploy.outputs.deployment-url }}",
        "        with:",
    ]
    lines += script_block(PUBLISH_JS)
    lines += [
        "",
        "  fork:",
        "    if: github.event.action != 'closed' && !(%s)" % same_repo,
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - run: %s" % scalar('echo "::notice::No preview: pull requests from forks get no deploy secrets."'),
        "",
        "  cleanup:",
        "    if: github.event.action == 'closed' && %s" % same_repo,
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 5",
        "    steps:",
        "      - name: Take the review link down",
        "        uses: %s" % ACTIONS["github-script"],
        "        with:",
    ]
    lines += script_block(CLEANUP_JS)
    return "\n".join(lines) + "\n"


# --- render.yaml -------------------------------------------------------------


def render_blueprint(facts: Dict[str, Any], name: str) -> str:
    if facts.get("kind") == "static":
        need(facts, "build", "output_dir")
        build = " && ".join(c for c in (facts.get("install"), facts["build"]) if c)
        lines = ["services:", "  - type: web", "    name: %s" % name, "    runtime: static",
                 "    buildCommand: %s" % scalar(build), "    staticPublishPath: %s" % scalar(facts["output_dir"])]
    elif facts.get("kind") == "server":
        need(facts, "start")
        if facts.get("language") not in ("node", "python"):
            raise Unknown(["runtime (node or python)"])
        build = " && ".join(c for c in (facts.get("install"), facts.get("build")) if c) or None
        lines = ["services:", "  - type: web", "    name: %s" % name, "    runtime: %s" % facts["language"],
                 "    plan: free"]
        if build:
            lines.append("    buildCommand: %s" % scalar(build))
        lines.append("    startCommand: %s" % scalar(facts["start"]))
    else:
        raise Unknown(["kind (static or server)"])
    lines += ["    previews:", "      generation: automatic"]
    header = ["# Render Blueprint. Connect it once in the Render dashboard (New > Blueprint).",
              "# Every PR gets its own preview instance, and Render publishes it as a GitHub Deployment,",
              "# which is where preview_link.py reads the review link from.",
              "# Previews copy the base service's environment variables: point them at test data."]
    return "\n".join(header + lines) + "\n"


# --- CLI ---------------------------------------------------------------------


def plan(args: argparse.Namespace, facts: Dict[str, Any], root: Path) -> List[Tuple[Path, str]]:
    if args.what == "ci":
        return [(root / ".github" / "workflows" / "ci.yml", ci_workflow(facts, args.branch or default_branch(root)))]
    if args.provider == "cloudflare-pages":
        if not args.project:
            raise Unknown(["--project (the Cloudflare Pages project name)"])
        return [(root / ".github" / "workflows" / "preview.yml", cloudflare_workflow(facts, args.project))]
    return [(root / "render.yaml", render_blueprint(facts, args.name or root.name))]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("what", choices=["ci", "preview"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--provider", choices=["cloudflare-pages", "render"],
                        help="preview host; defaults to the scan's suggestion")
    parser.add_argument("--project", help="Cloudflare Pages project name")
    parser.add_argument("--name", help="Render service name (default: the folder name)")
    parser.add_argument("--branch", help="default branch (default: origin's HEAD, else main)")
    for key in ("install", "lint", "typecheck", "test", "build", "output-dir", "start"):
        parser.add_argument("--" + key, help="override the scanned %s command" % key)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print("scaffold: not a directory: %s" % root, file=sys.stderr)
        return 2
    facts = stack_scan.scan(root)
    for key in ("install", "lint", "typecheck", "test", "build", "output_dir", "start"):
        value = getattr(args, key)
        if value:
            facts[key] = value
    if args.what == "preview":
        args.provider = args.provider or facts.get("provider")
        if not args.provider:
            print("scaffold: the scan can't tell static from server; pass --provider", file=sys.stderr)
            return 3
    try:
        files = plan(args, facts, root)
    except Unknown as err:
        print("scaffold: unknown, so nothing was written: %s" % err, file=sys.stderr)
        for item in facts["unknowns"]:
            print("  scan: %s" % item, file=sys.stderr)
        return 3
    code = 0
    for path, text in files:
        rel = path.relative_to(root)
        if args.dry_run:
            print("--- %s\n%s" % (rel, text))
            continue
        if path.exists() and not args.force:
            if path.read_text(encoding="utf-8") != text:
                print("exists, left alone (compare with --dry-run, replace with --force): %s" % rel)
                code = 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % rel)
    secrets = SECRETS.get(args.provider or "", [])
    if args.what == "preview" and secrets:
        print("secrets the repo owner adds (never paste their values into a chat):")
        for name in secrets:
            print("  gh secret set %s -R <owner>/<repo>" % name)
    return code


if __name__ == "__main__":
    sys.exit(main())
