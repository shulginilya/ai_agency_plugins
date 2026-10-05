"""The repository handbook: every plugin, command, agent and integration in one PDF.

Everything is read from source — plugin.json, commands/*.md, agents/*.md,
skills/*/SKILL.md, hooks/hooks.json, the MCP servers' TOOLS lists, targets/*.json,
integrations/*/README.md and the CLI's own argparse definitions — so the handbook
cannot drift from the code. Rebuild it with `apkit docs` whenever a plugin changes.

The HTML is produced with the standard library alone. Turning it into a PDF
needs a renderer, and the one every machine already has is a Chromium-family
browser (Chrome, Edge, Chromium) in headless mode, so that is what is used. With
no browser found the HTML is still written and the command says how to point
it at one.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .model import Doc, Plugin
from .targets import COMPONENTS, Target

BROWSER_ENV = "APKIT_BROWSER"
_ROOT_REF = re.compile(r"""(?:\$\{CLAUDE_PLUGIN_ROOT\}|\{\{PLUGIN_ROOT\}\})/([^"'\s]+)""")


class DocsError(Exception):
    """The handbook could not be rendered to PDF."""


# ------------------------------------------------------------------ markdown


_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)")


def inline(text: str) -> str:
    """Render inline markdown — code spans, links, bold, italics — as HTML."""
    links: List[str] = []

    def stash(match: "re.Match[str]") -> str:
        label, href = inline(match.group(1)), match.group(2)
        if href.startswith(("http://", "https://", "mailto:")):
            links.append('<a href="%s">%s</a>' % (html.escape(href), label))
        else:
            # Repo-relative links point nowhere once the page is a PDF.
            links.append(label)
        return "\x00%d\x00" % (len(links) - 1)

    text = _LINK.sub(stash, text)
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if len(part) >= 2 and part.startswith("`") and part.endswith("`"):
            out.append("<code>%s</code>" % html.escape(part[1:-1]))
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", part)
        out.append(part)
    rendered = "".join(out)
    return re.sub(r"\x00(\d+)\x00", lambda m: links[int(m.group(1))], rendered)


def _cells(row: str) -> List[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)]


def markdown(text: str, shift: int = 0) -> str:
    """A deliberately small markdown renderer: enough for this repo's READMEs.

    Headings (shifted down by `shift` levels), fenced code, pipe tables, flat
    lists, block quotes, rules and paragraphs.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    para: List[str] = []

    def flush() -> None:
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            del para[:]

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading:
            flush()
            level = min(6, len(heading.group(1)) + shift)
            out.append("<h%d>%s</h%d>" % (level, inline(heading.group(2)), level))
            i += 1
            continue
        if not stripped:
            flush()
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|?\s*:?-{3,}", lines[i + 1].strip())
        ):
            flush()
            header = [inline(c) for c in _cells(stripped)]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([inline(c) for c in _cells(lines[i])])
                i += 1
            out.append(table(header, rows))
            continue
        item = _LIST_ITEM.match(line)
        if item:
            flush()
            ordered = item.group(2)[0].isdigit()
            items: List[str] = []
            while i < len(lines):
                item = _LIST_ITEM.match(lines[i])
                if item:
                    items.append(item.group(3))
                elif items and lines[i].strip() and lines[i][:1] in (" ", "\t"):
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(
                "<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag)
            )
            continue
        if stripped.startswith(">"):
            flush()
            out.append("<blockquote>%s</blockquote>" % inline(stripped.lstrip("> ")))
            i += 1
            continue
        para.append(stripped)
        i += 1
    flush()
    return "\n".join(out)


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], cls: str = "") -> str:
    """An HTML table from cells that are already HTML."""
    head = "".join("<th>%s</th>" % h for h in headers)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in row) for row in rows)
    attr = ' class="%s"' % cls if cls else ""
    return "<table%s><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (attr, head, body)


def readme_section(text: str, heading: str) -> str:
    """The body of one `## heading` section of a markdown file, or ''."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    inside = fenced = False
    for line in lines:
        if line.strip().startswith("```"):
            fenced = not fenced
        if not fenced and re.match(r"^##\s+", line):
            if inside:
                break
            inside = line[2:].strip().lower() == heading.lower()
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


# ------------------------------------------------------------ source readers


def mcp_tools(plugin: Plugin) -> List[Tuple[str, str]]:
    """(name, description) for each tool the plugin's MCP servers declare.

    Read with `ast`, never imported: a server module runs its imports at load
    time, and documenting a plugin must not execute it.
    """
    mcp_dir = plugin.root / "mcp"
    found: List[Tuple[str, str]] = []
    if not mcp_dir.is_dir():
        return found
    for script in sorted(mcp_dir.glob("*.py")):
        try:
            tree = ast.parse(script.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            else:
                continue
            if not (isinstance(target, ast.Name) and target.id == "TOOLS"):
                continue
            if not isinstance(value, ast.List):
                continue
            for element in value.elts:
                if not isinstance(element, ast.Dict):
                    continue
                entry: Dict[str, str] = {}
                for key, val in zip(element.keys, element.values):
                    if isinstance(key, ast.Constant) and key.value in ("name", "description"):
                        try:
                            entry[key.value] = str(ast.literal_eval(val))
                        except ValueError:
                            pass
                if "name" in entry:
                    found.append((entry["name"], entry.get("description", "")))
    return found


def script_summary(path: Path) -> str:
    """The first paragraph of a script's module docstring, on one line."""
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
    except (OSError, SyntaxError, ValueError):
        return ""
    first = doc.strip().split("\n\n")[0]
    return " ".join(first.split())


def hook_rows(plugin: Plugin) -> List[Tuple[str, str, str, str]]:
    """(event, matcher, script, what it does) for each hook the plugin wires."""
    raw = plugin.hooks or {}
    events = raw.get("hooks", raw)
    rows = []
    for event, groups in events.items():
        for group in groups or []:
            matcher = str(group.get("matcher", ""))
            for hook in group.get("hooks") or []:
                command = str(hook.get("command", ""))
                ref = _ROOT_REF.search(command)
                script = ref.group(1) if ref else command
                summary = script_summary(plugin.root / script) if ref else ""
                rows.append((event, matcher, script, summary))
    return rows


def argument_hint(command: Doc) -> str:
    meta = command.meta
    return str(meta.get("argument_hint") or meta.get("argument-hint") or "").strip()


def cli_reference(parser: argparse.ArgumentParser) -> List[Tuple[str, str, List[Tuple[str, str]]]]:
    """(usage, help, [(flag, help)]) for each subcommand of the CLI."""
    found = []
    for action in parser._actions:  # argparse exposes no public walk
        if not isinstance(action, argparse._SubParsersAction):
            continue
        helps = {a.dest: a.help or "" for a in action._choices_actions}
        for name, sub in action.choices.items():
            positionals, options = [], []
            for opt in sub._actions:
                if isinstance(opt, argparse._HelpAction) or opt.help == argparse.SUPPRESS:
                    continue
                if not opt.option_strings:
                    positionals.append("<%s>" % opt.dest)
                    continue
                flag = ", ".join(opt.option_strings)
                if opt.nargs != 0:
                    flag += " " + (opt.metavar or opt.dest.upper())
                text = opt.help or ""
                if opt.choices:
                    text += (" " if text else "") + "(one of: %s)" % ", ".join(opt.choices)
                if opt.default not in (None, False, argparse.SUPPRESS) and "default" not in text:
                    text += (" " if text else "") + "(default: %s)" % opt.default
                if isinstance(opt, argparse._AppendAction):
                    text += (" " if text else "") + "(repeatable)"
                options.append((flag, text))
            usage = " ".join(["apkit", name] + positionals + (["[options]"] if options else []))
            found.append((usage, helps.get(name, ""), options))
    return found


def git_stamp(root: Path) -> str:
    """`branch @ sha` for the tree being documented, or '' outside git.

    Read-only rev-parse only: anything that refreshes the index can leave a
    lock file behind on some mounts.
    """
    def ask(*args: str) -> str:
        try:
            done = subprocess.run(
                ["git", "-C", str(root)] + list(args),
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return done.stdout.strip() if done.returncode == 0 else ""

    branch, sha = ask("rev-parse", "--abbrev-ref", "HEAD"), ask("rev-parse", "--short", "HEAD")
    return "%s @ %s" % (branch, sha) if branch and sha else ""


# ------------------------------------------------------------------ the page


CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm;
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt sans-serif; color: #888; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 9.5pt/1.45 "Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif;
  color: #1d2129; background: #fff; margin: 0; }
h1, h2, h3, h4 { line-height: 1.25; color: #10131a; }
h1 { font-size: 20pt; margin: 0 0 4mm; padding-bottom: 2mm; border-bottom: 2px solid #2f5bd3;
  break-before: page; }
h2 { font-size: 13.5pt; margin: 7mm 0 2mm; break-after: avoid; }
h3 { font-size: 11pt; margin: 5mm 0 1.5mm; break-after: avoid; }
h4, h5, h6 { font-size: 10pt; margin: 4mm 0 1mm; break-after: avoid; }
p { margin: 1.5mm 0; }
a { color: #2f5bd3; text-decoration: none; }
code { font: 8.5pt Consolas, "SF Mono", Menlo, monospace; background: #f1f3f7;
  padding: 0 .3em; border-radius: 3px; }
pre { background: #f6f7fa; border: 1px solid #e3e6ec; border-radius: 4px; padding: 2.5mm 3mm;
  white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 3mm; font-size: 8.8pt; }
th, td { text-align: left; vertical-align: top; padding: 1.4mm 2mm; border-bottom: 1px solid #e3e6ec; }
th { background: #eef1f7; font-weight: 600; }
tr { break-inside: avoid; }
td:first-child { white-space: nowrap; }
td.wrap, table.wrap td:first-child { white-space: normal; }
blockquote { margin: 2mm 0; padding-left: 3mm; border-left: 3px solid #cfd6e4; color: #4a5160; }
ul, ol { margin: 1.5mm 0; padding-left: 5mm; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.cover h1 { break-before: auto; font-size: 30pt; border: none; margin-bottom: 2mm; }
.cover .lede { font-size: 12pt; color: #4a5160; max-width: 140mm; }
.cover .stamp { margin-top: 8mm; color: #6b7280; font-size: 9pt; }
.stats { display: flex; flex-wrap: wrap; gap: 4mm; margin-top: 10mm; }
.stat { border: 1px solid #e3e6ec; border-radius: 6px; padding: 3mm 4mm; min-width: 28mm; }
.stat b { display: block; font-size: 18pt; color: #2f5bd3; }
.stat span { font-size: 8.5pt; color: #6b7280; }
.toc ol { list-style: none; padding: 0; columns: 2; }
.toc li { margin: 1mm 0; }
.toc li.sub { padding-left: 4mm; font-size: 9pt; }
.plugin { break-inside: auto; }
.plugin + .plugin { break-before: page; }
td code { overflow-wrap: break-word; }
table.hooks { table-layout: fixed; }
table.hooks th:nth-child(1) { width: 14%; }
table.hooks th:nth-child(2) { width: 26%; }
table.hooks th:nth-child(3) { width: 24%; }
table.hooks code { overflow-wrap: anywhere; }
.meta { color: #6b7280; font-size: 8.5pt; }
.usage { font-weight: 600; }
.lv { font-weight: 600; font-size: 8.3pt; padding: .2mm 1.5mm; border-radius: 3px; white-space: nowrap; }
.native { background: #e3f4e8; color: #17672f; }
.emulated { background: #fff3d6; color: #835c00; }
.manual { background: #e5ecfb; color: #2448a8; }
.unsupported { background: #f2f2f4; color: #7a7f8a; }
.matrix td, .matrix th { text-align: center; }
.matrix td:first-child, .matrix th:first-child { text-align: left; }
.legend { font-size: 8.5pt; color: #4a5160; }
"""


def _anchor(*parts: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-") for p in parts)


def _plugin_section(plugin: Plugin) -> str:
    out = ['<section class="plugin" id="%s">' % _anchor("plugin", plugin.name)]
    title = plugin.manifest.get("displayName") or plugin.name
    out.append("<h2>%s</h2>" % html.escape(str(title)))
    out.append(
        '<p class="meta"><code>%s</code> · v%s</p>'
        % (html.escape(plugin.name), html.escape(plugin.version))
    )
    out.append("<p>%s</p>" % inline(plugin.description))

    if plugin.agents:
        out.append("<h3>Agents</h3>")
        rows = []
        for agent in plugin.agents:
            meta = agent.meta
            tools = meta.get("tools") or ""
            if isinstance(tools, list):
                tools = ", ".join(str(t) for t in tools)
            rows.append([
                "<code>%s</code>" % html.escape(str(meta.get("name") or agent.name)),
                inline(str(meta.get("description", ""))),
                html.escape(str(meta.get("model") or "inherit")),
                html.escape(str(tools) or "all"),
            ])
        out.append(table(["Agent", "What it does", "Model", "Tools"], rows))

    if plugin.commands:
        out.append("<h3>Slash commands</h3>")
        rows = []
        for command in plugin.commands:
            hint = argument_hint(command)
            usage = "/%s%s" % (command.name, (" " + hint) if hint else "")
            rows.append([
                '<code class="usage">%s</code>' % html.escape(usage),
                inline(str(command.meta.get("description", ""))),
            ])
        out.append(table(["Usage", "What it does"], rows, cls="wrap"))

    if plugin.skills:
        out.append("<h3>Skills</h3>")
        rows = [
            ["<code>%s</code>" % html.escape(s.name), inline(s.description)] for s in plugin.skills
        ]
        out.append(table(["Skill", "When it triggers"], rows))

    tools = mcp_tools(plugin)
    if tools:
        out.append("<h3>MCP tools</h3>")
        servers = ", ".join("<code>%s</code>" % html.escape(n) for n in plugin.mcp_servers)
        if servers:
            out.append('<p class="meta">Server: %s</p>' % servers)
        out.append(table(
            ["Tool", "What it does"],
            [["<code>%s</code>" % html.escape(n), inline(d)] for n, d in tools],
        ))

    hooks = hook_rows(plugin)
    if hooks:
        out.append("<h3>Hooks</h3>")
        out.append(table(
            ["Event", "Fires on", "Script", "Behaviour"],
            [
                [
                    html.escape(event),
                    "<code>%s</code>" % html.escape(matcher) if matcher else "every session",
                    "<code>%s</code>" % html.escape(script),
                    inline(summary) or "—",
                ]
                for event, matcher, script, summary in hooks
            ],
            cls="wrap hooks",
        ))
    out.append("</section>")
    return "\n".join(out)


def _matrix(targets: Sequence[Target]) -> str:
    rows = []
    notes = []
    for target in targets:
        cells = ["<strong>%s</strong><br><code>%s</code>" % (html.escape(target.name), target.id)]
        for name in COMPONENTS:
            comp = target.component(name)
            mark = " †" if comp.emitted and not comp.verified else ""
            cells.append('<span class="lv %s">%s</span>%s' % (comp.support, comp.support, mark))
            if comp.note:
                notes.append((target.name, name, comp.note))
        rows.append(cells)
    out = [table(["Target"] + list(COMPONENTS), rows, cls="matrix")]
    out.append(
        '<p class="legend"><span class="lv native">native</span> the harness has it · '
        '<span class="lv emulated">emulated</span> projected onto something it does have · '
        '<span class="lv manual">manual</span> emitted, you wire it in · '
        '<span class="lv unsupported">unsupported</span> dropped, with the reason in '
        "<code>INSTALL.md</code> · † mapping not yet checked against the harness's own docs</p>"
    )
    if notes:
        out.append("<h2>What degrades, and why</h2>")
        out.append(table(
            ["Target", "Component", "Note"],
            [[html.escape(t), html.escape(c), inline(n)] for t, c, n in notes],
            cls="wrap",
        ))
    return "\n".join(out)


def _cli(parser: argparse.ArgumentParser) -> str:
    out = [
        "<p>Run from the repo root as <code>python -m tools.apkit &lt;command&gt;</code>, "
        "or as <code>apkit</code> after <code>pip install -e .</code>. "
        "<code>--root DIR</code> before the command points it at another checkout.</p>"
    ]
    for usage, text, options in cli_reference(parser):
        out.append("<h3><code>%s</code></h3>" % html.escape(usage))
        if text:
            out.append("<p>%s</p>" % inline(text[:1].upper() + text[1:] + "."))
        if options:
            out.append(table(
                ["Option", "Meaning"],
                [["<code>%s</code>" % html.escape(f), inline(h) or "—"] for f, h in options],
            ))
    return "\n".join(out)


def _integrations(root: Path) -> str:
    base = root / "integrations"
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    if not dirs:
        return "<p>No integrations yet.</p>"
    out = []
    for directory in dirs:
        out.append('<section id="%s">' % _anchor("integration", directory.name))
        readme = directory / "README.md"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8")
            if not re.match(r"^\s*#\s", text):
                out.append("<h2>%s</h2>" % html.escape(directory.name))
            out.append(markdown(text, shift=1))
        else:
            out.append("<h2>%s</h2>" % html.escape(directory.name))
            files = ", ".join("<code>%s</code>" % html.escape(p.name) for p in sorted(directory.iterdir()))
            out.append("<p>Files: %s</p>" % files)
        out.append("</section>")
    return "\n".join(out)


def render_html(
    root: Path,
    plugins: Sequence[Plugin],
    targets: Sequence[Target],
    parser: argparse.ArgumentParser,
    today: Optional[datetime.date] = None,
) -> str:
    today = today or datetime.date.today()
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    lede = ""
    for block in re.split(r"\n\s*\n", readme):
        if block.strip() and not block.lstrip().startswith("#"):
            lede = " ".join(block.split())
            break

    n_cmd = sum(len(p.commands) for p in plugins)
    n_agent = sum(len(p.agents) for p in plugins)
    n_skill = sum(len(p.skills) for p in plugins)
    n_tool = sum(len(mcp_tools(p)) for p in plugins)
    stamp = git_stamp(root)
    stats = [
        (len(plugins), "plugins"), (n_cmd, "slash commands"), (n_agent, "agents"),
        (n_skill, "skills"), (n_tool, "MCP tools"), (len(targets), "harness targets"),
    ]

    toc = ['<li><a href="#quick-start">1. Quick start</a></li>',
           '<li><a href="#commands">2. Slash commands</a></li>',
           '<li><a href="#plugins">3. Plugins</a></li>']
    toc += [
        '<li class="sub"><a href="#%s">%s</a></li>'
        % (_anchor("plugin", p.name), html.escape(str(p.manifest.get("displayName") or p.name)))
        for p in plugins
    ]
    toc += ['<li><a href="#integrations">4. Integrations</a></li>',
            '<li><a href="#matrix">5. Harness support</a></li>',
            '<li><a href="#cli">6. apkit CLI reference</a></li>']

    command_rows = []
    for plugin in plugins:
        for command in plugin.commands:
            hint = argument_hint(command)
            command_rows.append([
                '<code class="usage">/%s%s</code>'
                % (html.escape(command.name), html.escape((" " + hint) if hint else "")),
                '<a href="#%s">%s</a>' % (_anchor("plugin", plugin.name), html.escape(plugin.name)),
                inline(str(command.meta.get("description", ""))),
            ])

    quick = readme_section(readme, "Quick start")
    body = [
        '<div class="cover">',
        "<h1>ai_agency_plugins</h1>",
        '<p class="lede">%s</p>' % inline(lede),
        '<div class="stats">%s</div>'
        % "".join('<div class="stat"><b>%d</b><span>%s</span></div>' % s for s in stats),
        '<p class="stamp">Generated %s%s by <code>apkit docs</code> — do not edit by hand; '
        "rebuild it.</p>" % (today.isoformat(), (" from " + html.escape(stamp)) if stamp else ""),
        "</div>",
        '<nav class="toc"><h1 style="break-before:page">Contents</h1><ol>%s</ol></nav>' % "".join(toc),
        '<h1 id="quick-start">1. Quick start</h1>',
        markdown(quick, shift=1) if quick else "<p>See README.md.</p>",
        '<h1 id="commands">2. Slash commands</h1>',
        "<p>Type the command in any harness that has commands; the argument is optional unless "
        "the hint says otherwise. In Claude Code each command is also reachable as "
        "<code>/&lt;plugin&gt;:&lt;command&gt;</code> when two plugins share a name. Harnesses "
        "without a command format get the same text as a skill — see section 5.</p>",
        table(["Usage", "Plugin", "What it does"], command_rows, cls="wrap"),
        '<h1 id="plugins">3. Plugins</h1>',
        "<p>Per plugin: the agents it ships, its commands, the skills that trigger on their own, "
        "the MCP tools it serves and the hooks it wires (Claude Code only).</p>",
    ]
    body += [_plugin_section(p) for p in plugins]
    body += [
        '<h1 id="integrations">4. Integrations</h1>',
        _integrations(root),
        '<h1 id="matrix">5. Harness support</h1>',
        "<p>What each target harness does with each component type, read from "
        "<code>targets/*.json</code>.</p>",
        _matrix(targets),
        '<h1 id="cli">6. apkit CLI reference</h1>',
        _cli(parser),
    ]
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        "<title>ai_agency_plugins handbook</title><style>%s</style></head><body>\n%s\n</body></html>\n"
        % (CSS, "\n".join(body))
    )


# ------------------------------------------------------------------ PDF output


def _browser_candidates() -> List[str]:
    names = [
        "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
        "msedge", "microsoft-edge", "microsoft-edge-stable",
    ]
    found = [p for p in (shutil.which(n) for n in names) if p]
    if os.name == "nt":
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if not base:
                continue
            found.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
            found.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
    if sys.platform == "darwin":
        for app in ("Google Chrome", "Microsoft Edge", "Chromium"):
            found.append("/Applications/%s.app/Contents/MacOS/%s" % (app, app))
    return found


def find_browser(explicit: Optional[str] = None) -> Optional[str]:
    """A Chromium-family browser: --browser, then $APKIT_BROWSER, then the usual places."""
    chosen = explicit or os.environ.get(BROWSER_ENV)
    if chosen:
        resolved = shutil.which(chosen) or chosen
        return resolved if os.path.isfile(resolved) else None
    for candidate in _browser_candidates():
        if os.path.isfile(candidate):
            return candidate
    return None


def print_pdf(browser: str, html_path: Path, pdf_path: Path, timeout: int = 180) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    partial = pdf_path.with_name(pdf_path.name + ".partial")
    if partial.exists():
        partial.unlink()
    with tempfile.TemporaryDirectory(prefix="apkit-docs-") as profile:
        cmd = [
            browser, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--user-data-dir=%s" % profile,
            "--no-pdf-header-footer", "--print-to-pdf-no-header",
            "--print-to-pdf=%s" % partial, html_path.resolve().as_uri(),
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")  # Chromium refuses to run as root otherwise
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise DocsError("%s did not finish within %ds" % (browser, timeout)) from exc
        except OSError as exc:
            raise DocsError("could not run %s: %s" % (browser, exc)) from exc
    if not partial.is_file() or partial.stat().st_size == 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
        raise DocsError("%s wrote no PDF (exit %d)%s" % (
            browser, done.returncode, (": " + " | ".join(detail)) if detail else ""))
    # Replace only once the new file is complete, so a failed run never
    # leaves a half-written handbook where the committed one was.
    os.replace(str(partial), str(pdf_path))
