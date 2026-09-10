#!/usr/bin/env python3
"""PostToolUse hook: notice an edit that breaks ping-pong turn discipline.

Two edits contradict the turn, and both are the ordinary way a TDD session stops
being test-driven:

    * production code touched while the turn is to write a failing test — the
      code is being written first and the test shaped to fit it;
    * a test file touched while the turn is to make it pass — the test is being
      edited to meet the code.

The classification is not defined here. `is_test_path` is imported from the
tdd-ping-pong skill, which owns it, so the hook cannot disagree with the gate
the /pingpong command runs.

Silent outside ping-pong mode, and silent when the edit is consistent with the
turn. It never blocks: the exit status is always 0, and an unreadable or
unrecognised event is ignored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
for directory in (
    PLUGIN_ROOT / "skills" / "pair-session" / "scripts",
    PLUGIN_ROOT / "skills" / "tdd-ping-pong" / "scripts",
):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

try:
    import session  # type: ignore
    import tdd  # type: ignore
except ImportError:  # the skill was installed without the bundle; stay silent
    session = None
    tdd = None

COMPLAINTS = {
    "write-failing-test": (
        "pair: %s is production code, and the turn is to write a failing test.\n"
        "      If the test needs a stub to fail on an assertion, that is fine — "
        "more than that and the code is leading."
    ),
    "make-it-pass": (
        "pair: %s is a test file, and the turn is to make the test pass.\n"
        "      If the test is wrong, say so and hand back rather than editing it "
        "to meet the code."
    ),
}


def target_path(event):
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filePath")
    return str(raw) if raw else None


def main() -> int:
    if session is None or tdd is None:
        return 0
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0

    path = target_path(event)
    if not path:
        return 0

    try:
        state = session.read(Path(session.DEFAULT_PATH))
    except Exception:
        return 0
    if state.get("status") != "open" or state.get("mode") != "pingpong":
        return 0

    turn = state.get("turn")
    if turn not in COMPLAINTS:
        return 0

    is_test = tdd.is_test_path(path, state.get("test_globs"))
    contradicts = (turn == "write-failing-test" and not is_test) or (
        turn == "make-it-pass" and is_test
    )
    if contradicts:
        print(COMPLAINTS[turn] % Path(path).name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
