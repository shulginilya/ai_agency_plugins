# Upwork

Status: verified against the official Upwork connector on 2026-10-04.

## Access

1. **Official Upwork connector** (preferred). Signed in through Upwork's own
   authorisation; no password is ever handled. List the accounts first and use
   the freelancer account's `org_uid` on every call.
2. **Job-alert emails** in the user's mailbox, when the connector is absent.
   Read-only: they carry title, budget and link, not the client record.
3. **A signed-in browser** as the last resort, at a human pace, read-only.

## Before searching

- **Check the Connects balance** by opening any one posting: the detail view
  returns the balance and the cost to apply. A balance of 0 means nothing can
  be submitted at all — report that as the blocker before the list.
- Read the plan's `limit`: results come 10 to a page.

## Searching

Run both, then merge by id:

- **Recommendations** (`smart_search`, `best_match`) — Upwork's own ranking
  for this freelancer's profile. Takes no query. Add `most_recent` with a
  `days_posted` window when the user wants only new work.
- **Title searches** — one per query from the plan. `title` matches the job
  title only, every word required, whole words, stemmed. Use 1–3 words.
  Filters worth always setting: `job_type=hourly` when the profile prefers
  hourly, `rate_min=<floor>`, `verified_payment_only=true`,
  `proposals_max=20`, `sort=recency`.

What the filters do **not** do:

- `rate_min` is a **range overlap**: it keeps any job whose posted maximum
  reaches the value, so a $25–47/h job passes a $45 floor. The script applies
  the real floor afterwards.
- A single-technology title ("Vue", "TypeScript", "Next.js") mostly returns
  nothing — clients title by role. Use the role phrases.
- `title` cannot be combined with `query` or `sort=relevance`; both are
  refused.
- There is no date filter on title search; only the recommendations feed
  honours dates.

## Reading a posting

Open the full posting for the top candidates. Look at:

- `jobActivity`: `totalHired` or `totalOffered` above 0 means hiring is
  already done or nearly done; many `totalInvitedToInterview` means it is
  late.
- `client_record`: hires, hire rate, total spend, feedback. A client with
  several jobs posted and zero hires is a weak bet.
- `preferred_locations` and `preferred_qualifications` (country, English
  level, success score, earnings): a stated country preference outside the
  user's is close to a deal-breaker even when marked optional.
- Screening questions and mandatory extras (a Loom video, a test).
- `connects_cost`.
- `applied`: never recommend a job already applied to.

## Normalising

| Field | From |
| --- | --- |
| `id` | the job id |
| `title`, `url` | as returned |
| `client` | the client company id when known, else the country |
| `rate` | `{min, max, currency: "USD", per: "hour"}` from the hourly budget; `per: "fixed"` for fixed-price |
| `hours` | the engagement (`<30 h/wk`, `30+ h/wk`, `as needed`) |
| `proposals` | the proposals tier |
| `posted` | the published date |
| `applied` | as returned |
| `summary` | the description snippet |

## Red flags particular to Upwork

- The same client posting the same job several times, with zero hires.
- "This account shows 0 hires, but we hire on another account."
- Many freelancers to hire at entry level with an expert rate — an agency
  reselling.
- New client, crypto gambling or betting, rate far above market.
- A brief asking to get around an AI provider's safety limits.
- Budget range far under the stated seniority ("expert", $15–30/h).
