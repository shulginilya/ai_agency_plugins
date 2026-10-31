#!/usr/bin/env python3
"""Write CI/CD files for a repository from what stack_scan.py found in it.

    scaffold.py ci      [--root .] [--branch main]                 .github/workflows/ci.yml
    scaffold.py preview [--root .] --provider cloudflare-pages --project NAME
                                                                   .github/workflows/preview.yml
    scaffold.py preview [--root .] --provider render [--name NAME] render.yaml (Render PR previews)
                                                                   + .github/workflows/review-link.yml

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

Host drift: every preview file starts with `# devops:preview kind=<k>
provider=<p>`, the stack it was set up for. The scan is copied into the repo as
.github/devops/stack_scan.py, and every PR runs `stack_scan.py --expect <k>`,
which fails with a `devops:stack-changed` error when the repo has become the
other kind. Scaffolding the other provider later removes the first one's files;
scaffolding the same provider for a new kind rewrites them (only files this
script wrote, so no --force is needed for those).

Review links: with the repository variable REVIEW_DOMAIN set, the Cloudflare
workflow also serves each preview at `<branch>.<slug>.<REVIEW_DOMAIN>` (slug:
REVIEW_SLUG, else the repository name) and publishes that as the link. Either
host keeps one comment on every ticket the PR closes, edited on each deploy,
with a `<!-- devops:review-link link=... commit=... pr=... state=live|down -->`
marker that QA reads. Secrets are referenced by name only.

Standard library only. Exit status: 0 written (or printed), 1 a file exists and
was left alone, 2 bad input, 3 something the file needs is unknown.
"""

from __future__ import annotations

import argparse
import json
import re
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
REVIEW_SECRETS = {"cloudflare-pages": ["CLOUDFLARE_ZONE_ID"], "render": []}  # only with REVIEW_DOMAIN
STEPS = ("lint", "typecheck", "test", "build")
MARKER = "<!-- devops:preview -->"
TICKET_MARKER = "<!-- devops:review-link"
SCANNER = Path(".github") / "devops" / "stack_scan.py"  # stack_scan.py, copied for the drift check
RECORD = "# devops:preview kind=%s provider=%s"
RECORD_RE = re.compile(r"^# devops:preview kind=(\S+) provider=(\S+)")
# The copy lives in someone else's repo: keep its linters and formatters off it.
SCANNER_HEADER = ("# Copied by the devops plugin (scaffold.py preview) for the per-PR preview host check.\n"
                  "# Regenerate it with the plugin rather than editing it here.\n"
                  "# flake8: noqa\n# ruff: noqa\n# pylint: skip-file\n# fmt: off\n")


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


def drift_step(kind: str, provider: str) -> List[str]:
    """Fail the preview, naming the new kind, when the repo is no longer the kind it was set up for."""
    return ["      - name: Check the stack still fits this host",
            "        run: python3 %s . --expect %s --host %s" % (SCANNER.as_posix(), kind, provider)]


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


# One comment per ticket the PR closes, edited on every deploy. QA's review_link.py
# reads the marker: which link, which commit it serves, and whether it is still up.
TICKETS_JS = """\
async function postToTickets({ prNumber, url, sha, state, run }) {
  const { owner, repo } = context.repo;
  const found = await github.graphql(`query($owner: String!, $repo: String!, $n: Int!) {
    repository(owner: $owner, name: $repo) { pullRequest(number: $n) {
      closingIssuesReferences(first: 20) { nodes { number repository { nameWithOwner } } } } } }`,
    { owner, repo, n: prNumber });
  const issues = found.repository.pullRequest.closingIssuesReferences.nodes;
  if (!issues.length) core.notice(`PR #${prNumber} closes no ticket, so no ticket gets the review link`);
  const marker = `TICKET_MARKER link=${url || 'none'} commit=${sha} pr=${prNumber} state=${state} -->`;
  const body = state === 'live'
    ? `${marker}\\n**Review link:** ${url}\\n\\nServes commit \\`${sha.slice(0, 7)}\\` of #${prNumber} · updated ${new Date().toISOString()} · [deploy run](${run})`
    : `${marker}\\n**Review link:** taken down, #${prNumber} is closed.`;
  for (const issue of issues) {
    if (issue.repository.nameWithOwner !== `${owner}/${repo}`) {
      core.notice(`#${issue.number} is in ${issue.repository.nameWithOwner}: this token can't comment there`);
      continue;
    }
    const comments = await github.paginate(github.rest.issues.listComments,
      { owner, repo, issue_number: issue.number, per_page: 100 });
    const mine = comments.find(c => c.user.type === 'Bot' && c.body.startsWith('TICKET_MARKER')
      && c.body.includes(` pr=${prNumber} `));
    if (mine) await github.rest.issues.updateComment({ owner, repo, comment_id: mine.id, body });
    else if (state === 'live') await github.rest.issues.createComment({ owner, repo, issue_number: issue.number, body });
  }
}
""".replace("TICKET_MARKER", TICKET_MARKER)

# Serve the preview at <branch>.<slug>.<REVIEW_DOMAIN>: a Pages custom domain plus a
# proxied CNAME to the PR's branch alias (Cloudflare's "custom domain on a branch").
DOMAIN_JS = """\
const pr = context.payload.pull_request;
const label = s => (s || '').toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/-+/g, '-')
  .replace(/^-+/, '').slice(0, 63).replace(/-+$/, '');
const host = `${label(pr.head.ref) || `pr-${pr.number}`}.${label(process.env.REVIEW_SLUG)}.${process.env.REVIEW_DOMAIN}`;
const target = `pr-${pr.number}.${process.env.PAGES_PROJECT}.pages.dev`;
async function cf(method, path, body) {
  const res = await fetch(`https://api.cloudflare.com/client/v4${path}`, { method,
    headers: { Authorization: `Bearer ${process.env.CLOUDFLARE_API_TOKEN}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok && data.success !== false, data };
}
const domains = `/accounts/${process.env.CLOUDFLARE_ACCOUNT_ID}/pages/projects/${process.env.PAGES_PROJECT}/domains`;
const records = `/zones/${process.env.CLOUDFLARE_ZONE_ID}/dns_records`;
const existing = ((await cf('GET', `${records}?type=CNAME&name=${host}`)).data.result || [])[0];
if (process.env.ACTION === 'down') {
  await cf('DELETE', `${domains}/${host}`);
  if (existing) await cf('DELETE', `${records}/${existing.id}`);
  return;
}
if (!(await cf('GET', `${domains}/${host}`)).ok) {
  const added = await cf('POST', domains, { name: host });
  if (!added.ok) { core.setFailed(`Pages refused ${host}: ${JSON.stringify(added.data.errors || added.data)}`); return; }
}
const record = { type: 'CNAME', name: host, content: target, proxied: true, ttl: 1,
  comment: `review link of PR #${pr.number}` };
const saved = existing ? await cf('PUT', `${records}/${existing.id}`, record) : await cf('POST', records, record);
if (!saved.ok) { core.setFailed(`DNS refused ${host}: ${JSON.stringify(saved.data.errors || saved.data)}`); return; }
core.setOutput('url', `https://${host}`);
"""

PUBLISH_JS = TICKETS_JS + """\
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
await postToTickets({ prNumber: pr.number, url, sha: pr.head.sha, state: 'live', run });
""".replace("MARKER", MARKER)

CLEANUP_JS = TICKETS_JS + """\
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
await postToTickets({ prNumber: pr.number, url: null, sha: pr.head.sha, state: 'down', run: '' });
""".replace("MARKER", MARKER)

# Render deploys previews itself and reports them as GitHub Deployments; this
# workflow carries each one to the PR's tickets, and marks them down on close.
RENDER_TICKETS_JS = TICKETS_JS + """\
const { owner, repo } = context.repo;
if (context.eventName === 'pull_request') {
  const pr = context.payload.pull_request;
  await postToTickets({ prNumber: pr.number, url: null, sha: pr.head.sha, state: 'down', run: '' });
  return;
}
const deployment = context.payload.deployment;
const status = context.payload.deployment_status;
const prs = (await github.rest.repos.listPullRequestsAssociatedWithCommit(
  { owner, repo, commit_sha: deployment.sha })).data.filter(p => p.state === 'open');
if (!prs.length) { core.notice('not a deploy of an open PR, so no ticket gets a review link'); return; }
for (const pr of prs) {
  await postToTickets({ prNumber: pr.number, url: status.environment_url, sha: deployment.sha, state: 'live',
    run: status.log_url || status.target_url || '' });
}
"""


def script_block(js: str) -> List[str]:
    return ["          script: |"] + ["            " + line if line else "" for line in js.splitlines()]


def cloudflare_workflow(facts: Dict[str, Any], project: str) -> str:
    if facts.get("kind") != "static":
        raise Unknown(["a static build (the scan says kind=%s; Cloudflare Pages serves built files only)"
                       % facts.get("kind")])
    need(facts, "install", "build", "output_dir")
    kind = stack_scan.preview_kind(facts)  # static, or static+api: the API is previewed elsewhere
    same_repo = "github.event.pull_request.head.repo.full_name == github.repository"
    lines = [
        RECORD % (kind, "cloudflare-pages"),
        "name: Preview",
        "",
        "# One preview per PR on Cloudflare Pages: https://pr-<N>.%s.pages.dev" % project,
        "# The review link is published as GitHub Deployment preview-pr-<N>, a sticky PR comment and",
        "# one comment on each ticket the PR closes (marker: devops:review-link), which QA reads.",
        "# With the repo variable REVIEW_DOMAIN set, the link is https://<branch>.<slug>.<REVIEW_DOMAIN>",
        "# (slug: variable REVIEW_SLUG, else the repo name), served from the same preview.",
        "# Secrets (added by the repo owner with gh secret set): %s; with REVIEW_DOMAIN also %s"
        % (", ".join(SECRETS["cloudflare-pages"]), ", ".join(REVIEW_SECRETS["cloudflare-pages"])),
        "",
        "on:",
        "  pull_request:",
        "    types: [opened, synchronize, reopened, closed]",
        "",
        "permissions:",
        "  contents: read",
        "  deployments: write",
        "  issues: write",
        "  pull-requests: write",
        "",
        "concurrency:",
        "  group: preview-${{ github.event.pull_request.number }}",
        "  cancel-in-progress: true",
        "",
        "env:",
        "  REVIEW_DOMAIN: ${{ vars.REVIEW_DOMAIN }}",
        "  REVIEW_SLUG: ${{ vars.REVIEW_SLUG || github.event.repository.name }}",
        "  PAGES_PROJECT: %s" % quote(project),
        "",
        "jobs:",
        "  deploy:",
        "    if: github.event.action != 'closed' && %s" % same_repo,
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 20",
        "    steps:",
    ]
    setup = setup_steps(facts)
    lines += setup[:1] + drift_step(kind, "cloudflare-pages") + setup[1:]
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
        "      - name: Serve it on the review domain",
        "        id: review",
        "        if: env.REVIEW_DOMAIN != ''",
        "        uses: %s" % ACTIONS["github-script"],
        "        env:",
        "          ACTION: up",
        "          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}",
        "          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "          CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}",
        "        with:",
    ]
    lines += script_block(DOMAIN_JS)
    lines += [
        "      - name: Publish the review link",
        "        uses: %s" % ACTIONS["github-script"],
        "        env:",
        "          PREVIEW_URL: ${{ steps.review.outputs.url || steps.deploy.outputs.pages-deployment-alias-url || "
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
        "      - name: Take the review domain down",
        "        if: env.REVIEW_DOMAIN != ''",
        "        uses: %s" % ACTIONS["github-script"],
        "        env:",
        "          ACTION: down",
        "          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}",
        "          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "          CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}",
        "        with:",
    ]
    lines += script_block(DOMAIN_JS)
    lines += [
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
    header = [RECORD % (facts["kind"], "render"),
              "# Render Blueprint. Connect it once in the Render dashboard (New > Blueprint).",
              "# Every PR gets its own preview instance, and Render publishes it as a GitHub Deployment,",
              "# which is where preview_link.py reads the review link from.",
              "# Previews copy the base service's environment variables: point them at test data."]
    return "\n".join(header + lines) + "\n"


def render_tickets_workflow(kind: str) -> str:
    same_repo = "github.event.pull_request.head.repo.full_name == github.repository"
    lines = [
        RECORD % (kind, "render"),
        "name: Review link",
        "",
        "# Render deploys every PR's preview and reports it as a GitHub Deployment. This carries the",
        "# link to each ticket the PR closes: one comment per ticket (marker: devops:review-link),",
        "# edited on every deploy and marked down when the PR closes. QA reads it.",
        "# On every push it also checks the stack still fits Render (job: stack).",
        "",
        "on:",
        "  deployment_status:",
        "  pull_request:",
        "    types: [opened, synchronize, reopened, closed]",
        "",
        "permissions:",
        "  contents: read",
        "  issues: write",
        "  pull-requests: read",
        "",
        "jobs:",
        "  stack:",
        "    if: github.event_name == 'pull_request' && github.event.action != 'closed'",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 5",
        "    steps:",
        "      - uses: %s" % ACTIONS["checkout"],
    ] + drift_step(kind, "render") + [
        "",
        "  tickets:",
        "    if: >-",
        "      (github.event_name == 'deployment_status' && github.event.deployment_status.state == 'success'",
        "      && github.event.deployment_status.environment_url != '')",
        "      || (github.event_name == 'pull_request' && github.event.action == 'closed'",
        "      && %s)" % same_repo,
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 5",
        "    steps:",
        "      - name: Post the review link to the PR's tickets",
        "        uses: %s" % ACTIONS["github-script"],
        "        with:",
    ]
    lines += script_block(RENDER_TICKETS_JS)
    return "\n".join(lines) + "\n"


# --- CLI ---------------------------------------------------------------------


PREVIEW_FILES = {
    "cloudflare-pages": [Path(".github") / "workflows" / "preview.yml"],
    "render": [Path("render.yaml"), Path(".github") / "workflows" / "review-link.yml"],
}
LINKS = {"cloudflare-pages": "https://<branch>.<slug>.<REVIEW_DOMAIN> (or https://pr-<N>.<project>.pages.dev)",
         "render": "https://<service>-pr-<N>.onrender.com (Render takes no review domain)"}


def ours(path: Path) -> bool:
    """A preview file this script wrote: the record line, or an older file's own markers."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return (text.startswith("# devops:preview ") or MARKER in text or TICKET_MARKER in text
            or text.startswith("# Render Blueprint."))


def recorded_kind(path: Path) -> Optional[str]:
    """The kind on a preview file's record line, or None for a file without one."""
    try:
        with path.open(encoding="utf-8") as handle:
            match = RECORD_RE.match(handle.readline())
    except OSError:
        return None
    return match.group(1) if match else None


def outdated(path: Path, kind: str) -> bool:
    """A preview file this script wrote for another kind of stack: safe to rewrite without --force."""
    found = recorded_kind(path) if path.is_file() else None
    return found is not None and found != kind


def replaced(provider: str, root: Path) -> List[Path]:
    """The other provider's preview files in the repo, which this preview replaces."""
    return [root / rel for other, files in PREVIEW_FILES.items() if other != provider
            for rel in files if (root / rel).is_file() and ours(root / rel)]


def plan(args: argparse.Namespace, facts: Dict[str, Any], root: Path) -> List[Tuple[Path, str]]:
    if args.what == "ci":
        return [(root / ".github" / "workflows" / "ci.yml", ci_workflow(facts, args.branch or default_branch(root)))]
    source = Path(stack_scan.__file__).read_text(encoding="utf-8")
    shebang, rest = source.split("\n", 1) if source.startswith("#!") else ("", source)
    scanner = (root / SCANNER, (shebang + "\n" if shebang else "") + SCANNER_HEADER + rest)
    if args.provider == "cloudflare-pages":
        if not args.project:
            raise Unknown(["--project (the Cloudflare Pages project name)"])
        return [(root / PREVIEW_FILES["cloudflare-pages"][0], cloudflare_workflow(facts, args.project)), scanner]
    if facts.get("kind") not in ("static", "server"):
        raise Unknown(["kind (static or server)"])
    return [(root / "render.yaml", render_blueprint(facts, args.name or root.name)),
            (root / PREVIEW_FILES["render"][1], render_tickets_workflow(facts["kind"])), scanner]


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
    kind = None
    if args.what == "preview":
        kind = stack_scan.preview_kind(facts) if args.provider == "cloudflare-pages" else facts["kind"]
    for path, text in files:
        rel = path.relative_to(root)
        if args.dry_run:
            print("--- %s\n%s" % (rel, text))
            continue
        was = recorded_kind(path) if kind and outdated(path, kind) else None
        if path.exists() and not args.force and path != root / SCANNER and not was:
            if path.read_text(encoding="utf-8") != text:
                print("exists, left alone (compare with --dry-run, replace with --force): %s" % rel)
                code = 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("rewrote %s (it was set up for kind=%s)" % (rel.as_posix(), was) if was else "wrote %s" % rel)
    stale = replaced(args.provider, root) if args.what == "preview" else []
    for path in stale:
        rel = path.relative_to(root).as_posix()
        if args.dry_run:
            print("would remove %s (the old preview's)" % rel)
        elif code == 0:
            path.unlink()
            print("removed %s (the old preview's)" % rel)
    if stale and code == 0:
        print("review links now look like %s: say so in the report, QA reads them from the ticket comment"
              % LINKS[args.provider])
    if kind == "static+api":
        print("the API (%s) isn't previewed by this workflow: give it its own Render preview "
              "(the preview-environments skill, 'a static frontend and an API')" % ", ".join(facts["api"]))
    secrets = SECRETS.get(args.provider or "", [])
    if args.what == "preview" and secrets:
        print("secrets the repo owner adds (never paste their values into a chat):")
        for name in secrets:
            print("  gh secret set %s -R <owner>/<repo>" % name)
        for name in REVIEW_SECRETS.get(args.provider or "", []):
            print("  gh secret set %s -R <owner>/<repo>   # only with a review domain" % name)
    if args.what == "preview" and args.provider == "cloudflare-pages":
        print("review domain (optional; a variable, not a secret):")
        print("  gh api -X POST repos/<owner>/<repo>/actions/variables -f name=REVIEW_DOMAIN -f value=<domain>")
    return code


if __name__ == "__main__":
    sys.exit(main())
