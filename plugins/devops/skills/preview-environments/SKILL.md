---
name: preview-environments
description: Gives every pull request its own review link — a running preview of the PR's head commit — on a free host picked for the stack (Cloudflare Pages for static frontends, Render for backends), optionally served at <branch>.<slug>.<review domain>, published the same way whatever the host as a GitHub Deployment, one sticky PR comment and one comment on each ticket the PR closes saying which commit the link serves, taken down when the PR closes, and proved with a real PR whose link answers. Use when asked for PR previews, preview or review links, deploy previews, ephemeral or staging environments per pull request, or a link QA can test a PR on.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.3.0"
---

# Preview environments

Every PR gets a link to a running build of its head commit. Whatever hosts it,
the link ends up in the same three places:

- a **GitHub Deployment** whose latest status has `environment_url`. Anyone
  can read it back with the shared `preview-link` skill;
- **one sticky PR comment**, updated on each push, never duplicated;
- **one comment on each ticket the PR closes**, edited on every deploy, with
  a hidden marker QA reads to pick the latest version:
  `<!-- devops:review-link link=<url> commit=<sha> pr=<N> state=live -->`,
  or `state=down` once the PR closes.

With a **review domain** set (repo variable `REVIEW_DOMAIN`), the link is
`https://<branch>.<slug>.<REVIEW_DOMAIN>`, the shape QA recognises, served
from the same preview. The flow is drawn in the devops plugin's
`docs/review-links.drawio`, in the source repository.

```bash
python ../ci-setup/scripts/stack_scan.py .                       # static or server? which provider?
python ../ci-setup/scripts/scaffold.py preview --project <name> --dry-run   # Cloudflare Pages
python ../ci-setup/scripts/scaffold.py preview --provider render --dry-run  # Render
python ../preview-link/scripts/preview_link.py --pr <N> --wait 600 --check  # the proof
```

## 1. Pick the host

| The scan says | Host | Preview URL | Free-tier limits |
| --- | --- | --- | --- |
| `kind: static` | **Cloudflare Pages** | `https://pr-<N>.<project>.pages.dev` | 500 builds a month, 1 at a time |
| `kind: server` | **Render** (web service, `plan: free`) | `https://<service>-pr-<N>.onrender.com` | 750 instance-hours a month; sleeps after 15 min idle, about 1 min to wake |
| a static frontend and an API | both: Pages for the frontend, Render for the API | two links | as above |

Details, the alternatives and why not Vercel are in
[references/providers.md](references/providers.md). If the repo already
deploys somewhere with its own previews, use those, and only make sure they
publish a GitHub Deployment.

## 2. The one-time setup, done by the repository owner

You can't do these steps, because each one needs an account login or a
secret value. List them in the report, with the exact commands, and stop
until they're done.

**Cloudflare Pages**
1. Create a free account.
2. Create the project once, from their own machine:
   `npx wrangler login`, then `npx wrangler pages project create <project> --production-branch <default branch>`.
3. Create an API token with the *Account › Cloudflare Pages › Edit*
   permission. Then add both secrets:
   `gh secret set CLOUDFLARE_API_TOKEN -R <owner>/<repo>` and
   `gh secret set CLOUDFLARE_ACCOUNT_ID -R <owner>/<repo>`.

**Render**
1. Create a free account and install the Render GitHub app on the repo.
2. Commit `render.yaml`, then connect it in the dashboard (*New › Blueprint*).
   PR previews are on in the Blueprint (`previews: generation: automatic`).
3. Point the preview's environment variables at test data. A preview copies
   the base service's variables, including its database URL.

Render needs no GitHub secret. It creates the GitHub Deployment itself.

**Review domain (optional, Cloudflare Pages only)**
1. The domain's zone is on Cloudflare (ticket: choosing and setting it up).
2. The API token also gets *Zone › DNS › Edit* on that zone only. Add the
   zone: `gh secret set CLOUDFLARE_ZONE_ID -R <owner>/<repo>`.
3. Set the variables. They aren't secrets, but `gh` 2.4 has no
   `gh variable`:
   `gh api -X POST repos/<owner>/<repo>/actions/variables -f name=REVIEW_DOMAIN -f value=<domain>`.
   `REVIEW_SLUG` (the middle label) defaults to the repo name.
4. Render previews can't take a custom domain, so they keep their
   `onrender.com` link. The ticket comment still carries it.

## 3. Write it

- **Cloudflare Pages:** `scaffold.py preview --project <name>` writes
  `.github/workflows/preview.yml`.
  - It builds with the repo's own commands and deploys with
    `wrangler pages deploy --branch=pr-<N>`.
  - With `REVIEW_DOMAIN` set, it adds `<branch>.<slug>.<REVIEW_DOMAIN>` as a
    Pages custom domain, with a proxied CNAME to `pr-<N>.<project>.pages.dev`
    (Cloudflare's "custom domain on a branch"). That address becomes the
    link. The branch name is cut to a DNS label: lowercase, `a-z0-9-`, at most
    63 characters.
  - It creates Deployment `preview-pr-<N>`, with `auto_inactive` so older
    pushes go inactive, and upserts the PR comment and the ticket comments.
    The tickets are the ones the PR closes (`Closes #N`). A ticket in another
    repo is skipped with a notice, because the token can't write there.
  - When the PR closes, it marks the Deployment inactive, removes the custom
    domain and its DNS record, and marks the ticket comments `state=down`.
  - A fork PR gets no secrets, so its preview is skipped with a notice.
    Don't work around that with `pull_request_target`.
- **Render:** `scaffold.py preview --provider render` writes `render.yaml`
  and `.github/workflows/review-link.yml`. Render deploys by itself. The
  workflow runs on Render's `deployment_status`, and carries the link to the
  tickets, marking it down when the PR closes.
- **The host is checked on every PR.** Each file starts with
  `# devops:preview kind=<kind> provider=<provider>`, the stack it was set up
  for. The scan is copied into the repo as `.github/devops/stack_scan.py`
  (commit it with the workflow). Every PR runs
  `stack_scan.py . --expect <kind>`, which fails with a `devops:stack-changed`
  error naming the new kind once the repo has become the other one, for
  example a Next.js app that dropped `output: "export"` for a database. A scan
  that can't tell only warns.
  The copy starts with lint and format opt-outs (`# flake8: noqa`,
  `# ruff: noqa`, `# fmt: off`), so the repo's own checks stay green.
- **Changing host.** When that check fails, run this skill again; the error
  says which case it is.
  - **Another host** (static ↔ server): scaffold the scan's provider. It
    removes the old provider's files (only files this script wrote) and
    prints the new link shape. Put that in the report, since QA's links
    change. Moving to Render needs the owner's steps above first.
  - **Same host, new kind** (a Render static site that became a server):
    scaffold the same provider. It rewrites its own files for the new kind
    without `--force`; a file without the record line is still left alone.
  - **A static frontend that grew an API** (`static+api`: express, hono…
    in its runtime dependencies): the frontend stays on Pages, rewritten for
    `kind=static+api`, and the API gets its own Render preview, as in the
    table's "a static frontend and an API" row.
- The app must work from the root of its own host. If it has a hardcoded base
  path or an absolute API URL, make the API URL a build-time variable.
- Same rules as `ci-setup`: least-privilege `permissions` (the preview job
  needs `deployments: write`, `issues: write` and `pull-requests: write`,
  nothing else), pinned
  major versions, and `actionlint` when it's installed.

## 4. Prove it

Not done until all of these are true, and each is in the report:

1. A test PR on the target repo.
2. A green preview run: `gh run watch`.
3. `preview_link.py --pr <N> --wait 600 --check` returns **current**, with
   HTTP 2xx. This is the same lookup QA will use.
4. Push one more commit. The link follows it (the `sha` changes), and the PR
   has one comment, not two.
5. The PR's ticket has one review-link comment, whose commit is the new
   head. `review_link.py --issue <ticket> --pr <N>` (QA's script) says
   `test`, not `wait`.
6. With a review domain: the link is `https://<branch>.<slug>.<domain>` and
   answers over HTTPS. The first time, the certificate can take a few
   minutes.

Close the test PR. Check that the Deployment went inactive, the ticket
comment says taken down, and, with a review domain, the custom domain and its
DNS record are gone.

## Report

```
Repo:      <owner/repo>
Host:      <provider> — why (scan: <kind, framework>)
Replaced:  <the old provider's files removed, and the new link shape> | nothing
Wrote:     <files>  (actionlint: clean | not installed)
Owner to do: <account, project and secret steps still open, or none>
Review domain: <domain> (slug <slug>) | not set
Proof:     PR <link> — run <link> — preview <url> @ <sha>, HTTP <code>; follows new pushes: yes/no
Ticket:    <ticket link> — review-link comment @ <sha>; review_link.py says <action>
```
