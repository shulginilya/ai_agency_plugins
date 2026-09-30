---
description: Run a prompt cold against a sample input and report every point where the model had to guess.
argument_hint: "[path to the prompt] [optional: path to a sample input]"
model: sonnet
allowed_tools: Read Grep Glob
---

Test this prompt: {{ARGS}}

If no prompt is given, use the last prompt written in this conversation. If no
sample input is given and the prompt takes one, ask for a real one — an
invented sample tests the prompt against the author's assumptions.

Hand the prompt and the sample, and nothing else, to the `prompt-tester`
agent. Do not pass the conversation, the user's goals or your own notes on
what the prompt should do — the test is only worth running if the tester
cannot fill the gaps from memory.

Where subagents are not available, do the same yourself: carry the prompt out
literally, log every guess, and try one input with a key part missing. Say that
the test ran in the same context and is weaker for it.

Report the tester's verdict and its guesses. For each guess that would change
the output, propose the one sentence that removes it — then offer to apply
them with `/prompt-review`.
