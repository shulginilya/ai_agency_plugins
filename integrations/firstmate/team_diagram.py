#!/usr/bin/env python3
"""Draw the firstmate crew — who does what, who owns what, and a worked example.

    python integrations/firstmate/team_diagram.py            # write docs/firstmate/
    python integrations/firstmate/team_diagram.py --out DIR  # somewhere else

Two sources, so the picture follows the team as it changes:

* the repo itself — the crew is `crew_plugins` in deploy.sh; each crew plugin's
  version, commands, subagents (and their models), MCP tools and hooks come from
  plugins/<name>/; what each one is routed for comes from brief-include.md;
  Captain-only plugins are every other plugin under plugins/.
* team.json next to this script — what the repo cannot say: role names,
  ownership, the Captain/Firstmate duties, known gaps, the RACI matrix and the
  example workflow.

Add a plugin to `crew_plugins` and rerun: it gets a card, a matrix column and a
lane automatically, and the script warns about whatever team.json or
brief-include.md still has to say about it.

Writes one file, team.drawio, with three pages.
CI regenerates docs/firstmate/team.drawio on main after each merge, so a branch
never commits it: run this to preview, then leave the file out of the commit.
Standard library only; Python 3.9+.
Exit status: 0 written, 1 written with warnings and --strict, 2 bad input.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"
MONO = "JetBrains Mono, Consolas, Menlo, monospace"

# fill, stroke, text
PALETTE = {
    "captain": ("#fff4e0", "#d08a00", "#5c3d00"),
    "firstmate": ("#e8f0fe", "#3c6fd1", "#1b3a78"),
    "crew": ("#e8f6ee", "#2e8b57", "#174d30"),
    "write": ("#f3e8fd", "#8e44ad", "#4a1f63"),
    "gap": ("#fdecea", "#c0392b", "#6e1a12"),
    "optional": ("#f4f4f4", "#8a8a8a", "#333333"),
    "panel": ("#fafafa", "#c8c8c8", "#333333"),
    "lane": ("#ffffff", "#d6d6d6", "#333333"),
}
RACI_FILL = {"R": "#cfe9d9", "A": "#ffe2b0", "A/R": "#ffd08a", "C": "#dbe6fb", "I": "#eeeeee"}

warnings: List[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"warning: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- repo


def frontmatter(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    out: Dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if sep and not line.startswith(" "):
                out[k.strip()] = v.strip().strip('"')
    return out


def crew_plugin_names(deploy: Path) -> List[str]:
    m = re.search(r"^crew_plugins=\(([^)]*)\)", deploy.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"error: no crew_plugins=(...) line in {deploy}")
    return m.group(1).split()


def routing(brief: Path) -> Dict[str, List[str]]:
    """plugin -> the kinds of work brief-include.md sends to it."""
    text = brief.read_text(encoding="utf-8").split("Crewmate rules")[0]
    routes: Dict[str, List[str]] = {}
    bullets = re.split(r"\n- ", "\n" + text)
    for b in bullets[1:]:
        b = " ".join(b.split())
        if b.startswith("Only the "):
            continue
        # "Label: `/p:cmd` ... . Other label: `/p:cmd`" — each label owns the commands after it
        marks = list(re.finditer(r"(?:^|\.\s+)([A-Z][^:`.]*?):\s", b))
        for i, mk in enumerate(marks):
            label = mk.group(1)
            cmds = b[mk.end():marks[i + 1].start() if i + 1 < len(marks) else len(b)]
            for plugin in dict.fromkeys(re.findall(r"`/([a-z-]+):", cmds)):
                routes.setdefault(plugin, [])
                if label.strip() not in routes[plugin]:
                    routes[plugin].append(label.strip())
    return routes


def read_plugin(name: str) -> Dict:
    root = REPO / "plugins" / name
    meta = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    cmds, agents, models = [], [], []
    for f in sorted((root / "commands").glob("*.md")) if (root / "commands").is_dir() else []:
        fm = frontmatter(f)
        cmds.append(f"/{name}:{f.stem}")
        if fm.get("model"):
            models.append(fm["model"])
    for f in sorted((root / "agents").glob("*.md")) if (root / "agents").is_dir() else []:
        fm = frontmatter(f)
        agents.append(f"{fm.get('name', f.stem)} ({fm.get('model', 'inherit')})")
    skills = sorted(p.parent.name for p in root.glob("skills/*/SKILL.md"))
    skills += [f"{n} (shared)" for n in meta.get("shared_skills") or []]
    tools: List[str] = []
    server = root / "mcp" / "server.py"
    if server.is_file():
        tools = list(dict.fromkeys(re.findall(r'"name":\s*"([a-z_][a-z0-9_]*)"', server.read_text(encoding="utf-8"))))
    hooks: List[str] = []
    hj = root / "hooks" / "hooks.json"
    if hj.is_file():
        data = json.loads(hj.read_text(encoding="utf-8"))
        for event, entries in data.get("hooks", data).items():
            for e in entries:
                scripts = [re.search(r"([\w-]+\.py)", h.get("command", "")) for h in e.get("hooks", [])]
                what = ", ".join(s.group(1) for s in scripts if s)
                on = f"({e['matcher']})" if e.get("matcher") else ""
                hooks.append(f"{event}{on} → {what}" if what else f"{event}{on}")
    return {
        "name": name,
        "display": meta.get("displayName", name),
        "version": meta.get("version", "?"),
        "commands": cmds,
        "agents": agents,
        "skills": skills,
        "tools": tools,
        "hooks": hooks,
        "models": sorted(set(models)),
    }


def load(team_path: Path) -> Dict:
    try:
        team = json.loads(team_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {team_path}: {exc}", file=sys.stderr)
        sys.exit(2)
    fm = HERE
    crew_names = crew_plugin_names(fm / "deploy.sh")
    routes = routing(fm / "brief-include.md")
    crew = []
    for n in crew_names:
        if not (REPO / "plugins" / n / "plugin.json").is_file():
            warn(f"crew plugin {n} in deploy.sh has no plugins/{n}/plugin.json")
            continue
        p = read_plugin(n)
        extra = team.get("crew", {}).get(n)
        if not extra:
            warn(f"{n}: no entry under 'crew' in team.json — role name and ownership unknown")
            extra = {}
        p["role"] = extra.get("role", p["display"])
        p["owns"] = extra.get("owns", ["(not declared in team.json)"])
        p["routed"] = routes.get(n, [])
        if not p["routed"]:
            warn(f"{n}: brief-include.md routes no work to it (README: every crew plugin needs routing lines)")
        for c in re.findall(rf"`(/{n}:[a-z-]+)", (fm / "brief-include.md").read_text(encoding="utf-8")):
            if c not in p["commands"]:
                warn(f"brief-include.md routes to {c}, which plugins/{n}/commands/ does not have")
        crew.append(p)
    for n in team.get("crew", {}):
        if n not in crew_names:
            warn(f"team.json describes '{n}', which is not in crew_plugins — it is left off the diagram")
    captain_only = sorted(
        d.name for d in (REPO / "plugins").iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "plugin.json").is_file() and d.name not in crew_names
    )
    gaps = list(team.get("gaps", []))
    if not (fm / "crew-dispatch.json").is_file():
        gaps.append("crew-dispatch.json does not exist yet, so deploy.sh deploys brief-include.md alone")
    roles = {l["id"]: l["role"] for l in team.get("leads", [])}
    roles.update({p["name"]: p["role"] for p in crew})
    for row in team.get("raci", {}).get("rows", []):
        for k in row:
            if k != "activity" and k not in roles:
                warn(f"RACI row '{row['activity']}' names unknown role id '{k}'")
    for s in team.get("scenario", {}).get("steps", []):
        if s["lane"] not in roles:
            warn(f"scenario step {s['id']} is in unknown lane '{s['lane']}'")
    return {"team": team, "crew": crew, "captain_only": captain_only, "gaps": gaps, "roles": roles}


# ------------------------------------------------------------------- primitives
# A page is a list of shapes with computed geometry; the emitter writes them as
# draw.io cells.


def text_width(s: str, size: float, bold: bool = False, mono: bool = False) -> float:
    k = 0.61 if mono else (0.6 if bold else 0.55)
    return len(s) * size * k


def wrap(s: str, width: float, size: float, bold: bool = False, mono: bool = False) -> List[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and text_width(trial, size, bold, mono) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


class Line:
    def __init__(self, text: str, size: float = 11, bold: bool = False, mono: bool = False,
                 color: Optional[str] = None, gap: float = 0, italic: bool = False):
        self.text, self.size, self.bold, self.mono = text, size, bold, mono
        self.color, self.gap, self.italic = color, gap, italic


class Box:
    def __init__(self, id: str, x: float, y: float, w: float, h: float, lines: List[Line],
                 fill: str, stroke: str, color: str, dashed: bool = False, rounded: bool = True,
                 align: str = "left", valign: str = "top", pad: float = 10, stroke_w: float = 1.2,
                 container: bool = False):
        self.id, self.x, self.y, self.w, self.h = id, x, y, w, h
        self.lines, self.fill, self.stroke, self.color = lines, fill, stroke, color
        self.dashed, self.rounded, self.align, self.valign, self.pad = dashed, rounded, align, valign, pad
        self.stroke_w, self.container = stroke_w, container


class Edge:
    def __init__(self, id: str, points: List[Tuple[float, float]], label: str = "",
                 dashed: bool = False, color: str = "#555555", src: str = "", dst: str = ""):
        self.id, self.points, self.label, self.dashed, self.color = id, points, label, dashed, color
        self.src, self.dst = src, dst


def laid_out(lines: List[Line], width: float) -> List[Tuple[Line, str]]:
    out = []
    for ln in lines:
        for i, piece in enumerate(wrap(ln.text, width, ln.size, ln.bold, ln.mono)):
            out.append((Line(piece, ln.size, ln.bold, ln.mono, ln.color, ln.gap if i == 0 else 0, ln.italic), piece))
    return out


def lines_height(lines: List[Line], width: float) -> float:
    return sum(l.size * 1.35 + l.gap for l, _ in laid_out(lines, width))


def fit_box(id: str, x: float, y: float, w: float, lines: List[Line], style: str, min_h: float = 0, **kw) -> Box:
    pad = kw.get("pad", 10)
    h = max(min_h, lines_height(lines, w - 2 * pad) + 2 * pad)
    fill, stroke, color = PALETTE[style]
    return Box(id, x, y, w, h, lines, fill, stroke, color, **kw)


def section(title: str, items: List[str], mono: bool = False, bullet: bool = True) -> List[Line]:
    if not items:
        return []
    out = [Line(title.upper(), 9, True, color="#777777", gap=6)] if title else []
    for it in items:
        out.append(Line(("• " if bullet and not mono else "") + it, 10.5, mono=mono))
    return out


# ------------------------------------------------------------------------ pages


def page_team(m: Dict) -> Tuple[str, List, float, float]:
    shapes: List = []
    team = m["team"]
    W = 40
    shapes.append(Box("t_title", W, 20, 1400, 34, [Line(team.get("title", "firstmate crew"), 22, True)],
                      "none", "none", "#1a1a1a", pad=0))
    shapes.append(Box("t_sub", W, 56, 1500, 24, [Line(
        "Generated by integrations/firstmate/team_diagram.py from deploy.sh, brief-include.md, plugins/ and team.json — edit those, not this file.",
        11, color="#666666")], "none", "none", "#666666", pad=0))

    leads = {l["id"]: l for l in team.get("leads", [])}
    y0 = 100
    lead_boxes = {}
    x = W
    for lid, style in (("captain", "captain"), ("firstmate", "firstmate")):
        l = leads.get(lid)
        if not l:
            continue
        lines = [Line(l["role"], 16, True), Line(l.get("who", ""), 11, italic=True, color="#555555")]
        lines += section("Does", l.get("does", [])) + section("Owns", l.get("owns", []))
        b = fit_box(f"lead_{lid}", x, y0, 420, lines, style, pad=12, stroke_w=1.6)
        shapes.append(b)
        lead_boxes[lid] = b
        x += 420 + 120

    integ_lines = [Line("Integration layer", 14, True), Line("integrations/firstmate/ → <firstmate home>/config/", 10, mono=True, color="#555555")]
    integ_lines += section("Files", [
        "brief-include.md — appended to every ship and scout brief: routes work to plugins, sets unattended rules",
        "deploy.sh — copies config; --with-plugins installs exactly the crew_plugins into ~/.claude; refuses while a crewmate is live",
        "crew-dispatch.json — " + ("present, deployed" if (HERE / "crew-dispatch.json").is_file() else "planned, not present"),
        "team.json + team_diagram.py — this diagram",
    ])
    integ_lines += section("Crew rules (from brief-include.md)", [
        "Nobody watches the pane: decide from the brief, record why, continue",
        "Can't decide from the brief: write the question in the report and stop",
        "Never guess on anything irreversible",
        "Write to remotes only as far as the delivery contract allows",
    ])
    integ = fit_box("integ", x, y0, 480, integ_lines, "panel", pad=12)
    shapes.append(integ)

    top_h = max([b.h for b in lead_boxes.values()] + [integ.h])
    if "captain" in lead_boxes and "firstmate" in lead_boxes:
        c, f = lead_boxes["captain"], lead_boxes["firstmate"]
        yy = c.y + 40
        shapes.append(Edge("e_cf", [(c.x + c.w, yy), (f.x, yy)], "intent", src=c.id, dst=f.id, color=PALETTE["captain"][1]))
        yy2 = c.y + 90
        shapes.append(Edge("e_fc", [(f.x, yy2), (c.x + c.w, yy2)], "questions, results", src=f.id, dst=c.id, color=PALETTE["firstmate"][1]))

    # crew container + cards
    cy = y0 + top_h + 70
    card_w, gap = 330, 20
    n = max(1, len(m["crew"]))
    per_row = min(n, 4)
    cards: List[Box] = []
    row_y = cy + 70
    row_h = 0.0
    for i, p in enumerate(m["crew"]):
        col = i % per_row
        if i and col == 0:
            row_y += row_h + gap
            row_h = 0
        models = sorted(set(p["models"]))
        lines = [Line(p["role"], 15, True), Line(f"{p['name']} plugin · v{p['version']}" + (f" · {', '.join(models)}" if models else ""), 10, color="#555555")]
        lines += section("Routed here when", p["routed"] or ["(nothing routed — see warnings)"])
        lines += section("Commands", p["commands"], mono=True)
        lines += section("Subagent", p["agents"], mono=True)
        lines += section("Skills", p["skills"], mono=True)
        lines += section("MCP tools", [", ".join(p["tools"])] if p["tools"] else [], mono=True)
        lines += section("Hooks", p["hooks"], mono=True)
        lines += section("Owns", p["owns"])
        b = fit_box(f"crew_{p['name']}", W + 20 + col * (card_w + gap), row_y, card_w, lines, "crew", pad=12)
        cards.append(b)
        row_h = max(row_h, b.h)
    for b in cards:  # equal heights per row look calmer
        same = [c for c in cards if c.y == b.y]
        b.h = max(c.h for c in same)
    crew_w = per_row * card_w + (per_row - 1) * gap + 40
    crew_h = (row_y + row_h + 20) - cy
    note = team.get("crew_note", "")
    container = Box("crew_box", W, cy, max(crew_w, 600), crew_h,
                    [Line(f"Crew — {len(m['crew'])} crew plugins (deploy.sh crew_plugins), each crewmate a Claude Code session", 14, True),
                     Line(note, 10.5, color="#3a5a46")],
                    "#f5fbf7", PALETTE["crew"][1], PALETTE["crew"][2], dashed=True, pad=14, container=True)
    shapes.append(container)
    shapes.extend(cards)
    if "firstmate" in lead_boxes:
        f = lead_boxes["firstmate"]
        x1 = f.x + 140
        shapes.append(Edge("e_fcrew", [(x1, f.y + f.h), (x1, cy)], "brief + delivery contract (ship / scout)",
                           src=f.id, dst=container.id, color=PALETTE["firstmate"][1]))
        x2 = f.x + f.w - 120
        shapes.append(Edge("e_crewf", [(x2, cy), (x2, f.y + f.h)], "report",
                           src=container.id, dst=f.id, color=PALETTE["crew"][1]))
    shapes.append(Edge("e_integ", [(integ.x + integ.w / 2, integ.y + integ.h), (integ.x + integ.w / 2, cy)],
                       "routes + installs", dashed=True, src=integ.id, dst=container.id, color="#888888"))

    # bottom row: captain-only plugins + gaps
    by = cy + crew_h + 40
    cap_lines = [Line("Captain-only plugins", 13, True),
                 Line("Installed for your own sessions; brief-include.md forbids crewmates to use them.", 10, color="#555555")]
    cap_lines += section("Plugins", m["captain_only"], mono=True)
    cap = fit_box("captain_only", W, by, 420, cap_lines, "captain", pad=12, dashed=True)
    gap_lines = [Line("Known gaps", 13, True)] + section("", m["gaps"])
    gap_lines[1:2] = [Line(gap_lines[1].text, 10.5, gap=6)] if len(gap_lines) > 1 else []
    gaps = fit_box("gaps", W + 440, by, 640, gap_lines, "gap", pad=12, dashed=True)
    shapes += [cap, gaps]
    width = max(container.x + container.w, integ.x + integ.w, gaps.x + gaps.w) + 40
    height = max(cap.y + cap.h, gaps.y + gaps.h) + 40
    return "1 · Team and ownership", shapes, width, height


def page_matrix(m: Dict) -> Tuple[str, List, float, float]:
    team = m["team"]
    raci = team.get("raci", {})
    cols = list(raci.get("columns", []))
    for p in m["crew"]:  # a new crew member gets a column even before team.json mentions it
        if p["name"] not in cols:
            cols.append(p["name"])
    cols = [c for c in cols if c in m["roles"]]
    shapes: List = [Box("m_title", 40, 20, 1200, 34, [Line("2 · Who does what — responsibility matrix", 22, True)], "none", "none", "#1a1a1a", pad=0)]
    leg = raci.get("legend", {})
    lx = 40
    for k in ("R", "A", "A/R", "C", "I"):
        meaning = leg.get(k, "does it and signs off" if k == "A/R" else "")
        w = 34 + text_width(meaning, 11) + 16
        shapes.append(Box(f"leg_{k.replace('/', '')}", lx, 64, 34, 22, [Line(k, 11, True)], RACI_FILL[k], "#999999", "#222222", align="center", valign="middle", pad=2))
        shapes.append(Box(f"legt_{k.replace('/', '')}", lx + 38, 64, w - 38, 22, [Line(meaning, 11, color="#444444")], "none", "none", "#444444", pad=2, valign="middle"))
        lx += w + 10
    act_w, col_w, row_h, top = 330, 128, 30, 104
    shapes.append(Box("mh_act", 40, top, act_w, 44, [Line("Activity", 12, True)], "#f0f0f0", "#bbbbbb", "#222222", rounded=False, valign="middle"))
    for j, c in enumerate(cols):
        style = "captain" if c == "captain" else "firstmate" if c == "firstmate" else "crew"
        fill, stroke, color = PALETTE[style]
        shapes.append(Box(f"mh_{c}", 40 + act_w + j * col_w, top, col_w, 44, [Line(m["roles"][c], 12, True)],
                          fill, stroke, color, rounded=False, align="center", valign="middle", pad=4))
    for i, row in enumerate(raci.get("rows", [])):
        y = top + 44 + i * row_h
        shapes.append(Box(f"mr_{i}", 40, y, act_w, row_h, [Line(row["activity"], 11)], "#ffffff", "#dddddd", "#222222", rounded=False, valign="middle", pad=8))
        for j, c in enumerate(cols):
            v = row.get(c, "")
            shapes.append(Box(f"mc_{i}_{j}", 40 + act_w + j * col_w, y, col_w, row_h, [Line(v, 11, bool(v))],
                              RACI_FILL.get(v, "#ffffff"), "#dddddd", "#222222", rounded=False, align="center", valign="middle", pad=2))
    n = len(raci.get("rows", []))
    width = 40 + act_w + len(cols) * col_w + 40
    height = top + 44 + n * row_h + 40
    return "2 · Responsibility matrix", shapes, max(width, lx + 40), height


def page_flow(m: Dict) -> Tuple[str, List, float, float]:
    sc = m["team"].get("scenario", {})
    lanes = list(sc.get("lanes", []))
    for p in m["crew"]:
        if p["name"] not in lanes:
            lanes.append(p["name"])
    lanes = [l for l in lanes if l in m["roles"]]
    steps = sc.get("steps", [])
    by_id: Dict[str, Dict] = {}
    prev = None
    for s in steps:
        after = s.get("after") or ([prev] if prev else [])
        s["_after"] = [a for a in after if a in by_id]
        s["_col"] = s.get("col") or (max([by_id[a]["_col"] for a in s["_after"]] or [0]) + 1)
        by_id[s["id"]] = s
        prev = s["id"]
    ncols = max([s["_col"] for s in steps] or [1])
    lane_label_w, col_w, box_w, top = 150, 210, 186, 120
    # lane heights: tallest box in the lane
    boxes: Dict[str, Box] = {}
    lane_h: Dict[str, float] = {}
    style_of = {"decision": "captain", "gap": "gap", "write": "write", "optional": "optional"}
    for s in steps:
        if s["lane"] not in lanes:
            continue
        lane_style = "captain" if s["lane"] == "captain" else "firstmate" if s["lane"] == "firstmate" else "crew"
        style = style_of.get(s.get("kind", ""), lane_style)
        b = fit_box(f"st_{s['id']}", 0, 0, box_w, [Line(s["text"], 11.5)], style, min_h=56, pad=8,
                    dashed=s.get("kind") in ("gap", "optional"))
        num = steps.index(s) + 1
        b.lines = [Line(str(num), 9, True, color=b.stroke)] + b.lines
        b.h += 13
        boxes[s["id"]] = b
        lane_h[s["lane"]] = max(lane_h.get(s["lane"], 0), b.h + 36)
    shapes: List = [
        Box("f_title", 40, 20, 1600, 34, [Line("3 · " + sc.get("title", "Workflow example"), 22, True)], "none", "none", "#1a1a1a", pad=0),
    ]
    lx = 40
    for k, label in (("captain", "Captain decision"), ("firstmate", "Firstmate"), ("crew", "Crewmate work"),
                     ("write", "Writes to GitHub"), ("gap", "Gap — no skill covers it"), ("optional", "Only if needed")):
        fill, stroke, color = PALETTE[k]
        shapes.append(Box(f"fl_{k}", lx, 66, 18, 18, [], fill, stroke, color, dashed=k in ("gap", "optional")))
        shapes.append(Box(f"flt_{k}", lx + 24, 64, text_width(label, 11) + 10, 22, [Line(label, 11, color="#444444")], "none", "none", "#444444", pad=0, valign="middle"))
        lx += 24 + text_width(label, 11) + 30
    width = 40 + lane_label_w + ncols * col_w + 30
    y = top
    lane_y: Dict[str, float] = {}
    groups: Dict[str, List[int]] = {}
    for s in steps:
        if s.get("group"):
            groups.setdefault(s["group"], []).append(s["_col"])
    lane_shapes = []
    for ln in lanes:
        h = lane_h.get(ln, 60)
        lane_y[ln] = y
        style = "captain" if ln == "captain" else "firstmate" if ln == "firstmate" else "crew"
        fill, stroke, color = PALETTE[style]
        lane_shapes.append(Box(f"lane_{ln}", 40, y, width - 40, h, [], "none", "#d6d6d6", "#333", rounded=False))
        lane_shapes.append(Box(f"lanel_{ln}", 40, y, lane_label_w, h, [Line(m["roles"][ln], 13, True)], fill, stroke, color,
                               rounded=False, align="center", valign="middle"))
        y += h
    # group bands sit behind the lanes' boxes
    for gi, (g, cols_) in enumerate(groups.items()):
        x0 = 40 + lane_label_w + (min(cols_) - 1) * col_w + 4
        x1 = 40 + lane_label_w + max(cols_) * col_w - 4
        shapes.append(Box(f"grp_{gi}", x0, top - 26, x1 - x0, y - top + 32, [Line(g, 11, True, color="#666666")],
                          "#f6f6f6", "#b5b5b5", "#666666", dashed=True, pad=6))
    shapes += lane_shapes
    for s in steps:
        b = boxes.get(s["id"])
        if not b:
            continue
        b.x = 40 + lane_label_w + (s["_col"] - 1) * col_w + (col_w - box_w) / 2
        b.y = lane_y[s["lane"]] + (lane_h[s["lane"]] - b.h) / 2
        shapes.append(b)
    edges = []
    for s in steps:
        for a in s["_after"]:
            if a not in boxes or s["id"] not in boxes:
                continue
            p, q = boxes[a], boxes[s["id"]]
            if q.x > p.x + 1:
                x1, y1 = p.x + p.w, p.y + p.h / 2
                x2, y2 = q.x, q.y + q.h / 2
                xm = x1 + (x2 - x1) / 2 if q.x - (p.x + p.w) < col_w else x2 - (col_w - box_w) / 2
                pts = [(x1, y1), (xm, y1), (xm, y2), (x2, y2)] if abs(y1 - y2) > 1 else [(x1, y1), (x2, y2)]
            else:  # same column, different lane
                down = q.y > p.y
                xx = p.x + p.w / 2
                pts = [(xx, p.y + p.h if down else p.y), (xx, q.y if down else q.y + q.h)]
            edges.append(Edge(f"fe_{a}_{s['id']}", pts, src=p.id, dst=q.id))
    shapes += edges
    return "3 · Example workflow", shapes, width + 20, y + 40


# ---------------------------------------------------------------------- emitters


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def box_html(b: Box) -> str:
    parts = []
    for ln in b.lines:
        t = esc(ln.text)
        if ln.mono:
            t = f'<font face="{MONO.split(",")[0]}">{t}</font>'
        if ln.bold:
            t = f"<b>{t}</b>"
        if ln.italic:
            t = f"<i>{t}</i>"
        style = f"font-size:{ln.size}px;"
        if ln.color:
            style += f"color:{ln.color};"
        if ln.gap:
            style += f"margin-top:{ln.gap}px;"
        parts.append(f'<div style="{style}">{t}</div>')
    return "".join(parts)


def drawio_page(name: str, shapes: List, w: float, h: float, idx: int) -> str:
    cells = ['<mxCell id="0" />', '<mxCell id="1" parent="0" />']
    for s in shapes:
        if isinstance(s, Box):
            style = (f"rounded={1 if s.rounded else 0};arcSize=6;whiteSpace=wrap;html=1;"
                     f"fillColor={s.fill};strokeColor={s.stroke};fontColor={s.color};strokeWidth={s.stroke_w};"
                     f"align={s.align};verticalAlign={s.valign};spacing={s.pad};fontFamily={FONT.split(',')[0]};")
            if s.dashed:
                style += "dashed=1;"
            if s.container:
                style += "container=0;"
            cells.append(
                f'<mxCell id="p{idx}_{s.id}" value="{esc(box_html(s))}" style="{style}" vertex="1" parent="1">'
                f'<mxGeometry x="{s.x:.0f}" y="{s.y:.0f}" width="{s.w:.0f}" height="{s.h:.0f}" as="geometry" /></mxCell>')
        else:
            (sx, sy), (tx, ty) = s.points[0], s.points[-1]
            style = (f"edgeStyle=none;html=1;endArrow=block;endFill=1;strokeColor={s.color};strokeWidth=1.4;"
                     f"fontSize=10;fontColor=#333333;labelBackgroundColor=#ffffff;")
            if s.dashed:
                style += "dashed=1;"
            pts = "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}" />' for x, y in s.points[1:-1])
            cells.append(
                f'<mxCell id="p{idx}_{s.id}" value="{esc(s.label)}" style="{style}" edge="1" parent="1">'
                f'<mxGeometry relative="1" as="geometry"><mxPoint x="{sx:.0f}" y="{sy:.0f}" as="sourcePoint" />'
                f'<mxPoint x="{tx:.0f}" y="{ty:.0f}" as="targetPoint" />'
                + (f'<Array as="points">{pts}</Array>' if pts else "") + "</mxGeometry></mxCell>")
    body = "\n        ".join(cells)
    return (f'  <diagram id="page{idx}" name="{esc(name)}">\n'
            f'    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
            f'fold="1" page="1" pageScale="1" pageWidth="{w:.0f}" pageHeight="{h:.0f}" math="0" shadow="0">\n'
            f'      <root>\n        {body}\n      </root>\n    </mxGraphModel>\n  </diagram>')


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--team", default=str(HERE / "team.json"))
    ap.add_argument("--out", default=str(REPO / "docs" / "firstmate"))
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything needed a warning")
    args = ap.parse_args(argv)
    model = load(Path(args.team))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = [page_team(model), page_matrix(model), page_flow(model)]
    xml = ['<mxfile host="app.diagrams.net" agent="team_diagram.py" version="24.7.7" type="device">']
    for i, (name, shapes, w, h) in enumerate(pages, 1):
        xml.append(drawio_page(name, shapes, w, h, i))
    xml.append("</mxfile>\n")
    (out / "team.drawio").write_text("\n".join(xml), encoding="utf-8")
    print(f"wrote {out / 'team.drawio'}")
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
