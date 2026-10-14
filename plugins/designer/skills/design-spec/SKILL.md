---
name: design-spec
description: Writes the design spec a developer builds and tests against for one ticket or feature — the user flow, every screen state (empty, loading, error, success, no permission), layout and responsive behavior, copy, accessibility and testable acceptance criteria — using the project's own tokens and components, with an optional low-fidelity HTML wireframe. Use when asked to design a screen, page, flow or feature, spec the UI for a ticket, write UX requirements, sketch a wireframe, or decide how something should look and behave before it is built.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Design spec

A spec exists so the developer never has to guess what the user sees. A screen
the spec doesn't describe will be built in its happy state only, and its
empty, error and loading states will be improvised in code review.

```bash
python ../ux-review/scripts/ui_inventory.py --root .    # tokens, components and pages to build from
python ../ux-review/scripts/contrast.py FG BG           # check any new color pairing
```

## 1. Understand the job

- Read the ticket whole, including comments. Restate in one sentence who the
  user is, what they are trying to get done, and how they will know they have.
  If you can't, ask that question and stop. Don't design around a guess.
- Find what already exists. Run `ui_inventory.py`, then open the closest
  existing screen and the shared components it uses. New UI that looks like
  the rest of the product beats new UI that looks better.
- List the constraints: data the screen has or lacks, permissions, platforms,
  and performance.

## 2. Write the flow

Number the steps from entry point to done, and include the way back out:

```
1. From the Sessions list, the user selects "Upload session".
2. A dialog asks for a .jsonl file (drag-and-drop or "Choose file").
3. ...
Exit: Cancel or Escape closes the dialog at any step without uploading.
```

Every branch a real user takes belongs here: a wrong file type, a duplicate,
a lost connection.

## 3. Specify each screen and its states

Use [references/spec-template.md](references/spec-template.md). For each
screen:

- **Layout:** regions top to bottom, and what changes at about 375px, 768px
  and 1280px.
- **Components:** name the project's existing ones (`Button variant="primary"`,
  `Dialog`). Introduce a new component only with a reason.
- **Tokens:** colors, type and spacing by token name, never raw values. Check
  every new text and background pairing with `contrast.py` in both themes.
- **States:** loading, empty, partial and long content, error, success, and no
  permission. Each one says what the user sees and what they can do next.
- **Copy:** every visible string, final wording, in the product's voice.
  Errors say what happened and what to do.
- **Accessibility:** focus order, where focus goes on open and close,
  accessible names for icon-only controls, what is announced (`role="status"`),
  and keyboard shortcuts.

## 4. Optional: a wireframe

When layout is the hard part, add a low-fidelity HTML wireframe at
`docs/design/<ticket>-<slug>.html`:

- grey boxes and real copy,
- the project's CSS custom properties where they exist,
- every state shown as its own labelled frame on one page.

It is a sketch for agreement, not code to ship. Say so at the top of the file.

## 5. Acceptance criteria

End with checkboxes a developer can verify and a reviewer can test. One per
state, plus the accessibility and responsive ones:

```
- [ ] Given no sessions, the list shows "No sessions yet" and an "Upload session" button
- [ ] Given a file over 10 MB, an inline error names the limit and the upload does not start
- [ ] The dialog can be completed with the keyboard alone, and focus returns to "Upload session" on close
- [ ] At 375px the dialog fills the width and nothing scrolls sideways
```

## 6. Hand it over

The designer does not write tickets. Only developer and scrum-master manage
them. Give the spec in your reply, or in your report under a crew brief, ready
to paste under `## Design` in the ticket's body or as a comment. Say which
ticket it belongs to, so the developer or scrum-master can attach it. If the
spec splits the work, propose the slices; scrum-master's `story-splitter` owns
the split.
