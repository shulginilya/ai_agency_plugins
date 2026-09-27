#!/usr/bin/env python3
"""Read one inbound recruiter or networking message and say what it is and what it needs.

Usage:
    python scripts/inbound.py message.txt
    cat message.txt | python scripts/inbound.py - --json
    python scripts/inbound.py message.txt --profile .jobhunt/profile.json
    python scripts/inbound.py --init      # add the `replies` section to the profile

This is a first pass, not a judgement. It answers what is countable -- whether
the message is about a job at all, whether it looks like sales or a scam
pattern, which declared titles, must-haves and deal-breakers it mentions,
what it asks for, which language it is in -- and lists what the message does
not say. The model reading the output still decides; the point is that the
reply is built from a list of what is actually unknown rather than from a
general impression that the message "sounds promising".

The profile is the same `.jobhunt/profile.json` the job-hunter plugin reads,
plus a `replies` section this plugin owns (how to sign, what may be said about
money, which contact details may be shared, when calls can happen).

Exit codes:
    0   engage     a job conversation that fits well enough to aim for a call now
    1   decline    a deal-breaker or an explicit mismatch -- or ignore: sales,
                   spam, or a scam pattern (the `intent` field says which)
    2   unusable   no profile, an unreadable message, or an empty one
    3   qualify    about a job, but something decisive is missing -- or personal:
                   not about work at all, which is the user's to answer
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PROFILE_PATH = Path(".jobhunt/profile.json")

# The job-hunter profile fields, so `--init` on a fresh workspace writes a file
# both plugins can read. Kept identical to job-hunter's template on purpose.
PROFILE_TEMPLATE: Dict[str, Any] = {
    "titles": ["Senior Software Engineer", "Senior AI Engineer"],
    "must_have": ["typescript", "react", "node"],
    "nice_to_have": ["aws", "python", "next.js"],
    "markets": {"onsite": ["Berlin"], "remote": ["eu", "europe", "global", "worldwide"]},
    "tracks": ["contract", "permanent"],
    "rate_floor": {"currency": "EUR", "per": "day", "amount": 0},
    "deal_breakers": ["relocation required", "unpaid", "equity only"],
    "min_must_have_ratio": 0.6,
}

SEND_MODES = ["approve-then-send", "fill-only", "draft-only"]
DISCLOSE = ["never", "on-request", "early"]

# The part of the profile this plugin owns. Every value is the user's to set;
# an empty one means "ask the user", never "make something up".
REPLIES_TEMPLATE: Dict[str, Any] = {
    "name": "",
    "send_mode": "approve-then-send",
    "languages": ["en"],
    "timezone": "Europe/Berlin",
    "availability": [],
    "notice_period": "",
    "earliest_start": "",
    "salary": {"say": "", "disclose": "on-request"},
    "day_rate": {"say": ""},
    "shareable": {"email": "", "phone": "", "links": []},
    "never_mention": [],
    "must_ask": ["salary range", "remote policy", "interview process"],
    "max_chars": 900,
}

REMOTE_HINTS = ("remote", "fully remote", "work from home", "anywhere", "distributed", "homeoffice", "home office")
ONSITE_HINTS = ("on-site", "onsite", "in office", "hybrid", "in-office", "vor ort")
CONTRACT_HINTS = ("contract", "freelance", "freelancer", "b2b", "interim", "day rate", "daily rate",
                  "projekt", "tagessatz", "stundensatz", "freiberuf")
PERMANENT_HINTS = ("permanent", "full-time employee", "festanstellung", "unbefristet", "salary",
                   "festangestellt", "gehalt")

JOB_TERMS = (
    "role", "position", "opening", "vacancy", "hiring", "recruit", "headhunt", "job",
    "career", "interview", "salary", "compensation", "contract", "freelance", "project",
    "team is looking", "we are looking", "looking for a", "join our", "join the",
    "stelle", "projekt", "vakanz", "karriere", "gehalt", "wir suchen", "suchen wir",
    "opportunity",
)

SALES_TERMS = (
    "our services", "we help companies", "we help businesses", "outsourc", "nearshore",
    "offshore", "white-label", "white label", "dedicated developers", "dedicated team",
    "staff augmentation", "lead generation", "book a demo", "free trial", "webinar",
    "bootcamp", "resume writing", "cv writing", "ghostwrit", "grow your", "boost your",
    "partnership", "investment opportunity", "software development company",
    "our agency can", "we can provide", "unsere dienstleistung",
)

AGENCY_TERMS = (
    "my client", "our client", "on behalf of", "for a client", "confidential client",
    "undisclosed", "a client of ours", "unser kunde", "unseren kunden", "mein kunde",
    "meines kunden", "unseres kunden", "für einen kunden",
)

# Scam patterns are requests, not topics: a fintech posting may well mention bank
# accounts. What gives a scam away is asking the candidate to send or pay.
SCAM_PATTERNS = (
    r"\b(send|share|provide|upload)\b[^.?!]{0,40}\b(passport|id card|identity card|ausweis|"
    r"bank (details|account)|social security|iban)\b",
    r"\b(pay|paid|payment of|transfer)\b[^.?!]{0,40}\b(fee|deposit|training|equipment|starter kit)\b",
    r"\b(registration|processing|application|training|onboarding) fee\b",
    r"\b(crypto|usdt|bitcoin|btc|ethereum|wallet address)\b",
    r"\bdeposit (the|a|this) (cheque|check)\b|\b(cheque|check) to deposit\b",
    r"\bno interviews? (needed|required|necessary)\b|\bwithout (an )?interview\b",
    r"\breshipp?ing\b|\bpackage forwarding\b",
)
OFF_PLATFORM = r"\b(telegram|whatsapp|wechat)\b"

ASKS = {
    "call": r"\b(call|chat|talk|phone|zoom|teams|meet|speak|telefonat|gespr(ä|ae)ch|kennenlernen|termin)\b",
    "cv": r"\b(cv|resume|résumé|lebenslauf)\b",
    "salary": r"\b(salary|compensation|expectations|expected (salary|rate)|day rate|daily rate|hourly rate|"
              r"gehalt|gehaltsvorstellung|stundensatz|tagessatz)\b",
    "availability": r"\b(availab\w*|notice period|start date|when (can|could) you start|k(ü|ue)ndigungsfrist|"
                    r"verf(ü|ue)gbar\w*|eintrittstermin|starttermin)",
    "interest": r"\b(interested|open to|would you be open|keen|interesse|offen f(ü|ue)r|wechselbereit)\b",
}

DE_WORDS = {
    "und", "der", "die", "das", "ich", "sie", "nicht", "mit", "für", "ist", "wir", "ihnen",
    "ihr", "bei", "eine", "einen", "zu", "auf", "sehr", "gerne", "würde", "können", "hallo",
    "grüße", "vielen", "dank", "stelle", "unser", "unsere", "wäre", "haben", "freue", "mich",
}
EN_WORDS = {
    "the", "and", "you", "your", "with", "for", "is", "we", "to", "are", "our", "would",
    "could", "hi", "hello", "thanks", "thank", "looking", "best", "regards", "this", "that",
    "i", "am", "be", "have", "of", "in", "it",
}

_CUR = r"(?:€|\$|£|\bEUR\b|\bUSD\b|\bGBP\b|\bCHF\b|\beuros?\b)"
_NUM = r"\d{1,3}(?:[.,  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_K = r"\s?[kK]\b"
_RANGE = r"\s?(?:-|–|—|to|bis)\s?"
MONEY_SPAN = re.compile(
    r"(?:{cur}\s?(?:{num})(?:{k})?(?:{rng}{cur}?\s?(?:{num})(?:{k})?)?)"
    r"|(?:(?:{num})(?:{k})?(?:{rng}(?:{num})(?:{k})?)?\s?{cur})"
    r"|(?:\b(?:{num})(?:{rng}(?:{num}))?{k})".format(cur=_CUR, num=_NUM, k=_K, rng=_RANGE),
    re.I,
)


class ProfileError(Exception):
    """The profile is missing or unusable."""


def load_profile(path: Optional[str] = None) -> Dict[str, Any]:
    candidate = Path(path) if path else DEFAULT_PROFILE_PATH
    if not candidate.is_file():
        raise ProfileError(
            "no profile at %s -- run `inbound.py --init` to write one, then fill it in" % candidate
        )
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError("%s is not readable JSON (%s)" % (candidate, exc))
    if not isinstance(data, dict):
        raise ProfileError("%s must contain a JSON object" % candidate)
    merged = copy.deepcopy(PROFILE_TEMPLATE)
    merged.update(data)
    return merged


def replies_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    """The `replies` section with every default filled in, nested maps included."""
    merged = copy.deepcopy(REPLIES_TEMPLATE)
    declared = profile.get("replies") or {}
    if not isinstance(declared, dict):
        return merged
    for key, value in declared.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    if merged.get("send_mode") not in SEND_MODES:
        merged["send_mode"] = "approve-then-send"
    return merged


def init_profile(path: Optional[str] = None) -> str:
    """Write a profile, or add the `replies` section to an existing one.

    Never overwrites anything the user wrote: an existing file is backed up and
    only gains the missing section; a file that is not a JSON object is refused.
    """
    candidate = Path(path) if path else DEFAULT_PROFILE_PATH
    if not candidate.is_file():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        data = copy.deepcopy(PROFILE_TEMPLATE)
        data["replies"] = copy.deepcopy(REPLIES_TEMPLATE)
        candidate.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return "wrote %s -- fill in titles, must-haves, markets and the replies section" % candidate
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ProfileError("%s is not valid JSON (%s); fix it by hand first" % (candidate, exc))
    if not isinstance(data, dict):
        raise ProfileError("%s must contain a JSON object" % candidate)
    if isinstance(data.get("replies"), dict):
        return "%s already has a replies section; nothing changed" % candidate
    shutil.copyfile(str(candidate), str(candidate) + ".bak")
    data["replies"] = copy.deepcopy(REPLIES_TEMPLATE)
    candidate.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "added a replies section to %s (backup at %s.bak) -- fill it in" % (candidate, candidate)


def read_message(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("no such message file: %s" % source)
    return path.read_text(encoding="utf-8", errors="replace")


def _present(text_lower: str, term: str) -> bool:
    """Substring match, word-bounded for short alphanumeric terms so that 'go'
    does not match 'django' and 'job' does not match 'jobs-noreply'."""
    term = term.strip().lower()
    if not term:
        return False
    if len(term) <= 4 and term.isalnum():
        return re.search(r"\b%s\b" % re.escape(term), text_lower) is not None
    return term in text_lower


def detect_language(text: str) -> str:
    tokens = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(1 for t in tokens if t in DE_WORDS)
    en = sum(1 for t in tokens if t in EN_WORDS)
    if de + en < 3:
        return "unknown"
    if de > en * 1.2:
        return "de"
    if en > de * 1.2:
        return "en"
    return "unknown"


def _to_number(raw: str) -> Optional[float]:
    s = raw.replace(" ", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[., ]\d{3})+", s):
        return float(re.sub(r"[., ]", "", s))
    grouped = re.fullmatch(r"(\d{1,3}(?:[., ]\d{3})+)[.,]\d+", s)
    if grouped:
        return float(re.sub(r"[., ]", "", grouped.group(1)))
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def money_spans(text: str) -> List[str]:
    return [m.group(0).strip() for m in MONEY_SPAN.finditer(text)]


def money_figures(text: str) -> List[int]:
    """Every money amount in the text as a whole number: '95-110k' -> 95000, 110000;
    'EUR 700/day' -> 700; '95.000 €' -> 95000. Bare numbers with neither a
    currency nor a 'k' are not money -- they are years, times and team sizes."""
    figures = set()
    for span in money_spans(text):
        has_k = re.search(r"\d\s?[kK]\b", span) is not None
        for raw in re.findall(_NUM, span):
            value = _to_number(raw)
            if value is None:
                continue
            if has_k and value < 1000:
                value *= 1000
            figures.add(int(round(value)))
    return sorted(figures)


def detect_track(text_lower: str) -> Optional[str]:
    contract = any(hint in text_lower for hint in CONTRACT_HINTS)
    permanent = any(hint in text_lower for hint in PERMANENT_HINTS)
    if contract and not permanent:
        return "contract"
    if permanent and not contract:
        return "permanent"
    return None


def detect_location(text_lower: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    markets = profile.get("markets") or {}
    remote_ok = any(hint in text_lower for hint in REMOTE_HINTS)
    onsite_only = any(hint in text_lower for hint in ONSITE_HINTS) and not remote_ok
    named = [city for city in (markets.get("onsite") or []) if _present(text_lower, str(city))]
    remote_region = [r for r in (markets.get("remote") or []) if _present(text_lower, str(r))]
    if remote_ok and (remote_region or not onsite_only):
        match = True
    elif named:
        match = True
    elif onsite_only:
        match = False
    else:
        match = None  # the message does not say
    return {"remote": remote_ok, "onsite_only": onsite_only, "cities_matched": named,
            "remote_regions_matched": remote_region, "match": match}


def detect_asks(text_lower: str) -> List[str]:
    return [name for name, pattern in ASKS.items() if re.search(pattern, text_lower)]


def assess(message: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    text_lower = message.lower()
    language = detect_language(message)

    scam = [p for p in SCAM_PATTERNS if re.search(p, text_lower)]
    off_platform = sorted(set(re.findall(OFF_PLATFORM, text_lower)))
    job_hits = [t for t in JOB_TERMS if _present(text_lower, t)]
    sales_hits = [t for t in SALES_TERMS if t in text_lower]
    agency = [t for t in AGENCY_TERMS if t in text_lower]
    asks = detect_asks(text_lower)

    titles = [str(t) for t in (profile.get("titles") or []) if _present(text_lower, str(t))]
    must = [str(t) for t in (profile.get("must_have") or [])]
    must_hit = [t for t in must if _present(text_lower, t)]
    must_missing = [t for t in must if t not in must_hit]
    breakers = [str(t) for t in (profile.get("deal_breakers") or []) if _present(text_lower, str(t))]
    track = detect_track(text_lower)
    location = detect_location(text_lower, profile)
    comp = money_spans(message)
    ratio = (len(must_hit) / len(must)) if must else 1.0
    short = len(message.strip()) < 600

    reasons: List[str] = []
    unknowns: List[str] = []

    job_related = bool(job_hits or titles or must_hit)
    if scam:
        kind, intent = "scam-risk", "ignore"
        reasons.append("asks for money, identity documents or payment details, or skips the interview")
    elif sales_hits and (not job_related or (len(sales_hits) >= 2 and len(sales_hits) > len(job_hits))):
        kind, intent = "sales", "ignore"
        reasons.append("reads as a sales pitch: %s" % ", ".join(sales_hits[:3]))
    elif not job_related:
        kind, intent = "network", "personal"
        reasons.append("nothing in it is about a role -- the user's to answer, or to leave")
    else:
        kind = "recruiter-agency" if agency else "opportunity"
        tracks = [str(t).lower() for t in (profile.get("tracks") or [])]
        if breakers:
            reasons.append("trips a deal-breaker: %s" % ", ".join(breakers))
        if location["match"] is False:
            reasons.append("on-site only, and not in a declared city")
        if track and tracks and track not in tracks:
            reasons.append("%s work, which the profile does not take" % track)
        if reasons:
            intent = "decline"
        elif titles or (must and ratio >= float(profile.get("min_must_have_ratio") or 0.6)):
            intent = "engage"
            reasons.append("matches %s" % ", ".join(titles + must_hit) if (titles or must_hit)
                           else "matches the profile")
        else:
            intent = "qualify"
            reasons.append("about a job, but too little is said to judge the fit")

        if not comp:
            unknowns.append("compensation")
        if location["match"] is None:
            unknowns.append("location and remote policy")
        if track is None:
            unknowns.append("contract or permanent")
        if agency:
            unknowns.append("the client company (an agency is not naming it)")
        if must_missing and short:
            unknowns.append("the stack (not stated: %s)" % ", ".join(must_missing))
        if not titles:
            unknowns.append("the level and title")

    if off_platform:
        reasons.append("asks to move the conversation to %s" % ", ".join(off_platform))

    return {
        "kind": kind,
        "intent": intent,
        "language": language,
        "asks": asks,
        "reasons": reasons,
        "unknowns": unknowns,
        "signals": {
            "job_terms": job_hits,
            "sales_terms": sales_hits,
            "agency_terms": agency,
            "scam_patterns_hit": len(scam),
            "off_platform": off_platform,
            "titles_matched": titles,
            "must_have": {"present": must_hit, "missing": must_missing},
            "deal_breakers_hit": breakers,
            "track": track,
            "location": location,
            "compensation_mentioned": comp,
        },
    }


EXIT = {"engage": 0, "decline": 1, "ignore": 1, "qualify": 3, "personal": 3}


def render(report: Dict[str, Any]) -> str:
    s = report["signals"]
    lines = [
        "Intent:   %s  (%s, language %s)" % (report["intent"].upper(), report["kind"], report["language"]),
        "Why:      %s" % ("; ".join(report["reasons"]) or "-"),
        "Asks for: %s" % (", ".join(report["asks"]) or "nothing specific"),
    ]
    if report["kind"] in ("opportunity", "recruiter-agency"):
        lines.append("Matched:  %s" % (", ".join(s["titles_matched"] + s["must_have"]["present"]) or "-"))
        lines.append("Money:    %s" % (", ".join(s["compensation_mentioned"]) or "not stated"))
        lines.append("Unknown:  %s" % (", ".join(report["unknowns"]) or "nothing decisive"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("message", nargs="?", help="message file, or - for stdin")
    parser.add_argument("--profile", help="profile JSON (default .jobhunt/profile.json)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--init", action="store_true", help="write the profile, or add its replies section")
    args = parser.parse_args()

    try:
        if args.init:
            print(init_profile(args.profile))
            return 0
        if not args.message:
            parser.print_help()
            return 2
        profile = load_profile(args.profile)
        message = read_message(args.message)
    except (ProfileError, OSError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    if not message.strip():
        sys.stderr.write("the message is empty\n")
        return 2

    report = assess(message, profile)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return EXIT[report["intent"]]


if __name__ == "__main__":
    raise SystemExit(main())
