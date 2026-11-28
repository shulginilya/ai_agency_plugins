#!/usr/bin/env python3
"""Discover the checks this repository already runs, and optionally run them.

The point is to verify a change the way the project verifies it, instead of
guessing at `npm test`. Manifests are read for what they actually declare; a
check is only reported when the repo really has it.

Usage:
    python scripts/verify.py                  # list the checks, in order
    python scripts/verify.py --json
    python scripts/verify.py --run            # run them, stop at the first failure
    python scripts/verify.py --root ../api --only test

Exits 0 when checks are listed or all pass, 1 when a run fails, and 2 when no
project manifest was found (nothing to verify is a different answer from
everything passed).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# Slowest-feedback-last: a type error should surface before a full build does.
ORDER = ["format", "typecheck", "lint", "test", "build"]

NODE_SCRIPT_KINDS = {
    "format": ("format:check", "format", "prettier:check"),
    "typecheck": ("typecheck", "type-check", "tsc"),
    "lint": ("lint", "eslint"),
    "test": ("test", "test:unit", "jest", "vitest"),
    "build": ("build",),
}

LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
]

MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+):(?!=)", re.M)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _node_runner(root: Path) -> str:
    for lockfile, runner in LOCKFILES:
        if (root / lockfile).is_file():
            return runner
    return "npm"


def _node_checks(root: Path) -> List[Dict[str, str]]:
    manifest = _read_json(root / "package.json")
    scripts = manifest.get("scripts")
    if not isinstance(scripts, dict):
        return []
    runner = _node_runner(root)
    found: List[Dict[str, str]] = []
    for kind in ORDER:
        for candidate in NODE_SCRIPT_KINDS[kind]:
            if candidate in scripts:
                found.append(
                    {
                        "kind": kind,
                        "command": "%s run %s" % (runner, candidate),
                        "source": "package.json scripts.%s" % candidate,
                    }
                )
                break
    return found


def _python_checks(root: Path) -> List[Dict[str, str]]:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.is_file() else ""
    has_project = bool(text) or (root / "setup.cfg").is_file() or (root / "tox.ini").is_file()
    if not has_project:
        return []
    found: List[Dict[str, str]] = []
    if "[tool.mypy]" in text:
        found.append({"kind": "typecheck", "command": "mypy .", "source": "pyproject [tool.mypy]"})
    if "[tool.ruff" in text:
        found.append({"kind": "lint", "command": "ruff check .", "source": "pyproject [tool.ruff]"})
    if "[tool.pytest" in text or (root / "tests").is_dir() or (root / "conftest.py").is_file():
        found.append({"kind": "test", "command": "pytest", "source": "pytest layout"})
    return found


def _make_checks(root: Path) -> List[Dict[str, str]]:
    makefile = root / "Makefile"
    if not makefile.is_file():
        return []
    try:
        targets = set(MAKE_TARGET_RE.findall(makefile.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return []
    return [
        {"kind": kind, "command": "make %s" % kind, "source": "Makefile target"}
        for kind in ORDER
        if kind in targets
    ]


def _simple_checks(root: Path) -> List[Dict[str, str]]:
    if (root / "go.mod").is_file():
        return [
            {"kind": "lint", "command": "go vet ./...", "source": "go.mod"},
            {"kind": "test", "command": "go test ./...", "source": "go.mod"},
            {"kind": "build", "command": "go build ./...", "source": "go.mod"},
        ]
    if (root / "Cargo.toml").is_file():
        return [
            {"kind": "lint", "command": "cargo clippy", "source": "Cargo.toml"},
            {"kind": "test", "command": "cargo test", "source": "Cargo.toml"},
        ]
    return []


def discover(root: Path) -> List[Dict[str, str]]:
    """Every check the repo declares, de-duplicated by kind, in feedback order."""
    checks: List[Dict[str, str]] = []
    for finder in (_node_checks, _python_checks, _simple_checks, _make_checks):
        checks.extend(finder(root))
    best: Dict[str, Dict[str, str]] = {}
    for check in checks:
        best.setdefault(check["kind"], check)
    return [best[kind] for kind in ORDER if kind in best]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository directory (default: cwd)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--run", action="store_true", help="run the checks in order")
    parser.add_argument("--only", action="append", choices=ORDER, help="restrict to these kinds")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("not a directory: %s\n" % root)
        return 2

    checks = discover(root)
    if args.only:
        checks = [check for check in checks if check["kind"] in args.only]

    if not checks:
        sys.stderr.write(
            "no checks found in %s — no package.json scripts, pyproject tooling, "
            "Makefile targets, go.mod or Cargo.toml\n" % root
        )
        return 2

    if args.json:
        print(json.dumps(checks, indent=2))
        return 0

    if not args.run:
        for check in checks:
            print("%-9s %-28s (%s)" % (check["kind"], check["command"], check["source"]))
        return 0

    for check in checks:
        print("== %s: %s" % (check["kind"], check["command"]))
        sys.stdout.flush()
        result = subprocess.run(check["command"], shell=True, cwd=str(root), env=os.environ.copy())
        if result.returncode != 0:
            print("FAILED at %s (exit %d)" % (check["kind"], result.returncode))
            return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
