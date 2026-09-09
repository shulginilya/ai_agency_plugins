---
description: Implement a feature, ticket or fix end to end — orient, plan, build in slices, verify with the repo's own checks, self-review.
argument_hint: "[what to build, a ticket reference, or a path]"
model: sonnet
allowed_tools: Bash(git:*) Bash(python:*) Read Edit Write Grep Glob
---

Implement: {{ARGS}}

If that is empty, ask what to implement — but first run
`python {{PLUGIN_ROOT}}/skills/feature-implementation/scripts/verify.py` and report the checks
this repository runs, so the question comes with context.

Follow the `feature-implementation` skill:

1. **Orient.** Find the module that owns this concern and the closest existing
   equivalent; read it in full. Note the contract and the tests around it.
2. **Plan.** State goal, slices, contracts, risk and verification in the
   conversation. Wait for agreement when the change alters a contract or
   touches migrations, auth, money or data deletion; otherwise proceed.
3. **Build slice by slice.** Tests with the code, unhappy paths in the same
   slice, no unrelated changes.
4. **Verify.** `python {{PLUGIN_ROOT}}/skills/feature-implementation/scripts/verify.py --run`,
   the whole set, and report failures you did not cause rather than ignoring
   them.
5. **Self-review** against `references/handoff.md`, then report in the skill's
   Done / Changed / Verified / Not done format.

Do not report a change as finished while any part of the plan is unproven —
name what is left instead.
