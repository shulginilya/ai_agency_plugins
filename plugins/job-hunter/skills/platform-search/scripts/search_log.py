#!/usr/bin/env python3
"""Plan, filter and record a job search on one freelance platform.

The model does the searching — through a connector, a browser or alert emails —
and this script owns the parts that must not depend on judgement: what to search
for, which results are already known, which fall under the rate floor, which are
the same posting twice, and what gets written down afterwards.

    python search_log.py plan upwork                 # queries, filters, limit, mode
    python search_log.py filter upwork found.json    # drop seen / below floor / dupes
    python search_log.py record upwork filtered.json # mark seen, write the run report
    python search_log.py seen upwork                 # what is already known

A posting is a JSON object; only "id" and "title" are required:

    {"id": "2101475603967995100", "title": "AI Developer", "url": "https://...",
     "client": "1013755849", "rate": {"min": 40, "max": 75, "currency": "USD",
     "per": "hour"}, "hours": "~8 h/wk", "proposals": "15 to 20", "posted":
     "2026-09-20", "applied": false, "summary": "...", "verdict": "pursue",
     "note": "best fit"}

Exit codes (filter): 0 new postings survived, 1 nothing survived, 2 unusable
input (no profile, malformed JSON, unknown platform). plan/record/seen exit 0 or 2.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROFILE_PATH = Path(".jobhunt/profile.json")
SEARCH_DIR = Path(".jobhunt/searches")
SEEN_FILE = "seen.json"

PLATFORMS = ("upwork", "arc", "contra")
DEFAULT_LIMIT = 10

# A role search returns noise when it is a single technology word; these are the
# role words a title search is built from when the profile does not say.
ROLE_WORDS = ("full stack", "frontend", "AI engineer", "React", "Node", "Next.js")


class Unusable(Exception):
    """Input the script cannot work with; exit 2."""


# ---------------------------------------------------------------- profile


def load_profile(path: Path = PROFILE_PATH) -> Dict[str, Any]:
    if not path.is_file():
        raise Unusable(
            "no profile at %s — create it first (opportunity-triage: fit.py --init)" % path
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Unusable("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise Unusable("%s must contain a JSON object" % path)
    return data


def check_platform(name: str) -> str:
    platform = name.strip().lower()
    if platform not in PLATFORMS:
        raise Unusable("unknown platform %r; known: %s" % (name, ", ".join(PLATFORMS)))
    return platform


def search_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    search = profile.get("search") or {}
    mode = str(search.get("mode") or "draft").lower()
    if mode not in ("draft", "submit"):
        raise Unusable("profile search.mode must be 'draft' or 'submit', not %r" % mode)
    limit = int(search.get("results_per_run") or DEFAULT_LIMIT)
    if limit < 1:
        raise Unusable("profile search.results_per_run must be at least 1")
    return {
        "platforms": [str(p).lower() for p in (search.get("platforms") or PLATFORMS)],
        "limit": limit,
        "mode": mode,
    }


def rate_floor(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    floor = profile.get("rate_floor") or {}
    amount = floor.get("amount")
    if not amount:
        return None
    return {
        "amount": float(amount),
        "currency": str(floor.get("currency") or "").upper() or None,
        "per": str(floor.get("per") or "hour").lower(),
    }


# ---------------------------------------------------------------- plan


def build_plan(platform: str, profile: Dict[str, Any], query: Optional[str]) -> Dict[str, Any]:
    settings = search_settings(profile)
    titles = [str(t) for t in (profile.get("titles") or [])]
    stack = [str(t) for t in (profile.get("must_have") or []) + (profile.get("nice_to_have") or [])]
    if query:
        queries = [query]
    else:
        # Titles minus the seniority word: "Senior Frontend Engineer" -> "Frontend Engineer".
        # Platforms title-match on every word, so short role phrases beat full titles.
        queries = []
        for title in titles:
            words = [w for w in title.split() if w.lower() not in ("senior", "lead", "principal", "staff")]
            phrase = " ".join(words[-2:]) if len(words) > 2 else " ".join(words)
            variants = [phrase]
            # Clients write "Developer" at least as often as "Engineer".
            for a, b in (("Engineer", "Developer"), ("Developer", "Engineer")):
                if phrase.endswith(a):
                    variants.append(phrase[: -len(a)] + b)
            for variant in variants:
                if variant and variant not in queries:
                    queries.append(variant)
        if not queries:
            queries = list(ROLE_WORDS)
    availability = profile.get("availability") or {}
    return {
        "platform": platform,
        "enabled_in_profile": platform in settings["platforms"],
        "queries": queries,
        "stack": stack,
        "rate_floor": rate_floor(profile),
        "rate_target": profile.get("rate_target"),
        "billing": availability.get("preferred_billing"),
        "max_hours_per_week": availability.get("max_hours_per_week"),
        "deal_breakers": profile.get("deal_breakers") or [],
        "limit": settings["limit"],
        "mode": settings["mode"],
        "seen": len(load_seen().get(platform, {})),
    }


# ---------------------------------------------------------------- seen store


def seen_path() -> Path:
    return SEARCH_DIR / SEEN_FILE


def load_seen() -> Dict[str, Dict[str, Any]]:
    path = seen_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Unusable("%s is not valid JSON (%s); fix or move it — refusing to overwrite" % (path, exc))
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise Unusable("%s is not a seen-postings file; refusing to overwrite" % path)
    return data


def save_seen(data: Dict[str, Dict[str, Any]]) -> None:
    path = seen_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copyfile(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- postings


def read_postings(source: str) -> List[Dict[str, Any]]:
    raw = sys.stdin.read() if source == "-" else _read_file(source)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise Unusable("postings are not valid JSON: %s" % exc)
    if isinstance(data, dict):
        # The output of `filter` can be fed straight back to `record`.
        data = list(data.get("kept") or []) + list(data.get("dropped") or [])
    if not isinstance(data, list):
        raise Unusable("postings must be a JSON list of objects")
    postings = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or not str(item.get("id") or "").strip() or not str(item.get("title") or "").strip():
            raise Unusable("posting %d needs at least an 'id' and a 'title'" % index)
        posting = dict(item)
        posting["id"] = str(posting["id"]).strip()
        postings.append(posting)
    return postings


def _read_file(source: str) -> str:
    path = Path(source)
    if not path.is_file():
        raise Unusable("no such file: %s" % source)
    return path.read_text(encoding="utf-8")


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def rate_check(posting: Dict[str, Any], floor: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """(keep, flag). Drops only when the posted maximum is known and under the floor."""
    rate = posting.get("rate") or {}
    per = str(rate.get("per") or "hour").lower()
    low, high = _number(rate.get("min")), _number(rate.get("max"))
    if per not in ("hour", "hourly"):
        return True, "fixed-price — compare the budget to the hours it implies"
    if low is None and high is None:
        return True, "no rate stated"
    if floor is None:
        return True, None
    currency = str(rate.get("currency") or "").upper() or None
    if floor["currency"] and currency and currency != floor["currency"]:
        return True, "rate in %s, floor in %s — not converted" % (currency, floor["currency"])
    if high is not None and high < floor["amount"]:
        return False, "below floor: tops out at %g/h, floor %g/h" % (high, floor["amount"])
    if high is None:
        return True, "no maximum stated"
    if high < floor["amount"] * 1.15:
        return True, "barely above floor: tops out at %g/h" % high
    return True, None


def filter_postings(
    platform: str, postings: List[Dict[str, Any]], profile: Dict[str, Any]
) -> Dict[str, Any]:
    floor = rate_floor(profile)
    breakers = [str(b).lower() for b in (profile.get("deal_breakers") or []) if str(b).strip()]
    known = load_seen().get(platform, {})
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    first_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    ids_this_run = set()

    for posting in postings:
        flags = list(posting.get("flags") or [])
        reason = None
        if posting["id"] in ids_this_run:
            reason = "duplicate id in this run"
        elif posting["id"] in known:
            reason = "already seen on %s" % known[posting["id"]].get("first_seen", "an earlier run")
        elif posting.get("applied") is True:
            reason = "already applied"
        else:
            text = (str(posting.get("title") or "") + " " + str(posting.get("summary") or "")).lower()
            hit = [b for b in breakers if b in text]
            if hit:
                reason = "deal-breaker: %s" % ", ".join(hit)
        if reason is None:
            keep, flag = rate_check(posting, floor)
            if not keep:
                reason = flag
            elif flag:
                flags.append(flag)
        if reason is None and posting.get("client"):
            key = (str(posting["client"]), _norm_title(str(posting["title"])))
            original = first_by_key.get(key)
            if original is not None:
                original["duplicates"] = original.get("duplicates", 0) + 1
                reason = "same client re-posted the same job (%s)" % original["id"]
            else:
                first_by_key[key] = posting
        ids_this_run.add(posting["id"])
        if reason is None:
            posting["flags"] = flags
            kept.append(posting)
        else:
            dropped.append(dict(posting, verdict="filtered", note=reason))

    for posting in kept:
        if posting.get("duplicates"):
            posting["flags"].append(
                "client posted this %d more time(s) — check it is a real opening" % posting["duplicates"]
            )
    return {
        "platform": platform,
        "kept": kept,
        "dropped": dropped,
        "limit": search_settings(profile)["limit"],
    }


# ---------------------------------------------------------------- record


def _rate_text(posting: Dict[str, Any]) -> str:
    rate = posting.get("rate") or {}
    low, high = _number(rate.get("min")), _number(rate.get("max"))
    per = str(rate.get("per") or "hour").lower()
    unit = "/h" if per in ("hour", "hourly") else " fixed"
    cur = str(rate.get("currency") or "")
    if low is None and high is None:
        return "—"
    if low is not None and high is not None:
        return "%s%g–%g%s" % (cur + " " if cur else "", low, high, unit)
    return "%s%g%s%s" % (cur + " " if cur else "", low if low is not None else high, "+" if high is None else " max", unit)


def _cell(value: Any) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "/").replace("\n", " ").strip()


def render_report(platform: str, date: dt.date, postings: List[Dict[str, Any]]) -> str:
    reported = [p for p in postings if p.get("verdict") != "filtered"]
    filtered = [p for p in postings if p.get("verdict") == "filtered"]
    lines = [
        "# %s search — %s" % (platform.capitalize(), date.isoformat()),
        "",
        "%d reported, %d filtered out." % (len(reported), len(filtered)),
        "",
        "| # | Verdict | Job | Rate | Load | Proposals | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for number, posting in enumerate(reported, 1):
        title = _cell(posting.get("title"))
        job = "[%s](%s)" % (title, posting["url"]) if posting.get("url") else title
        note = "; ".join([str(posting.get("note") or "")] + [str(f) for f in posting.get("flags") or []]).strip("; ")
        lines.append(
            "| %d | %s | %s | %s | %s | %s | %s |"
            % (
                number,
                _cell(str(posting.get("verdict") or "unscreened").upper()),
                job,
                _rate_text(posting),
                _cell(posting.get("hours")),
                _cell(posting.get("proposals")),
                _cell(note),
            )
        )
    if filtered:
        lines += ["", "## Filtered out", ""]
        for posting in filtered:
            lines.append("- %s — %s" % (_cell(posting.get("title")), _cell(posting.get("note"))))
    return "\n".join(lines) + "\n"


def record(platform: str, postings: List[Dict[str, Any]], date: dt.date) -> Dict[str, Any]:
    seen = load_seen()
    bucket = seen.setdefault(platform, {})
    added = 0
    for posting in postings:
        if posting["id"] in bucket:
            continue
        bucket[posting["id"]] = {
            "first_seen": date.isoformat(),
            "title": str(posting.get("title")),
            "verdict": str(posting.get("verdict") or "unscreened"),
            "url": posting.get("url"),
        }
        added += 1
    save_seen(seen)
    report = SEARCH_DIR / ("%s-%s.md" % (date.isoformat(), platform))
    body = render_report(platform, date, postings)
    if report.is_file():
        # A second run on the same day appends rather than replacing the first.
        body = report.read_text(encoding="utf-8").rstrip("\n") + "\n\n---\n\n" + body
    report.write_text(body, encoding="utf-8")
    return {"report": str(report), "newly_seen": added, "total_seen": len(bucket)}


# ---------------------------------------------------------------- cli


def parse_date(value: Optional[str]) -> dt.date:
    if not value:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise Unusable("dates are YYYY-MM-DD, not %r" % value)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="what to search for on a platform")
    p_plan.add_argument("platform")
    p_plan.add_argument("--query", help="search this instead of the profile's titles")

    p_filter = sub.add_parser("filter", help="drop seen, below-floor, duplicate and deal-breaker postings")
    p_filter.add_argument("platform")
    p_filter.add_argument("postings", help="JSON file of postings, or - for stdin")

    p_record = sub.add_parser("record", help="mark postings seen and write the run report")
    p_record.add_argument("platform")
    p_record.add_argument("postings", help="JSON file (a list, or the output of filter), or - for stdin")
    p_record.add_argument("--date", help="YYYY-MM-DD; default today")

    p_seen = sub.add_parser("seen", help="list postings already seen on a platform")
    p_seen.add_argument("platform")

    args = parser.parse_args(argv)
    try:
        platform = check_platform(args.platform)
        if args.command == "plan":
            print(json.dumps(build_plan(platform, load_profile(), args.query), indent=2))
            return 0
        if args.command == "filter":
            result = filter_postings(platform, read_postings(args.postings), load_profile())
            print(json.dumps(result, indent=2))
            return 0 if result["kept"] else 1
        if args.command == "record":
            print(json.dumps(record(platform, read_postings(args.postings), parse_date(args.date)), indent=2))
            return 0
        if args.command == "seen":
            print(json.dumps(load_seen().get(platform, {}), indent=2, sort_keys=True))
            return 0
    except Unusable as exc:
        sys.stderr.write("search_log: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
