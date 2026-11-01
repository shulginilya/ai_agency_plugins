#!/usr/bin/env python3
"""Draw every skill — which plugin owns it, how the skills relate, and which model and effort run them.

    python integrations/firstmate/skills_diagram.py            # write docs/firstmate/
    python integrations/firstmate/skills_diagram.py --out DIR  # somewhere else
    python integrations/firstmate/skills_diagram.py --strict   # exit 1 on any drift

Everything comes from the repo, so the picture follows the plugins as they change:

* plugins/<name>/skills/*/SKILL.md — the skills each plugin owns;
  plugins/_shared/skills/ — the shared ones, bundled into the plugins whose
  plugin.json lists them under `shared_skills`;
* plugins/<name>/commands/*.md — the commands, with the `model` and `effort`
  their frontmatter pins, and the skills and subagents each one names (by name
  in backticks, as "<name> skill", or through a script that lives in a skill);
* plugins/<name>/agents/*.md — the subagents and their own model and effort;
* each SKILL.md's text — the other skills and subagents it hands work to;
* deploy.sh (`crew_plugins`) and team.json — who is crew, and the role names;
* crew-dispatch.json — the profiles Firstmate dispatches crew work with.

A skill has no model of its own: it runs on the model of the command or session
that loads it. So the diagram shows each command's pin next to the skills it
loads, and each subagent's own pin.

Drift is warned about, drawn in red and fails --strict: a command that names no
skill or subagent, a command or subagent with no model pin, a `shared_skills`
entry that _shared/skills does not have, and a shared skill a plugin's command
or skill uses without listing it in `shared_skills` (it would be missing from
the built plugin). A test runs this with --strict, so that drift fails CI.

Writes one file, skills.drawio, with two pages: the skills map, and the models.
CI regenerates docs/firstmate/skills.drawio on main after each merge, so a
branch never commits it: run this to preview, then leave the file out of the commit.
Standard library only; Python 3.9+.
Exit status: 0 written, 1 written with warnings and --strict, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from team_diagram import PALETTE, Box, Edge, Line, crew_plugin_names, drawio_page, fit_box, frontmatter  # noqa: E402

REPO = HERE.parent.parent
SHARED = "_shared"

# model id or alias -> (label, family)
MODEL_NAMES = {
    "claude-fable-5-1": ("Fable 5.1", "fable"),
    "claude-opus-5-5": ("Opus 5.5", "opus"),
    "claude-sonnet-5-5": ("Sonnet 5.5", "sonnet"),
    "claude-haiku-5-5": ("Haiku 5.5", "haiku"),
    "fable": ("Fable (alias: latest)", "fable"),
    "opus": ("Opus (alias: latest)", "opus"),
    "sonnet": ("Sonnet (alias: latest)", "sonnet"),
    "haiku": ("Haiku (alias: latest)", "haiku"),
    "inherit": ("Session model", "inherit"),
    "": ("Session model", "inherit"),
}
# fill, stroke, text
FAMILY = {
    "fable": ("#fde8f1", "#c2185b", "#5e0b2c"),
    "opus": ("#f3e8fd", "#8e44ad", "#4a1f63"),
    "sonnet": ("#e8f0fe", "#3c6fd1", "#1b3a78"),
    "haiku": ("#e8f6ee", "#2e8b57", "#174d30"),
    "inherit": ("#f4f4f4", "#8a8a8a", "#333333"),
}
SKILL_STYLE = ("#fff8e6", "#d08a00", "#5c3d00")
EFFORTS = ["max", "xhigh", "high", "medium", "low", ""]

warnings: List[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"warning: {msg}", file=sys.stderr)


def model_label(model: str) -> Tuple[str, str]:
    if model in MODEL_NAMES:
        return MODEL_NAMES[model]
    family = next((f for f in ("fable", "opus", "sonnet", "haiku") if f in model), "inherit")
    return model, family


def profile(model: str, effort: str) -> str:
    return f"{model_label(model)[0]} · {effort or 'default effort'}"


# --------------------------------------------------------------------------- repo


def mentions(text: str, names: List[str]) -> List[str]:
    """The names this text refers to: `name`, "name skill|subagent|agent", or a skills/name/ path."""
    found = []
    for n in names:
        # (?<![\w-]): "code-reviewer agent" is not the `reviewer` agent
        if re.search(rf"`{re.escape(n)}`|(?<![\w-]){re.escape(n)} (?:skill|subagent|agent)\b|skills/{re.escape(n)}/",
                     text):
            found.append(n)
    return found


def body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if text.startswith("---") and len(parts) == 3 else text


def first_sentence(text: str, limit: int = 150) -> str:
    s = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "…"


def check_effort(who: str, effort: str) -> None:
    if effort not in EFFORTS:
        warn(f"{who} pins effort '{effort}', which is not one of {', '.join(e for e in EFFORTS if e)}")


def load_plugins(plugins: Path) -> Dict:
    """plugin -> its skills, commands, agents and shared_skills; plus the shared skills."""
    out: Dict[str, Dict] = {}
    for d in sorted(p for p in plugins.iterdir() if p.is_dir() and (p.name == SHARED or not p.name.startswith("_"))):
        meta = {}
        if (d / "plugin.json").is_file():
            meta = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
        elif d.name != SHARED:
            continue
        skills = {}
        for s in sorted(d.glob("skills/*/SKILL.md")):
            fm = frontmatter(s)
            skills[s.parent.name] = {
                "name": s.parent.name, "plugin": d.name, "desc": first_sentence(fm.get("description", "")),
                "text": body(s), "scripts": sorted(p.name for p in s.parent.glob("scripts/*.py")),
            }
        agents = {}
        for a in sorted(d.glob("agents/*.md")):
            fm = frontmatter(a)
            name = fm.get("name", a.stem)
            agents[name] = {"name": name, "plugin": d.name, "model": fm.get("model", ""),
                            "effort": fm.get("effort", "")}
            if not fm.get("model"):
                warn(f"subagent {d.name}:{name} pins no model, so it runs on whatever spawns it")
            check_effort(f"subagent {d.name}:{name}", fm.get("effort", ""))
        commands = []
        for c in sorted(d.glob("commands/*.md")):
            fm = frontmatter(c)
            check_effort(f"/{d.name}:{c.stem}", fm.get("effort", ""))
            commands.append({"name": f"/{d.name}:{c.stem}", "plugin": d.name, "model": fm.get("model", ""),
                             "effort": fm.get("effort", ""), "desc": fm.get("description", ""), "text": body(c)})
        out[d.name] = {"name": d.name, "display": meta.get("displayName", d.name), "version": meta.get("version", ""),
                       "shared": list(meta.get("shared_skills") or []), "skills": skills, "agents": agents,
                       "commands": commands}
    return out


def link(plugins: Dict[str, Dict]) -> None:
    """Resolve what every command and skill uses, and warn about drift."""
    shared = plugins.get(SHARED, {"skills": {}})["skills"]
    all_agents = {(a["plugin"], n): a for p in plugins.values() for n, a in p["agents"].items()}
    owner_of = {}
    for p in plugins.values():
        for n in p["skills"]:
            owner_of.setdefault(n, p["name"])  # a plugin's own skill wins over a shared one of the same name

    def resolve(plugin: str, text: str, me: str = "") -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        own = plugins[plugin]["skills"]
        names = [n for n in owner_of if n != me]
        skills = []
        for n in mentions(text, names):
            skills.append((n, plugin if n in own else (SHARED if n in shared else owner_of[n])))
        # a script named in the text belongs to the skill whose scripts/ holds it: the plugin's own skill
        # when one has it, else any shared skill (listed in shared_skills or not, so the check below sees it)
        for script in re.findall(r"scripts/([\w-]+\.py)", text):
            holders = [s for s in own.values() if script in s["scripts"]] or \
                      [s for s in shared.values() if script in s["scripts"]]
            for s in holders:
                if s["name"] != me and (s["name"], s["plugin"]) not in skills:
                    skills.append((s["name"], s["plugin"]))
        agents = []
        local = [n for (pl, n) in all_agents if pl == plugin]
        for n in mentions(text, local):
            agents.append((n, plugin))
        for (pl, n) in all_agents:
            if pl != plugin and n not in local and (n, pl) not in agents and mentions(text, [n]):
                agents.append((n, pl))
        return list(dict.fromkeys(skills)), agents

    for p in plugins.values():
        for n in p["shared"]:
            if n not in shared:
                warn(f"{p['name']}/plugin.json lists shared skill '{n}', which plugins/_shared/skills does not have")
        for c in p["commands"]:
            c["skills"], c["agents"] = resolve(p["name"], c["text"])
            if not c["skills"] and not c["agents"]:
                warn(f"{c['name']} names no skill or subagent, so the diagram can't say what it runs")
            if not c["model"]:
                warn(f"{c['name']} pins no model, so it runs on whatever the session is on")
        for s in p["skills"].values():
            s["uses"], s["agents"] = resolve(p["name"], s["text"], me=s["name"])
    for p in plugins.values():  # every skill is resolved now, the shared ones included
        if p["name"] == SHARED:
            continue
        used = [(c["name"], c["skills"]) for c in p["commands"]]
        used += [(s["name"], s["uses"]) for s in p["skills"].values()]
        # a bundled shared skill ships inside this plugin, so what it hands off to must ship too
        used += [(f"shared skill {n}", shared[n]["uses"]) for n in p["shared"] if n in shared]
        for who, refs in used:
            for n, owner in refs:
                if owner == SHARED and n not in p["shared"]:
                    warn(f"{who} ({p['name']}) uses shared skill '{n}', which "
                         f"{p['name']}/plugin.json does not list in shared_skills")
    for p in plugins.values():
        for s in p["skills"].values():
            s["used_by"] = [c["name"] for q in plugins.values() for c in q["commands"]
                            if (s["name"], p["name"]) in c["skills"]]
            s["needed_by"] = [f"{t['name']} ({q['name']})" for q in plugins.values() for t in q["skills"].values()
                              if (s["name"], p["name"]) in t["uses"]]
        if p["name"] == SHARED:
            for s in p["skills"].values():
                s["bundled_in"] = [q["name"] for q in plugins.values() if s["name"] in q["shared"]]


def dispatch_rules(path: Path, commands: List[str]) -> List[Dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = []
    for r in data.get("rules", []) + ([{"when": "Anything no rule above matches.", "use": data["default"]}]
                                      if data.get("default") else []):
        text = f"{r.get('when', '')} {r.get('why', '')}"
        named = [c for c in dict.fromkeys(re.findall(r"(/[a-z-]+:[a-z-]+)", text))]
        for c in named:
            if c not in commands:
                warn(f"crew-dispatch.json names {c}, which no plugin has")
        use = r.get("use", {})
        rules.append({"when": r.get("when", ""), "model": use.get("model", ""), "effort": use.get("effort", ""),
                      "approval": r.get("approval"), "commands": named})
    return rules


def load(team_path: Path, plugins_dir: Path, deploy: Path, dispatch: Path) -> Dict:
    try:
        team = json.loads(team_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {team_path}: {exc}", file=sys.stderr)
        sys.exit(2)
    plugins = load_plugins(plugins_dir)
    link(plugins)
    crew = [n for n in crew_plugin_names(deploy) if n in plugins]
    roles = {n: (team.get("crew", {}).get(n) or {}).get("role") for n in plugins}
    order = crew + sorted(n for n in plugins if n not in crew and n != SHARED) + ([SHARED] if SHARED in plugins else [])
    commands = [c["name"] for p in plugins.values() for c in p["commands"]]
    return {"plugins": plugins, "crew": crew, "roles": roles, "order": order,
            "dispatch": dispatch_rules(dispatch, commands)}


# ------------------------------------------------------------------------ pages

PW = 1060  # plugin panel width
CMD_DX, CMD_W = 20, 290
SK_DX, SK_W = 380, 360
AG_DX, AG_W = 800, 240


def owner_line(m: Dict, name: str) -> str:
    if name == SHARED:
        return "Shared skills · bundled into the plugins that list them in shared_skills"
    p = m["plugins"][name]
    who = m["roles"].get(name) or p["display"]
    kind = "Crew · Firstmate routes work to it" if name in m["crew"] else "Captain-only · not deployed to the crew"
    return f"{who} · {name} v{p['version']} · {kind}"


def ref(name: str, owner: str, here: str) -> str:
    return name if owner == here else f"{name} ({'shared' if owner == SHARED else owner})"


def panel(m: Dict, name: str, x: float, y: float) -> Tuple[List, float]:
    p = m["plugins"][name]
    shapes: List = []
    title = "Shared skills" if name == SHARED else (m["roles"].get(name) or p["display"])
    head = [Line(title, 16, True), Line(owner_line(m, name), 10.5, color="#555555")]
    head_box = fit_box(f"{name}_head", x + 12, y + 10, PW - 24, head, "panel", pad=6)
    head_box.fill = head_box.stroke = "none"
    top = head_box.y + head_box.h + 10
    shapes.append(head_box)

    # commands
    cmd_box: Dict[str, Box] = {}
    cy = top
    for i, c in enumerate(p["commands"]):
        label, family = model_label(c["model"])
        lines = [Line(c["name"], 11.5, True, mono=True), Line(f"{label} · {c['effort'] or 'default effort'}", 10.5, True,
                                                              color=FAMILY[family][2]),
                 Line(first_sentence(c["desc"], 110), 9.5, color="#444444")]
        others = [ref(n, o, name) for n, o in c["skills"] if o != name]
        if others:
            lines.append(Line("also loads: " + ", ".join(others), 9.5, italic=True, color="#5c3d00"))
        if not c["skills"] and not c["agents"]:
            lines.append(Line("names no skill or subagent (drift)", 9.5, True, color=PALETTE["gap"][2]))
        b = fit_box(f"{name}_c{i}", x + CMD_DX, cy, CMD_W, lines, "panel", pad=7)
        b.fill, b.stroke, b.color = FAMILY[family]
        if not c["skills"] and not c["agents"]:
            b.fill, b.stroke, b.color = PALETTE["gap"]
        shapes.append(b)
        cmd_box[c["name"]] = b
        cy = b.y + b.h + 10

    # skills, ordered by the first command that loads them
    first_use = {}
    for i, c in enumerate(p["commands"]):
        for n, o in c["skills"]:
            if o == name:
                first_use.setdefault(n, i)
    skills = sorted(p["skills"].values(), key=lambda s: (first_use.get(s["name"], 999), s["name"]))
    sk_box: Dict[str, Box] = {}
    sy = top
    for i, s in enumerate(skills):
        lines = [Line(s["name"], 12, True), Line(s["desc"], 9.5, color="#444444")]
        if name == SHARED:
            lines.append(Line("bundled into: " + (", ".join(s.get("bundled_in", [])) or "no plugin"), 9.5, True))
        if not s["used_by"]:
            lines.append(Line("no command loads it: the model loads it from its description", 9.5, italic=True,
                              color="#777777"))
        elif name == SHARED:
            lines.append(Line("loaded by: " + ", ".join(s["used_by"]), 9.5, mono=False, color="#333333"))
        uses = [ref(n, o, name) for n, o in s["uses"]]
        if uses:
            lines.append(Line("hands off to / uses: " + ", ".join(uses), 9.5, italic=True, color="#5c3d00"))
        far = [ref(n, o, name) for n, o in s["agents"] if o != name]
        if far:
            lines.append(Line("subagent from another plugin: " + ", ".join(far), 9.5, italic=True, color="#5c3d00"))
        if s["needed_by"] and name != SHARED:
            outside = [n for n in s["needed_by"] if not n.endswith(f"({name})")]
            if outside:
                lines.append(Line("used by skills of: " + ", ".join(outside), 9.5, italic=True, color="#777777"))
        b = fit_box(f"{name}_s{i}", x + SK_DX, sy, SK_W, lines, "panel", pad=7, stroke_w=1.4)
        b.fill, b.stroke, b.color = SKILL_STYLE
        shapes.append(b)
        sk_box[s["name"]] = b
        sy = b.y + b.h + 10

    # subagents
    ag_box: Dict[str, Box] = {}
    ay = top
    for i, a in enumerate(p["agents"].values()):
        label, family = model_label(a["model"])
        lines = [Line("subagent", 9, True, color="#777777"), Line(a["name"], 11.5, True, mono=True),
                 Line(f"{label} · {a['effort'] or 'default effort'}", 10.5, True, color=FAMILY[family][2])]
        b = fit_box(f"{name}_a{i}", x + AG_DX, ay, AG_W, lines, "panel", pad=7, dashed=True)
        b.fill, b.stroke, b.color = FAMILY[family]
        shapes.append(b)
        ag_box[a["name"]] = b
        ay = b.y + b.h + 10

    # edges: command -> its own skills, and to its own subagents when no skill of it spawns them
    def ports(box: Box, n: int, k: int) -> float:
        return box.y + box.h * (k + 1) / (n + 1)

    out_edges = [(c["name"], s) for c in p["commands"] for s, o in c["skills"] if o == name and s in sk_box]
    in_count: Dict[str, int] = {}
    for _, s in out_edges:
        in_count[s] = in_count.get(s, 0) + 1
    seen_in: Dict[str, int] = {}
    per_cmd: Dict[str, List[str]] = {}
    for cmd, s in out_edges:
        per_cmd.setdefault(cmd, []).append(s)
    for cmd, targets in per_cmd.items():
        a = cmd_box[cmd]
        for k, s in enumerate(targets):
            b = sk_box[s]
            j = seen_in.get(s, 0)
            seen_in[s] = j + 1
            shapes.append(Edge(f"{name}_e_{a.id}_{b.id}", [(a.x + a.w, ports(a, len(targets), k)),
                                                          (b.x, ports(b, in_count[s], j))], color="#b07a00"))
    spawned = set()
    sk_agents = [(s["name"], n) for s in skills for n, o in s["agents"] if o == name and n in ag_box]
    ag_in: Dict[str, int] = {}
    for _, n in sk_agents:
        ag_in[n] = ag_in.get(n, 0) + 1
    seen_ag: Dict[str, int] = {}
    per_sk: Dict[str, List[str]] = {}
    for s, n in sk_agents:
        per_sk.setdefault(s, []).append(n)
    for s, targets in per_sk.items():
        a = sk_box[s]
        for k, n in enumerate(targets):
            b = ag_box[n]
            j = seen_ag.get(n, 0)
            seen_ag[n] = j + 1
            spawned.add(n)
            shapes.append(Edge(f"{name}_ea_{a.id}_{b.id}", [(a.x + a.w, ports(a, len(targets), k)),
                                                           (b.x, ports(b, ag_in[n], j))], color="#8a8a8a", dashed=True))
    for c in p["commands"]:
        direct = [n for n, o in c["agents"] if o == name and n in ag_box and n not in spawned]
        a = cmd_box[c["name"]]
        for n in direct:
            b = ag_box[n]
            # route above the skills column: out right, along the panel top, down into the subagent
            lane_y = top - 6
            shapes.append(Edge(f"{name}_ed_{a.id}_{b.id}", [(a.x + a.w, a.y + 12), (a.x + a.w + 30, a.y + 12),
                                                           (a.x + a.w + 30, lane_y), (b.x - 20, lane_y),
                                                           (b.x - 20, b.y + 14), (b.x, b.y + 14)],
                               color="#8a8a8a", dashed=True))
            spawned.add(n)

    bottom = max([cy, sy, ay]) + 6
    frame = Box(f"{name}_frame", x, y, PW, bottom - y, [], "#ffffff", "#c8c8c8", "#333333", stroke_w=1.4)
    if name in m["crew"]:
        frame.stroke = PALETTE["crew"][1]
    elif name == SHARED:
        frame.stroke = SKILL_STYLE[1]
    return [frame] + shapes, bottom - y


def legend_lines() -> List[Line]:
    lines = [Line("How to read it", 12, True),
             Line("Left: the plugin's commands (what you type). Fill = the model its frontmatter pins; "
                  "the line under the name = model · effort.", 10),
             Line("Middle (amber): the plugin's skills. A skill has no model of its own — it runs on the model "
                  "of the command or session that loads it. Amber arrow: the command loads that skill.", 10),
             Line("Right (dashed): subagents, each on its own pinned model. Grey dashed arrow: the skill or "
                  "command spawns it, in a fresh context.", 10),
             Line("'hands off to / uses' = other skills a skill sends work to or reads; '(shared)' = from "
                  "plugins/_shared, bundled into the plugin.", 10),
             Line("Green frame: crew plugin, deployed by Firstmate. Grey frame: Captain-only.", 10)]
    for fam, label in (("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku"), ("fable", "Fable"),
                       ("inherit", "No pin: session model")):
        lines.append(Line(f"■ {label}", 10.5, True, color=FAMILY[fam][1]))
    return lines


def page_map(m: Dict) -> Tuple[str, List, float, float]:
    shapes: List = []
    X0, GAP = 40, 40
    shapes.append(Box("title", X0, 20, 1600, 34, [Line("Skills map — who owns each skill, how they connect, "
                                                        "and what runs them", 22, True)],
                      "none", "none", "#1a1a1a", pad=0))
    shapes.append(Box("sub", X0, 56, 1900, 24, [Line(
        "Generated by integrations/firstmate/skills_diagram.py from plugins/*/skills, commands, agents and "
        "plugin.json, deploy.sh, team.json and crew-dispatch.json — edit those, not this file.", 11,
        color="#666666")], "none", "none", "#666666", pad=0))
    lg = fit_box("legend", X0, 100, 2 * PW + GAP, legend_lines(), "panel", pad=10)
    shapes.append(lg)
    y = lg.y + lg.h + 30
    if warnings:
        drift = fit_box("drift", X0, y, 2 * PW + GAP, [Line("Drift — fix the plugin files", 12, True)]
                        + [Line("• " + w, 10) for w in warnings], "gap", pad=10)
        shapes.append(drift)
        y = drift.y + drift.h + 30
    order = m["order"]
    for i in range(0, len(order), 2):
        row = order[i:i + 2]
        heights = []
        for k, name in enumerate(row):
            s, h = panel(m, name, X0 + k * (PW + GAP), y)
            shapes += s
            heights.append(h)
        # stretch both frames of a row to the taller one
        tall = max(heights)
        for s in shapes:
            if isinstance(s, Box) and s.id.endswith("_frame") and s.y == y:
                s.h = tall
        y += tall + GAP
    return "Skills map", shapes, X0 * 2 + 2 * PW + GAP, y + 20


def page_models(m: Dict) -> Tuple[str, List, float, float]:
    """Model × effort: which commands and subagents run on each profile, and Firstmate's dispatch profiles."""
    shapes: List = []
    X0 = 40
    shapes.append(Box("m_title", X0, 20, 1400, 34, [Line("Models and effort — what runs each command and subagent",
                                                          22, True)], "none", "none", "#1a1a1a", pad=0))
    shapes.append(Box("m_sub", X0, 56, 1600, 24, [Line(
        "Pins from each command's and subagent's frontmatter. A skill runs on the pin of the command that loads it. "
        "Crew work Firstmate dispatches runs on the profile of the matching crew-dispatch.json rule (right).", 11,
        color="#666666")], "none", "none", "#666666", pad=0))
    cells: Dict[Tuple[str, str], List[str]] = {}
    models: List[str] = []
    for name in m["order"]:
        p = m["plugins"][name]
        for c in p["commands"]:
            cells.setdefault((c["model"], c["effort"]), []).append(
                f"{c['name']}  → " + (", ".join(n for n, _ in c["skills"]) or "—"))
            models.append(c["model"])
        for a in p["agents"].values():
            cells.setdefault((a["model"], a["effort"]), []).append(f"subagent {name}:{a['name']}")
            models.append(a["model"])
    rank = {"fable": 0, "opus": 1, "sonnet": 2, "haiku": 3, "inherit": 4}
    rows = sorted(dict.fromkeys(models), key=lambda mo: (rank[model_label(mo)[1]], mo.startswith("claude") is False, mo))
    cols = [e for e in EFFORTS if any(k[1] == e for k in cells)]
    cols += sorted({k[1] for k in cells if k[1] not in EFFORTS})  # an unknown effort (a warning) is still drawn
    RX, RW, CW = X0, 200, 380
    y = 110
    for j, e in enumerate(cols):
        shapes.append(Box(f"h_{j}", RX + RW + j * CW, y, CW, 30, [Line(e or "default effort", 13, True)],
                          "#fafafa", "#c8c8c8", "#333333", align="center", valign="middle", pad=4))
    y += 30
    for i, mo in enumerate(rows):
        label, fam = model_label(mo)
        boxes = []
        for j, e in enumerate(cols):
            items = cells.get((mo, e), [])
            lines = [Line(t, 9.5, mono=True) for t in items] or [Line("", 9.5)]
            b = fit_box(f"cell_{i}_{j}", RX + RW + j * CW, y, CW, lines, "panel", pad=8)
            if items:
                b.fill, b.stroke, b.color = FAMILY[fam]
            else:
                b.fill = "#ffffff"
            boxes.append(b)
        h = max(b.h for b in boxes)
        for b in boxes:
            b.h = h
        head = Box(f"r_{i}", RX, y, RW, h, [Line(label, 13, True),
                                            Line(mo or "no model pinned", 9.5, mono=True, color="#555555")],
                   *FAMILY[fam], pad=8)
        shapes += [head] + boxes
        y += h
    table_w = RW + CW * len(cols)
    dx = RX + table_w + 40
    dy = 110
    if m["dispatch"]:
        shapes.append(Box("d_title", dx, dy, 460, 26, [Line("Firstmate's crew dispatch profiles", 14, True)],
                          "none", "none", "#1a1a1a", pad=0))
        dy += 32
        for k, r in enumerate(m["dispatch"]):
            label, fam = model_label(r["model"])
            lines = [Line(f"{label} · {r['effort'] or 'default effort'}"
                          + ("  ·  Captain approves" if r.get("approval") else ""), 11, True, color=FAMILY[fam][2]),
                     Line(first_sentence(r["when"], 200), 9.5)]
            if r["commands"]:
                lines.append(Line("names: " + ", ".join(r["commands"]), 9.5, mono=True, color="#555555"))
            b = fit_box(f"d_{k}", dx, dy, 460, lines, "panel", pad=8)
            b.fill, b.stroke, b.color = FAMILY[fam]
            shapes.append(b)
            dy = b.y + b.h + 10
    width = dx + 500
    return "Models and effort", shapes, width, max(y, dy) + 40


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--team", default=str(HERE / "team.json"))
    ap.add_argument("--plugins", default=str(REPO / "plugins"), help="the plugins folder to read")
    ap.add_argument("--deploy", default=str(HERE / "deploy.sh"))
    ap.add_argument("--dispatch", default=str(HERE / "crew-dispatch.json"))
    ap.add_argument("--out", default=str(REPO / "docs" / "firstmate"))
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything needed a warning")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    plugins = Path(args.plugins)
    if not plugins.is_dir():
        print(f"error: not a directory: {plugins}", file=sys.stderr)
        return 2
    model = load(Path(args.team), plugins, Path(args.deploy), Path(args.dispatch))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = [page_map(model), page_models(model)]
    xml = ['<mxfile host="app.diagrams.net" agent="skills_diagram.py" version="24.7.7" type="device">']
    for i, (name, shapes, w, h) in enumerate(pages, 1):
        xml.append(drawio_page(name, shapes, w, h, i))
    xml.append("</mxfile>\n")
    (out / "skills.drawio").write_text("\n".join(xml), encoding="utf-8")
    print(f"wrote {out / 'skills.drawio'}")
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
