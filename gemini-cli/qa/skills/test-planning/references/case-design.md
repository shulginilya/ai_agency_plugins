# Case design checklist

Use it to choose cases, not to fill a quota. A case earns its place when it
could fail in a way the others would miss.

## Inputs

- **Empty:** no items, empty string, missing optional field.
- **One / many:** exactly one item, the page size, one more than the page size.
- **Bounds:** the stated minimum and maximum, one inside, one outside
  (for example 10 MB, 10 MB − 1 byte, 10 MB + 1 byte).
- **Shape:** very long text, leading or trailing spaces, unicode and emoji,
  right-to-left text, HTML or SQL-looking text, which must be shown, not run.
- **Numbers:** 0, negative, decimals, very large, the wrong locale's separator.
- **Time:** time zones, midnight, month end, a leap day, a clock going back.

## State

- First use (nothing set up) versus a returning user with data.
- Logged out, logged in, wrong role, a session that expired mid-flow.
- The same action twice: double submit, back then resubmit, two tabs.
- Concurrent change: someone else edits or deletes the record meanwhile.

## Failure

- Network down, slow (more than 10 s), or failing with 500 or 404.
- A downstream service returning nonsense or a partial result.
- Disk full, quota exceeded, rate limited.
- The user's own mistakes: a wrong file type, a typo, cancelling halfway.

## Regression

- What else reads or writes the same data, screen or endpoint?
- What did the last bug fix in this area protect? Is that test still there?
- Does the old way of doing it still work, if the change was additive?

## UI and accessibility

- Keyboard only: reach, operate and leave every control. Escape closes.
- Focus is visible and lands somewhere sensible after each action.
- Every input and icon button has a name a screen reader announces.
- Text contrast is at least 4.5:1, or 3:1 for large text and UI parts.
  The designer's `contrast.py` checks it.
- At 375 px wide nothing scrolls sideways, and the main action is visible.

## Evidence that counts

The command and its output, a screenshot path, the response body, a log
line, a row count. "Looked fine" isn't evidence. A pass nobody else could
check is recorded as not run.
