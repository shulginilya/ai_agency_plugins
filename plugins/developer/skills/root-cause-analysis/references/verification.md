# Verification

The fix is not done when the symptom stops. It is done when the mechanism is
gone, proved gone, and cannot return unnoticed.

## The failing test comes first

Write the test before the fix and watch it fail. A test written afterwards
routinely passes against the broken code too — it tests the fix, not the bug.

The order is exactly:

1. Write the test that encodes the trigger from step 4 of the diagnosis.
2. Run it against the unfixed code. **It must fail, for the reported reason.**
   A test that fails with a different error is testing something else.
3. Apply the fix.
4. Run it again. It passes.
5. Revert the fix, confirm it fails again, reapply. This is the two-way proof
   and it takes thirty seconds.

If step 2 will not fail, the test does not capture the bug. Fix the test.

## What the test should assert

Assert the invariant that was violated, not the shape of the fix. `total`
equals the sum of line items after a discount is removed is durable; "the
`recalculate` function is called twice" breaks the next time anyone touches the
implementation and tells you nothing about correctness.

One test for the reported trigger. One more for the boundary next to it — the
empty case, the zero, the concurrent second call — because the reported trigger
is rarely the only one the mechanism accepts.

## Sweep for the same mechanism

A bug is a pattern that appeared once. Before closing, search for the pattern:

```bash
grep -rn "<the unguarded call, the same coercion, the same cache key shape>" src
git log -L <start>,<end>:<fixed file>
```

The `regression-triage` skill's `history.py` does the same sweep with authors
and dates grouped; reach for it by skill name, never by a path into a sibling
skill.

The history of the fixed lines usually shows the same author, the same week and
the same idiom copied elsewhere. List every other site you found, and either
fix them in the same change (if identical and small) or name them explicitly as
follow-ups. Silently fixing one of five is how the same incident recurs.

## Make it observable

Ask what production would have shown had this happened at 3am with nobody
watching. If the answer is "nothing", the change is incomplete. Add the log
line, the metric, or the alert — at the point where the invariant is now
checked, with enough fields to identify the trigger.

Prefer an assertion that fails loudly in test and a counter that rises in
production over a log line nobody reads.

## Close-out checklist

- The test fails without the fix and passes with it — verified in both
  directions
- Temporary logging, prints and debugger statements are removed
- The change contains the fix and its test, and nothing else
- Every other site of the same mechanism is fixed or listed
- The failure is now visible in monitoring if it recurs
- The report names the cause, not just the change
