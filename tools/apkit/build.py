"""Project a portable plugin onto one harness target."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from . import render
from .model import Plugin
from .targets import Target


@dataclass
class BuildResult:
    target: Target
    plugin: Plugin
    root: Path
    files: List[Path] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)


def _skip_reason(component, fallback: str) -> str:
    return component.note or fallback


def build(plugin: Plugin, target: Target, dist_root: Path) -> BuildResult:
    dest_root = dist_root / target.id / plugin.name
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    result = BuildResult(target=target, plugin=plugin, root=dest_root)
    plugin_root = render.plugin_root_value(target, plugin)
    emitted: Dict[str, bool] = {}
    override = plugin.target_override(target.id)

    # ---- skills -----------------------------------------------------------
    skills_component = target.component("skills")
    if plugin.skills:
        if skills_component.emitted:
            for skill in plugin.skills:
                result.files.append(
                    render.render_skill_dir(
                        skill, skills_component, target, dest_root, plugin_root
                    )
                )
            emitted["skills"] = True
        else:
            result.skipped.append(("skills", _skip_reason(skills_component, "not supported")))

    # ---- agents -----------------------------------------------------------
    agents_component = target.component("agents")
    if plugin.agents:
        if agents_component.support == "native" and agents_component.path:
            for agent in plugin.agents:
                result.files.append(
                    render.render_markdown_doc(
                        agent, agents_component, target, dest_root, plugin_root
                    )
                )
            emitted["agents"] = True
        elif agents_component.strategy == "as-skill" and skills_component.emitted:
            for agent in plugin.agents:
                synthetic = render.agent_as_skill(agent, plugin)
                result.files.append(
                    render.render_skill_dir(
                        synthetic, skills_component, target, dest_root, plugin_root
                    )
                )
            result.warnings.append(
                "agents emitted as skills (%s has no subagent format): %s"
                % (target.name, ", ".join(a.name for a in plugin.agents))
            )
            emitted["agents"] = True
        else:
            result.skipped.append(("agents", _skip_reason(agents_component, "not supported")))

    # ---- commands ---------------------------------------------------------
    commands_component = target.component("commands")
    if plugin.commands:
        if commands_component.emitted:
            for command in plugin.commands:
                if commands_component.fmt == "toml-command":
                    path = render.render_toml_command(
                        command, commands_component, target, dest_root, plugin_root
                    )
                else:
                    path = render.render_markdown_doc(
                        command, commands_component, target, dest_root, plugin_root
                    )
                result.files.append(path)
            emitted["commands"] = True
        else:
            result.skipped.append(
                (
                    "commands",
                    _skip_reason(
                        commands_component,
                        "no custom-command format; invoke the matching skill by name instead",
                    ),
                )
            )

    # ---- hooks ------------------------------------------------------------
    hooks_component = target.component("hooks")
    if plugin.hooks:
        if hooks_component.emitted and hooks_component.fmt == "claude-hooks":
            result.files.append(
                render.render_claude_hooks(plugin.hooks, hooks_component, dest_root)
            )
            emitted["hooks"] = True
        else:
            result.skipped.append(
                (
                    "hooks",
                    _skip_reason(
                        hooks_component,
                        "no lifecycle hooks; enforce the same checks in CI or a git hook",
                    ),
                )
            )

    # ---- mcp --------------------------------------------------------------
    mcp_component = target.component("mcp")
    servers = dict(plugin.mcp_servers or {})
    servers.update(override.get("mcpServers") or {})
    if servers:
        # MCP entries reference scripts on disk; resolve {{PLUGIN_ROOT}} the same
        # way skill bodies do, so the emitted config actually starts.
        servers = json.loads(
            json.dumps(servers).replace("{{PLUGIN_ROOT}}", plugin_root.replace("\\", "/"))
        )
    if servers:
        if mcp_component.emitted:
            if mcp_component.fmt == "mcp-opencode-json":
                path = render.render_mcp_opencode_json(servers, mcp_component, dest_root)
            elif mcp_component.fmt == "mcp-codex-toml":
                path = render.render_mcp_codex_toml(servers, mcp_component, dest_root)
            else:
                path = render.render_mcp_servers_json(servers, mcp_component, dest_root)
            result.files.append(path)
            emitted["mcp"] = True
            if mcp_component.support == "manual":
                result.warnings.append(
                    "MCP config for %s must be merged by hand: %s"
                    % (target.name, path.relative_to(dest_root))
                )
        else:
            result.skipped.append(("mcp", _skip_reason(mcp_component, "not supported")))

    # ---- plugin manifest --------------------------------------------------
    manifest_component = target.component("manifest")
    if manifest_component.emitted and manifest_component.fmt == "claude-plugin-manifest":
        result.files.append(
            render.render_claude_manifest(plugin, manifest_component, dest_root, emitted)
        )

    # ---- MCP server implementations --------------------------------------
    # An emitted MCP config is useless if the server it points at is not there.
    # Bundle targets resolve {{PLUGIN_ROOT}} to the installed bundle, so the
    # server files have to travel with it; loose targets point back at the
    # source tree, where they already are.
    mcp_source = plugin.root / "mcp"
    if emitted.get("mcp") and target.bundle == "plugin" and mcp_source.is_dir():
        extras = [
            entry
            for entry in sorted(mcp_source.iterdir())
            if entry.name != "servers.json" and not entry.name.startswith(".")
        ]
        for entry in extras:
            destination = dest_root / "mcp" / entry.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if entry.is_dir():
                shutil.copytree(
                    entry, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
                )
            else:
                shutil.copyfile(entry, destination)
            result.files.append(destination)

    # ---- shared scripts ---------------------------------------------------
    if plugin.scripts_dir and target.bundle == "plugin":
        destination = dest_root / "scripts"
        shutil.copytree(
            plugin.scripts_dir,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        result.files.append(destination)
    elif plugin.scripts_dir:
        result.skipped.append(
            (
                "scripts",
                "plugin-level scripts/ only ships with bundle targets; skills that need a "
                "script on this harness must carry it in their own scripts/ directory",
            )
        )

    # ---- notes ------------------------------------------------------------
    notes: List[str] = ["# %s — %s" % (plugin.name, target.name), ""]
    if target.docs:
        notes.append("Harness docs: %s" % target.docs)
        notes.append("")
    if target.install:
        notes.append("## Install")
        notes.append("")
        notes.append("```bash")
        notes.append(
            "python -m tools.apkit install %s --target %s --scope user" % (plugin.name, target.id)
        )
        notes.append("```")
        notes.append("")
        for scope, placements in target.install.items():
            notes.append("**%s scope**" % scope)
            notes.append("")
            for placement in placements:
                notes.append(
                    "- `%s` → `%s` (%s)" % (placement.component, placement.dest, placement.mode)
                )
            notes.append("")
    if result.skipped:
        notes.append("## Not emitted for this target")
        notes.append("")
        for component_name, reason in result.skipped:
            notes.append("- **%s** — %s" % (component_name, reason))
        notes.append("")
    unverified = target.unverified()
    if unverified:
        notes.append("## Unverified mappings")
        notes.append("")
        notes.append(
            "These component paths are best-effort and may drift with the harness. "
            "Check them against the docs above before trusting them: %s."
            % ", ".join(unverified)
        )
        notes.append("")
    if target.notes:
        notes.append("## Notes")
        notes.append("")
        notes.extend("- %s" % note for note in target.notes)
        notes.append("")
    path = render.render_notes(dest_root, notes)
    if path:
        result.files.append(path)

    return result


def build_all(plugins: List[Plugin], targets: List[Target], dist_root: Path) -> List[BuildResult]:
    results: List[BuildResult] = []
    for plugin in plugins:
        excluded = set(plugin.excluded_targets())
        for target in targets:
            if target.id in excluded:
                continue
            results.append(build(plugin, target, dist_root))
    return results
