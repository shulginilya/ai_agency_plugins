# Contra (contra.com)

Status: **inferred, not yet verified.** Correct this file after the first real
run — page names, filters and what a signed-in view shows.

## Access

There is no official connector. In order of preference:

1. **Notification emails** from Contra in the user's mailbox about new
   opportunities.
2. **The public jobs / opportunities pages** on contra.com, read without
   signing in, where they are public.
3. **A signed-in browser session** the user opened themselves — prefer the
   app's own built-in browser — for the opportunities feed. Read-only, at a
   human pace.

## Searching

- Contra is commission-free and project-based: expect fixed-price projects
  and hourly retainers side by side. Keep fixed-price ones (the script flags
  them) and compare the budget to the hours it implies.
- Use the plan's role phrases; Contra's categories lean towards design and
  product, so expect to discard more than on Upwork.

## Reading a posting

Look for: budget and whether it is fixed or hourly, expected timeline, the
client's profile and past projects, and whether applying requires a portfolio
piece.

## Normalising

| Field | From |
| --- | --- |
| `id` | the opportunity's id or slug from its URL |
| `client` | the client's profile handle |
| `rate` | `per: "hour"` for hourly, `per: "fixed"` for a project budget |
| `hours`, `posted`, `summary` | as shown |

## Red flags

- A fixed budget that works out under the rate floor once the hours are
  estimated.
- "Exposure" or equity in place of payment.
