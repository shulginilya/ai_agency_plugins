"""Loading of declarative harness manifests from targets/*.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

COMPONENTS = ("manifest", "skills", "commands", "agents", "hooks", "mcp")
SUPPORT_LEVELS = ("native", "emulated", "manual", "unsupported")


class TargetError(Exception):
    """A target manifest is malformed."""


@dataclass
class Component:
    name: str
    support: str
    path: Optional[str] = None
    fmt: Optional[str] = None
    verified: bool = False
    strategy: Optional[str] = None
    note: Optional[str] = None
    frontmatter: bool = True
    frontmatter_map: Dict[str, str] = None  # type: ignore[assignment]
    frontmatter_allow: Optional[List[str]] = None
    placeholders: Dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.frontmatter_map is None:
            self.frontmatter_map = {}
        if self.placeholders is None:
            self.placeholders = {}

    @property
    def emitted(self) -> bool:
        return self.support in ("native", "emulated", "manual") and bool(self.path)


@dataclass
class Placement:
    component: str
    dest: str
    mode: str
    merge_key: Optional[str] = None


@dataclass
class Target:
    id: str
    name: str
    docs: str
    bundle: str
    components: Dict[str, Component]
    install: Dict[str, List[Placement]]
    notes: List[str]
    placeholders: Dict[str, str]

    def component(self, name: str) -> Component:
        return self.components.get(name) or Component(name=name, support="unsupported")

    def unverified(self) -> List[str]:
        return [c.name for c in self.components.values() if c.emitted and not c.verified]


def _component(name: str, raw: Dict[str, Any]) -> Component:
    support = raw.get("support", "unsupported")
    if support not in SUPPORT_LEVELS:
        raise TargetError("component %r: unknown support level %r" % (name, support))
    return Component(
        name=name,
        support=support,
        path=raw.get("path"),
        fmt=raw.get("format"),
        verified=bool(raw.get("verified", False)),
        strategy=raw.get("strategy"),
        note=raw.get("note"),
        frontmatter=raw.get("frontmatter", True),
        frontmatter_map=dict(raw.get("frontmatter_map") or {}),
        frontmatter_allow=raw.get("frontmatter_allow"),
        placeholders=dict(raw.get("placeholders") or {}),
    )


def load_target(path: Path) -> Target:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TargetError("%s: invalid JSON (%s)" % (path, exc)) from exc

    for key in ("id", "name"):
        if not raw.get(key):
            raise TargetError("%s: missing %r" % (path, key))

    components = {
        name: _component(name, value) for name, value in (raw.get("components") or {}).items()
    }
    for name in components:
        if name not in COMPONENTS:
            raise TargetError("%s: unknown component %r" % (path, name))

    install: Dict[str, List[Placement]] = {}
    for scope, entries in (raw.get("install") or {}).items():
        placements = []
        for entry in entries:
            mode = entry.get("mode", "children")
            if mode not in ("bundle", "children", "tree", "merge-json", "file"):
                raise TargetError("%s: unknown install mode %r" % (path, mode))
            placements.append(
                Placement(
                    component=entry["component"],
                    dest=entry["dest"],
                    mode=mode,
                    merge_key=entry.get("merge_key"),
                )
            )
        install[scope] = placements

    return Target(
        id=raw["id"],
        name=raw["name"],
        docs=raw.get("docs", ""),
        bundle=raw.get("bundle", "loose"),
        components=components,
        install=install,
        notes=list(raw.get("notes") or []),
        placeholders=dict(raw.get("placeholders") or {}),
    )


def load_targets(targets_root: Path, only: Optional[List[str]] = None) -> List[Target]:
    targets = []
    for path in sorted(targets_root.glob("*.json")):
        target = load_target(path)
        if only and target.id not in only:
            continue
        targets.append(target)
    if only:
        found = {t.id for t in targets}
        missing = [t for t in only if t not in found]
        if missing:
            raise TargetError("unknown target(s): %s" % ", ".join(missing))
    return targets
