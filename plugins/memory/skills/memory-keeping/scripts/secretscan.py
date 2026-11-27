"""Spot text that looks like a credential, so it is never stored.

A pattern scan catches the common shapes, not every secret: the skill still
tells the agent never to save one.
"""

from __future__ import annotations

import re
from typing import Optional

_TOKENS = (
    ("a private key", r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----"),
    ("an AWS access key id", r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    ("a GitHub token", r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    ("a Slack token", r"xox[abeoprs]-[A-Za-z0-9-]{10,}|xapp-\d-[A-Za-z0-9-]{10,}"),
    # real keys carry digits; a long hyphenated name such as sk-refactor-the-settings-screen does not
    ("an OpenAI or Anthropic API key", r"(?<![A-Za-z0-9_-])sk-(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}"),
)

# Each captures the value, which is then checked for being a placeholder.
_VALUES = (
    ("a password in a connection string", r"://[^\s/:@]*:([^\s/]+)@"),
    ("a password, token or secret assignment",
     r"(?i)(?:password|passwd|token|secret|api_?key)[ \t]*=(?!=)[ \t]*[\"']?([^\s\"';&,]+)"),
    ("a password, token or secret value",
     r"(?i)[\"'][\w-]*(?:password|passwd|token|secret|api_?key)[\"'][ \t]*:[ \t]*[\"']([^\"'\s]+)[\"']"),
)

# A value that stands for a secret without being one. Each form must match the whole value, so a real
# password that merely starts with a symbol or holds a bracket is still refused.
_PLACEHOLDER = re.compile("(?i)(?:%s)" % "|".join((
    r"\$\{[^}]*\}?|\$\(.*|\$[a-z_]\w*(?:\.\w+)*",  # ${VAR}, $(command), $VAR
    r"%[a-z_]\w*%|%s",
    r"<.*|\{.*|\[.*\]",  # <your password>, {{ value }}, [redacted]
    r"\*+|x{3,}|.*\.\.\.",
    r"\d{1,5}|none|null|nil|true|false|undefined",  # max_token=4000, token=null
    r"[a-z_][\w.]*\((?:[\w.]*\))?",  # a call: getToken(), env(
    r"(?:process\.env|os\.environ|os\.getenv|env\.|env\[).*",
)))


def find(text: str) -> Optional[str]:
    """The kind of credential the text seems to hold, or None."""
    for kind, pattern in _TOKENS:
        if re.search(pattern, text):
            return kind
    for kind, pattern in _VALUES:
        for match in re.finditer(pattern, text):
            if not _PLACEHOLDER.fullmatch(match.group(1)):
                return kind
    return None
