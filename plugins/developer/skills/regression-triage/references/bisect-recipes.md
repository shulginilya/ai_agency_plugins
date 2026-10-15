# Bisect recipes

`git bisect run` semantics, and the cases where the naive invocation lies to
you.

## Exit codes the verdict command must respect

| Exit | Meaning to bisect |
| --- | --- |
| 0 | good |
| 1–124, 126, 127 | bad |
| 125 | **skip** — cannot be tested (does not build, missing fixture) |
| 128–255 | abort the bisect entirely |

Wrap the verdict so an unbuildable commit exits 125 rather than 1. Otherwise
every commit that predates a build change is silently marked "bad" and bisect
converges on the wrong sha:

```bash
#!/bin/sh
npm ci --silent || exit 125
npm test -- cart.total
```

## Old commits need their own dependencies

The lockfile at each commit is part of that commit. Installing once at the
start and bisecting on top of it tests today's dependencies against yesterday's
code, which is a different question — and occasionally the answer you actually
want, but only deliberately.

```bash
git bisect run sh -c 'npm ci --silent || exit 125; npm test -- cart.total'
git bisect run sh -c 'pip install -q -e . || exit 125; pytest -x -q tests/test_cart.py'
```

Add the install step whenever the range crosses a lockfile change. Check with
`git log --oneline <good>..<bad> -- package-lock.json pnpm-lock.yaml poetry.lock`.

## Flaky verdicts

Bisect assumes a deterministic answer. A verdict that fails 1 run in 5 will
mark good commits bad. Repeat the test and take the aggregate:

```bash
# bad if it fails at least once in ten
git bisect run sh -c 'for i in $(seq 10); do npm test -- cart.total || exit 1; done; exit 0'
```

If the failure rate is low enough that ten runs are not conclusive, bisect is
the wrong tool — stabilise the repro first, or fall back to reading history.

## Merge-heavy history

Bisecting through every commit on every merged branch tests states that were
never released and often do not build:

```bash
git bisect start --first-parent <bad> <good>
```

That finds the merge commit that introduced the regression. Then bisect inside
that branch separately if you need the specific commit.

## Squashed or shallow history

`git bisect` needs the commits. A shallow clone has to be deepened first:

```bash
git fetch --unshallow
```

With squash merges, the finest granularity available is the squashed commit —
which is usually a whole PR. Say so in the report rather than implying a
line-level culprit.

## Bisecting something other than commits

The technique is bisection, not git. When the code range comes back empty:

- **Dependencies.** Pin the previous resolution of one package at a time,
  halving the set of upgraded packages each round. `npm ls <pkg>` and the
  lockfile diff give you the list.
- **Configuration.** Diff the environment between the working and broken
  deployment, then apply half the differing keys at a time.
- **Data.** Bisect the input, not the code: half the rows, half the fields.
- **Deploys.** When the pipeline changed and the code did not, bisect the base
  image or the build config the same way.

## Manual bisect, when scripting the verdict is impossible

```bash
git bisect start
git bisect bad                 # current commit is broken
git bisect good v1.4.0
# ... test by hand at each step, then:
git bisect good     # or: git bisect bad     # or: git bisect skip
git bisect log > bisect.log    # keep the record before resetting
git bisect reset
```

`git bisect log` is worth saving: it is the audit trail of what was tested and
lets someone replay the run with `git bisect replay bisect.log`.

## Always reset

```bash
git bisect reset
```

Run it even after a failed or interrupted bisect. A repo left in a detached
bisect state is the cause of the next hour's confusion, and `git status` says
so only if you read past the first line.
