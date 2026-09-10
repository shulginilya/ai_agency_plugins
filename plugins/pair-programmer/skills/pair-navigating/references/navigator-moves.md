# Navigator moves

Three interruptions are worth making. Each has a version that works and a
version that gets the navigator tuned out.

## 1. The work has left the goal

The session said "make the webhook retry safely". The driver is now three files
into a logging refactor, because the logging was in the way.

**Works:** "We're in the logger now — is that on the way to retries, or is it
its own change?"

**Does not:** "You're off track." It is a verdict rather than a question, and
about a third of the time the detour genuinely was on the way.

The useful move is to make the choice explicit rather than to make it. Two
outcomes are fine — carry on with a widened scope, or park it — and one is not:
drifting there without anyone noticing.

## 2. Something is being assumed

The driver writes `response.json()["id"]` and moves on.

**Works:** "Does it always come back with an id, or only on the success path?"

**Does not:** "That'll break." Sometimes it will not, and a navigator who is
wrong twice in a row stops being listened to when they are right.

The best form is a question with a cheap answer — one the driver can settle in
ten seconds by looking. Assumptions that need a meeting to resolve are not
interruptions; they go into the journal as open questions and the work continues
around them.

## 3. A decision is being made silently

The driver picks a default: retries three times, backs off two seconds, drops
the event after that. Nothing announced it; it was typed.

**Works:** "Three retries then drop — is dropping right, or should it dead-letter?"
Then, whichever way it goes, record it with the reason.

**Does not:** letting it pass because it looks reasonable. Reasonable defaults
are exactly the ones nobody can explain later, and they are the ones that get
blamed in the incident review.

## What waits

- **Naming**, unless the name is actively wrong about what the thing does.
- **Style and formatting.** A linter does this without spending anyone's
  attention.
- **A neater way to write the same thing.** Refactor step, or review.
- **A better architecture for the whole feature.** If it is real, it deserves
  its own conversation, not the last ten minutes of this one.
- **Anything the tests would say for you.** Let them say it.

## Silence is a position

A navigator who says nothing for twenty minutes while the driver is in a good
run is doing the job. The instinct that something must be said to justify the
seat is the instinct that produces the forty-comment session.

Say nothing, and keep the journal current instead. The next question you ask
will land.

## When the driver is the agent

The roles invert when the human hands the keyboard over. The same three reasons
apply, and one more: **state the intent before typing.** One sentence of what is
about to change and why, then the change, then stop at the checkpoint. A driver
who writes four files and narrates afterwards has not been paired with; they
have been watched.
