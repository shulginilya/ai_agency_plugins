# Audit checklist

Work top to bottom. Skip a section with a one-line reason rather than silently.

## Scope and history

- [ ] The PR does one thing; the title describes it accurately
- [ ] Unrelated refactors, formatting sweeps and dependency bumps are separate
- [ ] Commits are individually revertible; no "fix", "wip", "oops" left in history
- [ ] Generated files, lockfiles and build output are intentional, not accidental
- [ ] Nothing committed that should not be: secrets, `.env`, personal paths, debug logs

## Contracts

- [ ] Public API changes are additive, or versioned, or have a deprecation path
- [ ] Response payload shape changes are backward compatible for existing clients
- [ ] Event and queue message shapes are versioned; old consumers still parse them
- [ ] Shared types changed in lockstep with every consumer in the repo

## Data

- [ ] Migrations are expand-contract: add nullable, backfill, switch reads, then drop
- [ ] Every migration has a tested down path, or an explicit note that it is one-way
- [ ] Backfills are batched and resumable, not one statement over the whole table
- [ ] New columns have indexes where they are queried, and defaults that do not
      rewrite the table
- [ ] Data loss is impossible on rollback, or is called out explicitly

## Deploy and rollback

- [ ] Ordering is stated when more than one deploy step is required
- [ ] Old and new code can run simultaneously during a rolling deploy
- [ ] Feature flags default to off, and the off path is the current behaviour
- [ ] The rollback procedure is one action, and someone has said what it is
- [ ] Infrastructure changes (IAM, security groups, queues) are least-privilege

## Operations

- [ ] New failure modes produce a log line with enough context to debug
- [ ] Metrics or traces exist for anything with a latency or error budget
- [ ] Alerts exist for the failure that would otherwise be discovered by a user
- [ ] Timeouts, retries with backoff, and idempotency on anything over a network
- [ ] Nothing new logs a secret, a token, or personal data

## Verification

- [ ] CI is green, and the failures that were re-run were understood, not retried
- [ ] Tests cover the behaviour that changed, not only the lines that changed
- [ ] Someone has run it — say who, and against what
- [ ] The PR description tells a reviewer how to verify it themselves
