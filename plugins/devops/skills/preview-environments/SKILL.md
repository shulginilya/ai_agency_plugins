---
name: preview-environments
description: Gives every pull request its own review link — a running preview of the PR's head commit — on a free host picked for the stack (Cloudflare Pages for static frontends, Render for backends), published the same way whatever the host as a GitHub Deployment plus one sticky PR comment, taken down when the PR closes, and proved with a real PR whose link answers. Use when asked for PR previews, preview or review links, deploy previews, ephemeral or staging environments per pull request, or a link QA can test a PR on.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Preview environments

Every PR gets a link to a running build of its head commit. Whatever hosts it,
the link ends up in the same two places:

- a **GitHub Deployment** whose latest status has `environment_url`. That is
  what QA and everyone else reads, through the shared `preview-link` skill;
- **one sticky PR comment**, updated on each push, never duplicated.

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

## 3. Write it

- **Cloudflare Pages:** `scaffold.py preview --project <name>` writes
  `.github/workflows/preview.yml`.
  - It builds with the repo's own commands and deploys with
    `wrangler pages deploy --branch=pr-<N>`.
  - It creates Deployment `preview-pr-<N>`, with `auto_inactive` so older
    pushes go inactive, and upserts the comment.
  - When the PR closes, it marks the Deployment inactive.
  - A fork PR gets no secrets, so its preview is skipped with a notice.
    Don't work around that with `pull_request_target`.
- **Render:** `scaffold.py preview --provider render` writes `render.yaml`.
  There is no workflow to write.
- The app must work from the root of its own host. If it has a hardcoded base
  path or an absolute API URL, make the API URL a build-time variable.
- Same rules as `ci-setup`: least-privilege `permissions` (the preview job
  needs `deployments: write` and `pull-requests: write`, nothing else), pinned
  major versions, and `actionlint` when it's installed.

## 4. Prove it

Not done until all four are true, and each is in the report:

1. A test PR on the target repo.
2. A green preview run: `gh run watch`.
3. `preview_link.py --pr <N> --wait 600 --check` returns **current**, with
   HTTP 2xx. This is the same lookup QA will use.
4. Push one more commit. The link follows it (the `sha` changes) and the PR
   has one comment, not two.

Close the test PR and check that the Deployment went inactive.

## Report

```
Repo:      <owner/repo>
Host:      <provider> — why (scan: <kind, framework>)
Wrote:     <files>  (actionlint: clean | not installed)
Owner to do: <account, project and secret steps still open, or none>
Proof:     PR <link> — run <link> — preview <url> @ <sha>, HTTP <code>; follows new pushes: yes/no
```
