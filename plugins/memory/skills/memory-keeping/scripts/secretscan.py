"""Spot text that looks like a credential, so it is never stored.

A pattern scan catches the common shapes, not every secret: the skill still
tells the agent never to save one.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

_TOKENS = (
    ("a private key", r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----"),
    ("an AWS access key id", r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    ("a GitHub token", r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    ("a Slack token", r"xox[abeoprs]-[A-Za-z0-9-]{10,}|xapp-\d-[A-Za-z0-9-]{10,}"),
    # real keys carry digits; a long hyphenated name such as sk-refactor-the-settings-screen does not
    ("an OpenAI or Anthropic API key", r"(?<![A-Za-z0-9_-])sk-(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}"),
)

# Punctuation a sentence or Markdown can put right after a placeholder: "(password=<pw>)." or "**token=<t>**".
_TRAILING = ".:)]}`*_!?|"

# A value runs to the next space or separator, except that a closed placeholder form is taken whole, spaces
# and all, when nothing but punctuation follows it.
_VALUE = (r"((?:<[^<>\n]*>|\$?\{\{[^{}\n]*\}\}|\$\([^()\n]*\)|\[[^\[\]\n]*\])"
          r"(?=[" + re.escape(_TRAILING) + r"]*(?:[\s\"';&,]|$))"
          r"|[^\s\"';&,]+)")

# A value that stands for a secret without being one. Each form must match the whole value and be closed,
# so a real password that merely starts with a symbol, holds a bracket or ends in dots is still refused.
_PLACEHOLDER = "|".join((
    r"<[^<>]*>",  # <your password>
    r"\$?\{\{[^{}]*\}\}|\{(?:[a-z_]*|\d{1,2})\}",  # {{ value }}, ${{ secrets.X }}, {password}, {0}
    r"\[[^\[\]]*\]",  # [redacted]
    r"\$\{[^{}]*\}|\$\([^()]*\)",  # ${VAR}, $(command)
    # $VAR, $var or $camelCase; digits among mixed case is how a password that starts with $ looks
    r"(?-i:\$(?:[A-Z_][A-Z0-9_]*|[a-z_][a-z0-9_]*|[a-z][a-zA-Z_]*)(?:\.\w+)*)|\$env:\w+",
    r"%[a-z_]\w*%|%s",
    r"\*+|x{3,}|\.{3,}|\u2026",
    r"none|null|nil|true|false|undefined",
    # A call: getToken(), env(. A name with digits must be dotted, or start lowercase and close its list,
    # since "Summer2024(" is how a password looks.
    r"[a-z_][a-z_.]*\((?:[\w.]*\))?",
    r"[a-z_]\w*(?:\.[a-z_]\w*)+\((?:[\w.]*\))?",  # base64.b64decode(raw)
    r"(?-i:[a-z_]\w*)\([\w.]*\)",  # uuid4(), sha256(raw)
    r"(?:process\.env|os\.environ|os\.getenv|env\.|env\[).*",
))
_KEYS = r"(password|passwd|token|secret|api_?key)"

# (kind, pattern): the last group is the value, checked for being a placeholder.
_VALUES = (
    ("a password in a connection string", r"://[^\s/:@]*:([^\s/]+)@"),
    ("a password, token or secret assignment", r"(?i)" + _KEYS + r"[ \t]*=(?!=)[ \t]*[\"']?" + _VALUE),
    ("a password, token or secret value",
     r"(?i)[\"'][\w-]*" + _KEYS + r"[\"'][ \t]*:[ \t]*[\"']([^\"'\s]+)[\"']"),
)


def _plain_spaces(text: str) -> str:
    """No-break, zero-width and other odd characters read as a space, as they look; line breaks stay."""
    return "".join(" " if c != "\n" and unicodedata.category(c)[0] in "CZ" else c for c in text)


def _folded(text: str) -> str:
    """Invisible format characters removed and look-alikes such as a full-width "=" made ordinary."""
    return unicodedata.normalize("NFKC", "".join(c for c in text if unicodedata.category(c) != "Cf"))


def _placeholder(match: "re.Match[str]") -> bool:
    value = match.group(match.lastindex)
    # a short number after "token" is a count (max_token=4000); after password or secret it is the secret
    if match.lastindex > 1 and match.group(1).lower() == "token" and re.fullmatch(r"\d{1,5}", value):
        return True
    # The sentence's own punctuation is not part of a closed form. A form may itself end in up to three of
    # those characters (${{ x }}), so try each of those cuts: a fixed number, so this stays linear.
    core = len(value.rstrip(_TRAILING))
    forms = [value] + [value[:end] for end in range(core, min(core + 4, len(value)))
                       if end and value[end - 1] in ">})]"]
    return any(re.fullmatch(_PLACEHOLDER, form, re.IGNORECASE) for form in forms)


def find(text: str) -> Optional[str]:
    """The kind of credential the text seems to hold, or None."""
    # as written, as it looks (odd spaces), and as it reads (invisible characters gone)
    for candidate in (text, _plain_spaces(text), _folded(text)):
        for kind, pattern in _TOKENS:
            if re.search(pattern, candidate):
                return kind
        for kind, pattern in _VALUES:
            for match in re.finditer(pattern, candidate):
                if not _placeholder(match):
                    return kind
    return None
