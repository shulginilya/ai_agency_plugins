# Recruiter mail in Gmail

Two different things arrive by email: LinkedIn's notifications about messages
(pointers — the conversation is on LinkedIn) and recruiters writing directly
(the conversation is the email thread).

## LinkedIn notification senders

Observed in a LinkedIn member's inbox in September 2026:

| Sender | What it is | Use |
| --- | --- | --- |
| `messages-noreply@linkedin.com` | "X sent you a new message" | find the thread; open it on LinkedIn |
| `messaging-digest-noreply@linkedin.com` | digest of unread messages | same |
| `jobalerts-noreply@linkedin.com`, `jobs-noreply@linkedin.com` | job alerts | not conversations — ignore here |
| `invitations@linkedin.com` | connection requests | not conversations — ignore here |
| `notifications-noreply@linkedin.com` | general activity | ignore here |

InMail notifications have historically come from `inmail-hit-reply@linkedin.com`;
it was not seen in the sample, so include it in the query but do not rely on it.

Never reply to a notification email. The sender is a no-reply address, and the
reply would not reach the recruiter.

## Queries

LinkedIn message notifications from the last week:

```
from:(messages-noreply@linkedin.com OR messaging-digest-noreply@linkedin.com OR inmail-hit-reply@linkedin.com) newer_than:7d
```

Direct recruiter email in the inbox, excluding LinkedIn's own mail:

```
in:inbox newer_than:14d -from:linkedin.com -category:promotions (recruiter OR role OR position OR opportunity OR interview OR Stelle OR Projekt OR Position)
```

Search results show only a preview of the oldest messages in each thread. Read
the thread in full before triaging it; the newest message is the one to answer.

## Recording

The ledger key for an email thread is `gm:<thread id>`. Use `--channel gmail`,
the sender's name as `--contact`, and the date of the newest inbound message as
`--at`.

## Replying

- Reply to the **latest** message in the thread (its message id), plain-text
  `body` only, exactly the approved text. The send gate compares the whole body.
- Keep their subject; do not add a signature the approved text does not have.
- `draft-only` mode: create a Gmail draft as a reply to that message and tell
  the user it is waiting in Drafts. Creating a draft is not gated; sending is.
- No attachments from the actor. If a CV is wanted and a link is in `shareable`,
  the approved text carries the link; otherwise the user attaches it.
