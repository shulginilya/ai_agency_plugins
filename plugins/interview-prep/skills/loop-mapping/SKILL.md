---
name: loop-mapping
description: Turns a job description, Notion page, recruiter email or scrappy notes about a role into the interview loop it implies and a risk-ranked prep plan — which rounds are stated, which are inferred, what each one will test, and what the candidate is weakest on. Use when the user shares a posting or company and asks how to prepare, what the interview will cover, what to expect, or what to study first.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Loop mapping

Preparation that is not aimed at a specific loop is just studying. The job here
is to convert whatever the user has about a role — a full description, a Notion
page, three lines from a recruiter — into two things: the rounds they will
actually sit, and the shortest list of things to fix before they do.

The failure mode is confident invention. A model asked "what will the interview
be like?" will produce a plausible five-stage loop for a company that runs two.
Every round in the output carries where it came from, and an inferred loop is
labelled inferred.

## 1. Get the input, in full

Accept: pasted text, a file, a URL, a Notion export, a recruiter email, or the
user's own notes from a call. Fetch a URL where the harness has a web tool; if
it cannot be fetched, ask for a paste rather than working from the title.

Save what you receive to a file (`.interview/jd/<company>.txt` is the
convention) so the scan and every later session read the same text.

Never map a loop from a job title alone. "Senior AI Engineer at a Berlin
scale-up" is not an input; it is a category.

## 2. Scan what is countable

```bash
python scripts/jd_scan.py .interview/jd/acme.txt
python scripts/jd_scan.py - --json          # paste on stdin
```

Four answers, and the last two are the useful ones:

| Exit | Verdict | What it means | What to do |
| --- | --- | --- | --- |
| 0 | mapped | stack and round signals both present | draft the loop from what is stated |
| 1 | thin | boilerplate; almost nothing concrete | ask for the real description before planning |
| 2 | unusable | empty or too short to read | get the text |
| 3 | unclear | the work is described, the process is not | draft the loop as *inferred*, and send the recruiter the questions |

The scan reports the stack by area, the seniority and leadership weight, the
company archetype, and the rounds the text admits to. It does not judge.

## 3. Read for what the scan cannot see

Load [references/jd-signals.md](references/jd-signals.md) on the first posting
of a session. The short version: which requirements are load-bearing and which
are a wishlist, what "you will own X" tells you the design round is really
about, and whether the seniority in the title matches the seniority in the
responsibilities. A posting that asks a senior engineer to "execute on a defined
roadmap" will not run a leadership round, whatever its title says.

## 4. Draft the loop

Work from [references/loop-patterns.md](references/loop-patterns.md) — the
archetypes, their usual loops, who sits in each, and the Berlin and EU-contract
specifics.

Every round in the draft is tagged:

- **stated** — the description or the recruiter said it
- **inferred** — this archetype and this role almost always run it
- **unknown** — likely, but you would be guessing at the format

Then hand it to the `prep-tracker` skill, so the plan survives the session —
it owns `.interview/state.json` and the script that writes it:

```bash
prep.py add --company Acme --role "Senior AI Engineer" \
  --source .interview/jd/acme.txt --archetype scale-up \
  --rounds recruiter-screen,live-coding,system-design,behavioral
```

If anything is tagged unknown, the first output of this skill is the message to
the recruiter asking for the loop. Two sentences, sent today, replaces a week of
preparing for the wrong round.

## 5. Rank the gaps, do not list them

A plan with fourteen items is a plan the user will abandon. Rank by risk:

**risk = how much of the loop tests it × how far it is from evidence the user
can already produce.**

Evidence means a story, a project, a repo or a number they have. Something they
have done but never articulated is a *medium* — it needs a rehearsal, not a
month. Something the loop is built on and they have never done is the only kind
of *high*.

Write the top three to five, no more:

```bash
prep.py item --company Acme --add "RAG eval story with real numbers" \
  --risk high --round system-design --due 2026-09-25
```

Dates come from the user. If they say "before the call next week", ask which day
or compute it and say which date you used.

## Rules

- **Label every inferred round.** The user will walk in expecting what you told
  them. Being wrong is survivable; being wrong confidently is not.
- **Do not pad the plan with what they are already good at.** A senior frontend
  engineer does not need a React refresher because the ad mentions React.
- **A missing requirement is a fact, not a verdict.** Report it and say whether
  the loop is built on it or merely lists it.
- **The plan has dates or it is a wish list.** Every item gets a day, tied to
  the round it serves.
- **Re-map after the first real round.** What was asked beats what was
  advertised — the `prep-tracker` skill's debrief feeds straight back here.
