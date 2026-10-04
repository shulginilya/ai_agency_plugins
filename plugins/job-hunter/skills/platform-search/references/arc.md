# Arc (arc.dev)

Status: **inferred, not yet verified.** Correct this file after the first real
run — page names, filters and what a signed-in view shows.

## Access

There is no official connector. In order of preference:

1. **Job-alert emails** from Arc in the user's mailbox. Search the mailbox for
   mail from arc.dev in the last 14 days; each alert names roles with links.
2. **The public remote-jobs board** on arc.dev, read without signing in.
3. **A signed-in browser session** the user opened themselves — prefer the
   app's own built-in browser over the user's personal browser — for the
   matched roles in the developer dashboard. Read-only, at a human pace.

## Searching

- Use the plan's role phrases and filter to **freelance / contract** and
  **remote**. Arc lists many full-time roles; drop permanent roles unless the
  profile's `tracks` includes `permanent`.
- Arc vets developers and matches them to roles; a posting the user is not
  eligible for may show as locked. Record it as `unclear` with the reason
  rather than skipping silently.

## Reading a posting

Look for: hourly rate or rate range (often stated), hours per week, time-zone
overlap required, contract length, the company name and size, and the stack.

## Normalising

| Field | From |
| --- | --- |
| `id` | the job's slug or numeric id from its URL |
| `client` | the company name |
| `rate` | the stated hourly range, `per: "hour"`; a yearly salary means a permanent role — drop it by track, do not convert it |
| `hours`, `posted`, `summary` | as shown |

## Red flags

- Required overlap with a US time zone for most of the day.
- "Full-time freelance" at 40 h/week when the profile caps hours lower.
