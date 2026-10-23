# devops

The crew's DevOps engineer. It sets up CI that runs a repository's own checks
on every pull request. It gives every PR a review link: a running preview of
the PR's head commit. When a run goes red, it says why and whose fix it is.
Its work is done when a real PR proves it: a green run and a link that
answers, not YAML that only looks right.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `ci-setup` | Scan the repo, write a GitHub Actions workflow from its own commands (least privilege, caching, concurrency, timeouts), prove it on a PR. Also deploy jobs and Dockerfiles |
| Skill | `preview-environments` | A preview per PR on a free host: Cloudflare Pages (static) or Render (server). Published as a GitHub Deployment and one sticky PR comment, taken down on close |
| Skill | `pipeline-triage` | The failed job and step, the lines that prove the cause, a category and an owner (developer or devops) |
| Skill (shared) | `preview-link` | Reads a PR's review link from the Deployments API: current, pending, failed, stale or none. QA uses the same skill. Source: `plugins/_shared/skills/` |
| Command | `/ci` | Set up or fix CI for a repo |
| Command | `/preview` | PR previews for a repo |
| Command | `/triage` | Why a run failed, and whose fix it is |

## The review-link contract

Every preview, whatever the host, ends as a **GitHub Deployment** whose latest
status carries `environment_url`:

- the Cloudflare workflow creates one for environment `preview-pr-<N>`;
- Render creates its own.

`preview_link.py --pr N` reads it back and reports it as current only when it
was deployed from the PR's head commit. QA tests on that link, and records
the commit.

## Secrets

The agent never sees, asks for, prints or writes a secret value. It lists
the secret names a workflow needs, and the repository owner adds each one
with `gh secret set NAME -R <owner>/<repo>`. It checks them with
`gh secret list`, which shows names only.

It has no ticket permissions. Findings that need a ticket go in its report,
for the developer or scrum-master to file.

## Scripts

All standard-library Python.

- `skills/ci-setup/scripts/stack_scan.py` reads what the repo declares:
  - its language and package manager, and the toolchain version;
  - its install, lint, typecheck, test and build commands;
  - the build output, and whether it is `static` or a `server`;
  - its existing workflows.

  What it can't tell goes under `UNKNOWN`. It exits 3 when the kind is
  unknown.
- `skills/ci-setup/scripts/scaffold.py` writes `.github/workflows/ci.yml`,
  `.github/workflows/preview.yml` (Cloudflare Pages) or `render.yaml`
  (Render) from the scan. It stops (exit 3) when something a file needs is
  unknown, and it never overwrites a file without `--force`. Action major
  versions live in its `ACTIONS` table.
- `skills/pipeline-triage/scripts/triage.py` triages failed runs by PR, by
  run or from a saved log. The categories are test, build, lint, dependency,
  workflow, infra and unknown.
- `../_shared/skills/preview-link/scripts/preview_link.py` finds the link,
  with `--wait` and `--check`.

`skills/preview-environments/references/providers.md` compares the free
hosts, and says how each one meets the contract.

**Out of scope:** Terraform, Kubernetes and cloud provisioning.

## Try it

```bash
python plugins/devops/skills/ci-setup/scripts/stack_scan.py path/to/repo
python plugins/devops/skills/ci-setup/scripts/scaffold.py ci --root path/to/repo --dry-run
python plugins/devops/skills/pipeline-triage/scripts/triage.py --pr 42
python plugins/_shared/skills/preview-link/scripts/preview_link.py --pr 42 --check
python -m tools.apkit test --plugin devops
```

## Install it

It's a crew plugin: `integrations/firstmate/deploy.sh --with-plugins`
installs it with the others.

## What degrades where

- **Claude Code and OpenCode** take everything.
- **Codex CLI, Cursor and Gemini CLI** take the skills and the commands.
- **Generic `.agents/skills`** takes the skills only. Each skill carries its
  own script, and `preview-environments` uses the `ci-setup` scripts next to
  it.
