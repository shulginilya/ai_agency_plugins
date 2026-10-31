#!/usr/bin/env python3
"""Read what a repository declares about how it is built, tested and served.

    stack_scan.py [ROOT]           summary
    stack_scan.py [ROOT] --json    the facts scaffold.py builds workflows from
    stack_scan.py [ROOT] --expect static --host cloudflare-pages
                                   the preview workflow's check: does the stack
                                   still fit the host it was set up for?

Nothing is invented: a command is reported only when the repo declares it (a
package.json script, a pytest config, a manage.py), and everything the scan
can't tell goes into `unknowns` for the agent to settle by reading the repo or
asking. `kind` is `static` (a folder of built files any static host serves),
`server` (needs a running process, so a backend host) or `unknown`. A static
frontend whose runtime dependencies include an API server (express, hono...)
also gets `api`, and its preview kind is `static+api`: the frontend on a static
host, the API on a backend host next to it.

scaffold.py copies this file into the repository as .github/devops/stack_scan.py,
so the check runs in CI without the plugin.

Standard library only. Exit status: 0 the kind is known (with --expect: it is
the expected one, or the scan can't tell), 3 it is unknown, 4 with --expect: it
changed, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LOCKFILES = [("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun"),
             ("package-lock.json", "npm")]
RUN = {"npm": "npm run", "pnpm": "pnpm run", "yarn": "yarn", "bun": "bun run"}
INSTALL = {"npm": "npm ci", "pnpm": "pnpm install --frozen-lockfile", "yarn": "yarn install --frozen-lockfile",
           "bun": "bun install --frozen-lockfile"}
SERVER_DEPS = ("express", "fastify", "koa", "@nestjs/core", "@hapi/hapi", "hono")
PY_SERVERS = ("fastapi", "flask", "django", "starlette", "aiohttp")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def first(root: Path, *names: str) -> Optional[Path]:
    for name in names:
        if (root / name).exists():
            return root / name
    return None


def config_text(root: Path, stem: str) -> str:
    found = first(root, *("%s.%s" % (stem, ext) for ext in ("ts", "mts", "js", "mjs", "cjs")))
    return read(found) if found else ""


# --- node --------------------------------------------------------------------


def scan_node(root: Path, facts: Dict[str, Any]) -> None:
    try:
        pkg = json.loads(read(root / "package.json") or "{}")
    except ValueError:
        facts["unknowns"].append("package.json is not valid JSON")
        return
    deps = dict(pkg.get("dependencies") or {}, **(pkg.get("devDependencies") or {}))
    scripts = pkg.get("scripts") or {}
    manager = next((m for f, m in LOCKFILES if (root / f).exists()), None)
    declared = str(pkg.get("packageManager") or "").split("@")[0]
    if declared in RUN:
        manager = declared
    if not manager:
        manager = "npm"
        facts["notes"].append("no lockfile: CI installs with npm install, so builds are not reproducible")
    facts.update(language="node", package_manager=manager,
                 install=INSTALL[manager] if any((root / f).exists() for f, _ in LOCKFILES) else "npm install")
    if manager == "pnpm":
        facts["pnpm_version"] = (str(pkg.get("packageManager") or "").split("@") + [""])[1].split("+")[0] or None

    nvm = first(root, ".nvmrc", ".node-version")
    if nvm:
        facts["node_version"] = read(nvm).strip().lstrip("v") or None
    elif (pkg.get("engines") or {}).get("node"):
        facts["node_version"] = re.sub(r"^[^\d]*", "", pkg["engines"]["node"]).split(" ")[0].split(".")[0] or None

    for step in ("lint", "typecheck", "test", "build"):
        name = step
        if step == "typecheck":
            name = next((n for n in ("typecheck", "type-check", "tsc", "check-types") if n in scripts), None)
        if name and name in scripts and not re.search(r"no test specified", scripts[name]):
            facts[step] = "%s %s" % (RUN[manager], name)
    if "start" in scripts:
        facts["start"] = "%s start" % RUN[manager]

    def frame(name: str, kind: str, out: Optional[str], **extra: Any) -> None:
        facts.update(framework=name, kind=kind, output_dir=out, **extra)

    if "next" in deps:
        text = config_text(root, "next.config")
        if re.search(r"""output\s*:\s*['"]export['"]""", text):
            frame("next", "static", "out")
        else:
            frame("next", "server", None)
            facts["notes"].append("Next.js without output: 'export' needs a Node server (or a Next-aware host)")
    elif "nuxt" in deps:
        if "generate" in scripts:
            frame("nuxt", "static", ".output/public", build="%s generate" % RUN[manager])
        else:
            frame("nuxt", "server", None)
            facts["notes"].append("Nuxt without a generate script builds a Node server (.output/server)")
    elif "@sveltejs/kit" in deps:
        if "@sveltejs/adapter-static" in deps:
            frame("sveltekit", "static", "build")
        else:
            frame("sveltekit", "server", None)
            facts["notes"].append("SvelteKit without adapter-static needs a server adapter")
    elif "astro" in deps:
        text = config_text(root, "astro.config")
        if re.search(r"""output\s*:\s*['"](server|hybrid)['"]""", text):
            frame("astro", "server", None)
            facts["notes"].append("Astro with output: 'server' or 'hybrid' needs a server adapter")
        else:
            match = re.search(r"""outDir\s*:\s*['"]([^'"]+)['"]""", text)
            frame("astro", "static", match.group(1).lstrip("./") if match else "dist")
    elif "gatsby" in deps:
        frame("gatsby", "static", "public")
    elif "@angular/core" in deps:
        name = pkg.get("name") or "?"
        frame("angular", "static", "dist/%s/browser" % name)
        facts["unknowns"].append("angular output dir: check outputPath in angular.json (assumed dist/<name>/browser)")
    elif "react-scripts" in deps:
        frame("create-react-app", "static", "build")
    elif "vite" in deps:
        text = config_text(root, "vite.config")
        match = re.search(r"""outDir\s*:\s*['"]([^'"]+)['"]""", text)
        out = match.group(1).lstrip("./") if match else "dist"
        frame("vite", "static", out)
    elif any(d in deps for d in SERVER_DEPS):
        frame(next(d for d in SERVER_DEPS if d in deps), "server", None)
    # Runtime dependencies only: an express in devDependencies is usually a dev or mock server.
    api = [d for d in SERVER_DEPS if d in (pkg.get("dependencies") or {})]
    if facts.get("kind") == "static" and api:
        facts["api"] = api
        facts["notes"].append("%s plus %s: the frontend is static, the API needs a backend host"
                              % (facts["framework"], ", ".join(api)))
    if facts.get("kind") == "static" and "build" not in facts:
        facts["unknowns"].append("no build script in package.json")
    if facts.get("kind") == "server" and "start" not in facts:
        facts["unknowns"].append("no start script in package.json: how is the server started?")


# --- python ------------------------------------------------------------------


def python_text(root: Path) -> str:
    """The declared Python dependencies, lowercased: pyproject, requirements files and Pipfile."""
    return "\n".join(read(root / n) for n in ("pyproject.toml", "requirements.txt", "requirements-dev.txt",
                                              "Pipfile")).lower()


def python_server(root: Path) -> Optional[str]:
    """The Python web framework this repo serves with, if any."""
    if (root / "manage.py").exists():
        return "django"
    text = python_text(root)
    return next((f for f in PY_SERVERS if re.search(r"(^|[\s\"'\[,])%s\b" % f, text)), None)


def scan_python(root: Path, facts: Dict[str, Any]) -> None:
    pyproject = read(root / "pyproject.toml")
    requirements = read(root / "requirements.txt") + read(root / "requirements-dev.txt")
    text = python_text(root)
    facts["language"] = "python"
    if (root / "uv.lock").exists():
        facts.update(package_manager="uv", install="uv sync --frozen", run="uv run ")
    elif (root / "poetry.lock").exists():
        facts.update(package_manager="poetry", install="poetry install --no-interaction", run="poetry run ")
    elif requirements:
        extra = " -r requirements-dev.txt" if (root / "requirements-dev.txt").exists() else ""
        facts.update(package_manager="pip", install="pip install -r requirements.txt" + extra, run="")
    elif pyproject:
        facts.update(package_manager="pip", install="pip install -e .", run="")
        facts["notes"].append("install assumes the project installs with pip install -e .; check for test extras")
    else:
        facts.update(package_manager="pip", install=None, run="")
        facts["unknowns"].append("no requirements.txt or pyproject.toml: how are dependencies installed?")
    version = first(root, ".python-version")
    if version:
        facts["python_version"] = read(version).strip() or None
    else:
        match = re.search(r"""requires-python\s*=\s*['"][^\d]*(\d+\.\d+)""", pyproject)
        facts["python_version"] = match.group(1) if match else None
    run = facts.get("run", "")
    if "pytest" in text or (root / "pytest.ini").exists() or (root / "conftest.py").exists():
        facts["test"] = "%spytest" % run
    elif (root / "tests").is_dir():
        facts["test"] = "%spython -m unittest discover -s tests" % run
    if "ruff" in text or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists():
        facts["lint"] = "%sruff check ." % run
    if "mypy" in text:
        facts["typecheck"] = "%smypy ." % run

    framework = python_server(root)
    if not framework:
        return
    facts.update(framework=framework, kind="server", output_dir=None)
    if framework == "django":
        project = next((p.parent.name for p in root.glob("*/wsgi.py")), None)
        if project:
            facts["start"] = "%sgunicorn %s.wsgi --bind 0.0.0.0:$PORT" % (run, project)
        else:
            facts["unknowns"].append("django: no <project>/wsgi.py found, so the start command is unknown")
        return
    module = None
    for candidate in sorted(root.glob("*.py")) + sorted(root.glob("*/*.py")):
        if re.search(r"^\s*app\s*=\s*(FastAPI|Flask|Starlette)\(", read(candidate), re.M):
            module = ".".join(candidate.relative_to(root).with_suffix("").parts)
            break
    if not module:
        facts["unknowns"].append("%s: no module defining app = %s(...) found, so the start command is unknown"
                                 % (framework, framework.capitalize()))
    elif framework in ("fastapi", "starlette"):
        facts["start"] = "%suvicorn %s:app --host 0.0.0.0 --port $PORT" % (run, module)
    elif framework == "flask":
        facts["start"] = "%sgunicorn %s:app --bind 0.0.0.0:$PORT" % (run, module)
    if "start" in facts and facts["start"].split()[len(run.split())] not in text:
        facts["notes"].append("%s is not in the declared dependencies; add it before deploying"
                              % facts["start"].split()[len(run.split())])


# --- whole repo --------------------------------------------------------------


def scan(root: Path) -> Dict[str, Any]:
    facts: Dict[str, Any] = {"root": str(root), "kind": "unknown", "language": None, "framework": None,
                             "package_manager": None, "install": None, "output_dir": None,
                             "unknowns": [], "notes": []}
    # A Python server with a package.json is a server whose package.json builds its assets
    # (Vite for Django, say): the Python side decides the kind.
    if (root / "package.json").exists() and python_server(root):
        scan_python(root, facts)
        facts["notes"].append("package.json is asset tooling for the %s server: build its assets in the "
                              "server's build command" % facts.get("framework"))
    elif (root / "package.json").exists():
        scan_node(root, facts)
    elif first(root, "pyproject.toml", "requirements.txt", "Pipfile", "manage.py", "setup.py"):
        scan_python(root, facts)
    elif (root / "index.html").exists():
        facts.update(language="html", framework="plain", kind="static", output_dir=".")
    if facts["kind"] == "unknown" and facts["language"]:
        facts["unknowns"].append("no framework the scan knows: is this served as built files or as a process?")
    elif facts["kind"] == "unknown":
        facts["unknowns"].append("no package.json, Python project or index.html at the root (a monorepo? "
                                 "scan its app folder)")
    facts["dockerfile"] = (root / "Dockerfile").exists()
    workflows = root / ".github" / "workflows"
    facts["workflows"] = sorted(p.name for p in workflows.glob("*.y*ml")) if workflows.is_dir() else []
    facts["provider"] = {"static": "cloudflare-pages", "server": "render"}.get(facts["kind"])
    facts.pop("run", None)
    return facts


def render(facts: Dict[str, Any]) -> str:
    keys = ("kind", "language", "framework", "package_manager", "node_version", "python_version", "install",
            "lint", "typecheck", "test", "build", "output_dir", "start", "provider")
    lines = ["%-16s %s" % (k + ":", facts[k]) for k in keys if facts.get(k) is not None]
    if facts.get("api"):
        lines.append("%-16s %s" % ("api:", ", ".join(facts["api"])))
    lines.append("%-16s %s" % ("workflows:", ", ".join(facts["workflows"]) or "(none)"))
    if facts["dockerfile"]:
        lines.append("%-16s %s" % ("dockerfile:", "yes"))
    lines += ["note:            %s" % n for n in facts["notes"]]
    lines += ["UNKNOWN:         %s" % u for u in facts["unknowns"]]
    return "\n".join(lines)


HOSTS = {"cloudflare-pages": "Cloudflare Pages", "render": "Render"}
KINDS = ("static", "static+api", "server")
DRIFT = "devops:stack-changed"  # pipeline-triage files a failure carrying this as devops' own


def preview_kind(facts: Dict[str, Any]) -> str:
    """The kind a preview is set up for: the scan's kind, or static+api for a static frontend with an API."""
    return "static+api" if facts["kind"] == "static" and facts.get("api") else facts["kind"]


def expect(facts: Dict[str, Any], kind: str, host: str) -> int:
    """The preview workflow's check: 0 the stack still fits the host, 4 it changed kind.

    Prints GitHub workflow commands, so the reason shows on the PR's checks. A
    scan that can't tell is a warning, not a failure: no false alarm.
    """
    now = preview_kind(facts)
    where = HOSTS.get(host, host)
    if now == kind:
        print("stack still fits %s: kind=%s, framework=%s" % (where, now, facts.get("framework")))
        return 0
    if now == "unknown":
        print("::warning title=Preview host check::the scan can't tell static from server any more; "
              "previews stay on %s. %s" % (where, "; ".join(facts["unknowns"])))
        return 0
    why = "; ".join(facts["notes"]) or "framework %s" % facts.get("framework")
    head = ("::error title=Preview host no longer fits the stack::%s recorded=%s now=%s host=%s. "
            "This repo's previews were set up for a %s build on %s, but it is now %s (%s). "
            % (DRIFT, kind, now, host, kind, where, now, why))
    fits = facts["provider"]
    if fits != host:
        tail = ("It needs %s. Run /devops:preview again: it replaces this preview with the %s one."
                % (HOSTS[fits], HOSTS[fits]))
        if now == "static+api":
            tail = ("The frontend needs Cloudflare Pages. Run /devops:preview again: it puts the frontend on "
                    "Cloudflare Pages and keeps this Render service for the API.")
    elif now == "static+api":
        tail = ("The frontend stays on %s, but the API needs its own preview on a backend host (Render). "
                "Run /devops:preview again: it rewrites this preview for kind=static+api, and the API gets its own Render preview."
                % where)
    else:
        tail = ("The host stays %s, but the preview has to change (on Render, the service type). "
                "Run /devops:preview again: it rewrites this preview's files for kind=%s." % (where, now))
    print(head + tail)
    return 4


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--expect", choices=KINDS,
                        help="the kind the preview was set up for; exit 4 when the scan says otherwise")
    parser.add_argument("--host", choices=sorted(HOSTS), help="with --expect: the host the preview runs on")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("stack_scan: not a directory: %s" % root, file=sys.stderr)
        return 2
    facts = scan(root)
    if args.expect:
        return expect(facts, args.expect, args.host or ("render" if args.expect == "server" else "cloudflare-pages"))
    print(json.dumps(facts, indent=2) if args.json else render(facts))
    return 0 if facts["kind"] != "unknown" else 3


if __name__ == "__main__":
    sys.exit(main())
