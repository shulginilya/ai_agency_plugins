# Node.js best practices

Load this in the **node** pass, after [node.md](node.md), and apply every
section. The **tests** pass applies its Testing section to the tests of
`node` files. In the *Node.js best practices only* mode of `SKILL.md` (a
question about existing code, or a change to a `Dockerfile` alone), apply it
to the code or files named.

The checks come from [Node.js Best Practices](https://github.com/goldbergyoni/nodebestpractices)
by Yoni Goldberg and contributors, licensed CC BY-SA 4.0: the practices you
can see in code, written here in our own words as review checks. Each one
cites the practice it comes from; follow the link for the guide's reasoning
and examples. Section 1 (architecture and project layout) is design choice,
not defect, so it is under *Not findings*, except configuration (1.4), which
is under Going to production.

**All changed paths** means `git diff --name-only $(git merge-base <base> HEAD)`
plus `git ls-files --others --exclude-standard`: every file the change touches
since the merge base, untracked files included. That is the set `ts_scope.py`
compares, but the scope lists only code and config files, and the lockfile
check (5.4) and the Docker section depend on files it never lists. So the
node pass gets the base ref and all changed paths.

## How a practice becomes a finding

A practice is a lead, not a rule. Breaking one is a finding only when you can
write its **failure scenario**: concrete inputs or state, and the crash, hang,
wrong result, data loss or exposure they produce in this code. Each check
names the failure to look for; find it here, or drop the check.

- "No `unhandledRejection` handler" is a finding when you can name the
  rejection that goes unhandled and what the process does next. It is not a
  finding as a missing line.
- "Use a mature logger" is not a finding. "This `console.log(req.body)` writes
  the password field to the log" is one, and it is the security check, not the
  logging one.
- A practice the code already meets another way (a validation library other
  than the one the guide names, a reverse proxy that limits body size) is met.
  Check the config, middleware and infrastructure files before you claim a gap.

Severity follows the review's scale:

- **blocker**: a security exposure reachable from untrusted input; a crash
  or hang of the whole process on a normal path; data loss.
- **major**: wrong behaviour on a plausible path, such as a request that hangs,
  an error the client cannot act on, a deploy that drops in-flight requests,
  or a test that passes while the behaviour it names is broken.
- **minor**: a real defect on an unlikely path.

Put the practice number in the finding's `why`: `Why: an error from the
stream is never handled (Node.js best practice 2.13)`. The number is the
pointer; the failure scenario is the finding.

- **The failure, not the practice.** A finding that only says "this breaks
  practice 6.6" is a hunch. Drop it.
- **Practices that a diff cannot show are never findings.** *Not findings*
  below lists them: style the formatter owns, naming, team process, and
  tooling and vendor choices.
- **The change, not the codebase.** When you review a change (a change to a
  `Dockerfile` alone included), report what the diff adds or breaks: a gap
  that was already there is in scope only when the diff makes it worse or
  reachable. When asked about existing code with no change, every gap in the
  code named is in scope.
- **The guide lags the runtime.** Where Node.js itself now covers a practice
  (an unhandled rejection exits the process since Node 15; Express 5 forwards
  async errors), judge the code against the runtime and versions in
  `package.json` and `engines`, not against the guide's wording.

## Error handling

- **Callback-style async** in new code: an error passed to a callback that the caller never checks, or a throw inside a callback that no `try` can catch. Look for `fs.readFile(p, (err, data) => ...)` that ignores `err`. Failure: the handler continues with `undefined` data, or the process crashes. [2.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/asyncerrorhandling.md)
- **Thrown non-errors**: `throw 'not found'`, `throw { code: 404 }`, `reject(msg)`. Failure: no stack trace, and a central handler that reads `err.status` or `instanceof AppError` treats it as a crash or returns a 500 for a 404. [2.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/useonlythebuiltinerror.md)
- **Operational and programmer errors handled the same way**: a `catch` that answers 200 or retries on a `TypeError`, or one that crashes the process on a validation error. Failure: a bug is hidden as success, or one bad request restarts the service. [2.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/operationalvsprogrammererror.md)
- **Error handling scattered across routes**: a new route, job or queue consumer that logs and answers its own errors instead of handing them to the app's central handler. Failure: that entry point's errors miss the status mapping, logging fields or crash decision the rest of the app has. Cron jobs and consumers that are not wired to the handler at all are the usual case. [2.4](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/centralizedhandling.md)
- **A new error response the API contract does not declare**: a new status code or error body on a documented endpoint (OpenAPI, GraphQL schema) that the spec does not list. Failure: a generated client throws on the unknown status or shape. [2.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/documentingusingswagger.md)
- **Running on after an unknown error**: an `uncaughtException` handler that logs and keeps the process alive, or one that calls `process.exit()` before the log flushes and connections close. Failure: the process serves requests in a corrupt state, or exits with the cause lost. [2.6](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/shuttingtheprocess.md)
- **Error paths with no test**: a new `catch`, error status or retry that no test reaches. Failure: name the broken error path that would pass CI. (Also under Testing.) [2.8](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/testingerrorflows.md)
- **Unhandled rejections**: a new entry point (server, worker, CLI) with no `process.on('unhandledRejection')` policy, combined with a promise that can reject unobserved. Failure: on Node 15+ the process exits on the first one; on an older runtime or with `--unhandled-rejections=warn` the error is lost. [2.10](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/catchunhandledpromiserejection.md)
- **Validation deep inside instead of at the edge**: input used several calls in before anything checks it. Failure: a malformed payload half-writes (row inserted, then a throw) or fails with an unhelpful `TypeError` deep in a service. (Also under Security, 6.10.) [2.11](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/failfast.md)
- **`return promise` without `await` inside `try`**: `try { return db.save(x) } catch (e) { ... }`. Failure: the rejection skips the `catch` entirely; the async stack trace also loses this frame. [2.12](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/returningpromises.md)
- **Emitters and streams with no `'error'` listener**: a new stream, socket, child process or `EventEmitter` that can emit `'error'`, wrapped in a `try` as if that caught it. Failure: the first error event throws and takes the process down. [2.13](https://github.com/goldbergyoni/nodebestpractices#readme)

## Code patterns

- **Loose equality on input**: `==` or `!=` between values where one can come from a request, env or JSON. Failure: `'0' == 0`, `'' == 0` and `null == undefined` let a wrong value through a check. [3.10](https://github.com/goldbergyoni/nodebestpractices#readme)
- **Floating callbacks where a promise exists**: a new `util.promisify`-able API used with callbacks mixed into `async` code. Failure: the callback's error never reaches the surrounding `try`/`catch`. [3.11](https://github.com/goldbergyoni/nodebestpractices#readme)
- **Side effects at module load**: a database connect, network call, timer or `process.env` read-and-throw at the top level of an imported module. Failure: importing it in a test or a script opens connections or crashes before configuration is ready; an unhandled rejection at import time exits the process. [3.13](https://github.com/goldbergyoni/nodebestpractices#readme)
- **`require`/dynamic `import` inside a hot function**: a module loaded per request. Failure: a missing or broken module surfaces on the first request instead of at startup, and a synchronous `require` blocks the event loop each first call. [3.8](https://github.com/goldbergyoni/nodebestpractices#readme)
- **Deep imports into another package's internals**: `import x from 'lib/dist/internal/thing'`, or a package with an `exports` map that does not export a path its users import. Failure: the import breaks on the dependency's next minor release, or throws `ERR_PACKAGE_PATH_NOT_EXPORTED`. [3.9](https://github.com/goldbergyoni/nodebestpractices#readme)

## Testing

- **Only the happy path tested** for an endpoint or flow the diff adds. Look at the five outcomes a flow can have: the response, a state change (database), an outgoing call, a queued message, and an observability call (log, metric). Failure: name the outcome that could break with tests still green, e.g. the row is never written but the response is 201. [4.13](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/test-five-outcomes.md)
- **No API-level test for a new route**: only unit tests of the service, none that sends a request through routing, middleware and validation. Failure: a route registered under the wrong path, or a missing auth middleware, passes CI. [4.1](https://github.com/goldbergyoni/nodebestpractices#readme)
- **Shared fixtures and seeds**: a test that relies on rows another test or a global seed created, or mutates shared records. Failure: the test passes alone and fails (or passes wrongly) depending on order or parallelism. [4.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/avoid-global-test-fixture.md)
- **Real network calls to external services**: a test that hits a live third-party API, or no test of what happens when it answers 500, times out or returns a malformed body. Failure: flaky CI, and the failure path of the integration is never exercised. [4.10](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/mock-external-services.md)
- **Middleware logic tested only through one route**: a new auth, rate-limit or validation middleware with branches no test reaches. Failure: name the branch (expired token, missing header) that would pass CI broken. [4.11](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/test-middlewares.md)
- **Fixed port in tests**: a test server that listens on a hard-coded port. Failure: parallel test files or a dev server on that port fail with `EADDRINUSE`. Listening on port `0` picks a free one. [4.12](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/randomize-port.md)
- **Node version drift**: a change that relies on a Node API, flag or syntax newer than the version pinned in `.nvmrc`, `engines`, CI or the Dockerfile, or those disagree with each other. Failure: tests pass on the developer's Node and the build or production fails. [4.4](https://github.com/goldbergyoni/nodebestpractices#readme)

## Going to production

- **Config read without validation or defaults**: a new `process.env.X` read in place, with no schema, no type conversion and no default, instead of through the app's config module. Failure: a missing variable becomes `undefined` or `NaN` on the first request instead of failing at startup. [1.4](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/configguide.md)
- **Logs that cannot be correlated**: a new log line in a request path without the request or transaction id the app's other logs carry, or a new async boundary (queue, `setImmediate`, worker) that drops the `AsyncLocalStorage` context. Failure: an error log that cannot be tied to its request. [5.14](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/assigntransactionid.md)
- **The app choosing its log destination**: a logger configured to write to a file path or a vendor endpoint from code. Failure: in a container the file fills the writable layer and is lost on restart; logs never reach the platform's collector. [5.18](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/logrouting.md)
- **In-process state that must be shared**: sessions, uploads, rate-limit counters, caches or locks kept in memory or on local disk. Failure: with two instances, a user's session or a lock exists on one and not the other; a restart loses them. [5.12](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/bestateless.md)
- **Unbounded memory**: a module-level map, array or cache that grows with requests or users and is never evicted, or a whole file or result set read into memory. Failure: the process grows until the heap limit kills it. Give the growth per request or per user. [5.10](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/measurememory.md)
- **Unpinned or drifting dependencies**: a `package.json` change with no matching lockfile change (look at all changed paths before you claim one: the TypeScript scope never lists lockfiles), a lockfile deleted or ignored, or CI and Docker installing with `npm install` instead of `npm ci` (or the yarn/pnpm frozen-lockfile equivalent). Failure: production runs dependency versions no test ran against. [5.4](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/lockdependencies.md) [5.19](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/installpackageswithnpmci.md)
- **`NODE_ENV` not set for production**: a start script, Dockerfile or deploy config for production with no `NODE_ENV=production`, or code that enables debug output, stack traces or dev middleware unless it is set. Failure: production runs with development behaviour (stack traces in responses, unminified templates, verbose logging). [5.15](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/setnodeenv.md)
- **A runtime that is not LTS**: a Dockerfile, `.nvmrc` or CI matrix moved to an odd-numbered or end-of-life Node release. Failure: name the date security fixes stop for that version. [5.17](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/LTSrelease.md)
- **Static assets served by the Node process** on a hot path: `express.static` for large or many files with no CDN or proxy in front. Failure: give the expected traffic and the event-loop time it takes from API requests. [5.11](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/frontendout.md)
- **A maintenance or debug endpoint without auth**: a new route that exposes heap snapshots, memory, config or a REPL. Failure: anyone who finds the path reads secrets or stalls the process. [5.7](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/createmaintenanceendpoint.md)

## Security

- **Query built from strings**: SQL with template strings or `+`, a raw query helper with interpolation, a Mongo filter or `$where` taken from the request body. Failure: give the payload, e.g. `{"password": {"$ne": ""}}` logs in as anyone. [6.4](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/ormodmusage.md)
- **Request bodies not validated against a schema**: a new route that reads `req.body` fields with a type assertion and no runtime schema (zod, ajv, joi, class-validator). Failure: give the payload (a wrong type, an extra `role: "admin"` field, a nested object where a string was expected) and what the handler does with it. [6.10](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/validation.md)
- **No limit on body size**: a new body parser, upload route or raw-body webhook with no size limit, and no limit at the proxy. Failure: one large request holds memory and the event loop for every other user. [6.14](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/requestpayloadsizelimit.md)
- **No rate limit on an expensive or sensitive route**: a new login, password reset, OTP, search or export endpoint with no rate limiting in the app or in front of it. Failure: password guessing at full speed, or a handful of clients exhausting the service. [6.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/limitrequests.md) [6.12](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/login-rate-limit.md)
- **Secrets in code or config files**: a key, token, password or connection string committed in source, a config file, a test fixture or a Dockerfile `ARG`/`ENV`. Failure: anyone with read access to the repo or the image has the secret. [6.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/secretmanagement.md)
- **Missing security headers** on a new server or a changed header setup: no `helmet` (or equivalent), `X-Powered-By` left on, CSP or HSTS removed. Failure: name the attack the missing header leaves open on this app, e.g. clickjacking of the account page with no `frame-ancestors`. [6.6](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/secureheaders.md) [6.22](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/sessions.md)
- **A new dependency with known vulnerabilities**: a dependency added or upgraded to a version with a published advisory. Failure: name the advisory and whether this code reaches the vulnerable function. [6.7](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/dependencysecurity.md)
- **Passwords stored with a fast hash or reversibly**: a password or other human-chosen secret stored with `md5` or `sha1`/`sha256` and no key-stretching function, or encrypted where it should be hashed; or any secret compared with `===`. Failure: a leaked table is cracked offline; a `===` comparison leaks timing. Use `bcrypt`, `scrypt` or `argon2`, and `crypto.timingSafeEqual`. A random, high-entropy token (an API key from `crypto.randomBytes(32)`) is fine with SHA-256 or an HMAC: key stretching adds nothing there and costs every request. [6.8](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/userpasswords.md)
- **Unescaped output**: user data written into HTML, a server-rendered template with escaping turned off, a `<script>` block or a CSS value. Failure: give the stored value that runs as script in another user's browser. [6.9](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/escape-output.md)
- **JWTs that cannot be revoked**: long-lived access tokens with no expiry, or no way to revoke one (logout, password change, a compromised account). Failure: a stolen token keeps working until it expires, which may be never. [6.11](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/expirejwt.md)
- **`eval` and its relatives**: `eval`, `new Function`, `vm.runInThisContext`, or `setTimeout`/`setInterval` with a string, on anything input can reach. Failure: give the input that runs code on the server. [6.15](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/avoideval.md)
- **Regex that backtracks on input**: nested or overlapping quantifiers (`(a+)+`, `(\w+\s?)*$`) applied to request data, or a user-supplied pattern passed to `new RegExp`. Failure: give the input length that blocks the event loop for seconds. [6.16](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/regex.md)
- **Module or file loaded from a variable**: `require(x)`, `import(x)`, `fs.readFile(x)` or `res.sendFile(x)` where `x` derives from input. Failure: `../` reads files outside the intended directory, or loads attacker-chosen code. [6.17](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/safemoduleloading.md)
- **Untrusted code run in the main process**: plugins, user scripts or templates evaluated in the server's own context. Failure: the code reads `process.env` and the filesystem. [6.18](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/sandbox.md)
- **Shell built from input**: `exec`, `execSync` or `spawn(..., { shell: true })` with a template string containing input. Failure: give the input, e.g. a filename `a; rm -rf ~`. Prefer `execFile`/`spawn` with an argument array. [6.19](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/childprocesses.md)
- **Error details sent to the client**: `res.status(500).json(err)`, `err.stack` or `err.message` from a database or third-party error returned to the caller. Failure: the response shows the table names, file paths, SQL or internal hostnames. [6.20](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/hideerrors.md)
- **Input that crashes the process**: a request that can trigger an uncaught throw on a path that exits, e.g. `JSON.parse` of a header outside a `try`, or an async handler whose rejection is never forwarded. Failure: give the request; replaying it takes the service down repeatedly. [6.23](https://github.com/goldbergyoni/nodebestpractices#readme)
- **Open redirects**: `res.redirect(req.query.next)` or a `returnTo` parameter not checked against an allow list or a same-origin path. Failure: a login link that lands the user on an attacker's lookalike site. [6.24](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/saferedirects.md)
- **Secrets in a published package**: a publishable package with no `files` allow list and no `.npmignore`, next to `.env`, keys or test fixtures with credentials. Failure: `npm publish` ships them to the registry. [6.25](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/avoid_publishing_secrets.md)
- **A built-in shadowed in a bundle**: a built-in imported without the `node:` prefix (`import fs from 'fs'`) in code a bundler resolves, where its `resolve.alias` or `fallback` (webpack, Vite, esbuild) maps that bare name to a package. Plain Node always loads the core module first, so outside a bundler this is not a finding. Failure: name the alias and what the bundle ships instead of the built-in. [6.27](https://github.com/goldbergyoni/nodebestpractices#readme)
- **The process running as root**: a Dockerfile for a Node app with no `USER` (or `USER root`). Failure: a code-execution bug in the app is root in the container. [6.13](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/non-root-user.md)

## Performance

- **CPU-bound work on the event loop**: a synchronous hash, compression, image or PDF processing, a large `JSON.parse`/`JSON.stringify`, or a tight loop over user-sized data in a request handler. Failure: give the input size and the time every other request waits; move it to a worker thread or a job. [7.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/performance/block-loop.md)
- **A utility library pulled in for what the runtime does**: a new `lodash`/`underscore`/`moment` dependency in a hot path or a bundle where `Array`, `Object`, `structuredClone` or `Intl` covers it. A finding only with a measured cost: bundle size added, or an order-of-magnitude slowdown on the expected input. [7.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/performance/nativeoverutil.md)

## Docker

Apply this section when all changed paths (not only the files the TypeScript
scope lists, which never include them) take in a `Dockerfile`, a compose file, `.dockerignore` or the container's start command.

- **`npm start` (or any shell wrapper) as the container command**: one of all changed paths is a `Dockerfile` or compose file whose command is `CMD npm start`, `CMD ["npm", "run", "start"]`, a script (`sh start.sh`) or a compound shell command (`cd app && node server.js`). A bare `CMD node server.js` in shell form is one on Debian-based images (`node:*-bookworm`, `-slim`): their `/bin/sh` is dash, which stays PID 1 and runs node as its child. On Alpine (`node:*-alpine`) BusyBox `sh` execs the last command, so node is PID 1 there and the bare form is not a finding. When the base image is neither, confirm which process is PID 1 before you file it. Failure: npm or the shell does not forward `SIGTERM`, so the app never runs its shutdown code and is killed after the grace period, dropping in-flight requests. [8.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/bootstrap-using-node.md)
- **No graceful shutdown**: a new server or worker with no `SIGTERM` handler that stops accepting work, finishes in-flight requests and jobs, then closes connections. Failure: every deploy or scale-down cuts off the requests it was serving. [8.6](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/graceful-shutdown.md)
- **A process manager or cluster inside an orchestrated container**: PM2 or `cluster.fork()` under Kubernetes, ECS or a similar orchestrator. Failure: a crashed worker is restarted inside the container where the orchestrator cannot see it, and the health checks report a healthy container that is serving with fewer workers. [8.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/restart-and-replicate-processes.md)
- **Secrets copied into the image**: `COPY . .` with no `.dockerignore` covering `.env`, `.npmrc`, `.aws` and keys, or an npm token passed as a build `ARG` and left in a layer. Failure: anyone who can pull the image reads the secret from its layers. [8.4](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/docker-ignore.md) [8.11](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/avoid-build-time-secrets.md)
- **Dev dependencies and build tools in the final image**: a single-stage build, or no `--omit=dev` in the runtime stage. Failure: the image ships compilers and test tooling; name a concrete risk (size, a vulnerable dev dependency now in production). [8.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/multi_stage_builds.md) [8.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/install-for-production.md)
- **Mutable base image**: `FROM node:latest`, `FROM node` with no tag, or a tag that floats to another major. Failure: a rebuild silently changes the Node major version under the app. [8.9](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/image-tags.md)
- **No memory limit the runtime knows about**: a container memory limit with no matching `--max-old-space-size` (on Node versions that do not size the heap from the cgroup), or none at all. Failure: the heap grows past the container limit and the kernel kills the process without a heap error or a graceful exit. [8.7](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/memory-limit.md)
- **Cache-busting layer order**: `COPY . .` before `npm ci`. Failure: every code change reinstalls all dependencies; give the build time this adds in CI. [8.8](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/use-cache-for-shorter-build-time.md)

## Not findings

These practices from the guide are real advice but cannot be shown wrong from
a diff, or are taste the formatter and linter own. Never report them, even as
a nit.

- Project structure and layering, utilities as packages, framework choice and how much TypeScript to use: [1.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/breakintcomponents.md), [1.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/createlayers.md), [1.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/wraputilities.md), [1.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/choose-framework.md), [1.6](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/typescript-considerations.md).
- Which logger, APM or monitoring product to use: [2.7](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/usematurelogger.md), [2.9](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/errorhandling/apmproducts.md), [5.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/monitoring.md), [5.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/smartlogging.md), [5.8](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/apmproducts.md). A log line that leaks a secret is a security finding instead.
- Linting setup and code style: ESLint and its plugins, brace placement, statement separation, naming functions and conventions, `const` over `let`, arrow functions: [3.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/codestylepractices/eslint_prettier.md), [3.2](https://github.com/goldbergyoni/nodebestpractices#readme), [3.3](https://github.com/goldbergyoni/nodebestpractices#readme), [3.4](https://github.com/goldbergyoni/nodebestpractices#readme), [3.5](https://github.com/goldbergyoni/nodebestpractices#readme), [3.6](https://github.com/goldbergyoni/nodebestpractices#readme), [3.7](https://github.com/goldbergyoni/nodebestpractices#readme), [3.12](https://github.com/goldbergyoni/nodebestpractices#readme), [6.1](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/lintrules.md).
- How tests are named, laid out, tagged and measured: [4.2](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/3-parts-in-name.md), [4.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/aaa.md), [4.6](https://github.com/goldbergyoni/nodebestpractices#readme), [4.7](https://github.com/goldbergyoni/nodebestpractices#readme), [4.8](https://github.com/goldbergyoni/nodebestpractices#readme), [4.9](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/testingandquality/refactoring.md).
- Infrastructure and process outside the code: reverse proxy for TLS and gzip, process supervision, using every core, deployment pipeline, vulnerability scanners, outdated-package checks, npm 2FA, generic security and Docker advice, image size and scanning, Dockerfile linting, cache cleanup: [5.3](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/delegatetoproxy.md), [5.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/guardprocess.md), [5.6](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/utilizecpu.md), [5.9](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/productioncode.md), [5.13](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/production/detectvulnerabilities.md), [5.16](https://github.com/goldbergyoni/nodebestpractices#readme), [6.5](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/security/commonsecuritybestpractices.md), [6.21](https://github.com/goldbergyoni/nodebestpractices#readme), [6.26](https://github.com/goldbergyoni/nodebestpractices#readme), [8.10](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/smaller_base_images.md), [8.12](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/scan-images.md), [8.13](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/clean-cache.md), [8.14](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/generic-tips.md), [8.15](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/docker/lint-dockerfile.md).
