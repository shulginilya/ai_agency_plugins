# What goes in the journal, and what does not

The journal is worth keeping only if reading it later is faster than
reconstructing the session. That sets a hard limit on what belongs in it.

## Record

**Decisions, with the reason.** "Queue the retries — they have to survive a
restart." The reason is the part that ages well; the decision alone is just the
code with extra steps.

**Rejected alternatives, with theirs.** This is the half almost everyone drops,
and the half that saves the most time. Six weeks later someone proposes cron
again; the journal says why not, and the conversation takes a minute instead of
an afternoon.

**Questions nobody could answer.** Not questions the pair answered in passing —
those became decisions or nothing. The ones that were parked: what the provider
actually sends, whether anything downstream depends on the old shape. Each one
is an assumption that has been made honest.

**The next step, kept current.** One line, concrete enough to act on cold:
"extract the backoff policy into `retry.py` and point both callers at it", not
"continue with retries".

**Facts that were expensive to learn.** The failure only appears with two
workers. The staging database has no index on that column. Anything that took
twenty minutes to find and would take twenty minutes to find again.

## Leave out

**Narration.** "Opened the file. Read the tests. They look fine." Nobody reads
this back, including the person who wrote it.

**What the diff already says.** The journal is for what the code cannot say
about itself. A list of the functions that changed is not that.

**Anything you would have to reconstruct.** A reason invented at the end of the
session is a plausible reason, not the real one, and it will be trusted as if it
were the real one. If the reason has been lost, record the decision without it
and say the reason is not recorded — an honest gap beats a confident fabrication.

**Praise, tone, and how the session felt.** Not because it does not matter,
but because it does not survive the read.

## Shape of a good entry

| Bad | Good |
| --- | --- |
| `decide "use a queue"` | `decide "queue the retries" --because "they must survive a restart"` |
| `next "keep going"` | `next "point both callers at retry.backoff and delete the inline sleep"` |
| `note "discussed idempotency"` | `ask "is the provider's webhook idempotent, or do we dedupe on our side?"` |
| `note "fixed the test"` | (leave out — the diff says this) |

## One goal per session

When the goal changes mid-session — and it does, usually because the first
change revealed the real problem — close the session and start another one.
A session with two goals cannot be checked for drift, cannot be handed over
cleanly, and its journal reads as two half-stories.
