#!/usr/bin/env python3
"""The ping-pong turn gate: run the suite, name the state, and refuse a turn it does not earn.

Usage:
    python scripts/tdd.py state [--command "pytest -q"] [--json] [--timeout 300]
    python scripts/tdd.py turn                       # whose turn, and what it needs
    python scripts/tdd.py advance [--json]           # next turn, if the suite allows it
    python scripts/tdd.py classify path/to/file.py   # test file or production file

The point of the gate is that ping-pong has exactly two ways to go quietly
wrong, and both look like progress:

    * you write a test, the suite is green, and you move on — the test either
      passed already or was never collected;
    * you write a test, the suite errors on an import, and you "fix" it — an
      import error is not a red test, and the code you wrote to clear it was
      never driven by anything.

So the suite has FOUR states, not two, and the two extra ones are the load
bearing ones:

    GREEN     every test passed
    RED       a test failed — an assertion, which is what a new test should do
    ERRORED   the suite did not reach a verdict: import error, collection
              error, timeout, or it ran zero tests
    UNUSABLE  no test command declared, or the command does not exist

Exit codes for `state`:  0 GREEN, 1 RED, 2 UNUSABLE, 3 ERRORED.
Exit codes for `advance`: 0 advanced, 1 refused by the gate, 2 unusable, 3 the
suite errored so the gate cannot judge.

The declared test command runs through the shell, because that is how test
commands are written. It comes from the session file the user wrote; nothing
here invents one.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SESSION_SCRIPTS = Path(__file__).resolve().parents[2] / "pair-session" / "scripts"
if str(SESSION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SESSION_SCRIPTS))

try:  # the plugin ships both skills; tolerate a partial install rather than crash
    import session  # type: ignore
except ImportError:  # pragma: no cover - exercised only by a broken install
    session = None

GREEN, RED, ERRORED, UNUSABLE = "GREEN", "RED", "ERRORED", "UNUSABLE"
EXIT = {GREEN: 0, RED: 1, UNUSABLE: 2, ERRORED: 3}

DEFAULT_TIMEOUT = 300

# A zero-test run reports success. Every one of these is a green that means
# nothing, and treating it as green is how a ping-pong session drifts.
NO_TESTS_MARKERS = (
    "no tests ran", "no tests collected", "collected 0 items", "ran 0 tests",
    "no tests found", "no test files found", "0 passing", "there are no tests",
    "no tests to run",
)

# The suite blew up before it could judge anything.
ERROR_MARKERS = (
    "importerror", "modulenotfounderror", "cannot find module", "syntaxerror",
    "errors during collection", "error collecting", "internal error",
    "unable to resolve", "compilation error", "traceback (most recent call last)",
)

NOT_FOUND_MARKERS = ("command not found", "is not recognized", "no such file or directory")

TURN_NEEDS = {
    "write-failing-test": RED,
    "make-it-pass": GREEN,
    "refactor": GREEN,
}

TURN_MEANS = {
    "write-failing-test": "write one failing test and nothing else",
    "make-it-pass": "write the smallest code that turns it green, and no more",
    "refactor": "improve the code with the suite green the whole way, then hand back",
}

REFUSALS = {
    ("write-failing-test", GREEN): (
        "the suite is green. Either the test you wrote already passes, or it is not "
        "being collected. Both mean the next code you write is undriven — check which."
    ),
    ("write-failing-test", ERRORED): (
        "the suite errored rather than failed. An import or collection error is not a "
        "red test; fix it and run again, so the red you get is the one you wrote."
    ),
    ("make-it-pass", RED): (
        "still red. Stay on this turn — do not hand back a failing suite, and do not "
        "edit the test to meet the code."
    ),
    ("make-it-pass", ERRORED): (
        "the suite errored rather than failed. Fix the error before deciding whether "
        "the implementation is done."
    ),
    ("refactor", RED): (
        "the refactor broke something. Revert to the last green rather than fixing "
        "forward — a refactor that needs a fix was a rewrite."
    ),
    ("refactor", ERRORED): (
        "the suite errored during a refactor. Get back to a suite that runs before "
        "going any further."
    ),
}


def classify_state(returncode: int, output: str) -> Dict[str, str]:
    """Map an exit code and output to one of the four states, with a reason."""
    text = (output or "").lower()

    if returncode == 127 or any(m in text for m in NOT_FOUND_MARKERS):
        return {"state": UNUSABLE, "reason": "the test command did not run at all"}

    for marker in NO_TESTS_MARKERS:
        if marker in text:
            return {"state": ERRORED, "reason": "the suite ran no tests (%r) — a green with nothing behind it" % marker}

    if returncode == 0:
        return {"state": GREEN, "reason": "every test passed"}

    for marker in ERROR_MARKERS:
        if marker in text:
            return {"state": ERRORED, "reason": "the suite did not reach a verdict (%r in the output)" % marker}

    if returncode == 1:
        return {"state": RED, "reason": "a test failed"}

    # pytest: 2 interrupted, 3 internal error, 4 usage error, 5 nothing collected.
    return {"state": ERRORED, "reason": "the runner exited %d, which is not a test verdict" % returncode}


def run_suite(command: str, cwd: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    if not command or not command.strip():
        return {"state": UNUSABLE, "reason": "no test command is declared for this session",
                "command": command or "", "exit_code": None, "output_tail": ""}
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"state": ERRORED, "reason": "the suite did not finish in %ds" % timeout,
                "command": command, "exit_code": None, "output_tail": ""}
    except OSError as exc:
        return {"state": UNUSABLE, "reason": "could not run the test command (%s)" % exc,
                "command": command, "exit_code": None, "output_tail": ""}

    output = (result.stdout or "") + (result.stderr or "")
    verdict = classify_state(result.returncode, output)
    tail = "\n".join(output.strip().splitlines()[-20:])
    return {"state": verdict["state"], "reason": verdict["reason"], "command": command,
            "exit_code": result.returncode, "output_tail": tail}


def is_test_path(path: str, globs: Optional[List[str]] = None) -> bool:
    """True when a path looks like a test file under the session's own globs."""
    patterns = globs or (session.DEFAULT_TEST_GLOBS if session else [])
    normalised = str(path).replace("\\", "/")
    name = normalised.rsplit("/", 1)[-1]
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        if fnmatch.fnmatch(normalised, pattern) or fnmatch.fnmatch(normalised, "*/" + pattern):
            return True
    return False


def gate(turn: str, state: str) -> Dict[str, Any]:
    """May this turn be handed over? Returns the verdict and, when not, why."""
    needed = TURN_NEEDS.get(turn)
    if needed is None:
        return {"allowed": False, "reason": "unknown turn %r" % turn, "next": None, "code": 2}
    if state == UNUSABLE:
        return {"allowed": False, "next": None, "code": 2,
                "reason": "no usable test command, so nothing gates this turn. Declare one before pairing this way."}
    if state == needed:
        return {"allowed": True, "next": session.NEXT_TURN[turn] if session else None,
                "reason": "suite is %s, which is what %r needs" % (state, turn), "code": 0}
    refusal = REFUSALS.get((turn, state), "the suite is %s; %r needs %s" % (state, turn, needed))
    return {"allowed": False, "next": None, "reason": refusal,
            "code": 3 if state == ERRORED else 1}


def _load_session(path: Optional[str]) -> Dict[str, Any]:
    if session is None:
        raise RuntimeError("the pair-session skill is not installed alongside this one")
    return session.read(Path(path) if path else session.DEFAULT_PATH)


def cmd_state(args) -> int:
    command = args.command
    if not command:
        try:
            state_file = _load_session(args.file)
            command = state_file.get("test_command", "")
        except Exception as exc:
            sys.stderr.write("%s\n" % exc)
            return EXIT[UNUSABLE]
    result = run_suite(command, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("%s — %s" % (result["state"], result["reason"]))
        if result["output_tail"] and result["state"] in (RED, ERRORED):
            print("---")
            print(result["output_tail"])
    return EXIT[result["state"]]


def cmd_turn(args) -> int:
    try:
        state_file = _load_session(args.file)
    except Exception as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    turn = state_file.get("turn")
    if not turn:
        print("this session is not in ping-pong mode")
        return 2
    print("%s — %s" % (turn, TURN_MEANS[turn]))
    print("hands over when the suite is %s" % TURN_NEEDS[turn])
    return 0


def cmd_advance(args) -> int:
    try:
        state_file = _load_session(args.file)
    except Exception as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    turn = state_file.get("turn")
    if not turn:
        sys.stderr.write("this session is not in ping-pong mode; run `session.py turn --to write-failing-test`\n")
        return 2

    result = run_suite(args.command or state_file.get("test_command", ""), timeout=args.timeout)
    verdict = gate(turn, result["state"])
    payload = {"turn": turn, "suite": result["state"], "reason": verdict["reason"],
               "allowed": verdict["allowed"], "next": verdict["next"]}

    if verdict["allowed"]:
        following = session.NEXT_TURN[turn]
        state_file["turn"] = following
        session.add_entry(state_file, "turn", following, previous=turn)
        session.write(state_file, Path(args.file) if args.file else session.DEFAULT_PATH)
        payload["next"] = following

    if args.json:
        print(json.dumps(payload, indent=2))
    elif verdict["allowed"]:
        print("%s -> %s (suite %s)" % (turn, payload["next"], result["state"]))
        print(TURN_MEANS[payload["next"]])
    else:
        print("staying on %s — %s" % (turn, verdict["reason"]))
        if result["output_tail"]:
            print("---")
            print(result["output_tail"])
    return 0 if verdict["allowed"] else verdict["code"]


def cmd_classify(args) -> int:
    try:
        globs = _load_session(args.file).get("test_globs")
    except Exception:
        globs = None
    verdict = "test" if is_test_path(args.path, globs) else "production"
    print("%s: %s" % (args.path, verdict))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ping-pong turn gate.")
    parser.add_argument("--file", help="session file (default: .pair/session.json)")
    sub = parser.add_subparsers(dest="command_name")

    p_state = sub.add_parser("state")
    p_state.add_argument("--command", help="override the session's test command")
    p_state.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p_state.add_argument("--json", action="store_true")

    sub.add_parser("turn")

    p_advance = sub.add_parser("advance")
    p_advance.add_argument("--command")
    p_advance.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p_advance.add_argument("--json", action="store_true")

    p_classify = sub.add_parser("classify")
    p_classify.add_argument("path")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"state": cmd_state, "turn": cmd_turn, "advance": cmd_advance, "classify": cmd_classify}
    if not args.command_name:
        parser.print_help()
        return 2
    return handlers[args.command_name](args)


if __name__ == "__main__":
    raise SystemExit(main())
