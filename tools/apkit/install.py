"""Placing built bundles into the directories each harness actually reads."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .targets import Target

LEDGER_NAME = ".apkit.local.json"


class InstallError(Exception):
    pass


@dataclass
class Action:
    source: Path
    dest: Path
    mode: str
    detail: str = ""

    def describe(self) -> str:
        return "%-11s %s -> %s%s" % (
            self.mode,
            self.source.name,
            self.dest,
            (" (%s)" % self.detail) if self.detail else "",
        )


def resolve_dest(raw: str, plugin_name: str, project_root: Path) -> Path:
    text = raw.replace("{plugin}", plugin_name)
    if text.startswith("~"):
        return Path(os.path.expanduser(text))
    return (project_root / text).resolve()


def component_source(target: Target, component_name: str, bundle_root: Path) -> Optional[Path]:
    """Locate a component's output inside a built bundle."""
    if component_name == "__bundle__":
        return bundle_root
    component = target.component(component_name)
    if not component.path:
        return None
    template = component.path
    if "{name}" in template:
        directory = template.split("{name}")[0].rstrip("/")
        path = bundle_root / directory if directory else bundle_root
        return path if path.is_dir() else None
    path = bundle_root / template
    return path if path.exists() else None


def _merge_json(source: Path, dest: Path, key: str, dry_run: bool) -> str:
    incoming = json.loads(source.read_text(encoding="utf-8"))
    fragment = incoming.get(key, incoming)
    existing: Dict[str, Any] = {}
    if dest.exists():
        try:
            existing = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InstallError("%s is not valid JSON; refusing to overwrite (%s)" % (dest, exc))
        if not isinstance(existing, dict):
            raise InstallError("%s is not a JSON object; refusing to overwrite" % dest)
    merged = dict(existing)
    section = dict(merged.get(key) or {})
    added = [name for name in fragment if name not in section]
    section.update(fragment)
    merged[key] = section
    for extra_key, value in incoming.items():
        if extra_key not in (key,) and extra_key not in merged:
            merged[extra_key] = value
    if not dry_run:
        if dest.exists():
            shutil.copyfile(dest, dest.with_suffix(dest.suffix + ".apkit.bak"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return "merged %d key(s) into %s%s" % (
        len(fragment),
        key,
        "" if added else " (all pre-existing)",
    )


def _place(source: Path, dest: Path, link: bool, dry_run: bool) -> None:
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    if link:
        try:
            dest.symlink_to(source, target_is_directory=source.is_dir())
            return
        except (OSError, NotImplementedError):
            # Windows without Developer Mode, or a filesystem that refuses links.
            pass
    if source.is_dir():
        shutil.copytree(source, dest)
    else:
        shutil.copyfile(source, dest)


def plan(
    target: Target,
    plugin_name: str,
    bundle_root: Path,
    scope: str,
    project_root: Path,
) -> List[Action]:
    placements = target.install.get(scope)
    if placements is None:
        raise InstallError(
            "target %r has no %r scope (available: %s)"
            % (target.id, scope, ", ".join(sorted(target.install)) or "none")
        )
    actions: List[Action] = []
    for placement in placements:
        source = component_source(target, placement.component, bundle_root)
        if source is None:
            continue
        dest = resolve_dest(placement.dest, plugin_name, project_root)
        if placement.mode == "children":
            for child in sorted(source.iterdir()):
                actions.append(Action(child, dest / child.name, "copy"))
        elif placement.mode in ("bundle", "tree"):
            actions.append(Action(source, dest, "copy"))
        elif placement.mode == "file":
            actions.append(Action(source, dest, "copy"))
        elif placement.mode == "merge-json":
            actions.append(
                Action(source, dest, "merge-json", detail=placement.merge_key or "mcpServers")
            )
    return actions


def apply(actions: List[Action], link: bool = False, dry_run: bool = False) -> List[str]:
    log: List[str] = []
    for action in actions:
        if action.mode == "merge-json":
            log.append(_merge_json(action.source, action.dest, action.detail, dry_run))
        else:
            _place(action.source, action.dest, link, dry_run)
            log.append("%s %s" % ("linked" if link else "copied", action.dest))
    return log


def read_ledger(project_root: Path) -> Dict[str, Any]:
    path = project_root / LEDGER_NAME
    if not path.is_file():
        return {"installs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"installs": []}


def record(project_root: Path, plugin_name: str, target_id: str, scope: str, actions) -> None:
    ledger = read_ledger(project_root)
    ledger["installs"] = [
        entry
        for entry in ledger.get("installs", [])
        if not (
            entry.get("plugin") == plugin_name
            and entry.get("target") == target_id
            and entry.get("scope") == scope
        )
    ]
    ledger["installs"].append(
        {
            "plugin": plugin_name,
            "target": target_id,
            "scope": scope,
            "paths": [str(a.dest) for a in actions if a.mode != "merge-json"],
            "merged": [str(a.dest) for a in actions if a.mode == "merge-json"],
        }
    )
    (project_root / LEDGER_NAME).write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8"
    )


def uninstall(project_root: Path, plugin_name: str, target_id: Optional[str] = None) -> List[str]:
    ledger = read_ledger(project_root)
    removed: List[str] = []
    keep = []
    for entry in ledger.get("installs", []):
        if entry.get("plugin") != plugin_name or (target_id and entry.get("target") != target_id):
            keep.append(entry)
            continue
        for raw in entry.get("paths", []):
            path = Path(raw)
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed.append(raw)
            elif path.is_dir():
                shutil.rmtree(path)
                removed.append(raw)
        for raw in entry.get("merged", []):
            removed.append("%s (merged config left in place — edit it by hand)" % raw)
    ledger["installs"] = keep
    (project_root / LEDGER_NAME).write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8"
    )
    return removed
