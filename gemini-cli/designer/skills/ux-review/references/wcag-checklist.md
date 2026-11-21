# WCAG 2.2 AA: the checks that catch most failures

Not the whole standard. These are the success criteria that real product UI
fails most often, each with how to test it in a few minutes. Cite the number
in the finding.

## Perceivable
| SC | Check |
| --- | --- |
| 1.1.1 Non-text content | Every meaningful image has alt text. Decorative ones have `alt=""`. Icon-only buttons have an accessible name. |
| 1.3.1 Info and relationships | Headings are real `h1`–`h6` in order, lists are lists, tables have headers, and every input has a programmatic label. |
| 1.3.5 Identify input purpose | Personal-data fields have the right `autocomplete` (email, name, tel). |
| 1.4.1 Use of color | Color is never the only signal: errors also have text or an icon, and links in text are also underlined. |
| 1.4.3 Contrast (minimum) | Text 4.5:1, large text 3:1. Run `contrast.py` in both themes, including placeholder and disabled-looking text that still carries meaning. |
| 1.4.4 Resize text | At 200% zoom nothing is cut off or overlapping. |
| 1.4.10 Reflow | At 320px wide there is no horizontal scrolling, except for tables, code and maps. |
| 1.4.11 Non-text contrast | Input borders, focus rings, icons and chart marks are 3:1 against what is next to them. |
| 1.4.12 Text spacing | Larger line and letter spacing does not clip text: no fixed heights on text containers. |
| 1.4.13 Content on hover or focus | Tooltips can be dismissed with Escape, can be hovered, and stay until dismissed. |

## Operable
| SC | Check |
| --- | --- |
| 2.1.1 Keyboard | Everything works with the keyboard alone: menus, dialogs, drag-and-drop (with an alternative), and custom widgets. |
| 2.1.2 No keyboard trap | Focus can always leave a component: editors, embeds and dialogs. |
| 2.4.3 Focus order | Tab order follows the visual order. A dialog moves focus in, traps it while open, and returns it on close. |
| 2.4.4 Link purpose | Link text makes sense alone: no bare "click here" or "more". |
| 2.4.7 Focus visible | Every focusable element shows a visible focus indicator. `outline: none` without a replacement fails. |
| 2.4.11 Focus not obscured | Sticky headers and footers and cookie banners do not cover the focused element. |
| 2.5.3 Label in name | A visible label is part of the accessible name, so voice control works. |
| 2.5.7 Dragging movements | Anything done by dragging also has a single-pointer alternative. |
| 2.5.8 Target size | Pointer targets are at least 24×24 CSS px, or spaced so a 24px circle fits. |

## Understandable
| SC | Check |
| --- | --- |
| 3.1.1 Language of page | `<html lang>` is set. |
| 3.2.2 On input | Changing a field does not submit, navigate or open something unexpected. |
| 3.3.1 Error identification | Errors are shown in text, next to the field, and say which field. |
| 3.3.2 Labels or instructions | Required fields and formats are stated before the user types. |
| 3.3.7 Redundant entry | Information already given in the flow is not asked for again. |
| 3.3.8 Accessible authentication | Login does not depend on a memory or puzzle test. Paste and password managers work. |

## Robust
| SC | Check |
| --- | --- |
| 4.1.2 Name, role, value | Custom controls expose their role and state, such as `aria-expanded`, `aria-checked`, `aria-selected`. |
| 4.1.3 Status messages | Toasts, "saved" and result counts are announced through `role="status"` or `aria-live` without moving focus. |

Also respect `prefers-reduced-motion`: large movement and parallax should stop
or calm down when it is set. That is 2.3.3 (AAA), but users depend on it.
