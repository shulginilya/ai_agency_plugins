# Node.js pass

Load this when `ts_scope.py` tags a changed file `node`: it imports a Node
built-in (`node:fs`, `path`, `child_process`, ...), a server framework or a
database client, or it is a Next.js route handler, middleware or server
action. Server code is where a type mistake turns into a crash for every user,
or into a hole.

After this list, apply [node-best-practices.md](node-best-practices.md): the
Node.js Best Practices guide as review checks, each with the practice it comes
from.

## Async and errors

- **Floating promises.** An async call with no `await`, `.catch` or `void`
  and a reason: a rejection is unhandled, and since Node 15 an unhandled
  rejection crashes the process. Look for `forEach(async ...)`, event handlers
  that are `async`, and fire-and-forget calls in a request.
- **Express 4 and async handlers.** An `async (req, res) => {}` whose
  rejection is not passed to `next(err)`: the request hangs until it times
  out (Express 5 forwards it). Check the Express version in `package.json`.
- **Errors swallowed.** `catch {}` or `catch (e) { console.log(e) }` that
  then returns success; a `finally` that returns and discards the throw.
- **`catch (e)` assumed to be `Error`.** Libraries throw strings, objects and
  `AbortError`s; `e.message` is `undefined` and the log says nothing.
- **Missing timeouts.** An outbound `fetch`, database or queue call with no
  timeout or `AbortSignal.timeout(...)`: one slow dependency holds every
  request open.
- **EventEmitter `error`.** A stream, socket or emitter with no `'error'`
  listener throws and takes the process down on the first error event.

## Concurrency and the event loop

- **Read then write** with no lock, transaction or conditional update: two
  requests both read stock 1, both sell it.
- **Unbounded `Promise.all`** over user-sized input: 10,000 rows open 10,000
  connections. Batch or limit concurrency.
- **Sequential awaits in a loop** where the calls are independent: give the
  latency it adds at the expected size.
- **Blocking work in a request path:** `fs.readFileSync`, `crypto.pbkdf2Sync`,
  `zlib.*Sync`, a large `JSON.parse`, or a regex with nested quantifiers on
  user input (ReDoS) stalls every other request.
- **Streams without backpressure:** `readable.on('data', c => writable.write(c))`
  ignoring the return value buffers the whole file in memory. Use
  `stream/promises` `pipeline`.

## Input at the boundary

- **Typed but not validated.** `req.body`, `req.query`, `req.params`,
  headers, cookies, webhook payloads, queue messages and environment
  variables are typed by assertion only. `req.query.page` is
  `string | string[] | undefined`; `Number('abc')` is `NaN`;
  `parseInt('10abc')` is `10`.
- **Environment variables.** `process.env.PORT` is `string | undefined`;
  `Number(undefined)` is `NaN`, and `process.env.FLAG === 'false'` is truthy
  as a bare `if (process.env.FLAG)`. Validate them once at startup.
- **Prototype pollution.** Merging a parsed JSON body into an object with a
  recursive merge or `Object.assign` on nested keys: `__proto__` keys
  change every object.

## Injection and exposure

- **SQL / NoSQL injection.** A query built with a template string or `+` from
  input, `$where`, or a Mongo filter taken straight from `req.body`
  (`{ "password": { "$ne": "" } }`). Parameterize; validate filter shape.
- **Command injection.** `exec`/`execSync` with a template string; prefer
  `execFile`/`spawn` with an argument array.
- **Path traversal.** `path.join(root, req.params.file)` accepts `../`;
  resolve and check the result still starts with `root + path.sep`.
- **SSRF.** A server-side `fetch` to a user-supplied URL with no allow list,
  reaching internal hosts or cloud metadata (`169.254.169.254`).
- **Auth gaps.** A new route or server action with no authentication or no
  ownership check (`/orders/:id` returns any user's order).
- **Secrets in logs or responses.** Logging a whole request, token, or error
  object with config attached; returning `err.stack` to the client.

## Resources and lifecycle

- A database connection, file handle or lock acquired without a `finally`
  (or `using`) that releases it on the error path: the pool drains after N
  failures.
- A module-level cache, map or listener that grows per request and is never
  pruned.
- A new server or worker with no graceful shutdown on `SIGTERM`: in-flight
  requests or jobs are cut off on every deploy.

## Modules and runtime

- ESM/CJS mismatches the types do not catch: `"type": "module"` with
  `require`, a relative import with no `.js` extension under `NodeNext`,
  `__dirname` in ESM, a CommonJS default export imported as a named one.
- A Node API newer than the `engines.node` version or the runtime in the
  Dockerfile or CI.

## Reporting

Name the request or event and what the server does: "a `POST /upload` whose
stream errors mid-file leaves the `fs.createWriteStream` at `upload.ts:40`
open with no `'error'` listener, so the process exits and drops every
in-flight request."
