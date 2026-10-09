#!/usr/bin/env python3
"""The checks a generated plugin must pass before it counts as done.

    gate.py run NAME      run every step in order, write .plugin-dev/NAME/gate.json
    gate.py status NAME   say whether the last run still describes the plugin on disk
    gate.py close NAME    end the build session (refused while the gate is failing or stale)

Steps, in order. The run stops at the first failure and prints that step's
output; later steps are reported as not run.

    markers          no `TODO(plugin-developer)` stub is left anywhere (a marker
                     written inside backticks is documentation, not a stub)
    trace            requirements <-> components <-> tests coverage (req_trace.py)
    readme           the README's components table matches requirements.json
    validate         python -m tools.apkit validate --plugin NAME --strict
    build            python -m tools.apkit build --plugin NAME  (degradations recorded)
    claude-validate  claude plugin validate dist/claude-code/NAME --strict --json
    load             claude --plugin-dir dist/claude-code/NAME plugin list --json
    inventory        claude ... plugin details NAME@inline lists what the source declares
    tests            python -m tools.apkit test --plugin NAME
    mcp              mcp_smoke.py, when the plugin declares MCP servers

Exits:

    0  pass        every step passed
    1  fail        a step failed -- its output says why
    2  unusable    not in the repo, or plugins/NAME does not exist
    3  incomplete  nothing failed, but a step could not run here (usually the
                   claude CLI is missing or restricted). Not a pass: say which
                   steps were not checked.

`status` exits 0 when the last run passed and still matches the plugin, 1 when it
failed, 3 when it was incomplete, and 4 when it is missing or stale.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = Path(__file__).resolve().parent
_ANALYSIS = HERE.parents[1] / "requirements-analysis" / "scripts"
for _directory in (HERE, _ANALYSIS):
    if _directory.is_dir() and str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

import mcp_smoke  # noqa: E402
import req_trace  # noqa: E402

STATE_DIR = ".plugin-dev"
# Built, not spelled out, so this file does not trip its own check.
MARKER = "TODO" + "(plugin-developer)"
STUB = re.compile(r"(?<!`)" + re.escape(MARKER))
CLAUDE_TIMEOUT = 180
RESTRICTED = "only `claude -p"

PASS, FAIL, SKIP, UNAVAILABLE, NOT_RUN = "pass", "fail", "skip", "unavailable", "not run"


# ---- locations ---------------------------------------------------------------

def find_root(start: Path) -> Optional[Path]:
    here = Path(start).resolve()
    for candidate in [here] + list(here.parents):
        if (candidate / "plugins").is_dir() and (candidate / "tools" / "apkit").is_dir():
            return candidate
    return None


def state_dir(root: Path, name: str) -> Path:
    return Path(root) / STATE_DIR / name


def gate_file(root: Path, name: str) -> Path:
    return state_dir(root, name) / "gate.json"


def active_file(root: Path) -> Path:
    return Path(root) / STATE_DIR / "active.json"


def now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def plugin_files(plugin_dir: Path) -> List[Path]:
    files = []
    for path in sorted(Path(plugin_dir).rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(plugin_dir).parts
        if "__pycache__" in parts or path.suffix in (".pyc", ".pyo") or path.name.endswith(".bak"):
            continue
        files.append(path)
    return files


def fingerprint(plugin_dir: Path) -> str:
    """A hash of the plugin's content, so an edit after a run makes the run stale."""
    digest = hashlib.sha256()
    for path in plugin_files(plugin_dir):
        digest.update(path.relative_to(plugin_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


# ---- session ------------------------------------------------------------------

def open_session(root: Path, name: str) -> None:
    path = active_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plugin": name, "opened": now()}, indent=2) + "\n", encoding="utf-8")


def active(root: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(active_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("plugin") else None


def freshness(root: Path, name: str) -> Tuple[str, str]:
    """('pass' | 'incomplete' | 'fail' | 'stale' | 'missing', reason)."""
    plugin_dir = Path(root) / "plugins" / name
    try:
        record = json.loads(gate_file(root, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "missing", "the gate has not been run for %s" % name
    if not plugin_dir.is_dir():
        return "missing", "plugins/%s does not exist" % name
    if record.get("fingerprint") != fingerprint(plugin_dir):
        return "stale", "plugins/%s changed after the last gate run (%s)" % (name, record.get("finished"))
    result = record.get("result")
    if result == PASS:
        return "pass", "the gate passed at %s" % record.get("finished")
    failed = [s["name"] for s in record.get("steps", []) if s.get("status") == FAIL]
    if result == "incomplete":
        missing = [s["name"] for s in record.get("steps", []) if s.get("status") == UNAVAILABLE]
        return "incomplete", "nothing failed, but not checked here: %s" % ", ".join(missing)
    return "fail", "the gate failed at: %s" % (", ".join(failed) or "unknown step")


# ---- step helpers -------------------------------------------------------------

def run(argv: List[str], cwd: Path, timeout: Optional[int] = None) -> Tuple[int, str]:
    try:
        done = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ss: %s" % (timeout, " ".join(argv))
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def apkit(root: Path, *args: str) -> Tuple[int, str]:
    return run([sys.executable, "-m", "tools.apkit"] + list(args), root)


def claude_unavailable(code: int, output: str) -> bool:
    return code == 127 or RESTRICTED in output


def json_in(text: str) -> Any:
    """The JSON value in a command's output, ignoring anything printed around it."""
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                continue
    raise ValueError("no JSON found in output")


def parse_degradations(output: str) -> List[Dict[str, str]]:
    """'skip <component>: <reason>' lines from apkit build, with their target."""
    found: List[Dict[str, str]] = []
    target = ""
    for line in output.splitlines():
        built = re.match(r"\s*built \S+ -> dist/([^/\s]+)/", line)
        if built:
            target = built.group(1)
            continue
        skipped = re.match(r"\s+skip ([^:]+): (.*)$", line)
        if skipped:
            found.append({"target": target, "component": skipped.group(1).strip(),
                          "reason": skipped.group(2).strip()})
    return found


INVENTORY_LINE = re.compile(r"^\s+(Skills|Agents|Hooks|MCP servers|LSP servers) \((\d+)\)\s*(.*)$")


def parse_inventory(text: str) -> Optional[Dict[str, Set[str]]]:
    """`claude plugin details` text -> {'Skills': {...}, ...}; None if the shape is not recognised."""
    if "Component inventory" not in text:
        return None
    found: Dict[str, Set[str]] = {}
    for line in text.splitlines():
        match = INVENTORY_LINE.match(line)
        if not match:
            continue
        label, count, rest = match.group(1), int(match.group(2)), match.group(3)
        names = rest.split("  ")[0].strip() if count else ""
        found[label] = {n.strip() for n in names.split(",") if n.strip()}
    return found or None


def expected_inventory(plugin_dir: Path) -> Dict[str, Set[str]]:
    disk = req_trace.on_disk(plugin_dir)
    return {
        "Skills": {n for t, n in disk if t in ("skill", "command")},
        "Agents": {n for t, n in disk if t == "agent"},
        "Hooks": {n for t, n in disk if t == "hook"},
        "MCP servers": {n for t, n in disk if t == "mcp"},
    }


# ---- the gate -----------------------------------------------------------------

def gate(root: Path, name: str, claude: Optional[str] = "claude") -> Dict[str, Any]:
    plugin_dir = Path(root) / "plugins" / name
    requirements_file = plugin_dir / "requirements.json"
    dist = Path(root) / "dist" / "claude-code" / name
    steps: List[Dict[str, Any]] = []
    record: Dict[str, Any] = {"plugin": name, "started": now(), "steps": steps, "degradations": []}
    claude_bin = shutil.which(claude) if claude else None

    def add(step: str, status: str, detail: str = "") -> bool:
        steps.append({"name": step, "status": status, "detail": detail})
        return status != FAIL

    def step_markers() -> bool:
        left = []
        for path in plugin_files(plugin_dir):
            try:
                if STUB.search(path.read_text(encoding="utf-8", errors="ignore")):
                    left.append(path.relative_to(plugin_dir).as_posix())
            except OSError:
                continue
        if left:
            return add("markers", FAIL, "stubs still to write: " + ", ".join(left))
        return add("markers", PASS)

    def step_trace() -> bool:
        try:
            data = req_trace.load(requirements_file)
        except req_trace.Unusable as exc:
            return add("trace", FAIL, str(exc))
        record["_data"] = data
        if not data.get("requirements") or not data.get("components"):
            return add("trace", FAIL, "requirements.json has no requirements or no components")
        problems = req_trace.issues(data, plugin_dir)
        if problems:
            return add("trace", FAIL, "\n".join(problems))
        return add("trace", PASS, "%d requirement(s), %d component(s)" % (
            len(data["requirements"]), len(data["components"])))

    def step_readme() -> bool:
        current = req_trace.readme_is_current(plugin_dir / "README.md", record["_data"])
        if current is None:
            return add("readme", FAIL, "README.md has no components table -- run req_trace.py table --write-readme")
        if not current:
            return add("readme", FAIL, "README.md components table is out of date -- run req_trace.py table --write-readme")
        return add("readme", PASS)

    def step_validate() -> bool:
        code, out = apkit(root, "validate", "--plugin", name, "--strict")
        return add("validate", PASS if code == 0 else FAIL, tail(out))

    def step_build() -> bool:
        code, out = apkit(root, "build", "--plugin", name)
        record["degradations"] = parse_degradations(out)
        if code != 0:
            return add("build", FAIL, tail(out))
        return add("build", PASS, "%d degradation(s) recorded" % len(record["degradations"]))

    def step_claude_validate() -> bool:
        if not claude_bin:
            return add("claude-validate", UNAVAILABLE, "claude CLI not found")
        code, out = run([claude_bin, "plugin", "validate", str(dist), "--strict", "--json"], root, CLAUDE_TIMEOUT)
        if claude_unavailable(code, out):
            return add("claude-validate", UNAVAILABLE, "claude CLI here cannot run plugin commands: " + tail(out, 2))
        try:
            report = json_in(out)
        except ValueError:
            return add("claude-validate", FAIL if code else UNAVAILABLE, tail(out))
        ok = code == 0 and isinstance(report, dict) and report.get("success") is True
        return add("claude-validate", PASS if ok else FAIL, "" if ok else json.dumps(report, indent=2)[:4000])

    def step_load() -> bool:
        if not claude_bin:
            return add("load", UNAVAILABLE, "claude CLI not found")
        code, out = run([claude_bin, "--plugin-dir", str(dist), "plugin", "list", "--json"], root, CLAUDE_TIMEOUT)
        if claude_unavailable(code, out):
            return add("load", UNAVAILABLE, tail(out, 2))
        try:
            listed = json_in(out)
        except ValueError:
            return add("load", UNAVAILABLE, "could not read plugin list output: " + tail(out, 5))
        entry = next((p for p in listed if isinstance(p, dict) and p.get("id") == name + "@inline"), None)
        if entry is None:
            return add("load", FAIL, "%s@inline is not in the loaded plugins:\n%s" % (name, tail(out)))
        if entry.get("enabled") is False:
            return add("load", FAIL, "%s@inline loaded but is disabled" % name)
        return add("load", PASS, "%s@inline %s" % (name, entry.get("version", "")))

    def step_inventory() -> bool:
        if not claude_bin:
            return add("inventory", UNAVAILABLE, "claude CLI not found")
        code, out = run([claude_bin, "--plugin-dir", str(dist), "plugin", "details", name + "@inline"],
                        root, CLAUDE_TIMEOUT)
        if claude_unavailable(code, out):
            return add("inventory", UNAVAILABLE, tail(out, 2))
        actual = parse_inventory(out)
        if actual is None:
            return add("inventory", UNAVAILABLE, "plugin details output not recognised: " + tail(out, 5))
        missing = []
        for label, names in expected_inventory(plugin_dir).items():
            gone = names - actual.get(label, set())
            if gone:
                missing.append("%s: %s" % (label, ", ".join(sorted(gone))))
        if missing:
            return add("inventory", FAIL, "declared in source but not loaded by Claude Code -- " + "; ".join(missing))
        return add("inventory", PASS)

    def step_tests() -> bool:
        if not list(plugin_dir.glob("tests/test_*.py")):
            return add("tests", SKIP, "no tests -- the plugin has no scripts or MCP server")
        code, out = apkit(root, "test", "--plugin", name)
        return add("tests", PASS if code == 0 else FAIL, tail(out, 40))

    def step_mcp() -> bool:
        if not (plugin_dir / "mcp" / "servers.json").is_file():
            return add("mcp", SKIP, "no MCP servers declared")
        try:
            results = mcp_smoke.smoke(plugin_dir)
        except mcp_smoke.Unusable as exc:
            return add("mcp", FAIL, str(exc))
        verdict = mcp_smoke.verdict(results)
        detail = "\n".join("%s %s: %s" % (r["status"], r["server"], r["detail"]) for r in results)
        status = {0: PASS, 1: FAIL}.get(verdict, UNAVAILABLE)
        return add("mcp", status, detail)

    order = [
        ("markers", step_markers), ("trace", step_trace), ("readme", step_readme),
        ("validate", step_validate), ("build", step_build),
        ("claude-validate", step_claude_validate), ("load", step_load),
        ("inventory", step_inventory), ("tests", step_tests), ("mcp", step_mcp),
    ]
    stopped = False
    for step_name, step in order:
        if stopped:
            steps.append({"name": step_name, "status": NOT_RUN, "detail": ""})
            continue
        if not step():
            stopped = True

    record.pop("_data", None)
    statuses = [s["status"] for s in steps]
    if FAIL in statuses:
        record["result"] = FAIL
    elif UNAVAILABLE in statuses:
        record["result"] = "incomplete"
    else:
        record["result"] = PASS
    record["finished"] = now()
    record["fingerprint"] = fingerprint(plugin_dir)
    return record


def report(record: Dict[str, Any]) -> str:
    lines = ["gate %s: %s" % (record["plugin"], record["result"].upper())]
    for step in record["steps"]:
        lines.append("  %-16s %s" % (step["name"], step["status"]))
        if step["status"] in (FAIL, UNAVAILABLE) and step.get("detail"):
            for line in step["detail"].splitlines():
                lines.append("      " + line)
    if record.get("degradations"):
        lines.append("  degradations (what other harnesses cannot express):")
        for d in record["degradations"]:
            lines.append("      %s: %s -- %s" % (d["target"], d["component"], d["reason"]))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("name")
    p.add_argument("--claude", default=os.environ.get("PLUGIN_DEV_CLAUDE", "claude"),
                   help="claude CLI to use (env PLUGIN_DEV_CLAUDE)")
    p.add_argument("--no-claude", action="store_true", help="skip the claude CLI steps (reported, not passed)")
    p = sub.add_parser("status")
    p.add_argument("name")
    p = sub.add_parser("close")
    p.add_argument("name")
    p.add_argument("--abandon", action="store_true", help="close even though the gate is not passing")
    for p in sub.choices.values():
        p.add_argument("--root", type=Path)
    args = parser.parse_args(argv)

    root = args.root or find_root(Path.cwd())
    if root is None:
        print("UNUSABLE: not inside the plugins repo (no plugins/ and tools/apkit/ above here)", file=sys.stderr)
        return 2
    plugin_dir = Path(root) / "plugins" / args.name

    if args.cmd == "run":
        if not plugin_dir.is_dir():
            print("UNUSABLE: plugins/%s does not exist" % args.name, file=sys.stderr)
            return 2
        record = gate(Path(root), args.name, None if args.no_claude else args.claude)
        path = gate_file(root, args.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(report(record))
        return {PASS: 0, FAIL: 1}.get(record["result"], 3)

    state, reason = freshness(Path(root), args.name)
    if args.cmd == "status":
        print("%s: %s" % (state.upper(), reason))
        return {"pass": 0, "fail": 1, "incomplete": 3}.get(state, 4)

    session = active(Path(root))
    if not session or session.get("plugin") != args.name:
        print("no open build session for %s" % args.name)
        return 0
    if state not in ("pass", "incomplete") and not args.abandon:
        print("REFUSED: %s. Fix it and re-run the gate, or close with --abandon and say so." % reason)
        return 1
    active_file(root).unlink()
    print("closed the build session for %s (%s)" % (args.name, state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
