#!/usr/bin/env python3
"""Check a reply draft against the profile before anyone is asked to approve it.

Usage:
    python scripts/draft_check.py draft.txt
    python scripts/draft_check.py draft.txt --inbound message.txt --intent qualify --json
    cat draft.txt | python scripts/draft_check.py - --channel gmail

The checks are the things a reply to a recruiter must never do without the
user saying so, and they are deterministic on purpose: a number, a phone
number or "I accept" in an outgoing message is either there or it is not.

BLOCKED means the draft says something only the user can authorise:
    * a money figure that is not in the profile's `salary.say` / `day_rate.say`
      (any figure at all when `salary.disclose` is "never")
    * a phone number, email address or link that is not in `shareable`
    * accepting an offer, agreeing terms, or resigning
    * anything in `never_mention` (a current employer, a private date)
    * an unfilled placeholder such as [Company] or {{name}}

REVIEW means the draft is allowed but probably not finished:
    * it neither asks anything nor proposes a time, so the thread stalls
    * it offers call times when no availability is declared
    * it is longer than `max_chars`, or written in a different language from
      the message it answers
    * it names a figure the sender did not ask for, or promises an attachment
    * it reads like a template ("I hope this message finds you well")

Exit codes:
    0   clean     nothing found
    1   blocked   at least one BLOCKED item -- do not ask for approval as is
    2   unusable  an empty draft, no profile, or the triage script is missing
    3   review    only REVIEW items -- fix them or say why they stand
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

TRIAGE_SCRIPTS = Path(__file__).resolve().parents[2] / "inbound-triage" / "scripts"
if str(TRIAGE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TRIAGE_SCRIPTS))

try:
    import inbound  # type: ignore
except ImportError:  # the sibling skill was not installed alongside this one
    inbound = None

PLACEHOLDERS = (
    r"\[[^\]\n]{1,40}\]",
    r"«[^»\n]{1,60}»",
    r"\{\{[^}\n]*\}\}",
    r"<(?:insert|name|company|role|date|time|your)[^>\n]{0,30}>",
    r"\b(?:TODO|TBD|XXX)\b",
    r"\blorem ipsum\b",
    r"\binsert (?:your|the|a|an)\b",
)

COMMITMENTS = (
    r"\bi (?:hereby )?accept\b",
    r"\bhappy to accept\b",
    r"\bi(?:'ll| will) sign\b",
    r"\bagree to (?:the|your) (?:offer|terms|contract)\b",
    r"\bi resign\b|\bmy resignation\b|\bhanded in my notice\b",
    r"\bnehme (?:das|ihr|dein) angebot an\b",
    r"\bich sage (?:hiermit )?zu\b",
    r"\bk(?:ü|ue)ndige (?:hiermit|meine stelle)\b",
)

TEMPLATE_TELLS = (
    "i hope this message finds you well", "i hope you are doing well", "i hope you're doing well",
    "i am writing to", "i'm writing to", "delve", "thrilled", "i am excited to", "i'm excited to",
    "passionate about", "dear hiring manager", "to whom it may concern", "synergy", "leverage my",
    "ich hoffe, es geht ihnen gut", "sehr geehrte damen und herren",
)

ATTACHMENT = r"\b(attached|attachment|please find|anbei|im anhang)\b"
EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
URL = r"\b(?:https?://|www\.)[^\s<>()]+"
PHONE = r"(?<![\w+])(?:\+|00|0)\d[\d\s\-/().]{6,}\d"
TIME_SLOT = (r"\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b|\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\b\d{1,2}:\d{2}\b"
             r"|\b(montag|dienstag|mittwoch|donnerstag|freitag)\b|\b\d{1,2}(\.|:)\d{2} uhr\b")

LIMITS = {"linkedin": None, "gmail": 1500, "other": None}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _phones(text: str) -> List[str]:
    found = []
    for match in re.finditer(PHONE, text):
        raw = match.group(0)
        # A phone number has a long unbroken run of digits; a date such as
        # 09/30/2026 does not, which is what keeps dates out of this list.
        if re.search(r"\d{6,}", raw) or raw.startswith(("+", "00")):
            if len(_digits(raw)) >= 9:
                found.append(raw.strip())
    return found


def _allowed_figures(settings: Dict[str, Any]) -> List[int]:
    said = " ".join([
        str((settings.get("salary") or {}).get("say") or ""),
        str((settings.get("day_rate") or {}).get("say") or ""),
    ])
    return inbound.money_figures(said)


def _normalise_link(link: str) -> str:
    return re.sub(r"^(https?://)?(www\.)?", "", link.strip().lower()).rstrip("/.,;")


def check(draft: str, profile: Dict[str, Any], inbound_text: Optional[str] = None,
          intent: Optional[str] = None, channel: str = "linkedin") -> Dict[str, Any]:
    settings = inbound.replies_settings(profile)
    lower = draft.lower()
    blocked: List[str] = []
    review: List[str] = []

    for pattern in PLACEHOLDERS:
        match = re.search(pattern, draft, re.I)
        if match:
            blocked.append("unfilled placeholder %r" % match.group(0))
            break

    figures = inbound.money_figures(draft)
    disclose = str((settings.get("salary") or {}).get("disclose") or "on-request")
    if figures:
        if disclose == "never":
            blocked.append("names a money figure (%s) and the profile says never to" % inbound.money_spans(draft)[0])
        else:
            allowed = set(_allowed_figures(settings))
            stray = [f for f in figures if f not in allowed]
            if stray:
                blocked.append(
                    "names %s, which is not in salary.say or day_rate.say -- only the user sets a number"
                    % ", ".join(str(f) for f in stray)
                )
            elif disclose == "on-request" and inbound_text is not None and \
                    "salary" not in inbound.detect_asks(inbound_text.lower()):
                review.append("states a figure the sender did not ask for")

    shareable = settings.get("shareable") or {}
    allowed_email = str(shareable.get("email") or "").lower()
    for address in re.findall(EMAIL, draft):
        if address.lower() != allowed_email:
            blocked.append("contains the email address %s, which is not in shareable.email" % address)
    allowed_phone = _digits(str(shareable.get("phone") or ""))
    for phone in _phones(draft):
        if not allowed_phone or _digits(phone)[-9:] != allowed_phone[-9:]:
            blocked.append("contains the phone number %s, which is not in shareable.phone" % phone)
    allowed_links = [_normalise_link(str(link)) for link in (shareable.get("links") or [])]
    for link in re.findall(URL, draft):
        clean = _normalise_link(link)
        if not any(clean == a or clean.startswith(a.rstrip("/") + "/") for a in allowed_links if a):
            blocked.append("contains the link %s, which is not in shareable.links" % link.rstrip(".,;"))

    for pattern in COMMITMENTS:
        match = re.search(pattern, lower)
        if match:
            blocked.append("commits to something only the user can: %r" % match.group(0))
            break

    for term in settings.get("never_mention") or []:
        if str(term).strip() and str(term).lower() in lower:
            blocked.append("mentions %r, which is in never_mention" % term)

    limit = settings.get("max_chars") if channel == "linkedin" else LIMITS.get(channel)
    if isinstance(limit, int) and limit > 0 and len(draft) > limit:
        review.append("%d characters, over the %d limit for %s" % (len(draft), limit, channel))

    proposes_time = re.search(TIME_SLOT, lower) is not None
    if intent in ("engage", "qualify") and "?" not in draft and not proposes_time:
        review.append("asks nothing and proposes no time -- the thread stalls here")
    if proposes_time and not settings.get("availability"):
        review.append("offers times, but no availability is declared in the profile")
    if intent in ("ignore", "personal"):
        review.append("triage said %s -- a reply was not expected" % intent)

    if inbound_text:
        theirs = inbound.detect_language(inbound_text)
        ours = inbound.detect_language(draft)
        languages = [str(code).lower() for code in (settings.get("languages") or [])]
        if theirs != "unknown" and ours != "unknown" and theirs != ours and theirs in languages:
            review.append("they wrote in %s and the draft is in %s" % (theirs, ours))

    if re.search(ATTACHMENT, lower):
        review.append("mentions an attachment -- attach it by hand, or send a link from shareable.links")
    tells = [t for t in TEMPLATE_TELLS if t in lower]
    if draft.count("—") > 2:
        tells.append("%d em dashes" % draft.count("—"))
    if tells:
        review.append("reads like a template: %s" % ", ".join(tells[:3]))

    verdict = "blocked" if blocked else ("review" if review else "clean")
    return {
        "verdict": verdict,
        "blocked": blocked,
        "review": review,
        "stats": {"chars": len(draft), "language": inbound.detect_language(draft),
                  "money_figures": figures, "channel": channel},
    }


EXIT = {"clean": 0, "blocked": 1, "review": 3}


def render(report: Dict[str, Any]) -> str:
    lines = ["Draft: %s  (%d chars, %s)" % (report["verdict"].upper(), report["stats"]["chars"],
                                           report["stats"]["language"])]
    lines += ["  BLOCKED  %s" % item for item in report["blocked"]]
    lines += ["  review   %s" % item for item in report["review"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("draft", help="draft file, or - for stdin")
    parser.add_argument("--inbound", help="the message being answered, for language and ask checks")
    parser.add_argument("--intent", choices=["engage", "qualify", "decline", "ignore", "personal"])
    parser.add_argument("--channel", default="linkedin", choices=sorted(LIMITS))
    parser.add_argument("--profile", help="profile JSON (default .jobhunt/profile.json)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if inbound is None:
        sys.stderr.write("the inbound-triage skill is missing; install the plugin whole\n")
        return 2
    try:
        profile = inbound.load_profile(args.profile)
        draft = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
        inbound_text = Path(args.inbound).read_text(encoding="utf-8") if args.inbound else None
    except (inbound.ProfileError, OSError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    if not draft.strip():
        sys.stderr.write("the draft is empty\n")
        return 2

    report = check(draft, profile, inbound_text, args.intent, args.channel)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return EXIT[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
