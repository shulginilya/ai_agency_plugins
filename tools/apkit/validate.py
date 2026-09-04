"""Validation of plugin sources against the Agent Skills spec and repo rules.

Reference: https://agentskills.io/specification
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from .model import Plugin

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")

NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
BODY_SOFT_LIMIT_LINES = 500

SKILL_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}

# Claude Code lifecycle events. Unknown events are a warning, not an error:
# the list grows, and a plugin may legitimately target a newer runtime.
KNOWN_HOOK_EVENTS = {
    "SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion", "PreToolUse",
    "PermissionRequest", "PermissionDenied", "PostToolUse", "PostToolUseFailure",
    "PostToolBatch", "Notification", "MessageDisplay", "SubagentStart", "SubagentStop",
    "TaskCreated", "TaskCompleted", "Stop", "StopFailure", "TeammateIdle",
    "InstructionsLoaded", "ConfigChange", "CwdChanged", "DirectoryAdded", "FileChanged",
    "WorktreeCreate", "WorktreeRemove", "PreCompact", "PostCompact", "PreModelSwitch",
    "PostModelSwitch", "Elicitation", "ElicitationResult", "SessionEnd",
}


@dataclass
class Finding:
    level: str  # "error" | "warning"
    where: str
    message: str

    def __str__(self) -> str:
        mark = "ERROR" if self.level == "error" else "warn "
        return "%s  %s: %s" % (mark, self.where, self.message)


class Report:
    def __init__(self) -> None:
        self.findings: List[Finding] = []

    def error(self, where: str, message: str) -> None:
        self.findings.append(Finding("error", where, message))

    def warn(self, where: str, message: str) -> None:
        self.findings.append(Finding("warning", where, message))

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "warning"]

    def ok(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)


def _check_name(report: Report, where: str, value: Any, expected: str = None) -> None:
    if not value:
        report.error(where, "missing required field 'name'")
        return
    name = str(value)
    if len(name) > NAME_MAX:
        report.error(where, "name is %d chars, max is %d" % (len(name), NAME_MAX))
    if not NAME_RE.match(name):
        report.error(
            where,
            "name %r must be lowercase alphanumerics and single hyphens, "
            "not starting or ending with one" % name,
        )
    if expected is not None and name != expected:
        report.error(where, "name %r must match its directory name %r" % (name, expected))


def _check_description(
    report: Report, where: str, value: Any, require_trigger: bool = True
) -> None:
    if not value or not str(value).strip():
        report.error(where, "missing required field 'description'")
        return
    text = str(value)
    if len(text) > DESCRIPTION_MAX:
        report.error(where, "description is %d chars, max is %d" % (len(text), DESCRIPTION_MAX))
    if len(text) < 40:
        report.warn(
            where,
            "description is very short; say what it does AND when to use it, "
            "with words a user would actually type",
        )
    if require_trigger:
        lowered = text.lower()
        if "use when" not in lowered and "use this" not in lowered:
            report.warn(
                where, "description has no explicit trigger clause (e.g. 'Use when ...')"
            )


def validate_skill(report: Report, plugin: Plugin, skill) -> None:
    where = "%s/skills/%s/SKILL.md" % (plugin.name, skill.name)
    meta: Dict[str, Any] = skill.meta

    _check_name(report, where, meta.get("name"), expected=skill.name)
    _check_description(report, where, meta.get("description"))

    unknown = set(meta) - SKILL_FRONTMATTER_KEYS
    if unknown:
        report.warn(
            where,
            "non-spec frontmatter key(s): %s — harnesses may ignore or reject them; "
            "put harness-specific config in plugin.json or targets/"
            % ", ".join(sorted(unknown)),
        )

    compatibility = meta.get("compatibility")
    if compatibility and len(str(compatibility)) > COMPATIBILITY_MAX:
        report.error(where, "compatibility exceeds %d chars" % COMPATIBILITY_MAX)

    metadata = meta.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            report.error(where, "metadata must be a mapping of string keys to string values")
        else:
            for key, value in metadata.items():
                if not isinstance(value, str):
                    report.warn(
                        where, "metadata.%s is not a string; the spec defines a string map" % key
                    )

    line_count = len(skill.body.splitlines())
    if line_count > BODY_SOFT_LIMIT_LINES:
        report.warn(
            where,
            "body is %d lines; keep SKILL.md under %d and move detail into references/"
            % (line_count, BODY_SOFT_LIMIT_LINES),
        )

    for reference in re.findall(r"\]\(([^)]+)\)", skill.body):
        if reference.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (skill.path / reference).resolve()
        if not target.exists():
            report.error(where, "broken relative reference: %s" % reference)
        elif reference.count("/") > 1:
            report.warn(where, "reference %s is more than one level deep" % reference)


def validate_doc(report: Report, plugin: Plugin, doc, kind: str) -> None:
    where = "%s/%s/%s.md" % (plugin.name, kind, doc.name)
    if not NAME_RE.match(doc.name):
        report.error(where, "file name %r must be lowercase-hyphenated" % doc.name)
    _check_description(
        report, where, doc.meta.get("description"), require_trigger=(kind == "agents")
    )
    if kind == "agents":
        declared = doc.meta.get("name")
        if declared and str(declared) != doc.name:
            report.error(where, "frontmatter name %r must match file name %r" % (declared, doc.name))
    if "{{ARGS}}" not in doc.body and kind == "commands":
        report.warn(
            where,
            "no {{ARGS}} placeholder; the command will ignore whatever the user types after it",
        )


def validate_plugin(plugin: Plugin, strict: bool = False) -> Report:
    report = Report()
    where = "%s/plugin.json" % plugin.name
    manifest = plugin.manifest

    _check_name(report, where, manifest.get("name"), expected=plugin.root.name)
    _check_description(report, where, manifest.get("description"))

    version = manifest.get("version")
    if not version:
        report.error(where, "missing 'version'")
    elif not SEMVER_RE.match(str(version)):
        report.error(where, "version %r is not semver (MAJOR.MINOR.PATCH)" % version)

    if not manifest.get("license"):
        report.warn(where, "no 'license' declared")

    if not (plugin.skills or plugin.commands or plugin.agents or plugin.mcp_servers):
        report.error(plugin.name, "plugin has no skills, commands, agents or MCP servers")

    seen = set()
    for skill in plugin.skills:
        if skill.name in seen:
            report.error(plugin.name, "duplicate skill name %r" % skill.name)
        seen.add(skill.name)
        validate_skill(report, plugin, skill)

    for command in plugin.commands:
        validate_doc(report, plugin, command, "commands")

    for agent in plugin.agents:
        validate_doc(report, plugin, agent, "agents")
        if agent.name in seen:
            report.error(
                plugin.name,
                "agent %r collides with a skill of the same name; targets without "
                "subagents emit agents as skills" % agent.name,
            )

    for server_name, server in (plugin.mcp_servers or {}).items():
        location = "%s/mcp/servers.json" % plugin.name
        if not isinstance(server, dict):
            report.error(location, "server %r must be an object" % server_name)
            continue
        if not (server.get("command") or server.get("url")):
            report.error(location, "server %r needs either 'command' or 'url'" % server_name)

    if plugin.hooks:
        location = "%s/hooks/hooks.json" % plugin.name
        events = plugin.hooks.get("hooks", plugin.hooks)
        if not isinstance(events, dict):
            report.error(location, "hooks must be an object keyed by event name")
        else:
            for event in events:
                if event not in KNOWN_HOOK_EVENTS:
                    report.warn(location, "unrecognized hook event %r" % event)

    return report
