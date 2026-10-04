---
name: portfolio-case-study
description: Writes a portfolio entry for one project — a case study for a portfolio site plus a CV bullet and a freelance-platform blurb — from the project's codebase or its live web app, using only facts read from the source or confirmed by the user. Use when the user gives a local project folder, a GitHub link or a web app URL and asks to describe, showcase or write up a project for their portfolio, CV, LinkedIn, Upwork or Malt profile.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.2.0"
---

# Portfolio case study

A portfolio entry has one job: make a stranger believe *this person built this
thing, and it was hard in an interesting way*. A feature list does not do that.
A description of the problem, the decisions and the result does.

The failure to avoid is fluency without facts. A model that has skimmed a repo
will happily write "architected a scalable microservices platform serving
thousands of users" about a single Express app with no users. That sentence
ends up in a CV, and the user gets asked about it in an interview.

## 1. Read the project

Work out which input you have, then gather facts from it — not impressions.

**A codebase** — a local project folder, or a git URL you clone read-only
into a temp directory. A local folder is read in place: never copy, move or
change it, and never delete it afterwards. If the path does not exist where you
are running — the folder is on the user's computer and you are not — use
whatever access to the user's files the harness gives you, or ask the user to
share that folder. Do not describe a folder you could not open.

```bash
python scripts/project_facts.py <dir> --author "<the user's name or email>"
python scripts/project_facts.py <dir> --author "<...>" --json
```

The script reports what can be counted: name and self-description, languages,
technologies from the manifests, infrastructure files, CI, tests, and git
history including the user's share of commits. Every technology comes with the
file that proves it. Exit codes: 0 usable, 3 thin, 2 unusable. *Thin* means
something decisive is missing — nothing says what the project is, or none of
the commits are the user's — and the output names it. Ask about that before
writing.

Then read the code the script points at, for what it cannot count: the entry
points, the domain model, the one or two parts that were clearly hard (a sync
engine, a permissions model, a pipeline, an unusual integration). Where the
harness supports subagents, hand a large codebase to `project-analyst` so the
reading does not fill this context.

**A live web app** (a URL): fetch the landing page and one or two inner pages
(features, pricing, docs). Record what the product does, for whom, and what a
visitor can see. Save the HTML and run `project_facts.py --page <file>` for
stack hints — but a page cannot tell you the backend, the user's role or any
outcome, and its framework fingerprints are unconfirmed. If the user can also
give the local folder or repo, read that too; the two together make the best
entry.

**Both** — a live URL and a local folder in one request (`<url> --path
<folder>`). Run the script on the folder and on the saved page, read both, and
let the code settle any disagreement: the page says what a visitor sees, the
folder says how it is built and who built it.

What each source can and cannot prove is in
[references/evidence-sources.md](references/evidence-sources.md). Load it on
the first project of a session.

## 2. Ask for what the project cannot tell you

Always ask, in one message, only the questions whose answers you do not have:

- **Role and scope** — solo, lead, or one of several? What did *they* design or
  decide, as opposed to implement?
- **The problem** — who was it for, and what was broken before it existed?
- **Outcomes** — users, customers, money, latency, time saved, uptime. If there
  are no numbers, what changed for whom?
- **Constraints** — deadline, team size, budget, legacy, compliance.
- **Visibility** — is it confidential? Can the client be named, the code be
  linked, screenshots be shown?

If the user has no metric, do not invent one and do not leave a placeholder.
Describe the system precisely instead; specificity carries the entry.

## 3. Write it

Use the structure and the three variants in
[references/case-study-format.md](references/case-study-format.md): the full
case study, a CV bullet, and a platform blurb. Match the register to where it
will be published.

Rules:

- **Every claim traces to a source**: a file, the commit history, the live
  page, or a sentence the user wrote. If you cannot say where a claim came
  from, cut it.
- **Stack lists only what the manifests or the user confirm.** A dependency in
  `devDependencies` is tooling, not "built with". A framework fingerprint from
  a page is a question, not a fact.
- **Scale words need numbers.** "Scalable", "high-traffic", "enterprise-grade"
  appear only next to the figure that earns them.
- **Credit honestly.** A 30% commit share on a five-person team is "one of
  five engineers; owned X", never "built".
- **Lead with the problem, not the stack.** The stack goes last and short.
- **Respect confidentiality.** If the client is under NDA, describe the
  industry and the problem, not the name — and never publish private repo links.
- **No AI cadence.** No "leveraged", "seamless", "robust", "cutting-edge", no
  triple-adjective openers. Read it back as the user would say it.

## 4. Save and hand over

Write the entry to `.jobhunt/portfolio/<project-slug>.md` so the
`application-tailoring` skill can cite it as evidence in later applications.
Then tell the user, plainly: which facts came from the code, which from the
page, which from them, and what you left out because nothing supported it.
Never publish or post the entry anywhere; the user does that.
