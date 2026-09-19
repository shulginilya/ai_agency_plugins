---
name: story-bank
description: Builds and maintains the bank of STAR stories a behavioral or leadership round is won from — pulls real situations out of the user's own history, writes them in first person with an outcome, checks coverage across the competencies interviewers actually ask about, and flags the ones that would not survive a follow-up. Use when the user asks for help with behavioral questions, STAR answers, "tell me about a time", leadership examples, or wants their stories reviewed.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Story bank

Behavioral rounds are not won by recall. Nobody produces a good story about
conflict, under pressure, from a standing start. They are won from a bank of
eight to twelve real situations, written down once, rehearsed lightly, and
mapped to the competencies that get asked.

The work here is extraction, not composition. Every fact comes from the user.

## 1. Interview the user for material

Ask for situations, not stories. People do not remember "a time I showed
leadership"; they remember the quarter the migration slipped.

Prompts that actually produce material:

- What is the thing you shipped that you would put on a slide about yourself?
- When did production break and you were the one on it?
- What did you argue for that the team did not want to do?
- What did you get wrong, and when did you find out?
- Who did you make better at their job? What did you actually do?
- What did you cut, and who was unhappy about it?
- When did you have to build something with no spec?

One situation at a time. Pull the detail out with follow-ups before writing
anything: what was at stake, what you personally did, what happened, how you
know.

## 2. Write it as they would say it

Load [references/star-format.md](references/star-format.md) for the shape and
the anti-patterns. The essentials:

- **Two minutes spoken.** Situation and task get 20 seconds together. Action
  gets the bulk. Result gets a number.
- **First person.** "We migrated" tells the interviewer nothing about the
  candidate. Every Action sentence has an "I" in it, and the team's part is
  named separately and honestly.
- **An outcome that can be checked.** A number, a before-and-after, or a
  concrete change. If the user does not have the number, the story says what
  changed and the action item is to find it — never a number you invented.
- **One sentence of reflection.** What they would do differently. Without it the
  story reads as polished rather than examined.

Then store it:

```bash
stories.py add --title "Halved checkout LCP" --competencies delivery,technical-decision \
  --situation "..." --task "..." --action "..." --result "..." --metric "LCP 4.1s -> 1.9s"
```

## 3. Check coverage, not volume

```bash
python scripts/stories.py check
```

Four answers, and the last two matter most:

| Exit | Verdict | Means |
| --- | --- | --- |
| 0 | covered | every competency has a story that would hold up |
| 1 | gaps | a competency has no story at all |
| 2 | unusable | no bank yet — run `stories.py init` |
| 3 | thin | covered, but some stories fail a quality rule |

The quality rules are mechanical on purpose: no situation, an action under 120
characters, an action with no "I" in it, a result with neither a number nor a
concrete change, no competency tagged. Each is a follow-up question waiting to
happen.

A competency listed under "covered only by a story that would not survive a
follow-up" is the most dangerous state in the bank — the user believes they are
covered there.

## 4. Reuse, adapt, never re-invent

One story serves several competencies. The migration story is delivery *and*
influence *and* scope, depending on which 20 seconds you lead with. Adapt the
framing to the question; never adapt the facts.

When a round is coming, pull the three or four stories that match its
competencies and rehearse those — [references/star-format.md](references/star-format.md)
has the follow-up ladder each story must survive.

## Rules

- **Never write a story the user did not live.** Not a composite, not a
  plausible reconstruction, not "something like this". A fabricated story
  collapses on the second follow-up and it is the only unrecoverable failure in
  an interview.
- **Never invent a metric.** "Roughly 30%" that the user said is fine; "30%"
  that you supplied is not.
- **Old stories decay.** A story from six years ago competing with one from last
  year loses. Flag anything predating the seniority being interviewed for.
- **Do not polish into corporate voice.** The interviewer is listening for a
  person. Keep their words, fix the structure.
- **Rehearse twice, not five times.** A recited answer reads worse than a rough
  one.
