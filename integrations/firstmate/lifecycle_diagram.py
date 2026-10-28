#!/usr/bin/env python3
"""Draw a ticket's lifecycle on the board — its columns, who moves it between them, and the ways back.

    python integrations/firstmate/lifecycle_diagram.py            # write docs/firstmate/
    python integrations/firstmate/lifecycle_diagram.py --out DIR  # somewhere else
    python integrations/firstmate/lifecycle_diagram.py --strict   # exit 1 on any drift

Two sources, so the picture follows the lifecycle as it changes:

* the repo itself — the columns and their order are DEFAULT_COLUMNS in the
  board-setup skill's create_board.py; the card moves come from every plugin
  command (`board.py move ... --status X`, a bare move meaning board.py's
  default column, and `tickets.py create|batch ... --status X`); the crew is
  `crew_plugins` in deploy.sh and the leads come from team.json.
* lifecycle.json next to this script — what the repo cannot say: what each
  column means, what happens while a card is in it, and every transition with
  who makes it and how.

Add a column or a card move and rerun: the script warns about whatever
lifecycle.json does not describe yet, and draws it in red. A test runs it with
--strict, so that drift fails CI.

Writes one file, lifecycle.drawio, with one page.
CI regenerates docs/firstmate/lifecycle.drawio on main after each merge, so a
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
from typing import Dict, List, Optional, Set, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from team_diagram import PALETTE, Box, Edge, Line, crew_plugin_names, drawio_page, fit_box, section  # noqa: E402

REPO = HERE.parent.parent
BOARD_SETUP = REPO / "plugins" / "_shared" / "skills" / "board-setup" / "scripts" / "create_board.py"
BOARD = REPO / "plugins" / "_shared" / "skills" / "ticket-management" / "scripts" / "board.py"
BACK = ("#fdecea", "#c0392b", "#6e1a12")

warnings: List[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"warning: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- repo


def board_columns(path: Path = BOARD_SETUP) -> List[str]:
    m = re.search(r"^DEFAULT_COLUMNS\s*=\s*(\[[^\]]*\])", path.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"error: no DEFAULT_COLUMNS = [...] in {path}")
    return json.loads(m.group(1))


def default_move_column(path: Path = BOARD) -> str:
    """The column a bare `board.py move` sets: the default of its --status option."""
    m = re.search(r'add_argument\("--status",\s*default="([^"]+)"', path.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"error: no --status default in {path}")
    return m.group(1)


def moves_in(text: str, default: str) -> List[str]:
    """The columns the board writes in one command file set a card to."""
    found = []
    for line in text.splitlines():
        for m in re.finditer(r"\b(board\.py move|tickets\.py (?:create|batch))\b([^`\n]*)", line):
            status = re.search(r'--status\s+(?:"([^"]+)"|([^\s"`<>]+))', m.group(2))
            if status:
                found.append(status.group(1) or status.group(2))
            elif m.group(1) == "board.py move":
                found.append(default)
    return list(dict.fromkeys(found))


def command_moves(plugins: Path, default: str) -> Dict[Tuple[str, str], List[str]]:
    """(plugin, column) -> the commands that move a card there."""
    out: Dict[Tuple[str, str], List[str]] = {}
    for cmd in sorted(plugins.glob("*/commands/*.md")):
        plugin = cmd.parent.parent.name
        if plugin.startswith("_"):
            continue
        for column in moves_in(cmd.read_text(encoding="utf-8"), default):
            out.setdefault((plugin, column), []).append(f"/{plugin}:{cmd.stem}")
    return out


def mover_names(team: Dict, plugins: Path) -> Dict[str, str]:
    """mover id -> display name: the leads, every plugin, and GitHub itself."""
    names = {lead["id"]: lead["role"] for lead in team.get("leads", [])}
    for p in sorted(plugins.glob("*/plugin.json")):
        if not p.parent.name.startswith("_"):
            meta = json.loads(p.read_text(encoding="utf-8"))
            names[p.parent.name] = (team.get("crew", {}).get(p.parent.name) or {}).get("role") or meta.get(
                "displayName", p.parent.name)
    names["github"] = "GitHub"
    return names


def check(life: Dict, columns: List[str], moves: Dict[Tuple[str, str], List[str]],
          movers: Dict[str, str]) -> List[Dict]:
    """Warn about every way lifecycle.json and the repo disagree; return the transitions that can be drawn."""
    described = life.get("columns", {})
    for c in columns:
        if c not in described:
            warn(f"column '{c}' is on every new board (create_board.py) but lifecycle.json does not describe it")
    for c in described:
        if c not in columns:
            warn(f"lifecycle.json describes column '{c}', which create_board.py no longer creates")
        for item in described[c].get("while_here", []):
            if item.get("by") not in movers:
                warn(f"column '{c}': unknown mover '{item.get('by')}' in while_here")
    drawable = []
    for t in life.get("transitions", []):
        label = f"{t.get('from') or 'new'} -> {t.get('to')}"
        bad = [c for c in (t.get("from"), t.get("to")) if c is not None and c not in columns]
        if bad or not t.get("to"):
            warn(f"transition {label} names a column that is not on the board: {', '.join(bad) or 'no target'}")
            continue
        for who in t.get("by", []):
            if who not in movers:
                warn(f"transition {label}: unknown mover '{who}'")
        if not t.get("by"):
            warn(f"transition {label} says nobody makes it")
        drawable.append(t)
    for i, c in enumerate(columns):
        if i and not any(t["to"] == c for t in drawable):
            warn(f"nothing moves a card into '{c}'")
        if i < len(columns) - 1 and not any(t.get("from") == c and not t.get("back") for t in drawable):
            warn(f"nothing moves a card forward out of '{c}'")
    for (plugin, column), cmds in sorted(moves.items()):
        if column not in columns:
            warn(f"{', '.join(cmds)} moves cards to '{column}', which is not a board column")
        elif not any(t["to"] == column and plugin in t.get("by", []) for t in drawable):
            warn(f"{', '.join(cmds)} moves cards to '{column}', but lifecycle.json has no transition into "
                 f"'{column}' by {plugin}")
    return drawable


def load(life_path: Path, team_path: Path) -> Dict:
    try:
        life = json.loads(life_path.read_text(encoding="utf-8"))
        team = json.loads(team_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read lifecycle or team file: {exc}", file=sys.stderr)
        sys.exit(2)
    plugins = REPO / "plugins"
    columns = board_columns()
    moves = command_moves(plugins, default_move_column())
    movers = mover_names(team, plugins)
    crew: Set[str] = set(crew_plugin_names(HERE / "deploy.sh"))
    transitions = check(life, columns, moves, movers)
    return {"life": life, "columns": columns, "moves": moves, "movers": movers, "crew": crew,
            "transitions": transitions}


# ------------------------------------------------------------------------- page


def who(ids: List[str], movers: Dict[str, str]) -> str:
    return " · ".join(movers.get(i, i) for i in ids)


def page_lifecycle(m: Dict) -> Tuple[str, List, float, float]:
    life, columns, movers = m["life"], m["columns"], m["movers"]
    described = life.get("columns", {})
    ts = m["transitions"]
    shapes: List = []
    ENTRY_X, ENTRY_W, COL_X, COL_W = 40, 250, 360, 470
    shapes.append(Box("l_title", ENTRY_X, 20, 1400, 34, [Line(life.get("title", "Ticket lifecycle"), 22, True)],
                      "none", "none", "#1a1a1a", pad=0))
    shapes.append(Box("l_sub", ENTRY_X, 56, 1500, 24, [Line(
        "Generated by integrations/firstmate/lifecycle_diagram.py from create_board.py, the plugins' commands, "
        "deploy.sh, team.json and lifecycle.json — edit those, not this file.", 11, color="#666666")],
        "none", "none", "#666666", pad=0))

    # entries ("new ticket" sources), per target column
    entries: Dict[str, List[Dict]] = {}
    for t in ts:
        if t.get("from") is None:
            entries.setdefault(t["to"], []).append(t)
    forward = {(t["from"], t["to"]): t for t in ts if t.get("from") is not None and not t.get("back")
               and columns.index(t["to"]) == columns.index(t["from"]) + 1}
    lanes = [t for t in ts if t.get("from") is not None and (t.get("back") or (t["from"], t["to"]) not in forward)]

    y = 110
    col_box: Dict[str, Box] = {}
    for i, c in enumerate(columns):
        d = described.get(c)
        if d is None:
            lines = [Line(c, 16, True), Line("Not described in lifecycle.json", 11, italic=True)]
            style = "gap"
        else:
            lines = [Line(c, 16, True), Line(d.get("meaning", ""), 11, italic=True, color="#444444")]
            lines += section("While here", [f"{movers.get(w['by'], w['by'])}: {w['text']}"
                                            for w in d.get("while_here", [])])
            style = "done" if i == len(columns) - 1 else "column"
        src = []
        ey = y
        for k, t in enumerate(entries.get(c, [])):
            b = fit_box(f"entry_{i}_{k}", ENTRY_X, ey, ENTRY_W,
                        [Line("New ticket", 9, True, color="#777777"), Line(who(t["by"], movers), 11, True),
                         Line(t.get("how", ""), 10)], "optional", dashed=True)
            shapes.append(b)
            src.append(b)
            ey += b.h + 12
        min_h = (ey - 12 - y) if src else 0
        palette = {"column": ("#e8f0fe", "#3c6fd1", "#1b3a78"), "done": PALETTE["crew"], "gap": PALETTE["gap"]}[style]
        box = fit_box(f"col_{i}", COL_X, y, COL_W, lines, "panel", min_h=min_h, pad=12, stroke_w=1.6)
        box.fill, box.stroke, box.color = palette
        shapes.append(box)
        col_box[c] = box
        for k, b in enumerate(src):
            cy = b.y + b.h / 2
            shapes.append(Edge(f"entry_e_{i}_{k}", [(b.x + b.w, cy), (COL_X, cy)], color="#8a8a8a", dashed=True))
        y = box.y + box.h
        nxt = columns[i + 1] if i + 1 < len(columns) else None
        if nxt is None:
            break
        t = forward.get((c, nxt))
        if t is None:
            y += 50
            continue
        label = fit_box(f"fwd_l_{i}", COL_X + 70, y + 8, COL_W - 70,
                        [Line(who(t["by"], movers), 11, True), Line(t.get("how", ""), 10)], "panel", pad=6)
        label.fill = label.stroke = "none"
        shapes.append(label)
        gap = max(56.0, label.h + 16)
        shapes.append(Edge(f"fwd_{i}", [(COL_X + 50, y), (COL_X + 50, y + gap)], color="#3c6fd1"))
        y += gap

    # back and skipping transitions: lanes to the right, each with its label box
    lane_x0 = COL_X + COL_W + 40
    label_x = lane_x0 + 34 * max(1, len(lanes)) + 20
    below = 0.0  # label boxes stack downwards, never overlapping
    for k, t in enumerate(lanes):
        a, b = col_box[t["from"]], col_box[t["to"]]
        x = lane_x0 + 34 * k
        # an outer lane leaves lower and arrives higher, so it wraps the inner ones and never crosses them
        step = 0.5 / max(1, len(lanes))
        sy = a.y + a.h * (0.4 + step * k) if a.y > b.y else a.y + a.h * (0.6 - step * k)
        ty = b.y + b.h * (0.6 - step * k) if a.y > b.y else b.y + b.h * (0.4 + step * k)
        color = BACK[1] if t.get("back") else "#3c6fd1"
        shapes.append(Edge(f"lane_{k}", [(COL_X + COL_W, sy), (x, sy), (x, ty), (COL_X + COL_W, ty)],
                           color=color, dashed=bool(t.get("back"))))
        lines = [Line(("Back: " if t.get("back") else "") + who(t["by"], movers), 11, True, color=color),
                 Line(f"{t['from']} → {t['to']}", 9.5, color="#777777"), Line(t.get("how", ""), 10)]
        lb = fit_box(f"lane_l_{k}", label_x, max(min(sy, ty) - 10, below + 12), 300, lines, "panel", pad=8)
        lb.fill, lb.stroke, lb.color = (BACK if t.get("back") else ("#e8f0fe", "#3c6fd1", "#1b3a78"))
        shapes.append(lb)
        below = lb.y + lb.h

    # legend, then drift
    ly = 110
    legend_x = label_x + 340
    legend = [Line("Legend", 12, True),
              Line("Blue arrow: the card moves forward, made by the movers named beside it", 10),
              Line("Red dashed arrow: the card goes back to be fixed", 10),
              Line("Grey dashed box: how a new ticket enters the board", 10),
              Line("While here: what happens to the card before it moves on", 10),
              Line("Red box: drift between lifecycle.json and the repo", 10)]
    lg = fit_box("legend", legend_x, ly, 330, legend, "panel", pad=10)
    shapes.append(lg)
    if warnings:
        drift = fit_box("drift", legend_x, lg.y + lg.h + 20, 330,
                        [Line("Drift — update lifecycle.json", 12, True)] + [Line("• " + w, 10) for w in warnings],
                        "gap", pad=10)
        shapes.append(drift)
    width = legend_x + 330 + 40
    height = max([s.y + s.h for s in shapes if isinstance(s, Box)]) + 40
    return "Ticket lifecycle", shapes, width, height


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lifecycle", default=str(HERE / "lifecycle.json"))
    ap.add_argument("--team", default=str(HERE / "team.json"))
    ap.add_argument("--out", default=str(REPO / "docs" / "firstmate"))
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything needed a warning")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    model = load(Path(args.lifecycle), Path(args.team))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name, shapes, w, h = page_lifecycle(model)
    xml = ['<mxfile host="app.diagrams.net" agent="lifecycle_diagram.py" version="24.7.7" type="device">',
           drawio_page(name, shapes, w, h, 1), "</mxfile>\n"]
    (out / "lifecycle.drawio").write_text("\n".join(xml), encoding="utf-8")
    print(f"wrote {out / 'lifecycle.drawio'}")
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
