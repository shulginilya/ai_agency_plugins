#!/usr/bin/env python3
"""Discover how this repository is tested, and run a reproduction against it.

Usage:
    python scripts/repro.py --discover
    python scripts/repro.py --discover --json
    python scripts/repro.py --test "order total"          # run one matching test
    python scripts/repro.py --cmd "npm test -- cart" --times 10
    python scripts/repro.py --test "order total" --print  # show the command, run nothing

Discovery reads what the repo declares — package.json scripts and its lockfile,
pyproject/pytest config, Makefile targets, go.mod, Cargo.toml — rather than
guessing a command. "No checks declared" (exit 2) is a different answer from
"the checks fail", and the caller needs to be able to tell them apart.

Exit codes:
    0   every run passed
    1   every run failed  (a deterministic reproduction)
    2   nothing to run: no declared checks, or bad usage
    3   mixed results     (an intermittent reproduction)
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
]

# package.json script names worth surfacing, in the order a diagnosis wants them
SCRIPT_KEYS = ["test", "test:unit", "typecheck", "tsc", "lint", "check", "build"]

# how to select a single test, per framework
SELECTORS = {
    "pytest": '-k "{expr}"',
    "jest": '-t "{expr}"',
    "vitest": '-t "{expr}"',
    "mocha": '--grep "{expr}"',
    "go": "-run {expr}",
    "cargo": "{expr}",
    "unittest": '-k "{expr}"',
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _package_manager(root: Path) -> str:
    for name, manager in LOCKFILES:
        if (root / name).is_file():
            return manager
    return "npm"


def _framework(text: str) -> Optional[str]:
    for name in ("vitest", "jest", "mocha", "pytest"):
        if name in text:
            return name
    return None


def discover(root: Path) -> Dict[str, Any]:
    """Return the checks this repository declares, with their source."""
    commands: List[Dict[str, str]] = []
    framework: Optional[str] = None
    manager: Optional[str] = None

    package_json = root / "package.json"
    if package_json.is_file():
        manager = _package_manager(root)
        try:
            data = json.loads(_read(package_json) or "{}")
        except ValueError:
            data = {}
        scripts = data.get("scripts") or {}
        if isinstance(scripts, dict):
            for key in SCRIPT_KEYS:
                if key in scripts:
                    commands.append(
                        {
                            "kind": "test" if key.startswith("test") else key,
                            "command": "%s run %s" % (manager, key),
                            "source": "package.json scripts.%s" % key,
                        }
                    )
            framework = _framework(" ".join(str(v) for v in scripts.values()))
        if framework is None:
            deps = json.dumps(data.get("devDependencies") or {}) + json.dumps(
                data.get("dependencies") or {}
            )
            framework = _framework(deps)

    py_config = "".join(
        _read(root / name)
        for name in ("pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini")
    )
    if py_config:
        if "pytest" in py_config or (root / "pytest.ini").is_file():
            framework = framework or "pytest"
            commands.append(
                {"kind": "test", "command": "pytest -q", "source": "pytest configuration"}
            )
        if "[tool.mypy]" in py_config:
            commands.append({"kind": "typecheck", "command": "mypy .", "source": "pyproject [tool.mypy]"})
        if "[tool.ruff" in py_config:
            commands.append({"kind": "lint", "command": "ruff check .", "source": "pyproject [tool.ruff]"})

    has_test = any(entry["kind"] == "test" for entry in commands)
    if not has_test and (root / "tests").is_dir() and list(root.glob("tests/test_*.py")):
        framework = framework or "unittest"
        commands.append(
            {
                "kind": "test",
                "command": "python -m unittest discover -s tests",
                "source": "tests/ directory",
            }
        )

    makefile = _read(root / "Makefile")
    if makefile:
        for target in re.findall(r"(?m)^([a-zA-Z][\w.-]*):(?!=)", makefile):
            if target in ("test", "check", "lint", "typecheck", "build"):
                commands.append(
                    {
                        "kind": "test" if target == "test" else target,
                        "command": "make %s" % target,
                        "source": "Makefile target %s" % target,
                    }
                )

    if (root / "go.mod").is_file():
        framework = framework or "go"
        commands.append({"kind": "test", "command": "go test ./...", "source": "go.mod"})
    if (root / "Cargo.toml").is_file():
        framework = framework or "cargo"
        commands.append({"kind": "test", "command": "cargo test", "source": "Cargo.toml"})

    seen = set()
    unique = []
    for entry in commands:
        if entry["command"] in seen:
            continue
        seen.add(entry["command"])
        unique.append(entry)

    return {
        "root": str(root),
        "package_manager": manager,
        "framework": framework,
        "commands": unique,
    }


def single_test_command(found: Dict[str, Any], expr: str) -> Optional[str]:
    """Build a command that runs only the tests matching expr."""
    framework = found.get("framework")
    selector = SELECTORS.get(str(framework))
    if selector is None:
        return None
    flag = selector.format(expr=expr)

    if framework == "pytest":
        return "pytest -x -q %s" % flag
    if framework == "go":
        return "go test ./... %s" % flag
    if framework == "cargo":
        return "cargo test %s" % flag
    if framework == "unittest":
        return "python -m unittest discover -s tests %s" % flag

    tests = [c for c in found.get("commands", []) if c["kind"] == "test"]
    base = tests[0]["command"] if tests else "%s test" % (found.get("package_manager") or "npm")
    return "%s -- %s" % (base, flag)


def run_times(command: str, cwd: Path, times: int, quiet: bool) -> Dict[str, Any]:
    outcomes: List[int] = []
    first_failure = ""
    for attempt in range(times):
        result = subprocess.run(
            command, shell=True, cwd=str(cwd), check=False,
            capture_output=quiet or times > 1, text=True,
        )
        outcomes.append(result.returncode)
        if result.returncode != 0 and not first_failure and result.stdout is not None:
            first_failure = ((result.stdout or "") + (result.stderr or ""))[-4000:]
        if times > 1:
            sys.stderr.write("run %d/%d: %s\n" % (attempt + 1, times, "pass" if result.returncode == 0 else "FAIL"))
    failures = sum(1 for code in outcomes if code != 0)
    return {
        "command": command,
        "runs": times,
        "failures": failures,
        "exit_codes": outcomes,
        "verdict": "deterministic-pass" if failures == 0
        else "deterministic-fail" if failures == times
        else "intermittent",
        "output": first_failure,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="repository directory (default: .)")
    parser.add_argument("--discover", action="store_true", help="list the checks this repo declares")
    parser.add_argument("--test", metavar="EXPR", help="run only the tests matching EXPR")
    parser.add_argument("--cmd", help="run this exact command as the reproduction")
    parser.add_argument("--times", type=int, default=1, help="repeat the run N times to measure flakiness")
    parser.add_argument("--print", dest="dry_run", action="store_true", help="print the command, run nothing")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    root = Path(args.cwd).resolve()
    if not root.is_dir():
        sys.stderr.write("not a directory: %s\n" % root)
        return 2
    if args.times < 1:
        sys.stderr.write("--times must be at least 1\n")
        return 2

    found = discover(root)

    if args.discover or (not args.test and not args.cmd):
        if args.json:
            print(json.dumps(found, indent=2))
        else:
            if not found["commands"]:
                print("no checks declared in %s" % root)
            else:
                print("package manager: %s" % (found["package_manager"] or "-"))
                print("test framework:  %s" % (found["framework"] or "unknown"))
                for entry in found["commands"]:
                    print("  %-10s %-40s (%s)" % (entry["kind"], entry["command"], entry["source"]))
        return 0 if found["commands"] else 2

    command = args.cmd
    if command is None:
        command = single_test_command(found, args.test)
        if command is None:
            sys.stderr.write(
                "cannot build a single-test command: no test framework detected.\n"
                "Pass the command explicitly with --cmd.\n"
            )
            return 2

    if args.dry_run:
        print(command)
        return 0

    report = run_times(command, root, args.times, quiet=args.json)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n%s: %d/%d runs failed (%s)" % (
            shlex.quote(command), report["failures"], report["runs"], report["verdict"]
        ))
        if report["verdict"] == "intermittent":
            print("Intermittent. Do not diagnose this as a logic bug until the rate is explained;")
            print("see references/reproduction.md for the rate-to-mechanism table.")
        if report["output"] and args.times > 1:
            print("\n--- first failing output (tail) ---\n%s" % report["output"])

    if report["failures"] == 0:
        return 0
    if report["failures"] == report["runs"]:
        return 1
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
