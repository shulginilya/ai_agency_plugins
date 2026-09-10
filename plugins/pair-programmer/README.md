# pair-programmer

Pairs on code instead of taking it over. The plugin exists to make three things
cheap: staying in the navigator's seat while someone else drives, running a TDD
cycle where the suite rather than either partner decides when a turn is over,
and stopping mid-work without losing the session.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `pair-navigating` | Hold the goal, question decisions, catch the change spreading — without taking the keyboard |
| Skill | `tdd-ping-pong` | Alternate turns: failing test, smallest pass, refactor — gated on the suite's real state |
| Skill | `pair-session` | The journal: goal, decisions and reasons, rejected alternatives, open questions, next step |
| Command | `/pair` | Start or resume a session; settle goal, scope, test command and mode |
| Command | `/navigate` | One navigator pass over the work in progress |
| Command | `/pingpong` | Play the current turn and hand over if the suite allows |
| Command | `/handoff` | Render the handoff; name what is still open |
| Agent | `navigator` | Reads the accumulated change in a clean context, so it is seen from outside |
| Hook | `SessionStart` | Picks the session back up — silent when none is open |
| Hook | `PostToolUse` | Flags an edit that breaks turn discipline; never blocks |
| MCP | `pair-programmer` | Dependency-free stdio server: `session_status`, `drift_check`, `pair_playbook` |

## Setup

One file in the user's own repo, `.pair/session.json`, written by the script:

```bash
python skills/pair-session/scripts/session.py start \
  --goal "make the webhook retry safely" \
  --scope src/webhooks --scope tests/webhooks \
  --test-command "pytest -q tests/webhooks" --mode pingpong
```

Nothing in the plugin is personalised; the session is. The goal and scope are
what the drift check measures against, and the test command is what the
ping-pong gate runs — which is why `start` refuses ping-pong mode without one
rather than inventing a command.

## The scripts

```bash
# the journal — status exits 0 ok, 1 needs attention, 2 unusable, 3 stale
python skills/pair-session/scripts/session.py status
python skills/pair-session/scripts/session.py decide "queue the retries" --because "must survive a restart"
python skills/pair-session/scripts/session.py ask "is the provider's webhook idempotent?"
python skills/pair-session/scripts/session.py handoff        # renders .pair/handoff.md

# the ping-pong gate — state exits 0 GREEN, 1 RED, 2 UNUSABLE, 3 ERRORED
python skills/tdd-ping-pong/scripts/tdd.py state
python skills/tdd-ping-pong/scripts/tdd.py advance           # refuses a turn the suite does not earn

# the drift check — 0 on scope, 1 drift, 2 unusable, 3 cannot tell
python skills/pair-navigating/scripts/drift.py --json
```

### Four answers, not two

Each script returns four states, and in each case the extra two carry the work.

`tdd.py` separates **RED** (a test failed) from **ERRORED** (the suite never
reached a verdict — an import error, a timeout, or a run that collected zero
tests). Both of the errored cases masquerade as progress: a green with nothing
behind it, or an error mistaken for a legitimate red. A two-state model gets
both wrong, and a ping-pong session built on it stops being test-driven without
anyone noticing.

`drift.py` separates **drift** from **cannot tell** — no declared scope, or the
base commit is gone. Reporting that as clean is worse than reporting nothing.

`session.py status` separates **needs attention** from **stale**: a journal
whose branch moved underneath it describes different work, and carrying on
against it is the failure the exit code exists to prevent.

## Design notes

- **The journal is JSON; the handoff is rendered.** A journal parsed back out of
  prose loses an entry eventually. `.pair/session.json` is the state,
  `.pair/handoff.md` is output, and writes back up to `*.bak` first. A file that
  does not parse is refused, never replaced.
- **`decide` and `reject` require `--because`.** The reason is the half that
  ages well, and the rejected alternatives are the half everyone loses.
- **One home for each rule.** `status_report`, `is_test_path` and `assess` live
  in the skills that own them; the hooks and the MCP server import them rather
  than restating them, so a hook cannot disagree with its own command.
- **Both hooks are advisory and exit 0.** The `PostToolUse` check is silent
  outside ping-pong mode and silent when the edit fits the turn.
- **The navigator does not write code.** That constraint is the whole value of
  the seat, and it is stated in the skill, the command and the agent.
