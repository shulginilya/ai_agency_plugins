# typescript-code-reviewer

The TypeScript Code Reviewer. It reviews TypeScript code written for React
and Node.js, the way a senior TypeScript engineer reads a change: tsc is
already green, so it looks for where the types and the run-time values part
ways, and for the React and Node.js defects no compiler checks. Every finding
carries a concrete failure scenario, and the verdict follows fixed rules.

It is a Captain plugin, not a crew role: the crew's `code-reviewer` stays the
reviewer in the ticket flow. It never edits code, pushes, files tickets or
moves board cards. Installing dependencies and running a repo's checks run
the change's code, so for a pull request from a fork or from another author
it asks first.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Agent | `typescript-reviewer` | The TypeScript Code Reviewer: one pass (types, correctness, tests, react or node) in a fresh context, returning only findings that carry a failure scenario |
| Skill | `typescript-review` | Scope the change, run the repo's checks, read whole files and the users of changed contracts, run the passes, record findings, give the verdict |
| Command | `/typescript-code-reviewer:review` | Review the current branch, a base ref or a PR; `--post` posts the report on the PR |

**The passes.** Types, correctness and tests always; react when a React file
changed; node when a Node.js file changed. Each has a checklist in
`skills/typescript-review/references/`:

- `types.md`: unvalidated boundaries (`res.json() as T`), casts, `!`, `any`
  leaks, lying type guards, exhaustiveness, optionals and records, enums,
  `isolatedModules`, ESM/CJS, changed exported types.
- `react.md`: rules of hooks, effect dependencies and cleanup, async races,
  state mutation, keys, hydration mismatches, server code in the client
  bundle, XSS through `dangerouslySetInnerHTML` and `href`.
- `node.md`: floating promises, Express 4 async handlers, timeouts, the event
  loop, input typed but not validated, injection, path traversal, SSRF, auth
  gaps, resource cleanup.
- `node-best-practices.md`: the Node.js Best Practices guide
  ([goldbergyoni/nodebestpractices](https://github.com/goldbergyoni/nodebestpractices),
  Yoni Goldberg and contributors, CC BY-SA 4.0) as review checks, each citing
  its practice and naming the failure to look for, with the practices a diff
  can't show listed as never findings. The node pass applies it after
  `node.md`, and the tests pass applies its Testing section to tests of node
  files. Asked only whether Node.js code or a Node app's `Dockerfile` follows
  Node.js best practices, the review applies `node.md` and this list without
  scoping a change.

**Verdicts.** **approve** when there is no blocker and no major finding;
**request changes** otherwise. A red typecheck, lint or test run is a
blocker. Nits never change the verdict.

Two scripts, both standard-library Python:

- `skills/typescript-review/scripts/ts_scope.py` compares the working tree
  with the merge base of a ref (default: the remote's default branch) and
  prints the changed TypeScript, JavaScript and config files with their tags
  (react, node, test, declaration, config, symlink — a symlink is never read
  through, only its target printed), the passes to run, each package's
  package manager, install, typecheck, lint and test commands, each
  tsconfig's effective strictness (following `extends`, and TypeScript 6's
  strict default) with what tsc will not catch under it, and the escape
  hatches the diff adds (`any`, `as unknown as`, `!`, `@ts-ignore`, ...).
- `skills/typescript-review/scripts/review_report.py` turns recorded
  findings into the verdict and the report. It refuses a finding that isn't a
  nit and has no failure scenario, a failed check with no blocker, and a
  review whose passes leave out types, correctness or tests. It exits 0 on
  approve and 1 on request changes.

## Try it

```bash
python plugins/typescript-code-reviewer/skills/typescript-review/scripts/ts_scope.py --base origin/main
python plugins/typescript-code-reviewer/skills/typescript-review/scripts/review_report.py findings.json --commit abc1234
python -m tools.apkit test --plugin typescript-code-reviewer
```

In Claude Code:

```
/typescript-code-reviewer:review              # the current branch against the default branch
/typescript-code-reviewer:review origin/dev   # against another base
/typescript-code-reviewer:review 43 --post    # a PR, posting the report on it
```

## Install it

```bash
python -m tools.apkit build --plugin typescript-code-reviewer
python -m tools.apkit install typescript-code-reviewer --target claude-code
```

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes the skill, the command and the `typescript-reviewer` agent.
- **Codex CLI, Cursor, Gemini CLI** take the skill and the command.
  `typescript-reviewer` becomes a skill, so the passes survive but the fresh
  context doesn't. Run each pass in a new session.
- **Generic `.agents/skills`** takes the skills only. The skill carries its
  own scripts.
