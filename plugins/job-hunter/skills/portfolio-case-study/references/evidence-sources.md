# What each source can prove

Write down a fact only if one of these sources supports it. When two disagree
(the README says "real-time", the code polls every 30 seconds), the code wins
and the user decides how to describe it.

| Claim | Codebase | Git history | Live app | Only the user |
| --- | --- | --- | --- | --- |
| What the product does | README, routes, domain model | — | ✅ best source | — |
| Who it is for | README, sometimes | — | ✅ landing copy | often |
| Languages and frameworks | ✅ manifests, file counts | — | hints only | confirm hints |
| Infrastructure and deploy target | ✅ IaC, Dockerfile, CI | — | CDN/host hints | if not in repo |
| Architecture | ✅ entry points, packages, service boundaries | — | — | the *why* |
| Testing and CI discipline | ✅ test files, workflows | — | — | — |
| Timeline | — | ✅ first/last commit | — | if history was squashed or migrated |
| The user's role and share | — | commit share, which areas they touched | — | ✅ always confirm |
| Team size | — | author count (lower bound) | — | ✅ |
| Users, revenue, performance, uptime | — | — | rarely, and marketing copy is not a measurement | ✅ only source |
| Why a decision was made | ADRs, comments, sometimes | commit messages, sometimes | — | ✅ |
| Whether it can be named or linked | — | — | public means linkable, not nameable as a client | ✅ always |

## Traps

- **`devDependencies` are not the product.** ESLint, Prettier and Jest are how
  it was built, not what it is built with. Mention testing as a practice, not
  as stack.
- **A dependency is not a feature.** `stripe` in `package.json` does not mean
  payments shipped; find the call site.
- **Author count is a floor.** Squash merges, bots and pair commits all hide
  people. Ask.
- **Commit share is not ownership.** Someone with 20% of commits may have
  designed the whole system. Someone with 80% may have done a migration. Look
  at *which* directories their commits touched (`git log --author=<x>
  --name-only`) before describing their part, and confirm with them.
- **Scaffolding looks like architecture.** A Next.js starter has an `api/`
  folder whether or not anyone designed an API.
- **Marketing copy on a live site** ("trusted by thousands") is the company's
  claim, not a measurement. Do not repeat it as the user's outcome.
- **A shallow clone** has partial history; say the dates are incomplete or
  clone with full history.
- **Forks and templates** carry someone else's commits and README. Check
  whether the first commits are the user's before crediting anything.
