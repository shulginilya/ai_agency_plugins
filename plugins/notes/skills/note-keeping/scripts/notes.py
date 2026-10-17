#!/usr/bin/env python3
"""Running notes in plain Markdown: capture, organize, see what is open, turn items into tickets.

    notes.py where                                   the notes folder in use, and why
    notes.py set-root PATH                           remember the notes folder (Windows paths are fine)
    notes.py add --topic T (--todo|--wip|--note) TEXT  capture into topics/<t>.md
    notes.py status [--topic T]                      open items per topic
    notes.py scan [--topic T] [--json]               every item: status, section, file:line, ticket
    notes.py organize --file F [--write]             regroup one file into the standard sections
    notes.py check BEFORE AFTER                      prove an edit lost or duplicated no line
    notes.py defaults [--repo O/R] [--board N|NAME] [--assignee LOGIN|@me|none]
                                                     where tickets go when a topic names nothing
    notes.py export [--status todo,wip,done] [--topic T] [--repo O/R] [--board N] [--assignee A] --out DIR
    notes.py file --plans DIR [--yes]                create the tickets, then link them back

Where the notes are, first match wins: --root, then $NOTES_DIR, then the folder
saved by `set-root` (in $XDG_CONFIG_HOME/ai-agency/notes.json, by default
~/.config/ai-agency/notes.json).

File format: one Markdown file per topic, optional front matter (topic, repo,
board), and the sections `## In progress`, `## TODO`, `## Done`, `## Dropped`
and `## Notes`. Items: `- [ ]` todo, `- [/]` in progress, `- [x]` done,
`- [-]` dropped. Loose `TODO:` / `WIP:` lines count as items. Indented lines
under an item belong to it. A filed item ends with `→ #N` or `→ owner/repo#N`.

Inline markers count anywhere in a line, mid-sentence too: `"text"(todo)`,
`"text"(optional)` (both go to the backlog), `"text"(wip)` and `"text"(done)`
or `"text"(+)`, in any case. The quoted text is
the ticket title. A filed marker is followed by `→ #N`. Inline done markers are
filed into the Done column and closed; checkbox `- [x]` items never are.

Defaults for topics whose front matter names no repo, board or assignee are
saved in the same config file by `defaults`. The assignee defaults to @me.

Standard library only. Exit status: 0 done, 1 GitHub or a check failed, 2 bad input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STATUSES = ("wip", "todo", "done", "dropped")
SECTION = {"wip": "In progress", "todo": "TODO", "done": "Done", "dropped": "Dropped"}
SECTION_ALIASES = {
    "in progress": "wip", "wip": "wip", "doing": "wip", "work in progress": "wip",
    "todo": "todo", "to do": "todo", "todos": "todo", "next": "todo",
    "done": "done", "completed": "done", "dropped": "dropped", "won't do": "dropped",
    "notes": "notes", "log": "notes",
}
MARK = {" ": "todo", "/": "wip", "~": "wip", "x": "done", "X": "done", "-": "dropped"}
CANON = {"todo": " ", "wip": "/", "done": "x", "dropped": "-"}
ITEM_RE = re.compile(r"^(\s*)[-*+] \[([ /~xX-])\]\s+(.*)$")
LOOSE_RE = re.compile(r"^(\s*)(TODO|FIXME|WIP|DOING)\s*:\s*(.+)$", re.I)
LOOSE_STATUS = {"todo": "todo", "fixme": "todo", "wip": "wip", "doing": "wip"}
TICKET_RE = re.compile(r"\s*(?:→|->)\s*((?:[\w.-]+/[\w.-]+)?#\d+)\s*$")
TITLE_MAX = 80
DEFAULT_COLUMNS = {"todo": "Backlog", "wip": "In progress", "done": "Done"}
INLINE_RE = re.compile(r'["\u201c]([^"\u201c\u201d\n]+)["\u201d]\s*\((todo|optional|wip|done|\+)\)'
                       r'(?:\s*(?:→|->)\s*((?:[\w.-]+/[\w.-]+)?#\d+))?', re.I)
INLINE_STATUS = {"todo": "todo", "optional": "todo", "wip": "wip", "done": "done", "+": "done"}
DEFAULT_ASSIGNEE = "@me"


class NotesError(Exception):
    exit_code = 2


class CheckFailed(NotesError):
    exit_code = 1


# --- where the notes are -----------------------------------------------------


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ai-agency" / "notes.json"


def normalize_path(text: str) -> Path:
    """Accept a Windows path like C:\\Users\\me\\notes and map it to /mnt/c/... under WSL."""
    text = text.strip().strip('"')
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
    if match and os.name != "nt":
        drive, rest = match.group(1).lower(), match.group(2).replace("\\", "/")
        mount = Path("/mnt") / drive
        if mount.is_dir():
            return mount / rest
    return Path(os.path.expanduser(text))


def load_config() -> Dict[str, Any]:
    cfg = config_path()
    if not cfg.is_file():
        return {}
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except ValueError:
        raise NotesError("%s is not valid JSON; fix it or delete it and run `set-root` again" % cfg)
    return data if isinstance(data, dict) else {}


def save_config(**changes: Any) -> Path:
    """Merge changes into the config file; a None value removes the key."""
    data = load_config()
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    cfg = config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return cfg


def resolve_root(flag: Optional[str]) -> Tuple[Path, str]:
    if flag:
        return normalize_path(flag), "--root"
    if os.environ.get("NOTES_DIR"):
        return normalize_path(os.environ["NOTES_DIR"]), "$NOTES_DIR"
    saved = load_config().get("root")
    if saved:
        return normalize_path(saved), str(config_path())
    raise NotesError("no notes folder set. Run `notes.py set-root PATH`, set $NOTES_DIR, or pass --root")


def notes_root(flag: Optional[str]) -> Path:
    root, source = resolve_root(flag)
    if not root.is_dir():
        raise NotesError("the notes folder %s (from %s) does not exist" % (root, source))
    return root


def note_files(root: Path) -> List[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        files += [Path(dirpath) / f for f in sorted(filenames) if f.endswith(".md") and not f.startswith(".")]
    return files


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "untitled"


# --- parsing -----------------------------------------------------------------


def split_front_matter(lines: List[str]) -> Tuple[List[str], Dict[str, str], List[str]]:
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                meta = {}
                for raw in lines[1:end]:
                    if ":" in raw:
                        key, value = raw.split(":", 1)
                        meta[key.strip().lower()] = value.strip().strip('"\'')
                return lines[:end + 1], meta, lines[end + 1:]
    return [], {}, lines


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def parse(text: str, name: str = "") -> Dict[str, Any]:
    """Split a note into front matter, title, items (with their indented children) and prose."""
    lines = text.splitlines()
    fm_lines, meta, body = split_front_matter(lines)
    offset = len(fm_lines)
    title, items, blocks = None, [], []
    section, group = "notes", None
    i = 0
    while i < len(body):
        line, number = body[i], offset + i + 1
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if heading:
            level, label = len(heading.group(1)), heading.group(2)
            if level == 1 and title is None and not items:
                title = label
            elif level == 2:
                known = SECTION_ALIASES.get(label.lower())
                section, group = (known, None) if known else ("custom", label)
                if not known:
                    blocks.append({"kind": "heading", "lines": [line], "group": label, "line": number})
            elif section in STATUSES and level >= 3:
                group = label
            else:
                blocks.append({"kind": "prose", "lines": [line], "group": group, "section": section, "line": number})
            i += 1
            continue
        item = ITEM_RE.match(line)
        loose = None if item else LOOSE_RE.match(line)
        if item or loose:
            base = indent(line)
            if item:
                status, rest = MARK[item.group(2)], item.group(3)
            else:
                status, rest = LOOSE_STATUS[loose.group(2).lower()], loose.group(3)
            children = []
            j = i + 1
            while j < len(body) and (not body[j].strip() or indent(body[j]) > base):
                if not body[j].strip():
                    # a blank line ends the item unless more indented lines follow it
                    k = j
                    while k < len(body) and not body[k].strip():
                        k += 1
                    if k >= len(body) or indent(body[k]) <= base:
                        break
                children.append(body[j])
                j += 1
            ticket = TICKET_RE.search(rest)
            items.append({
                "status": status, "text": TICKET_RE.sub("", rest).strip(),
                "ticket": ticket.group(1) if ticket else None, "line": number,
                "raw": line, "children": children, "section": section, "group": group,
                "loose": bool(loose), "indent": base,
            })
            i = j
            continue
        blocks.append({"kind": "prose", "lines": [line], "group": group, "section": section, "line": number})
        i += 1
    topic = meta.get("topic") or title or Path(name).stem.replace("-", " ").replace("_", " ").strip() or "untitled"
    return {"front_matter": fm_lines, "meta": meta, "title": title, "topic": topic,
            "items": items, "blocks": blocks}


def inline_items(text: str) -> List[Dict[str, Any]]:
    """Every inline `"text"(todo|optional|wip|done|+)` marker, outside front matter and code fences."""
    lines = text.splitlines()
    fm_lines, _, body = split_front_matter(lines)
    found, fenced = [], False
    for offset, line in enumerate(body):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        for m in INLINE_RE.finditer(line):
            found.append({"status": INLINE_STATUS[m.group(2).lower()], "text": m.group(1).strip(),
                          "ticket": m.group(3), "line": len(fm_lines) + offset + 1, "raw": line,
                          "children": [], "section": None, "group": None, "loose": False,
                          "inline": True, "optional": m.group(2).lower() == "optional", "indent": 0})
    return found


def note_items(note: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    """Checkbox and loose items, plus inline markers. A checkbox line holding a marker counts once, as the marker."""
    plain = [dict(it, inline=False) for it in note["items"] if not INLINE_RE.search(it["raw"])]
    return sorted(plain + inline_items(text), key=lambda it: it["line"])


def item_line(item: Dict[str, Any]) -> str:
    """The canonical one-line form of an item: loose TODO:/WIP: lines become task items."""
    ticket = " → %s" % item["ticket"] if item["ticket"] else ""
    return "- [%s] %s%s" % (CANON[item["status"]], item["text"], ticket)


# --- organize and check ------------------------------------------------------


def organize_text(text: str, name: str = "") -> str:
    note = parse(text, name)
    out: List[str] = list(note["front_matter"])
    out.append("# %s" % (note["title"] or note["topic"]))
    for status in STATUSES:
        mine = [it for it in note["items"] if it["status"] == status]
        if not mine:
            continue
        out += ["", "## %s" % SECTION[status]]
        groups: Dict[Optional[str], List[Dict[str, Any]]] = {}
        for it in mine:
            groups.setdefault(it["group"], []).append(it)
        for group, members in groups.items():
            if group:
                out += ["", "### %s" % group]
            for it in members:
                out.append(item_line(it))
                out += [c[it["indent"]:] if c[:it["indent"]].strip() == "" else c for c in it["children"]]
    notes = [b for b in note["blocks"] if b["kind"] == "prose" and b.get("section") in ("notes", None)]
    custom: Dict[str, List[Dict[str, Any]]] = {}
    for b in note["blocks"]:
        if b.get("section") == "custom" and b["kind"] == "prose":
            custom.setdefault(b["group"], []).append(b)
        elif b.get("section") in STATUSES and b["kind"] == "prose":
            notes.append(b)  # prose that sat inside a status section moves to Notes, in order
    notes.sort(key=lambda b: b["line"])
    if any(line.strip() for b in notes for line in b["lines"]):
        out += ["", "## Notes"] + trim([line for b in notes for line in b["lines"]])
    for group, members in custom.items():
        content = trim([line for b in members for line in b["lines"]])
        if any(line.strip() for line in content):
            out += ["", "## %s" % group] + content
    return "\n".join(collapse_blanks(drop_empty_headings(out))).rstrip() + "\n"


def drop_empty_headings(lines: List[str]) -> List[str]:
    """Remove a ## or deeper heading that has no content before the next heading of its level or above."""
    out: List[str] = []
    for idx, line in enumerate(lines):
        m = re.match(r"^(#{2,6})\s", line)
        if m:
            level = len(m.group(1))
            has_content = False
            for nxt in lines[idx + 1:]:
                h = re.match(r"^(#{1,6})\s", nxt)
                if h and len(h.group(1)) <= level:
                    break
                if nxt.strip() and not h:
                    has_content = True
                    break
            if not has_content:
                continue
        out.append(line)
    return out


def trim(lines: List[str]) -> List[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines


def collapse_blanks(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line.rstrip())
    return out


def content_lines(text: str) -> Counter:
    """Every line that carries content, normalized so a regroup compares equal and a loss does not."""
    counts: Counter = Counter()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or re.match(r"^#{1,6}\s", stripped):
            continue
        loose = LOOSE_RE.match(stripped)
        if loose:
            stripped = "- [%s] %s" % (CANON[LOOSE_STATUS[loose.group(2).lower()]], loose.group(3).strip())
        item = ITEM_RE.match(stripped)
        if item:
            stripped = "- [%s] %s" % (CANON[MARK[item.group(2)]], item.group(3).strip())
        counts[re.sub(r"\s+", " ", stripped)] += 1
    return counts


def compare(before: str, after: str) -> Dict[str, List[str]]:
    a, b = content_lines(before), content_lines(after)
    return {"lost": sorted((a - b).elements()), "added": sorted((b - a).elements())}


# --- capture -----------------------------------------------------------------


def add_to(text: str, topic: str, kind: str, entry: str, today: str) -> str:
    """Append one item or note to a topic file's text, creating the section it belongs in."""
    lines = text.splitlines() if text.strip() else ["# %s" % topic]
    if kind in ("todo", "wip"):
        heading, new = "## %s" % SECTION[kind], ["- [%s] %s" % (CANON[kind], entry)]
    else:
        heading, new = "## Notes", ["### %s" % today, entry]
    order = ["## %s" % SECTION[s] for s in STATUSES] + ["## Notes"]
    if heading in lines:
        start = lines.index(heading)
        end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        if kind == "note" and "### %s" % today in lines[start:end]:
            new = [entry]
        return "\n".join(lines[:end] + new + lines[end:]).rstrip() + "\n"
    rank = order.index(heading)
    later = [k for k, line in enumerate(lines) if line in order[rank + 1:]]
    at = later[0] if later else len(lines)
    block = ([""] if at and lines[at - 1].strip() else []) + [heading] + new + ([""] if later else [])
    return "\n".join(lines[:at] + block + lines[at:]).rstrip() + "\n"


# --- export, file, link ------------------------------------------------------


def item_key(rel: str, item: Dict[str, Any]) -> str:
    kind = "inline" if item.get("inline") else ""
    digest = hashlib.sha1(("%s\0%s\0%s" % (rel, item["text"], kind)).encode("utf-8")).hexdigest()[:10]
    return "n-%s" % digest


def ticket_title(text: str) -> str:
    text = re.sub(r"\s+#[\w-]+", "", text)  # drop inline #tags
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    if len(text) <= TITLE_MAX:
        return text
    cut = text[:TITLE_MAX - 1].rsplit(" ", 1)[0]
    return cut + "…"


def ticket_body(topic: str, rel: str, item: Dict[str, Any]) -> str:
    details = "\n".join(c.strip() if not c.strip().startswith(("-", "*", "+")) else c.strip()
                        for c in item["children"] if c.strip())
    parts = ["From my notes: **%s** (`%s`, line %d, %s)." % (topic, rel, item["line"], SECTION[item["status"]]),
             "", item["text"]]
    context = INLINE_RE.sub(lambda m: m.group(1), item["raw"]).strip() if item.get("inline") else ""
    if context and context != item["text"]:
        parts += ["", "> " + context]
    if item.get("optional"):
        parts += ["", "Marked optional: nice to have, not committed."]
    if details:
        parts += ["", details]
    return "\n".join(parts) + "\n"


def export(root: Path, statuses: List[str], topic: Optional[str], repo: Optional[str],
           board: Optional[int], columns: Dict[str, str], assignee: Optional[str] = None) -> List[Dict[str, Any]]:
    """Group the unfiled items into one ticket plan per (repo, board, status).

    Open checkbox items and every inline marker are filed; a done checkbox item never is."""
    plans: Dict[Tuple[str, Optional[int], str], Dict[str, Any]] = {}
    problems = []
    for path in note_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        note = parse(text, path.name)
        if topic and slug(topic) not in (slug(note["topic"]), slug(path.stem)):
            continue
        target_repo = note["meta"].get("repo") or repo
        target_board = note["meta"].get("board") or board
        target_assignee = note["meta"].get("assignee") or assignee
        if target_assignee and target_assignee.lower() == "none":
            target_assignee = None
        for item in note_items(note, text):
            if item["status"] not in statuses or item["ticket"]:
                continue
            if item["status"] == "done" and not item["inline"]:
                continue
            if not target_repo:
                problems.append("%s: no repo — add `repo: owner/name` to its front matter or pass --repo" % rel)
                break
            try:
                board_number = int(target_board) if target_board not in (None, "") else None
            except ValueError:
                raise NotesError("%s: board %r is not a project number" % (rel, target_board))
            key = (target_repo, board_number, item["status"])
            plan = plans.setdefault(key, {"repo": target_repo, "board": board_number, "status": item["status"],
                                          "column": columns[item["status"]], "issues": [], "sources": {},
                                          "close": item["status"] == "done"})
            title = ticket_title(item["text"])
            if any(i["title"] == title for i in plan["issues"]):
                title = ticket_title("%s (%s)" % (item["text"], note["topic"]))
            k = item_key(rel, item)
            issue = {"key": k, "title": title, "body": ticket_body(note["topic"], rel, item)}
            if target_assignee:
                issue["assignees"] = [target_assignee]
            plan["issues"].append(issue)
            plan["sources"][k] = {"file": rel, "line": item["line"], "text": item["text"],
                                  "repo_in_file": bool(note["meta"].get("repo")), "inline": item["inline"]}
    if problems:
        raise NotesError("cannot export:\n  " + "\n  ".join(dict.fromkeys(problems)))
    return list(plans.values())


def write_plans(plans: List[Dict[str, Any]], out: Path) -> List[Dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for plan in plans:
        name = "%s-%s-%s" % (slug(plan["repo"]), plan["board"] or "noboard", plan["status"])
        (out / (name + ".json")).write_text(json.dumps({"issues": plan["issues"]}, indent=2) + "\n", encoding="utf-8")
        meta = {k: plan[k] for k in ("repo", "board", "status", "column", "sources", "close")}
        (out / (name + ".meta.json")).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        summary.append({"plan": str(out / (name + ".json")), "repo": plan["repo"], "board": plan["board"],
                        "column": plan["column"], "closed_after": plan["close"],
                        "assignees": sorted({a for i in plan["issues"] for a in i.get("assignees", [])}),
                        "items": [i["title"] for i in plan["issues"]]})
    return summary


def link_back(root: Path, meta: Dict[str, Any], numbers: Dict[str, int]) -> List[str]:
    """Append `→ #N` to each filed item's line, found by its text even if the file moved lines around."""
    linked = []
    by_file: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for key, src in meta["sources"].items():
        if key in numbers:
            by_file.setdefault(src["file"], []).append((key, src))
    for rel, entries in by_file.items():
        path = root / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        for key, src in entries:
            ref = "#%d" % numbers[key] if src["repo_in_file"] else "%s#%d" % (meta["repo"], numbers[key])
            at = None
            for idx, line in enumerate(lines):
                if src.get("inline"):
                    hit = next((m for m in INLINE_RE.finditer(line)
                                if m.group(1).strip() == src["text"] and not m.group(3)), None)
                    if hit:
                        lines[idx] = "%s → %s%s" % (line[:hit.end()], ref, line[hit.end():])
                        at = idx
                        break
                    continue
                m = ITEM_RE.match(line) or LOOSE_RE.match(line)
                if m and TICKET_RE.sub("", m.group(3)).strip() == src["text"] and not TICKET_RE.search(m.group(3)) \
                        and not INLINE_RE.search(line):
                    lines[idx] = "%s → %s" % (line.rstrip(), ref)
                    at = idx
                    break
            if at is None:
                linked.append("%s: could not find %r to link %s — add `→ %s` to it by hand" % (rel, src["text"], ref, ref))
                continue
            linked.append("%s:%d → %s" % (rel, at + 1, ref))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return linked


def tickets_script() -> Path:
    """tickets.py from the shared ticket-management skill: beside this skill in a built bundle,
    or in plugins/_shared when running from the repository."""
    skills = Path(__file__).resolve().parent.parent.parent
    for candidate in (skills / "ticket-management" / "scripts" / "tickets.py",
                      skills.parent.parent / "_shared" / "skills" / "ticket-management" / "scripts" / "tickets.py"):
        if candidate.is_file():
            return candidate
    raise NotesError("ticket-management/scripts/tickets.py is missing beside this skill")


def file_plans(root: Path, plans_dir: Path) -> List[Dict[str, Any]]:
    results = []
    for plan in sorted(plans_dir.glob("*.json")):
        if plan.name.endswith(".meta.json"):
            continue
        meta = json.loads(plan.with_name(plan.stem + ".meta.json").read_text(encoding="utf-8"))
        cmd = [sys.executable, str(tickets_script()), "batch", "--plan", str(plan)]
        if meta["board"]:
            cmd += ["--project", str(meta["board"]), "--status", meta["column"]]
        env = dict(os.environ, GH_REPO=meta["repo"])
        run = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
        if run.returncode != 0:
            raise CheckFailed("filing %s into %s failed: %s" % (plan.name, meta["repo"], run.stderr.strip()))
        report = json.loads(run.stdout)
        numbers = {i["key"]: i["number"] for i in report["issues"]}
        closed = []
        if meta.get("close"):
            for issue in report["issues"]:
                if not issue["created"]:
                    continue
                done = subprocess.run([sys.executable, str(tickets_script()), "close", "--issue", str(issue["number"]),
                                       "--reason", "completed"], capture_output=True, text=True, env=env, check=False)
                if done.returncode != 0:
                    raise CheckFailed("#%d was created in %s but could not be closed: %s"
                                      % (issue["number"], meta["repo"], done.stderr.strip()))
                closed.append(issue["number"])
        results.append({"repo": meta["repo"], "board": meta["board"], "column": meta["column"],
                        "created": report["created"], "skipped": report["skipped"], "closed": closed,
                        "issues": [{"number": i["number"], "title": i["title"], "created": i["created"]}
                                   for i in report["issues"]],
                        "linked": link_back(root, meta, numbers)})
    return results


# --- commands ----------------------------------------------------------------


def cmd_where(args) -> Any:
    root, source = resolve_root(args.root)
    return {"root": str(root), "from": source, "exists": root.is_dir()}


def cmd_set_root(args) -> Any:
    root = normalize_path(args.path)
    if not root.is_dir():
        raise NotesError("%s does not exist; create it first" % root)
    return {"root": str(root), "saved_in": str(save_config(root=args.path))}


def find_board(owner: str, wanted: str) -> Dict[str, Any]:
    """A board of `owner` by exact title (case-insensitive), through board.py's GraphQL plumbing."""
    sys.path.insert(0, str(tickets_script().parent))
    import board  # type: ignore
    nodes = "projectsV2(first:50){nodes{number title closed}}"
    data = board.graphql("query($owner:String!){repositoryOwner(login:$owner){... on User{%s} ... on Organization{%s}}}"
                         % (nodes, nodes), owner=owner)
    boards = (((data.get("repositoryOwner") or {}).get("projectsV2") or {}).get("nodes")) or []
    match = [b for b in boards if not b["closed"] and b["title"].strip().lower() == wanted.strip().lower()]
    if not match:
        raise NotesError("%s has no open board named %r. Boards: %s"
                         % (owner, wanted, ", ".join("#%d %s" % (b["number"], b["title"]) for b in boards) or "none"))
    return match[0]


def cmd_defaults(args) -> Any:
    cfg = load_config()
    changes: Dict[str, Any] = {}
    if args.repo:
        if args.repo.lower() == "none":
            changes["repo"] = None
        elif not re.match(r"^[\w.-]+/[\w.-]+$", args.repo):
            raise NotesError("--repo is owner/name, not %r" % args.repo)
        else:
            changes["repo"] = args.repo
    if args.board:
        if args.board.lower() == "none":
            changes.update(board=None, board_title=None)
        elif args.board.isdigit():
            changes.update(board=int(args.board), board_title=None)
        else:
            repo = changes.get("repo") or cfg.get("repo")
            if not repo:
                raise NotesError("set --repo first: a board is found by name among its owner's boards")
            found = find_board(repo.split("/")[0], args.board)
            changes.update(board=found["number"], board_title=found["title"])
    if args.assignee:
        changes["assignee"] = None if args.assignee.lower() == "default" else args.assignee
    if changes:
        save_config(**changes)
        cfg = load_config()
    return {"repo": cfg.get("repo"), "board": cfg.get("board"), "board_title": cfg.get("board_title"),
            "assignee": cfg.get("assignee", DEFAULT_ASSIGNEE), "saved_in": str(config_path())}


def cmd_add(args) -> Any:
    root = notes_root(args.root)
    kind = "todo" if args.todo else "wip" if args.wip else "note"
    entry = " ".join(args.text).strip()
    if not entry:
        raise NotesError("nothing to add")
    existing = [p for p in note_files(root) if slug(parse(p.read_text(encoding="utf-8"), p.name)["topic"]) == slug(args.topic)
                or slug(p.stem) == slug(args.topic)]
    path = existing[0] if existing else root / ("%s.md" % slug(args.topic))
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(add_to(text, args.topic, kind, entry, dt.date.today().isoformat()), encoding="utf-8")
    return {"file": str(path.relative_to(root)), "added": kind, "text": entry}


def scan_items(root: Path, topic: Optional[str]) -> List[Dict[str, Any]]:
    rows = []
    for path in note_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        note = parse(text, path.name)
        if topic and slug(topic) not in (slug(note["topic"]), slug(path.stem)):
            continue
        for it in note_items(note, text):
            rows.append({"topic": note["topic"], "file": rel, "line": it["line"], "status": it["status"],
                         "text": it["text"], "ticket": it["ticket"], "group": it["group"],
                         "loose": it["loose"], "inline": it["inline"],
                         "repo": note["meta"].get("repo"), "board": note["meta"].get("board")})
    return rows


def cmd_scan(args) -> Any:
    return scan_items(notes_root(args.root), args.topic)


def cmd_status(args) -> Any:
    rows = scan_items(notes_root(args.root), args.topic)
    topics: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        t = topics.setdefault(r["topic"], {"file": r["file"], "wip": 0, "todo": 0, "done": 0, "dropped": 0,
                                            "unfiled_open": 0, "unfiled_done_markers": 0, "loose": 0})
        t[r["status"]] += 1
        t["unfiled_open"] += r["status"] in ("todo", "wip") and not r["ticket"]
        t["unfiled_done_markers"] += r["status"] == "done" and r["inline"] and not r["ticket"]
        t["loose"] += r["loose"]
    return topics


def cmd_organize(args) -> Any:
    path = Path(args.file)
    if not path.is_file():
        path = notes_root(args.root) / args.file
    before = path.read_text(encoding="utf-8")
    after = organize_text(before, path.name)
    diff = compare(before, after)
    if diff["lost"] or diff["added"]:
        raise CheckFailed("organize would change content, so nothing was written: %s" % json.dumps(diff))
    if args.write and after != before:
        path.with_name(path.name + ".bak").write_text(before, encoding="utf-8")
        path.write_text(after, encoding="utf-8")
    return {"file": str(path), "changed": after != before, "written": bool(args.write and after != before),
            "preview": None if args.write else after}


def cmd_check(args) -> Any:
    diff = compare(Path(args.before).read_text(encoding="utf-8"), Path(args.after).read_text(encoding="utf-8"))
    if diff["lost"] or diff["added"]:
        raise CheckFailed("content differs: %s" % json.dumps(diff, ensure_ascii=False))
    return {"same_content": True}


def cmd_export(args) -> Any:
    statuses = [s.strip() for s in args.status.split(",") if s.strip()]
    bad = [s for s in statuses if s not in ("todo", "wip", "done")]
    if bad:
        raise NotesError("--status takes todo, wip and/or done, not %s" % ", ".join(bad))
    columns = {"todo": args.todo_column, "wip": args.wip_column, "done": args.done_column}
    cfg = load_config()
    repo = args.repo or cfg.get("repo")
    board = args.board if args.board is not None else cfg.get("board")
    assignee = args.assignee or cfg.get("assignee", DEFAULT_ASSIGNEE)
    plans = export(notes_root(args.root), statuses, args.topic, repo, board, columns, assignee)
    if not plans:
        return {"plans": [], "message": "nothing to file: every open item already has a ticket"}
    return {"plans": write_plans(plans, Path(args.out))}


def cmd_file(args) -> Any:
    if not args.yes:
        raise NotesError("filing creates GitHub issues; show the export to the user first, then pass --yes")
    return file_plans(notes_root(args.root), Path(args.plans))


def main(argv: Optional[List[str]] = None) -> int:
    # Notes and their "→ #N" markers are UTF-8; a Windows console defaults to cp1252 and would crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", help="notes folder (overrides $NOTES_DIR and the saved one)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where", help="the notes folder in use, and where that came from")
    p = sub.add_parser("set-root", help="remember the notes folder")
    p.add_argument("path")
    p = sub.add_parser("add", help="capture a todo, an in-progress item or a note")
    p.add_argument("--topic", required=True)
    kind = p.add_mutually_exclusive_group(required=True)
    kind.add_argument("--todo", action="store_true")
    kind.add_argument("--wip", action="store_true")
    kind.add_argument("--note", action="store_true")
    p.add_argument("text", nargs="+")
    for name in ("scan", "status"):
        p = sub.add_parser(name)
        p.add_argument("--topic")
        p.add_argument("--json", action="store_true")
    p = sub.add_parser("organize", help="regroup one file into the standard sections")
    p.add_argument("--file", required=True, help="path, or a name inside the notes folder")
    p.add_argument("--write", action="store_true", help="write it (keeps <file>.bak); default is a preview")
    p = sub.add_parser("check", help="prove an edit lost or duplicated no line")
    p.add_argument("before")
    p.add_argument("after")
    p = sub.add_parser("defaults", help="show or set where tickets go when a topic names nothing")
    p.add_argument("--repo", help="owner/name, or none")
    p.add_argument("--board", help="project number or exact board name, or none")
    p.add_argument("--assignee", help="login, @me, none (unassigned), or default (@me)")
    p = sub.add_parser("export", help="unfiled items to ticket plans")
    p.add_argument("--status", default="todo,wip,done")
    p.add_argument("--topic")
    p.add_argument("--repo", help="owner/name for topics whose front matter names none")
    p.add_argument("--board", type=int, help="project number for topics whose front matter names none")
    p.add_argument("--todo-column", default=DEFAULT_COLUMNS["todo"])
    p.add_argument("--wip-column", default=DEFAULT_COLUMNS["wip"])
    p.add_argument("--done-column", default=DEFAULT_COLUMNS["done"])
    p.add_argument("--assignee", help="login, @me or none; overrides the saved default")
    p.add_argument("--out", required=True)
    p = sub.add_parser("file", help="create the exported tickets and link them back into the notes")
    p.add_argument("--plans", required=True)
    p.add_argument("--yes", action="store_true", help="the user approved the exported list")
    args = parser.parse_args(argv)
    handlers = {"where": cmd_where, "set-root": cmd_set_root, "add": cmd_add, "scan": cmd_scan,
                "status": cmd_status, "organize": cmd_organize, "check": cmd_check,
                "defaults": cmd_defaults, "export": cmd_export, "file": cmd_file}
    try:
        result = handlers[args.cmd](args)
    except NotesError as exc:
        print("notes: %s" % exc, file=sys.stderr)
        return exc.exit_code
    if args.cmd == "organize" and result.get("preview") is not None:
        print(result["preview"], end="")
    elif args.cmd == "status" and not getattr(args, "json", False):
        if not result:
            print("no items yet")
        for topic, t in result.items():
            print("%-28s %2d in progress  %2d todo  %2d done   %d open unfiled%s  (%s)"
                  % (topic[:28], t["wip"], t["todo"], t["done"], t["unfiled_open"],
                     ", %d loose" % t["loose"] if t["loose"] else "", t["file"]))
    elif args.cmd == "scan" and not getattr(args, "json", False):
        for r in result:
            print("%-8s %s:%d  %s%s" % (r["status"], r["file"], r["line"], r["text"],
                                        "  → %s" % r["ticket"] if r["ticket"] else ""))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
