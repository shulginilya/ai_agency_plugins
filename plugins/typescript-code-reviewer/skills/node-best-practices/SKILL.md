---
name: node-best-practices
description: Applies the Node.js best practices of goldbergyoni/nodebestpractices to a code review — error handling, input validation, security, testing, production readiness, the event loop and Docker — as checks that each name what the defect looks like in a diff and the failure it causes, so a practice becomes a finding only with a concrete failure scenario. Lists the practices a diff cannot show (style, naming, team process, tooling choice) as never findings. Use when reviewing Node.js or TypeScript server code, an Express, Fastify, Koa or NestJS service, a Next.js route handler or server action, a worker, a CLI, a Dockerfile for a Node app, or their tests, or when asked whether code follows Node.js best practices.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Node.js best practices for review

The [Node.js Best Practices](https://github.com/goldbergyoni/nodebestpractices)
guide (Yoni Goldberg and contributors, CC BY-SA 4.0) collects about a hundred
practices for building Node.js services. This skill turns the ones you can see
in code into review checks. Each check is written in this repo's own words and
cites the practice it comes from, so you can read the reasoning at the source.

The checks are in [references/checklist.md](references/checklist.md). Read it
before the pass.

## When it applies

- **In a TypeScript review** (`typescript-review`): the **node** pass applies
  the checklist on top of `references/node.md` whenever `ts_scope.py` tags a
  changed file `node`. The **tests** pass applies its Testing section to tests
  of node files. When the change touches a `Dockerfile` or compose file
  (`git diff --name-only <base>`), the node pass also applies the Docker
  section.
- **On its own**, when asked whether Node.js code follows best practices:
  read the code, apply every section, and report in the same finding shape.

## How a practice becomes a finding

A practice is a lead, not a rule. Breaking one is a finding only when you can
write its **failure scenario**: concrete inputs or state, and the crash, hang,
wrong result, data loss or exposure they produce in this code. Each check
names the failure to look for; find it here, or drop the check.

- "No `unhandledRejection` handler" is a finding when you can name the
  rejection that goes unhandled and what the process does next. It is not a
  finding as a missing line.
- "Use a mature logger" is not a finding. "This `console.log(req.body)` writes
  the password field to the log" is one, and it is the security check, not the
  logging one.
- A practice the code already meets another way (a validation library other
  than the one the guide names, a reverse proxy that limits body size) is met.
  Check the config, middleware and infrastructure files before you claim a gap.

Severity follows the review's own scale:

- **blocker**: a security exposure reachable from untrusted input; a crash
  or hang of the whole process on a normal path; data loss.
- **major**: wrong behaviour on a plausible path, such as a request that hangs,
  an error the client cannot act on, a deploy that drops in-flight requests,
  or a test that passes while the behaviour it names is broken.
- **minor**: a real defect on an unlikely path.

## Reporting

Use the finding shape of the pass you are in, and put the practice number in
the `why`: `Why: an error from the stream is never handled (Node.js best
practice 2.13)`. The number is the pointer; the failure scenario is the
finding.

## Rules

- **The failure, not the practice.** A finding that only says "this breaks
  practice 6.6" is a hunch. Drop it.
- **Practices that a diff cannot show are never findings.** The checklist's
  *Not findings* section lists them: style the formatter owns, naming, team
  process, and tooling and vendor choices.
- **The change, not the codebase.** Report what the diff adds or breaks. A
  gap that was already there is in scope only when the diff makes it worse or
  reachable.
- **The guide lags the runtime.** Where Node.js itself now covers a practice
  (an unhandled rejection exits the process since Node 15; Express 5 forwards
  async errors), judge the code against the runtime and versions in
  `package.json` and `engines`, not against the guide's wording.
