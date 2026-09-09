---
name: application-tailoring
description: Writes the application for one specific posting — a freelance proposal or bid, a cover letter, or a CV variant — from the user's declared profile and their own reusable template, matching the posting's stated needs to evidence the user actually has. Use when the user asks to write or improve a proposal, bid, cover note, application or CV for a particular role or gig.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Application tailoring

A tailored application answers one question the reader is actually asking: *can
this person do the specific thing described in this posting, and how do I know?*
Everything that does not serve that is padding, and padding is what makes
applications interchangeable.

Do not write anything until the posting has been through the
`opportunity-triage` skill. Tailoring a posting you have not scored means
writing enthusiastically about a role that is a bad fit.

## What you need before drafting

1. **The posting**, in full. Not a summary of it.
2. **The profile** — `.jobhunt/profile.json` for the declared stack and titles.
3. **The user's own template**, if they have one. Reuse it; do not replace their
   voice with a generic one. Ask for it once and remember it exists.
4. **Evidence**: specific projects, numbers, systems the user has actually
   built. If you do not have these, ask. This is the one thing you cannot infer,
   and it is the entire value of the document.

If evidence is missing, ask for it rather than writing a placeholder. A draft
full of `[insert metric]` is not a draft; a draft with an invented metric is
worse, and the user may not catch it before sending.

## The shape

Match the length and register to the channel — a platform bid is 120–200
words, a cover letter is under one page, a cold email is shorter than both, and
a CV variant is a reordering rather than a piece of writing. The differences
that decide whether each gets read are in
[references/channels.md](references/channels.md); load it once you know which
channel this is.

```
1. The hook — the specific problem in their posting, in their words, and that
   you have solved it before. One or two sentences. No greeting theatre.
2. The evidence — two or three concrete things, each tied to a requirement they
   named. What was built, the constraint, the outcome.
3. The gap — where you do not match, handled in one clause, honestly. Skipping
   it reads as not having read the posting.
4. The ask — one clear next step, and your availability or start date.
```

For a CV variant: reorder and re-weight, never invent. Move the relevant roles
up, expand the bullets that match the posting's requirements, cut the ones that
do not. The facts stay identical across every variant.

## Rules

- **Never claim experience the user has not stated.** Not softened, not
  implied, not "familiar with". This is the one hard rule; everything else is
  taste.
- **Name the thing.** "Reduced p95 checkout latency from 1.8s to 400ms" beats
  "improved performance". If the user has no number, describe the system
  precisely instead — specificity, not statistics, is what is doing the work.
- **Mirror their vocabulary, not their buzzwords.** If they say "design
  system", do not write "component library". If they say "rockstar", do not.
- **Address the gap once and move on.** "I have not used Rust in production,
  though the concurrency work in X is the closest analogue" is enough. Do not
  apologise, and do not oversell the substitute.
- **Cut every sentence that would fit any other application.** "I am excited by
  your mission" is filler in every language. If a sentence survives being
  pasted into a different application, delete it.
- **No em-dash-heavy AI cadence, no "I am writing to express my interest".**
  Read the draft back as the user; if it does not sound like them, it is not
  finished.
- **Rates are the user's to set.** Quote the floor from their profile if they
  ask you to, but never negotiate, discount, or propose a number they have not
  agreed to.

## Before handing it over

State plainly: which requirements you matched to which evidence, which
requirement you could not match, and anything you had to ask the user to
confirm. Then record it with the `application-pipeline` skill — a sent
application with no row and no follow-up date is the failure this plugin
exists to prevent.
