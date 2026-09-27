# Reading a recruiter message

What the sender's type, the message's shape and its warning signs say about the
reply. Load this once you have read the message in full.

## Who is writing, and what the reply needs

| Sender | Recognise by | What they want | What the reply must get |
| --- | --- | --- | --- |
| In-house recruiter | company domain, "our team", a specific req | fill one role | salary band, process, the hiring manager's name |
| Hiring manager / founder | engineering title, talks about the problem | a peer conversation | a technical call soon; skip the recruiter dance |
| Agency recruiter | "my client", "on behalf of", no company named | your CV on file | the client's name **before** consenting to a CV submission |
| Freelance project broker | "Projekt", day rate, start date, duration, "remote %" | availability and rate | end client or industry, duration, remote share, rate |
| Executive search / headhunter | retained search, senior title, discreet tone | a confidential first call | scope, reporting line, band |

**Agency CVs, especially in Germany.** An agency that submits a CV without
explicit consent for a named client can make a later direct application look
like a duplicate, and the two submissions can collide on fees. Consent is per
client and per role: "yes, you may submit me to Acme for the Senior AI Engineer
role" — never a blanket yes. The reply asks who the client is before anything
else moves.

## Signals of a real opportunity

- A named company, team, product or problem.
- A title and level that exist on the company's careers page or in the thread.
- A process described in steps ("intro call, technical round, team day").
- A band or rate, or an honest "I can share the range on a call".
- A sender whose profile shows a real recruiting or engineering history.

## Signals of a mailshot

- "Exciting opportunity", "fast-growing", "leading company" and nothing concrete.
- A title unrelated to the profile, or two levels off.
- The same wording as an earlier message from someone else at the same agency.
- A request for a CV before anything about the role is said.

A mailshot is not a scam. It gets a qualifying reply, not silence — some turn
out to be real roles described badly.

## Scam patterns — no reply, flag to the user

- Payment in any direction before work: fees, equipment, training, "starter kits".
- Identity documents, bank details or tax IDs requested before an offer.
- Crypto, wallets, cheques to deposit, package reshipping.
- "No interview needed", an offer after one chat message.
- Moving to Telegram, WhatsApp or a personal address in the first message,
  especially with urgency.
- A company name that does not match the sender's email domain or profile.

## Sales dressed as recruiting

Outsourcing and staff-augmentation firms, CV-writing services, courses,
"partnership opportunities", agencies offering developers. They use the same
words ("opportunity", "team") and want a meeting, not a hire. Ignore, and close
the thread in the ledger with the reason.

## What to extract for the ledger

| Field | From |
| --- | --- |
| contact | the sender's name as shown |
| company | the employer, or empty when an agency withholds it |
| role | title as written, with level |
| kind | opportunity, recruiter-agency, network, sales, scam-risk |
| intent | engage, qualify, decline, ignore, personal |
| at | the message's own timestamp, ISO |

Leave a field empty rather than guess it. "Acme (probably)" is worse than empty.
