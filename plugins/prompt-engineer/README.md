# prompt-engineer

Text in, tailored prompt out. Give it a task description, rough notes, a
pasted example or a prompt that is not working, and it hands back a prompt
built for that task, the model that will run it, and the place the prompt
will live: a chat message, a system prompt, a pipeline template, an agent
file or an image-model prompt.

The plugin replaces the usual approach, which is to wrap the request in a
generic template and add "You are an expert". It works out the brief
first, asks only for what the prompt cannot work without, states every other
assumption where the user can see it, and then checks the result twice: once
with a linter and once in a fresh context that has never seen the conversation.

## What it does

| Component | Name | Purpose |
| --- | --- | --- |
| Skill | `prompt-crafting` | The method: read the brief, ask the few critical questions, pick the pattern, tailor to the target, lint, test cold |
| Command | `/prompt` | Build a prompt from some text |
| Command | `/prompt-review` | Diagnose an underperforming prompt and change only what its defects need |
| Command | `/prompt-test` | Run a prompt cold against a sample input and list every guess it forced |
| Agent | `prompt-tester` | Runs the prompt in a context that only has the prompt, and reports READY / GAPS / BROKEN |
| Hook | `PostToolUse` | Lints `*.prompt.md`, `*.prompt.txt`, `*.prompt` and files under `prompts/` as they are written |
| MCP | `prompt-engineer` | Dependency-free stdio server: `prompt_brief`, `prompt_lint`, `prompt_guide` |

The skill carries the method. The two references load only when the work
reaches them: `prompt-patterns.md` has one pattern per task type (writing,
code, summarization, extraction, classification, analysis, agent, image,
research, brainstorm), and `target-tailoring.md` covers where the prompt goes
and which model runs it.

## The scripts

```bash
# what kind of prompt is this, what does the text already say, what must be asked?
python skills/prompt-crafting/scripts/brief.py --text "write a cold email to CTOs about our API"

# lint a draft: exits 1 on errors, 0 when only warnings remain
python skills/prompt-crafting/scripts/prompt_lint.py welcome.prompt.md
```

`brief.py` is a checklist that cannot forget an item, not a classifier. Every
brief slot it reports as present quotes the words that triggered it, so a wrong call is visible.
What counts as critical depends on the task type. An extraction prompt must
have a schema, a writing prompt must have a reader, and a classification
prompt must have labelled examples. Missing critical slots become questions,
at most three. Everything else becomes a stated assumption.

`prompt_lint.py` reports errors for unfilled placeholders, unclosed section
tags and a prompt that ends by pointing at material that is not attached.
It warns about a missing output shape, vague wording, shouted emphasis,
negative-only rules, contradictory length and a single example. Fenced and
inline code are treated as data, and so is `<placeholder>` notation
mid-sentence. The rules are tuned so the agent files already in this repo
lint clean: a linter that fires on good prompts gets ignored.

## One home for a rule

The lint rules live in `skills/prompt-crafting/scripts/prompt_lint.py`, and
the brief slots live in `brief.py` next to it. The hook and the MCP server
import them and do not restate them. So there is one place to correct a noisy
rule, and the server never contradicts the skill.

## Try it

```bash
python plugins/prompt-engineer/skills/prompt-crafting/scripts/brief.py \
  --text "make a system prompt for our support bot"

echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python plugins/prompt-engineer/mcp/server.py

python -m tools.apkit test --plugin prompt-engineer
```

## Install it

```bash
python -m tools.apkit build --plugin prompt-engineer
python -m tools.apkit install prompt-engineer --target claude-code --scope user
```

## What degrades where

- **Claude Code** takes everything.
- **OpenCode** takes skills, commands and agents, but no hooks.
- **Codex CLI, Cursor, Gemini CLI** take skills and commands. The
  `prompt-tester` agent is emitted as a skill, so the test still runs, but in
  the same context. `/prompt-test` says so when that happens, because a
  same-context test is weaker. There are no hooks.
- **Generic `.agents/skills`** takes skills only. The skill carries its own
  `scripts/`, so `brief.py` and `prompt_lint.py` travel with it.
