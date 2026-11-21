#!/usr/bin/env python3
"""Where a repository's UI lives: stack, design tokens, components, pages, theming.

    ui_inventory.py [--root DIR] [--json]

Reads package.json dependencies and walks the tree (skipping node_modules,
build output and VCS folders) for the things a designer needs before judging
or specifying a screen:

    stack       UI framework, styling system and component library
    tokens      where colors, type and spacing are defined (CSS custom
                properties, Tailwind config, theme or token files)
    components  directories of reusable components
    pages       route and page files: the screens a user actually sees
    theming     dark-mode and theme signals
    storybook   whether components can be viewed in isolation

Standard library only. Exit status: 0 UI found, 2 no UI found or a bad root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
             ".svelte-kit", ".turbo", "vendor", "__pycache__", ".venv", "venv", "target"}
FRAMEWORKS = {"next": "Next.js", "react": "React", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte",
              "@sveltejs/kit": "SvelteKit", "@angular/core": "Angular", "solid-js": "Solid",
              "astro": "Astro", "react-native": "React Native", "@remix-run/react": "Remix"}
STYLING = {"tailwindcss": "Tailwind CSS", "styled-components": "styled-components",
           "@emotion/react": "Emotion", "sass": "Sass", "@vanilla-extract/css": "vanilla-extract",
           "@pandacss/dev": "Panda CSS", "@stitches/react": "Stitches"}
LIBRARIES = {"@mui/material": "MUI", "@chakra-ui/react": "Chakra UI", "antd": "Ant Design",
             "@mantine/core": "Mantine", "@radix-ui/react-slot": "Radix (shadcn/ui)",
             "vuetify": "Vuetify", "primevue": "PrimeVue", "@headlessui/react": "Headless UI",
             "bootstrap": "Bootstrap"}
UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".astro", ".html"}
STYLE_EXT = {".css", ".scss", ".sass", ".less", ".pcss"}
TOKEN_NAME = re.compile(r"(^|[-_.])(tokens?|theme|design-tokens|variables|palette|colors)([-_.]|$)", re.I)
PAGE_PATTERNS = [re.compile(p) for p in (
    r"(^|/)app/(.+/)?page\.(t|j)sx?$", r"(^|/)pages/.+\.(t|j)sx?$", r"(^|/)src/routes/.+\.(svelte|tsx?|jsx?)$",
    r"(^|/)(views|screens)/.+\.(vue|tsx|jsx)$", r"(^|/)src/pages/.+\.(astro|vue|tsx|jsx)$",
)]
COMPONENT_DIR = re.compile(r"(^|/)(components|ui|widgets)$")
THEME_SIGNALS = {"prefers-color-scheme": "prefers-color-scheme media query",
                 "data-theme": "data-theme attribute", "next-themes": "next-themes",
                 'darkMode': "Tailwind darkMode"}
MAX_FILES = 20000


def deps(root: Path) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for manifest in [root / "package.json"] + sorted(root.glob("*/package.json"))[:20]:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            found.update(data.get(key) or {})
    return found


def walk(root: Path):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        yield rel_dir, sorted(filenames)
        count += len(filenames)
        if count > MAX_FILES:
            return


def inventory(root: Path) -> Dict:
    packages = deps(root)
    pick = lambda table: [name for key, name in table.items() if key in packages]
    report: Dict = {"root": str(root), "stack": {"framework": pick(FRAMEWORKS), "styling": pick(STYLING),
                                                  "library": pick(LIBRARIES)},
                    "tokens": [], "components": [], "pages": [], "theming": [], "storybook": False,
                    "ui_files": 0}
    if (root / "components.json").is_file():
        report["stack"]["library"].append("shadcn/ui (components.json)")
    theming = set()
    for rel_dir, files in walk(root):
        if rel_dir == ".":
            rel_dir = ""
        if COMPONENT_DIR.search(rel_dir) and any(Path(f).suffix in UI_EXT for f in files):
            report["components"].append(rel_dir)
        for name in files:
            rel = "%s/%s" % (rel_dir, name) if rel_dir else name
            suffix = Path(name).suffix
            if suffix in UI_EXT:
                report["ui_files"] += 1
            if any(p.search(rel) for p in PAGE_PATTERNS):
                report["pages"].append(rel)
            is_style = suffix in STYLE_EXT
            if name.startswith("tailwind.config.") or (TOKEN_NAME.search(Path(name).stem) and
                                                       suffix in STYLE_EXT | {".json", ".ts", ".js"}):
                report["tokens"].append(rel)
            if is_style or name.startswith("tailwind.config.") or suffix in {".tsx", ".jsx", ".ts", ".js", ".vue"}:
                try:
                    text = (root / rel).read_text(encoding="utf-8", errors="ignore")[:200000]
                except OSError:
                    continue
                if is_style:
                    props = len(re.findall(r"--[\w-]+\s*:", text))
                    if props >= 5 and rel not in report["tokens"]:
                        report["tokens"].append("%s (%d custom properties)" % (rel, props))
                for needle, label in THEME_SIGNALS.items():
                    if needle in text:
                        theming.add(label)
    report["storybook"] = (root / ".storybook").is_dir() or "storybook" in packages
    report["theming"] = sorted(theming)
    report["pages"] = report["pages"][:200]
    return report


def has_ui(report: Dict) -> bool:
    return bool(report["ui_files"] or report["stack"]["framework"])


def describe(report: Dict) -> str:
    stack = report["stack"]
    lines = ["Stack:      %s" % (", ".join(stack["framework"] + stack["styling"] + stack["library"]) or "not identified"),
             "Tokens:     %s" % (", ".join(report["tokens"]) or "none found - colors and spacing are likely hard-coded"),
             "Components: %s" % (", ".join(report["components"]) or "no component directory"),
             "Pages:      %d found%s" % (len(report["pages"]), (" e.g. " + ", ".join(report["pages"][:5])) if report["pages"] else ""),
             "Theming:    %s" % (", ".join(report["theming"]) or "no dark mode or theme signals"),
             "Storybook:  %s" % ("yes" if report["storybook"] else "no")]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("ui_inventory: %s is not a directory" % root, file=sys.stderr)
        return 2
    report = inventory(root)
    if not has_ui(report):
        print("ui_inventory: no UI found under %s (no UI framework in package.json and no UI files)" % root,
              file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else describe(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
