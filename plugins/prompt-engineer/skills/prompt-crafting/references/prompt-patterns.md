# Prompt patterns by task type

One pattern per task type `brief.py` reports. Each gives the parts that carry
the weight for that task, the defect prompts of that type most often have, and
a skeleton. Skeletons are starting points: delete any part the task does not
need, and replace every `<…>` with the user's own specifics — a skeleton with
angle brackets left in fails the lint.

---

## writing

**Carries the weight:** audience, purpose (what the reader should do or feel
after), length as a number, voice. A sample of the voice beats any adjective.

**Usual defect:** no reader. "Write a blog post about X" yields a post for
nobody in particular.

```
<Who the reader is, what they already know, and what they should do after reading.>

Write a <piece> about <topic> for that reader.

Voice: <two or three concrete traits>. Match this sample:
<sample>
<a paragraph the user actually wrote>
</sample>

Requirements:
- <the point that must land, and why it matters to this reader>
- <anything that must not be claimed, and why>

Output: <length in words>, <structure — e.g. subject line + 3 short paragraphs>, no preamble.
```

## code

**Carries the weight:** language and versions, the existing code or interface
it must fit, what "done" means (tests pass, signature unchanged), what not to
touch.

**Usual defect:** no definition of done, so the model stops at "looks right".

```
<Repository / stack context: language, framework, versions, conventions to match.>

Task: <the change, in one or two sentences>.

<code or files it must fit, in fenced blocks>

Constraints:
- Keep <public interface / signature> unchanged because <callers>.
- Match the existing style: <specific convention>.

Done when: <tests that must pass, or behaviour that must be observable>.

Output: <a unified diff | the full file | the function only>, then one line per non-obvious decision.
```

## summarization

**Carries the weight:** who reads the summary and what they will use it for;
length as a number; what to keep verbatim (numbers, names, decisions, dates).

**Usual defect:** "summarise this" with no reader, which yields a neutral
précis nobody needed.

```
Summarise the <document type> below for <reader>, who will use it to <decision / action>.

<document>
{{document}}
</document>

Keep: decisions, owners, dates, numbers — exactly as written.
Drop: <what this reader does not need>.
If the document does not say something, do not infer it.

Output: <N> bullets, most important first, each under <M> words. Then "Open questions:" if any.
```

## extraction

**Carries the weight:** the exact schema with types; what to do when a field is
missing, ambiguous or repeated; that output is parsed, so nothing else is
emitted.

**Usual defect:** no rule for missing fields, so the model estimates them.

```
Extract the fields below from the <document type>. The output is parsed by code.

<document>
{{document}}
</document>

Schema:
{
  "<field>": <type>,        // <meaning, units, format e.g. ISO 8601>
  "<field>": <type> | null  // null when the document does not state it
}

Rules:
- Copy values as written; do not normalise <x> unless stated.
- A field not present in the document is null. Never estimate.
- <how to handle multiples: first / all as an array / the one marked "total">

Output only the JSON object, no code fence, no commentary.
```

## classification

**Carries the weight:** the label set with a one-line definition each; the
tie-breaker between the two labels that get confused; two or three examples
per hard boundary; a label for "none of these".

**Usual defect:** labels with no definitions, so the boundaries are the
model's guess and drift between runs.

```
Classify the <item> into exactly one label.

Labels:
- <label>: <definition>. Example: "<real item>"
- <label>: <definition>. Example: "<real item>"
- other: none of the above clearly applies.

When <label A> and <label B> both seem to fit, choose <A> if <deciding test>.

<item>
{{item}}
</item>

Output: <label>|<one-sentence reason quoting the item>
```

## analysis

**Carries the weight:** the decision the analysis feeds; the criteria and
their weights; what counts as evidence; a required verdict.

**Usual defect:** no decision, so the output is a balanced essay with no
conclusion.

```
<Context: what is being decided, by whom, and by when.>

Analyse <material> against these criteria, most important first:
1. <criterion> — <why it matters here>
2. <criterion>

Cite the part of the material behind each point. Where the material does not
support a judgement, say so rather than filling the gap.

Output: a table <option × criterion>, then "Recommendation:" with one choice and
the single strongest reason, then "Would change my mind:" — what evidence would.
```

## agent

A system prompt for an assistant, bot or custom GPT that talks to someone else.

**Carries the weight:** who the users are and what they come for; what the
assistant can actually do (tools, knowledge, handoff); the boundaries and what
to say at them; the voice; what to do when unsure.

**Usual defect:** a personality and a list of "never"s, with nothing about
what to do when a request falls outside scope.

```
You are <name>, the <role> for <company / product>. <Users> come to you to
<top two or three jobs>.

What you know and can do:
- <knowledge source / tools, and their limits>

How you work:
- <the behaviour that makes this assistant good, with the reason>
- When you do not know, <say so and do X> — do not guess at <policies / prices / dates>.

Boundaries:
- <Out-of-scope request>: <what to say and where to send them>.
- <Sensitive case>: <handoff rule>.

Voice: <traits>, <length norm — e.g. two to four sentences unless asked for more>.
```

## image

**Carries the weight:** subject, composition, style, lighting, palette, aspect
ratio — as concrete nouns and adjectives, front-loaded. Image models weigh
early tokens most and do not follow instructions or negations the way chat
models do.

**Usual defect:** a sentence of intent ("a nice logo for my bakery") instead of
a description of the picture.

```
<subject, with specific attributes>, <action / pose>, <setting>,
<composition: close-up | wide shot | centred, negative space left>,
<style: e.g. flat vector illustration | 35mm photograph | watercolour>,
<lighting>, <palette: 2–4 named colours>, <mood>
Aspect ratio: <16:9 | 1:1 | 4:5>
Exclude: <text, watermarks, extra fingers>     (only where the tool has a negative-prompt field)
```

Tool syntax differs (Midjourney parameters, negative-prompt fields); see
`target-tailoring.md`.

## research

**Carries the weight:** the question, sharply; the sources that count and the
ones that do not; recency; the standard of evidence; what to do when sources
disagree.

**Usual defect:** a topic instead of a question, so the output is a survey.

```
Question: <one answerable question>.
It matters because <decision it feeds>.

Use <source types>; not <source types>. Prefer material from <date> onward.
Every claim gets a citation to a source you actually read. Where sources
conflict, show both and say which is stronger and why.

Output: "Answer:" in two sentences, then the evidence as bullets with citations,
then "Confidence:" high | medium | low and what would raise it.
```

## brainstorm

**Carries the weight:** the constraint that makes the ideas usable (budget,
brand, length, availability); how many; how different they must be from each
other; how the user will choose.

**Usual defect:** no constraints, so ten interchangeable generic ideas.

```
<Context: what the ideas are for, and who decides.>

Generate <N> <things> for <purpose>.

Each must: <hard constraints — e.g. under 12 characters, .com plausible, no "AI">.
Make them genuinely different: <axes of variety — tone, angle, mechanism>.
Skip the obvious ones: <what the user already has or rejected>.

Output: a numbered list, each idea with one line on why it fits. Then mark your top pick.
```

## unclear

The scan found no task signal, or a tie. Do not guess: ask the one question
that decides it — "What should the model hand back to you?" — and pick the
pattern from the answer.
