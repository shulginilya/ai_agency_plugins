# Bug classes: symptom to mechanism

Match the signature, run the first probe. This table exists so the first hour
is spent testing the likely mechanism rather than reading files in file order.

## State and lifecycle

**Signature** — correct on first run, wrong on the second; correct after a
refresh; wrong value that used to be right; a change that "doesn't take".

| Mechanism | Tell | First probe |
| --- | --- | --- |
| Stale closure | a handler reads a value from an earlier render | log the captured value and the current one side by side |
| Cache never invalidated | writes succeed, reads are old | read the store directly, bypassing the cache |
| Cache key collides | two entities share an entry | print the key; check every field that should be in it |
| Effect re-runs or never runs | duplicated requests, or none | log entry and cleanup with the dependency values |
| Subscription not torn down | grows with navigation; leaks | count listeners across the repro |
| Mutated shared object | a far-away value changes | freeze the object and see what throws |

## Async and ordering

**Signature** — intermittent, load-dependent, "works when I step through it in
the debugger", fixed by an unexplained `await` or `setTimeout`.

| Mechanism | Tell | First probe |
| --- | --- | --- |
| Read-then-write race | lost update under two concurrent callers | run the two paths concurrently on purpose |
| Out-of-order response | the slower earlier request wins | tag each request and assert the sequence |
| Retry lands after the original | duplicate side effect | log attempt numbers and completion order |
| Unawaited promise | error vanishes; work happens after the response | fail the process on unhandled rejection |
| Event fires before state is ready | first interaction after load only | assert readiness at the top of the handler |
| Deadlock or pool exhaustion | hangs at a fixed concurrency | count checked-out connections over the run |

## Data and boundaries

**Signature** — fails for one record, one customer, one row; fails at the start
or end of a list, a month, a page.

| Mechanism | Tell | First probe |
| --- | --- | --- |
| Off-by-one | the first or last element | run with exactly 0, 1 and 2 items |
| Empty collection | crash or wrong total on no rows | run with an empty input |
| Null versus undefined versus missing key | one field only | print the raw payload, not the parsed object |
| Unicode, whitespace, casing | one user's name, one locale | hexdump the offending value |
| Float rounding, money in floats | totals off by cents | assert against integer minor units |
| Timezone or DST | off by hours, or by a day near a boundary | run with TZ set to the failing region |
| Pagination or truncation | wrong past N records | run with a limit smaller than the data |

## Types and contracts

**Signature** — appeared after an API, schema, or dependency change; a shape
that is right in the type system and wrong at runtime.

| Mechanism | Tell | First probe |
| --- | --- | --- |
| Contract drift | the caller sends what the callee no longer accepts | diff the payload against the schema, at runtime |
| Coercion | "10" + 1, a truthy "0", a stringified null | log `typeof` at the boundary |
| Cast or `any` hiding a real shape | the type says one thing, the value another | validate at the boundary and let it throw |
| Serialisation loss | a Date, a Set, a BigInt through JSON | round-trip the value and compare |
| Version skew between deployed parts | one instance fails, another does not | compare deployed versions of both sides |

## Environment and configuration

**Signature** — works locally, fails in CI or production; works for one
deployment; started at a deploy with no code change.

| Mechanism | Tell | First probe |
| --- | --- | --- |
| Missing or defaulted env var | a silent fallback path | print the resolved config, not the file |
| Different dependency version resolved | lockfile ignored, or not committed | compare installed versions across environments |
| Permissions, IAM, network policy | fails only against the real service | run the exact call with the deployed identity |
| Resource limits | fails at size or memory, not logic | reproduce at the limit, not at the default |
| Build-time versus run-time value | correct in dev, baked-in in prod | inspect the built artefact for the value |

## Resource and performance

**Signature** — slow before it is wrong; degrades over time; falls over under
load; the first request is fine.

| Mechanism | Tell | First probe |
| --- | --- | --- |
| N+1 queries | latency scales with rows | count queries per request |
| Unbounded growth | memory or a collection rises monotonically | measure across a long repro run |
| Missing index | one query dominates | read the query plan |
| Work inside a loop that belongs outside | scales with iterations | count calls, do not time them first |
| Timeout mistaken for a bug | a truncated result treated as complete | check whether the caller timed out |

## How to use this

Pick the one or two classes the signature matches and run those probes. If both
come back clean, that is real information: state the classes you eliminated and
widen to the next axis in the skill's narrowing table rather than re-reading
the same code.
