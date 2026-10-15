#!/usr/bin/env python3
"""Turn an approved plan into a plugin skeleton holding only what was planned.

    scaffold.py NAME [--requirements .plugin-dev/NAME/requirements.json] [--root .]

Refuses unless the requirements file is ready (requirements.py check) and the
plan is complete (req_trace.py check, without --plugin-dir). Then it:

    1. runs `python -m tools.apkit new NAME` so plugin.json starts from the
       repo's own template (author, licence, repository);
    2. deletes every template example -- none of them were asked for;
    3. writes plugin.json's name, displayName, version and description from the plan;
    4. writes one stub per planned component, each carrying the marker
       `TODO(plugin-developer)` -- the gate fails while any marker is left, so a
       planned component cannot be silently skipped;
    5. moves requirements.json into the plugin, and writes README.md with the
       components table rendered from it;
    6. opens the build session (.plugin-dev/active.json) the Stop hook watches.

Exits: 0 scaffolded, 1 the plan is not ready (problems listed), 2 unusable
(not in the repo, file missing, plugins/NAME already exists).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
for _directory in (SKILLS / "requirements-analysis" / "scripts", SKILLS / "plugin-verification" / "scripts"):
    if _directory.is_dir() and str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

import gate  # noqa: E402
import req_trace  # noqa: E402
import requirements as reqs  # noqa: E402

MARKER = gate.MARKER
PY = '"$(command -v python3 || command -v python)"'


def _frontmatter(fields: Dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append("%s: %s" % (key, value))
    lines.append("---")
    return "\n".join(lines) + "\n"


def stub_skill(name: str, covers: str) -> str:
    return _frontmatter({
        "name": name,
        "description": "%s -- say what this skill does and when to use it, in the user's words." % MARKER,
        "license": "MIT",
        "metadata": '\n  author: ilya-shulgin\n  version: "0.1.0"',
    }) + "\n# %s\n\n%s Write the body. Covers %s.\n" % (name, MARKER, covers)


def stub_command(name: str, covers: str) -> str:
    return _frontmatter({
        "description": "%s one line for the command list." % MARKER,
        "argument_hint": '"[what to type after the command]"',
    }) + "\n%s Write what /%s does with: {{ARGS}}\nCovers %s.\n" % (MARKER, name, covers)


def stub_agent(name: str, covers: str) -> str:
    return _frontmatter({
        "name": name,
        "description": "%s what it does and when to delegate to it." % MARKER,
        "model": "sonnet",
        "tools": "Read, Grep, Glob, Bash",
    }) + "\n%s Write the system prompt: the one job, the standard, the exact output. Covers %s.\n" % (MARKER, covers)


def stub_script(path: str, covers: str) -> str:
    return (
        '#!/usr/bin/env python3\n"""%s %s -- covers %s.\n\n'
        "State what it answers and every exit code, including the ones that are not a pass.\n"
        '"""\n\nfrom __future__ import annotations\n\n\ndef main() -> int:\n    raise SystemExit("not written yet")\n\n\n'
        'if __name__ == "__main__":\n    raise SystemExit(main())\n'
    ) % (MARKER, path, covers)


def stub_test(path: str, verifies: List[str]) -> str:
    return (
        '#!/usr/bin/env python3\n"""%s tests for: %s"""\n\nfrom __future__ import annotations\n\n'
        "import unittest\n\n\nif __name__ == \"__main__\":\n    unittest.main(verbosity=2)\n"
    ) % (MARKER, ", ".join(verifies) or "nothing listed")


def stub_server() -> str:
    return (
        '#!/usr/bin/env python3\n"""%s the MCP server: stdlib JSON-RPC over stdio.\n\n'
        "Start from plugins/scrum-master/mcp/server.py. Tools import their logic from the\n"
        'skills\' scripts/ -- never restate a rule here.\n"""\n'
    ) % MARKER


def scaffold(root: Path, name: str, requirements_file: Path) -> int:
    try:
        data = reqs.load(requirements_file)
    except reqs.Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2
    problems = reqs.issues(data) + req_trace.issues(data)
    if (data.get("plugin") or {}).get("name") != name:
        problems.append("requirements.json names plugin %r, not %r" % ((data.get("plugin") or {}).get("name"), name))
    if reqs.open_questions(data):
        problems.append("open questions remain: " + "; ".join(reqs.open_questions(data)))
    if not data.get("components"):
        problems.append("no components planned yet")
    if problems:
        print("NOT READY (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1

    plugin_dir = root / "plugins" / name
    if plugin_dir.exists():
        print("UNUSABLE: plugins/%s already exists" % name, file=sys.stderr)
        return 2
    code, out = gate.apkit(root, "new", name)
    if code != 0:
        print("UNUSABLE: apkit new failed:\n%s" % out, file=sys.stderr)
        return 2

    # 2. nothing from the template survives except plugin.json
    for child in list(plugin_dir.iterdir()):
        if child.name == "plugin.json":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    # 3. manifest
    manifest_path = plugin_dir / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plugin = data["plugin"]
    manifest["name"] = name
    manifest["displayName"] = plugin.get("display_name") or name.replace("-", " ").title()
    manifest["version"] = "0.1.0"
    manifest["description"] = plugin["description"]
    manifest["keywords"] = list(plugin.get("keywords") or [])
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4. stubs
    created: List[str] = []

    def write(rel: str, text: str) -> None:
        path = plugin_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        created.append(rel)

    hooks: Dict[str, Any] = {}
    servers: Dict[str, Any] = {}
    for component in data["components"]:
        ctype, cname = req_trace.key(component)
        covers = ", ".join(str(r) for r in component.get("covers") or []) or "-"
        if ctype == "skill":
            write("skills/%s/SKILL.md" % cname, stub_skill(cname, covers))
        elif ctype == "command":
            write("commands/%s.md" % cname, stub_command(cname, covers))
        elif ctype == "agent":
            write("agents/%s.md" % cname, stub_agent(cname, covers))
        elif ctype == "script":
            write(cname, stub_script(cname, covers))
        elif ctype == "test":
            write(cname, stub_test(cname, [str(v) for v in component.get("verifies") or []]))
        elif ctype == "hook":
            hooks[cname] = [{"hooks": [{
                "type": "command",
                "command": '%s "${CLAUDE_PLUGIN_ROOT}/scripts/%s.py"' % (PY, MARKER),
            }]}]
        elif ctype == "mcp":
            servers[cname] = {
                "command": "sh",
                "args": ["-c", 'exec "$(command -v python3 || command -v python)" "$@"', "sh",
                         "{{PLUGIN_ROOT}}/mcp/server.py"],
                "env": {},
            }
    if hooks:
        write("hooks/hooks.json", json.dumps({"hooks": hooks}, indent=2) + "\n")
    if servers:
        write("mcp/servers.json", json.dumps({"mcpServers": servers}, indent=2) + "\n")
        write("mcp/server.py", stub_server())

    # 5. the plan moves into the plugin -- one home for it
    target = plugin_dir / "requirements.json"
    reqs.save(target, data)
    if Path(requirements_file).resolve() != target.resolve():
        Path(requirements_file).unlink()
    readme = plugin_dir / "README.md"
    readme.write_text(
        "# %s\n\n%s\n\n## Components and why\n\n%s\n" % (
            manifest["displayName"], plugin["description"], req_trace.readme_block(data)),
        encoding="utf-8",
    )

    # 6. the Stop hook now holds the session to the gate
    gate.open_session(root, name)

    print("scaffolded plugins/%s" % name)
    for rel in ["plugin.json", "requirements.json", "README.md"] + created:
        print("  %s" % rel)
    print("next: replace every %s stub, then run gate.py run %s" % (MARKER, name))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name")
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    root = args.root or gate.find_root(Path.cwd())
    if root is None:
        print("UNUSABLE: not inside the plugins repo", file=sys.stderr)
        return 2
    requirements_file = args.requirements or Path(root) / gate.STATE_DIR / args.name / "requirements.json"
    return scaffold(Path(root), args.name, requirements_file)


if __name__ == "__main__":
    raise SystemExit(main())
