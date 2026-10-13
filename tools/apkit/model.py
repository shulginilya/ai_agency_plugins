"""Discovery of portable plugin sources under plugins/<name>/."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import frontmatter

MANIFEST_NAME = "plugin.json"
SKILL_FILE = "SKILL.md"
SHARED_DIR = "_shared"  # plugins/_shared/skills/<name>, borrowed via "shared_skills"


class SourceError(Exception):
    """A plugin source directory is malformed."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceError("%s: invalid JSON (%s)" % (path, exc)) from exc


@dataclass
class Skill:
    """One Agent Skills directory: SKILL.md plus whatever it bundles."""

    name: str
    path: Path
    meta: Dict[str, Any]
    body: str
    synthetic: bool = False  # True when derived from an agent for a target that lacks agents

    @property
    def description(self) -> str:
        return str(self.meta.get("description", ""))


@dataclass
class Doc:
    """A markdown document with frontmatter: a command or an agent."""

    name: str
    path: Path
    meta: Dict[str, Any]
    body: str


@dataclass
class Plugin:
    root: Path
    manifest: Dict[str, Any]
    skills: List[Skill] = field(default_factory=list)
    commands: List[Doc] = field(default_factory=list)
    agents: List[Doc] = field(default_factory=list)
    hooks: Optional[Dict[str, Any]] = None
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    scripts_dir: Optional[Path] = None

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.root.name)

    @property
    def version(self) -> str:
        return str(self.manifest.get("version") or "0.0.0")

    @property
    def description(self) -> str:
        return str(self.manifest.get("description") or "")

    def excluded_targets(self) -> List[str]:
        targets = self.manifest.get("targets") or {}
        return list(targets.get("exclude") or [])

    def target_override(self, target_id: str) -> Dict[str, Any]:
        targets = self.manifest.get("targets") or {}
        return dict((targets.get("overrides") or {}).get(target_id) or {})


def _load_doc(path: Path) -> Doc:
    text = path.read_text(encoding="utf-8")
    try:
        meta, body = frontmatter.parse(text)
    except frontmatter.FrontmatterError as exc:
        raise SourceError("%s: %s" % (path, exc)) from exc
    return Doc(name=path.stem, path=path, meta=meta, body=body)


def _load_skill(directory: Path) -> Skill:
    skill_file = directory / SKILL_FILE
    if not skill_file.is_file():
        raise SourceError("%s: missing %s" % (directory, SKILL_FILE))
    text = skill_file.read_text(encoding="utf-8")
    try:
        meta, body = frontmatter.parse(text)
    except frontmatter.FrontmatterError as exc:
        raise SourceError("%s: %s" % (skill_file, exc)) from exc
    return Skill(name=directory.name, path=directory, meta=meta, body=body)


def _load_shared_skills(
    root: Path, manifest: Dict[str, Any], manifest_path: Path, local: List[Skill]
) -> List[Skill]:
    """Skills a plugin borrows from plugins/_shared/skills/ by listing them in "shared_skills".

    One source directory, built into every plugin that lists it, so a skill the
    whole crew needs is never copied into each plugin and left to drift. The
    _-prefix keeps _shared out of discovery, like _template.
    """
    names = manifest.get("shared_skills") or []
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise SourceError("%s: 'shared_skills' must be a list of skill names" % manifest_path)
    taken = {skill.name for skill in local}
    shared_root = root.parent / SHARED_DIR / "skills"
    loaded = []
    for name in names:
        if name in taken:
            raise SourceError(
                "%s: shared skill %r clashes with the plugin's own skills/%s" % (manifest_path, name, name)
            )
        directory = shared_root / name
        if not directory.is_dir():
            raise SourceError(
                "%s: shared skill %r not found in %s" % (manifest_path, name, shared_root)
            )
        loaded.append(_load_skill(directory))
        taken.add(name)
    return loaded


def load_plugin(root: Path) -> Plugin:
    """Read one plugin source directory into a Plugin."""
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise SourceError("%s: missing %s" % (root, MANIFEST_NAME))
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise SourceError("%s: manifest must be a JSON object" % manifest_path)

    plugin = Plugin(root=root, manifest=manifest)

    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for entry in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            plugin.skills.append(_load_skill(entry))
    plugin.skills.extend(_load_shared_skills(root, manifest, manifest_path, plugin.skills))

    commands_dir = root / "commands"
    if commands_dir.is_dir():
        for entry in sorted(commands_dir.glob("*.md")):
            plugin.commands.append(_load_doc(entry))

    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for entry in sorted(agents_dir.glob("*.md")):
            plugin.agents.append(_load_doc(entry))

    hooks_file = root / "hooks" / "hooks.json"
    if hooks_file.is_file():
        hooks = _read_json(hooks_file)
        if not isinstance(hooks, dict):
            raise SourceError("%s: hooks must be a JSON object" % hooks_file)
        plugin.hooks = hooks

    mcp_file = root / "mcp" / "servers.json"
    if mcp_file.is_file():
        data = _read_json(mcp_file)
        if not isinstance(data, dict):
            raise SourceError("%s: mcp servers must be a JSON object" % mcp_file)
        # Accept both {"mcpServers": {...}} and a bare {name: {...}} map.
        plugin.mcp_servers = data.get("mcpServers", data)

    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        plugin.scripts_dir = scripts_dir

    return plugin


# Directories and files that say nothing about whether a plugin lives here.
# Switching branches leaves every other plugin's __pycache__ behind, so plugins/
# fills up with directories that hold caches and nothing else.
CACHE_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".ipynb_checkpoints",
}
CACHE_FILE_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}
CACHE_SUFFIXES = (".pyc", ".pyo")


def _holds_only_caches(directory: Path) -> bool:
    """True when a directory contains nothing a plugin author put there.

    Used to tell a branch-switch leftover (skip it silently) apart from a real
    plugin directory whose plugin.json is missing (say so loudly).
    """
    for child in directory.rglob("*"):
        if child.is_dir():
            continue
        relative = child.relative_to(directory)
        if any(part in CACHE_DIR_NAMES for part in relative.parts[:-1]):
            continue
        if child.name in CACHE_FILE_NAMES or child.suffix in CACHE_SUFFIXES:
            continue
        return False
    return True


def _candidate_dirs(plugins_root: Path, only: Optional[List[str]]) -> List[Path]:
    if not plugins_root.is_dir():
        return []
    chosen = []
    for entry in sorted(p for p in plugins_root.iterdir() if p.is_dir()):
        if entry.name.startswith("_") and not (only and entry.name in only):
            continue
        if only and entry.name not in only:
            continue
        chosen.append(entry)
    return chosen


def discover(plugins_root: Path, only: Optional[List[str]] = None) -> List[Plugin]:
    """Load every plugin under plugins/, skipping _-prefixed template dirs.

    A directory with no manifest is skipped rather than raised on: erroring
    here made a stale cache directory break every unscoped command, which
    pushed callers towards --plugin scoping — and scoping the marketplace index
    silently writes a partial file. Discovery is lenient; `validate` is the
    command whose job is to complain. Use unmanifested() to find the ones that
    look like a plugin somebody forgot to finish.
    """
    plugins: List[Plugin] = []
    for entry in _candidate_dirs(plugins_root, only):
        if not (entry / MANIFEST_NAME).is_file():
            continue
        plugins.append(load_plugin(entry))
    return plugins


def unmanifested(plugins_root: Path, only: Optional[List[str]] = None) -> List[Path]:
    """Directories under plugins/ that have real content but no manifest.

    Cache-only leftovers are excluded: those are branch-switch residue, not a
    mistake anyone needs to hear about.
    """
    strays = []
    for entry in _candidate_dirs(plugins_root, only):
        if (entry / MANIFEST_NAME).is_file():
            continue
        if _holds_only_caches(entry):
            continue
        strays.append(entry)
    return strays
