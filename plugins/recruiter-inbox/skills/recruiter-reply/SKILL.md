---
name: recruiter-reply
description: Writes the reply to a recruiter or hiring message that moves the conversation one step toward a first call or interview — qualifying questions, interest with proposed times, a courteous decline, a follow-up — in the sender's language and the user's voice, then checks it against the profile's rules before asking the user to approve it word for word. Use when the user wants to answer a recruiter, reply to a LinkedIn message, InMail or job offer message, handle a salary or availability question, or follow up on a quiet thread.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Recruiter reply

Every reply has one job: move the conversation one step closer to a call with
someone who can hire. Not to be charming, not to summarise the CV, not to
negotiate. A reply that ends without a question or a proposed time hands the
next move to a recruiter with forty other threads, and the thread dies there.

```
first contact → qualifying → interested → scheduling → scheduled
                    ↘ declined (explicit mismatch)          ↘ handed to job-hunter + interview-prep
```

Do not write anything until the message has been through the `inbound-triage`
skill. Answering a message you have not triaged means writing warmly to a
scam, or accepting a call for a role that trips a deal-breaker.

## What you need before drafting

1. **The whole thread**, from the channel — not the notification email, not the
   last message alone. What was already asked and answered decides the reply.
2. **The triage report**: intent, what they asked, what is unknown.
3. **The profile's `replies` section** (`.jobhunt/profile.json`): name, send
   mode, languages, availability, what may be said about money, what is
   shareable, what is never mentioned, the questions the user always asks.
4. **Evidence**, if the reply claims fit: `.jobhunt/portfolio/` entries from the
   job-hunter plugin, or facts the user has stated. Nothing else.
5. **The ledger**: is a draft for this thread already waiting or approved? Then
   this is a revision, not a new reply.

If something the reply needs is missing — no availability declared and they
asked for times, a salary question and no `salary.say` — ask the user. Do not
fill the gap with something plausible.

## The shape

```
1. Their question, answered first — in one or two sentences. If they asked
   three things, answer three things.
2. One or two facts that make the fit credible for THIS role, only if the
   thread is at that point. From the profile or portfolio, never invented.
3. The questions that decide the fit — the triage unknowns that matter most,
   intersected with `must_ask`. Three at most. Money, remote, process, company.
4. The next step, concrete: two or three slots from `availability`, or a
   request for theirs. One ask, not a menu.
5. Sign-off with the profile's `name`. No title block, no links unless shareable.
```

The replies for each stage — first contact, qualifying, interested, scheduling,
declining, following up, and an offer arriving — are in
[references/reply-moves.md](references/reply-moves.md). Load it once you know
which stage this thread is at. Anything about money, notice period, start date
or remote work: [references/negotiation.md](references/negotiation.md).

## Voice and length

- **Their language.** Reply in the sender's language when it is in the
  profile's `languages`; otherwise in English. Mirror their register — *Sie*
  or *du*, first name or surname.
- **LinkedIn: 300–900 characters.** Short paragraphs. The composer is small and
  the recruiter reads on a phone.
- **Email: under 150 words**, a subject that keeps theirs.
- **The user's voice, not an assistant's.** No "I hope this message finds you
  well", no "I'm excited to", no em-dash cadence. If a sentence would fit any
  reply to any recruiter, cut it.

## Check it, then ask

```bash
python scripts/draft_check.py draft.txt --inbound message.txt --intent qualify
```

Or record and check in one step with the `reply-ledger` skill
(`threads.py draft`). Exit 1 (blocked) means the draft says something only the
user can authorise — a number, a phone number, "I accept". Fix it; do not ask
for approval of a blocked draft unless the user has already said that exact
thing is fine. Exit 3 (review) means fix it, or say which item stands and why.

Then show the user, for each draft:

```
To:       <contact> (<company>) — <channel>, thread <id>
They:     <one line: what they said and asked>
Draft:    <the exact text, as it will be sent>
Check:    clean | review: <items> 
Commits:  <anything the draft commits the user to — a time, a figure, a CV>
Send this as written?
```

**Only an explicit yes to that exact text is approval.** "Looks good but change
Tuesday to Wednesday" is an edit: make it, check again, show it again. Record
the approval with `threads.py approve` only after the yes — the send-gate hook
compares what is typed or mailed against that record, and anything else stops
at the user's permission prompt.

## Rules

- **Never state a number the user has not set.** Salary, day rate, notice
  period, start date — from the profile or from the user in this conversation,
  word for word. Otherwise the reply asks for their range or says it will be
  discussed on the call.
- **Never accept, agree or commit.** An offer, a contract, terms, a start date:
  the reply acknowledges and hands it to the user. Accepting is not a reply.
- **Never share what is not shareable.** Phone, email, CV link, calendar link —
  only what `shareable` lists. A CV goes to an agency only after the client is
  named and the user consents for that client.
- **Never mention what `never_mention` lists** — a current employer, a leave
  date, a reason for leaving.
- **Answer what they asked.** Skipping their question to ask yours reads as not
  having read the message.
- **One thread, one draft.** A new draft replaces the old one; an approved draft
  that needs changing is re-drafted and re-approved.
- **Decline in two sentences.** Thank them, say it is not a fit and the one
  reason if it helps them, leave the door open for the right role. No
  explanations the user did not give.
