#!/usr/bin/env python3
"""Acceptance criteria out of a ticket, into a numbered test-plan skeleton.

    criteria.py --issue 42 [--repo owner/name] [--json]    read the issue with gh
    criteria.py --file ticket.md [--json]                    read a Markdown body
    cat body.md | criteria.py [--json]                       read stdin

Finds the criteria the way tickets in this repo write them: checkbox items
(`- [ ]` or `- [x]`) under an "Acceptance criteria" heading, or, when the
body has no such heading, every checkbox item in it. Each becomes AC1, AC2, …
with its Given/When/Then parts split out when it has them, and a flag when a
criterion cannot be tested as written: no observable result, or a vague word
like "fast", "intuitive" or "properly".

Standard library only. Exit status: 0 criteria found, 1 gh failed,
2 bad input or no criteria at all, which is a finding in itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Dict, List, Optional

HEADING_RE = re.compile(r"^#{1,6}\s*acceptance criteria\b.*$", re.I)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(.+?)\s*$")
GWT_RE = re.compile(r"^\s*given\s+(?P<given>.+?),?\s+when\s+(?P<when>.+?),?\s+then\s+(?P<then>.+?)\s*$", re.I)
VAGUE = ("fast", "quickly", "intuitive", "user-friendly", "user friendly", "properly", "correctly",
         "nice", "clean", "easy", "smooth", "robust", "as expected", "etc", "happy", "satisfied", "better")
OBSERVABLE = re.compile(r"\b(shows?|displays?|returns?|is|are|has|have|exits?|lists?|contains?|equals?|"
                        r"rejects?|refuses?|redirects?|creates?|writes?|reads?|passes|fails|appears?|"
                        r"sees?|receives?|responds?|names?|states?|stays?|keeps?|moves?|links?|prints?|validates?|builds?|"
                        r"runs?|gives?|routes?|accepts?|extracts?|says|cannot|renders?|records?|installs?|"
                        r"deletes?|closes?|opens?|loads?|saves?|sends?|blocks?|allows?|warns?|errors?)\b", re.I)


class CriteriaError(Exception):
    exit_code = 2


def extract(body: str) -> List[Dict[str, object]]:
    """Checkbox items under an Acceptance criteria heading, else every checkbox item."""
    lines = body.splitlines()
    section: List[str] = []
    inside = False
    for line in lines:
        if HEADING_RE.match(line.strip()):
            inside = True
            continue
        if inside and ANY_HEADING_RE.match(line.strip()):
            break
        if inside:
            section.append(line)
    source = section if inside else lines
    texts = [m.group(1) for m in (CHECKBOX_RE.match(l) for l in source) if m]
    items = []
    for number, text in enumerate(texts, 1):
        item: Dict[str, object] = {"id": "AC%d" % number, "text": text, "problems": problems(text)}
        gwt = GWT_RE.match(text)
        if gwt:
            item.update(given=gwt.group("given"), when=gwt.group("when"), then=gwt.group("then"))
        items.append(item)
    return items


def problems(text: str) -> List[str]:
    found = []
    lower = text.lower()
    vague = [w for w in VAGUE if re.search(r"\b%s\b" % re.escape(w), lower)]
    if vague:
        found.append("vague: %s — name the observable result instead" % ", ".join(vague))
    if not OBSERVABLE.search(text) and not GWT_RE.match(text):
        found.append("no observable result — say what the user or the system shows, returns or does")
    return found


def plan_skeleton(items: List[Dict[str, object]]) -> str:
    out = ["| AC | Criterion | Cases (happy · edge/boundary · negative · regression) | Problems |",
           "| --- | --- | --- | --- |"]
    for it in items:
        out.append("| %s | %s | %s-1 … | %s |" % (it["id"], str(it["text"]).replace("|", "\\|"), it["id"],
                                                 "; ".join(it["problems"]) or "—"))
    return "\n".join(out)


def read_issue(number: int, repo: Optional[str]) -> str:
    cmd = ["gh", "issue", "view", str(number), "--json", "body", "-q", ".body"]
    if repo:
        cmd += ["--repo", repo]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        err = CriteriaError("gh is not installed; pass --file instead")
        err.exit_code = 1
        raise err
    if run.returncode != 0:
        err = CriteriaError("gh could not read issue #%d: %s" % (number, run.stderr.strip()))
        err.exit_code = 1
        raise err
    return run.stdout


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--issue", type=int)
    source.add_argument("--file")
    parser.add_argument("--repo", help="owner/name for --issue (default: the current repo)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.issue:
            body = read_issue(args.issue, args.repo)
        elif args.file:
            with open(args.file, encoding="utf-8") as handle:
                body = handle.read()
        else:
            body = sys.stdin.read()
        items = extract(body)
        if not items:
            raise CriteriaError("no acceptance criteria found: there is nothing to test against. "
                                "Ask for checkbox criteria under an 'Acceptance criteria' heading.")
    except (CriteriaError, OSError) as exc:
        print("criteria: %s" % exc, file=sys.stderr)
        return getattr(exc, "exit_code", 2)
    print(json.dumps(items, indent=2, ensure_ascii=False) if args.json else plan_skeleton(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
