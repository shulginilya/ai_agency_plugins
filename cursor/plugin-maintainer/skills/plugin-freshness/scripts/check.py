#!/usr/bin/env python3
"""Is every installed plugin up to date with the plugins repo? Prints a Markdown report.

A plugin is up to date when its installed copy (~/.claude/skills/<name>) has the
source version and is file-for-file identical to a fresh build of the source.
The report also says whether the local default branch matches origin, since a
stale checkout makes every comparison stale too.

Read-only unless --update is given: it fetches remote refs, builds into a
temporary directory, and never installs, pulls, commits or edits a tracked file.

With --update it then brings the install up to date, but only from a safe
source: the default branch, no uncommitted changes under plugins/, not ahead of
origin, and the default skills dir (where `apkit install` writes). Otherwise it
prints "Not updating: <why>" and changes nothing. When the default branch is
behind origin it fast-forwards it (`git pull --ff-only`, never a merge), then for
each stale plugin, and each source plugin that is not installed yet, runs
`apkit build --plugin <name>` and `apkit install <name>` for Claude Code, and
prints the report again as the proof.

Exit codes: 0 everything up to date (after the update, with --update), 1 something
stale, out of sync, not updated or failed to update, 2 the check could not run
(not the plugins repo, build failed).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_FILES = 8
TARGET = "claude-code"
IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = (".pyc",)
DEFAULT_SKILLS = Path.home() / ".claude" / "skills"  # where `apkit install --target claude-code` writes


def _files(root: Path) -> Dict[str, Path]:
    out = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix in IGNORED_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if IGNORED_DIRS.intersection(rel.parts):
            continue
        out[rel.as_posix()] = path
    return out


def compare_trees(built: Path, installed: Path) -> List[str]:
    """Relative paths that differ, are only built, or are only installed; sorted."""
    a, b = _files(built), _files(installed)
    diffs = set(a).symmetric_difference(b)
    diffs.update(rel for rel in set(a) & set(b) if a[rel].read_bytes() != b[rel].read_bytes())
    return sorted(diffs)


def read_version(manifest: Path) -> Optional[str]:
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def compare_versions(a: str, b: str) -> Optional[int]:
    """-1, 0 or 1 for x.y.z[-pre] versions (a pre-release sorts below its release); None if either isn't one."""
    keys = []
    for v in (a, b):
        m = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+\S*)?", v.strip())
        if not m:
            return None
        keys.append((tuple(int(n) for n in m.group(1).split(".")), m.group(2) is None, m.group(2) or ""))
    return (keys[0] > keys[1]) - (keys[0] < keys[1])


def parse_plugin_list(text: str) -> List[Tuple[str, str, str]]:
    """(name, source, version) for each plugin in `claude plugin list` output."""
    found = []
    current = None
    for line in text.splitlines():
        head = re.match(r"\s*❯\s+([^@\s]+)@(\S+)", line)
        if head:
            current = (head.group(1), head.group(2))
            continue
        ver = re.match(r"\s*Version:\s*(\S+)", line)
        if ver and current:
            found.append((current[0], current[1], ver.group(1)))
            current = None
    return found


def _git(repo: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_sync(repo: Path, fetch: bool = True) -> Optional[Dict]:
    """Where the checkout stands against origin, or None outside a git repo."""
    if not repo.is_dir() or _git(repo, "rev-parse", "--git-dir") is None:
        return None
    ref = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    default = ref.split("/", 1)[1] if ref and "/" in ref else "main"
    sync = {
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "?",
        "default": default,
        "head": _git(repo, "rev-parse", "--short", "HEAD") or "?",
        "behind": None,
        "ahead": None,
        "fetch_failed": False,
        "dirty": bool(_git(repo, "status", "--porcelain", "--", "plugins")),
    }
    if fetch and _git(repo, "fetch", "--quiet", "origin", default) is None:
        sync["fetch_failed"] = True
    counts = _git(repo, "rev-list", "--left-right", "--count", "%s...origin/%s" % (default, default))
    if counts:
        ahead, behind = counts.split()
        sync["ahead"], sync["behind"] = int(ahead), int(behind)
    return sync


def sync_ok(sync: Optional[Dict]) -> bool:
    if sync is None:
        return True
    return (sync["branch"] == sync["default"] and sync["behind"] == 0
            and sync["ahead"] == 0 and not sync.get("dirty"))


def render_sync(sync: Optional[Dict]) -> str:
    if sync is None:
        return "Source: not a git repository; compared against the working tree as it is."
    default = sync["default"]
    parts = []
    if sync["branch"] != default:
        parts.append("on branch %s, not %s, so this compares against that branch" % (sync["branch"], default))
    if sync["behind"] is None:
        parts.append("no origin/%s to compare with" % default)
    elif sync["behind"] or sync["ahead"]:
        parts.append("%s is %d behind, %d ahead of origin/%s; pull before trusting this report"
                     % (default, sync["behind"], sync["ahead"], default))
    else:
        parts.append("%s is in sync with origin/%s" % (default, default))
    if sync.get("dirty"):
        parts.append("uncommitted changes under plugins/ are part of the build")
    if sync.get("fetch_failed"):
        parts.append("fetch failed, so origin may be out of date")
    return "Source: %s @ %s; %s." % (sync["branch"], sync["head"], "; ".join(parts))


def source_plugins(repo: Path) -> Dict[str, str]:
    out = {}
    for d in sorted((repo / "plugins").iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            version = read_version(d / "plugin.json")
            if version is not None:
                out[d.name] = version
    return out


def build(repo: Path, into: Path) -> Optional[Path]:
    cmd = [sys.executable, "-m", "tools.apkit", "--root", str(repo), "build",
           "--target", TARGET, "--dist-dir", str(into), "--skip-validate"]
    out = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.stdout.write("Build failed (%s):\n%s%s" % (" ".join(cmd[1:]), out.stdout, out.stderr))
        return None
    return into / TARGET


def read_plugin_list(path: Optional[str]) -> Tuple[List[Tuple[str, str, str]], Optional[str]]:
    if path:
        try:
            return parse_plugin_list(Path(path).read_text(encoding="utf-8")), None
        except OSError as exc:
            return [], "could not read %s: %s" % (path, exc)
    claude = shutil.which("claude")
    if not claude:
        return [], "`claude` is not on PATH, so plugins from other sources were not checked"
    try:
        out = subprocess.run([claude, "plugin", "list"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], "`claude plugin list` failed: %s" % exc
    if out.returncode != 0:
        return [], "`claude plugin list` exited %d (%s), so plugins from other sources were not checked" % (
            out.returncode, (out.stderr or "").strip() or "no output")
    return parse_plugin_list(out.stdout), None


def report(repo: Path, skills: Path, built: Path, sync: Optional[Dict],
           listing: List[Tuple[str, str, str]], listing_note: Optional[str]) -> Tuple[str, bool]:
    sources = source_plugins(repo)
    rows, stale, diffs, notes = [], [], {}, []
    for name, src_version in sources.items():
        installed = skills / name
        if not installed.is_dir():
            notes.append("%s: in the source (%s) but not installed." % (name, src_version))
            continue
        if not (built / name).is_dir():
            notes.append("%s: installed but not built for %s, so its files were not compared." % (name, TARGET))
            continue
        inst_version = read_version(installed / ".claude-plugin" / "plugin.json") or "?"
        changed = compare_trees(built / name, installed)
        ok = not changed and inst_version == src_version
        rows.append("| %s | %s | %s | %s | %s |" % (
            name, inst_version, src_version, "identical" if not changed else "differs",
            "up to date" if ok else "stale"))
        if not ok:
            stale.append(name)
        if changed:
            diffs[name] = changed
    for name, source, version in listing:
        if source == "skills-dir" or name not in sources or version == sources[name]:
            continue
        order = compare_versions(version, sources[name])
        relation = {-1: "is older than", 1: "is newer than"}.get(order, "differs from")
        notes.append("%s@%s %s %s the source (%s)." % (name, source, version, relation, sources[name]))
    if listing_note:
        notes.append(listing_note[0].upper() + listing_note[1:] + ".")

    lines = [render_sync(sync), ""]
    if rows:
        lines += ["| Plugin | Installed | Source | Files | Status |", "| --- | --- | --- | --- | --- |"] + rows + [""]
        if stale:
            lines.append("%d of %d stale: %s." % (len(stale), len(rows), ", ".join(stale)))
        else:
            lines.append("All %d up to date." % len(rows))
    else:
        lines.append("No plugin from this repo is installed in %s." % skills)
    if diffs:
        lines += ["", "Differing files (built vs installed):"]
        for name, changed in diffs.items():
            shown = ", ".join(changed[:MAX_FILES])
            more = len(changed) - MAX_FILES
            lines.append("- %s: %s%s" % (name, shown, " … and %d more" % more if more > 0 else ""))
    if notes:
        lines += ["", "Notes:"] + ["- " + n for n in notes]
    return "\n".join(lines) + "\n", not stale and sync_ok(sync)


def stale_names(repo: Path, skills: Path, built: Path) -> List[str]:
    """Installed plugins from this repo whose version or files differ from the build."""
    stale = []
    for name, src_version in source_plugins(repo).items():
        installed = skills / name
        if not installed.is_dir() or not (built / name).is_dir():
            continue
        inst_version = read_version(installed / ".claude-plugin" / "plugin.json") or "?"
        if inst_version != src_version or compare_trees(built / name, installed):
            stale.append(name)
    return stale


def new_names(repo: Path, skills: Path, built: Path) -> List[str]:
    """Plugins in the source, built for Claude Code, that are not installed yet."""
    return [name for name in source_plugins(repo) if not (skills / name).is_dir() and (built / name).is_dir()]


def refuse_reason(sync: Optional[Dict], skills: Path) -> Optional[str]:
    """Why the install must not be changed from this checkout, or None when it is safe to."""
    if skills.resolve() != DEFAULT_SKILLS.resolve():
        return "the skills dir %s is not %s, where apkit installs" % (skills, DEFAULT_SKILLS)
    if sync is None:
        return None
    default = sync["default"]
    if sync["branch"] != default:
        return "on branch %s, not %s" % (sync["branch"], default)
    if sync.get("dirty"):
        return "uncommitted changes under plugins/"
    if sync["behind"] is None:
        return "no origin/%s to compare with" % default
    if sync["ahead"]:
        return "%s is %d commits ahead of origin/%s" % (default, sync["ahead"], default)
    return None


def pull_ff(repo: Path, default: str) -> Optional[str]:
    """Fast-forward the default branch from origin; the error text, or None on success."""
    out = subprocess.run(["git", "pull", "--ff-only", "origin", default], cwd=str(repo), capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode == 0:
        return None
    return (out.stderr or out.stdout).strip() or "exit %d" % out.returncode


def update_plugins(repo: Path, names: List[str]) -> List[Tuple[str, bool, str]]:
    """Build then install each plugin for Claude Code: (name, ok, output of the step that failed)."""
    results = []
    for name in names:
        output = ""
        for step in (["build", "--plugin", name], ["install", name]):
            cmd = [sys.executable, "-m", "tools.apkit", *step, "--target", TARGET]
            done = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            if done.returncode != 0:
                output = ("%s%s" % (done.stdout, done.stderr)).strip() or "exit %d" % done.returncode
                break
        results.append((name, not output, output))
    return results


def find_repo(start: Path) -> Path:
    top = _git(start, "rev-parse", "--show-toplevel") if start.is_dir() else None
    return Path(top) if top else start


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--repo", help="plugins repo (default: the git repo holding the current directory)")
    ap.add_argument("--skills-dir", default=str(DEFAULT_SKILLS),
                    help="where plugins are installed (default: ~/.claude/skills)")
    ap.add_argument("--build-dir", help="compare against these already-built %s bundles instead of building" % TARGET)
    ap.add_argument("--no-fetch", action="store_true", help="do not fetch origin first")
    ap.add_argument("--update", action="store_true",
                    help="bring stale plugins up to date and install new ones (build + install), from a safe source only")
    ap.add_argument("--plugin-list-file", help="saved `claude plugin list` output instead of running it")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve() if args.repo else find_repo(Path.cwd())
    if not (repo / "tools" / "apkit").is_dir() or not (repo / "plugins").is_dir():
        print("%s is not the plugins repo (no tools/apkit); run it from the plugins repo." % repo)
        return 2

    skills = Path(args.skills_dir)
    sync = git_sync(repo, fetch=not args.no_fetch)
    listing, listing_note = read_plugin_list(args.plugin_list_file)
    tmp = []

    def fresh_build() -> Optional[Path]:
        if args.build_dir:
            return Path(args.build_dir)
        tmp.append(tempfile.mkdtemp(prefix="plugin-check-"))
        return build(repo, Path(tmp[-1]))

    try:
        built = fresh_build()
        if built is None:
            return 2
        text, ok = report(repo, skills, built, sync, listing, listing_note)
        sys.stdout.write(text)
        if not args.update:
            return 0 if ok else 1
        stale = stale_names(repo, skills, built)
        new = new_names(repo, skills, built)
        behind = bool(sync and sync.get("behind"))
        if not (stale or new or behind):
            return 0 if ok else 1
        why = refuse_reason(sync, skills)
        if why:
            print("\nNot updating: %s." % why)
            return 1
        if behind:
            failure = pull_ff(repo, sync["default"])
            if failure:
                print("\nNot updating: git pull --ff-only failed: %s." % failure)
                return 1
            sync = git_sync(repo, fetch=False)
            built = fresh_build()
            if built is None:
                return 2
            stale = stale_names(repo, skills, built)
            new = new_names(repo, skills, built)
        results = update_plugins(repo, stale + new)
        done = [name for name, good, _ in results if good]
        failed = [(name, out) for name, good, out in results if not good]
        print()
        updated = [name for name in done if name not in new]
        installed = [name for name in done if name in new]
        if updated:
            print("Updated: %s." % ", ".join(updated))
        if installed:
            print("Installed: %s." % ", ".join(installed))
        for name, out in failed:
            print("Failed: %s\n%s" % (name, "\n".join("    " + line for line in out.splitlines())))
        text, ok = report(repo, skills, built, sync, listing, listing_note)
        print("\nAfter the update:\n")
        sys.stdout.write(text)
        if done:
            print("\nRun /reload-plugins to load the %s plugins in this session."
                  % " and ".join(w for w, names in (("updated", updated), ("new", installed)) if names))
        return 0 if ok and not failed else 1
    finally:
        for path in tmp:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
