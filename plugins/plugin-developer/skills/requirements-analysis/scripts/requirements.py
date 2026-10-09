#!/usr/bin/env python3
"""Keep a plugin's requirements file honest.

A requirements file is the contract a generated plugin is built and audited
against. It holds the original prompt verbatim, the requirements split out of
it (each with a kind and an acceptance test), the assumptions made where the
prompt was silent, the questions still open, and -- once planned -- the
components that cover each requirement.

    requirements.py new NAME --prompt-file brief.md     # start .plugin-dev/NAME/requirements.json
    requirements.py check FILE                          # is it ready to plan against?
    requirements.py prompt FILE                         # print the original prompt, nothing else

`check` answers one of four things, and only the first is a pass:

    0  ready      every requirement has an id, a kind and a checkable acceptance test
    1  issues     something is missing or unverifiable -- fix the file
    2  unusable   the file is missing, is not JSON, or is not a requirements file
    3  ask        open questions remain -- they go to the user, not into a guess

Standard library only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = 1
STATE_DIR = ".plugin-dev"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ID_RE = re.compile(r"^R[1-9][0-9]*$")
# apkit validate refuses a longer plugin.json description (the desktop app rejects it).
MANIFEST_DESCRIPTION_MAX = 500

# What shape of need a requirement is. The kind decides which component can
# legitimately cover it -- see references/component-rules.md.
KINDS = {
    "action": "the user starts it on purpose",
    "knowledge": "expertise or a procedure the model should apply when relevant",
    "computation": "a calculation, parse, check or saved state that must come out the same every time",
    "event": "must happen on a lifecycle event whatever the model decides",
    "integration": "an outside system, or a structured tool other agents call",
    "isolation": "work that needs a clean context or an independent judgement",
    "constraint": "a property every component must keep (platform, dependencies, privacy)",
}

# Words that make an acceptance test unfalsifiable. A number next to them
# ("responds within 2 s") rescues the sentence.
VAGUE = (
    "properly", "correctly", "works", "work well", "good", "nice", "user-friendly",
    "user friendly", "intuitive", "fast", "quickly", "robust", "appropriate",
    "appropriately", "as needed", "etc", "and so on", "seamless", "seamlessly", "easy",
    "easily", "reasonable", "sensible",
)


class Unusable(Exception):
    """The file cannot be read as a requirements file at all."""


def load(path: Path) -> Dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Unusable("cannot read %s: %s" % (path, exc))
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise Unusable("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("requirements"), list):
        raise Unusable("%s has no 'requirements' list -- not a requirements file" % path)
    return data


def save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def vague_terms(text: str) -> List[str]:
    lowered = text.lower()
    if re.search(r"\d", lowered):
        return []
    found = []
    for term in VAGUE:
        if re.search(r"(?<![a-z-])" + re.escape(term) + r"(?![a-z-])", lowered):
            found.append(term)
    return found


def requirement_ids(data: Dict[str, Any]) -> List[str]:
    return [str(r.get("id")) for r in data.get("requirements", []) if isinstance(r, dict)]


def requirements_by_id(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(r.get("id")): r for r in data.get("requirements", []) if isinstance(r, dict)
    }


def issues(data: Dict[str, Any]) -> List[str]:
    """Everything that stops the file from being planned against."""
    found: List[str] = []

    plugin = data.get("plugin")
    if not isinstance(plugin, dict):
        found.append("missing 'plugin' block (name, display_name, description)")
    else:
        name = plugin.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name or ""):
            found.append("plugin.name %r must be lowercase-hyphenated" % (name,))
        description = plugin.get("description")
        if not isinstance(description, str) or not description.strip():
            found.append("plugin.description is empty -- it is what the model reads first")
        elif len(description) > MANIFEST_DESCRIPTION_MAX:
            found.append("plugin.description is %d chars; plugin.json caps it at %d"
                         % (len(description), MANIFEST_DESCRIPTION_MAX))
        elif "use when" not in description.lower():
            found.append("plugin.description should say when to use it ('Use when ...')")

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        found.append("'prompt' is empty -- keep the original requirements prompt verbatim")

    requirements = data.get("requirements") or []
    if not requirements:
        found.append("no requirements yet")
    seen = set()
    for index, req in enumerate(requirements, 1):
        if not isinstance(req, dict):
            found.append("requirement #%d is not an object" % index)
            continue
        rid = str(req.get("id", ""))
        where = rid or "requirement #%d" % index
        if not ID_RE.match(rid):
            found.append("%s: id must look like R1, R2, ..." % where)
        elif rid in seen:
            found.append("%s: duplicate id" % rid)
        seen.add(rid)
        if not str(req.get("text", "")).strip():
            found.append("%s: no text" % where)
        kind = req.get("kind")
        if kind not in KINDS:
            found.append("%s: kind %r is not one of %s" % (where, kind, ", ".join(KINDS)))
        acceptance = str(req.get("acceptance", "")).strip()
        if not acceptance:
            found.append("%s: no acceptance test -- how would anyone know it is met?" % where)
        else:
            terms = vague_terms(acceptance)
            if terms:
                found.append(
                    "%s: acceptance is not checkable (%s) -- say what is observed, not how it feels"
                    % (where, ", ".join(repr(t) for t in terms))
                )

    for key in ("assumptions", "open_questions", "components"):
        value = data.get(key, [])
        if not isinstance(value, list):
            found.append("'%s' must be a list" % key)
    return found


def open_questions(data: Dict[str, Any]) -> List[str]:
    return [str(q) for q in data.get("open_questions") or [] if str(q).strip()]


def check(path: Path, root: Optional[Path] = None) -> int:
    try:
        data = load(path)
    except Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2

    problems = issues(data)
    if root is not None:
        name = (data.get("plugin") or {}).get("name")
        destination = Path(root) / "plugins" / str(name)
        if name and destination.exists() and destination.resolve() != Path(path).resolve().parent:
            problems.append("plugins/%s already exists -- pick another name" % name)

    if problems:
        print("ISSUES (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1
    questions = open_questions(data)
    if questions:
        print("ASK (%d open question%s):" % (len(questions), "" if len(questions) == 1 else "s"))
        for question in questions:
            print("  - %s" % question)
        return 3
    print("READY: %d requirement(s), %d assumption(s)" % (
        len(data["requirements"]), len(data.get("assumptions") or [])))
    return 0


def new(name: str, prompt: str, root: Path, force: bool = False) -> int:
    if not NAME_RE.match(name):
        print("plugin name %r must be lowercase-hyphenated" % name, file=sys.stderr)
        return 2
    if (root / "plugins" / name).exists():
        print("plugins/%s already exists -- pick another name" % name, file=sys.stderr)
        return 2
    path = root / STATE_DIR / name / "requirements.json"
    if path.exists() and not force:
        print("%s already exists -- read it, or pass --force to start over" % path, file=sys.stderr)
        return 2
    if not prompt.strip():
        print("the requirements prompt is empty", file=sys.stderr)
        return 2
    save(path, {
        "schema": SCHEMA,
        "plugin": {"name": name, "display_name": "", "description": ""},
        "prompt": prompt,
        "requirements": [],
        "assumptions": [],
        "open_questions": [],
        "components": [],
    })
    print(str(path))
    return 0


def find_root(start: Path) -> Path:
    """The repo root: the nearest directory holding plugins/ and tools/apkit/."""
    here = Path(start).resolve()
    for candidate in [here] + list(here.parents):
        if (candidate / "plugins").is_dir() and (candidate / "tools" / "apkit").is_dir():
            return candidate
    return here


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="start a requirements file for a new plugin")
    p.add_argument("name")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt-file", type=Path)
    source.add_argument("--prompt")
    p.add_argument("--root", type=Path)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("check", help="is the file ready to plan against?")
    p.add_argument("file", type=Path)
    p.add_argument("--root", type=Path, help="repo root, to catch a name already taken")

    p = sub.add_parser("prompt", help="print the original prompt and nothing else")
    p.add_argument("file", type=Path)

    args = parser.parse_args(argv)
    if args.cmd == "new":
        root = args.root or find_root(Path.cwd())
        if args.prompt_file is not None:
            try:
                prompt = args.prompt_file.read_text(encoding="utf-8")
            except OSError as exc:
                print("cannot read %s: %s" % (args.prompt_file, exc), file=sys.stderr)
                return 2
        else:
            prompt = args.prompt
        return new(args.name, prompt, root, args.force)
    if args.cmd == "check":
        return check(args.file, args.root)
    try:
        data = load(args.file)
    except Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2
    print(data.get("prompt", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
