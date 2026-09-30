# Tailoring to the target

The same task needs a different prompt depending on what runs it and where the
text goes. Settle both before writing. When the user does not say, assume a
current frontier chat model and a single user message, and state that
assumption under the prompt.

## Where the prompt goes

| Placement | What changes |
| --- | --- |
| **One-off message** a person pastes into a chat | Material can be pasted inline, inside delimiters. No variables. Can end with "ask me if anything is unclear" when a follow-up is possible. |
| **System prompt** for an assistant or custom GPT | Written for many conversations, not one. Describes the users, the scope, the boundaries and the voice. No specific task content. Must say what to do when a request falls outside scope. |
| **Template in a pipeline** (API call, batch job) | Nobody reads the output before code does. Named variables (`{{document}}`), an exact output schema, a defined output for bad input, and nothing that invites a question back — there is nobody to answer it. |
| **Agent / skill / command file** (Claude Code, Codex, Cursor rules) | Read by an agent that has tools and a repository. Say what to inspect and run, not just what to think. Put the trigger in the description. Keep it short; long detail goes in files the agent loads on demand. |
| **Image-model prompt** | Not an instruction at all — a description of the picture. See below. |

## Which model runs it

**Frontier chat models (current Claude, GPT, Gemini).** They follow
instructions literally and precisely, so say exactly what you want, including
"go beyond the basics" if you want that. Give context and the reason behind a
rule rather than repeated emphasis — capitals and "CRITICAL" cause
over-application. XML-style tags (`<document>`, `<examples>`) are a reliable
way to separate material from instructions for all of them. Ask for reasoning
before the answer only when the task needs it and the output format allows it;
many of these models reason internally when extended thinking is on.

**Small, local or older models (Haiku-class, 7–70B open models).** Tighter
everything: a short instruction, a rigid output format, two or three worked
examples that show the exact shape, and one task per prompt. Put the most
important instruction last as well as first — small models lose the middle.

**Reasoning models / extended thinking on.** Give the goal, the constraints
and the bar; drop the step-by-step method unless the method itself is a
requirement. Prescribing each step tends to do worse than letting the model
plan.

**Coding agents (Claude Code, Codex, Cursor, Copilot agent).** They act, so
the prompt names files, commands and a verification: "run `npm test -- cart`
and stop when it passes". Say what not to touch. Say whether to ask before
large changes.

**Image models.**

- *Midjourney*: comma-separated descriptors, subject first; parameters at the
  end (`--ar 16:9 --style raw --v <version>`); `--no <thing>` for exclusions.
- *DALL·E / GPT image*: a full descriptive sentence or two works; state any
  text that must appear, in quotes, exactly.
- *Stable Diffusion / Flux*: descriptors weighted by order; a separate
  negative-prompt field for exclusions — do not write "no X" in the positive
  prompt, it tends to add X.

Across all of them: describe the picture, not the intent ("a logo" says
nothing; "a flat single-colour mark of a wheat stalk inside a circle" says
what to draw).

## Language and locale

Write the prompt in the language the output must be in, unless the model is
known to follow instructions better in English and the output language is
stated explicitly ("Answer in German"). Name the locale for dates, currency
and spelling when it matters.

## Length budget

A prompt is part of the context window it competes with. For a pipeline
template run thousands of times, every sentence costs money; cut anything that
does not change the output. For a system prompt, stay well under a couple of
thousand words — the lint warns past 4,000 — and move reference material
(policies, catalogues) into retrieved documents rather than the instructions.
