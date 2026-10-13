---
name: ux-review
description: Reviews an existing interface — screens, flows or a UI diff — for usability, accessibility (WCAG 2.2 AA) and consistency with the project's own design tokens and components, and reports findings ranked by severity, each with the concrete user who gets hurt and how. Use when asked to review UX or UI, audit a screen, flow or page, check accessibility or color contrast, find usability problems, or check that new UI matches the design system.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# UX review

Judge the interface from the user's side of the screen. A finding counts only
if you can name who gets stuck, at which step, and what they see. "Could be
cleaner" is taste, and it is not a finding.

```bash
python scripts/ui_inventory.py --root .          # stack, tokens, components, pages, theming
python scripts/contrast.py "#767676" "#ffffff"    # WCAG ratio and the marks it meets
python scripts/contrast.py --pairs pairs.txt      # many pairs; exit 1 if any fails AA
```

## 1. Scope it

- **What:** a diff (`git diff <base>...HEAD -- <ui paths>`), a flow (sign up,
  upload a file), or named screens. A review of "the whole app" finds nothing
  deep. Ask for, or pick and state, the two or three flows that matter most.
- **For whom:** the task's user, from the ticket or the README. A developer
  tool and a consumer app fail differently.
- **Against what:** run `ui_inventory.py`. The project's own tokens and
  components are the standard. A hard-coded `#3b82f6` beside a `--primary`
  token is a finding. A color you would have picked differently is not.

## 2. Look at it running

Read the code, and also look at the running interface whenever you can. The
README or `/verify` says how to start it.

- Take each flow end to end at desktop width and at about 375px.
- Do it in light and dark mode where the app has both.
- Go keyboard only, with Tab, Shift+Tab, Enter, Space and Escape.
- Force every state you can: empty list, slow network, server error, a very
  long name, no permission.

If it cannot run, review from the code and say so in the report.

## 3. Check it

Work through [references/heuristics.md](references/heuristics.md) for
usability and [references/wcag-checklist.md](references/wcag-checklist.md) for
accessibility. The checks that find the most real problems:

- **Missing states:** what the user sees while loading, when empty, on error,
  and after success.
- **Feedback:** every action shows that it happened. Destructive ones can be
  undone or ask for confirmation.
- **Contrast:** run `contrast.py` on text and on the tokens behind it, in both
  themes. Don't eyeball it.
- **Keyboard and focus:** everything reachable, a visible focus ring, a
  logical order, and focus moved into and back out of dialogs.
- **Labels:** every input and icon-only button has an accessible name.
- **Copy:** names things the way the user would. Error messages say what
  happened and what to do next.
- **Consistency:** the same action looks and is worded the same everywhere,
  and uses the shared component rather than a lookalike.

For a whole flow, hand it to the `first-time-user` subagent as well. It walks
the flow knowing only what the screen says, so it catches what you can no
longer see.

## 4. Report

Rank by harm: **blocker** (the user cannot finish the task, or a WCAG A or AA
failure), **major** (they finish, but slowly or with an error), **minor**
(friction or inconsistency).

```
[blocker] Upload — no error state
Where:  components/upload-form.tsx:42, step 2 of "upload a session"
Who:    a user whose file is over 10 MB
Sees:   the spinner stops and nothing else happens; they retry, then give up
Fix:    show the error inline under the drop zone with the limit and "Choose a smaller file"
Check:  WCAG 3.3.1 Error Identification
```

End with the flows and checks you could not cover and why, such as "dark mode
not reviewed: no toggle in the running app". When a finding should become a
ticket, file it with the `ticket-management` skill, under the same approval
rules as any other ticket write.
