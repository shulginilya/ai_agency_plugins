"""Spot text that looks like a credential, so it is never stored.

A pattern scan catches the common shapes, not every secret: the skill still
tells the agent never to save one.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

_TOKENS = (
    # five dashes for PEM and PGP; four and a space for SSH2
    ("a private key", r"-{4,5} ?BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)? ?-{4,5}"),
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
# secret also names SECRET_KEY, SECRET_KEY_BASE, AWS_SECRET_ACCESS_KEY and secretKey
_KEYS = r"(password|passwd|token|secret(?:[_-]?(?:access[_-]?)?key(?:[_-]?base)?)?|api_?key)"

# How an assignment is written. What may close the key: "token", `token`, **token**; in code also config['token']
_CLOSE = r"[\"'`*_]{0,6}"
_CODE_CLOSE = r"[\"'`\]*_]{0,6}"
# password: str = ..., token: Optional[str] = ..., token: string | null = ...
_TYPE = (r"(?:[ \t]*:[ \t]*[a-z_][\w.]{0,60}(?:\[[^\n=]{0,60}\])?"
         r"(?:[ \t]*\|[ \t]*[a-z_][\w.]{0,60}){0,4})?")
_CODE_ASSIGN = r"[ \t]*(?:::|\|\||\?\?|[:?+.])?=(?!=)"  # = := ::= ?= += .= ||= ??= but not ==
_QUOTE = r"(?:[\"'`]|\*\*)?"
_LITERAL = r"[rbuf]{0,2}[\"'`]"  # opens a string in code
# What follows "host:" in a URL with a port, so a later "@" in its path does not end a password. A number is
# always a port. A placeholder is one only where that "@" opens a path segment (/@scope), since
# "$ecret/x@host" is a password.
_PORT = (r"(?:\d{1,5}/"
         r"|(?:port|\$?\{\{[^{}]*\}\}|\$\{[^{}\s]*\}|\$\([\w.]*\)|\$\w+|%\w*%|%[sd]|\{\w*\}|<[\w-]*>)"
         r"/(?:[^\s@/]{0,256}/){0,16}@)")
_PATH = r"[ \t]*[\"']?[~.]?/"  # how the shell's PWD starts; a password after Pwd= rarely does
# What can follow "NAME=" on the next line of text without being its value
_NOT_A_VALUE = (r"(?!"
                # the next entry of a template: NAME=value, or an empty name all in one case. Base64 padding is
                # neither: mixed case, and nothing but "=" after its first "="
                r"[a-z_][\w.-]*=(?!=)\S"
                r"|(?-i:[A-Z_][A-Z0-9_.-]*|[a-z_][a-z0-9_.-]*)=[ \t]*(?=\r?\n|\Z)"
                # a comment, a rule, a code fence or a closing line
                r"|#|//|-{3}|~{3}|={3}|_{3}|```|</|<!|[})\]])")

# (kind, pattern): the last group is the value, checked for being a placeholder.
_VALUES = (
    ("a password in a connection string", r"://[^\s/:@]*:([^\s/]+)@"),
    # the same with a "/" in the password; the bounds keep the scan linear
    # (a drive letter, as in file://C:/, is not a user name)
    ("a password in a connection string",
     r"://(?![A-Za-z]:/)[^\s/:@\[\]]*:(?!(?i:" + _PORT + r"))([^\s@\"'/]{0,256}/[^\s@\"']{0,256})@"),
    # Pwd is ODBC's key. Only inside a connection string: PWD= alone is the shell's directory
    ("a password in a connection string",
     r"(?i);[ \t]*pwd[ \t]*=(?!" + _PATH + r")[ \t]*" + _QUOTE + _VALUE),
    ("a password in a connection string",
     r"(?i)(?<![\w$])pwd[ \t]*=(?!" + _PATH + r")[ \t]*" + _QUOTE + r"([^\s;\"'][^\s;]{0,255}?)"
     r"(?=[\"'*]{0,2};[ \t]*(?:uid|user id|server|database|driver|dsn)[ \t]*=)"),
    # as a shell, an env file, a Makefile default or Markdown writes it
    ("a password, token or secret assignment",
     r"(?i)" + _KEYS + _CLOSE + r"[ \t]*\??=(?!=)[ \t]*" + _QUOTE + _VALUE),
    # as code writes it. Only a string counts here: an unquoted value is a variable or a call
    ("a password, token or secret assignment",
     r"(?i)" + _KEYS + _CODE_CLOSE + _TYPE + _CODE_ASSIGN + r"[ \t]*" + _LITERAL + _VALUE),
    # a Makefile's := takes a bare value; its names are in capitals, unlike Go's. _KEYS has no \x classes to upper()
    ("a password, token or secret assignment", _KEYS.upper() + r"[ \t]*::?=[ \t]*" + _VALUE),
    # the value alone on the next line, perhaps with a ";", a "," or a comment after it
    ("a password, token or secret assignment",
     r"(?i)" + _KEYS + _CODE_CLOSE + _CODE_ASSIGN + r"[ \t]*\r?\n[ \t]*" + _NOT_A_VALUE + _QUOTE + _VALUE
     + _QUOTE + r"[ \t]*(?:[;,][ \t]*)?(?:(?:#|//)[^\n]*)?(?=\r?\n|\Z)"),
    ("a password, token or secret value",
     r"(?i)[\"'][\w.-]*" + _KEYS + r"[\"'][ \t]*:[ \t]*[\"']([^\"'\s][^\"'\n]*)[\"']"),
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
