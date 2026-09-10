---
name: pair-session
description: Keeps a running record of a pairing session — the goal, the decisions and the ones rejected, the open questions, whose turn it is and the next step — so the work can be paused, resumed or handed to someone else without re-deriving it. Use when starting or resuming a pairing session, when a decision gets made mid-work, when a question comes up that nobody can answer yet, or when writing a handoff at the end.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Pair session

Two people pairing hold the whole session in their heads and lose most of it by
the next morning. An agent pairing with someone loses it at the end of the
context window, which is sooner. The journal is what survives.

It is not a transcript. A transcript of a pairing session is unreadable and
nobody writes one. Four things get recorded, and everything else is left out:

- **the goal**, in one sentence, stated before the work starts;
- **decisions**, each with the reason — and the alternatives that were rejected,
  with theirs;
- **open questions** — things nobody could answer, kept visible instead of
  quietly assumed;
- **the next step**, kept current, so a session that stops mid-thought can start
  again.

## 1. Open the session before the work

```bash
python scripts/session.py start --goal "make the webhook retry safely" \
  --scope src/webhooks --scope tests/webhooks \
  --test-command "pytest -q tests/webhooks" --mode pingpong
```

The goal is the load-bearing argument. Do not accept "let's look at the webhook
code" as a goal — ask what would be true at the end that is not true now, and
write that. A session whose goal is a location rather than an outcome cannot
drift, because it never pointed anywhere.

`--scope` is what the change is allowed to touch. It is what `pair-navigating`
checks against, and without it that check has nothing to say.

If a session is already open, the script refuses and tells you. Read it before
restarting — the usual reason is that yesterday's session was never closed, and
its next step is the one you want.

## 2. Record as you go, not at the end

```bash
python scripts/session.py decide "queue the retries" --because "they have to survive a restart"
python scripts/session.py reject "cron every 5 min" --because "worst case latency is 5 minutes"
python scripts/session.py ask "is the provider's webhook idempotent?"
python scripts/session.py next "extract the backoff policy"
```

`decide` and `reject` both require `--because`, and the requirement is the
point: a decision without its reason is indistinguishable from an accident three
weeks later, and the rejected alternatives are the half people always lose. When
someone reopens the question later, the record of *why not cron* is worth more
than the record of *we used a queue*.

Record a decision at the moment it is made, while the reason is still in
someone's mouth. Reconstructing reasons at the end of a session produces
plausible ones rather than true ones.

**Ask rather than assume.** When something cannot be answered in the session —
what the provider actually sends, whether anyone depends on the old behaviour —
record it with `ask` and keep working around it. An assumption that was written
down as a question is recoverable; one that was silently made is not. See
[references/journal-format.md](references/journal-format.md) for what belongs in
the journal and what does not.

## 3. Check the state when it matters

```bash
python scripts/session.py status
```

Four answers, not two: `0` open and clear, `1` something needs the pair
(unanswered questions, no next step, ping-pong with no test command), `2` no
usable session, and `3` *the journal may not describe the work in front of you*
— the branch changed, or the base commit is gone. That third state is the one
worth stopping for. Do not carry on against a journal that describes different
work; start a new session or say plainly that this one is stale.

## 4. Hand off before you need to

```bash
python scripts/session.py handoff        # writes .pair/handoff.md
python scripts/session.py close
```

Write the handoff while the session is still fresh, not once it has already
ended badly. The rendered file names the goal, the next step, every decision and
its reason, what was rejected, and the questions still open. If the next step is
missing, the handoff says so rather than inventing one.

The markdown is generated output. The session state is the JSON; edit that
through the script, never by hand-patching the rendered file.
