#!/usr/bin/env python3
"""PreToolUse hook: nothing leaves as a message unless the user approved that text.

Runs before the browser tools that type into a page (Claude in Chrome, the
desktop app's built-in browser) and before mail tools that send or reply. It
pulls the text out of the call and compares it with the approved, unsent
drafts in the reply ledger:

    * approved text, or a paragraph of it -> silent; the call goes ahead
    * anything else that looks like a message -> "ask": the harness puts the
      call in front of the user, with the reason, instead of running it
    * profile send_mode "draft-only" -> "deny": the user said nothing is sent
    * a mail send whose text is not visible in the call -> "ask"

Scope, stated plainly: the hook sees text, not the page it lands on. Typed
text shorter than 40 characters (a search box, a filter) passes unchecked,
and a click on a Send button is not text at all -- which is why approval is
the recruiter-reply skill's rule and this hook is the net under it, not the
rule itself. It is silent outside a workspace that has a reply ledger.

The approval rule is not defined here: `is_approved` is imported from the
reply-ledger skill, so the hook can never disagree with `threads.py`.

Never blocks by failing: the exit status is always 0, and an unreadable event
is ignored. A decision is expressed as JSON on stdout.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
for directory in (
    PLUGIN_ROOT / "skills" / "reply-ledger" / "scripts",
    PLUGIN_ROOT / "skills" / "inbound-triage" / "scripts",
):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

try:
    import inbound  # type: ignore
    import threads  # type: ignore
except ImportError:  # installed without the skills; stay silent
    threads = None
    inbound = None

MESSAGE_MIN_CHARS = 40
TEXT_KEYS = ("body", "text", "plain_text", "plainText", "plain_text_body", "html", "htmlBody",
             "html_body", "content", "message")
MAIL_VERBS = ("send", "reply", "forward")


def _short(name: str) -> str:
    return name.rsplit("__", 1)[-1]


def is_browser(tool_name: str) -> bool:
    return _short(tool_name) in ("computer", "form_input", "browser_batch")


def is_mail_send(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return "mail" in lowered and _short(lowered).startswith(MAIL_VERBS)


def browser_texts(tool: str, tool_input: Dict[str, Any]) -> List[str]:
    short = _short(tool)
    if short == "computer":
        if tool_input.get("action") == "type" and isinstance(tool_input.get("text"), str):
            return [tool_input["text"]]
        return []
    if short == "form_input":
        value = tool_input.get("value")
        return [value] if isinstance(value, str) else []
    if short == "browser_batch":
        out: List[str] = []
        for action in tool_input.get("actions") or []:
            if isinstance(action, dict):
                out += browser_texts(str(action.get("name") or ""), action.get("input") or {})
        return out
    return []


def _plain(key: str, value: str) -> str:
    if "html" in key.lower():
        value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return value


def mail_texts(tool_input: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key, value in tool_input.items():
        if key in TEXT_KEYS and isinstance(value, str) and value.strip():
            out.append(_plain(key, value))
        elif isinstance(value, dict):
            out += [_plain(k, v) for k, v in value.items()
                    if k in TEXT_KEYS and isinstance(v, str) and v.strip()]
    return [t for t in out if t.strip()]


def decide(event: Dict[str, Any], root: Path) -> Optional[Tuple[str, str]]:
    """Return (decision, reason), or None to stay silent."""
    tool = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None

    if is_browser(tool):
        texts = [t for t in browser_texts(tool, tool_input) if len(t.strip()) >= MESSAGE_MIN_CHARS]
        blind = False
    elif is_mail_send(tool):
        texts = mail_texts(tool_input)
        blind = not texts
    else:
        return None
    if not texts and not blind:
        return None

    ledger_path = root / threads.DEFAULT_PATH
    if not ledger_path.is_file():
        return None

    mode = "approve-then-send"
    try:
        mode = inbound.replies_settings(inbound.load_profile(str(root / inbound.DEFAULT_PROFILE_PATH)))["send_mode"]
    except Exception:
        pass
    if mode == "draft-only":
        return ("deny", "recruiter-inbox: send_mode is draft-only in the profile, so no message text is "
                        "typed or sent. Hand the approved draft to the user to send themselves.")

    try:
        state = threads.read(ledger_path)
    except Exception as exc:
        return ("ask", "recruiter-inbox: the reply ledger is unreadable (%s), so this text cannot be "
                       "checked against an approval. Send it only if you approved it." % exc)

    if blind:
        return ("ask", "recruiter-inbox: this sends mail, and the text is not visible in the call, so "
                       "it cannot be matched to an approved draft.")
    if is_mail_send(tool) and tool_input.get("attachments"):
        return ("ask", "recruiter-inbox: this mail carries attachments. Approval covers the text only; "
                       "confirm the files are the ones you mean to send.")
    whole = is_mail_send(tool)
    unapproved = [t for t in texts if not threads.is_approved(t, state, whole=whole)]
    if not unapproved:
        return None
    sample = threads.normalise(unapproved[0])
    if len(sample) > 80:
        sample = sample[:77] + "..."
    return ("ask", "recruiter-inbox: %r is not an approved draft in %s. Approve it with "
                   "`threads.py approve`, or allow it here only if you mean to send it as it is."
            % (sample, threads.DEFAULT_PATH))


def main() -> int:
    if threads is None or inbound is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    root = Path(str(event.get("cwd") or os.getcwd()))
    try:
        verdict = decide(event, root)
    except Exception:
        return 0
    if verdict is None:
        return 0
    decision, reason = verdict
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
