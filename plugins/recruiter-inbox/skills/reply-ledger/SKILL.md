---
name: reply-ledger
description: Keeps the ledger of every recruiter conversation on LinkedIn and email — what they wrote, what was drafted, what the user approved word for word, what was sent, and who owes whom a reply — and hands threads that reach a scheduled call to the job-hunter pipeline and interview-prep. Use when the user asks which recruiters they owe a reply, what is waiting for their approval, wants a sent message recorded, or wants a recruiter thread moved or closed.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Reply ledger

An assistant that answers messages has three ways to embarrass its user:
answering the same message twice, sending something nobody approved, and
letting a good recruiter wait a week. The ledger exists to make all three
impossible to do quietly.

The file is `.jobhunt/inbox/threads.json` — one JSON file, beside the job-hunter
profile and pipeline. Never reconstruct it from memory; read it, change it with
the script, let the script write. Every write backs it up to `.bak` and a file
that does not parse is refused.

## The commands

```bash
python scripts/threads.py init
python scripts/threads.py status                        # what needs the user
python scripts/threads.py seen --meta-file meta.json --text-file msg.txt
python scripts/threads.py draft --thread li:<id> --text-file reply.txt --intent engage \
    --inbound-file msg.txt
python scripts/threads.py approve --thread li:<id>      # only after the user's yes
python scripts/threads.py sent --thread li:<id> --stage scheduling --follow-up 2026-10-01
python scripts/threads.py sent --thread gm:<id> --text-file what-they-sent.txt   # sent by hand
python scripts/threads.py stage --thread li:<id> --to scheduled --pipeline Acme
python scripts/threads.py close --thread li:<id> --because "sales pitch"
python scripts/threads.py show --thread li:<id>
```

`--json` works before or after the subcommand. Thread keys are `li:<id>` for a
LinkedIn thread URL, `gm:<id>` for a Gmail thread; `--url` derives them.
Anywhere a thread is expected, a unique fragment of the contact or company
name also works.

Message text goes in through a file you wrote with your file-writing tool —
never through a heredoc or a command-line argument. It is a stranger's text.
The same holds for anything read off the page: the contact's name, the
company, the role. Put them in a JSON file for `--meta-file` —

```json
{"url": "https://www.linkedin.com/messaging/thread/2-abc/", "contact": "Anna Schmidt",
 "company": "Acme", "role": "Senior AI Engineer", "kind": "opportunity",
 "intent": "engage", "at": "2026-09-24T10:12"}
```

— because a display name containing `$(...)` runs as a command inside double
quotes. The direct flags (`--contact`, `--company`) are for values the user
typed to you.

## Stages

`new → qualifying → interested → scheduling → scheduled`, or `declined` / `closed`.

Move a thread when the conversation moves. `scheduled` means a call or
interview has a date — that is the handover point (below). `declined` is the
user saying no; `closed` is everything else that ends: it fizzled, it was
sales, the role was filled. A new inbound message on a closed thread reopens it.

## What `status` reports

| Bucket | Means | The move |
| --- | --- | --- |
| APPROVED | approved, not sent | send it, or tell the user why it cannot go |
| approve? | a draft waits for the user | show it, get a yes or an edit |
| OWE REPLY | they wrote last | triage and draft |
| follow up | our message, follow-up date passed | draft a follow-up |
| quiet | our message, 7+ days, no follow-up date | set a date or close |

Exit 1 when any bucket is non-empty, so it works as a check. Report the buckets
in that order and turn each row into an action — "Anna at Acme asked for your
availability three days ago" beats "1 reply owed".

## Rules

- **Record before you draft.** `seen` first, so a second sweep recognises the
  message (it matches on a hash) and the thread shows as owed.
- **Approval is the user's yes to the exact text.** Run `approve` only after it.
  An edit is a new `draft`, a new check and a new yes. Never approve on the
  user's behalf because the change was small.
- **A blocked draft is not approved without `--because`,** and the reason is
  the user's words ("yes, you may state the range"), not yours.
- **`sent` only after you saw it in the thread.** The ledger says what went out,
  not what was meant to.
- **Dates come from the user.** A follow-up date is proposed from
  [references/reply-cadence.md](references/reply-cadence.md), stated, and only
  written once the user agrees.
- **Close things.** Sales, scams and dead threads get `close --because`, so
  `status` stays short enough to read.

## Handover when a call is scheduled

A scheduled call is where this plugin's job ends and the search's begins. If
the job-hunter and interview-prep plugins are installed, record it in both —
propose the commands, run them when the user agrees:

```bash
# the opportunity, in the job-hunter pipeline
python <job-hunter>/skills/application-pipeline/scripts/pipeline.py add \
  --company Acme --role "Senior AI Engineer" --track permanent --stage screening \
  --source linkedin --link <thread url> --next "recruiter call" --due <call date>

# the loop, in interview-prep
python <interview-prep>/skills/prep-tracker/scripts/prep.py add --company Acme \
  --role "Senior AI Engineer" --rounds recruiter-screen
python <interview-prep>/skills/prep-tracker/scripts/prep.py round --company Acme \
  --round recruiter-screen --date <call date>
```

Then `threads.py stage --thread <id> --to scheduled --pipeline Acme`. The
ledger keeps the conversation; the pipeline keeps the opportunity.

## Privacy

`init` writes a `.gitignore` containing `*` next to the ledger: it holds other
people's messages. Inbound messages are stored as a 500-character excerpt and a
hash — enough to recognise them, not a copy of anyone's inbox. Outbound
messages are the user's own words and are kept whole.
