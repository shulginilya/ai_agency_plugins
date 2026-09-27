---
description: Draft the reply to one recruiter message - pasted, a file, or a ledger thread - check it, and get it approved.
argument_hint: "[paste the message, a file path, or a thread id like li:2-abc]"
model: sonnet
---

Reply to: {{ARGS}}

If that is empty, ask for the message — the whole thread if there is one. Do
not draft from a summary of it.

1. **Get the text.** A thread id → read the thread from its channel (the
   `inbox-channels` skill). Pasted text → write it to
   `.jobhunt/inbox/tmp/message.txt` with your file-writing tool; never pass it
   through the shell.
2. **Triage it.**

   ```bash
   python "{{PLUGIN_ROOT}}/skills/inbound-triage/scripts/inbound.py" .jobhunt/inbox/tmp/message.txt
   ```

   Exit 2 without a profile: run `--init` and fill in the replies section with
   the user first. Intent ignore or personal: say so and stop unless the user
   still wants a reply.
3. **Record it** in the ledger if it is not there (`threads.py seen
   --meta-file`, with a `thread` key the user can recognise when there is no
   URL). Names and companies from the message go in the meta file, not on the
   command line.
4. **Draft** following the `recruiter-reply` skill, and check it:

   ```bash
   python "{{PLUGIN_ROOT}}/skills/reply-ledger/scripts/threads.py" draft \
     --thread <id> --text-file .jobhunt/inbox/tmp/reply.txt --intent <intent> \
     --inbound-file .jobhunt/inbox/tmp/message.txt
   ```

5. **Show it and ask** "Send this as written?" with the exact text, the check,
   and what it commits to. Only a yes is approval → `threads.py approve`.
6. **Deliver** according to `send_mode` and the channel: send it through the
   channel (the `inbox-channels` skill, or the `linkedin-actor` agent in send
   mode), or give the user the text to paste. Once it is sent — or the user
   says they sent it — record it with `threads.py sent`, with the stage and
   follow-up date they agree.
