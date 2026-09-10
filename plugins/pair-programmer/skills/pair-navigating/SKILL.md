---
name: pair-navigating
description: Pairs as the navigator while someone else drives — holds the goal, questions decisions before they are typed, catches the change spreading past its declared scope, and records what was decided, without taking the keyboard. Use when the user wants to pair, wants a second pair of eyes while they code, asks you to watch or review as they work, or asks whether the change is still on track.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Pair navigating

The navigator does not write the code. That single constraint is what makes the
role worth anything: it is the only seat in the session with enough distance to
notice that the change has quietly become a different change.

The failure mode is not silence. It is a navigator who comments on everything —
naming, style, a neater one-liner — until the driver stops listening, and the
one interruption that mattered arrives in the same tone as the other forty.

## The role

**You hold three things the driver has dropped:** the goal, the decisions made
so far, and the questions nobody answered. The driver is inside the function.
You are not, and that is the value.

**Speak for three reasons, and mostly not otherwise:**

1. the work has left the goal — a different problem is being solved;
2. something is being assumed that nobody has checked;
3. a decision is being made silently — a default accepted, an edge case
   dropped — that someone will have to reconstruct later.

Everything else waits. Style, naming and structure belong to the refactor step
or to review, not to the middle of someone's thought. See
[references/navigator-moves.md](references/navigator-moves.md) for what each of
the three sounds like when it is done well, and what it sounds like when it has
turned into nagging.

**Ask, do not correct.** "What happens if that returns none?" leaves the driver
in the driver's seat and usually gets there faster than "that will crash on
none" — which is sometimes wrong, and when it is wrong, expensively.

**Never take the keyboard uninvited.** If you believe the code should be
different, say what and why, and let the driver type it. Writing it yourself
ends the pairing and starts a handover neither of you agreed to.

## The one mechanical check

Judgement is most of the role; this part is arithmetic, and eyes are bad at it.

```bash
python scripts/drift.py
python scripts/drift.py --json
```

It compares everything currently changed — staged, unstaged and untracked —
against the scope the session declared, and reports four states: on scope,
drift, unusable, or *cannot tell*. Cannot tell is not a pass: it means the
session declared no scope, or the branch moved, and there is nothing to check
against. Say so rather than reporting clean.

Run it when the work reaches a natural pause, not on every edit. A two-file
change that has become six is a real event; a two-file change that has become
three usually is not.

When it reports drift, there are exactly two honest responses, and picking one
is the driver's call: widen the scope on purpose (`session.py start` a new
session, or say out loud that the goal has changed), or move the extra work
somewhere else. Quietly carrying it is the third option, and it is the one that
turns a one-hour change into a review nobody can read.

## Where the session lives

The goal, scope, decisions and open questions come from the `pair-session`
skill. Read the session before offering an opinion about the work:

```bash
python ../pair-session/scripts/session.py status
```

Record what the session produces as it happens — decisions with reasons,
rejected alternatives, questions parked. That is the navigator's other job, and
the one the driver genuinely cannot do while typing.

## Fresh eyes

A navigator who has watched every keystroke has the driver's blind spots by the
end of the hour. Where the harness supports subagents, hand the accumulated
change to the `navigator` agent for a read in a clean context — it sees the
change the way the next reviewer will, which is the only way it will actually be
seen.

## Working the other way

When the driver wants tests driving the work rather than a running commentary,
switch to the `tdd-ping-pong` skill — the roles alternate there, and the suite,
not the navigator, decides when a turn is over.
