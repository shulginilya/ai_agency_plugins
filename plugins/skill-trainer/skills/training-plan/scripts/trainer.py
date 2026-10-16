#!/usr/bin/env python3
"""Skill training next to a full-time job: daily and weekly plans, spaced review, an interview track.

    trainer.py where                                  the training folder in use, and why
    trainer.py set-home PATH                          remember the training folder (Windows paths are fine)
    trainer.py init [--stack S] [--interview-language L] [--cadence daily|weekly] [--focus F] ...
    trainer.py config show [--json]
    trainer.py config set KEY VALUE                   stack, interview-language, cadence, focus, daily-minutes,
                                                      weekly-sessions, session-minutes, goals, weak-areas,
                                                      interview-date
    trainer.py plan [--write] [--json]                both plans: the daily rotation and the weekly sessions
    trainer.py today [--date D] [--cadence C] [--json]  the session to do now, reviews first
    trainer.py log --topic ID --score 1-5 [--minutes M] [--notes T] [--kind practice|mock] [--date D]
    trainer.py topics [--area A] [--track skills|interview] [--json]
    trainer.py add-topic --area A --title T [--id ID] [--hint H ...]
    trainer.py interview [--json]                     coding-pattern and system-design progress
    trainer.py status [--date D] [--json]             streaks, coverage, what is due

Where the training lives, first match wins: --home, then $SKILL_TRAINER_HOME, then the
folder saved by `set-home` (in $XDG_CONFIG_HOME/ai-agency/skill-trainer.json, by default
~/.config/ai-agency/skill-trainer.json), then ~/.config/ai-agency/skill-trainer/.
The folder holds state.json (owned by this script) and plan.md (rendered from it).

Scores: 1 could not do it, 2 needed major help, 3 done but slow or with hints,
4 solid in time, 5 fast and clean enough to teach. A score of 1-2 brings the topic
back the next day; a 5 pushes it out by days or weeks.

Standard library only. Exit status: 0 done or nothing due, 1 something is due,
2 bad input or unusable state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG = Path(__file__).resolve().parent.parent / "references" / "catalog.json"
KIND = "skill-trainer"
AREAS = ("coding", "design", "deep-dive", "practices", "build")
TRACKS = {"skills": AREAS, "interview": ("coding", "design")}
FOCUSES = ("skills", "interview", "mixed")
CADENCES = ("daily", "weekly")
DEFAULTS: Dict[str, Any] = {
    "stack": ["React", "TypeScript", "Node", "Python"],
    "interview_language": "Node",
    "cadence": "daily",
    "focus": "mixed",
    "daily_minutes": 40,
    "weekly_sessions": 3,
    "session_minutes": 75,
    "goals": [],
    "weak_areas": [],
    "interview_date": None,
}
# One slot per weekday, Monday first. "review" is due items only; "mock" is a full graded round.
DAILY = {
    "skills": ["coding", "deep-dive", "design", "practices", "deep-dive", "build", "review"],
    "interview": ["coding", "design", "coding", "design", "coding", "mock", "review"],
    "mixed": ["coding", "design", "deep-dive", "coding", "practices", "build", "review"],
}
WEEKLY = {
    "skills": [["coding", "deep-dive"], ["design", "practices"], ["build"], ["review", "deep-dive"]],
    "interview": [["coding", "coding"], ["design"], ["mock"], ["coding", "review"]],
    "mixed": [["coding", "design"], ["deep-dive", "practices"], ["build"], ["mock", "review"]],
}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
STACK_ALIASES = {
    "node.js": "node", "nodejs": "node", "ts": "typescript", "js": "javascript",
    "py": "python", "reactjs": "react", "react.js": "react", "golang": "go", "c#": "csharp",
}
LANGUAGES = {
    "node": "JavaScript (Node)", "javascript": "JavaScript", "typescript": "TypeScript",
    "python": "Python", "go": "Go", "java": "Java", "kotlin": "Kotlin", "rust": "Rust",
    "csharp": "C#", "c++": "C++", "ruby": "Ruby", "swift": "Swift", "php": "PHP", "scala": "Scala",
}
GENERATED = (
    ("internals", "{name}: internals and runtime model", 1),
    ("idioms", "{name}: idioms and common pitfalls", 1),
    ("testing", "{name}: testing and tooling", 2),
    ("performance", "{name}: performance and profiling", 3),
)
MAX_INTERVAL = 60
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TrainerError(Exception):
    exit_code = 2


# --- where the training lives ------------------------------------------------


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ai-agency" / "skill-trainer.json"


def normalize_path(text: str) -> Path:
    """Accept a Windows path like C:\\Users\\me\\training and map it to /mnt/c/... under WSL."""
    text = text.strip().strip('"')
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
    if match and os.name != "nt":
        mount = Path("/mnt") / match.group(1).lower()
        if mount.is_dir():
            return mount / match.group(2).replace("\\", "/")
    return Path(os.path.expanduser(text))


def resolve_home(flag: Optional[str]) -> Tuple[Path, str]:
    if flag:
        return normalize_path(flag), "--home"
    if os.environ.get("SKILL_TRAINER_HOME"):
        return normalize_path(os.environ["SKILL_TRAINER_HOME"]), "$SKILL_TRAINER_HOME"
    cfg = config_path()
    if cfg.is_file():
        try:
            saved = json.loads(cfg.read_text(encoding="utf-8")).get("home")
        except ValueError:
            raise TrainerError("%s is not valid JSON; run `trainer.py set-home PATH` again" % cfg)
        if saved:
            return normalize_path(saved), str(cfg)
    return config_path().parent / "skill-trainer", "default"


def state_path(home: Path) -> Path:
    return home / "state.json"


# --- dates -------------------------------------------------------------------


def parse_date(text: Optional[str]) -> dt.date:
    if not text:
        return dt.date.today()
    if not ISO_RE.match(text):
        raise TrainerError("dates are ISO YYYY-MM-DD, not %r" % text)
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise TrainerError("%r is not a real date" % text)


def week_key(day: dt.date) -> Tuple[int, int]:
    iso = day.isocalendar()
    return iso[0], iso[1]


# --- state -------------------------------------------------------------------


def new_state(settings: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULTS)
    merged.update(settings)
    return {"kind": KIND, "version": 1, "settings": merged, "progress": {}, "sessions": [],
            "custom_topics": []}


def read_state(home: Path) -> Dict[str, Any]:
    path = state_path(home)
    if not path.is_file():
        raise TrainerError("no training set up in %s. Run `trainer.py init` first (or /skill-trainer:plan)" % home)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TrainerError("%s is not valid JSON (%s)" % (path, exc))
    if not isinstance(state, dict) or state.get("kind") != KIND:
        raise TrainerError("%s is not a skill-trainer state file; refusing to touch it" % path)
    settings = dict(DEFAULTS)
    settings.update(state.get("settings") or {})
    state["settings"] = settings
    for key, empty in (("progress", {}), ("sessions", []), ("custom_topics", [])):
        state.setdefault(key, empty)
    return state


def write_state(home: Path, state: Dict[str, Any]) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = state_path(home)
    if path.is_file():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


# --- settings ----------------------------------------------------------------


def split_list(text: str, sep: str = ",") -> List[str]:
    return [part.strip() for part in text.split(sep) if part.strip()]


def stack_key(name: str) -> str:
    key = name.strip().lower()
    return STACK_ALIASES.get(key, key)


def set_setting(settings: Dict[str, Any], key: str, value: str) -> str:
    """Apply one `config set`; returns the canonical key. History is never touched."""
    key = key.strip().lower().replace("_", "-")
    if key == "stack":
        items = split_list(value)
        if not items:
            raise TrainerError("stack needs at least one entry, e.g. \"React,TypeScript,Node,Python\"")
        settings["stack"] = items
    elif key in ("interview-language", "language"):
        if not value.strip():
            raise TrainerError("interview-language needs a value, e.g. Node, Python or TypeScript")
        settings["interview_language"] = value.strip()
        key = "interview-language"
    elif key == "cadence":
        if value not in CADENCES:
            raise TrainerError("cadence is one of %s" % ", ".join(CADENCES))
        settings["cadence"] = value
    elif key == "focus":
        if value not in FOCUSES:
            raise TrainerError("focus is one of %s" % ", ".join(FOCUSES))
        settings["focus"] = value
    elif key in ("daily-minutes", "session-minutes", "weekly-sessions"):
        try:
            number = int(value)
        except ValueError:
            raise TrainerError("%s takes a whole number" % key)
        low, high = (1, 4) if key == "weekly-sessions" else (10, 240)
        if not low <= number <= high:
            raise TrainerError("%s must be between %d and %d" % (key, low, high))
        settings[key.replace("-", "_")] = number
    elif key == "goals":
        settings["goals"] = split_list(value, ";")
    elif key == "weak-areas":
        settings["weak_areas"] = split_list(value)
    elif key == "interview-date":
        settings["interview_date"] = None if value.lower() in ("", "none", "-") else parse_date(value).isoformat()
    else:
        raise TrainerError("unknown setting %r. Settings: stack, interview-language, cadence, focus, "
                           "daily-minutes, weekly-sessions, session-minutes, goals, weak-areas, "
                           "interview-date" % key)
    return key


def coding_language(settings: Dict[str, Any], day: dt.date) -> str:
    """Interview and mixed focus practise in the interview language; skills focus rotates the stack's languages."""
    if settings["focus"] in ("interview", "mixed"):
        return settings["interview_language"]
    langs = [LANGUAGES[stack_key(s)] for s in settings["stack"] if stack_key(s) in LANGUAGES]
    return langs[day.toordinal() % len(langs)] if langs else settings["interview_language"]


# --- topics ------------------------------------------------------------------


def load_catalog() -> Dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog.get("kind") != "skill-trainer-catalog":
        raise TrainerError("%s is not a skill-trainer catalog" % CATALOG)
    return catalog


def all_topics(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The catalog, plus generated deep-dives for stack entries the catalog does not cover, plus custom topics."""
    topics = [dict(t, origin="catalog") for t in load_catalog()["topics"]]
    covered = {s for t in topics for s in t.get("stack", [])}
    for name in state["settings"]["stack"]:
        key = stack_key(name)
        if key in covered:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-") or "stack"
        for suffix, title, level in GENERATED:
            topics.append({"id": "%s-%s" % (slug, suffix), "area": "deep-dive", "level": level,
                           "stack": [key], "title": title.format(name=name.strip()), "hints": [],
                           "origin": "generated"})
        covered.add(key)
    topics += [dict(t, origin="custom") for t in state["custom_topics"]]
    return topics


def active_topics(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Topics that apply to the current stack. Topics for a dropped stack keep their history but stop coming up."""
    stack = {stack_key(s) for s in state["settings"]["stack"]}
    return [t for t in all_topics(state) if not t.get("stack") or stack & set(t["stack"])]


def topic_by_id(state: Dict[str, Any], topic_id: str) -> Dict[str, Any]:
    for topic in all_topics(state):
        if topic["id"] == topic_id:
            return topic
    raise TrainerError("no topic %r. Run `trainer.py topics` for the ids" % topic_id)


# --- scheduling --------------------------------------------------------------


def next_interval(progress: Optional[Dict[str, Any]], score: int) -> int:
    """A light SM-2: weak results return tomorrow, strong ones space out."""
    reps = progress.get("reps", 0) if progress else 0
    interval = progress.get("interval", 0) if progress else 0
    if score <= 2:
        return 1
    if reps == 0:
        return {3: 2, 4: 4, 5: 7}[score]
    factor = {3: 1.4, 4: 2.2, 5: 3.0}[score]
    return min(MAX_INTERVAL, max(interval + 1, int(round(interval * factor))))


def record(state: Dict[str, Any], topic_id: str, score: int, day: dt.date, minutes: Optional[int],
           notes: str, kind: str) -> Dict[str, Any]:
    if not 1 <= score <= 5:
        raise TrainerError("score is 1-5 (1 could not do it, 3 done but slow, 5 could teach it)")
    topic = topic_by_id(state, topic_id)
    old = state["progress"].get(topic_id)
    interval = next_interval(old, score)
    progress = {
        "reps": 0 if score <= 2 else (old or {}).get("reps", 0) + 1,
        "interval": interval,
        "due": (day + dt.timedelta(days=interval)).isoformat(),
        "last_score": score,
        "last_date": day.isoformat(),
        "seen": (old or {}).get("seen", 0) + 1,
    }
    state["progress"][topic_id] = progress
    session = {"date": day.isoformat(), "topic": topic_id, "area": topic["area"], "score": score,
               "kind": kind, "cadence": state["settings"]["cadence"]}
    if minutes:
        session["minutes"] = minutes
    if notes:
        session["notes"] = notes
    state["sessions"].append(session)
    return progress


def due_topics(state: Dict[str, Any], day: dt.date, areas: Optional[Tuple[str, ...]] = None) -> List[Dict[str, Any]]:
    out = []
    for topic in active_topics(state):
        prog = state["progress"].get(topic["id"])
        if prog and dt.date.fromisoformat(prog["due"]) <= day and (areas is None or topic["area"] in areas):
            out.append(dict(topic, progress=prog, overdue=(day - dt.date.fromisoformat(prog["due"])).days))
    out.sort(key=lambda t: (-t["overdue"], t["progress"]["last_score"], t["id"]))
    return out


def new_topics(state: Dict[str, Any], area: str) -> List[Dict[str, Any]]:
    weak = {w.lower() for w in state["settings"]["weak_areas"]}
    stack = [stack_key(s) for s in state["settings"]["stack"]]

    def rank(item: Tuple[int, Dict[str, Any]]) -> Tuple[int, int, int]:
        index, topic = item
        is_weak = topic["area"] in weak or topic["id"] in weak or bool(weak & set(topic.get("stack", [])))
        return (0 if is_weak else 1, topic.get("level", 2), index)

    fresh = [(i, t) for i, t in enumerate(active_topics(state))
             if t["area"] == area and t["id"] not in state["progress"]]
    ordered = [t for _, t in sorted(fresh, key=rank)]
    if area == "deep-dive" and stack:
        # Spread deep-dives across the stack instead of finishing one technology first.
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for topic in ordered:
            buckets.setdefault((topic.get("stack") or ["any"])[0], []).append(topic)
        rotated: List[Dict[str, Any]] = []
        while any(buckets.values()):
            for key in list(buckets):
                if buckets[key]:
                    rotated.append(buckets[key].pop(0))
        is_weak = [t for t in rotated if rank((0, t))[0] == 0]
        ordered = is_weak + [t for t in rotated if t not in is_weak]
    return ordered


def pick(state: Dict[str, Any], slot: str, day: dt.date, taken: List[str]) -> Optional[Dict[str, Any]]:
    """One topic for a slot: a due review in that area first, then the next new topic, then the weakest seen."""
    focus_areas = TRACKS["interview"] if state["settings"]["focus"] == "interview" else AREAS
    if slot == "review":
        due = [t for t in due_topics(state, day, focus_areas) if t["id"] not in taken]
        if due:
            return dict(due[0], why="review: due %s, last score %d" % (due[0]["progress"]["due"],
                                                                      due[0]["progress"]["last_score"]))
        return weakest(state, focus_areas, taken)
    if slot == "mock":
        area = "design" if day.isocalendar()[1] % 2 else "coding"
        choice = pick(state, area, day, taken)
        return dict(choice, kind="mock", why="full mock round, graded") if choice else None
    due = [t for t in due_topics(state, day, (slot,)) if t["id"] not in taken]
    if due:
        return dict(due[0], why="review: due %s, last score %d" % (due[0]["progress"]["due"],
                                                                  due[0]["progress"]["last_score"]))
    fresh = [t for t in new_topics(state, slot) if t["id"] not in taken]
    if fresh:
        return dict(fresh[0], why="new")
    return weakest(state, (slot,), taken)


def weakest(state: Dict[str, Any], areas: Tuple[str, ...], taken: List[str]) -> Optional[Dict[str, Any]]:
    seen = [dict(t, progress=state["progress"][t["id"]]) for t in active_topics(state)
            if t["id"] in state["progress"] and t["area"] in areas and t["id"] not in taken]
    if not seen:
        return None
    seen.sort(key=lambda t: (t["progress"]["last_score"], t["progress"]["last_date"]))
    return dict(seen[0], why="weakest so far (last score %d)" % seen[0]["progress"]["last_score"])


def weekly_index(state: Dict[str, Any], day: dt.date) -> int:
    days = {s["date"] for s in state["sessions"]
            if week_key(dt.date.fromisoformat(s["date"])) == week_key(day) and s["date"] < day.isoformat()}
    return len(days)


def session_for(state: Dict[str, Any], day: dt.date, cadence: Optional[str] = None) -> Dict[str, Any]:
    settings = state["settings"]
    cadence = cadence or settings["cadence"]
    focus = settings["focus"]
    if cadence == "daily":
        minutes = settings["daily_minutes"]
        slots = [DAILY[focus][day.weekday()]]
        if minutes > 30 and slots[0] not in ("review", "mock", "build"):
            slots.insert(0, "review")  # a short review warms up a longer block
        label = "%s daily session" % WEEKDAYS[day.weekday()]
    else:
        minutes = settings["session_minutes"]
        index = weekly_index(state, day)
        plan = WEEKLY[focus][:settings["weekly_sessions"]]
        slots = list(plan[index]) if index < len(plan) else ["review"]
        label = ("weekly session %d of %d" % (index + 1, len(plan)) if index < len(plan)
                 else "bonus session (this week's %d are done)" % len(plan))
    items: List[Dict[str, Any]] = []
    for slot in slots:
        choice = pick(state, slot, day, [i["id"] for i in items])
        if choice is None:
            continue
        if slot == "review" and choice.get("why", "").startswith("weakest") and len(slots) > 1:
            continue  # nothing is due; spend the time on the main slot
        items.append(choice)
    for item in items:
        item.setdefault("kind", "practice")
        item["minutes"] = max(10, minutes // max(1, len(items)))
        if item["area"] == "coding":
            item["language"] = coding_language(settings, day)
        item.pop("origin", None)
    done = [x["topic"] for x in state["sessions"] if x["date"] == day.isoformat()]
    return {"date": day.isoformat(), "cadence": cadence, "focus": focus, "label": label,
            "minutes": minutes, "items": items, "logged_today": done}


# --- reports -----------------------------------------------------------------


def streaks(state: Dict[str, Any], day: dt.date) -> Dict[str, int]:
    dates = {dt.date.fromisoformat(s["date"]) for s in state["sessions"]}
    daily, cursor = 0, day if day in dates else day - dt.timedelta(days=1)
    while cursor in dates:
        daily += 1
        cursor -= dt.timedelta(days=1)
    per_week: Dict[Tuple[int, int], int] = {}
    for date in dates:
        per_week[week_key(date)] = per_week.get(week_key(date), 0) + 1
    target = state["settings"]["weekly_sessions"]
    weekly, monday = 0, day - dt.timedelta(days=day.weekday())
    if per_week.get(week_key(monday), 0) < target:
        monday -= dt.timedelta(days=7)  # the current week is still open
    while per_week.get(week_key(monday), 0) >= target:
        weekly += 1
        monday -= dt.timedelta(days=7)
    return {"daily": daily, "weekly": weekly, "this_week": per_week.get(week_key(day), 0)}


def coverage(state: Dict[str, Any], areas: Tuple[str, ...] = AREAS) -> List[Dict[str, Any]]:
    rows = []
    for area in areas:
        topics = [t for t in active_topics(state) if t["area"] == area]
        seen = [state["progress"][t["id"]] for t in topics if t["id"] in state["progress"]]
        avg = round(sum(p["last_score"] for p in seen) / len(seen), 1) if seen else None
        rows.append({"area": area, "total": len(topics), "seen": len(seen), "avg_score": avg,
                     "weak": sorted(t["id"] for t in topics
                                    if t["id"] in state["progress"] and state["progress"][t["id"]]["last_score"] <= 2)})
    return rows


def status_report(state: Dict[str, Any], day: dt.date) -> Dict[str, Any]:
    settings = state["settings"]
    done_today = any(s["date"] == day.isoformat() for s in state["sessions"])
    report: Dict[str, Any] = {
        "date": day.isoformat(), "cadence": settings["cadence"], "focus": settings["focus"],
        "streak": streaks(state, day), "done_today": done_today,
        "due": [{"id": t["id"], "area": t["area"], "due": t["progress"]["due"],
                 "last_score": t["progress"]["last_score"]} for t in due_topics(state, day)],
        "coverage": coverage(state),
    }
    if settings["interview_date"]:
        left = (dt.date.fromisoformat(settings["interview_date"]) - day).days
        report["interview_days_left"] = left
        if 0 <= left <= 21 and settings["focus"] == "skills":
            report["suggestion"] = "the interview is in %d days: `config set focus interview`" % left
    if settings["cadence"] == "weekly":
        report["sessions_left_this_week"] = max(0, settings["weekly_sessions"] - report["streak"]["this_week"])
    return report


def render_plan(state: Dict[str, Any], day: dt.date) -> str:
    s = state["settings"]
    lines = [
        "# Training plan", "",
        "Stack: %s · interview coding language: %s · focus: %s · active cadence: %s"
        % (", ".join(s["stack"]), s["interview_language"], s["focus"], s["cadence"]),
    ]
    if s["goals"]:
        lines += ["Goals: " + "; ".join(s["goals"])]
    if s["weak_areas"]:
        lines += ["Weak areas first: " + ", ".join(s["weak_areas"])]
    if s["interview_date"]:
        lines += ["Interview: %s (%d days)" % (s["interview_date"],
                                               (dt.date.fromisoformat(s["interview_date"]) - day).days)]
    lines += ["", "## Daily plan (%d min a day)" % s["daily_minutes"], "",
              "| Day | Block | Next up |", "| --- | --- | --- |"]
    taken: List[str] = []
    for index, slot in enumerate(DAILY[s["focus"]]):
        nxt = pick(state, slot, day, taken)
        if nxt:
            taken.append(nxt["id"])
        lines.append("| %s | %s | %s |" % (WEEKDAYS[index], slot, nxt["title"] if nxt else "—"))
    lines += ["", "## Weekly plan (%d sessions of %d min)" % (s["weekly_sessions"], s["session_minutes"]), "",
              "| Session | Blocks | Next up |", "| --- | --- | --- |"]
    taken = []
    for index, slots in enumerate(WEEKLY[s["focus"]][:s["weekly_sessions"]], 1):
        nexts = []
        for slot in slots:
            nxt = pick(state, slot, day, taken)
            if nxt:
                taken.append(nxt["id"])
                nexts.append(nxt["title"])
        lines.append("| %d | %s | %s |" % (index, " + ".join(slots), "; ".join(nexts) or "—"))
    lines += ["", "## Coverage", "", "| Area | Seen | Avg score | Weak |", "| --- | --- | --- | --- |"]
    for row in coverage(state):
        lines.append("| %s | %d/%d | %s | %s |" % (row["area"], row["seen"], row["total"],
                                                  row["avg_score"] if row["avg_score"] is not None else "—",
                                                  ", ".join(row["weak"]) or "—"))
    lines += ["", "Rendered from state.json on %s. Change settings with `trainer.py config set`; "
              "this file is rewritten by `plan --write`." % day.isoformat(), ""]
    return "\n".join(lines)


def interview_report(state: Dict[str, Any], day: dt.date) -> Dict[str, Any]:
    out: Dict[str, Any] = {"language": state["settings"]["interview_language"],
                           "interview_date": state["settings"]["interview_date"], "areas": {}}
    for area in TRACKS["interview"]:
        rows = []
        for topic in active_topics(state):
            if topic["area"] != area:
                continue
            prog = state["progress"].get(topic["id"])
            mocks = sum(1 for s in state["sessions"] if s["topic"] == topic["id"] and s["kind"] == "mock")
            rows.append({"id": topic["id"], "title": topic["title"], "level": topic.get("level", 2),
                         "last_score": prog["last_score"] if prog else None,
                         "due": prog["due"] if prog else None, "mocks": mocks})
        out["areas"][area] = rows
    out["next"] = [{"id": t["id"], "title": t["title"], "why": t["why"]}
                   for t in (pick(state, a, day, []) for a in TRACKS["interview"]) if t]
    return out


# --- commands ----------------------------------------------------------------


def emit(data: Any, as_json: bool, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if as_json else text)


def cmd_where(args) -> int:
    home, source = resolve_home(args.home)
    exists = state_path(home).is_file()
    print("%s (from %s)%s" % (home, source, "" if exists else " — not initialized yet"))
    return 0


def cmd_set_home(args) -> int:
    home = normalize_path(args.path)
    cfg = config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"home": args.path}, indent=2) + "\n", encoding="utf-8")
    note = "" if state_path(home).is_file() else " (no state.json there yet: run `init`, or move the old folder there)"
    print("training folder set to %s%s" % (home, note))
    return 0


def cmd_init(args) -> int:
    home, _ = resolve_home(args.home)
    if state_path(home).is_file() and not args.force:
        raise TrainerError("%s already exists. Change settings with `config set`; --force starts over "
                           "(history is backed up to state.json.bak)" % state_path(home))
    settings: Dict[str, Any] = {}
    for key in ("stack", "interview_language", "cadence", "focus", "daily_minutes", "weekly_sessions",
                "session_minutes", "goals", "weak_areas", "interview_date"):
        value = getattr(args, key)
        if value is not None:
            set_setting(settings, key, str(value))
    path = write_state(home, new_state(settings))
    print("initialized %s" % path)
    return 0


def cmd_config(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    if args.action == "set":
        if args.key is None or args.value is None:
            raise TrainerError("usage: config set KEY VALUE")
        key = set_setting(state["settings"], args.key, args.value)
        write_state(home, state)
        print("%s updated. History is kept; the next session uses the new value." % key)
        return 0
    s = state["settings"]
    text = "\n".join("%-20s %s" % (k, ", ".join(v) if isinstance(v, list) else v) for k, v in s.items())
    emit(s, args.json, text)
    return 0


def cmd_plan(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    day = parse_date(args.date)
    text = render_plan(state, day)
    if args.write:
        (home / "plan.md").write_text(text, encoding="utf-8")
        text += "\nwritten to %s" % (home / "plan.md")
    emit({"daily": DAILY[state["settings"]["focus"]],
          "weekly": WEEKLY[state["settings"]["focus"]][:state["settings"]["weekly_sessions"]],
          "settings": state["settings"]}, args.json, text)
    return 0


def cmd_today(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    if args.cadence and args.cadence not in CADENCES:
        raise TrainerError("cadence is one of %s" % ", ".join(CADENCES))
    session = session_for(state, parse_date(args.date), args.cadence)
    lines = ["%s — %d min (%s focus)" % (session["label"], session["minutes"], session["focus"])]
    if session["logged_today"]:
        lines.append("already logged today: %s. Anything below is extra." % ", ".join(session["logged_today"]))
    for item in session["items"]:
        extra = " in %s" % item["language"] if item.get("language") else ""
        lines.append("- [%s] %s (%s)%s, ~%d min — %s" % (item["area"], item["title"], item["id"], extra,
                                                       item["minutes"], item["why"]))
        if item.get("hints"):
            lines.append("    hints: " + "; ".join(item["hints"]))
    if not session["items"]:
        lines.append("- nothing to schedule: every topic for this focus is done; add one with add-topic")
    emit(session, args.json, "\n".join(lines))
    return 0


def cmd_log(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    if args.kind not in ("practice", "mock"):
        raise TrainerError("kind is practice or mock")
    day = parse_date(args.date)
    progress = record(state, args.topic, args.score, day, args.minutes, args.notes or "", args.kind)
    write_state(home, state)
    print("logged %s: score %d, back on %s (in %d day%s)" % (args.topic, args.score, progress["due"],
                                                           progress["interval"],
                                                           "" if progress["interval"] == 1 else "s"))
    return 0


def cmd_topics(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    areas = TRACKS[args.track] if args.track else AREAS
    rows = [t for t in active_topics(state) if t["area"] in areas and (not args.area or t["area"] == args.area)]
    for row in rows:
        row["progress"] = state["progress"].get(row["id"])
    text = "\n".join("%-28s %-10s L%s %-6s %s" % (t["id"], t["area"], t.get("level", 2),
                                                 ("s%d" % t["progress"]["last_score"]) if t["progress"] else "new",
                                                 t["title"]) for t in rows)
    emit(rows, args.json, text)
    return 0


def cmd_add_topic(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    if args.area not in AREAS:
        raise TrainerError("area is one of %s" % ", ".join(AREAS))
    topic_id = args.id or re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
    if any(t["id"] == topic_id for t in all_topics(state)):
        raise TrainerError("topic id %r already exists" % topic_id)
    state["custom_topics"].append({"id": topic_id, "area": args.area, "level": args.level,
                                   "title": args.title, "hints": args.hint or []})
    write_state(home, state)
    print("added %s (%s)" % (topic_id, args.area))
    return 0


def cmd_interview(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    report = interview_report(state, parse_date(args.date))
    lines = ["Interview track — coding in %s%s" % (report["language"],
             ", interview on %s" % report["interview_date"] if report["interview_date"] else "")]
    for area, rows in report["areas"].items():
        seen = [r for r in rows if r["last_score"] is not None]
        lines.append("%s: %d/%d practised, %d mocked" % (area, len(seen), len(rows), sum(1 for r in rows if r["mocks"])))
        for r in rows:
            mark = "s%d" % r["last_score"] if r["last_score"] is not None else "--"
            lines.append("  %-3s %-26s %s" % (mark, r["id"], r["title"]))
    lines.append("next: " + "; ".join("%s (%s)" % (n["id"], n["why"]) for n in report["next"]))
    emit(report, args.json, "\n".join(lines))
    return 0


def cmd_status(args) -> int:
    home, _ = resolve_home(args.home)
    state = read_state(home)
    report = status_report(state, parse_date(args.date))
    st = report["streak"]
    lines = ["%s cadence, %s focus. Streak: %d day%s; %d full week%s; %d session day%s this week."
             % (report["cadence"], report["focus"], st["daily"], "" if st["daily"] == 1 else "s",
                st["weekly"], "" if st["weekly"] == 1 else "s", st["this_week"], "" if st["this_week"] == 1 else "s"),
             "Today: %s." % ("done" if report["done_today"] else "not done yet")]
    if "interview_days_left" in report:
        lines.append("Interview in %d days." % report["interview_days_left"])
    if report.get("suggestion"):
        lines.append("Suggestion: " + report["suggestion"])
    lines.append("Due: " + (", ".join("%s (s%d)" % (d["id"], d["last_score"]) for d in report["due"]) or "nothing"))
    for row in report["coverage"]:
        lines.append("  %-10s %d/%d seen, avg %s%s" % (row["area"], row["seen"], row["total"],
                                                     row["avg_score"] if row["avg_score"] is not None else "—",
                                                     ", weak: " + ", ".join(row["weak"]) if row["weak"] else ""))
    emit(report, args.json, "\n".join(lines))
    return 1 if report["due"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--home", help="training folder (overrides $SKILL_TRAINER_HOME and set-home)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("where").set_defaults(func=cmd_where)
    p = sub.add_parser("set-home")
    p.add_argument("path")
    p.set_defaults(func=cmd_set_home)

    p = sub.add_parser("init")
    p.add_argument("--stack")
    p.add_argument("--interview-language", dest="interview_language")
    p.add_argument("--cadence")
    p.add_argument("--focus")
    p.add_argument("--daily-minutes", dest="daily_minutes")
    p.add_argument("--weekly-sessions", dest="weekly_sessions")
    p.add_argument("--session-minutes", dest="session_minutes")
    p.add_argument("--goals", help="semicolon-separated")
    p.add_argument("--weak-areas", dest="weak_areas", help="comma-separated areas, stack entries or topic ids")
    p.add_argument("--interview-date", dest="interview_date")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("config")
    p.add_argument("action", choices=("show", "set"))
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_config)

    for name, func in (("plan", cmd_plan), ("today", cmd_today), ("interview", cmd_interview),
                       ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--date")
        p.add_argument("--json", action="store_true")
        if name == "plan":
            p.add_argument("--write", action="store_true")
        if name == "today":
            p.add_argument("--cadence")
        p.set_defaults(func=func)

    p = sub.add_parser("log")
    p.add_argument("--topic", required=True)
    p.add_argument("--score", type=int, required=True)
    p.add_argument("--minutes", type=int)
    p.add_argument("--notes")
    p.add_argument("--kind", default="practice")
    p.add_argument("--date")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("topics")
    p.add_argument("--area")
    p.add_argument("--track", choices=tuple(TRACKS))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_topics)

    p = sub.add_parser("add-topic")
    p.add_argument("--area", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--id")
    p.add_argument("--level", type=int, default=2, choices=(1, 2, 3))
    p.add_argument("--hint", action="append")
    p.set_defaults(func=cmd_add_topic)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TrainerError as exc:
        print("trainer: %s" % exc, file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
