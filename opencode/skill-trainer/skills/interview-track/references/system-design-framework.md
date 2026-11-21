# System design framework

Seven steps, in this order, every time. The times are for a 45–60 minute round.

| # | Step | Time | Done when |
| --- | --- | --- | --- |
| 1 | Requirements | 5 min | 3–5 functional requirements, and the non-functional ones with numbers: latency, availability, consistency |
| 2 | Estimates | 3–5 min | QPS (read and write separately), storage per year, bandwidth; one line of arithmetic each |
| 3 | API | 3–5 min | the main endpoints or events, with their key fields and idempotency |
| 4 | Data model | 5 min | entities, the access patterns, the store chosen for each and why |
| 5 | High-level design | 10 min | the request path end to end: client → edge → services → stores → async workers |
| 6 | Deep dive | 10–15 min | the hardest part, chosen by the candidate or the interviewer, designed properly |
| 7 | Trade-offs and operations | 5 min | what breaks first at 10×, failure modes, what to monitor, what it costs |

## Numbers worth knowing

- One day is about 86,400 s, so 1M requests a day is about 12 QPS on average.
  Peak is often 2–3× the average.
- Rough latencies:
  - memory read: about 100 ns;
  - SSD random read: about 100 µs;
  - same-datacenter round trip: about 0.5 ms;
  - cross-continent round trip: about 100 ms.
- One machine can serve roughly:
  - thousands of simple HTTP requests per second;
  - a well-indexed Postgres doing low thousands to tens of thousands of
    simple queries per second;
  - Redis doing about 100k operations per second.

## What the interviewer is probing

- **Consistency:** what does the user see right after a write?
- **Hot keys and celebrities:** one key or one user taking a share of traffic
  far beyond average.
- **The write path, not only the read path.**
- **Idempotency and retries** wherever a network call can repeat.
- **Failure:** a node, a zone, or a dependency is slow, not down.
- **Cost:** what dominates the bill, and the one change that halves it.

## Common failure modes

- Drawing boxes before the requirements are settled.
- Listing technologies ("Kafka, Redis, Cassandra") instead of making a
  decision with a reason.
- No numbers anywhere.
- Three options presented neutrally instead of one chosen with its trade-off.
- Never mentioning monitoring, failure or cost.

## Grading a design session

Score 3 or less if any of these is missing:
- requirements before design;
- at least one estimate;
- a reasoned data store choice;
- one failure mode.

Score 4 needs all of them plus a coherent deep dive. Score 5 also needs
handling the 10× probe without a redesign and a sense of cost.
