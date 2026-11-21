#!/usr/bin/env python3
"""The red-green-refactor gate: run the tests, name the state, and fail a step that did not earn it.

    tdd.py detect [--json]                                   the test command this repo declares
    tdd.py check [--cmd C] [--expect red|green] [--json] [--timeout S]

`check` runs the tests (the --cmd given, else the one `detect` finds) and names
one of four states:

    GREEN     every test passed
    RED       a test failed: what a new test owes before any code is written
    ERRORED   the run reached no verdict: an import, collection or compile error,
              a timeout, or a run that collected no tests at all
    UNUSABLE  no test command, or it does not exist

A test command that "passes or fails" hides both mistakes that make TDD
theatre: a green with nothing behind it (the new test was never collected) and
an error taken for a red (a typo that stops the module loading). So ERRORED is
its own answer, and --expect red does not accept it.

For RED, `check` also says how the test failed: on an assertion (the right
reason), or on an exception such as a NameError (the code under test does not
exist yet: add a stub so the test fails on its assertion), and lists the failing
tests it can name, so you can confirm the one that failed is the one you wrote.

Exit status without --expect: 0 GREEN, 1 RED, 2 UNUSABLE, 3 ERRORED.
With --expect: 0 the state is the one expected, 1 it is not, 2 unusable, 3 errored.

Standard library only. The command runs through the shell, because that is how
test commands are written.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

GREEN, RED, ERRORED, UNUSABLE = "GREEN", "RED", "ERRORED", "UNUSABLE"
EXIT = {GREEN: 0, RED: 1, UNUSABLE: 2, ERRORED: 3}
DEFAULT_TIMEOUT = 300
TAIL = 40

# A run that collected nothing usually exits 0. Anchored so "10 passing" is not "0 passing".
NO_TESTS = [re.compile(p, re.I | re.M) for p in (
    r"\bno tests ran\b", r"\bno tests collected\b", r"\bcollected 0 items\b", r"\bran 0 tests\b",
    r"\bno tests found\b", r"\bno test files found\b", r"(?<![\d,.])0 passing\b", r"\bthere are no tests\b",
    r"\bno tests to run\b", r"\bno test files\b", r"^(?:#|ℹ) tests 0$", r"\btests:\s+0 total\b",
)]

# The run blew up before it could judge a test: loading, collecting or compiling.
LOAD_ERRORS = [re.compile(p, re.I | re.M) for p in (
    r"errors? during collection", r"\berror collecting\b", r"importerror while importing test module",
    r"failed to import test module", r"test suite failed to run", r"failed to load url",
    r"failed to resolve import", r"\berror TS\d+:", r"^\S+\.go:\d+:\d+: ", r"\[build failed\]",
    r"\[setup failed\]", r"^error\[E\d+\]", r"could not compile", r"compilation (?:failed|error)",
    r"\binternal error\b", r"syntaxerror", r"cannot find module",
)]

# A test ran and failed: the verdict a new test should produce.
FAILURES = [re.compile(p, re.M) for p in (
    r"^FAILED ", r"^FAIL: ", r"^ERROR: test", r"FAILED \((?:failures|errors)=", r"^\s*--- FAIL: ",
    r"^test \S+ \.\.\. FAILED$", r"Tests:\s+\d+ failed", r"^\s*(?:✕|×|✖) ", r"^not ok \d+",
    r"\d+ failed", r"^\s*\d+\) ", r"^ FAIL ",
)]

# The failure came from an assertion, not from code that does not exist yet. These match the
# runner's error report, not the test's source: pytest echoes the source, so a bare "assert" there
# says nothing about how the test failed.
ASSERTIONS = [re.compile(p, re.M) for p in (
    r"AssertionError", r"^E\s+assert ", r"[Aa]ssertion failed", r"expect\(received\)", r"^\s*Expected:",
    r"\bwant\b.*\bgot\b|\bgot\b.*\bwant\b", r"Error: expect\(",
)]
EXCEPTIONS = [re.compile(p) for p in (
    r"\bNameError\b", r"\bAttributeError\b", r"\bTypeError\b", r"\bReferenceError\b",
    r"is not a function", r"is not defined", r"has no attribute", r"\bundefined: ",
    r"cannot find (?:value|function)",
)]

# Names of failing tests, per runner.
FAILING_NAMES = [re.compile(p, re.M) for p in (
    r"^FAILED (\S+::\S+)",                   # pytest short summary
    r"^(?:FAIL|ERROR): (\S+ \([^)]+\))",      # unittest
    r"^\s*--- FAIL: (\S+)",                   # go
    r"^test (\S+) \.\.\. FAILED$",            # cargo
    r"^\s*● (.+?)$",                          # jest
    r"^\s*(?:✕|×|✖) (.+?)(?: \(\d+(?:\.\d+)? ?m?s\))?$",  # jest / vitest / node --test
    r"^not ok \d+ - (.+)$",                   # TAP, node --test
)]


def classify(returncode: Optional[int], output: str) -> Dict[str, Any]:
    """Map an exit code and the run's output to one of the four states, with a reason."""
    text = output or ""
    if returncode == 127 or re.search(r"command not found|is not recognized as|no such file or directory",
                                      text, re.I) and returncode not in (0, 1):
        return {"state": UNUSABLE, "reason": "the test command did not run at all"}
    missing = re.search(r"No module named '?(pytest|unittest|jest|vitest|mocha)\b", text)
    if missing and returncode != 0:
        return {"state": UNUSABLE, "reason": "the test runner %s is not installed" % missing.group(1)}
    for pattern in NO_TESTS:
        hit = pattern.search(text)
        if hit:
            return {"state": ERRORED, "reason": "the run collected no tests (%r): a green with nothing behind it"
                    % hit.group(0).strip()}
    if returncode == 0:
        return {"state": GREEN, "reason": "every test passed"}
    failed = any(p.search(text) for p in FAILURES)
    for pattern in LOAD_ERRORS:
        hit = pattern.search(text)
        if hit:
            line = next((l.strip() for l in text.splitlines() if hit.group(0) in l), hit.group(0))
            return {"state": ERRORED, "reason": "the run reached no verdict: a load, collection or compile error "
                    "(%r). Fix it, so the red you get is a test's" % line[:120]}
    if not failed:
        # A non-zero exit with no failing test reported is a crash or a misconfigured run, never a red.
        return {"state": ERRORED, "reason": "the runner exited %s without reporting a failing test: it crashed "
                "or is misconfigured, so there is no verdict" % returncode}
    if failed:
        names = failing_names(text)
        exception = any(p.search(text) for p in EXCEPTIONS)
        assertion = any(p.search(text) for p in ASSERTIONS)
        how = "exception" if exception and not assertion else "assertion"
        reason = "a test failed on its assertion" if how == "assertion" else (
            "a test failed on an exception, not an assertion: the code under test is missing or broken. "
            "Add the smallest stub so the test fails on its assertion, then check again")
        return {"state": RED, "reason": reason, "failed_how": how, "failing": names}
    return {"state": ERRORED, "reason": "the runner exited %s, which is not a test verdict" % returncode}


def failing_names(text: str) -> List[str]:
    names: List[str] = []
    for pattern in FAILING_NAMES:
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if name and name not in names and name.rstrip(":") != "failing tests":
                names.append(name)
    return names[:20]


def detect(root: Path) -> List[str]:
    """The test commands the repository declares, most likely first. Never invents one."""
    found: List[str] = []
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            script = (json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}).get("test", "")
        except ValueError:
            script = ""
        if script and "no test specified" not in script:
            found.append("npm test --silent")
    python_markers = [root / n for n in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "setup.py")]
    has_python_tests = any(root.glob("test_*.py")) or any(root.glob("tests/**/test_*.py")) or any(
        root.glob("**/tests/test_*.py"))
    if has_python_tests or any(p.is_file() for p in python_markers):
        uses_pytest = (root / "pytest.ini").is_file() or any(
            p.is_file() and "pytest" in p.read_text(encoding="utf-8", errors="ignore") for p in python_markers)
        if uses_pytest or importlib.util.find_spec("pytest"):
            found.append("python -m pytest -q")
        elif has_python_tests:
            found.append("python -m unittest discover -s tests" if (root / "tests").is_dir()
                         else "python -m unittest discover")
    if (root / "go.mod").is_file():
        found.append("go test ./...")
    if (root / "Cargo.toml").is_file():
        found.append("cargo test")
    if any(root.glob("*.sln")) or any(root.glob("*.csproj")):
        found.append("dotnet test")
    if (root / "pom.xml").is_file():
        found.append("mvn -q test")
    if (root / "gradlew").is_file():
        found.append("./gradlew test")
    return found


def run(command: str, cwd: Optional[str], timeout: int) -> Dict[str, Any]:
    if not command or not command.strip():
        return {"state": UNUSABLE, "reason": "no test command: pass --cmd, or declare one in the repo",
                "command": command or "", "exit_code": None, "output_tail": ""}
    try:
        done = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, check=False,
                              timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"state": ERRORED, "reason": "the run timed out after %ds" % timeout, "command": command,
                "exit_code": None, "output_tail": ""}
    output = (done.stdout or "") + (done.stderr or "")
    result = classify(done.returncode, output)
    result.update(command=command, exit_code=done.returncode,
                  output_tail="\n".join(output.rstrip().splitlines()[-TAIL:]))
    return result


def judge(result: Dict[str, Any], expect: Optional[str]) -> int:
    state = result["state"]
    if state in (UNUSABLE, ERRORED) or not expect:
        return EXIT[state]
    wanted = expect.upper()
    result["expected"] = wanted
    result["met"] = state == wanted
    if not result["met"]:
        result["advice"] = {
            (RED, GREEN): "the new test passed straight away, or was not collected: it specifies nothing yet. "
                          "Make it fail first: check it runs, then that it asserts the missing behaviour",
            (GREEN, RED): "still red. Keep to the smallest change that passes; never edit the test to meet the code. "
                          "In a refactor, revert to the last green instead of fixing forward",
        }.get((wanted, state), "")
    elif state == RED and result.get("failed_how") == "exception":
        result["advice"] = "red, but on an exception: add a stub and check again before writing the real code"
    return 0 if result["met"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("detect", help="the test command this repository declares")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("check", help="run the tests and name the state")
    p.add_argument("--cmd", dest="command", help="the test command; scope it to the tests in play")
    p.add_argument("--expect", choices=("red", "green"), help="fail unless the run is in this state")
    p.add_argument("--root", default=".")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "detect":
        commands = detect(Path(args.root))
        if args.json:
            print(json.dumps({"commands": commands}))
        else:
            print("\n".join(commands) if commands else "no test command found: pass --cmd to check")
        return 0 if commands else 2

    command = args.command
    if not command:
        found = detect(Path(args.root))
        command = found[0] if found else ""
    result = run(command, args.root, args.timeout)
    code = judge(result, args.expect)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        line = "%s: %s" % (result["state"], result["reason"])
        if args.expect:
            line += "  [expected %s: %s]" % (args.expect.upper(), "met" if result.get("met") else "NOT met")
        print(line)
        if result.get("failing"):
            print("failing: " + "; ".join(result["failing"]))
        if result.get("advice"):
            print("next: " + result["advice"])
        if result["state"] in (ERRORED, UNUSABLE) or (args.expect and not result.get("met")):
            print("--- %s (exit %s)\n%s" % (result.get("command"), result.get("exit_code"), result.get("output_tail")))
    return code


if __name__ == "__main__":
    sys.exit(main())
