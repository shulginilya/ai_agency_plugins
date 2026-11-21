#!/usr/bin/env python3
"""WCAG 2.x contrast ratio for a foreground/background color pair.

    contrast.py "#767676" "#ffffff"           one pair
    contrast.py --pairs pairs.txt [--json]    one "fg bg [label]" pair per line, // for comments

Colors: #rgb, #rrggbb, #rrggbbaa (alpha must be opaque), rgb(r, g, b), or a
CSS name from the short list below. Reports the ratio and which WCAG marks
it meets:

    AA   normal text 4.5:1, large text 3:1, UI components and graphics 3:1
    AAA  normal text 7:1,   large text 4.5:1

Large text is 24px regular or 18.66px (14pt) bold and up.
Standard library only. Exit status: 0 every pair meets AA for normal text,
1 at least one pair does not, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Dict, List, Optional, Tuple

NAMES = {
    "white": "#ffffff", "black": "#000000", "gray": "#808080", "grey": "#808080",
    "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "silver": "#c0c0c0",
}
MARKS = {
    "aa_normal": 4.5, "aa_large": 3.0, "aa_ui": 3.0,
    "aaa_normal": 7.0, "aaa_large": 4.5,
}

RGB = Tuple[int, int, int]


class ColorError(ValueError):
    pass


def parse_color(text: str) -> RGB:
    value = NAMES.get(text.strip().lower(), text.strip().lower())
    match = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)", value)
    if match:
        r, g, b = (int(x) for x in match.group(1, 2, 3))
        if match.group(4) is not None and float(match.group(4)) < 1:
            raise ColorError("%s is translucent; give the color it renders as on its background" % text)
        if max(r, g, b) > 255:
            raise ColorError("%s has a channel above 255" % text)
        return r, g, b
    match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})", value)
    if not match:
        raise ColorError("not a color: %r" % text)
    hexes = match.group(1)
    if len(hexes) == 3:
        hexes = "".join(c * 2 for c in hexes)
    if len(hexes) == 8:
        if hexes[6:] != "ff":
            raise ColorError("%s is translucent; give the color it renders as on its background" % text)
        hexes = hexes[:6]
    return int(hexes[0:2], 16), int(hexes[2:4], 16), int(hexes[4:6], 16)


def luminance(rgb: RGB) -> float:
    """Relative luminance, WCAG 2.x definition (sRGB, 0.04045 threshold)."""
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: RGB, bg: RGB) -> float:
    light, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def assess(fg_text: str, bg_text: str, label: str = "") -> Dict:
    value = ratio(parse_color(fg_text), parse_color(bg_text))
    # WCAG compares the unrounded ratio; 4.499 fails 4.5 even though it prints as 4.50.
    return {"fg": fg_text, "bg": bg_text, "label": label, "ratio": round(value, 2),
            **{mark: value >= need for mark, need in MARKS.items()}}


def parse_pairs(text: str) -> List[Tuple[str, str, str]]:
    pairs = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.split("//")[0].strip()  # "//" comments: "#" starts a hex color
        if not line:
            continue
        parts = re.findall(r"rgba?\([^)]*\)|\S+", line)
        if len(parts) < 2:
            raise ColorError("line %d: need a foreground and a background color" % number)
        pairs.append((parts[0], parts[1], " ".join(parts[2:])))
    return pairs


LABELS = {"aa_normal": "AA normal", "aa_large": "AA large", "aa_ui": "AA UI",
          "aaa_normal": "AAA normal", "aaa_large": "AAA large"}


def describe(row: Dict) -> str:
    marks = [LABELS[m] for m in MARKS if row[m]]
    verdict = "passes " + ", ".join(marks) if marks else "fails every mark"
    label = " (%s)" % row["label"] if row["label"] else ""
    return "%s on %s%s: %.2f:1, %s" % (row["fg"], row["bg"], label, row["ratio"], verdict)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("colors", nargs="*", help="foreground and background")
    parser.add_argument("--pairs", help="file with one 'fg bg [label]' pair per line")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.pairs:
            with open(args.pairs, encoding="utf-8") as handle:
                pairs = parse_pairs(handle.read())
        elif len(args.colors) == 2:
            pairs = [(args.colors[0], args.colors[1], "")]
        else:
            raise ColorError("give two colors, or --pairs FILE")
        rows = [assess(*pair) for pair in pairs]
    except (ColorError, OSError) as exc:
        print("contrast: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(rows, indent=2) if args.json else "\n".join(describe(r) for r in rows))
    return 0 if all(r["aa_normal"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
