# Design spec template

Copy this into the ticket under `## Design`, or into a comment. Delete any
section that truly doesn't apply and say why ("no list, so no empty state").
Don't leave a section blank.

```markdown
## Design

**User and job:** <who> wants to <do what> so that <outcome>.
**Entry point:** <where the user starts> · **Done when:** <what they see at the end>

### Flow
1. ...
2. ...
Exit: <how they get out at any step, and what is kept>

### Screen: <name>
**Layout (desktop):** <regions, top to bottom>
**At 768px / 375px:** <what stacks, collapses or moves>
**Components:** <existing components by name, with variant>
**Tokens:** <color, type and spacing tokens by name>

| State | What the user sees | What they can do |
| --- | --- | --- |
| Loading | | |
| Empty | | |
| Partial / long content | | |
| Error | | |
| Success | | |
| No permission | | |

**Copy**
| Key | Text |
| --- | --- |
| title | |
| primary action | |
| error.<case> | |

**Accessibility**
- Focus: <where it starts, the order, and where it goes on close>
- Names: <accessible names for icon-only controls>
- Announced: <status messages and how>
- Keyboard: <shortcuts, and Escape behavior>
- Contrast: <new pairs checked with contrast.py, ratio in both themes>

### Acceptance criteria
- [ ] Given <state>, when <action>, then <what the user sees>
- [ ] Keyboard only: <the flow> can be completed, and focus is never lost
- [ ] At 375px: <no sideways scroll, and the key action is still visible>

### Open questions
- <decision only a person can make, and who>
```
