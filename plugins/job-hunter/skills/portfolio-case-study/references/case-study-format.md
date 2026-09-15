# Portfolio entry format

One file per project, saved as `.jobhunt/portfolio/<project-slug>.md`. The
full case study comes first; the two short variants below it are cut from it,
never written separately — so they cannot drift apart.

```markdown
---
project: <name>
slug: <project-slug>
links:
  live: <url or omit>
  code: <public repo url, or omit if private>
period: <YYYY-MM – YYYY-MM>
role: <e.g. Lead engineer, team of 4>
confidential: <true|false>
sources: [<repo path or url>, <live url>, user]
---

# <Name> — <what it is, in under ten words>

**<One sentence: who it is for and what it lets them do.>**

## The problem
Two to four sentences. What was broken, slow, manual or missing before this
existed, and for whom. The reader should care before they read a single
technology name.

## What I did
My role, the team around me, and the parts I owned. Three to five bullets,
each a decision or a thing built — verb first, concrete noun second:
- Designed <X> so that <consequence>.
- Built <Y> on <Z>, replacing <W>.

## How it works
One short paragraph, or a list of the main components and how they talk. Name
the one hard part and how it was solved. An architecture sketch helps if the
user has one.

## Results
Numbers when the user gave them, with the period they cover. When there are
none, concrete qualitative change: "the support team stopped exporting CSVs by
hand". Never an invented figure.

## Stack
<Frontend> · <Backend> · <Data> · <Infra> · <Testing/CI> — only confirmed items.

---

## CV bullet
<One or two lines, past tense, outcome first, ≤ 35 words.>

## Platform blurb
<For Upwork/Malt/Contra/LinkedIn projects: 60–100 words, first line is the
outcome, no greeting, ends with the stack in one line.>
```

## Register by destination

| Destination | Length | Voice | Notes |
| --- | --- | --- | --- |
| Portfolio site | full case study | first person, plain | a screenshot or diagram per project beats a longer text |
| CV | the bullet | no pronoun, past tense | mirror the target posting's nouns when tailoring |
| Upwork / Malt / Contra | the blurb | first person | the first line shows in the card; lead with the outcome |
| LinkedIn "Projects" | the blurb, trimmed | first person | link the live app, never a private repo |
| GitHub README "About" | the one-sentence summary | neutral | — |

## A worked example of the difference

Weak — fluent, unsupported, interchangeable:

> Architected and developed a robust, scalable SaaS platform leveraging
> cutting-edge technologies to deliver seamless experiences.

Strong — every clause has a source:

> Built the booking and payments flow for a physiotherapy chain's patient app
> (React Native, Node.js, Stripe). Replaced phone booking at 14 clinics; no-show
> rate fell from 18% to 7% in the first quarter after reminders shipped.

The strong version names the user, the domain, the thing built and the change.
The numbers came from the user. Without them, it stops after "14 clinics" and
is still better than the weak one.
