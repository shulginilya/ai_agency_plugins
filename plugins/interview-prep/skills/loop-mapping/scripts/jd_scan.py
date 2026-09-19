#!/usr/bin/env python3
"""Read one job description and report what the interview will actually test.

Usage:
    python scripts/jd_scan.py jd.txt
    cat jd.txt | python scripts/jd_scan.py - --json

This is an extractor, not a judgement. It counts the concrete things a posting
commits to -- the stack it names, the seniority and leadership weight it asks
for, the domain it lives in, the rounds it admits to running -- and it says
loudly which of those it could not find. A posting that never describes its
process is not a posting with an easy loop; it is a posting whose loop you have
to ask about, and that is a different next action.

Exit codes:
    0   mapped     stack and round signals both present -- a loop can be drafted
    1   thin       almost nothing concrete; the ad is boilerplate, ask for more
    2   unusable   empty, unreadable, or too short to scan
    3   unclear    the work is described but the process is not -- ask the recruiter
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

MIN_CHARS = 200

STACK: Dict[str, List[str]] = {
    "languages": [
        "typescript", "javascript", "python", "go", "golang", "rust", "java", "kotlin",
        "c#", "scala", "ruby", "php", "swift", "sql",
    ],
    "frontend": [
        "react", "next.js", "nextjs", "vue", "angular", "svelte", "remix", "redux",
        "tailwind", "web components", "ssr", "ssg", "isr", "core web vitals",
        "accessibility", "wcag", "design system", "storybook",
    ],
    "backend": [
        "node", "node.js", "nestjs", "express", "fastapi", "django", "spring",
        "graphql", "rest", "grpc", "microservices", "event-driven", "kafka",
        "rabbitmq", "domain-driven", "clean architecture", "postgres", "postgresql",
        "mysql", "mongodb", "redis", "elasticsearch",
    ],
    "cloud": [
        "aws", "gcp", "azure", "lambda", "ecs", "fargate", "eks", "kubernetes",
        "docker", "terraform", "pulumi", "cloudformation", "api gateway", "dynamodb",
        "s3", "cloudfront", "sqs", "sns", "eventbridge", "cloudwatch", "ci/cd",
        "github actions", "observability", "prometheus", "grafana", "datadog",
    ],
    "data_ai": [
        "llm", "large language model", "genai", "generative ai", "rag",
        "retrieval augmented", "vector database", "embeddings", "pinecone", "weaviate",
        "pgvector", "langchain", "llamaindex", "openai", "anthropic", "claude",
        "fine-tuning", "prompt engineering", "agentic", "mlops", "evals",
        "evaluation harness", "pytorch", "tensorflow", "hugging face", "inference",
        "guardrails", "machine learning",
    ],
    "practices": [
        "code review", "mentoring", "pair programming", "tdd", "test-driven",
        "trunk-based", "feature flags", "blue-green", "canary", "incident response",
        "on-call", "postmortem", "architecture review", "rfc", "adr",
    ],
}

SENIORITY = [
    "principal", "staff", "lead", "head of", "senior", "mid-level", "junior",
    "architect", "engineering manager",
]

LEADERSHIP = [
    "mentor", "mentoring", "coach", "lead a team", "line management", "hiring",
    "roadmap", "stakeholder", "cross-functional", "technical direction",
    "own the architecture", "set the standard", "drive adoption", "influence",
]

ROUND_SIGNALS: Dict[str, List[str]] = {
    "recruiter-screen": ["recruiter call", "intro call", "screening call", "first call", "phone screen"],
    "hiring-manager": ["hiring manager", "team lead interview", "manager interview"],
    "live-coding": [
        "live coding", "pair programming interview", "coding interview", "technical screen",
        "codility", "hackerrank", "coderpad", "algorithm",
    ],
    "take-home": ["take-home", "take home", "coding challenge", "home assignment", "case study", "sample task"],
    "system-design": ["system design", "architecture interview", "design interview", "whiteboard"],
    "behavioral": ["behavioural", "behavioral", "values interview", "culture fit", "culture add", "competency"],
    "panel": ["panel", "onsite loop", "final round", "team interview", "meet the team"],
    "leadership": ["leadership interview", "cto interview", "founder interview", "vp interview"],
}

PROCESS_WORDS = [
    "interview process", "hiring process", "what to expect", "our process",
    "stages", "steps of the process", "first step", "the process looks",
]

ARCHETYPES: Dict[str, List[str]] = {
    "big-tech": ["faang", "thousands of engineers", "global scale", "nasdaq", "publicly traded"],
    "scale-up": ["scale-up", "scaleup", "series a", "series b", "series c", "hypergrowth", "fast-growing"],
    "early-startup": ["seed", "pre-seed", "founding engineer", "first engineer", "0 to 1", "zero to one"],
    "agency": ["agency", "consultancy", "consulting", "client projects", "billable"],
    "enterprise": ["gmbh", "corporate", "enterprise", "mittelstand", "works council", "betriebsrat"],
}

COMP = re.compile(
    r"(?:[€$£]|eur|usd|gbp|chf)\s?\d{2,3}(?:[.,]\d{3})*(?:\s?k)?|\d{2,3}\s?k\s?(?:€|eur|usd)"
    r"|salary range|gehalt|day rate|tagessatz|compensation range",
    re.I,
)


def read_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("no such description file: %s" % source)
    return path.read_text(encoding="utf-8", errors="replace")


def _present(haystack: str, term: str) -> bool:
    """Word-bounded everywhere: 'go' must not match 'django', and 'architect'
    must not match 'the architecture'. Punctuation in a term ('node.js', 'ci/cd')
    is fine -- the boundaries only exclude an adjacent letter or digit."""
    term = term.strip().lower()
    if not term:
        return False
    return re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(term), haystack) is not None


def _matches(haystack: str, terms: List[str]) -> List[str]:
    return [t for t in terms if _present(haystack, t)]


def detect_stack(text_lower: str) -> Dict[str, List[str]]:
    found = {}
    for area, terms in STACK.items():
        hits = _matches(text_lower, terms)
        if hits:
            found[area] = hits
    return found


def detect_rounds(text_lower: str) -> Dict[str, List[str]]:
    found = {}
    for round_name, terms in ROUND_SIGNALS.items():
        hits = _matches(text_lower, terms)
        if hits:
            found[round_name] = hits
    return found


def detect_archetype(text_lower: str) -> Optional[str]:
    scored = []
    for name, terms in ARCHETYPES.items():
        hits = _matches(text_lower, terms)
        if hits:
            scored.append((len(hits), name))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None  # two archetypes tie; say nothing rather than pick one
    return scored[0][1]


def assess(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    lower = stripped.lower()

    if len(stripped) < MIN_CHARS:
        return {
            "verdict": "unusable",
            "exit_code": 2,
            "reason": "the description is %d characters; nothing can be read from it" % len(stripped),
        }

    stack = detect_stack(lower)
    rounds = detect_rounds(lower)
    seniority = _matches(lower, SENIORITY)
    leadership = _matches(lower, LEADERSHIP)
    archetype = detect_archetype(lower)
    process_described = bool(_matches(lower, PROCESS_WORDS)) or len(rounds) >= 2
    comp_stated = bool(COMP.search(stripped))

    distinct_terms = sum(len(v) for v in stack.values())
    domain = max(stack, key=lambda a: len(stack[a])) if stack else None

    unknown = []
    if not rounds and not process_described:
        unknown.append("the description never says what the interview process is")
    if not seniority:
        unknown.append("no seniority level is named")
    if not comp_stated:
        unknown.append("compensation is not stated")
    if not archetype:
        unknown.append("the company stage or type is not stated")

    if distinct_terms < 4 and not rounds:
        verdict, code = "thin", 1
        reason = "only %d concrete technical terms and no process detail -- this is boilerplate" % distinct_terms
    elif rounds:
        verdict, code = "mapped", 0
        reason = "%d round signals and %d technical terms -- enough to draft the loop" % (len(rounds), distinct_terms)
    else:
        verdict, code = "unclear", 3
        reason = "the work is described (%d technical terms) but the process is not -- ask the recruiter" % distinct_terms

    return {
        "verdict": verdict,
        "exit_code": code,
        "reason": reason,
        "primary_domain": domain,
        "stack": stack,
        "distinct_terms": distinct_terms,
        "seniority_terms": seniority,
        "leadership_signals": leadership,
        "leadership_weight": "high" if len(leadership) >= 4 else "some" if leadership else "none stated",
        "round_signals": rounds,
        "archetype": archetype,
        "process_described": process_described,
        "compensation_stated": comp_stated,
        "unknown": unknown,
    }


def render(report: Dict[str, Any]) -> str:
    lines = ["%s -- %s" % (report["verdict"].upper(), report["reason"])]
    if report["verdict"] == "unusable":
        return "\n".join(lines)

    lines.append("")
    lines.append("Domain: %s" % (report["primary_domain"] or "not clear from the text"))
    for area, hits in sorted(report["stack"].items()):
        lines.append("  %-10s %s" % (area, ", ".join(sorted(hits))))
    lines.append("Seniority: %s" % (", ".join(report["seniority_terms"]) or "not named"))
    lines.append("Leadership weight: %s (%s)" % (
        report["leadership_weight"], ", ".join(report["leadership_signals"][:6]) or "no signals"))
    lines.append("Company type: %s" % (report["archetype"] or "not stated"))
    lines.append("")
    if report["round_signals"]:
        lines.append("Rounds the description admits to:")
        for name, hits in sorted(report["round_signals"].items()):
            lines.append("  %-16s from: %s" % (name, ", ".join(hits)))
    else:
        lines.append("Rounds the description admits to: none")
    if report["unknown"]:
        lines.append("")
        lines.append("Ask about:")
        for item in report["unknown"]:
            lines.append("  - %s" % item)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan a job description for what the interview will test.")
    parser.add_argument("source", help="description file, or - for stdin")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        text = read_text(args.source)
    except (OSError, FileNotFoundError) as exc:
        print("unusable: %s" % exc, file=sys.stderr)
        return 2

    report = assess(text)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
