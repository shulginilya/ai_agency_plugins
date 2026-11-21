# Types pass

Load this for every TypeScript review. The question is never "are the types
pretty" but "where does the type say one thing while the value at run time is
another". tsc is green on all of these, and that is why they reach production.

Check the strictness `ts_scope.py` printed first. With `strictNullChecks` off,
every `T` is really `T | null | undefined`; with `noUncheckedIndexedAccess`
off, `arr[i]` is typed as present when the array is empty. Read those paths
yourself, because tsc will not.

## Types that lie

- **Unvalidated boundaries.** `await res.json() as User`, `JSON.parse(s) as
  Config`, `req.body as CreateOrder`, `localStorage.getItem(k)` parsed and
  cast, a message from `postMessage` or a WebSocket. The cast adds no check:
  the first malformed payload flows through typed as valid. The fix is a
  runtime parse (zod, valibot, a type guard that checks every field) at the
  boundary, not deeper in.
- **`as` casts and `as unknown as`.** Each one asserts something tsc could not
  prove. Find what it asserts and whether it can be false: a cast to a
  narrower union member, a cast that drops `null`, a cast that hides a missing
  property.
- **Non-null `!`.** `map.get(id)!`, `document.getElementById('x')!`,
  `user!.email`. Name the state in which the value is null (an unknown id, a
  render before mount, a logged-out user) and what throws.
- **`any` leaking.** An `any` from a parameter, a `catch (e)`, an untyped
  library or `JSON.parse` turns off checking for everything it touches:
  `const total = data.items.reduce(...)` is unchecked when `data` is any.
  Follow it until it is narrowed or reaches a typed sink.
- **Type guards that lie.** `function isUser(x): x is User { return
  'id' in x }` vouches for every field of `User` after checking one. A wrong
  guard is worse than a cast because callers trust it.
- **`@ts-ignore` / `@ts-expect-error`.** Read the error it hides (remove it
  locally and run tsc). If the error is real, the line is a defect.
- **Declaration files.** A `.d.ts` or `declare module` that describes a
  JavaScript module or global differently from what it does at run time.

## Unions and exhaustiveness

- A `switch` or `if` chain over a union with no `never` check in the default:
  a member added later falls through silently. Find who adds members (an API
  enum, a status column) and what the fallthrough does.
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

## Changed exported types

A changed exported type, interface or function signature is a contract
change. `grep` for every importer, including the other side of the wire: a
type shared between a React client and a Node.js server changes both. A
widened return type (`T` to `T | null`) breaks every caller that does not
handle the new member; a narrowed parameter type breaks every caller that
passes the old one.

## Reporting

Name the run-time value that contradicts the type and the line that then
misbehaves: "`/api/user` returns `{ user: null }` for a deleted account; the
`as User` cast at `api.ts:31` lets `user.name.toUpperCase()` at
`Profile.tsx:18` throw `TypeError` and blank the page."
