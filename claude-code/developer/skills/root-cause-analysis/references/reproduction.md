# Reproduction

A reproduction is a command, not a story. Until you have one, every other step
is speculation.

## Build the deterministic case

Start from the report and remove variables one at a time, checking after each
removal that the failure survives:

1. **Pin the environment.** Same branch, same lockfile, same env vars, same
   database state. Note every difference you had to accept.
2. **Shrink the input.** Halve it. Still fails? Halve again. A 4-line input
   that fails is worth more than a 4000-line one that also fails.
3. **Drop the layers.** If it fails through the UI, does it fail against the
   API? Against the function directly? Each layer you remove is a whole class
   of cause eliminated.
4. **Freeze the clock and the randomness.** Fixed seed, fixed timestamp, fixed
   IDs. Anything that varies between runs will later be mistaken for the cause.

Stop shrinking when the next removal makes the failure disappear — that
boundary is itself evidence and belongs in the report.

## Intermittent failures

Run it enough times to get a rate before theorising:

```bash
python scripts/repro.py --cmd "<the failing command>" --times 20
```

A rate turns a vague complaint into a measurement, and the rate itself points
at the mechanism:

| Pattern | Usual mechanism | First probe |
| --- | --- | --- |
| Fails only in the full suite, passes alone | shared state between tests, ordering | run the suite with a fixed seed, then reversed |
| Fails only in CI | concurrency level, timezone, locale, cold cache, no TTY | run locally with CI's env vars and `--times` |
| Roughly 1 in N, no pattern | race between two async paths | add ordering asserts, not sleeps |
| Fails after running a while | resource leak, unbounded cache, connection pool | measure across the run, not at the end |
| Fails at a time of day or month | timezone, DST, month boundary, token expiry | freeze the clock and step it |

Never "fix" an intermittent failure by adding a sleep or a retry until the rate
drops. That converts a reproducible bug into an unreproducible one.

## When you cannot reproduce it

This is a legitimate outcome, and it has its own deliverable. Do not substitute
a plausible fix for a missing reproduction.

Report, in order:

1. **What you ruled out** and how — each attempt is a narrowed search space for
   whoever picks this up next.
2. **What differs** between your environment and the one that fails: version,
   data volume, permissions, region, concurrency, client.
3. **The instrumentation that would catch it** — the specific log line, metric,
   or assertion, at the specific place, with the fields needed to identify the
   trigger. "Add more logging" is not a deliverable; "log the resolved tenant
   ID and cache key at `resolveTenant` entry" is.
4. **What to ask the user or the production system for**: the exact timestamp,
   the request ID, the input that failed, the deployed version.

## Keep the reproduction

Once the fix lands, the reproduction becomes the regression test. If it cannot
become a test — it needs a real cluster, a specific customer's data — say so
explicitly and name what monitoring replaces it. An unrepeatable fix is a fix
that comes back.
