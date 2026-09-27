---
description: Which recruiter threads need you - replies owed, drafts to approve, approved but unsent, follow-ups due - and record stage changes.
argument_hint: "[nothing for what is owed, or: show <thread> | stage <thread> to <stage> | close <thread>]"
model: sonnet
allowed_tools: Bash Read Grep Glob
---

Threads: {{ARGS}}

Follow the `reply-ledger` skill. Read before changing — the user may have
edited or answered something by hand.

With no argument, report what is owed:

```bash
python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" status
```

If there is no ledger, say so and offer `/inbox setup`. Otherwise report the
buckets in order — approved but unsent, waiting for approval, replies owed,
follow-ups due, quiet — and turn each row into a specific action: "Anna at
Acme asked for your availability on the 22nd, three days ago" rather than a
count. Offer `/inbox` to deal with them.

To change a thread:

```bash
python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" show --thread <id>
python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" stage --thread <id> \
  --to <qualifying|interested|scheduling|scheduled|declined|closed> [--follow-up YYYY-MM-DD]
python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" close --thread <id> --because "<reason>"
```

Never move a thread on an assumption, and never write a follow-up date the
user has not agreed to. If they say "next week", convert it and say which date
you used. For a thread moving to `scheduled`, propose the job-hunter and
interview-prep handover from the skill.
