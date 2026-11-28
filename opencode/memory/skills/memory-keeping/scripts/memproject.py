"""Which project a directory belongs to: its git origin remote, else its root directory."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


def _git(directory: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def normalize_remote(url: str, root: Path) -> str:
    """One name for every way of writing a remote, with any credentials dropped."""
    url = url.strip()
    local = url.lower().startswith("file://") or url.startswith(("/", ".", "~")) or re.match(r"^[A-Za-z]:[\\/]", url)
    if not local:
        if "://" in url:
            netloc, _, path = url.split("://", 1)[1].partition("/")
            host = re.sub(r":\d*$", "", netloc.rsplit("@", 1)[-1])
            return _remote_name(host, path)
        scp = re.match(r"^(?:[^/]*@)?([^/:@]+):(.*)$", url)
        if scp:
            return _remote_name(scp.group(1), scp.group(2))
    if url.lower().startswith("file://"):
        url = url[len("file://"):]
    return "path:" + (root / Path(url).expanduser()).resolve().as_posix()


def _remote_name(host: str, path: str) -> str:
    path = path.strip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    return ("%s/%s" % (host, path.strip("/"))).lower()


def identify(directory: Path) -> str:
    directory = Path(directory)
    top = _git(directory, "rev-parse", "--show-toplevel")
    root = Path(top) if top else directory
    remote = _git(directory, "remote", "get-url", "origin")
    if remote:
        return normalize_remote(remote, root.resolve())
    return "dir:" + root.resolve().as_posix()


def head_commit(directory: Path) -> Optional[str]:
    return _git(Path(directory), "rev-parse", "HEAD")
