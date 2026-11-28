"""Where memory keeps its files, and the connection string.

Nothing here lives in a repository: the config file is in the user's config
directory and is readable by that user only, and the driver is installed in an
environment under the user's data directory. AI_AGENCY_MEMORY_URI, when set,
wins over the config file.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import unquote, urlsplit

ENV_URI = "AI_AGENCY_MEMORY_URI"


class ConfigError(Exception):
    """The config file exists and cannot be used. The message never quotes it."""


def _base(env: Mapping[str, str], variable: str, *fallback: str) -> Path:
    value = env.get(variable)
    return Path(value) if value else Path.home().joinpath(*fallback)


def config_path(env: Mapping[str, str] = os.environ) -> Path:
    return _base(env, "XDG_CONFIG_HOME", ".config") / "ai-agency" / "memory.json"


def venv_dir(env: Mapping[str, str] = os.environ) -> Path:
    return _base(env, "XDG_DATA_HOME", ".local", "share") / "ai-agency" / "memory" / "venv"


def python_in(venv: Path) -> Path:
    return venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"


def add_driver_path(env: Mapping[str, str] = os.environ) -> None:
    """Make the packages setup installed importable in this process."""
    venv = venv_dir(env)
    found = list(venv.glob("lib/python*/site-packages")) + list(venv.glob("Lib/site-packages"))
    for path in found:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def load(env: Mapping[str, str] = os.environ) -> Dict[str, Any]:
    path = config_path(env)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError) as exc:
        raise ConfigError("the config file %s cannot be read (%s)" % (path, type(exc).__name__))
    try:
        data = json.loads(text)
    except ValueError:
        raise ConfigError("the config file %s is not valid JSON" % path)
    if (not isinstance(data, dict) or not isinstance(data.get("uri", ""), str)
            or not isinstance(data.get("port", 0), int)):
        raise ConfigError("the config file %s does not have the expected shape" % path)
    return data


def save(data: Dict[str, Any], env: Mapping[str, str] = os.environ) -> None:
    """Replace the config file in one step; mkstemp creates it readable by the user only."""
    path = config_path(env)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".memory-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
            out.write("\n")
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def uri(env: Mapping[str, str] = os.environ) -> Optional[str]:
    return env.get(ENV_URI) or load(env).get("uri") or None


def redact(text: str, connection: Optional[str] = None) -> str:
    """The text with connection-string passwords removed."""
    if connection:
        try:
            password = urlsplit(connection).password
        except ValueError:
            password = None
        if password:
            for form in (password, unquote(password)):
                text = text.replace(form, "***")
    return re.sub(r"(://[^\s/:@]*:)[^\s/]*@", r"\1***@", text)
