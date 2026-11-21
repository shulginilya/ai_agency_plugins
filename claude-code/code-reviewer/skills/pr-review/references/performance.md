# Performance pass

Load this when the change touches loops over data, database access, rendering,
bundle size, or a documented hot path.

Measure or reason concretely. "This could be slow" is not a finding; "this
issues one query per row, so a 500-row page makes 501 round trips" is.

## Data access

- **N+1 queries.** A loop containing an await that hits the database. Look for
  `.map(async ...)` over records, and for ORM lazy-loading inside a render.
- **Missing indexes.** A new `WHERE`, `JOIN` or `ORDER BY` column with no index
  in the same change. Check the migration, not just the query.
- **Unbounded reads.** `SELECT *` with no limit, a scan that grows with the
  table, a full collection load to compute a count.
- **Transactions held open** across a network call or a slow computation.
- **Chatty caches.** A cache read per item where one multi-get would do; a
  cache with no TTL and no invalidation on write.

## JavaScript and Node

- Blocking the event loop: synchronous file or crypto work in a request path
- `JSON.parse`/`stringify` on large payloads in a hot path
- Quadratic work hiding in `includes`, `indexOf` or `find` inside a loop —
  build a `Set` or `Map` once
- Unbounded concurrency: `Promise.all` over an unbounded array of requests
- Memory retention: growing module-level maps, listeners never removed,
  closures capturing large objects

## Frontend

- **Re-render churn.** New object or array literals passed as props each render,
  inline handlers recreated every time, context values not memoized. Look for a
  provider whose value is an object literal.
- **Effect dependencies** that change identity every render, so the effect runs
  on every render.
- **List rendering** without stable keys, or without virtualization above a few
  hundred rows.
- **Bundle cost.** A new dependency imported at the top level of a route that
  did not need it. Check whether it can be dynamically imported.
- **Core Web Vitals.** Images without dimensions (CLS), render-blocking work
  before first paint (LCP), heavy hydration on an interaction path (INP).

## Rendering strategy

If the change alters what is server-rendered, statically generated or
incrementally revalidated, say what it costs: a page moved from static to
dynamic now hits the origin on every request.

## Reporting

Give an order of magnitude and the input that triggers it. "At 1,000 items this
does 1,000 sequential round trips (~10s at 10ms each); batching makes it one."
