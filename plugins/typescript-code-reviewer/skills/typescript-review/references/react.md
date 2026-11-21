# React pass

Load this when `ts_scope.py` tags a changed file `react`: a `.tsx`/`.jsx`
file, a `'use client'` module, or one that imports React, Next.js or a
`react-*` library. Read the component's whole file and its parent: most React
defects are about when code runs, not what it says.

The checks come from two sources. The correctness and security checks (hooks,
state, hydration, untrusted data, errors, accessibility that breaks use) are
this plugin's own. The performance checks come from
[React Best Practices](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices)
by Vercel Engineering, licensed MIT: its rules for React and Next.js, written
here in our own words as review checks. A check from the guide cites its rule;
follow the link for the guide's reasoning and its incorrect and correct
examples.

## How a practice becomes a finding

A rule is a lead, not a verdict. It becomes a finding only with a **failure
scenario** in the code under review:

- **Correctness and security:** name the interaction or data that triggers
  it and what the user sees, or who gets what they should not.
- **Performance:** give an **order-of-magnitude estimate** at the size the
  code will see: the network round trips added before the page renders, the
  kilobytes added to a route's initial bundle, the renders per keystroke or
  scroll event, the milliseconds of main-thread work. A rule broken with
  nothing measurable at stake is not a finding. When the number is not
  obvious, say how to measure it (the bundle analyzer, the React Profiler)
  rather than invent one.

Severity follows the review's scale:

- **blocker**: a security exposure (XSS, a server action anyone can call,
  one user's data rendered for another), or a crash or blank screen on a
  normal path.
- **major**: wrong behaviour on a plausible path, or a performance regression
  on a normal path that the estimate shows users will notice: a full extra
  round trip before the page renders, a large library added to every page's
  initial bundle, input that lags on every keystroke.
- **minor**: a real defect on an unlikely path, or a performance cost that is
  measurable but small.

Put the rule id in the finding's `why`: `Why: the two queries are independent
but awaited in turn (React best practices: async-parallel)`. Name the
interaction or data and what the user sees: "typing in the search box faster
than the API responds shows results for an earlier query, because the effect
at `Search.tsx:24` sets state from every response in arrival order."

- **The stack decides.** Many rules name Next.js (`next/dynamic`, `after()`,
  `optimizePackageImports`), React Server Components (`React.cache()`), SWR,
  or recent React APIs (`useEffectEvent`, `<Activity>`, `toSorted()`). Apply
  a rule only where the project has that stack and version (`package.json`,
  `next.config.*`, the build target), and accept another tool that does the
  same job (TanStack Query for SWR, `React.lazy` for `next/dynamic`).
- **The change, not the codebase.** Report what the diff adds or makes worse.
  A slow pattern that was already there is in scope only when the diff makes
  it slower or puts it on a hotter path.

## Hooks and effects

- **Rules of hooks.** A hook called after an early `return`, inside a condition or a loop, or from a plain function. React throws "Rendered more hooks than during the previous render" when the condition flips.
- **Effect dependencies.** A value read in `useEffect`, `useMemo` or `useCallback` but missing from the deps: the effect sees the first render's value forever (stale closure). Name the prop or state change that the effect then ignores.
- **Effects that run every render.** A dependency that is a new object, array or function each render (`{...}`, `[]`, an inline arrow, a non-memoized context value) re-runs the effect on every render; with a `setState` inside, it loops. Depend on the primitive the effect reads (`user.id`, not `user`) [`rerender-dependencies`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-dependencies.md). A `useEffectEvent` function listed in the deps does the same: its identity changes every render by design [`advanced-effect-event-deps`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/advanced-effect-event-deps.md).
- **Missing cleanup.** A subscription, interval, timeout, event listener, WebSocket or observer created in an effect with no cleanup: it leaks and fires after unmount, and StrictMode's double mount makes it fire twice.
- **Async races.** A fetch in an effect with no `AbortController` or ignore flag: typing `ab` then `abc` fast can show `ab`'s results last. Name the ordering that shows stale data.
- **`setState` from an old value.** `setCount(count + 1)` twice in one tick adds one, and a callback that closes over `count` keeps the value it was created with; use the updater form when the next state depends on the last. [`rerender-functional-setstate`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-functional-setstate.md)
- **An action modelled as state plus an effect.** A click sets `submitted`, and an effect posts when `submitted` is true. Failure: the post repeats when another dependency of the effect changes, or runs twice under StrictMode. Run the action in the event handler. [`rerender-move-effect-to-event`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-move-effect-to-event.md)
- **App-wide setup in a component effect.** Analytics or SDK initialization, or a global listener, in `useEffect(() => ..., [])`. Failure: it runs again whenever the component remounts (a route change, a key change, StrictMode in development), double-counting events or stacking listeners. Guard it at module level or move it to the entry module. [`advanced-init-once`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/advanced-init-once.md)
- **A component defined inside another component.** `function Row() { ... }` declared in a parent's body. Failure: every parent render creates a new component type, so React remounts it: an input inside loses focus and its text on each keystroke, and its state resets. [`rerender-no-inline-components`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-no-inline-components.md)

## State

- **Mutation.** `state.items.push(x); setState(state)` or sorting a state array in place: same reference, so React skips the render. `.sort()` and `.reverse()` on a prop also mutate the parent's array; copy first or use `toSorted()` where the build target has it. [`js-tosorted-immutable`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-tosorted-immutable.md)
- **Props copied into state.** `useState(props.value)` reads the prop once; a later prop change never shows. State synced from props or other state in an effect is the same defect: a render shows the stale value before the effect fixes it, and the two drift when one path forgets the update. Derive it during render, or key the component. [`rerender-derived-state-no-effect`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-derived-state-no-effect.md)
- **Controlled to uncontrolled.** `value={maybeUndefined}` on an input switches modes when the value arrives, and React warns and drops edits.
- **Keys.** Index keys on a list that can reorder, insert or delete: state and focus stay with the position, not the item. Duplicate keys drop items.
- **`&&` with a number.** `{items.length && <List />}` renders `0` when the list is empty, and `NaN` renders as text. Use a boolean condition or a ternary. [`rendering-conditional-render`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-conditional-render.md)
- **Stored state without a version, or with secrets.** A value read back from `localStorage` as the current type with no version in the key and no validation: after a deploy changes the shape, the old value breaks the parse or the render. Or a token, an email or a whole user object written there, readable by any script on the origin. [`client-localstorage-schema`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/client-localstorage-schema.md)

## Server, client and hydration

- **Hydration mismatch.** `Date.now()`, `Math.random()`, `new Date()` formatting in the user's locale, `window`, `localStorage` or `typeof window` checks during render of a server-rendered component: the server HTML differs from the client's first render. For client-only data that must show without a flash (a theme, a stored preference), an inline script that sets it before hydration is the fix, not an effect after mount [`rendering-hydration-no-flicker`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-hydration-no-flicker.md). `suppressHydrationWarning` is for an expected one-node difference such as a timestamp; anywhere else it hides a real mismatch and the wrong server content stays [`rendering-hydration-suppress-warning`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-hydration-suppress-warning.md).
- **Server-only code in the client bundle.** A `'use client'` module (or a module it imports) that reads a secret from `process.env`, imports a database client, or a server action file without `'use server'`. In Next.js only `NEXT_PUBLIC_*` variables reach the browser; anything else is `undefined` there, or worse, gets inlined into the bundle by a custom `define`.
- **Server actions without their own auth check.** A `'use server'` function that reads or changes data with no authentication and authorization check inside it, trusting middleware, a layout or the page that renders the form. Failure: anyone can call the action's endpoint directly, with another user's id. Its input needs the same validation as any route; run the node pass on it too. [`server-auth-actions`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-auth-actions.md)
- **Request data in module state.** A module-level `let`, or a mutable module-level object, written during a server render or a server action (`currentUser = await auth()`). Failure: concurrent requests in one process overwrite each other, and one user's data renders on another user's page. [`server-no-shared-module-state`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-no-shared-module-state.md)
- **Whole records passed to client components.** A server component passing a full database row or API object as a prop to a `'use client'` component. Failure: every field is serialized into the page's HTML and RSC payload, so private fields (a password hash, an email, internal flags) reach the browser, and the page carries kilobytes the client never reads. Pass only the fields it uses. [`server-serialization`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-serialization.md)

## Data fetching and waterfalls

- **Independent awaits in sequence.** `const a = await getA(); const b = await getB();` where `b` does not need `a`, in a server component, route handler, server action or client loader. Failure: the latency is the sum, one extra round trip per await. Start them together with `Promise.all`, and when only some depend on others, start each as soon as its inputs exist [`async-parallel`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-parallel.md) [`async-dependencies`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-dependencies.md). In route handlers and server actions, start independent work first and await it where it is used [`async-api-routes`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-api-routes.md).
- **An await before a branch that does not need it.** An `await` at the top of a function whose early return or other branch never uses the result, or a remote flag awaited before a cheap local condition that already decides the branch. Failure: every call pays the round trip, including the ones that return early. [`async-defer-await`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-defer-await.md) [`async-cheap-condition-before-await`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-cheap-condition-before-await.md)
- **A server component tree that fetches in sequence.** A parent awaits its data before rendering children that fetch their own, or a list awaits each item's nested data in a loop. Failure: the page waits for the chain of round trips, and the slowest item holds up the rest. Fetch in sibling components, or start the fetches together and chain each item's dependent fetch inside its own promise. [`server-parallel-fetching`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-parallel-fetching.md) [`server-parallel-nested-fetching`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-parallel-nested-fetching.md)
- **A page that awaits all its data before showing anything.** An async page or layout that awaits every query at the top, with no `Suspense` boundary. Failure: the first byte waits for the slowest query; name it and its latency. Put the slow part behind `Suspense` so the shell streams first. [`async-suspense-boundaries`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/async-suspense-boundaries.md)
- **The same request made per component.** Several component instances each fetching the same endpoint in an effect on mount. Failure: N identical requests per page load. Share it through the app's data library (SWR, TanStack Query) or lift it up. [`client-swr-dedup`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/client-swr-dedup.md)
- **The same server lookup repeated in one request.** The session, the current user or a config row loaded by several server components in the same render. Failure: one query per component per request. Wrap it in `React.cache()`; for data many requests share, use a bounded cross-request cache. [`server-cache-react`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-cache-react.md) [`server-cache-lru`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-cache-lru.md)
- **Static I/O per request.** A route or server component reading a font, a logo or a static JSON file from disk or the network on every request. Failure: I/O on every request for bytes that never change. Load it once at module level. [`server-hoist-static-io`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-hoist-static-io.md)
- **Logging or analytics awaited before the response.** Failure: every response waits for them. Use `after()` in Next.js, or start them without awaiting and handle their errors. [`server-after-nonblocking`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-after-nonblocking.md)

## Bundle size

- **A heavy component in the initial bundle.** An editor, chart, map or PDF viewer imported statically by a route that shows it only after an interaction or below the fold. Failure: give the kilobytes it adds to that route's first load. Load it with `next/dynamic` or `React.lazy`. [`bundle-dynamic-imports`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-dynamic-imports.md)
- **Code or data for a feature that may never run.** A large module or dataset imported eagerly for a feature behind a flag, a modal or a rarely used branch. Failure: every visitor downloads it. Import it when the feature activates. [`bundle-conditional`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-conditional.md)
- **Barrel imports from a large library.** `import { Check } from 'lucide-react'` (or `@mui/material`, `react-icons`, `lodash`) in a Next.js app whose `next.config` does not list the package in `optimizePackageImports`, or in a build that does not tree-shake that package. Failure: dev boot and cold starts load the whole library's re-exports (the guide measures 200 to 800 ms), and a build that does not tree-shake ships them. Check the config before you claim it. [`bundle-barrel-imports`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-barrel-imports.md)
- **Analytics, logging or error tracking in the critical path.** A third-party SDK imported by the root layout and initialized before hydration. Failure: give the kilobytes and main-thread time it adds before the page is interactive. Load it after hydration. [`bundle-defer-third-party`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-defer-third-party.md)
- **Paths the bundler cannot analyze.** ``import(`./locales/${lang}`)``, `require(name)` or a file path built from a variable. Failure: the bundler includes every file the pattern could match, or output tracing ships a whole directory with the server bundle. [`bundle-analyzable-paths`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-analyzable-paths.md)
- **A render-blocking script.** A `<script src>` in the document head with neither `defer` nor `async`, or `next/script` with a blocking strategy for code that is not critical. Failure: the page does not render until the script downloads and runs. [`rendering-script-defer-async`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-script-defer-async.md)

## Re-renders and rendering

- **Derived data recomputed** on every render over a large list with no `useMemo`: give the size where it hurts. Expensive work above an early return runs even when the component renders nothing; move it into a memoized child [`rerender-memo`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-memo.md). One `useMemo` that does two independent expensive things recomputes both when either input changes [`rerender-split-combined-hooks`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-split-combined-hooks.md).
- **Expensive initial state computed every render.** `useState(parse(bigString))` runs the computation on every render though only the first result is kept. Pass a function: `useState(() => parse(bigString))`. [`rerender-lazy-state-init`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-lazy-state-init.md)
- **`memo` defeated by a default prop.** A memoized component with a default `[]`, `{}` or function parameter: every call without the prop passes a new value, so `memo` never skips. Hoist the default to a constant. [`rerender-memo-with-default-value`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-memo-with-default-value.md)
- **Subscribing to more than the render uses.** Reading `useSearchParams()` or a store value only inside a callback, or subscribing to a continuous value (scroll position, window width) when the render needs one boolean. Failure: the component re-renders on every change; give the rate (per scroll event, per resize frame). Read it in the callback, or subscribe to the derived boolean. [`rerender-defer-reads`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-defer-reads.md) [`rerender-derived-state`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-derived-state.md)
- **State for values that change on every event.** `setPosition` on every `mousemove`, `scroll` or animation frame for a value the render does not need each time. Failure: a render per event. Keep it in a ref. [`rerender-use-ref-transient-values`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-use-ref-transient-values.md)
- **Input that waits for an expensive render.** A keystroke that synchronously filters or renders a large list. Failure: give the list size and the lag per keystroke. Mark the update as a transition, or render the list from `useDeferredValue`. [`rerender-transitions`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-transitions.md) [`rerender-use-deferred-value`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-use-deferred-value.md)
- **A long list rendered whole.** Thousands of rows rendered at once with no virtualization and no `content-visibility: auto`. Failure: give the row count and the render or layout time. [`rendering-content-visibility`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-content-visibility.md)
- **Scroll held by a listener.** A `touchstart`, `touchmove` or `wheel` listener on an element, not marked `{ passive: true }`, that never calls `preventDefault()`. Failure: the browser waits for the handler before it scrolls, so scrolling lags on touch devices. [`client-passive-event-listeners`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/client-passive-event-listeners.md)
- **Layout thrashing.** A loop that writes a style and then reads a layout value (`offsetWidth`, `getBoundingClientRect()`) for each element. Failure: a forced reflow per element; give the count. Read all, then write all, or toggle a class. [`js-batch-dom-css`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-batch-dom-css.md)
- **Synchronous storage in a hot path.** `localStorage`, `sessionStorage` or `document.cookie` read in render for every item of a list, or on every event. Failure: synchronous storage access per read. Read once and keep it in memory. [`js-cache-storage`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-cache-storage.md)
- **Quadratic lookups.** `.find()`, `.includes()` or `.indexOf()` inside a loop over another large array. Failure: give n × m at the expected sizes. Build a `Map` or `Set` once. [`js-set-map-lookups`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-set-map-lookups.md) [`js-index-maps`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-index-maps.md)

## Rendering untrusted data

- `dangerouslySetInnerHTML` with anything a user or an API controls, without a sanitizer: stored XSS.
- `href={url}` or `src={url}` from user data: `javascript:` URLs run script. Allow `http:`/`https:` (and what the app needs) only.
- Spreading untrusted objects into props (`<a {...userProps}>`) can set event handlers or `dangerouslySetInnerHTML`.

## Errors and loading

- A component that throws during render with no error boundary above it unmounts the whole tree: name the data that makes it throw.
- A `Suspense` boundary missing above a component that suspends, or a loading state that never ends because an error path never sets it back.
- A form that submits twice on double click or Enter because nothing disables it while the request is in flight.

## Accessibility that breaks use

Only what stops someone from using the feature. Leave the rest to a full
accessibility review.

- A clickable `div` with no role, keyboard handler or focus.
- An icon-only button with no accessible name.
- An input with no label.
- Focus lost after a modal closes.

## Not findings

These rules from the guide are sound advice but cannot carry a finding on
their own: they are micro-optimizations, styling choices, or improvements to
propose rather than defects in a change. Never report them as such. When one
causes a real, measurable cost in a hot path, that cost is the finding, under
the check above it falls under (quadratic lookups, layout thrashing, input
that waits for a render).

- Micro-optimizations of plain JavaScript: [`js-cache-function-results`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-cache-function-results.md), [`js-cache-property-access`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-cache-property-access.md), [`js-combine-iterations`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-combine-iterations.md), [`js-early-exit`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-early-exit.md), [`js-flatmap-filter`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-flatmap-filter.md), [`js-hoist-regexp`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-hoist-regexp.md), [`js-length-check-first`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-length-check-first.md), [`js-min-max-loop`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-min-max-loop.md), [`js-request-idle-callback`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/js-request-idle-callback.md).
- Memoization and JSX-hoisting choices: [`rerender-simple-expression-in-memo`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rerender-simple-expression-in-memo.md), [`rendering-hoist-jsx`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-hoist-jsx.md).
- Rendering polish and newer APIs to prefer: [`rendering-svg-precision`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-svg-precision.md), [`rendering-animate-svg-wrapper`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-animate-svg-wrapper.md), [`rendering-activity`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-activity.md), [`rendering-usetransition-loading`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-usetransition-loading.md).
- Improvements to propose, not defects: preloading on intent and resource hints ([`bundle-preload`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/bundle-preload.md), [`rendering-resource-hints`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/rendering-resource-hints.md)), sharing global listeners through SWR ([`client-event-listeners`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/client-event-listeners.md)), avoiding duplicate serialization in RSC props ([`server-dedup-props`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/server-dedup-props.md)).
- Stable-callback patterns, which the hooks checks above already cover when a stale closure or a re-subscription actually breaks something: [`advanced-event-handler-refs`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/advanced-event-handler-refs.md), [`advanced-use-latest`](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/rules/advanced-use-latest.md).
