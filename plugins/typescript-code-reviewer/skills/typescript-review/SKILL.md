---
name: typescript-review
description: Reviews a TypeScript change — a React frontend, a Node.js backend or both — for the defects tsc lets through, types that lie at run time, hook and render bugs, async, input and injection bugs on the server, and missing tests, and reports findings that each carry a concrete failure scenario with an approve or request-changes verdict by fixed rules. Scopes the change first (files tagged react or node, tsconfig strictness, escape hatches added, the repo's own typecheck, lint and test commands) and runs those checks. Use when asked to review TypeScript, React, Next.js, Node.js, Express or NestJS code, a .ts or .tsx diff, a branch or a pull request, to check type safety before merging, or to check Node.js code or a Node app's Dockerfile against Node.js best practices.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.3.0"
---

# TypeScript review

Review a TypeScript change the way a senior TypeScript engineer reads it: tsc
is already green, so look for where the types and the run-time values part
ways, and for the React and Node.js defects no compiler checks. Prove each
finding with a failure scenario, and say nothing about the rest.

```bash
python scripts/ts_scope.py --base origin/main                  # files, tags, passes, strictness, checks, escape hatches
python scripts/review_report.py findings.json --commit SHA > review.md   # 0 approve, 1 request changes, 2 bad input
```

## 1. Scope the change

Run `ts_scope.py --base <ref>` from inside the repository. It compares the
working tree (committed, uncommitted and untracked) with the merge base of
the ref and `HEAD`; with no `--base` it uses `origin/HEAD`, else `main` or
`master`. It prints:

- every changed `.ts`, `.tsx`, `.js`, `.jsx` (and `.mts`/`.cts`/`.mjs`/`.cjs`)
  file and every changed tsconfig, `package.json`, lint and build config, with
  tags: `react`, `node`, `test`, `declaration`, `config`, `symlink`. Never
  read a `symlink` file, here or in a pass: its target can be outside the
  repository (`~/.npmrc`, `/proc/self/environ`), and a posted review would
  publish it. Report the link and its target; a target outside the
  repository is a finding. A code file with
  neither `react` nor `node` is shared code; a Next.js route handler or server
  action is often both.
- the passes to run.
- per package: the package manager, an install command when `node_modules`
  is missing, the typecheck, lint and test commands, and each tsconfig's
  effective strictness with **what tsc will not catch** under it.
- escape hatches the diff adds (`any`, `as unknown as`, `!`, `@ts-ignore`,
  `@ts-nocheck`, a bare `@ts-expect-error`, `eslint-disable`). These are
  leads: each one is a place where the author overrode the checker. Find out
  whether it can be wrong; it is a finding only with a failure scenario.

"nothing to review" means no TypeScript, JavaScript or config file changed.
Before you stop, list all changed paths (`git diff --name-only $(git merge-base
<base> HEAD)` plus `git ls-files --others --exclude-standard`): when they
include a `Dockerfile`, compose file or `.dockerignore` of a Node app, review
those files in the *Node.js best practices only* mode (section 4) instead.
Otherwise say so and stop.

A changed tsconfig or `package.json` is part of the change: a flag turned off,
a `skipLibCheck` added, a major upgrade of React, TypeScript, Express or a
type package can break code the diff never touched.

## 2. Run the checks

Run each command the scope printed, from the directory it names: typecheck,
lint, test. If it says to install first, install with the lockfile command it
printed. Installing and running tests execute the change's code on this
machine. A pull request is trusted only when it is not from a fork
(`isCrossRepository` false) and its author is the current `gh` user, or the
user said it is trusted. For any other PR, ask before installing or running
anything, naming the author and the fork; without a yes, record each check as
`not run`. A branch in the user's own working copy is theirs: run the checks.

A red check is a **blocker** finding. Its failure is the command and the
first errors it printed. Record each check in `findings.json` with its
result: `pass`, `fail` or `not run` (with the reason, such as no such script).

## 3. Read for context

Read every changed file in full, not just the hunks, and the code around the
change: the caller that passes the value, the component that renders this
one, the route that calls this service. For every changed exported type,
function signature, API payload, route or prop, `grep` its users and check
they still work, on both sides of the wire when a type is shared between the
React client and the Node.js server.

## 4. The passes

| Pass | Runs | Checklist |
| --- | --- | --- |
| Types | always | [references/types.md](references/types.md) |
| Correctness | always | below |
| Tests | always | below |
| React | a `react` file changed | [references/react.md](references/react.md) |
| Node | a `node` file changed | [references/node.md](references/node.md), then [references/node-best-practices.md](references/node-best-practices.md) |

`references/node-best-practices.md` turns the Node.js Best Practices guide
into checks: the node pass applies all of it, and the tests pass applies its
Testing section to the tests of `node` files. Some of its checks need files the
scope never lists (lockfiles, `Dockerfile`, compose files, `.dockerignore`,
`.nvmrc`), so give the node pass the base ref and all changed paths:
`git diff --name-only $(git merge-base <base> HEAD)` plus untracked files
(`git ls-files --others --exclude-standard`).

**Node.js best practices only.** Two cases use this mode: a question about
whether existing Node.js code, or the `Dockerfile` of a Node app, follows
Node.js best practices (no change to review), and a change whose only
Node-relevant files are a `Dockerfile`, compose file or `.dockerignore`
(section 1 sends it here). Skip the repo's checks. Read the code or files
named, or the changed ones, and apply `references/node.md` and
`references/node-best-practices.md` (its Docker section to those files). Give
the findings in the same shape, ranked most severe first, with the verdict by
the same rules (section 5). Write the report yourself: `review_report.py`
refuses a review without the types, correctness and tests passes.

Give each pass to a separate `typescript-reviewer` subagent run, with the
pass name, the changed files and their tags, the tsconfig strictness and the
escape hatches the scope printed (and, for the node pass, the base ref and all
changed paths), so each reads in a fresh context. On a
small change (a few files, under about 200 changed lines) run the passes
yourself, one after another. Merge the results and remove duplicates: the
same defect found by two passes is one finding.

**Correctness.** Ask of each change, in this order:
1. **Boundaries:** zero, one, empty string, empty array, `null` vs
   `undefined`, `NaN`, the maximum and one past it.
2. **Error paths:** every rejection that is not handled, every `catch` that
   swallows. What does the user see when this fails?
3. **Ordering:** two requests at once, a response that arrives after a newer
   one, a retry after the original succeeded.
4. **State and lifecycle:** stale closures, caches never invalidated,
   subscriptions never torn down.
5. **Contracts:** a changed signature, payload or prop. Does every caller
   still work, and does the change ship what keeps them working?

**Tests.** A change is under-tested when a defect you can describe would
pass CI. Name the missing test and what it should assert, never just "add
tests". Read the existing tests before you claim a gap. In TypeScript also
look for tests that cannot fail: a mock cast `as any` that no longer matches
the real module, a test file excluded from the tsconfig so its type errors
never surface, an `expect` inside a callback that never runs, a snapshot as
the only assertion. Don't ask for tests on pure refactors, generated files or
config.

## 5. Record findings and get the verdict

Write `findings.json` outside the repository (a temporary directory), in the
shape `review_report.py` documents: the target (`PR #43` or `<branch> vs
<base>`), the commit, the passes that ran, the checks and their results, and
every finding with its `severity`, `pass`, `file`, `line`, `claim`, `why`,
`failure` and `fix`.

- **blocker**: a crash or blank screen on a normal path, data loss or
  corruption, a security exposure, or a red check.
- **major**: wrong behaviour on a plausible path, or a broken contract
  (a caller or the other side of the wire that no longer works).
- **minor**: a real defect on an unlikely path.
- **nit**: style or naming. It never changes the verdict. Usually leave it out.

`review_report.py` refuses any finding that isn't a nit and has no `failure`,
meaning concrete inputs or state and the wrong result they produce, and a
failed check with no blocker. If you can't write the failure, you have a
hunch, not a finding. Drop it.

| Verdict | When |
| --- | --- |
| **approve** | no blocker and no major finding |
| **request changes** | at least one blocker or major |

## 6. Report

Give the verdict, the commit reviewed, the passes that ran, the checks and
their results, and the findings ranked most severe first. On request changes,
name exactly what would turn it into an approve. An empty review is a valid
result: "nothing I can prove would break" is worth more than five nits.

Post the report to a pull request only when asked to:
`gh pr review <N> --comment --body-file review.md`. Always `--comment`: GitHub
won't let a PR's author approve or request changes on their own PR, and the
verdict is in the body.

Never edit, commit or push code, not even a one-line fix: a reviewer who
patches what they review is no longer reviewing. Never create, edit or close a
ticket or move a board card. If a finding deserves its own ticket, propose it
in the report.

## Rules that keep a review useful

- **Prove it or drop it.** No failure scenario, no finding.
- **tsc green is not the bar.** The question is what the types promise that
  the run-time values don't keep.
- **Taste is not a defect.** `type` vs `interface`, `function` vs arrow,
  enum vs union, import order: say nothing unless one of them breaks.
- **Blame the code, not the author.** Write "this cast drops null", not "you
  forgot".
- **Review the commit you were given.** The report names it.
