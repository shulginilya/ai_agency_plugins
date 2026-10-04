---
name: platform-search
description: Searches one freelance or job platform — Upwork, Arc, Contra — for postings that fit the declared profile, drops the ones already seen, under the rate floor or re-posted, screens the rest, and returns a ranked shortlist without applying to anything. Use when the user asks to search, find gigs, look for jobs or contracts, check a platform for new work, or run a search on Upwork, Arc or Contra.
license: MIT
metadata:
  author: ilya-shulgin
  version: 0.1.0
---

# Platform search

A search run has one product: a short list of postings worth the user's next
hour, each with the reason it made the list. Everything else — the hundred
results that were never going to work, the ones already looked at last week,
the same job posted three times — is filtered before the user sees it.

A search **never applies, bids, drafts or messages**. It reads. Drafting is the
`application-tailoring` skill's job, and only for a posting the user picked.

## 1. Plan from the profile

```bash
python scripts/search_log.py plan <platform>
```

This reads `.jobhunt/profile.json` and prints the queries (role phrases built
from the declared titles), the stack, the rate floor and target, the hours cap,
the deal-breakers, the result limit and the mode. Exit 2 means there is no
profile: stop and build one with the user — do not search against a guess.

If the user named a query (`/search upwork "LLM agents"`), pass `--query`.
If the platform is not in the profile's `search.platforms`, say so and ask
before searching it.

## 2. Search the platform the way it can be reached

Load the platform's reference before the first search of a session — it says
how to reach that platform, which filters work, what the filters do not do,
and the red flags particular to it:

- [references/upwork.md](references/upwork.md)
- [references/arc.md](references/arc.md)
- [references/contra.md](references/contra.md)

The order of preference for access is the same everywhere: an official
connector, then job-alert emails in the user's mailbox, then the public job
board, then a browser session the user signed in to. Never ask for, type or
store a password. If no route works, say which one failed and stop — do not
switch to a less appropriate route on your own.

Collect more candidates than the limit — roughly two to three times — because
filtering removes many. Search by role phrase, not by single technology word:
"Vue" as a title search returns nothing; "Frontend Developer" returns Vue work.

## 3. Normalise and filter

Write every candidate to a JSON list in the shape the script documents (`id`,
`title`, `url`, `client`, `rate`, `hours`, `proposals`, `posted`, `applied`,
`summary`), then:

```bash
python scripts/search_log.py filter <platform> candidates.json > filtered.json
```

The script drops what is already seen on this platform, anything already
applied to, deal-breakers, postings whose **posted maximum** is under the rate
floor, and a client's repeat posting of the same job. It flags — but keeps —
fixed-price work, missing rates, rates in another currency and rates barely
above the floor. Exit 1 means nothing survived: report that honestly, with the
counts per reason, rather than loosening the filters silently.

## 4. Check the survivors, then screen them

For the strongest candidates — never fewer than the top five — open the full
posting and read what a list view hides: whether someone is already hired or
offered, the client's real hiring record, required locations or languages,
mandatory extras (a video, a test), and the cost to apply.

Then judge each one on its own. With more than three, give each to its own
`screener` agent where the harness supports subagents; otherwise apply the
`opportunity-triage` skill to each in turn. Add the result to the posting as
`"verdict"` (`pursue`, `skip`, `unclear`) and a one-line `"note"`.

## 5. Record, then report

```bash
python scripts/search_log.py record <platform> filtered.json
```

This marks every candidate — reported and filtered — as seen, so the next run
shows only new postings, and writes `.jobhunt/searches/<date>-<platform>.md`.

Report to the user, at most `limit` postings, best first:

```
<Platform> — <n> worth a look (of <found> found, <filtered> filtered)
Blocker: <anything that stops applying at all — no credits, profile incomplete — or omit>

| # | Job (link) | Rate | Load | Why | Watch out |
...
Skipped: <one line per notable skip and why>
```

- **A blocker goes first.** No Connects on Upwork, a profile the platform
  will not let apply, a missing login — the user needs that before the list.
- **Below-floor and unclear postings are not padding.** If only two are worth
  it, report two.
- **Pursued postings go to the pipeline only when the user says so** — hand
  them to the `application-pipeline` skill with stage `sourced`.

## Mode

`profile.json` → `search.mode` is `draft` (default) or `submit`. It governs
what happens *after* a search, in `application-tailoring`: in `draft` nothing
is ever submitted; in `submit`, a proposal is submitted only after the user
approved that exact text. A search itself behaves identically in both modes.

## Adding a platform

Add `references/<name>.md` with the same sections as the others
(access, searching, reading a posting, normalising, red flags), and add the
name to `PLATFORMS` in `scripts/search_log.py`. Nothing else changes.
