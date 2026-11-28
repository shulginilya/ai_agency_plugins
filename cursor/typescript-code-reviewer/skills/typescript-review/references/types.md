# Types pass

Load this for every TypeScript review. The question is never "are the types
pretty" but "where does the type say one thing while the value at run time is
another". tsc is green on all of these, and that is why they reach production.

Check the strictness `ts_scope.py` printed first. With `strictNullChecks` off,
every `T` is really `T | null | undefined`; with `noUncheckedIndexedAccess`
off, `arr[i]` is typed as present when the array is empty. Read those paths
yourself, because tsc will not.

The failure checks are this plugin's own. The modelling checks (impossible
states, brands, schemas, `satisfies`, mocks) come from
[TypeScript best practices](https://github.com/cursor/plugins/tree/main/pstack/skills/typescript-best-practices)
in Cursor's `pstack` plugin, by Lauren Tan, licensed MIT: its 16 rules,
written here in our own words as review checks. A check from the guide cites
its rule; follow the link for the guide's examples.

## How a practice becomes a finding

A practice is a lead, not a rule. It is a finding only with a **failure
scenario**: the value, input or state that makes this code misbehave, and the
crash, wrong result or exposure that follows.

- **A design preference is never a finding.** Discriminated unions, brands,
  constructive types, object arguments and the order of narrowing are ways to
  make a bug impossible to write. Ask whether this diff contains the bug, and
  report the bug; say what the better shape would have prevented.
- **The repository decides the fix.** Use the repository's own schema library
  and existing schemas (zod, valibot, io-ts, a generated client), match the
  brand and discriminant conventions it already has, and never ask for a new
  dependency to replace one guard.
- **The version decides what is available.** `satisfies` needs TypeScript 4.9,
  and some lib methods need a newer target: read `typescript` and the tsconfig
  `target` and `lib` in `package.json` before you suggest one.
- **Do not ask for validation twice.** Validate once where data crosses in
  and trust the type inside; a missing check deep in a call chain is a finding
  only when the data did not come through a boundary that validated it.

Severity is the review's scale (`SKILL.md`, section 5): **blocker** for a
crash or blank screen on a normal path, data loss or a security exposure;
**major** for wrong behaviour on a plausible path or a broken contract;
**minor** for a real defect on an unlikely path. Put the rule in the
finding's `why`: `Why: the brand is forged by a cast (TypeScript best
practices: branded-types)`.

## Types that lie

- **Unvalidated boundaries.** `await res.json() as User`, `JSON.parse(s) as
  Config`, `req.body as CreateOrder`, `localStorage.getItem(k)` parsed and
  cast, a message from `postMessage` or a WebSocket. The cast adds no check:
  the first malformed payload flows through typed as valid. The fix is a
  runtime parse (zod, valibot, a type guard that checks every field) at the
  boundary, not deeper in, into a named domain type; `Record<string, unknown>`
  passed down the call chain means the boundary was never drawn. Stored data
  read back is a boundary too: a `JSON.parse` of a saved value with no
  try/catch throws on a corrupt or truncated one, and a value saved by an
  older release has the old shape, so a deploy that renames a field breaks
  every returning user's page. Version the stored blob and parse it
  defensively. [`boundary-validation`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#boundary-validation)
- **A guard or interface written next to a schema.** A property-by-property
  type guard, or an `interface` repeated beside a zod or valibot schema for
  the same data. Failure: they drift. The interface gains `email: string` that
  the schema and the guard never check, so `user.email.toLowerCase()` throws on
  parsed data that passed. The type should come from the schema (`z.infer`),
  or the schema should be annotated with the type (`z.ZodType<User>`) so the
  compiler rejects one that proves less. Where the repository has no schema
  library, a hand-written guard is fine if it checks every field; do not ask
  for a new dependency. [`schemas-before-guards`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#schemas-before-hand-rolled-guards)
- **`as` casts and `as unknown as`.** Each one asserts something tsc could not
  prove. Find what it asserts and whether it can be false: a cast to a
  narrower union member, a cast that drops `null`, a cast that hides a missing
  property. When you ask for the cast to go, say why tsc could not infer it: a
  missing discriminant, a source type that is too wide, or an unvalidated
  boundary; only then is a brand or `satisfies` the answer. [`no-as-casts`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#no-as-casts)
- **An object literal asserted into its type.** `const config = { theme:
  'dark' } as Config` compiles when `Config` also has a required `cols`, and
  `config.cols` is `undefined` at run time. `satisfies Config` (TypeScript 4.9
  or later: check the version) checks the literal against the type and keeps
  its literal types. [`satisfies-over-as`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#satisfies-over-as)
- **Non-null `!`.** `map.get(id)!`, `document.getElementById('x')!`,
  `user!.email`. Name the state in which the value is null (an unknown id, a
  render before mount, a logged-out user) and what throws. The same lie hides
  in `sessions.at(0)!`, `items[0] as Item` and a "should never happen" throw
  after a branch the types do not rule out: the empty list a filter or an API
  can return. Strengthen the input where the loose type forces the lie (a
  non-empty tuple, `[T, ...T[]]`), or return `T | undefined`; keep `T[]` when
  every operation on it is total (the sum of `[]` is 0) and do not ask for a
  non-empty type there. [`simplest-total-type`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#simplest-total-type)
- **`any` leaking.** An `any` from a parameter, a `catch (e)`, an untyped
  library or `JSON.parse` turns off checking for everything it touches:
  `const total = data.items.reduce(...)` is unchecked when `data` is any.
  Follow it until it is narrowed or reaches a typed sink. External data (a
  `JSON.parse` result, an RPC or `postMessage` payload, file contents,
  `process.env`, a database row) should arrive as `unknown` and be narrowed
  before use. [`unknown-over-any`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#unknown-over-any)
- **Type guards that lie.** `function isUser(x): x is User { return
  'id' in x }` vouches for every field of `User` after checking one. A wrong
  guard is worse than a cast because callers trust it. A guard must verify
  everything it claims. [`type-guards`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#type-guards)
- **`@ts-ignore` / `@ts-expect-error`.** Read the error it hides (remove it
  locally and run tsc). If the error is real, the line is a defect.
- **Declaration files.** A `.d.ts` or `declare module` that describes a
  JavaScript module or global differently from what it does at run time.

## Impossible states and invariants

- **Optional-field bags.** `{ loading: boolean; data?: T; error?: string }`
  lets `loading: false` with neither, or `data` and `error` together. Name the
  combination the code reaches (a failed refetch keeps the old `data` and sets
  `error`) and what the consumer does with it: `state.data!.items` throws, or
  stale data shows under an error banner. Model the variants as a union with
  one literal discriminant (`kind`), so only the valid states can be written.
  [`discriminated-unions`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#discriminated-unions)
- **A brand that nothing verified.** A brand (`string & { readonly __brand:
  'AgentId' }`) claims a check ran. `return input as AgentId`, or a guard
  `input is AgentId` that tests nothing, makes the claim without the check.
  Failure: an unvalidated string from the URL reaches code that trusts it as
  an id. A brand comes from a guard that verifies, at the boundary. Where two
  parameters of one primitive type can be swapped (`transfer(fromId, toId)`)
  and the diff has a call that swaps them, that call is the finding, and a
  brand is the fix. [`branded-types`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#branded-types)
- **An invariant held by a comment or a repeated check.** `{ start: Date; end:
  Date } // start <= end`, or a `T[]` whose callers each repeat `if (xs.length
  === 0) throw`. Failure: a caller or an API response builds `end` before
  `start`, and a negative duration flows on. Report it when the diff has a
  path that builds the bad value; the fix is a shape that cannot hold it
  (`start` plus `durationMs`, a non-empty tuple). [`constructive-modeling`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#constructive-modeling)
- **A hand-written copy of a generated type.** The same shape declared again
  beside what a `.proto`, an OpenAPI document, a GraphQL schema or a generated
  module already exports. Failure: the schema renames or adds a field, the copy
  still compiles against the fetched data, and the code reads the old property
  as `undefined`. Derive it (`Pick`, `Omit`, `Parameters`, `ReturnType`,
  `Awaited`, `typeof`). Report a copy that has drifted, or one the diff
  copies; a type that merely could be derived is not a finding.
  [`schema-derived-types`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#schema-derived-types)

## Unions and exhaustiveness

- A `switch` or `if` chain over a union with no `never` check in the default:
  a member added later falls through silently. Find who adds members (an API
  enum, a status column) and what the fallthrough does. The idiom is a default
  arm that assigns the value to a `never` local (`const _exhaustive: never =
  x`), so the compiler fails the build when a member is added. Without it a
  statement `switch` quietly does nothing for the new member, and a
  value-returning one returns `undefined` where its return type is inferred or
  includes `undefined`. [`exhaustiveness`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#exhaustiveness)
- A discriminated union narrowed on the wrong field, or a check like
  `if (result.error)` where `error` may be an empty string.
- `string` where the domain is a closed set, so a typo compiles:
  `status === 'canceled'` against a backend that sends `'cancelled'`.

## Objects, optionals and records

- `Partial<T>` passed where `T` is expected after a spread that may not fill
  every field.
- Optional vs undefined: `{ ...defaults, ...overrides }` where an override
  holds an explicit `undefined` wipes the default (unless
  `exactOptionalPropertyTypes` is on).
- `Record<string, T>` and index signatures: `record[key]` is `T`, never
  `undefined`, unless `noUncheckedIndexedAccess` is on.
- `Object.keys(obj)` is `string[]`; `Object.entries` loses the key type; a
  cast back to `keyof T` is a lie when the object has extra keys at run time
  (structural typing allows them).
- `Array.prototype.find`, `.at()`, `.pop()` return `T | undefined`; a `!` or a
  cast right after one is a finding candidate.

## Enums, modules and emit

- Numeric `enum`s accept any number; `const enum` breaks under
  `isolatedModules` (Vite, esbuild, SWC, Babel) when imported across files.
- A type-only import or re-export without `import type` / `export type` under
  `isolatedModules` or `verbatimModuleSyntax`: the build fails, or the import
  survives to run time and the module is not found.
- ESM vs CommonJS: under `module: NodeNext` a relative import needs its `.js`
  extension at run time; `__dirname` and `require` do not exist in ESM;
  a default import of a CommonJS module without `esModuleInterop` is
  `undefined` at run time.
- Path aliases (`@/x`) that tsc resolves but the runtime or bundler does not
  (no matching `paths` in Vite, Jest `moduleNameMapper` or the Node loader).

## Mocks and tests that prove nothing

- **Stubs standing in for what the test claims to exercise.** A test of
  `orderService` whose repository and collaborators are hand-written stubs
  cast `as unknown as Repo`, where the real ones run locally (an in-memory
  database, the framework's test utilities). Failure: the stub keeps passing
  after the real module changes shape or behaviour, so the assertion proves the
  stub, and the cast is why tsc says nothing. Mock what cannot run locally (a
  third-party API, the clock); run the rest. [`real-tests`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/SKILL.md)

## Changed exported types

A changed exported type, interface or function signature is a contract
change. `grep` for every importer, including the other side of the wire: a
type shared between a React client and a Node.js server changes both. A
widened return type (`T` to `T | null`) breaks every caller that does not
handle the new member; a narrowed parameter type breaks every caller that
passes the old one.

## Not findings

These rules from the guide are sound advice but cannot carry a finding on
their own. When one causes a real failure, the failure is the finding, under
the check it falls under above.

- The order of narrowing: a discriminant switch, then `in`, then `typeof` or
  `instanceof`, then a guard, then `as` last ([`narrowing-hierarchy`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#narrowing-hierarchy)). The
  order is taste; a bare `as` at the end of it is the cast check.
- Object arguments instead of positional ones ([`object-args`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/references/patterns.md#object-args)). A signature
  that stays positional is not a finding, and the guide itself skips hot
  paths. A call that passes two same-typed arguments in the wrong order is a
  correctness finding on its own.
- Structured logging over `console.log` ([`structured-telemetry`](https://github.com/cursor/plugins/blob/main/pstack/skills/typescript-best-practices/SKILL.md)). A
  `console.log` is not a finding. A log line that writes a secret is a
  finding of the node pass, and a `catch` that only logs and then reports
  success is one of the correctness pass.
- Names: `kind` or `type` as the discriminant, `isX` for guards, `type` or
  `interface`, a non-empty type spelled inline or as an alias.

## Reporting

Name the run-time value that contradicts the type and the line that then
misbehaves: "`/api/user` returns `{ user: null }` for a deleted account; the
`as User` cast at `api.ts:31` lets `user.name.toUpperCase()` at
`Profile.tsx:18` throw `TypeError` and blank the page."
