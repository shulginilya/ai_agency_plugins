"""Minimal YAML-frontmatter reader/writer.

Deliberately not a YAML implementation. Agent Skills frontmatter is a small,
flat shape (scalars, one list, one one-level map), and depending on PyYAML
would break the "standard library only" rule that keeps this toolkit runnable
inside any harness sandbox. If PyYAML happens to be installed we use it, since
it is strictly more correct; otherwise we fall back to the subset parser below.

Supported subset:
    key: scalar
    key: "quoted scalar"
    key: [a, b, c]
    key:
      - item
      - item
    key:
      sub: value
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

try:  # pragma: no cover - exercised only when PyYAML is present
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None

DELIM = "---"


class FrontmatterError(ValueError):
    """Raised when a document's frontmatter cannot be parsed."""


def split(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block excludes delimiters."""
    if not text.startswith(DELIM):
        return "", text
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == DELIM:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise FrontmatterError("frontmatter opened with '---' but never closed")


def parse(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse a document into (metadata, body)."""
    block, body = split(text)
    if not block.strip():
        return {}, body
    if _yaml is not None:
        loaded = _yaml.safe_load(block)
        if loaded is None:
            return {}, body
        if not isinstance(loaded, dict):
            raise FrontmatterError("frontmatter must be a mapping")
        return loaded, body
    return _parse_subset(block), body


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value[0] == value[-1] and value[0] in "\"'" and len(value) > 1:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _parse_subset(block: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    key = None
    container: Any = None
    for raw_line in block.split("\n"):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indented = raw_line[:1].isspace()
        line = raw_line.strip()
        if indented and key is not None:
            if line.startswith("- "):
                if not isinstance(container, list):
                    container = []
                    result[key] = container
                container.append(_scalar(line[2:]))
                continue
            if ":" in line:
                if not isinstance(container, dict):
                    container = {}
                    result[key] = container
                sub_key, _, sub_value = line.partition(":")
                container[sub_key.strip()] = _scalar(sub_value)
                continue
            raise FrontmatterError("unsupported indented line: %r" % raw_line)
        if ":" not in line:
            raise FrontmatterError("expected 'key: value', got %r" % raw_line)
        key, _, value = line.partition(":")
        key = key.strip()
        container = None
        result[key] = _scalar(value) if value.strip() else ""
    return result


def _dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    needs_quotes = (
        text[0] in "[]{}>|&*!%@`#-?" or ": " in text or text != text.strip() or "\n" in text
    )
    # Round-trip guard: a string like "1.0" or "true" must not come back as a
    # float or a bool, which matters for the spec's string-to-string metadata map.
    if not needs_quotes and _scalar(text) != text:
        needs_quotes = True
    if needs_quotes:
        return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')
    return text


def dump(meta: Dict[str, Any]) -> str:
    """Serialize a metadata mapping back to a frontmatter block (no delimiters)."""
    lines: List[str] = []
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                lines.append("%s: []" % key)
                continue
            lines.append("%s:" % key)
            lines.extend("  - %s" % _dump_scalar(item) for item in value)
        elif isinstance(value, dict):
            if not value:
                continue
            lines.append("%s:" % key)
            lines.extend("  %s: %s" % (k, _dump_scalar(v)) for k, v in value.items())
        else:
            lines.append("%s: %s" % (key, _dump_scalar(value)))
    return "\n".join(lines)


def compose(meta: Dict[str, Any], body: str) -> str:
    """Rebuild a full document from metadata and body."""
    block = dump(meta)
    body = body.lstrip("\n")
    if not block:
        return body
    return "%s\n%s\n%s\n\n%s" % (DELIM, block, DELIM, body)
