# Accessibility pass

Load this when the change touches user-facing markup or interaction.

Target WCAG 2.2 AA. Report violations as defects, not preferences — an
inaccessible control is broken for a real user.

## Structure

- One `h1` per page, headings in order with no skipped levels
- Landmarks used for what they are: `main`, `nav`, `header`, `footer`, `aside`
- Lists as lists, tables as tables with `th` and `scope`
- Language set on `html`

## Controls

- Every interactive element is a real control. A `div` with an `onClick` is
  not focusable, not announced, and does not fire on Enter or Space. Use
  `button` or `a`; if you cannot, it needs `role`, `tabIndex={0}` and keyboard
  handlers, and that is a worse outcome.
- Every input has a programmatically associated label (`htmlFor` / `id`), not
  just a placeholder
- Icon-only buttons carry an accessible name (`aria-label`)
- Disabled controls explain why somewhere a screen reader can reach

## Keyboard

- Everything reachable by mouse is reachable by Tab, in a sensible order
- Focus is visible — check that a reset stylesheet has not removed the outline
- Modals trap focus while open, restore it on close, and close on Escape
- No keyboard trap anywhere

## State and feedback

- Loading, error and success states are announced (`aria-live="polite"`, or
  `assertive` for errors), not conveyed by colour or motion alone
- Form errors are tied to their field (`aria-describedby`, `aria-invalid`)
- Expand/collapse and toggle state exposed with `aria-expanded` / `aria-pressed`

## Presentation

- Contrast: 4.5:1 for body text, 3:1 for large text and UI boundaries
- Text resizes to 200% without loss of content or function
- Nothing conveyed by colour alone
- `prefers-reduced-motion` respected for anything that moves
- Images have alt text; decorative images have `alt=""`

## ARIA

The first rule of ARIA is not to use ARIA. A native element beats a `role`
every time. Wrong ARIA is worse than none: check that any `role` in the diff
brings the keyboard behaviour that role implies.
