"""Generation of the Claude Code marketplace index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .model import Plugin

MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")


def build_index(
    plugins: List[Plugin], owner: Dict[str, Any], name: str, description: str, source_root: str
) -> Dict[str, Any]:
    entries = []
    for plugin in plugins:
        entry: Dict[str, Any] = {
            "name": plugin.name,
            "source": "%s/%s" % (source_root.rstrip("/"), plugin.name),
            "description": plugin.description,
            "version": plugin.version,
        }
        if plugin.manifest.get("author"):
            entry["author"] = plugin.manifest["author"]
        if plugin.manifest.get("keywords"):
            entry["keywords"] = plugin.manifest["keywords"]
        entries.append(entry)
    return {
        "name": name,
        "owner": owner,
        "metadata": {"description": description},
        "plugins": entries,
    }


def write_index(project_root: Path, index: Dict[str, Any]) -> Path:
    path = project_root / MARKETPLACE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return path
