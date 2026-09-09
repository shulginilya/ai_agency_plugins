#!/usr/bin/env python3
"""Score one posting against a declared profile, deterministically.

Usage:
    python scripts/fit.py posting.txt
    cat posting.txt | python scripts/fit.py -
    python scripts/fit.py posting.txt --profile .jobhunt/profile.json --json
    python scripts/fit.py --init            # write a profile template

This is a rule engine, not a judgement. It answers the parts that are countable
— which declared must-haves the posting mentions, which deal-breakers it trips,
whether the market and track match — and refuses to guess at the rest. A model
reading the output still has to decide; the point is that it decides from a
list of what is actually missing rather than from a general impression.

Exit codes:
    0   pursue     every must-have present, no deal-breaker, market and track fit
    1   skip       a deal-breaker, or a must-have gap too wide to argue past
    2   unusable   no profile, unreadable posting, or an empty one
    3   unclear    partial match, or the posting does not say something decisive
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PROFILE_PATH = Path(".jobhunt/profile.json")

PROFILE_TEMPLATE = {
    "titles": ["Senior Software Engineer", "Senior AI Engineer"],
    "must_have": ["typescript", "react", "node"],
    "nice_to_have": ["aws", "python", "next.js"],
    "markets": {"onsite": ["Berlin"], "remote": ["eu", "europe", "global", "worldwide"]},
    "tracks": ["contract", "permanent"],
    "rate_floor": {"currency": "EUR", "per": "day", "amount": 0},
    "deal_breakers": ["relocation required", "unpaid", "equity only"],
    "min_must_have_ratio": 0.6,
}

REMOTE_HINTS = ("remote", "fully remote", "work from home", "anywhere", "distributed")
ONSITE_HINTS = ("on-site", "onsite", "in office", "hybrid", "in-office")
CONTRACT_HINTS = ("contract", "freelance", "freelancer", "b2b", "interim", "day rate", "daily rate")
PERMANENT_HINTS = ("permanent", "full-time employee", "festanstellung", "unbefristet", "salary")

MONEY = re.compile(
    r"(?P<cur>[€$£]|EUR|USD|GBP)\s?(?P<low>\d{2,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s?"
    r"(?:k\b)?(?:\s?[-–—to]+\s?(?P<high>\d{2,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s?(?:k\b)?)?",
    re.I,
)


def load_profile(path: Optional[str]) -> Dict[str, Any]:
    candidate = Path(path) if path else DEFAULT_PROFILE_PATH
    if not candidate.is_file():
        raise FileNotFoundError(
            "no profile at %s — run `fit.py --init` to write a template, then edit it" % candidate
        )
    data = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % candidate)
    merged = dict(PROFILE_TEMPLATE)
    merged.update(data)
    return merged


def read_posting(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("no such posting file: %s" % source)
    return path.read_text(encoding="utf-8", errors="replace")


def _present(text_lower: str, term: str) -> bool:
    """Substring match, but word-bounded for short alphanumeric terms so that
    'go' does not match 'django' and 'r' does not match everything."""
    term = term.strip().lower()
    if not term:
        return False
    if len(term) <= 4 and term.isalnum():
        return re.search(r"\b%s\b" % re.escape(term), text_lower) is not None
    return term in text_lower


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
        match = None  # the posting does not say
    return {
        "remote": remote_ok,
        "onsite_only": onsite_only,
        "cities_matched": named,
        "remote_regions_matched": remote_region,
        "match": match,
    }


def detect_rate(text: str) -> Optional[Dict[str, Any]]:
    match = MONEY.search(text)
    if not match:
        return None
    return {"raw": match.group(0).strip(), "currency": match.group("cur")}


def assess(posting: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    text_lower = posting.lower()

    must = [str(t) for t in (profile.get("must_have") or [])]
    nice = [str(t) for t in (profile.get("nice_to_have") or [])]
    breakers = [str(t) for t in (profile.get("deal_breakers") or [])]

    must_hit = [t for t in must if _present(text_lower, t)]
    must_missing = [t for t in must if t not in must_hit]
    nice_hit = [t for t in nice if _present(text_lower, t)]
    breakers_hit = [t for t in breakers if _present(text_lower, t)]

    titles = [str(t) for t in (profile.get("titles") or [])]
    title_hit = [t for t in titles if _present(text_lower, t)]

    track = detect_track(text_lower)
    wanted_tracks = [str(t).lower() for t in (profile.get("tracks") or [])]
    track_match = None if track is None else (track in wanted_tracks)

    location = detect_location(text_lower, profile)
    ratio = (len(must_hit) / len(must)) if must else 1.0
    threshold = float(profile.get("min_must_have_ratio", 0.6))

    reasons: List[str] = []
    verdict = "pursue"

    if breakers_hit:
        verdict = "skip"
        reasons.append("deal-breaker present: %s" % ", ".join(breakers_hit))
    elif ratio < threshold:
        verdict = "skip"
        reasons.append(
            "only %d of %d must-haves present (%.0f%%, floor %.0f%%); missing: %s"
            % (len(must_hit), len(must), ratio * 100, threshold * 100, ", ".join(must_missing))
        )
    elif track_match is False:
        verdict = "skip"
        reasons.append("posting is %s, and the profile does not list that track" % track)
    elif location["match"] is False:
        verdict = "skip"
        reasons.append("on-site only, and no profile city is named in the posting")
    else:
        if must_missing:
            verdict = "unclear"
            reasons.append("must-haves not mentioned: %s" % ", ".join(must_missing))
        if track is None:
            verdict = "unclear"
            reasons.append("the posting does not say whether it is contract or permanent")
        if location["match"] is None:
            verdict = "unclear"
            reasons.append("the posting does not state a location or remote policy")
        if verdict == "pursue":
            reasons.append(
                "all %d must-haves present%s"
                % (len(must), ("; also " + ", ".join(nice_hit)) if nice_hit else "")
            )

    return {
        "verdict": verdict,
        "reasons": reasons,
        "must_have": {"present": must_hit, "missing": must_missing, "ratio": round(ratio, 2)},
        "nice_to_have_present": nice_hit,
        "deal_breakers_hit": breakers_hit,
        "titles_matched": title_hit,
        "track": track,
        "track_match": track_match,
        "location": location,
        "compensation_mentioned": detect_rate(posting),
    }


EXIT = {"pursue": 0, "skip": 1, "unclear": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("posting", nargs="?", help="file with the posting text, or - for stdin")
    parser.add_argument("--profile", help="path to profile.json (default: .jobhunt/profile.json)")
    parser.add_argument("--init", action="store_true", help="write a profile template and exit")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.init:
        target = Path(args.profile) if args.profile else DEFAULT_PROFILE_PATH
        if target.exists():
            sys.stderr.write("refusing to overwrite %s\n" % target)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(PROFILE_TEMPLATE, indent=2) + "\n", encoding="utf-8")
        print("wrote %s — edit it before triaging anything" % target)
        return 0

    if not args.posting:
        parser.error("give a posting file, or - to read stdin")

    try:
        profile = load_profile(args.profile)
        posting = read_posting(args.posting)
    except (OSError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    if not posting.strip():
        sys.stderr.write("the posting is empty\n")
        return 2

    report = assess(posting, profile)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("%s" % report["verdict"].upper())
        for reason in report["reasons"]:
            print("  - %s" % reason)
        must = report["must_have"]
        print("  must-haves: %d/%d present" % (len(must["present"]), len(must["present"]) + len(must["missing"])))
        if report["nice_to_have_present"]:
            print("  also mentions: %s" % ", ".join(report["nice_to_have_present"]))
        if report["compensation_mentioned"]:
            print("  compensation named: %s" % report["compensation_mentioned"]["raw"])
        else:
            print("  compensation: not stated — ask before investing time")
    return EXIT[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
