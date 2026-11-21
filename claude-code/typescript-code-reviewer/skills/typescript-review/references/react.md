# React pass

Load this when `ts_scope.py` tags a changed file `react`: a `.tsx`/`.jsx`
file, a `'use client'` module, or one that imports React, Next.js or a
`react-*` library. Read the component's whole file and its parent: most React
defects are about when code runs, not what it says.

## Hooks

- **Rules of hooks.** A hook called after an early `return`, inside a
  condition or a loop, or from a plain function. React throws "Rendered more
  hooks than during the previous render" when the condition flips.
- **Effect dependencies.** A value read in `useEffect`, `useMemo` or
  `useCallback` but missing from the deps: the effect sees the first render's
  value forever (stale closure). Name the prop or state change that the
  effect then ignores.
- **Effects that run every render.** A dependency that is a new object, array
  or function each render (`{...}`, `[]`, an inline arrow, a non-memoized
  context value) re-runs the effect on every render; with a `setState`
  inside, it loops.
- **Missing cleanup.** A subscription, interval, timeout, event listener,
  WebSocket or observer created in an effect with no cleanup: it leaks and
  fires after unmount, and StrictMode's double mount makes it fire twice.
- **Async races.** A fetch in an effect with no `AbortController` or ignore
  flag: typing `ab` then `abc` fast can show `ab`'s results last. Name the
  ordering that shows stale data.
- **`setState` from an old value.** `setCount(count + 1)` twice in one tick
  adds one; use the updater form when the next state depends on the last.

## State

- **Mutation.** `state.items.push(x); setState(state)` or sorting a state
  array in place: same reference, so React skips the render.
- **Props copied into state.** `useState(props.value)` reads the prop once;
  a later prop change never shows. Derive it during render, or key the
  component.
- **Controlled to uncontrolled.** `value={maybeUndefined}` on an input switches
  modes when the value arrives, and React warns and drops edits.
- **Keys.** Index keys on a list that can reorder, insert or delete: state and
  focus stay with the position, not the item. Duplicate keys drop items.
- **Derived data recomputed** on every render over a large list with no
  `useMemo`: give the size where it hurts.

## Server, client and hydration

- **Hydration mismatch.** `Date.now()`, `Math.random()`, `new Date()`
  formatting in the user's locale, `window`, `localStorage` or
  `typeof window` checks during render of a server-rendered component: the
  server HTML differs from the client's first render.
- **Server-only code in the client bundle.** A `'use client'` module (or a
  module it imports) that reads a secret from `process.env`, imports a
  database client, or a server action file without `'use server'`. In Next.js
  only `NEXT_PUBLIC_*` variables reach the browser; anything else is
  `undefined` there, or worse, gets inlined into the bundle by a custom
  `define`.
- **Server actions and route handlers** take their input from the client:
  they need the same validation and authorization as any API route (run the
  node pass on them).

## Rendering untrusted data

- `dangerouslySetInnerHTML` with anything a user or an API controls, without
  a sanitizer: stored XSS.
- `href={url}` or `src={url}` from user data: `javascript:` URLs run script.
  Allow `http:`/`https:` (and what the app needs) only.
- Spreading untrusted objects into props (`<a {...userProps}>`) can set event
  handlers or `dangerouslySetInnerHTML`.

## Errors and loading

- A component that throws during render with no error boundary above it
  unmounts the whole tree: name the data that makes it throw.
- A `Suspense` boundary missing above a component that suspends, or a
  loading state that never ends because an error path never sets it back.
- A form that submits twice on double click or Enter because nothing
  disables it while the request is in flight.

## Accessibility that breaks use

Only what stops someone from using the feature: a clickable `div` with no
role, keyboard handler or focus; an icon-only button with no accessible name;
an input with no label; focus lost after a modal closes. Leave the rest to a
full accessibility review.

## Reporting

Name the interaction or data that triggers it and what the user sees: "typing
in the search box faster than the API responds shows results for an earlier
query, because the effect at `Search.tsx:24` sets state from every response
in arrival order."
