---
name: preview-link
description: Paused for QA — review links are out of the crew workflow for now, so QA never tests on a PR's preview deployment; it checks out the PR's head commit and tests locally. Still finds the review link of a pull request — the URL of its preview deployment, read back from GitHub's Deployments API — and says whether it was deployed from the PR's head commit, is still deploying, failed, is stale (an older commit) or doesn't exist, and optionally whether it answers. Use when asked for a PR's preview, review or staging link, to see whether an old preview is still up, to wait for a preview to come up, or to check that a preview deploy worked.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.2.0"
---

# Preview link

> **Paused for QA.** Review links are out of the crew workflow for now. QA
> checks out the PR's head commit and tests it locally
> (`review_link.py --local`); it never tests on a preview deployment or a
> pasted review link, even when this script reports one as `current`. Asked
> to test "the running build" of a PR, run the head commit locally instead,
> and say that review links are paused. DevOps' preview setup
> (`preview-environments`) is paused too. Reading a link for any other
> reason (is an old preview still up?) is fine.

A pull request's review link is the running build of its head commit. Every
preview, whatever hosts it, ends as a **GitHub Deployment** whose latest status
carries `environment_url`:

- the devops preview workflow creates one for environment `preview-pr-<N>`
  (Cloudflare Pages, and any other provider it deploys to);
- Render creates its own for each PR preview.

So the PR's preview link comes from the Deployments API, never from a PR
comment or a guess at a URL pattern. With a review domain set,
`environment_url` is the `<branch>.<slug>.<domain>` address.

When review links are on, QA looks on the *ticket* first: the devops
workflow keeps a comment there with the same link and the commit it serves,
and people may paste one. QA's `review_link.py` reads those. This skill is
the fallback when the ticket names no link, and the way to check which
commit a pasted link serves. While review links are paused, neither applies.

```bash
python scripts/preview_link.py --pr 42                 # the link, and whether it's current
python scripts/preview_link.py --pr 42 --wait 600      # poll until it is up or has failed
python scripts/preview_link.py --pr 42 --check --json  # also GET it and report the HTTP status
```

Add `--repo owner/name` outside the repository's checkout.

## Reading the result

| State | Meaning | What to do |
| --- | --- | --- |
| `current` | deployed from the PR's head commit | Use the URL. Exit 0. |
| `pending` | the head commit is still deploying | Wait with `--wait`, or come back later. |
| `failed` | the deploy of the head commit failed | Report it, with the log link the result gives. Don't test an older build instead. |
| `stale` | the only live preview is of an older commit | Wait for the new deploy. Testing it would test the wrong code. |
| `none` | no deployment for this PR | The repo has no preview workflow, it was skipped (fork PRs get no secrets), or the PR is closed. |

Every state but `current` exits 1. A gh failure exits 2.

## Rules

- **Record the commit.** A verdict or a screenshot from a preview is only as
  good as the commit it was deployed from. Quote the `sha` the result gives.
- **`--check` before relying on it.** A Render free service sleeps after 15
  minutes idle and takes about a minute to wake: a first slow answer is not a
  failure, a 4xx or 5xx is.
- **Never print, request or pass on a secret** to reach a preview. If a
  preview needs credentials (a protected deployment, a login), say so and
  ask for access.
