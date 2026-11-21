# Security pass

Load this when the change touches input handling, authentication, data access,
file or network I/O, secrets, or dependencies.

## Trust boundaries

Draw the line where untrusted data enters. Everything crossing it needs
validation at the boundary, not at the point of use — validation at the point
of use is validation you will forget somewhere.

- Request bodies, query strings, path params, headers, cookies
- Webhook payloads (verify the signature before parsing, not after)
- File uploads (type, size, and the path you write them to)
- Anything read back from a queue, cache, or third-party API

## The recurring defects

**Injection.** String-concatenated SQL, shell commands built from user input,
`eval` on anything derived from a request. Parameterize; pass argument arrays
to `spawn`, never a command string to a shell.

**Broken authorization.** Authentication answers *who*; authorization answers
*may they*. The common miss is an endpoint that checks a valid session but not
that the session owns the record being read or written. Check every handler
that takes an ID from the request.

**Secrets in the wrong place.** Keys in source, in client bundles, in logs, in
error messages returned to the caller, in a `NEXT_PUBLIC_*` variable. Check
what the error handler serializes before it sends.

**IDOR and enumeration.** Sequential IDs plus a missing ownership check leaks
the whole table one request at a time.

**SSRF.** A URL from a request that the server then fetches. Allowlist the
host; block link-local and private ranges (169.254.0.0/16, 10/8, 172.16/12,
192.168/16, ::1).

**XSS.** `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, or any templating
that bypasses escaping. If the value can reach a page, it needs sanitizing at
render, and a Content-Security-Policy behind it.

**Deserialization and prototype pollution.** Merging an untrusted object into a
config or defaults; `__proto__` and `constructor` keys in a JSON body.

**Weak crypto and randomness.** `Math.random()` for tokens, MD5 or SHA-1 for
passwords, a hand-rolled comparison for secrets (use a constant-time compare),
a hard-coded IV.

**Dependency risk.** A new direct dependency in the diff: check what it pulls
in, when it was last released, and whether it needs the permissions it asks
for. A postinstall script in a new transitive dependency is worth a comment.

## Cloud and infrastructure

- IAM policies with `"*"` in Action or Resource
- Storage buckets or blobs that became public in this change
- Security groups opening a port to 0.0.0.0/0
- Secrets passed as environment variables in a task definition that gets logged
- Missing encryption at rest on a new data store

## What not to report

Theoretical issues with no reachable path, and framework behaviour the
framework already handles (a modern ORM's parameterization, a template
engine's default escaping). Say what an attacker does, step by step, or drop
the finding.
