"""Per-dialect renderers.

Each function turns one portable component into the bytes a specific harness
expects. Renderers are selected by the "format" key in targets/*.json, so
adding a harness that reuses an existing dialect costs zero Python.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import frontmatter
from .model import Doc, Plugin, Skill
from .targets import Component, Target

PORTABLE_PLACEHOLDERS = {
    "{{ARGS}}": "args",
    "{{ARG1}}": "arg1",
    "{{ARG2}}": "arg2",
}
DEFAULT_ARG_FALLBACK = {"args": "$ARGUMENTS", "arg1": "$1", "arg2": "$2"}


def plugin_root_value(target: Target, plugin: Plugin) -> str:
    """What {{PLUGIN_ROOT}} means for this target.

    Bundle targets (Claude Code) get the harness's own runtime variable. Loose
    targets install skills individually, so nothing resolves a bundle path at
    runtime — those point back at the plugin's source directory, which is where
    its scripts and MCP servers actually live on this machine.
    """
    raw = target.placeholders.get("plugin_root", ".")
    return str(plugin.root) if raw == "{{SOURCE}}" else raw


def substitute(
    text: str, component: Component, target: Target, plugin_root: Optional[str] = None
) -> str:
    """Replace portable placeholders with the target's own spelling."""
    for token, key in PORTABLE_PLACEHOLDERS.items():
        replacement = component.placeholders.get(key, DEFAULT_ARG_FALLBACK[key])
        text = text.replace(token, replacement)
    if plugin_root is None:
        plugin_root = target.placeholders.get("plugin_root", ".")
    return text.replace("{{PLUGIN_ROOT}}", plugin_root)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, data: Any) -> Path:
    return _write(path, json.dumps(data, indent=2) + "\n")


# --------------------------------------------------------------------------- skills


def render_skill_dir(
    skill: Skill,
    component: Component,
    target: Target,
    dest_root: Path,
    plugin_root: Optional[str] = None,
) -> Path:
    """Copy a skill directory, rewriting SKILL.md to the target's allowed frontmatter."""
    dest = dest_root / component.path.replace("{name}", skill.name)
    if dest.exists():
        shutil.rmtree(dest)
    if skill.path.is_dir() and not skill.synthetic:
        shutil.copytree(skill.path, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        dest.mkdir(parents=True, exist_ok=True)

    allowed = component.frontmatter_allow
    meta: Dict[str, Any] = dict(skill.meta)
    if allowed:
        meta = {key: value for key, value in meta.items() if key in allowed}
    meta.setdefault("name", skill.name)

    body = substitute(skill.body, component, target, plugin_root)
    _write(dest / "SKILL.md", frontmatter.compose(meta, body))
    return dest


def agent_as_skill(agent: Doc, plugin: Plugin) -> Skill:
    """Project a subagent onto a skill, for harnesses without subagents.

    The persona survives; the delegation does not. The body is prefixed with a
    line saying so, because an agent prompt written as "you are X" reads oddly
    when it is loaded inline instead of into a fresh context.
    """
    description = str(agent.meta.get("description", "")).strip()
    preamble = (
        "> Adapted from the `%s` subagent in the `%s` plugin. This harness has no "
        "subagent format, so the role is loaded inline: adopt it for the duration "
        "of the task, then drop it.\n" % (agent.name, plugin.name)
    )
    meta = {
        "name": agent.name,
        "description": description,
    }
    for key in ("license", "compatibility", "allowed-tools"):
        if key in agent.meta:
            meta[key] = agent.meta[key]
    return Skill(
        name=agent.name,
        path=agent.path.parent,
        meta=meta,
        body=preamble + "\n" + agent.body.lstrip("\n"),
        synthetic=True,
    )


# ------------------------------------------------------------------ markdown docs


def render_markdown_doc(
    doc: Doc,
    component: Component,
    target: Target,
    dest_root: Path,
    plugin_root: Optional[str] = None,
) -> Path:
    """Render a command or agent as markdown, mapping frontmatter keys."""
    dest = dest_root / component.path.replace("{name}", doc.name)
    body = substitute(doc.body, component, target, plugin_root)

    if component.frontmatter is False:
        description = str(doc.meta.get("description", "")).strip()
        header = "# /%s\n\n%s\n\n" % (doc.name, description) if description else ""
        return _write(dest, header + body.lstrip("\n"))

    meta: Dict[str, Any] = {}
    mapping = component.frontmatter_map or {"description": "description"}
    for source_key, target_key in mapping.items():
        value = doc.meta.get(source_key, doc.meta.get(source_key.replace("_", "-")))
        if value not in (None, ""):
            meta[target_key] = value
    return _write(dest, frontmatter.compose(meta, body))


def render_toml_command(
    doc: Doc,
    component: Component,
    target: Target,
    dest_root: Path,
    plugin_root: Optional[str] = None,
) -> Path:
    """Gemini CLI keeps custom commands as TOML with description + prompt keys."""
    dest = dest_root / component.path.replace("{name}", doc.name)
    body = substitute(doc.body, component, target, plugin_root).strip()
    description = str(doc.meta.get("description", "")).strip()
    lines = []
    if description:
        lines.append("description = %s" % _toml_basic(description))
    lines.append('prompt = """')
    lines.append(body.replace('"""', '\\"\\"\\"'))
    lines.append('"""')
    return _write(dest, "\n".join(lines) + "\n")


def _toml_basic(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"%s"' % escaped


# -------------------------------------------------------------------------- mcp


def render_mcp_servers_json(
    servers: Dict[str, Any], component: Component, dest_root: Path, key: str = "mcpServers"
) -> Path:
    return _write_json(dest_root / component.path, {key: servers})


def render_mcp_opencode_json(
    servers: Dict[str, Any], component: Component, dest_root: Path
) -> Path:
    """OpenCode nests MCP servers under "mcp" with a local/remote type tag."""
    converted: Dict[str, Any] = {}
    for name, server in servers.items():
        if server.get("url"):
            entry: Dict[str, Any] = {"type": "remote", "url": server["url"], "enabled": True}
            if server.get("headers"):
                entry["headers"] = server["headers"]
        else:
            command = [server.get("command", "")] + list(server.get("args") or [])
            entry = {"type": "local", "command": command, "enabled": True}
            if server.get("env"):
                entry["environment"] = server["env"]
        converted[name] = entry
    return _write_json(
        dest_root / component.path,
        {"$schema": "https://opencode.ai/config.json", "mcp": converted},
    )


def render_mcp_codex_toml(
    servers: Dict[str, Any], component: Component, dest_root: Path
) -> Path:
    """Codex keeps MCP servers in ~/.codex/config.toml; emit a mergeable snippet."""
    lines = [
        "# Merge into ~/.codex/config.toml — apkit does not rewrite that file for you.",
        "",
    ]
    for name, server in servers.items():
        lines.append("[mcp_servers.%s]" % name)
        if server.get("url"):
            lines.append("url = %s" % _toml_basic(str(server["url"])))
        else:
            lines.append("command = %s" % _toml_basic(str(server.get("command", ""))))
            args = server.get("args") or []
            if args:
                lines.append("args = [%s]" % ", ".join(_toml_basic(str(a)) for a in args))
        env = server.get("env") or {}
        if env:
            lines.append("")
            lines.append("[mcp_servers.%s.env]" % name)
            for env_key, env_value in env.items():
                lines.append("%s = %s" % (env_key, _toml_basic(str(env_value))))
        lines.append("")
    return _write(dest_root / component.path, "\n".join(lines))


# ------------------------------------------------------------------ claude-only


def render_claude_hooks(
    hooks: Dict[str, Any], component: Component, dest_root: Path
) -> Path:
    payload = hooks if "hooks" in hooks else {"hooks": hooks}
    return _write_json(dest_root / component.path, payload)


CLAUDE_MANIFEST_KEYS = (
    "name", "displayName", "version", "description", "author", "homepage",
    "repository", "license", "keywords",
)


def render_claude_manifest(
    plugin: Plugin, component: Component, dest_root: Path, emitted: Dict[str, bool]
) -> Path:
    manifest = {k: plugin.manifest[k] for k in CLAUDE_MANIFEST_KEYS if k in plugin.manifest}
    if emitted.get("hooks"):
        manifest["hooks"] = "./hooks/hooks.json"
    if emitted.get("mcp"):
        manifest["mcpServers"] = "./.mcp.json"
    return _write_json(dest_root / component.path, manifest)


def render_notes(dest_root: Path, lines: List[str]) -> Optional[Path]:
    if not lines:
        return None
    return _write(dest_root / "INSTALL.md", "\n".join(lines) + "\n")
