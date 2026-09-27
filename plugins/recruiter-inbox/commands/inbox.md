---
description: Work the recruiter inbox - sweep LinkedIn and Gmail, draft replies toward a first call, get your approval, send exactly what you approved.
argument_hint: "[nothing for a full run, or: sweep | send | setup]"
model: sonnet
---

Recruiter inbox: {{ARGS}}

With no argument, do a full run: setup check, sweep, approval, send. `sweep`
stops after the drafts are shown; `send` sends what is already approved;
`setup` only does step 1.

## 1. Setup check

```bash
python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" --json status
python "{{PLUGIN_ROOT}}/skills/inbound-triage/scripts/inbound.py" --init
```

If there is no ledger, run `threads.py init`. If `--init` wrote or extended the
profile, walk the user through the `replies` section before going further —
never fill it in for them:

- `name`, `languages`, `timezone`, `availability` (call slots you may offer)
- `send_mode`: `approve-then-send` (the actor clicks Send), `fill-only` (it
  types, they click), or `draft-only` (they paste). Tell them once, plainly,
  that LinkedIn's terms prohibit automated messaging and that any browser
  automation carries a risk of account restriction; the mode is their call.
- `salary.say` and `salary.disclose`, `day_rate.say` — exactly what may be said
- `shareable` (email, phone, links), `never_mention`, `must_ask`

Check that Claude in Chrome is connected and signed in to LinkedIn, and whether
a Gmail tool is available. Say which channels this run will cover.

## 2. Sweep

Delegate to the `linkedin-actor` agent in sweep mode. On a harness without
subagents, follow its sweep steps yourself. Relay its report.

## 3. Approval — one draft at a time

For each draft, show the exact text and ask for a decision, following the
`recruiter-reply` skill:

```
To:       <contact> (<company>) — <channel>, thread <id>
They:     <what they said and asked>
Draft:    <exact text>
Check:    <verdict and items>
Commits:  <times, figures, links it commits to>
Send this as written?  yes / edit / skip / close
```

- **yes** → `threads.py approve --thread <id>`
- **edit** → redraft, `threads.py draft` again, show it again
- **skip** → leave the draft proposed
- **close** → `threads.py close --thread <id> --because "<their reason>"`

Also ask, for each approved thread, the stage it moves to and a follow-up date
(propose one from the cadence; write only what they agree).

## 4. Send

Delegate to the `linkedin-actor` agent in send mode with the approved thread
ids, their stages and follow-up dates. The send-gate hook will put any text that
is not an approved draft in front of the user; if that prompt appears for an
approved draft, something changed the text — stop and look.

## 5. Report and hand over

What was sent and confirmed, what was not and why, and what is still owed
(`threads.py status`). For every thread now `scheduled`, propose the job-hunter
and interview-prep commands from the `reply-ledger` skill and run them when the
user agrees.
