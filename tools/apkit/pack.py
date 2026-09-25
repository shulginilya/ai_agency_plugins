"""Packing a built bundle into one archive a harness can ingest.

Why this is Python and not `zip`: Git Bash on Windows ships no zip binary, and
this repo's whole point is that a plugin reaches every harness from any machine.
zipfile is standard library, so it is there wherever apkit runs.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .targets import Target

PACK_DIR = Path("pack")

# Files that are noise inside an archive a harness unpacks.
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}
EXCLUDED_DIRS = {"__pycache__", ".git"}


class PackError(Exception):
    """A bundle cannot be packed into something the harness would accept."""


@dataclass
class PackResult:
    target: Target
    plugin_name: str
    version: str
    path: Path
    file_count: int

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size


def archive_name(plugin_name: str, version: str, target: Target) -> str:
    return "%s-%s%s" % (plugin_name, version, target.archive_suffix)


def _files(bundle_root: Path) -> List[Path]:
    kept = []
    for path in sorted(bundle_root.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(bundle_root).parts)
        if path.name in EXCLUDED_NAMES or parts & EXCLUDED_DIRS:
            continue
        kept.append(path)
    return kept


def _required_root_file(target: Target) -> Optional[str]:
    """The file a harness looks for at the top of the archive, if it has one."""
    manifest = target.component("manifest")
    return manifest.path if manifest.emitted else None


def pack_bundle(
    bundle_root: Path, target: Target, plugin_name: str, version: str, out_dir: Path
) -> PackResult:
    if not bundle_root.is_dir():
        raise PackError(
            "nothing built for %s -> %s: run a build first (looked in %s)"
            % (plugin_name, target.id, bundle_root)
        )

    files = _files(bundle_root)
    if not files:
        raise PackError("built bundle for %s -> %s is empty" % (plugin_name, target.id))

    required = _required_root_file(target)
    if required and not (bundle_root / required).is_file():
        # Uploading an archive without its manifest fails silently in the host
        # app, which is a miserable thing to debug. Refuse here instead.
        raise PackError(
            "%s -> %s has no %s; %s loads the archive by that file, so it would "
            "be rejected without explanation" % (plugin_name, target.id, required, target.name)
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / archive_name(plugin_name, version, target)
    if destination.exists():
        destination.unlink()

    # Contents go at the archive root: a wrapper directory is the difference
    # between a plugin that installs and one that is ignored.
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(bundle_root).as_posix())

    return PackResult(
        target=target,
        plugin_name=plugin_name,
        version=version,
        path=destination,
        file_count=len(files),
    )


def archive_members(path: Path) -> List[str]:
    """Read back what an archive holds -- used by tests and by --verify."""
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()
