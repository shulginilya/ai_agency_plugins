#!/usr/bin/env python3
"""Read the raw text a prompt is to be built from and say what it already covers.

Usage:
    python scripts/brief.py notes.txt
    python scripts/brief.py --text "write a cold email to CTOs about our API"
    cat notes.txt | python scripts/brief.py - --json

It answers three questions before a word of the prompt is written:

    task     — what kind of prompt this is (writing, extraction, agent, image ...)
    present  — which parts of a brief the text already states, with the evidence
    missing  — which of the parts that matter *for this task* it does not, and
               the one question that would fill each

The signals are deliberately plain keyword matches. This is a checklist that
cannot forget an item, not a classifier; the judgement stays with the model
reading the output. Anything it gets wrong is visible, because every "present"
slot quotes the words that triggered it.

Exits 0 whenever it could read the input, 2 when it could not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TASKS: Dict[str, List[str]] = {
    "writing": [
        r"\bwrite\b", r"\bdraft\b", r"\bemail\b", r"\bblog\b", r"\bpost\b", r"\barticle\b",
        r"\bcopy\b", r"\bnewsletter\b", r"\bletter\b", r"\bpitch\b", r"\bheadline", r"\btweet",
        r"\blinkedin\b", r"\blanding page\b", r"\bstory\b", r"\bscript\b(?! to)",
    ],
    "code": [
        r"\bcode\b", r"\bfunction\b", r"\bbug\b", r"\brefactor", r"\bimplement", r"\bapi\b",
        r"\bpython\b", r"\btypescript\b", r"\bjavascript\b", r"\bsql\b", r"\bunit tests?\b",
        r"\bendpoint\b", r"\bclass\b", r"\brepo(?:sitory)?\b", r"\bcompile", r"\bdebug",
    ],
    "summarization": [
        r"\bsummari[sz]", r"\btl;?dr\b", r"\bdigest\b", r"\bcondense", r"\bkey points\b",
        r"\brecap\b", r"\bminutes\b", r"\boverview of\b",
    ],
    "extraction": [
        r"\bextract", r"\bparse\b", r"\bpull out\b", r"\bfields?\b", r"\bstructured\b",
        r"\binvoices?\b", r"\bentities\b", r"\bscrape", r"\bfrom (?:each|every|the) (?:document|pdf|page|email)",
    ],
    "classification": [
        r"\bclassif", r"\bcategori[sz]", r"\blabel", r"\btag\b", r"\btriage", r"\bsentiment\b",
        r"\broute\b", r"\bspam\b", r"\bintent\b", r"\bwhich (?:category|bucket)",
    ],
    "analysis": [
        r"\banaly[sz]", r"\bcompare\b", r"\bevaluat", r"\bassess", r"\breview\b", r"\baudit\b",
        r"\bpros and cons\b", r"\btrade-?offs?\b", r"\brisks?\b", r"\bcritique",
    ],
    "agent": [
        r"\bsystem prompt\b", r"\bassistant\b", r"\bchatbot\b", r"\bbot\b", r"\bagent\b",
        r"\bpersona\b", r"\bcustomer support\b", r"\bgpt\b(?!-?\d)", r"\bcustom gpt\b",
        r"\bact as\b", r"\bplays? the role\b", r"\bresponds? to (?:users|customers)",
    ],
    "image": [
        r"\bimage\b", r"\bpicture\b", r"\billustration\b", r"\bphoto", r"\blogo\b", r"\bposter\b",
        r"\bmidjourney\b", r"\bdall-?e\b", r"\bstable diffusion\b", r"\brender\b", r"\bthumbnail\b",
        r"\bwallpaper\b",
    ],
    "research": [
        r"\bresearch\b", r"\bfind (?:sources|papers|studies)", r"\binvestigate\b", r"\bliterature\b",
        r"\bcitations?\b", r"\bmarket size\b", r"\bcompetitors?\b",
    ],
    "brainstorm": [
        r"\bbrainstorm", r"\bideas?\b", r"\bnames? for\b", r"\bslogans?\b", r"\btaglines?\b",
        r"\bsuggest(?:ions)?\b", r"\balternatives\b",
    ],
}

SLOTS: Dict[str, List[str]] = {
    "audience": [
        r"\baudience\b", r"\breaders?\b",
        r"\b(?:for|to|at|targeting|aimed at) (?:a |an |the |our )?(?:beginners?|experts?|executives?|kids"
        r"|children|developers|engineers|customers|users|clients|recruiters|managers|students|ctos?|ceos?"
        r"|founders|parents|patients|investors)\b",
        r"\bnon-?technical\b", r"\bstakeholders\b", r"\bend users?\b",
    ],
    "output_format": [
        r"\bjson\b", r"\btable\b", r"\bbullets?\b", r"\bbullet points\b", r"\bnumbered list\b",
        r"\bmarkdown\b", r"\bcsv\b", r"\byaml\b", r"\bxml\b", r"\bformat(?:ted)?\b", r"\bschema\b",
        r"\bheadings?\b", r"\bsections?\b", r"\btemplate\b", r"\bone-liner\b",
    ],
    "length": [
        r"\b\d+\s*(?:words?|sentences?|paragraphs?|pages?|characters?|chars|lines|bullets?|tokens)\b",
        r"\bunder \d+", r"\bshort\b", r"\bbrief\b", r"\bconcise\b", r"\bone (?:page|paragraph|sentence)\b",
        r"\blong-?form\b", r"\bdetailed\b",
    ],
    "tone": [
        r"\btone\b", r"\bvoice\b", r"\bformal\b", r"\bcasual\b", r"\bfriendly\b", r"\bprofessional\b",
        r"\bplayful\b", r"\bwarm\b", r"\bdirect\b", r"\bpersuasive\b", r"\bhumou?r", r"\bstyle of\b",
    ],
    "constraints": [
        r"\bmust\b", r"\bdo(?:n't| not)\b", r"\bavoid\b", r"\bnever\b", r"\bonly\b", r"\bwithout\b",
        r"\bno more than\b", r"\bat most\b", r"\bexclude\b", r"\bdeadline\b", r"\bbudget\b",
    ],
    "examples": [
        r"\bexamples?\b", r"\be\.g\.", r"\bfor instance\b", r"\blike this\b", r"\bsample\b",
        r"\bsomething like\b", r"\bsimilar to\b",
    ],
    "materials": [
        r"```", r"\battached\b", r"\bbelow\b", r"\bthe following\b", r"\bpasted\b", r"\bhere is\b",
        r"\bhere's\b", r"\bthis (?:document|text|email|transcript|article|code|data)\b",
        r"\bdataset\b", r"\bfile\b", r"\burl\b", r"https?://",
    ],
    "success": [
        r"\bsuccess\b", r"\bgoal is\b", r"\bso that\b", r"\bin order to\b", r"\bcriteria\b",
        r"\bshould be able to\b", r"\bmeasured? by\b", r"\bgood (?:output|result|answer) (?:is|means|looks)",
        r"\bthe point is\b", r"\bwe want\b", r"\bi want\b", r"\bi need\b",
    ],
    "target": [
        r"\bclaude\b", r"\bgpt-?\d", r"\bchatgpt\b", r"\bgemini\b", r"\bllama\b", r"\bmistral\b",
        r"\bopus\b", r"\bsonnet\b", r"\bhaiku\b", r"\bmidjourney\b", r"\bdall-?e\b", r"\bflux\b",
        r"\bstable diffusion\b", r"\bsystem prompt\b", r"\bapi call\b", r"\bpipeline\b",
        r"\bcursor\b", r"\bcodex\b", r"\bclaude code\b", r"\bcopilot\b",
    ],
    "style": [
        r"\bphotorealistic\b", r"\bwatercolou?r\b", r"\bminimalist\b", r"\bflat\b", r"\b3d\b",
        r"\bcinematic\b", r"\baspect ratio\b", r"\b\d+:\d+\b", r"\blighting\b", r"\bpalette\b",
        r"\bcolou?rs?\b", r"\bvector\b", r"\bsketch\b", r"\banime\b", r"\bisometric\b",
    ],
}

# Which slots decide whether the prompt works, per task. A missing critical
# slot is a question for the user; a missing optional one is an assumption the
# prompt states out loud.
CRITICAL: Dict[str, List[str]] = {
    "writing": ["audience", "success", "length"],
    "code": ["materials", "success"],
    "summarization": ["materials", "audience", "length"],
    "extraction": ["materials", "output_format"],
    "classification": ["output_format", "examples"],
    "analysis": ["materials", "success"],
    "agent": ["audience", "success", "constraints"],
    "image": ["style"],
    "research": ["success", "output_format"],
    "brainstorm": ["success", "constraints"],
    "unclear": ["success"],
}

OPTIONAL: List[str] = [
    "target", "audience", "output_format", "length", "tone", "constraints", "examples", "success",
]

QUESTIONS: Dict[str, str] = {
    "audience": "Who reads or uses the output, and what do they already know?",
    "output_format": "What exact shape should the output take — prose, bullets, a table, JSON with which fields?",
    "length": "How long should the output be — a number of words, sentences or items?",
    "tone": "What should it sound like — and is there a sample of the voice to match?",
    "constraints": "What must it never do, and what is off-limits or out of scope?",
    "examples": "Can you give two or three real examples of the input and the output you want for it?",
    "materials": "What input will the prompt run on — can you paste a real sample of it?",
    "success": "What does a good result let you do that a mediocre one does not?",
    "target": "Which model or tool will run this prompt, and is it a system prompt, a one-off message or a template in a pipeline?",
    "style": "What visual style, composition and aspect ratio — or a reference image to match?",
}


def _hits(text: str, patterns: List[str]) -> List[str]:
    found: List[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            found.append(match.group(0).strip())
    return found


def classify(text: str) -> List[Tuple[str, int]]:
    """Task types ranked by how many distinct signals fired, best first."""
    scored = [(task, len(_hits(text, patterns))) for task, patterns in TASKS.items()]
    scored = [item for item in scored if item[1] > 0]
    # A system prompt is the container, whatever the assistant does inside it.
    agent = dict(scored).get("agent", 0)
    if re.search(r"\bsystem prompt\b", text, flags=re.IGNORECASE):
        agent += 3
        scored = [(t, s) for t, s in scored if t != "agent"] + [("agent", agent)]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored


def brief(text: str) -> Dict[str, object]:
    ranked = classify(text)
    task = ranked[0][0] if ranked else "unclear"
    present: Dict[str, List[str]] = {}
    for slot, patterns in SLOTS.items():
        hits = _hits(text, patterns)
        if hits:
            present[slot] = hits[:4]

    critical = CRITICAL.get(task, CRITICAL["unclear"])
    ask = [{"slot": slot, "question": QUESTIONS[slot]} for slot in critical if slot not in present]
    assume = [slot for slot in OPTIONAL if slot not in present and slot not in critical]

    words = len(text.split())
    notes: List[str] = []
    if words < 12:
        notes.append("The input is %d words. Expect to ask more than you infer." % words)
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        notes.append(
            "Task type is a tie between %s and %s; decide which one the user means before writing."
            % (ranked[0][0], ranked[1][0])
        )
    if "```" in text or words > 400:
        notes.append("The input carries material of its own; keep it out of the instructions and pass it as data.")

    return {
        "task": task,
        "task_scores": dict(ranked),
        "words": words,
        "present": present,
        "ask": ask,
        "assume": assume,
        "notes": notes,
    }


def render(result: Dict[str, object]) -> str:
    lines = ["Task: %s  (%s)" % (
        result["task"],
        ", ".join("%s=%s" % item for item in dict(result["task_scores"]).items()) or "no signals",
    )]
    present = dict(result["present"])  # type: ignore[arg-type]
    lines.append("Present:")
    if present:
        for slot, hits in present.items():
            lines.append("  %-14s %s" % (slot, "; ".join('"%s"' % hit for hit in hits)))
    else:
        lines.append("  (nothing beyond the bare request)")
    ask = list(result["ask"])  # type: ignore[arg-type]
    lines.append("Ask (critical for this task, not stated):")
    if ask:
        for item in ask:
            lines.append("  %-14s %s" % (item["slot"], item["question"]))
    else:
        lines.append("  (none — every critical slot is covered)")
    assume = list(result["assume"])  # type: ignore[arg-type]
    if assume:
        lines.append("Assume and state: %s" % ", ".join(assume))
    for note in result["notes"]:  # type: ignore[union-attr]
        lines.append("Note: %s" % note)
    return "\n".join(lines)


def read_input(source: Optional[str], text: Optional[str]) -> str:
    if text is not None:
        return text
    if source in (None, "-"):
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", help="file with the raw text, or - for stdin")
    parser.add_argument("--text", help="the raw text itself, instead of a file")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a report")
    args = parser.parse_args(argv)
    # Evidence is quoted from the user's text; a cp1252 console must not crash on it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        text = read_input(args.source, args.text)
    except OSError as exc:
        print("brief: cannot read input: %s" % exc, file=sys.stderr)
        return 2
    if not text.strip():
        print("brief: the input is empty", file=sys.stderr)
        return 2
    result = brief(text)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
