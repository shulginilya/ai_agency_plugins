"""Generation of the Claude Code marketplace index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .model import Plugin

MARKETPLACE_PATH = Path(".claude-plugin/marketplace.json")

# How an entry points at the built bundle it installs.
#
#   path        a directory relative to the marketplace root. Resolves only for
#               a consumer who already has the built output -- which, since
#               dist/ is gitignored, means the machine that ran the build. An
#               index published this way names directories GitHub does not have.
#   git-subdir  a sparse checkout of one directory of one ref. This is the
#               publishable form: the index stays on main, the bundles live on
#               the branch CI force-pushes, and consumers add the repository
#               the ordinary way with no branch to know about.
PUBLISH_MODES = ("path", "git-subdir")

DEFAULT_SOURCE_ROOT = {"path": "./dist/claude-code", "git-subdir": "claude-code"}
DEFAULT_REF = "dist"

Source = Union[str, Dict[str, str]]


def _relative(value: str) -> str:
    """Drop a leading './' and any surrounding slashes: git paths carry neither."""
    if value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def plugin_source(
    plugin_name: str,
    publish: str = "path",
    source_root: Optional[str] = None,
    repo: Optional[str] = None,
    ref: Optional[str] = None,
) -> Source:
    if publish not in PUBLISH_MODES:
        raise ValueError(
            "unknown publish mode %r; expected one of %s" % (publish, ", ".join(PUBLISH_MODES))
        )
    root = source_root or DEFAULT_SOURCE_ROOT[publish]
    if publish == "path":
        return "%s/%s" % (root.rstrip("/"), plugin_name)
    if not repo:
        raise ValueError("git-subdir sources need a repo: owner/name, or a git URL")
    return {
        "source": "git-subdir",
        "url": repo,
        "path": "%s/%s" % (_relative(root), plugin_name),
        "ref": ref or DEFAULT_REF,
    }


def build_index(
    plugins: List[Plugin],
    owner: Dict[str, Any],
    name: str,
    description: str,
    source_root: Optional[str] = None,
    publish: str = "path",
    repo: Optional[str] = None,
    ref: Optional[str] = None,
) -> Dict[str, Any]:
    entries = []
    for plugin in plugins:
        entry: Dict[str, Any] = {
            "name": plugin.name,
            "source": plugin_source(
                plugin.name, publish=publish, source_root=source_root, repo=repo, ref=ref
            ),
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
