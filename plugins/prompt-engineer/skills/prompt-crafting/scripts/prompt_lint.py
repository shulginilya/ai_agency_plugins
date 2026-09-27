#!/usr/bin/env python3
"""Lint a prompt for the defects that make a model guess.

Usage:
    python scripts/prompt_lint.py prompt.md
    python scripts/prompt_lint.py --text "Summarize this. Make it good."
    cat prompt.md | python scripts/prompt_lint.py - --json

This is the single home for the rules. The plugin's PostToolUse hook and its
MCP server both import `lint` from here, so there is one list to correct when
a rule turns out to be noisy.

Every rule is narrow on purpose. A linter that fires on every prompt gets
ignored, and the point is that the one time it fires, someone reads it. It
checks the text, not the idea: a prompt can pass cleanly and still ask for the
wrong thing, which is what the `prompt-tester` agent is for.

Exits 0 when there are no errors (warnings are allowed), 1 when there is at
least one error, and 2 when the input could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ERROR, WARN, INFO = "error", "warn", "info"

PLACEHOLDERS = re.compile(
    r"\[(?:insert|your|add|todo|tbd|placeholder|fill in)[^\]]*\]"
    r"|<\s*(?:todo|tbd|insert[^>]*)\s*>"
    r"|\bTODO\b|\bTBD\b|\bXXX\b|lorem ipsum",
    re.IGNORECASE,
)
TEMPLATE_VARS = re.compile(r"\{\{\s*([A-Za-z_][\w.-]*)\s*\}\}|\$\{([A-Za-z_]\w*)\}")
VAGUE = re.compile(
    r"\betc\.?|\band so on\b|\bas (?:needed|appropriate)\b|\bif necessary\b"
    r"|\bhigh[- ]quality\b|\bmake it (?:good|better|nice|pop)\b|\bproperly\b"
    r"|\bin a good way\b|\bbest possible\b|\bsome kind of\b",
    re.IGNORECASE,
)
OUTPUT_SHAPE = re.compile(
    r"\b(?:format|output|respond|response|reply|return|json|markdown|bullets?|table|list"
    r"|sections?|headings?|words|sentences?|paragraphs?|schema|fields?|csv|yaml|structure"
    r"|deliver|produce|report|block|diff|verdict)\b",
    re.IGNORECASE,
)
SHOUT = re.compile(r"\b[A-Z]{4,}\b")
ACRONYMS = {
    "JSON", "HTML", "YAML", "HTTP", "HTTPS", "UUID", "ISO", "UTF", "ASCII", "REST", "CRUD",
    "TODO", "NOTE", "STAR", "GDPR", "HIPAA", "CSV", "TOML", "OAUTH", "JWT", "AWS", "GCP",
}
EMPHASIS = re.compile(r"\b(?:IMPORTANT|CRITICAL|MUST|NEVER|ALWAYS|ABSOLUTELY)\b")
NEGATIVE = re.compile(r"\b(?:don't|do not|never|avoid)\b", re.IGNORECASE)
POSITIVE_TURN = re.compile(r"\b(?:instead|rather|prefer|use|write|say|keep)\b", re.IGNORECASE)
BRIEF = re.compile(r"\b(?:brief|concise|short|succinct|terse|one sentence|minimal)\b", re.IGNORECASE)
EXHAUSTIVE = re.compile(r"\b(?:comprehensive|exhaustive|thorough|in[- ]depth|detailed|cover everything)\b", re.IGNORECASE)
DANGLING = re.compile(r"\b(?:below|following|attached|here is|here are)\b[^.\n]*:\s*$", re.IGNORECASE)
OPEN_TAG = re.compile(r"<([A-Za-z][\w-]*)(?:\s[^<>]*)?>")
CLOSE_TAG = re.compile(r"</([A-Za-z][\w-]*)\s*>")
# Void HTML elements, and the angle-bracket placeholders PLACEHOLDERS already reports.
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "todo", "tbd", "insert"}
EXAMPLE_HEAD = re.compile(r"(?im)^\s*(?:#+\s*)?(?:<example>|example\s*\d*\s*:|example\s*\d*$)")

MAX_WORDS = 4000
MIN_WORDS = 15


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _finding(rule: str, severity: str, line: int, message: str) -> Dict[str, object]:
    return {"rule": rule, "severity": severity, "line": line, "message": message}


def _strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code, keeping line numbers: material,
    examples and commands in code are data, and shouting, vague words or
    `<placeholders>` inside them are not the prompt's own voice."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", "``", text)


def _is_section_tag(prose: str, start: int, end: int) -> bool:
    """A tag alone on its line opens a section. `<the file name>` mid-sentence
    is placeholder notation for the reader, and flagging it as unclosed is noise."""
    line_start = prose.rfind("\n", 0, start) + 1
    line_end = prose.find("\n", end)
    line = prose[line_start:line_end if line_end != -1 else len(prose)]
    return line.strip() == prose[start:end]


def lint(text: str) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    prose = _strip_code(text)
    words = len(text.split())

    for match in PLACEHOLDERS.finditer(prose):
        findings.append(_finding(
            "unfilled-placeholder", ERROR, _line_of(prose, match.start()),
            "unfilled placeholder %r — the model will either copy it or invent a value" % match.group(0),
        ))

    variables = sorted({a or b for a, b in TEMPLATE_VARS.findall(text)})
    if variables:
        findings.append(_finding(
            "template-variables", INFO, 1,
            "template variables %s — every one must be filled at call time" % ", ".join(variables),
        ))

    stack: List[tuple] = []
    for match in re.finditer(r"</?[A-Za-z][\w-]*(?:\s[^<>]*)?>", prose):
        token = match.group(0)
        closing = CLOSE_TAG.fullmatch(token)
        if closing:
            name = closing.group(1)
            if stack and stack[-1][0] == name:
                stack.pop()
            elif any(entry[0] == name for entry in stack):
                while stack and stack[-1][0] != name:
                    unclosed = stack.pop()
                    findings.append(_finding(
                        "unclosed-tag", ERROR, unclosed[1],
                        "<%s> is never closed — the model cannot tell where the section ends" % unclosed[0],
                    ))
                stack.pop()
            else:
                findings.append(_finding(
                    "stray-closing-tag", ERROR, _line_of(prose, match.start()),
                    "</%s> closes a tag that was never opened" % name,
                ))
            continue
        opening = OPEN_TAG.fullmatch(token)
        if opening and not token.endswith("/>") and opening.group(1).lower() not in VOID_TAGS:
            name = opening.group(1)
            closed_somewhere = re.search(r"</%s\s*>" % re.escape(name), prose)
            if closed_somewhere or _is_section_tag(prose, match.start(), match.end()):
                stack.append((name, _line_of(prose, match.start())))
    for name, line in stack:
        findings.append(_finding(
            "unclosed-tag", ERROR, line,
            "<%s> is never closed — the model cannot tell where the section ends" % name,
        ))

    last = [line for line in text.rstrip().splitlines() if line.strip()]
    if last and DANGLING.search(last[-1]):
        findings.append(_finding(
            "dangling-reference", ERROR, len(text.rstrip().splitlines()),
            "the prompt ends by pointing at material that is not there (%r)" % last[-1].strip()[-60:],
        ))

    if words >= MIN_WORDS and not OUTPUT_SHAPE.search(prose):
        findings.append(_finding(
            "no-output-shape", WARN, 1,
            "nothing says what the output should look like — shape, length or format",
        ))

    vague = [(m.group(0), _line_of(prose, m.start())) for m in VAGUE.finditer(prose)]
    if vague:
        findings.append(_finding(
            "vague-instruction", WARN, vague[0][1],
            "vague wording the model has to interpret: %s — say what it means concretely"
            % ", ".join(sorted({'"%s"' % word for word, _ in vague})),
        ))

    shouted = [m for m in SHOUT.finditer(prose) if m.group(0) not in ACRONYMS]
    emphasis = EMPHASIS.findall(prose)
    # Enum values (CONFIRMED | REFUTED) are capitalised too; only shouting that
    # carries at least one emphasis word is inflation.
    if len(emphasis) >= 3 or (len({m.group(0) for m in shouted}) >= 5 and emphasis):
        first = shouted[0].start() if shouted else 0
        findings.append(_finding(
            "emphasis-inflation", WARN, _line_of(prose, first),
            "%d capitalised words (%d IMPORTANT/MUST-style) — current models over-apply shouted rules; "
            "state the reason instead" % (len(shouted), len(emphasis)),
        ))

    negative_lines = [
        index + 1 for index, line in enumerate(prose.splitlines())
        if NEGATIVE.search(line) and not POSITIVE_TURN.search(line)
    ]
    # A few "do not"s are normal in a good prompt; a prompt made mostly of them is not.
    prose_lines = sum(1 for line in prose.splitlines() if line.strip())
    if len(negative_lines) >= 5 or (len(negative_lines) >= 3 and len(negative_lines) * 4 >= prose_lines):
        findings.append(_finding(
            "negative-only", WARN, negative_lines[0],
            "%d lines only say what not to do (lines %s) — pair each with what to do instead"
            % (len(negative_lines), ", ".join(str(n) for n in negative_lines[:6])),
        ))

    brief, exhaustive = BRIEF.search(prose), EXHAUSTIVE.search(prose)
    if brief and exhaustive:
        findings.append(_finding(
            "conflicting-length", WARN, _line_of(prose, exhaustive.start()),
            "asks for %r and %r — give a number instead" % (brief.group(0), exhaustive.group(0)),
        ))

    examples = EXAMPLE_HEAD.findall(text)
    if len(examples) == 1:
        findings.append(_finding(
            "single-example", INFO, _line_of(text, text.find(examples[0].strip())),
            "one example gets copied closely — give two or three that differ, or say it is illustrative",
        ))

    if words < MIN_WORDS:
        findings.append(_finding(
            "too-thin", WARN, 1,
            "%d words — too little for the model to know the audience, the output or the bar" % words,
        ))
    elif words > MAX_WORDS:
        findings.append(_finding(
            "too-long", WARN, 1,
            "%d words — move reference material out of the instructions or split the task" % words,
        ))

    order = {ERROR: 0, WARN: 1, INFO: 2}
    findings.sort(key=lambda f: (order[str(f["severity"])], int(f["line"])))  # type: ignore[arg-type]
    return findings


def render(findings: List[Dict[str, object]]) -> str:
    if not findings:
        return "clean: no findings"
    return "\n".join(
        "%-5s line %-4s %-22s %s" % (f["severity"], f["line"], f["rule"], f["message"]) for f in findings
    )


def read_input(source: Optional[str], text: Optional[str]) -> str:
    if text is not None:
        return text
    if source in (None, "-"):
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", help="file with the prompt, or - for stdin")
    parser.add_argument("--text", help="the prompt itself, instead of a file")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a report")
    args = parser.parse_args(argv)
    # Findings quote the prompt; a cp1252 console must not crash on it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        text = read_input(args.source, args.text)
    except OSError as exc:
        print("prompt_lint: cannot read input: %s" % exc, file=sys.stderr)
        return 2
    if not text.strip():
        print("prompt_lint: the prompt is empty", file=sys.stderr)
        return 2
    findings = lint(text)
    print(json.dumps(findings, indent=2) if args.json else render(findings))
    return 1 if any(f["severity"] == ERROR for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
