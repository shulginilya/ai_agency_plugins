#!/usr/bin/env python3
"""Check that requirements and components cover each other, both ways.

Reads the `components` list of a requirements file (see the
requirements-analysis skill) and answers four questions:

    * Is every requirement covered by at least one component?
    * Does every component cover at least one requirement, with a reason?
    * Is every hook, MCP server and script justified by a requirement of a
      kind that actually needs one? (A hook for a user-started action is
      over-building; a command would do.)
    * Is every script and MCP server verified by a test that names it?

With --plugin-dir it also reads the plugin on disk, so a component that was
built but never planned -- or planned but never built -- is caught.

    req_trace.py check FILE [--plugin-dir plugins/NAME]
    req_trace.py table FILE [--write-readme plugins/NAME/README.md]

`check` exits:

    0  complete     coverage holds in both directions
    1  gaps         at least one rule is broken -- each is listed
    2  unusable     the file cannot be read
    3  cannot tell  nothing to check yet (no requirements, or no components planned)

The component file name is req_trace.py, not trace.py, because this directory
goes on sys.path and `trace` is a standard-library module.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = Path(__file__).resolve().parent
_ANALYSIS = HERE.parents[1] / "requirements-analysis" / "scripts"
if _ANALYSIS.is_dir() and str(_ANALYSIS) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS))

try:
    import requirements as reqs  # type: ignore
except ImportError:  # installed without its sibling skill
    reqs = None

TYPES = ("skill", "command", "agent", "hook", "mcp", "script", "test")

# A component of this type is only justified when it covers at least one
# requirement of one of these kinds. Types not listed may cover any kind.
JUSTIFIED_BY = {
    "hook": {"event"},
    "mcp": {"integration"},
    "script": {"computation", "integration", "event"},
}

README_START = "<!-- plugin-developer:components -->"
README_END = "<!-- /plugin-developer:components -->"


class Unusable(Exception):
    pass


def load(path: Path) -> Dict[str, Any]:
    if reqs is not None:
        try:
            return reqs.load(path)
        except reqs.Unusable as exc:
            raise Unusable(str(exc))
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unusable("cannot read %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("requirements"), list):
        raise Unusable("%s is not a requirements file" % path)
    return data


def _components(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in data.get("components") or [] if isinstance(c, dict)]


def key(component: Dict[str, Any]) -> Tuple[str, str]:
    return (str(component.get("type", "")), str(component.get("name", "")).replace("\\", "/"))


def on_disk(plugin_dir: Path) -> Set[Tuple[str, str]]:
    """Every component the plugin directory actually contains."""
    root = Path(plugin_dir)
    found: Set[Tuple[str, str]] = set()
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        found.add(("skill", skill.parent.name))
    for command in sorted((root / "commands").glob("*.md")):
        found.add(("command", command.stem))
    for agent in sorted((root / "agents").glob("*.md")):
        found.add(("agent", agent.stem))
    hooks_file = root / "hooks" / "hooks.json"
    if hooks_file.is_file():
        try:
            hooks = json.loads(hooks_file.read_text(encoding="utf-8")).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            hooks = {}
        for event in hooks:
            found.add(("hook", str(event)))
    servers_file = root / "mcp" / "servers.json"
    if servers_file.is_file():
        try:
            servers = json.loads(servers_file.read_text(encoding="utf-8")).get("mcpServers") or {}
        except (OSError, ValueError, AttributeError):
            servers = {}
        for server in servers:
            found.add(("mcp", str(server)))
    scripts = list(root.glob("skills/*/scripts/*.py")) + list(root.glob("scripts/*.py"))
    for script in sorted(scripts):
        found.add(("script", script.relative_to(root).as_posix()))
    for test in sorted(root.glob("tests/test_*.py")):
        found.add(("test", test.relative_to(root).as_posix()))
    return found


def _mentions(test_text: str, verified: Tuple[str, str]) -> bool:
    kind, name = verified
    if kind == "mcp":
        return "server.py" in test_text or "servers.json" in test_text or name in test_text
    stem = Path(name).stem
    return Path(name).name in test_text or stem in test_text


def issues(data: Dict[str, Any], plugin_dir: Optional[Path] = None) -> List[str]:
    found: List[str] = []
    requirements = {
        str(r.get("id")): r for r in data.get("requirements") or [] if isinstance(r, dict)
    }
    components = _components(data)
    planned = {key(c) for c in components}

    covered: Dict[str, List[str]] = {rid: [] for rid in requirements}
    verified: Set[Tuple[str, str]] = set()

    for component in components:
        ctype, name = key(component)
        label = "%s %s" % (ctype, name or "<unnamed>")
        if ctype not in TYPES:
            found.append("%s: type must be one of %s" % (label, ", ".join(TYPES)))
            continue
        if not name:
            found.append("%s: no name" % label)
        covers = [str(r) for r in component.get("covers") or []]
        why = str(component.get("why", "")).strip()
        for rid in covers:
            if rid not in requirements:
                found.append("%s: covers %s, which is not a requirement" % (label, rid))
            elif ctype != "test":
                covered[rid].append(label)
        if ctype == "test":
            targets = [str(v).replace("\\", "/") for v in component.get("verifies") or []]
            if not targets:
                found.append("%s: verifies nothing -- list the scripts or MCP servers it tests" % label)
            for target in targets:
                matched = [k for k in planned if k[1] == target and k[0] in ("script", "mcp")]
                if not matched:
                    found.append("%s: verifies %s, which is not a planned script or MCP server" % (label, target))
                verified.update(matched)
            continue
        if not covers:
            found.append("%s: covers no requirement -- remove it, or say which one needs it" % label)
        if not why:
            found.append("%s: no 'why' -- every component says why it is there" % label)
        needed = JUSTIFIED_BY.get(ctype)
        if needed and covers:
            kinds = {str(requirements.get(r, {}).get("kind")) for r in covers}
            if not kinds & needed:
                found.append(
                    "%s: a %s is only justified by a requirement of kind %s; it covers only %s"
                    % (label, ctype, "/".join(sorted(needed)), "/".join(sorted(kinds)))
                )

    for rid, labels in covered.items():
        if not labels:
            found.append("%s is not covered by any component" % rid)

    for component in components:
        k = key(component)
        if k[0] in ("script", "mcp") and k not in verified:
            found.append("%s %s: no test verifies it" % k)

    if plugin_dir is not None:
        actual = on_disk(Path(plugin_dir))
        for k in sorted(planned - actual):
            if k[0] in TYPES:
                found.append("%s %s is planned but not in %s" % (k[0], k[1], plugin_dir))
        for k in sorted(actual - planned):
            found.append("%s %s is in the plugin but not in the plan -- trace it or remove it" % k)
        for component in components:
            if key(component)[0] != "test":
                continue
            path = Path(plugin_dir) / key(component)[1]
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for target in component.get("verifies") or []:
                target = str(target).replace("\\", "/")
                kinds = [k for k in planned if k[1] == target and k[0] in ("script", "mcp")]
                for verified_key in kinds:
                    if not _mentions(text, verified_key):
                        found.append(
                            "test %s claims to verify %s but never names it"
                            % (key(component)[1], target)
                        )
    return found


def table(data: Dict[str, Any]) -> str:
    """The 'Components and why' and requirement tables, as markdown."""
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").strip()

    lines = ["| Component | Type | Covers | Why |", "| --- | --- | --- | --- |"]
    for component in _components(data):
        ctype, name = key(component)
        covers = ", ".join(str(r) for r in component.get("covers") or [])
        why = component.get("why", "")
        if ctype == "test":
            covers = covers or "-"
            why = why or "verifies " + ", ".join(str(v) for v in component.get("verifies") or [])
        lines.append("| `%s` | %s | %s | %s |" % (cell(name), ctype, cell(covers), cell(why)))

    by_req: Dict[str, List[str]] = {}
    for component in _components(data):
        ctype, name = key(component)
        if ctype == "test":
            continue
        for rid in component.get("covers") or []:
            by_req.setdefault(str(rid), []).append("`%s`" % name)

    lines += ["", "| Requirement | Kind | Covered by |", "| --- | --- | --- |"]
    for req in data.get("requirements") or []:
        if not isinstance(req, dict):
            continue
        rid = str(req.get("id"))
        lines.append("| **%s** %s | %s | %s |" % (
            rid, cell(req.get("text", "")), cell(req.get("kind", "")),
            ", ".join(by_req.get(rid, [])) or "**not covered**"))
    return "\n".join(lines) + "\n"


def readme_block(data: Dict[str, Any]) -> str:
    return "%s\n%s%s" % (README_START, table(data), README_END)


def readme_is_current(readme: Path, data: Dict[str, Any]) -> Optional[bool]:
    """True/False when the README carries the block; None when it has none."""
    try:
        text = Path(readme).read_text(encoding="utf-8")
    except OSError:
        return None
    start, end = text.find(README_START), text.find(README_END)
    if start < 0 or end < start:
        return None
    current = text[start:end + len(README_END)]
    return current.replace("\r\n", "\n") == readme_block(data)


def write_readme(readme: Path, data: Dict[str, Any]) -> None:
    readme = Path(readme)
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    block = readme_block(data)
    start, end = text.find(README_START), text.find(README_END)
    if start >= 0 and end > start:
        text = text[:start] + block + text[end + len(README_END):]
    else:
        text = text.rstrip("\n") + ("\n\n" if text else "") + "## Components and why\n\n" + block + "\n"
    readme.write_text(text, encoding="utf-8")


def check(path: Path, plugin_dir: Optional[Path] = None) -> int:
    try:
        data = load(path)
    except Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2
    if not data.get("requirements"):
        print("CANNOT TELL: no requirements yet")
        return 3
    if not _components(data):
        print("CANNOT TELL: no components planned yet")
        return 3
    problems = issues(data, plugin_dir)
    if problems:
        print("GAPS (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1
    print("COMPLETE: %d requirement(s), %d component(s)" % (
        len(data["requirements"]), len(_components(data))))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("file", type=Path)
    p.add_argument("--plugin-dir", type=Path)
    p = sub.add_parser("table")
    p.add_argument("file", type=Path)
    p.add_argument("--write-readme", type=Path, metavar="README")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        return check(args.file, args.plugin_dir)
    try:
        data = load(args.file)
    except Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2
    if args.write_readme:
        write_readme(args.write_readme, data)
        print("wrote the components table to %s" % args.write_readme)
    else:
        sys.stdout.write(table(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
