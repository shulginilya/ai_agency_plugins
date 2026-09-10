#!/usr/bin/env python3
"""The pairing session journal: goal, decisions, open questions, whose turn, next step.

Usage:
    python scripts/session.py start --goal "..." [--scope src/auth --scope tests/auth]
                                    [--test-command "pytest -q"] [--mode navigate|pingpong]
    python scripts/session.py status [--json]
    python scripts/session.py decide "use a queue" --because "retries need to survive a restart"
    python scripts/session.py reject "cron" --because "5-minute floor is too slow"
    python scripts/session.py ask "is the webhook idempotent?"
    python scripts/session.py answer 1 "yes, keyed on event id"
    python scripts/session.py note "the failure only shows with two workers"
    python scripts/session.py next "extract the retry policy"
    python scripts/session.py turn [--to write-failing-test|make-it-pass|refactor]
    python scripts/session.py log
    python scripts/session.py handoff [--out .pair/handoff.md]
    python scripts/session.py close

The state lives in ONE file, `.pair/session.json`, because a journal that is
parsed back out of prose loses an entry sooner or later. `handoff` renders that
state to markdown; the markdown is output, never input.

Every write copies the file to `.pair/session.json.bak` first, and a file that
does not parse is refused rather than replaced — silently re-initialising over
a session someone spent an afternoon on is the one unforgivable bug here.

Exit codes for `status` are four different answers:
    0   a session is open and nothing needs the pair's attention
    1   open, but something does: unanswered questions, no next step, or
        ping-pong with no test command
    2   unusable: no session file, or it does not parse
    3   open, but it may not describe the work in front of you — the branch
        moved, or the base commit is gone. That is a question, not a pass.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path(".pair/session.json")
SCHEMA_VERSION = 1

MODES = ["navigate", "pingpong"]
TURNS = ["write-failing-test", "make-it-pass", "refactor"]
NEXT_TURN = {
    "write-failing-test": "make-it-pass",
    "make-it-pass": "refactor",
    "refactor": "write-failing-test",
}

# What counts as a test file, unless the session declares its own. Used by the
# ping-pong turn gate; kept here because the session owns the setting and
# tdd.py imports it rather than keeping a second list.
DEFAULT_TEST_GLOBS = [
    "test_*.py", "*_test.py", "*.test.*", "*.spec.*", "*Test.java", "*Tests.cs",
    "tests/*", "test/*", "__tests__/*", "spec/*",
]

DEFAULT_DIFF_BUDGET = 400

REQUIRED_KEYS = ("version", "goal", "status", "entries")


class SessionError(Exception):
    """The session file is missing or unusable."""


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def git(args: List[str], cwd: Optional[str] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, check=False, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def read(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    """Load the session. Raises SessionError rather than returning a blank one."""
    if not path.is_file():
        raise SessionError("no pairing session at %s — run `session.py start` first" % path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(
            "%s does not parse (%s). It is not being overwritten; fix or move it." % (path, exc)
        )
    if not isinstance(state, dict) or any(key not in state for key in REQUIRED_KEYS):
        raise SessionError(
            "%s is missing %s — this is not a pairing session file, and it is not "
            "being overwritten." % (path, ", ".join(REQUIRED_KEYS))
        )
    state.setdefault("entries", [])
    return state


def write(state: Dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    if path.is_file():
        shutil.copyfile(str(path), str(path) + ".bak")
    state["updated"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def entries_of(state: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    return [e for e in state.get("entries", []) if e.get("kind") == kind]


def open_questions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [q for q in entries_of(state, "question") if not q.get("answer")]


def add_entry(state: Dict[str, Any], kind: str, text: str, **extra: Any) -> Dict[str, Any]:
    entry = {"n": len(state.get("entries", [])) + 1, "at": now(), "kind": kind, "text": text}
    entry.update({k: v for k, v in extra.items() if v is not None})
    state.setdefault("entries", []).append(entry)
    return entry


def status_report(state: Dict[str, Any], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Bucket what the session needs. The single home for this rule — the CLI,
    the SessionStart hook and the MCP server all call it."""
    attention: List[str] = []
    suspect: List[str] = []

    questions = open_questions(state)
    if questions:
        attention.append("%d unanswered question(s)" % len(questions))
    if not state.get("next_step"):
        attention.append("no next step recorded")
    if state.get("mode") == "pingpong" and not state.get("test_command"):
        attention.append("ping-pong is on but no test command is declared")

    branch_now = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if state.get("branch") and branch_now and branch_now != state["branch"]:
        suspect.append("started on %s, now on %s" % (state["branch"], branch_now))
    base = state.get("base_ref")
    if base and git(["rev-parse", "--verify", "--quiet", base + "^{commit}"], cwd) is None:
        suspect.append("base commit %s no longer resolves" % base[:12])

    closed = state.get("status") != "open"
    if closed:
        verdict, code = "closed", 0
    elif suspect:
        verdict, code = "suspect", 3
    elif attention:
        verdict, code = "needs-attention", 1
    else:
        verdict, code = "ok", 0

    return {
        "verdict": verdict,
        "exit_code": code,
        "goal": state.get("goal", ""),
        "mode": state.get("mode", "navigate"),
        "turn": state.get("turn"),
        "next_step": state.get("next_step", ""),
        "scope": state.get("scope", []),
        "test_command": state.get("test_command", ""),
        "open_questions": questions,
        "decisions": entries_of(state, "decision"),
        "rejected": entries_of(state, "rejected"),
        "attention": attention,
        "suspect": suspect,
        "started": state.get("started", ""),
        "updated": state.get("updated", ""),
        "status": state.get("status", "open"),
    }


def render_handoff(state: Dict[str, Any]) -> str:
    report = status_report(state)
    out = ["# Pairing handoff", ""]
    out.append("**Goal:** %s" % (report["goal"] or "(none stated)"))
    out.append("")
    out.append("- Started: %s" % (report["started"] or "-"))
    out.append("- Last touched: %s" % (report["updated"] or "-"))
    out.append("- Mode: %s%s" % (report["mode"], " — turn: %s" % report["turn"] if report["turn"] else ""))
    if report["scope"]:
        out.append("- Scope: %s" % ", ".join(report["scope"]))
    if report["test_command"]:
        out.append("- Tests: `%s`" % report["test_command"])
    out.append("")

    out.append("## Next step")
    out.append("")
    out.append(report["next_step"] or "_Not recorded. Whoever picks this up has to guess — don't make them._")
    out.append("")

    out.append("## Decisions")
    out.append("")
    if report["decisions"]:
        for d in report["decisions"]:
            out.append("- **%s** — %s" % (d["text"], d.get("because", "no reason recorded")))
    else:
        out.append("_None recorded._")
    out.append("")

    out.append("## Considered and rejected")
    out.append("")
    if report["rejected"]:
        for r in report["rejected"]:
            out.append("- **%s** — %s" % (r["text"], r.get("because", "no reason recorded")))
    else:
        out.append("_None recorded — which usually means the alternatives were never named._")
    out.append("")

    out.append("## Open questions")
    out.append("")
    if report["open_questions"]:
        for q in report["open_questions"]:
            out.append("- [%d] %s" % (q["n"], q["text"]))
    else:
        out.append("_None open._")
    out.append("")

    notes = entries_of(state, "note")
    if notes:
        out.append("## Log")
        out.append("")
        for e in state.get("entries", []):
            if e.get("kind") == "note":
                out.append("- `%s` %s" % (e.get("at", ""), e["text"]))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --- commands ---------------------------------------------------------------

def cmd_start(args, path: Path) -> int:
    if path.is_file():
        existing = read(path)  # refuses to clobber an unparseable file
        if existing.get("status") == "open" and not args.restart:
            sys.stderr.write(
                "a session is already open: %s\n"
                "Use `session.py status`, or `--restart` to close it and begin a new one.\n"
                % (existing.get("goal") or "(no goal)")
            )
            return 2
        if existing.get("status") == "open":
            archive = path.parent / ("session-%s.json" % dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
            path.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
            print("archived the previous session to %s" % archive)

    if args.mode not in MODES:
        sys.stderr.write("unknown mode %r; choose one of %s\n" % (args.mode, ", ".join(MODES)))
        return 2
    if args.mode == "pingpong" and not args.test_command:
        sys.stderr.write(
            "ping-pong needs --test-command: the turn gate has nothing to check without it.\n"
        )
        return 2

    base = args.base or git(["rev-parse", "HEAD"]) or ""
    state = {
        "version": SCHEMA_VERSION,
        "goal": args.goal,
        "scope": list(args.scope or []),
        "test_command": args.test_command or "",
        "test_globs": DEFAULT_TEST_GLOBS,
        "diff_budget": args.diff_budget,
        "mode": args.mode,
        "turn": "write-failing-test" if args.mode == "pingpong" else None,
        "driver": args.driver,
        "base_ref": base,
        "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]) or "",
        "started": now(),
        "updated": now(),
        "status": "open",
        "next_step": args.next or "",
        "entries": [],
    }
    write(state, path)
    print("session open: %s" % args.goal)
    if state["turn"]:
        print("turn: %s" % state["turn"])
    if not state["scope"]:
        print("no scope declared — drift.py cannot say anything until there is one")
    return 0


def cmd_status(args, path: Path) -> int:
    state = read(path)
    report = status_report(state)
    if args.json:
        print(json.dumps(report, indent=2))
        return report["exit_code"]
    print("goal: %s" % (report["goal"] or "(none)"))
    print("mode: %s%s" % (report["mode"], "  turn: %s" % report["turn"] if report["turn"] else ""))
    print("next: %s" % (report["next_step"] or "(not recorded)"))
    if report["scope"]:
        print("scope: %s" % ", ".join(report["scope"]))
    for question in report["open_questions"]:
        print("open  [%d] %s" % (question["n"], question["text"]))
    for line in report["suspect"]:
        print("SUSPECT  %s" % line)
    for line in report["attention"]:
        print("needs  %s" % line)
    if report["verdict"] == "ok":
        print("nothing outstanding")
    return report["exit_code"]


def _record(args, path: Path, kind: str) -> int:
    state = read(path)
    if kind in ("decision", "rejected") and not args.because:
        sys.stderr.write(
            "--because is required: a decision without its reason is a note, and a note "
            "does not survive the handoff.\n"
        )
        return 2
    entry = add_entry(state, kind, args.text, because=getattr(args, "because", None))
    write(state, path)
    print("[%d] %s: %s" % (entry["n"], kind, args.text))
    return 0


def cmd_decide(args, path: Path) -> int:
    return _record(args, path, "decision")


def cmd_reject(args, path: Path) -> int:
    return _record(args, path, "rejected")


def cmd_note(args, path: Path) -> int:
    return _record(args, path, "note")


def cmd_ask(args, path: Path) -> int:
    state = read(path)
    entry = add_entry(state, "question", args.text)
    write(state, path)
    print("[%d] open question: %s" % (entry["n"], args.text))
    return 0


def cmd_answer(args, path: Path) -> int:
    state = read(path)
    for entry in state.get("entries", []):
        if entry.get("n") == args.number and entry.get("kind") == "question":
            if entry.get("answer"):
                sys.stderr.write("[%d] is already answered: %s\n" % (args.number, entry["answer"]))
                return 2
            entry["answer"] = args.text
            entry["answered_at"] = now()
            write(state, path)
            print("[%d] answered: %s" % (args.number, args.text))
            return 0
    sys.stderr.write("no open question numbered %d\n" % args.number)
    return 2


def cmd_next(args, path: Path) -> int:
    state = read(path)
    state["next_step"] = args.text
    add_entry(state, "step", args.text)
    write(state, path)
    print("next: %s" % args.text)
    return 0


def cmd_turn(args, path: Path) -> int:
    state = read(path)
    if args.to is None:
        print(state.get("turn") or "(no turn — this session is not in ping-pong mode)")
        return 0
    if args.to not in TURNS:
        sys.stderr.write("unknown turn %r; choose one of %s\n" % (args.to, ", ".join(TURNS)))
        return 2
    was = state.get("turn")
    state["turn"] = args.to
    if state.get("mode") != "pingpong":
        state["mode"] = "pingpong"
    add_entry(state, "turn", args.to, previous=was)
    write(state, path)
    print("turn: %s -> %s" % (was or "(none)", args.to))
    return 0


def cmd_log(args, path: Path) -> int:
    state = read(path)
    for entry in state.get("entries", []):
        line = "[%d] %-9s %s" % (entry["n"], entry["kind"], entry["text"])
        if entry.get("because"):
            line += "  (because %s)" % entry["because"]
        if entry.get("answer"):
            line += "  -> %s" % entry["answer"]
        print(line)
    if not state.get("entries"):
        print("nothing recorded yet")
    return 0


def cmd_handoff(args, path: Path) -> int:
    state = read(path)
    out = Path(args.out) if args.out else path.parent / "handoff.md"
    text = render_handoff(state)
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if out.is_file():
        shutil.copyfile(str(out), str(out) + ".bak")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print("wrote %s" % out)
    unanswered = len(open_questions(state))
    if unanswered:
        print("%d question(s) are still open — say so in the handover, do not bury them" % unanswered)
    return 0


def cmd_close(args, path: Path) -> int:
    state = read(path)
    if state.get("status") != "open":
        print("already closed")
        return 0
    state["status"] = "closed"
    state["closed_at"] = now()
    add_entry(state, "note", args.text or "session closed")
    write(state, path)
    print("session closed: %s" % (state.get("goal") or ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pairing session journal.")
    parser.add_argument("--file", help="session file (default: .pair/session.json)")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start")
    p_start.add_argument("--goal", required=True)
    p_start.add_argument("--scope", action="append", help="path or glob the work is allowed to touch")
    p_start.add_argument("--test-command", dest="test_command")
    p_start.add_argument("--mode", default="navigate")
    p_start.add_argument("--driver", default="human", choices=["human", "agent"])
    p_start.add_argument("--base", help="commit the change is measured from (default: HEAD)")
    p_start.add_argument("--diff-budget", type=int, default=DEFAULT_DIFF_BUDGET)
    p_start.add_argument("--next", help="first next step")
    p_start.add_argument("--restart", action="store_true", help="archive an open session and start over")

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")

    for name in ("decide", "reject"):
        p = sub.add_parser(name)
        p.add_argument("text")
        p.add_argument("--because", required=False)

    p_note = sub.add_parser("note")
    p_note.add_argument("text")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("text")

    p_answer = sub.add_parser("answer")
    p_answer.add_argument("number", type=int)
    p_answer.add_argument("text")

    p_next = sub.add_parser("next")
    p_next.add_argument("text")

    p_turn = sub.add_parser("turn")
    p_turn.add_argument("--to")

    sub.add_parser("log")

    p_handoff = sub.add_parser("handoff")
    p_handoff.add_argument("--out")
    p_handoff.add_argument("--stdout", action="store_true")

    p_close = sub.add_parser("close")
    p_close.add_argument("text", nargs="?")
    return parser


HANDLERS = {
    "start": cmd_start, "status": cmd_status, "decide": cmd_decide, "reject": cmd_reject,
    "note": cmd_note, "ask": cmd_ask, "answer": cmd_answer, "next": cmd_next,
    "turn": cmd_turn, "log": cmd_log, "handoff": cmd_handoff, "close": cmd_close,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    path = Path(args.file) if args.file else DEFAULT_PATH
    try:
        return HANDLERS[args.command](args, path)
    except SessionError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    except (OSError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
