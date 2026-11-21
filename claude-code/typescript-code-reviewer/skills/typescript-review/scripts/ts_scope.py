#!/usr/bin/env python3
"""Say what a TypeScript change touches and how to check it, before anyone reviews it.

    ts_scope.py [--base REF] [--repo DIR] [--json]

Compares the working tree (committed, uncommitted and untracked changes) with
the merge base of REF and HEAD. REF defaults to the remote's default branch
(origin/HEAD), else main or master. Prints:

- every changed TypeScript or JavaScript file and config file (tsconfig,
  package.json, lint and build config), with its status, line counts and tags:
  react, node, test, declaration, config, symlink. A code file with neither
  react nor node is shared. A symlink is never read: its target is printed;
- the passes to run: types, correctness and tests whenever anything changed,
  react when a React file changed, node when a Node.js file changed;
- per package (the nearest package.json): the package manager, the install
  command when node_modules is missing, the typecheck, lint and test commands,
  and each tsconfig's effective strictness, following `extends` through
  relative files and node_modules packages, with what tsc will not catch;
- escape hatches the diff adds: any, as unknown as, non-null !, @ts-ignore,
  @ts-nocheck, @ts-expect-error with no reason, eslint-disable. They are leads
  for the reviewer, not findings.

Standard library only. Exit status: 0 scoped (even with nothing to review), 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
TS_EXT = (".ts", ".tsx", ".mts", ".cts")
DECLARATION_RE = re.compile(r"\.d\.[cm]?ts$")
TEST_RE = re.compile(r"(^|/)(__tests__|__mocks__|tests?|e2e)/|\.(test|spec)\.[cm]?[jt]sx?$")
SKIP_RE = re.compile(r"(^|/)(node_modules|dist|build|coverage|\.next|\.turbo|out)/|\.min\.js$")
CONFIG_RE = re.compile(
    r"(^|/)(tsconfig[^/]*\.json|package\.json|\.eslintrc(\.[a-z]+)?|eslint\.config\.[cm]?[jt]s"
    r"|(vite|vitest|jest|next|webpack|rollup|tsup|babel)\.config\.[cm]?[jt]s|babel\.config\.json|\.babelrc)$"
)
NEXT_SERVER_PATH_RE = re.compile(r"(^|/)pages/api/|(^|/)app/(.*/)?route\.[cm]?[jt]s$|(^|/)middleware\.[cm]?[jt]s$")

IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"\n]+)['"]""")
DIRECTIVE_RE = re.compile(r"""^\s*['"]use (client|server)['"]\s*;?\s*$""", re.M)
NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "crypto", "dgram", "dns", "events", "fs",
    "fs/promises", "http", "http2", "https", "net", "os", "path", "perf_hooks", "process", "readline", "stream",
    "stream/promises", "timers", "timers/promises", "tls", "url", "util", "v8", "vm", "worker_threads", "zlib",
}
SERVER_PACKAGES = {
    "express", "fastify", "koa", "hono", "@hapi/hapi", "@trpc/server", "@prisma/client", "prisma", "pg",
    "mysql2", "mongoose", "mongodb", "typeorm", "drizzle-orm", "knex", "sequelize", "ioredis", "redis", "bullmq",
    "ws", "socket.io", "jsonwebtoken", "bcrypt", "multer", "helmet", "dotenv", "nodemailer",
}
SERVER_SCOPES = ("@nestjs/", "@aws-sdk/", "@fastify/", "@koa/")
REACT_PACKAGES = {"react", "react-dom", "react-native", "next", "preact", "@remix-run/react"}
REACT_PREFIXES = ("react-", "@tanstack/react-", "@testing-library/react")

TYPECHECK_SCRIPTS = ("typecheck", "type-check", "check-types", "check:types", "types:check")
NPM_PLACEHOLDER_TEST = "no test specified"
LOCKFILES = (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"),
             ("package-lock.json", "npm"), ("npm-shrinkwrap.json", "npm"))
RUN = {"npm": "npm run", "pnpm": "pnpm run", "yarn": "yarn run", "bun": "bun run"}
# Each runs only a locally installed tsc: a bare `npx tsc` downloads the unrelated `tsc` package.
LOCAL_BIN = {"npm": "npx --no", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bun run"}

STRICT_FAMILY = ("strictNullChecks", "noImplicitAny", "useUnknownInCatchVariables")
OPT_IN = ("noUncheckedIndexedAccess", "exactOptionalPropertyTypes")
GAPS = {
    "strictNullChecks": "null and undefined are not checked: trace every nullable value yourself",
    "noImplicitAny": "an untyped parameter or variable is silently any",
    "useUnknownInCatchVariables": "catch (e) is any: e.message on a thrown non-Error is unchecked",
    "noUncheckedIndexedAccess": "arr[i] and record[key] are typed as always present",
    "exactOptionalPropertyTypes": "an optional property also accepts an explicit undefined",
}

# (kind, pattern, whether to match code only: strings and line comments removed first)
HATCHES: Tuple[Tuple[str, "re.Pattern[str]", bool], ...] = (
    ("any", re.compile(r":\s*any\b(?!\s*[:(])|\bas\s+any\b|<\s*any\s*[>,]|,\s*any\s*>|\bany\s*\[\]"), True),
    ("as unknown as", re.compile(r"\bas\s+unknown\s+as\b"), True),
    ("non-null !", re.compile(r"[\w\])]!(?=[.\[;,)])"), True),
    ("@ts-ignore", re.compile(r"@ts-ignore\b"), False),
    ("@ts-nocheck", re.compile(r"@ts-nocheck\b"), False),
    ("@ts-expect-error with no reason", re.compile(r"@ts-expect-error\s*(\*/\s*\}?\s*)?$"), False),
    ("eslint-disable", re.compile(r"eslint-disable(-next-line|-line)?\b"), False),
)
HATCH_LIMIT = 50
STRING_RE = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`")
DIFF = ("-c", "core.quotePath=false", "diff", "--no-renames", "--no-color", "--no-ext-diff")
# A fixed pathspec, never one argument per changed file: Windows caps a command line at 32,767 characters.
CODE_PATHSPECS = tuple(":(icase)*" + ext for ext in CODE_EXT)


class ScopeError(Exception):
    pass


# ---- git -------------------------------------------------------------------

def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, check=False)
    except OSError as exc:
        raise ScopeError("git is not available: %s" % exc)
    if out.returncode != 0:
        raise ScopeError("git %s: %s" % (" ".join(args), out.stderr.decode("utf-8", "replace").strip()))
    return out.stdout.decode("utf-8", "replace")


def ref_exists(repo: Path, ref: str) -> bool:
    try:
        git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
        return True
    except ScopeError:
        return False


def default_base(repo: Path) -> str:
    try:
        head = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").strip()
        if head:
            return head
    except ScopeError:
        pass
    for ref in ("origin/main", "origin/master", "main", "master"):
        if ref_exists(repo, ref):
            return ref
    raise ScopeError("no default branch found: pass --base REF")


def read_text(path: Path, limit: int = 400_000) -> Optional[str]:
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit)
    except OSError:
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", "replace")


def changed(repo: Path, merge_base: str) -> List[Dict[str, Any]]:
    """Every path that differs between the merge base and the working tree, plus untracked files."""
    status: Dict[str, str] = {}
    fields = git(repo, *DIFF, "--name-status", "-z", merge_base).split("\0")
    for code, path in zip(fields[0::2], fields[1::2]):
        if path:
            status[path] = code[:1]
    counts: Dict[str, Tuple[Optional[int], Optional[int]]] = {}
    for record in git(repo, *DIFF, "--numstat", "-z", merge_base).split("\0"):
        parts = record.split("\t", 2)
        if len(parts) == 3:
            added, deleted, path = parts
            counts[path] = (int(added) if added.isdigit() else None, int(deleted) if deleted.isdigit() else None)
    files = [{"path": p, "status": s, "added": counts.get(p, (None, None))[0],
              "deleted": counts.get(p, (None, None))[1]} for p, s in sorted(status.items())]
    for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path and path not in status:
            text = None if os.path.islink(repo / path) else read_text(repo / path)
            files.append({"path": path, "status": "?", "added": len(text.splitlines()) if text is not None else None,
                          "deleted": 0})
    return files


def added_lines(repo: Path, merge_base: str, paths: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """The lines the diff adds to each of the given tracked paths, numbered as they are in the working tree."""
    result: Dict[str, List[Tuple[int, str]]] = {}
    wanted = set(paths)
    if not wanted:
        return result
    diff = git(repo, *DIFF, "-U0", "--src-prefix=a/", "--dst-prefix=b/", merge_base, "--", *CODE_PATHSPECS)
    current: Optional[str] = None
    number = 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            # git ends the header with a tab when the path contains a space
            target = line[4:].rstrip("\t")
            current = target[2:] if target.startswith("b/") and target[2:] in wanted else None
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            number = int(m.group(1)) if m else 0
        elif current is not None and line.startswith("+"):
            result.setdefault(current, []).append((number, line[1:]))
            number += 1
    return result


# ---- classification --------------------------------------------------------

def base_package(spec: str) -> str:
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


def is_node_module(spec: str) -> bool:
    if spec.startswith("node:") or spec in NODE_BUILTINS or spec == "next/server":
        return True
    return base_package(spec) in SERVER_PACKAGES or spec.startswith(SERVER_SCOPES)


def is_react_module(spec: str) -> bool:
    if spec == "next/server":
        return False
    return base_package(spec) in REACT_PACKAGES or spec.startswith(REACT_PREFIXES)


def tags_of(path: str, text: Optional[str]) -> List[str]:
    if CONFIG_RE.search(path):
        return ["config"]
    lower = path.lower()
    specs = IMPORT_RE.findall(text or "")
    directives = set(DIRECTIVE_RE.findall(text or ""))
    tags: List[str] = []
    if lower.endswith((".tsx", ".jsx")) or "client" in directives or any(is_react_module(s) for s in specs):
        tags.append("react")
    if "server" in directives or NEXT_SERVER_PATH_RE.search(path) or any(is_node_module(s) for s in specs):
        tags.append("node")
    if TEST_RE.search(path):
        tags.append("test")
    if DECLARATION_RE.search(lower):
        tags.append("declaration")
    return tags


def passes_for(files: List[Dict[str, Any]]) -> List[str]:
    if not files:
        return []
    passes = ["types", "correctness", "tests"]
    for tag in ("react", "node"):
        if any(tag in f["tags"] for f in files):
            passes.append(tag)
    return passes


# ---- escape hatches ---------------------------------------------------------

def code_only(line: str) -> str:
    stripped = STRING_RE.sub('""', line)
    cut = stripped.find("//")
    return stripped[:cut] if cut >= 0 else stripped


def hatches_in(path: str, numbered_lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    found = []
    for number, line in numbered_lines:
        code = code_only(line)
        for kind, pattern, on_code in HATCHES:
            if pattern.search(code if on_code else line):
                found.append({"file": path, "line": number, "kind": kind, "text": line.strip()[:120]})
    return found


# ---- tsconfig ---------------------------------------------------------------

def skip_blank(text: str, j: int) -> int:
    """The index of the next character from j that is not whitespace or inside a comment."""
    n = len(text)
    while j < n:
        if text[j] in " \t\r\n":
            j += 1
        elif text.startswith("//", j):
            end = text.find("\n", j)
            j = n if end < 0 else end
        elif text.startswith("/*", j):
            end = text.find("*/", j + 2)
            j = n if end < 0 else end + 2
        else:
            break
    return j


def parse_jsonc(text: str) -> Any:
    """JSON with comments and trailing commas, as tsconfig allows. Strings are left untouched."""
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith(("//", "/*"), i):
            i = skip_blank(text, i)
        elif ch == ",":
            j = skip_blank(text, i + 1)
            if not (j < n and text[j] in "}]"):
                out.append(ch)
            i += 1
        else:
            out.append(ch)
            i += 1
    return json.loads("".join(out))


def find_up(start: Path, stop: Path, relative: str) -> Optional[Path]:
    """The first start/.../relative that exists, walking up from start to stop."""
    directory = start
    while True:
        candidate = directory / relative
        if candidate.exists():
            return candidate
        if directory == stop or directory.parent == directory:
            return None
        directory = directory.parent


def as_config(candidate: Path) -> Optional[Path]:
    for path in (candidate, Path(str(candidate) + ".json"), candidate / "tsconfig.json"):
        if path.is_file():
            return path
    return None


def resolve_extends(spec: str, config_dir: Path, stop: Path) -> Optional[Path]:
    if spec.startswith((".", "/")):
        return as_config((config_dir / spec).resolve())
    directory = config_dir
    while True:
        found = as_config(directory / "node_modules" / spec)
        if found:
            return found
        if directory == stop or directory.parent == directory:
            return None
        directory = directory.parent


def read_config(config: Path) -> Dict[str, Any]:
    raw = parse_jsonc(config.read_text(encoding="utf-8-sig"))
    return raw if isinstance(raw, dict) else {}


def load_options(config: Path, stop: Path, seen: Optional[set] = None) -> Tuple[Dict[str, Any], List[str]]:
    """(compilerOptions merged through extends, the extends it could not resolve or read)."""
    seen = set() if seen is None else seen
    if config in seen or len(seen) > 10:
        return {}, []
    seen.add(config)
    try:
        raw = read_config(config)
    except (OSError, ValueError) as exc:
        return {}, ["%s (unreadable: %s)" % (config.name, exc)]
    options: Dict[str, Any] = {}
    unresolved: List[str] = []
    extends = raw.get("extends")
    for spec in [extends] if isinstance(extends, str) else extends if isinstance(extends, list) else []:
        base = resolve_extends(str(spec), config.parent, stop)
        if base is None:
            unresolved.append(str(spec))
            continue
        base_options, base_unresolved = load_options(base, stop, seen)
        options.update(base_options)
        unresolved += base_unresolved
    own = raw.get("compilerOptions")
    if isinstance(own, dict):
        options.update(own)
    return options, unresolved


def typescript_major(start: Path, stop: Path) -> Optional[int]:
    manifest = find_up(start, stop, "node_modules/typescript/package.json")
    if manifest is None:
        return None
    try:
        return int(str(json.loads(manifest.read_text(encoding="utf-8-sig")).get("version", "")).split(".")[0])
    except (OSError, ValueError):
        return None


def strictness(config: Path, repo: Path) -> Dict[str, Any]:
    options, unresolved = load_options(config, repo)
    try:
        raw = read_config(config)
    except (OSError, ValueError):
        raw = {}
    references = raw.get("references") if isinstance(raw.get("references"), list) else []
    major = typescript_major(config.parent, repo)
    strict = options.get("strict")
    strict_value = (None if major is None else major >= 6) if strict is None else bool(strict)
    flags: Dict[str, Optional[bool]] = {"strict": strict_value}
    for name in STRICT_FAMILY:
        flags[name] = bool(options[name]) if name in options else strict_value
    for name in OPT_IN:
        flags[name] = bool(options.get(name, False))
    notes = []
    if strict is None:
        notes.append("strict is not set: on from TypeScript 6, off before (installed: %s)"
                     % ("%d.x" % major if major is not None else "unknown"))
    return {"config": rel(config, repo), "flags": flags,
            "gaps": [GAPS[name] for name in STRICT_FAMILY + OPT_IN if flags[name] is False],
            "unresolved": unresolved, "notes": notes,
            "solution": bool(references) and raw.get("files") == []}


def configs_for(package_dir: Path, repo: Path) -> List[Path]:
    """The package's tsconfig.json (or the nearest one above it), then the projects it references."""
    root = find_up(package_dir, repo, "tsconfig.json")
    if root is None or not root.is_file():
        return []
    configs = [root]
    try:
        references = read_config(root).get("references")
    except (OSError, ValueError):
        references = None
    for ref in references if isinstance(references, list) else []:
        if isinstance(ref, dict) and ref.get("path"):
            target = as_config((root.parent / str(ref["path"])).resolve())
            if target is not None and target not in configs:
                configs.append(target)
    return configs


# ---- packages and checks ----------------------------------------------------

def rel(path: Path, repo: Path) -> str:
    try:
        value = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)
    return value or "."


def package_dir_of(path: str, repo: Path) -> Path:
    found = find_up((repo / path).parent, repo, "package.json")
    return found.parent if found is not None and found.is_file() else repo


def read_manifest(directory: Path) -> Dict[str, Any]:
    try:
        data = json.loads((directory / "package.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def manager_of(package_dir: Path, repo: Path) -> Tuple[str, Optional[Path]]:
    """(the package manager, the directory holding its lockfile, if any)."""
    directory = package_dir
    declared = None
    while True:
        field = str(read_manifest(directory).get("packageManager") or "")
        if field and declared is None:
            declared = field.split("@")[0]
        for lockfile, manager in LOCKFILES:
            if (directory / lockfile).is_file():
                return (declared if declared in RUN else manager), directory
        if directory == repo or directory.parent == directory:
            break
        directory = directory.parent
    return (declared if declared in RUN else "npm"), None


def install_command(manager: str, lock_dir: Optional[Path]) -> str:
    if manager == "pnpm":
        return "pnpm install --frozen-lockfile"
    if manager == "yarn":
        berry = lock_dir is not None and (lock_dir / ".yarnrc.yml").is_file()
        return "yarn install --immutable" if berry else "yarn install --frozen-lockfile"
    if manager == "bun":
        return "bun install --frozen-lockfile"
    return "npm ci" if lock_dir is not None else "npm install"


def declares_typescript(package_dir: Path, repo: Path) -> bool:
    for directory in {package_dir, repo}:
        manifest = read_manifest(directory)
        for key in ("dependencies", "devDependencies"):
            deps = manifest.get(key)
            if isinstance(deps, dict) and "typescript" in deps:
                return True
    return False


def package_report(package_dir: Path, repo: Path) -> Dict[str, Any]:
    manifest = read_manifest(package_dir)
    scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
    manager, lock_dir = manager_of(package_dir, repo)
    checks: Dict[str, Optional[str]] = {"typecheck": None, "lint": None, "test": None}
    for name in TYPECHECK_SCRIPTS:
        if name in scripts:
            checks["typecheck"] = "%s %s" % (RUN[manager], name)
            break
    if "lint" in scripts:
        checks["lint"] = "%s lint" % RUN[manager]
    if "test" in scripts and NPM_PLACEHOLDER_TEST not in str(scripts["test"]):
        checks["test"] = "CI=true %s test" % RUN[manager]
    configs = configs_for(package_dir, repo)
    reports = [strictness(c, repo) for c in configs]
    notes: List[str] = []
    if checks["typecheck"] is None and configs:
        if reports[0]["solution"]:
            checks["typecheck"] = "%s tsc -b %s" % (
                LOCAL_BIN[manager], Path(os.path.relpath(configs[0], package_dir)).as_posix())
            notes.append("no typecheck script; %s only references projects, so tsc -b checks them "
                         "(it may write build output: check git status after)" % reports[0]["config"])
        else:
            checks["typecheck"] = "%s tsc --noEmit -p %s" % (
                LOCAL_BIN[manager], Path(os.path.relpath(configs[0], package_dir)).as_posix())
            notes.append("no typecheck script; tsc --noEmit is the fallback")
        if not declares_typescript(package_dir, repo):
            notes.append("typescript is not in package.json: the tsc fallback needs it installed")
    install = None
    if (package_dir / "package.json").is_file() and find_up(package_dir, repo, "node_modules") is None:
        install = {"dir": rel(lock_dir or package_dir, repo), "command": install_command(manager, lock_dir)}
    return {"dir": rel(package_dir, repo), "name": manifest.get("name"), "manager": manager, "install": install,
            "checks": checks, "tsconfigs": reports, "notes": notes}


# ---- the scope --------------------------------------------------------------

def scope(repo: Path, base: Optional[str] = None) -> Dict[str, Any]:
    repo = Path(git(repo, "rev-parse", "--show-toplevel").strip()).resolve()
    base = base or default_base(repo)
    if not ref_exists(repo, base):
        raise ScopeError("base %r is not a commit here (fetch it first?)" % base)
    merge_base = git(repo, "merge-base", base, "HEAD").strip()
    files = []
    for entry in changed(repo, merge_base):
        path = entry["path"]
        is_config = bool(CONFIG_RE.search(path))
        if SKIP_RE.search(path) or not (is_config or path.lower().endswith(CODE_EXT)):
            continue
        link = entry["status"] != "D" and os.path.islink(repo / path)
        # Never read through a symlink: its target can be outside the repository (~/.npmrc, /proc/self/environ).
        text = read_text(repo / path) if entry["status"] != "D" and not link else None
        entry["language"] = "config" if is_config else "ts" if path.lower().endswith(TS_EXT) else "js"
        entry["tags"] = tags_of(path, text) + (["symlink"] if link else [])
        if link:
            target = os.readlink(str(repo / path))
            # Windows returns an absolute target as an extended-length path: \\?\C:\...
            entry["target"] = target[4:] if target.startswith("\\\\?\\") else target
        files.append(entry)
    code = [f for f in files if f["language"] != "config" and f["status"] != "D" and "symlink" not in f["tags"]]
    hatches: List[Dict[str, Any]] = []
    tracked = [f["path"] for f in code if f["status"] != "?"]
    for path, lines in sorted(added_lines(repo, merge_base, tracked).items()):
        hatches += hatches_in(path, lines)
    for f in code:
        if f["status"] == "?":
            hatches += hatches_in(f["path"], list(enumerate((read_text(repo / f["path"]) or "").splitlines(), 1)))
    packages: Dict[str, Path] = {}
    for f in files:
        directory = package_dir_of(f["path"], repo)
        packages.setdefault(rel(directory, repo), directory)
    return {"base": base, "merge_base": merge_base[:12], "head": git(repo, "rev-parse", "--short", "HEAD").strip(),
            "uncommitted": bool(git(repo, "status", "--porcelain", "--untracked-files=no").strip()),
            "files": files, "passes": passes_for(files),
            "packages": [package_report(d, repo) for _, d in sorted(packages.items())],
            "hatches": hatches[:HATCH_LIMIT], "hatches_more": max(0, len(hatches) - HATCH_LIMIT)}


def count(value: Optional[int], sign: str) -> str:
    return "%s%s" % (sign, "?" if value is None else value)


def render(result: Dict[str, Any]) -> str:
    lines = ["base: %s (merge base %s)   head: %s%s" % (
        result["base"], result["merge_base"], result["head"],
        " + uncommitted changes" if result["uncommitted"] else "")]
    files = result["files"]
    if not files:
        lines += ["nothing to review: no TypeScript, JavaScript or config files changed", "passes: none"]
        return "\n".join(lines) + "\n"
    code = sum(1 for f in files if f["language"] != "config")
    lines.append("files: %d TypeScript/JavaScript, %d config" % (code, len(files) - code))
    names = [f["path"] + (" (untracked)" if f["status"] == "?" else "")
             + (" -> %s" % f["target"] if "target" in f else "") for f in files]
    width = max(len(name) for name in names)
    for f, name in zip(files, names):
        lines.append("  %s  %-*s  %6s %6s   %s" % (f["status"], width, name, count(f["added"], "+"),
                                                  count(f["deleted"], "-"), " ".join(f["tags"]) or "shared"))
    if any("symlink" in f["tags"] for f in files):
        lines.append("symlinks: never read them; report each link and its target, and any target outside the repo")
    lines.append("passes: %s" % ", ".join(result["passes"]))
    for package in result["packages"]:
        lines.append("package %s%s (%s)" % (package["dir"], " — %s" % package["name"] if package["name"] else "",
                                           package["manager"]))
        for report in package["tsconfigs"]:
            if report["solution"]:
                lines.append("  %s: references only" % report["config"])
                continue
            flags = "; ".join("%s %s" % (k, {True: "on", False: "off", None: "unset"}[v])
                              for k, v in report["flags"].items())
            lines.append("  %s: %s" % (report["config"], flags))
            if report["gaps"]:
                lines.append("    tsc will not catch: %s" % "; ".join(report["gaps"]))
            for note in report["notes"]:
                lines.append("    note: %s" % note)
            for spec in report["unresolved"]:
                lines.append("    extends %s not found: the flags it sets are unknown (install dependencies?)" % spec)
        if package["install"]:
            lines.append("  install first: (cd %s && %s)   node_modules is missing"
                         % (package["install"]["dir"], package["install"]["command"]))
        for name in ("typecheck", "lint", "test"):
            command = package["checks"][name]
            lines.append("  %s: %s" % (name, "(cd %s && %s)" % (package["dir"], command) if command else "none"))
        for note in package["notes"]:
            lines.append("  note: %s" % note)
    hatches = result["hatches"]
    if hatches:
        lines.append("escape hatches added (%d): leads to check, not findings" % (len(hatches) + result["hatches_more"]))
        for h in hatches:
            lines.append("  %s:%d  %s   %s" % (h["file"], h["line"], h["kind"], h["text"]))
        if result["hatches_more"]:
            lines.append("  ... and %d more" % result["hatches_more"])
    else:
        lines.append("escape hatches added: none")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", help="the ref to compare against (default: origin/HEAD, else main or master)")
    parser.add_argument("--repo", default=".", help="a directory inside the repository (default: .)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = scope(Path(args.repo).resolve(), args.base)
    except ScopeError as exc:
        print("ts_scope: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
