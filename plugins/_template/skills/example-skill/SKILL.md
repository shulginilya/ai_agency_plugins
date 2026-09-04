---
name: example-skill
description: Replace this with what the skill does and when to use it, in the words a user would actually type. The description is the only thing the model sees before deciding to load the skill, so it is the highest-leverage sentence in the whole plugin. Use when authoring a new skill from the template.
license: MIT
metadata:
  author: ilya-shulgin
  version: "0.1.0"
---

# Example skill

One paragraph on what this skill is for and what it assumes.

## When this applies

Be concrete about the trigger. The model matches on the description first, but
a body that restates the trigger in context makes it stick.

## Steps

1. The first thing to do, stated as an instruction.
2. The second. Keep steps short enough to follow without re-reading.
3. What to do when the input is not what step 1 expected.

```bash
python scripts/example.py --help
```

## Reference material

Put anything long in `references/` and link it, so it loads only when needed:

- [Detailed reference](references/REFERENCE.md)

## Output

Say exactly what the skill should produce. A skill that does good work and
reports it in a shape nobody asked for is a skill that gets ignored.
