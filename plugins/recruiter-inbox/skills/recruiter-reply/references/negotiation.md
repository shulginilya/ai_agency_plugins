# Money, notice, start date, remote

The questions a recruiter asks early to filter, and how a reply handles each
without giving away what only the user should decide. None of this is legal or
financial advice; it is how to keep a first conversation from closing a door or
fixing a number too early.

## What never goes in writing from the actor

- A number the user has not set in the profile or said in this conversation.
- An acceptance, a counter-offer, or agreement to terms.
- The current salary. It anchors every later number to the past, and in some
  jurisdictions employers may no longer ask for it (see below).
- A resignation date, or anything the user has not told their current employer.

`draft_check.py` blocks the first two mechanically. The rest is on you.

## "What are your salary expectations?"

The profile's `replies.salary` decides the move:

| `disclose` | `say` | The reply |
| --- | --- | --- |
| `never` | — | Ask for their range; say you will discuss numbers once scope and level are clear. |
| `on-request` | set | Only when they asked: state `say` exactly, as written, once. |
| `on-request` | empty | Ask for their range; tell the user they asked and that no figure is set. |
| `early` | set | May state `say` in the first qualifying reply. |

Their range first is the default for a reason: a band the company budgeted is
information, a number the candidate names is a ceiling. A good deflection is
short and still answers:

```
Happy to talk numbers once I know the level and scope. What range has the
team budgeted for it?
```

In German:

```
Über das Gehalt spreche ich gern, sobald Level und Umfang klar sind. Welche
Spanne ist für die Position vorgesehen?
```

State figures in the unit the market uses. In Germany a permanent salary is
annual and gross (brutto p.a.); a freelance rate is per day or per hour, net of
VAT (zzgl. MwSt.). Say which, so "95k" is not read as a monthly or net figure.

## Pay transparency — check before relying on it

The EU Pay Transparency Directive (2023/970) requires employers to give
applicants the starting pay or its range before the interview, and bars them
from asking about pay history. Member states had to transpose it by 7 June
2026. **Germany had not done so as of September 2026**, so these are not yet
enforceable rights for a German role; other member states may differ. Do not
cite the directive to a recruiter as if it were law in their country — asking
for the range is reasonable without it.

(Sources checked 2026-09-25: Ogletree, Feb 2026; yagemi.de, 4 Sep 2026. Re-check
before relying on this; the law is expected to change.)

## Notice period and start date

- Say the notice period only as the profile states it (`notice_period`), e.g.
  "three months to the end of a month". An empty field means ask the user.
- `earliest_start` is a date the user chose; never compute one from the notice
  period yourself.
- If a recruiter pushes for an earlier start, the reply says the user will
  check, not that it is possible.

## Remote, hybrid, working from abroad

Ask, do not assume. "Hybrid" ranges from one office day a month to four a
week, and "remote" may mean remote within one country. If working from abroad
now and then matters to the user, ask how many days a year the company allows
and from where — it is a policy question with tax and social-security answers
behind it, and the recruiter often does not know it offhand. A reply that asks
it early saves a late surprise.

## Contract and freelance

- Rate is the user's (`day_rate.say`). The profile's `rate_floor` is the line
  below which to decline, never a number to quote.
- Ask duration, remote share, start, end client or industry, and whether the
  broker's margin comes out of the stated budget.
- In Germany, ask whether it is a genuine project (Werkvertrag or
  Dienstvertrag) or disguised employment; a full-time, on-site, indefinite
  "project" can carry false self-employment (Scheinselbstständigkeit) risk.
  Flag it to the user rather than deciding it.

## When an offer arrives

Stop replying on substance. Acknowledge, and hand the offer — the document,
the numbers, the deadline — to the user. Negotiating an offer is the user's
conversation.
