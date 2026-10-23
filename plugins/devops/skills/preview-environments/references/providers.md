# Preview hosts

Terms checked on 2026-10-19 and 2026-10-23. Free tiers change, so check the
provider's pricing page before relying on a limit.

| Provider | Hosts | Free tier | PR preview |
| --- | --- | --- | --- |
| **Cloudflare Pages** | static frontends, light Pages Functions | 500 builds a month per account, 1 concurrent build, unlimited static bandwidth. Functions share Workers Free limits (100k requests a day, 10 ms CPU). No card. | `wrangler pages deploy --branch=pr-<N>` gives `https://pr-<N>.<project>.pages.dev` |
| **Render** | Node and Python web services, static sites, free Postgres | 750 instance-hours a month. A free service sleeps after 15 minutes idle and wakes in about a minute. Previews are billed like their base service, so a free base gives free previews, which count against those hours. | built in: `previews: generation: automatic` in `render.yaml`. Render posts a GitHub Deployment per PR. |
| Netlify Free | static frontends, functions | 300 credits a month, hard cap. Deploy previews cost 0 credits, a production deploy costs 15, traffic uses credits. The site pauses when credits run out. | `https://pr-<N>--<site>.netlify.app` |
| Vercel Hobby | frontends, Next.js | 100 deployments a day. **Personal, non-commercial use only.** | automatic per PR |
| GitHub Pages | static only | free for public repos only. Private repos need Pro, Team or Enterprise. | No native PR previews: the `deploy-pages` `preview` input is still alpha and not public. `rossjrw/pr-preview-action` publishes to `/pr-preview/pr-<N>/` on a public site. |

## The choice

- **Static:** Cloudflare Pages. It has the most builds, no bandwidth cap, and
  previews by branch alias.
- **Static, already on Netlify:** keep Netlify. Previews cost no credits.
- **Server:** Render. It's the only free tier here with built-in PR previews
  of a backend.
- **Next.js with a server (no `output: 'export'`):** Render as a Node web
  service. Vercel's free tier forbids commercial use.
- **Avoid** GitHub Pages previews for private repos: the previews are public
  and the plan must be paid.

## How each host meets the contract

The contract: a GitHub Deployment per PR whose latest status has
`environment_url`, and one sticky comment.

| Host | Deployment | Comment |
| --- | --- | --- |
| Cloudflare Pages | created by `preview.yml`, environment `preview-pr-<N>`, `ref` = head SHA | `preview.yml` upserts it (marker `<!-- devops:preview -->`) |
| Render | created by Render | Render's own deployment entry on the PR. Add no comment. |
| Netlify | `netlify deploy --alias pr-<N> --json` in a workflow, then the same publish step as `preview.yml` | same publish step |

Any other host: deploy, read the URL from the deploy command's output, then
reuse the "Publish the review link" step from `preview.yml` unchanged.

## When the PR closes

- **Cloudflare:** `preview.yml` marks the Deployment inactive. The branch
  alias stays on Cloudflare until it's deleted in the dashboard. That's
  harmless, but it's public if the URL is known.
- **Render:** deletes the preview instance itself.

## Privacy

Every free preview URL here is public to anyone who has it. For a private
app:
- Cloudflare: put Cloudflare Access in front of `*.pages.dev` (free for up
  to 50 users).
- Render: put a login in the app itself.

Say which applies in the report.
