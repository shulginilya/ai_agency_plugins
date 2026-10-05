"""Command line entry point: validate · build · pack · install · doctor · test · docs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from . import docs as docs_mod
from . import install as installer
from . import marketplace as marketplace_mod
from . import pack as pack_mod
from .build import build_all
from .model import Plugin, SourceError, discover, unmanifested
from .targets import TargetError, load_targets
from .validate import validate_plugin

PLUGINS_DIR = "plugins"
TARGETS_DIR = "targets"
DIST_DIR = "dist"
TEMPLATE_DIR = "_template"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _color(enabled: bool, code: str) -> str:
    return code if enabled else ""


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def project_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / PLUGINS_DIR).is_dir() and (candidate / TARGETS_DIR).is_dir():
            return candidate
    return Path.cwd()


def _load(root: Path, plugin_names: Optional[List[str]]) -> List[Plugin]:
    plugins = discover(root / PLUGINS_DIR, only=plugin_names)
    if not plugins:
        which = ", ".join(plugin_names) if plugin_names else "any"
        message = "no plugins found (looking for: %s)" % which
        strays = unmanifested(root / PLUGINS_DIR, only=plugin_names)
        if strays:
            message += "; these have content but no %s: %s" % (
                "plugin.json",
                ", ".join(_relative(p, root) for p in strays),
            )
        raise SourceError(message)
    return plugins


def _warn_unmanifested(root: Path, plugin_names: Optional[List[str]]) -> None:
    tty = sys.stdout.isatty()
    for stray in unmanifested(root / PLUGINS_DIR, only=plugin_names):
        print(
            "%swarn%s %s has content but no plugin.json — it is not being built"
            % (_color(tty, YELLOW), _color(tty, RESET), _relative(stray, root))
        )


# --------------------------------------------------------------------- commands


def cmd_validate(args) -> int:
    root = project_root(args.root)
    plugins = _load(root, args.plugin)
    _warn_unmanifested(root, args.plugin)
    tty = sys.stdout.isatty()
    failed = False
    for plugin in plugins:
        report = validate_plugin(plugin, strict=args.strict)
        for finding in report.findings:
            colour = _color(tty, RED if finding.level == "error" else YELLOW)
            print("%s%s%s" % (colour, finding, _color(tty, RESET)))
        if report.ok(strict=args.strict):
            print(
                "%sok%s   %s (%d skills, %d commands, %d agents)"
                % (
                    _color(tty, GREEN),
                    _color(tty, RESET),
                    plugin.name,
                    len(plugin.skills),
                    len(plugin.commands),
                    len(plugin.agents),
                )
            )
        else:
            failed = True
    return 1 if failed else 0


def cmd_build(args) -> int:
    root = project_root(args.root)
    plugins = _load(root, args.plugin)
    targets = load_targets(root / TARGETS_DIR, only=args.target)
    tty = sys.stdout.isatty()

    if not args.skip_validate:
        blocked = False
        for plugin in plugins:
            report = validate_plugin(plugin, strict=False)
            for finding in report.errors:
                print("%s%s%s" % (_color(tty, RED), finding, _color(tty, RESET)))
                blocked = True
        if blocked:
            print("\nbuild aborted: fix the errors above, or pass --skip-validate")
            return 1

    dist_root = Path(args.dist_dir).resolve() if args.dist_dir else root / DIST_DIR
    if args.clean and dist_root.exists():
        shutil.rmtree(dist_root)

    results = build_all(plugins, targets, dist_root)
    for result in results:
        print(
            "%sbuilt%s %s -> %s  (%d artifacts)"
            % (
                _color(tty, GREEN),
                _color(tty, RESET),
                result.plugin.name,
                _relative(result.root, root),
                result.file_count,
            )
        )
        for component_name, reason in result.skipped:
            print("      %sskip %s: %s%s" % (_color(tty, DIM), component_name, reason, _color(tty, RESET)))
        for warning in result.warnings:
            print("      %swarn %s%s" % (_color(tty, YELLOW), warning, _color(tty, RESET)))
    return 0


def cmd_install(args) -> int:
    root = project_root(args.root)
    plugins = _load(root, [args.plugin])
    plugin = plugins[0]
    targets = load_targets(root / TARGETS_DIR, only=args.target)
    project = Path(args.into).resolve() if args.into else Path.cwd()

    exit_code = 0
    for target in targets:
        dist_root = Path(args.dist_dir).resolve() if args.dist_dir else root / DIST_DIR
        bundle = dist_root / target.id / plugin.name
        if not bundle.is_dir():
            print("no build for %s/%s — run `apkit build` first" % (target.id, plugin.name))
            exit_code = 1
            continue
        actions = installer.plan(target, plugin.name, bundle, args.scope, project)
        if not actions:
            print("%s: nothing to install at %s scope" % (target.id, args.scope))
            continue
        print("%s (%s scope)" % (target.name, args.scope))
        for action in actions:
            print("  %s" % action.describe())
        if args.dry_run:
            continue
        for line in installer.apply(actions, link=args.link, dry_run=False):
            print("  %s" % line)
        installer.record(root, plugin.name, target.id, args.scope, actions)
    return exit_code


def cmd_uninstall(args) -> int:
    root = project_root(args.root)
    removed = installer.uninstall(root, args.plugin, args.target)
    if not removed:
        print("nothing recorded for %s" % args.plugin)
        return 0
    for path in removed:
        print("removed %s" % path)
    return 0


def cmd_doctor(args) -> int:
    root = project_root(args.root)
    targets = load_targets(root / TARGETS_DIR)
    project = Path(args.into).resolve() if args.into else Path.cwd()
    tty = sys.stdout.isatty()

    print("python      %s" % sys.version.split()[0])
    print("repo        %s" % root)
    print("project     %s" % project)
    print()

    for target in targets:
        unverified = target.unverified()
        flag = (
            " %s(unverified: %s)%s" % (_color(tty, YELLOW), ", ".join(unverified), _color(tty, RESET))
            if unverified
            else ""
        )
        print("%-12s %s%s" % (target.id, target.name, flag))
        for scope, placements in target.install.items():
            for placement in placements:
                dest = installer.resolve_dest(placement.dest, "<plugin>", project)
                parent = dest if placement.mode == "children" else dest.parent
                exists = "present" if parent.exists() else "absent "
                mark = _color(tty, GREEN if parent.exists() else DIM)
                print("  %s%-8s %-8s %s%s" % (mark, scope, exists, dest, _color(tty, RESET)))
        print()

    ledger = installer.read_ledger(root)
    entries = ledger.get("installs", [])
    if entries:
        print("recorded installs")
        for entry in entries:
            print(
                "  %s -> %s (%s), %d path(s)"
                % (entry["plugin"], entry["target"], entry["scope"], len(entry.get("paths", [])))
            )
    else:
        print("recorded installs: none")
    return 0


def cmd_targets(args) -> int:
    root = project_root(args.root)
    targets = load_targets(root / TARGETS_DIR)
    header = "%-12s %-30s %s" % ("id", "harness", "components")
    print(header)
    print("-" * len(header))
    for target in targets:
        summary = []
        for name in ("skills", "commands", "agents", "hooks", "mcp"):
            component = target.component(name)
            mark = {"native": "+", "emulated": "~", "manual": "!", "unsupported": "-"}[
                component.support
            ]
            summary.append("%s%s" % (mark, name))
        print("%-12s %-30s %s" % (target.id, target.name, " ".join(summary)))
    print()
    print("+ native   ~ emulated   ! manual step   - unsupported")
    return 0


def cmd_test(args) -> int:
    root = project_root(args.root)
    plugins = _load(root, args.plugin)
    failures = 0
    ran = 0
    for plugin in plugins:
        tests_dir = plugin.root / "tests"
        if not tests_dir.is_dir():
            continue
        for script in sorted(tests_dir.glob("test_*.py")):
            ran += 1
            print("running %s" % script.relative_to(root))
            outcome = subprocess.run(
                [sys.executable, str(script)], cwd=str(root), check=False
            )
            if outcome.returncode != 0:
                failures += 1
    repo_tests = root / "tests"
    if repo_tests.is_dir():
        for script in sorted(repo_tests.glob("test_*.py")):
            ran += 1
            print("running %s" % script.relative_to(root))
            outcome = subprocess.run(
                [sys.executable, str(script)], cwd=str(root), check=False
            )
            if outcome.returncode != 0:
                failures += 1
    if ran == 0:
        print("no tests found")
        return 0
    print("\n%d/%d test file(s) passed" % (ran - failures, ran))
    return 1 if failures else 0


def cmd_pack(args) -> int:
    """Turn built bundles into one archive per (plugin, target)."""
    root = project_root(args.root)
    plugins = _load(root, args.plugin)
    targets = load_targets(root / TARGETS_DIR, only=args.target)
    tty = sys.stdout.isatty()

    dist_root = Path(args.dist_dir).resolve() if args.dist_dir else root / DIST_DIR
    out_root = Path(args.out).resolve() if args.out else dist_root / pack_mod.PACK_DIR

    failures = 0
    for target in targets:
        for plugin in plugins:
            bundle = dist_root / target.id / plugin.name
            try:
                result = pack_mod.pack_bundle(
                    bundle, target, plugin.name, plugin.version, out_root / target.id
                )
            except pack_mod.PackError as exc:
                print("%serror%s %s" % (_color(tty, RED), _color(tty, RESET), exc))
                failures += 1
                continue
            print(
                "%spacked%s %s  (%d files, %.1f KiB)"
                % (
                    _color(tty, GREEN),
                    _color(tty, RESET),
                    _relative(result.path, root),
                    result.file_count,
                    result.size_bytes / 1024.0,
                )
            )
            if args.verbose and target.archive_note:
                print("       %s%s%s" % (_color(tty, DIM), target.archive_note, _color(tty, RESET)))

    if failures:
        print("\n%d archive(s) not written" % failures)
    return 1 if failures else 0


def cmd_marketplace(args) -> int:
    root = project_root(args.root)
    if getattr(args, "plugin", None):
        raise SourceError(
            "marketplace takes no --plugin. The index is generated from the whole "
            "tree and overwritten in full, so naming a subset writes a file that "
            "silently omits every other plugin. If you reached for it because an "
            "unscoped command failed, run `apkit validate` to see which directory "
            "is the problem."
        )
    plugins = _load(root, None)
    _warn_unmanifested(root, None)
    if args.publish == "git-subdir" and not args.repo:
        raise SourceError(
            "--publish git-subdir needs --repo (owner/name, or a git URL): the index "
            "lives on main while the bundles live on the published branch, so every "
            "entry has to say which repository to fetch them from."
        )
    index = marketplace_mod.build_index(
        plugins,
        owner={"name": args.owner, "email": args.email} if args.owner else {"name": "unknown"},
        name=args.name,
        description=args.description,
        source_root=args.source_root,
        publish=args.publish,
        repo=args.repo,
        ref=args.ref,
    )
    path = marketplace_mod.write_index(root, index)
    print("wrote %s (%d plugin(s))" % (path.relative_to(root), len(plugins)))
    return 0


def cmd_new(args) -> int:
    root = project_root(args.root)
    template = root / PLUGINS_DIR / TEMPLATE_DIR
    destination = root / PLUGINS_DIR / args.name
    if not template.is_dir():
        print("template missing at %s" % template)
        return 1
    if destination.exists():
        print("%s already exists" % destination)
        return 1
    shutil.copytree(template, destination, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = destination / "plugin.json"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("_template", args.name), encoding="utf-8"
    )
    print("created %s" % destination.relative_to(root))
    print("next: edit plugin.json, then `python -m tools.apkit validate --plugin %s`" % args.name)
    return 0


def cmd_docs(args) -> int:
    root = project_root(args.root)
    # Always every plugin: a scoped handbook would silently replace the full one.
    plugins = _load(root, None)
    _warn_unmanifested(root, None)
    targets = load_targets(root / TARGETS_DIR)
    html_path = Path(args.html).resolve() if args.html else root / DIST_DIR / "handbook.html"
    pdf_path = Path(args.out).resolve() if args.out else root / "docs" / "handbook.pdf"

    page = docs_mod.render_html(root, plugins, targets, build_parser())
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(page, encoding="utf-8")
    print("wrote %s" % _relative(html_path, root))
    if args.html_only:
        return 0

    browser = docs_mod.find_browser(args.browser)
    if not browser:
        print(
            "error: no Chrome, Edge or Chromium found to print the PDF. Pass --browser PATH "
            "or set %s; the HTML above is complete and can be printed by hand."
            % docs_mod.BROWSER_ENV,
            file=sys.stderr,
        )
        return 1
    try:
        docs_mod.print_pdf(browser, html_path, pdf_path)
    except docs_mod.DocsError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("wrote %s  (via %s)" % (_relative(pdf_path, root), browser))
    return 0


# ----------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apkit", description="Build harness-agnostic agent plugins."
    )
    parser.add_argument("--root", help="repo root (default: auto-detected)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check plugin sources against the Agent Skills spec")
    p.add_argument("--plugin", action="append", help="limit to this plugin (repeatable)")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("build", help="render every plugin for every target into dist/")
    p.add_argument("--plugin", action="append")
    p.add_argument("--target", action="append")
    p.add_argument("--clean", action="store_true", help="wipe the output directory first")
    p.add_argument("--dist-dir", help="write bundles here instead of ./dist")
    p.add_argument("--skip-validate", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("install", help="place a built bundle where a harness will find it")
    p.add_argument("plugin")
    p.add_argument("--target", action="append", required=True)
    p.add_argument("--scope", default="user", help="user | project (default: user)")
    p.add_argument("--into", help="project directory for project scope (default: cwd)")
    p.add_argument("--link", action="store_true", help="symlink instead of copy where possible")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dist-dir", help="read bundles from here instead of ./dist")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", help="remove what a previous install recorded")
    p.add_argument("plugin")
    p.add_argument("--target")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("doctor", help="show harness paths on this machine and what is installed")
    p.add_argument("--into")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("targets", help="list targets and their component support")
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("test", help="run plugin and repo test scripts")
    p.add_argument("--plugin", action="append")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("pack", help="zip built bundles into per-harness archives")
    p.add_argument("--plugin", action="append")
    p.add_argument("--target", action="append")
    p.add_argument("--dist-dir", help="where the built bundles are (default: dist/)")
    p.add_argument("--out", help="where to write archives (default: <dist>/pack/<target>/)")
    p.add_argument(
        "-v", "--verbose", action="store_true", help="print each target's install note"
    )
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("marketplace", help="regenerate .claude-plugin/marketplace.json")
    # Accepted only so the rejection in cmd_marketplace can explain itself;
    # argparse's "unrecognized arguments" would not.
    p.add_argument("--plugin", action="append", help=argparse.SUPPRESS)
    p.add_argument("--name", default="ai-agency")
    p.add_argument("--description", default="Harness-agnostic agent plugins.")
    p.add_argument("--owner", default="Ilya Shulgin")
    p.add_argument("--email", default="ishulgin8@gmail.com")
    p.add_argument(
        "--publish",
        choices=marketplace_mod.PUBLISH_MODES,
        default="git-subdir",
        help=(
            "how entries point at their bundle: git-subdir fetches it from the "
            "published branch (default, the only form that works off this machine), "
            "path names a local directory under dist/"
        ),
    )
    p.add_argument(
        "--repo",
        default="https://github.com/shulginilya/ai_agency_plugins.git",
        help="repository holding the published bundles (git-subdir only)",
    )
    p.add_argument(
        "--ref",
        default=marketplace_mod.DEFAULT_REF,
        help="branch or tag the bundles are published on (git-subdir only, default: %s)"
        % marketplace_mod.DEFAULT_REF,
    )
    p.add_argument(
        "--source-root",
        default=None,
        help=(
            "directory the bundles sit in -- relative to the marketplace root with "
            "--publish path (default: ./dist/claude-code), or to the branch root with "
            "--publish git-subdir (default: claude-code)"
        ),
    )
    p.set_defaults(func=cmd_marketplace)

    p = sub.add_parser("new", help="scaffold a plugin from plugins/_template")
    p.add_argument("name")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("docs", help="regenerate the PDF handbook (docs/handbook.pdf) from source")
    p.add_argument("--out", help="PDF path (default: docs/handbook.pdf)")
    p.add_argument("--html", help="also keep the HTML here (default: dist/handbook.html)")
    p.add_argument("--html-only", action="store_true", help="write the HTML and stop")
    p.add_argument("--browser", help="Chrome/Edge/Chromium executable (default: $APKIT_BROWSER, then auto-detect)")
    p.set_defaults(func=cmd_docs)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (SourceError, TargetError, installer.InstallError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
