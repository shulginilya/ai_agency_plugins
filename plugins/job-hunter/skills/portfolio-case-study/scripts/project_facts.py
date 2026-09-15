#!/usr/bin/env python3
"""Collect the verifiable facts about one project, before anyone writes about it.

Usage:
    python scripts/project_facts.py path/to/repo
    python scripts/project_facts.py path/to/repo --author "Ilya Shulgin" --json
    python scripts/project_facts.py --page saved_homepage.html --json

A portfolio entry is only as good as the facts under it, and the facts a model
"remembers" about a codebase after skimming three files are the ones that end
up wrong in a CV. This script reads what can be counted — manifests,
dependencies, languages, infrastructure files, CI, tests, git history — and
reports it with the file each fact came from. It does not describe the project;
that is the skill's job, done from this output.

With --page it reads a saved HTML page of a live web app and reports framework
fingerprints. Those are hints, not facts: a CDN or a static export can hide or
fake any of them, so the skill asks the user to confirm them.

Exit codes:
    0   usable    enough to say what the project is and what it is built with
    1   (unused — kept free so 0/2/3 mean the same thing as in fit.py)
    2   unusable  not a directory, nothing readable, or an empty page
    3   thin      readable, but something decisive is missing: no README or
                  manifest to say what it is, or --author has no commits here,
                  so the user's role cannot be read from the history
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
    "coverage", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache",
    ".pytest_cache", "target", "vendor", ".turbo", ".cache", ".idea", ".vscode",
    ".expo", "Pods", ".gradle", "bin", "obj",
}
MAX_FILES = 60000

LANGUAGES = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".py": "Python", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".dart": "Dart",
    ".scala": "Scala", ".ex": "Elixir", ".exs": "Elixir", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".vue": "Vue", ".svelte": "Svelte",
    ".sql": "SQL", ".tf": "Terraform", ".sh": "Shell", ".ps1": "PowerShell",
    ".css": "CSS", ".scss": "SCSS", ".html": "HTML", ".graphql": "GraphQL", ".proto": "Protobuf",
}
MARKUP = {"CSS", "SCSS", "HTML"}

# dependency name (lowercase, exact or prefix ending in '/') -> label
SIGNATURES = {
    "react": "React", "next": "Next.js", "react-native": "React Native", "expo": "Expo",
    "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte", "@sveltejs/kit": "SvelteKit",
    "@angular/core": "Angular", "astro": "Astro", "remix": "Remix", "@remix-run/": "Remix",
    "vite": "Vite", "tailwindcss": "Tailwind CSS", "@mui/material": "MUI",
    "styled-components": "styled-components", "redux": "Redux", "@reduxjs/toolkit": "Redux Toolkit",
    "@tanstack/react-query": "TanStack Query", "zustand": "Zustand", "graphql": "GraphQL",
    "@apollo/client": "Apollo Client", "@apollo/server": "Apollo Server",
    "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS", "koa": "Koa",
    "hono": "Hono", "trpc": "tRPC", "@trpc/server": "tRPC", "socket.io": "Socket.IO",
    "prisma": "Prisma", "@prisma/client": "Prisma", "drizzle-orm": "Drizzle", "typeorm": "TypeORM",
    "mongoose": "MongoDB (Mongoose)", "pg": "PostgreSQL", "mysql2": "MySQL", "redis": "Redis",
    "ioredis": "Redis", "@aws-sdk/": "AWS SDK", "aws-sdk": "AWS SDK", "aws-cdk-lib": "AWS CDK",
    "serverless": "Serverless Framework", "stripe": "Stripe", "@stripe/": "Stripe",
    "firebase": "Firebase", "@supabase/supabase-js": "Supabase", "openai": "OpenAI API",
    "@anthropic-ai/sdk": "Anthropic API", "anthropic": "Anthropic API",
    "@anthropic-ai/claude-agent-sdk": "Claude Agent SDK", "claude-agent-sdk": "Claude Agent SDK",
    "langchain": "LangChain", "@langchain/": "LangChain", "llama-index": "LlamaIndex",
    "jest": "Jest", "vitest": "Vitest", "@playwright/test": "Playwright", "cypress": "Cypress",
    "@testing-library/react": "Testing Library", "storybook": "Storybook", "@storybook/": "Storybook",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic", "celery": "Celery", "pytest": "pytest", "boto3": "AWS SDK (boto3)",
    "pandas": "pandas", "numpy": "NumPy", "torch": "PyTorch", "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn", "uvicorn": "Uvicorn", "alembic": "Alembic",
}

INFRA_FILES = {
    "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose", "compose.yaml": "Docker Compose",
    "serverless.yml": "Serverless Framework", "cdk.json": "AWS CDK",
    "template.yaml": "AWS SAM (probable)", "samconfig.toml": "AWS SAM",
    "Chart.yaml": "Helm", "skaffold.yaml": "Skaffold", "vercel.json": "Vercel",
    "netlify.toml": "Netlify", "fly.toml": "Fly.io", "render.yaml": "Render",
    "app.yaml": "Google App Engine (probable)", "Procfile": "Heroku-style Procfile",
    "amplify.yml": "AWS Amplify", "firebase.json": "Firebase Hosting", "eas.json": "Expo EAS",
    "nx.json": "Nx monorepo", "turbo.json": "Turborepo", "pnpm-workspace.yaml": "pnpm workspaces",
    "lerna.json": "Lerna",
}
CI_PATHS = {
    ".github/workflows": "GitHub Actions", ".gitlab-ci.yml": "GitLab CI",
    "azure-pipelines.yml": "Azure Pipelines", ".circleci": "CircleCI",
    "Jenkinsfile": "Jenkins", "bitbucket-pipelines.yml": "Bitbucket Pipelines",
}
TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|Test\.java$|Tests?\.cs$)")
URL = re.compile(r"https?://[^\s)\]>\"'`]+")

PAGE_HINTS = [
    ("Next.js", re.compile(r"/_next/|__NEXT_DATA__")),
    ("Nuxt", re.compile(r"/_nuxt/|__NUXT__")),
    ("Gatsby", re.compile(r"___gatsby")),
    ("SvelteKit", re.compile(r"__sveltekit|/_app/immutable/")),
    ("Astro", re.compile(r"astro-island|/_astro/")),
    ("Remix", re.compile(r"__remixContext")),
    ("Angular", re.compile(r"ng-version=")),
    ("React", re.compile(r"data-reactroot|react-dom|_reactListening")),
    ("Vue", re.compile(r"data-v-[0-9a-f]{6,}|__VUE__")),
    ("WordPress", re.compile(r"wp-content/|wp-includes/")),
    ("Webflow", re.compile(r"webflow\.js|data-wf-page")),
    ("Vercel", re.compile(r"vercel", re.I)),
    ("Cloudflare", re.compile(r"cdn-cgi/|cloudflareinsights")),
    ("Stripe", re.compile(r"js\.stripe\.com")),
    ("Google Analytics", re.compile(r"googletagmanager\.com|google-analytics\.com")),
    ("Tailwind CSS (probable)", re.compile(r'class="[^"]*\b(?:flex|px-\d|text-(?:sm|lg|xl))\b')),
]


def _label(dep: str) -> Optional[str]:
    dep = dep.lower().strip()
    if dep in SIGNATURES:
        return SIGNATURES[dep]
    for key, label in SIGNATURES.items():
        if key.endswith("/") and dep.startswith(key):
            return label
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _toml_deps(text: str) -> List[str]:
    """Pull dependency names out of pyproject.toml without a TOML parser (3.9 has none)."""
    names: List[str] = []
    for block in re.findall(r"dependencies\s*=\s*\[(.*?)\]", text, re.S):
        names += re.findall(r"[\"']\s*([A-Za-z0-9_.\-]+)", block)
    section = None
    for line in text.splitlines():
        header = re.match(r"\s*\[([^\]]+)\]", line)
        if header:
            section = header.group(1)
            continue
        if section and section.endswith("dependencies") and "poetry" in section:
            key = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*=", line)
            if key and key.group(1).lower() != "python":
                names.append(key.group(1))
    return names


def manifests(root: Path) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    deps: Dict[str, List[str]] = {}
    name = description = homepage = None

    for pkg in sorted(root.glob("package.json")) + sorted(root.glob("*/package.json"))[:20] \
            + sorted(root.glob("*/*/package.json"))[:20]:
        if any(part in SKIP_DIRS for part in pkg.relative_to(root).parts):
            continue
        try:
            data = json.loads(_read(pkg) or "{}")
        except json.JSONDecodeError:
            continue
        rel = pkg.relative_to(root).as_posix()
        names = sorted(set(data.get("dependencies", {})) | set(data.get("devDependencies", {})))
        deps[rel] = names
        if rel == "package.json":
            name = data.get("name")
            description = data.get("description")
            homepage = data.get("homepage")
            found["scripts"] = sorted(data.get("scripts", {}))

    py = root / "pyproject.toml"
    if py.is_file():
        text = _read(py)
        deps["pyproject.toml"] = sorted(set(_toml_deps(text)))
        name = name or (re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M) or [None, None])[1]
        description = description or (
            re.search(r'^\s*description\s*=\s*"([^"]+)"', text, re.M) or [None, None])[1]
    for req in sorted(root.glob("requirements*.txt")):
        deps[req.name] = sorted({
            re.split(r"[<>=!~\[; ]", line.strip(), maxsplit=1)[0]
            for line in _read(req).splitlines()
            if line.strip() and not line.strip().startswith(("#", "-"))
        })
    gomod = root / "go.mod"
    if gomod.is_file():
        text = _read(gomod)
        name = name or (re.search(r"^module\s+(\S+)", text, re.M) or [None, None])[1]
        deps["go.mod"] = sorted(set(re.findall(r"^\s*([a-z0-9.\-]+/[^\s]+)\s+v", text, re.M)))
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        text = _read(cargo)
        name = name or (re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M) or [None, None])[1]
        block = re.search(r"\[dependencies\](.*?)(\n\[|\Z)", text, re.S)
        deps["Cargo.toml"] = sorted(re.findall(r"^\s*([A-Za-z0-9_\-]+)\s*=", block.group(1), re.M)) if block else []

    tech: Dict[str, List[str]] = {}
    for source, names in deps.items():
        for dep in names:
            label = _label(dep)
            if label:
                tech.setdefault(label, [])
                if source not in tech[label]:
                    tech[label].append(source)

    found.update({
        "name": name, "description": description, "homepage": homepage,
        "manifests": sorted(deps), "dependency_count": sum(len(v) for v in deps.values()),
        "technologies": {k: tech[k] for k in sorted(tech)},
    })
    return found


def readme(root: Path) -> Dict[str, Any]:
    for candidate in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        path = root / candidate
        if path.is_file():
            text = _read(path)
            paragraphs = [
                p.strip() for p in re.split(r"\n\s*\n", text)
                if p.strip() and not p.lstrip().startswith(("#", "[!", "![", "<", "```", "|"))
            ]
            links = sorted({u.rstrip(".,") for u in URL.findall(text)
                            if not re.search(r"shields\.io|badge|img\.|\.svg|\.png", u)})
            return {"file": candidate, "words": len(text.split()),
                    "first_paragraph": paragraphs[0][:600] if paragraphs else None,
                    "links": links[:25]}
    return {"file": None}


def walk(root: Path) -> Dict[str, Any]:
    langs: Counter = Counter()
    lines: Counter = Counter()
    tests: List[str] = []
    infra: Dict[str, List[str]] = {}
    top_dirs: Counter = Counter()
    seen = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(root)
        for filename in filenames:
            seen += 1
            if seen > MAX_FILES:
                truncated = True
                break
            rel = (rel_dir / filename).as_posix()
            if rel_dir.parts:
                top_dirs[rel_dir.parts[0]] += 1
            if filename in INFRA_FILES:
                infra.setdefault(INFRA_FILES[filename], []).append(rel)
            if filename.endswith(".tf"):
                infra.setdefault("Terraform", []).append(rel)
            if TEST_FILE.search(filename) or "tests" in rel_dir.parts or "__tests__" in rel_dir.parts:
                if Path(filename).suffix in LANGUAGES:
                    tests.append(rel)
            lang = LANGUAGES.get(Path(filename).suffix.lower())
            if lang:
                langs[lang] += 1
                if lang not in MARKUP:
                    try:
                        with open(Path(dirpath) / filename, "rb") as fh:
                            lines[lang] += sum(1 for _ in fh)
                    except OSError:
                        pass
        if truncated:
            break
    ci = [label for path, label in CI_PATHS.items() if (root / path).exists()]
    workflows = sorted(p.name for p in (root / ".github" / "workflows").glob("*.y*ml")) \
        if (root / ".github" / "workflows").is_dir() else []
    return {
        "files_scanned": min(seen, MAX_FILES), "truncated": truncated,
        "languages": [{"language": k, "files": v, "lines": lines.get(k, 0)}
                      for k, v in langs.most_common()],
        "top_level_dirs": [d for d, _ in top_dirs.most_common(15)],
        "infrastructure": {k: v[:5] for k, v in sorted(infra.items())},
        "ci": ci, "workflows": workflows,
        "tests": {"files": len(tests), "examples": tests[:5]},
        "docs_dir": (root / "docs").is_dir(),
        "license": next((p.name for p in root.glob("LICENSE*")), None),
    }


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(root)] + list(args),
                             capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def history(root: Path, author: Optional[str]) -> Dict[str, Any]:
    if _git(root, "rev-parse", "--is-inside-work-tree") is None:
        return {"available": False}
    log = _git(root, "log", "--no-merges", "--format=%aI\x1f%an\x1f%ae")
    if not log:
        return {"available": True, "commits": 0}
    rows = [line.split("\x1f") for line in log.splitlines() if line.count("\x1f") == 2]
    authors: Counter = Counter("%s <%s>" % (r[1], r[2]) for r in rows)
    dates = sorted(r[0][:10] for r in rows)
    report: Dict[str, Any] = {
        "available": True, "commits": len(rows),
        "first_commit": dates[0], "last_commit": dates[-1],
        "authors": [{"author": a, "commits": c} for a, c in authors.most_common(10)],
        "author_count": len(authors),
        "shallow": (_git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true",
        "remote": (_git(root, "remote", "get-url", "origin") or "").strip() or None,
    }
    if author:
        needle = author.lower()
        mine = [r for r in rows if needle in r[1].lower() or needle in r[2].lower()]
        report["mine"] = {
            "match": author, "commits": len(mine),
            "share": round(len(mine) / len(rows), 2) if rows else 0.0,
            "first": min((r[0][:10] for r in mine), default=None),
            "last": max((r[0][:10] for r in mine), default=None),
        }
    return report


def assess_repo(root: Path, author: Optional[str] = None) -> Dict[str, Any]:
    report: Dict[str, Any] = {"kind": "repository", "path": str(root)}
    report["manifest"] = manifests(root)
    report["readme"] = readme(root)
    report["tree"] = walk(root)
    report["git"] = history(root, author)

    unknowns: List[str] = []
    if not report["readme"].get("first_paragraph") and not report["manifest"].get("description"):
        unknowns.append("nothing in the repo says what the project is for — ask the user")
    if not report["manifest"]["manifests"] and not report["tree"]["languages"]:
        unknowns.append("no manifest and no recognisable source files")
    if author and report["git"].get("available") and not report["git"].get("mine", {}).get("commits"):
        unknowns.append("no commits match %r — the user's role cannot be read from history" % author)
    if report["git"].get("shallow"):
        unknowns.append("shallow clone — commit counts and dates are incomplete")
    if report["tree"]["truncated"]:
        unknowns.append("scan stopped at %d files — language counts are partial" % MAX_FILES)
    always = [
        "outcomes (users, revenue, latency, uptime) — a codebase does not contain them",
        "the user's exact role and what they personally designed or decided",
    ]
    if not author:
        always.append("which commits are the user's — rerun with --author")
    report["unknowns"] = unknowns
    report["ask_the_user"] = always
    blocking = [u for u in unknowns if u.startswith(("nothing in", "no manifest", "no commits"))]
    report["verdict"] = "thin" if blocking else "usable"
    return report


def assess_page(html: str) -> Dict[str, Any]:
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)
    gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']*)', html, re.I)
    hints = [label for label, pattern in PAGE_HINTS if pattern.search(html)]
    if gen:
        hints.append("generator: %s" % gen.group(1))
    return {
        "kind": "page",
        "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else None,
        "meta_description": desc.group(1).strip() if desc else None,
        "stack_hints": hints,
        "note": "hints from markup only — confirm every one with the user before writing it down",
        "ask_the_user": [
            "the stack behind the page — markup shows the frontend at best",
            "the user's role, the team size, and what they built",
            "outcomes — traffic, customers, revenue — are not on the page",
        ],
        "verdict": "usable" if (title or desc) else "thin",
    }


EXIT = {"usable": 0, "thin": 3}


def render(report: Dict[str, Any]) -> str:
    out = ["%s — %s" % (report["verdict"].upper(), report.get("path") or report.get("title") or "page")]
    if report["kind"] == "page":
        out.append("  title: %s" % report["title"])
        out.append("  description: %s" % report["meta_description"])
        out.append("  stack hints (unconfirmed): %s" % (", ".join(report["stack_hints"]) or "none"))
    else:
        m, r, t, g = report["manifest"], report["readme"], report["tree"], report["git"]
        out.append("  name: %s" % (m.get("name") or "-"))
        out.append("  says it is: %s" % (m.get("description") or r.get("first_paragraph") or "-"))
        out.append("  languages: %s" % ", ".join(
            "%s (%d files)" % (l["language"], l["files"]) for l in t["languages"][:6]))
        out.append("  technologies: %s" % (", ".join(m["technologies"]) or "-"))
        out.append("  infrastructure: %s" % (", ".join(t["infrastructure"]) or "-"))
        out.append("  ci: %s   tests: %d files" % (", ".join(t["ci"]) or "none", t["tests"]["files"]))
        if g.get("available") and g.get("commits"):
            out.append("  history: %d commits, %s → %s, %d authors" % (
                g["commits"], g["first_commit"], g["last_commit"], g["author_count"]))
            if "mine" in g:
                out.append("  yours: %d commits (%d%%)" % (g["mine"]["commits"], g["mine"]["share"] * 100))
        links = [u for u in [m.get("homepage")] + r.get("links", []) if u]
        if links:
            out.append("  links: %s" % ", ".join(links[:6]))
    for item in report.get("unknowns", []):
        out.append("  ! %s" % item)
    out.append("  ask: " + "; ".join(report["ask_the_user"]))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", help="project directory (a local checkout or clone)")
    parser.add_argument("--author", help="name or email fragment identifying the user's commits")
    parser.add_argument("--page", help="a saved HTML page of the live app, instead of a directory")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.page:
        page = Path(args.page)
        html = _read(page) if page.is_file() else ""
        if not html.strip():
            sys.stderr.write("no readable page at %s\n" % args.page)
            return 2
        report = assess_page(html)
    else:
        if not args.path:
            parser.error("give a project directory, or --page with a saved HTML file")
        root = Path(args.path).resolve()
        if not root.is_dir():
            sys.stderr.write("not a directory: %s\n" % args.path)
            return 2
        if not any(root.iterdir()):
            sys.stderr.write("the directory is empty: %s\n" % args.path)
            return 2
        report = assess_repo(root, args.author)

    print(json.dumps(report, indent=2) if args.json else render(report))
    return EXIT[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
