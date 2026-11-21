#!/usr/bin/env python3
"""Read what a repository declares about how it is built, tested and served.

    stack_scan.py [ROOT]           summary
    stack_scan.py [ROOT] --json    the facts scaffold.py builds workflows from

Nothing is invented: a command is reported only when the repo declares it (a
package.json script, a pytest config, a manage.py), and everything the scan
can't tell goes into `unknowns` for the agent to settle by reading the repo or
asking. `kind` is `static` (a folder of built files any static host serves),
`server` (needs a running process, so a backend host) or `unknown`.

Standard library only. Exit status: 0 the kind is known, 3 it is unknown, 2 bad input.
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
        server = [d for d in SERVER_DEPS if d in deps]
        frame("vite", "static", out)
        if server:
            facts["notes"].append("vite plus %s: the frontend is static, the API needs a backend host"
                                  % ", ".join(server))
    elif any(d in deps for d in SERVER_DEPS):
        frame(next(d for d in SERVER_DEPS if d in deps), "server", None)
    if facts.get("kind") == "static" and "build" not in facts:
        facts["unknowns"].append("no build script in package.json")
    if facts.get("kind") == "server" and "start" not in facts:
        facts["unknowns"].append("no start script in package.json: how is the server started?")


# --- python ------------------------------------------------------------------


def scan_python(root: Path, facts: Dict[str, Any]) -> None:
    pyproject = read(root / "pyproject.toml")
    requirements = read(root / "requirements.txt") + read(root / "requirements-dev.txt")
    text = (pyproject + "\n" + requirements + "\n" + read(root / "Pipfile")).lower()
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

    framework = next((f for f in PY_SERVERS if re.search(r"(^|[\s\"'\[,])%s\b" % f, text)), None)
    if (root / "manage.py").exists():
        framework = "django"
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
    if (root / "package.json").exists():
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
    lines.append("%-16s %s" % ("workflows:", ", ".join(facts["workflows"]) or "(none)"))
    if facts["dockerfile"]:
        lines.append("%-16s %s" % ("dockerfile:", "yes"))
    lines += ["note:            %s" % n for n in facts["notes"]]
    lines += ["UNKNOWN:         %s" % u for u in facts["unknowns"]]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("stack_scan: not a directory: %s" % root, file=sys.stderr)
        return 2
    facts = scan(root)
    print(json.dumps(facts, indent=2) if args.json else render(facts))
    return 0 if facts["kind"] != "unknown" else 3


if __name__ == "__main__":
    sys.exit(main())
