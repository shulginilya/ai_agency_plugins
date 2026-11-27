#!/usr/bin/env python3
"""Set up memory: the driver in its own environment, MongoDB in Docker, the indexes, the connection string.

    setup_db.py [--port N]

Safe to run again: it repairs what is missing and otherwise changes nothing. It
never deletes the data volume, and it never prints the password. With
AI_AGENCY_MEMORY_URI set, Docker is left alone and that database is used.

Exit status: 0 ready, 1 stopped (the message says why).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import memconfig  # noqa: E402
import store as store_module  # noqa: E402

IMAGE = "mongo:8.0.38"
CONTAINER = "ai-agency-memory"
VOLUME = CONTAINER + "-data"
ENV_CONTAINER = "AI_AGENCY_MEMORY_CONTAINER"  # another name, to try setup beside a real one
LABEL = "ai-agency.memory"
DEFAULT_PORT = 27027
USER = "agent_memory"
REQUIREMENTS = SCRIPTS / "requirements.txt"
INSPECT = ('{{.State.Running}}|{{range $p, $b := .HostConfig.PortBindings}}{{if eq $p "27017/tcp"}}'
           '{{(index $b 0).HostPort}}{{end}}{{end}}|{{index .Config.Labels "%s"}}' % LABEL)
SETUP_USER = "memory_setup"
# MongoDB lets the first user be created from inside the container only if it can manage users. So a
# temporary one is made, creates the memory user (read and write on one database) and removes itself.
# An interrupted run leaves the temporary one behind, with the same password, and the next run finishes.
# The password arrives on standard input, so it is in no argument list and no shell history.
CREATE_USER = (
    "const password = require('fs').readFileSync(0, 'utf8').trim(); "
    "const admin = db.getSiblingDB('admin'); "
    "try { admin.createUser({user: '%(setup)s', pwd: password, roles: ['userAdminAnyDatabase']}) } catch (e) {} "
    "admin.auth('%(setup)s', password); "
    "if (!admin.getUser('%(user)s')) { admin.createUser({user: '%(user)s', pwd: password, "
    "roles: [{role: 'readWrite', db: '%(db)s'}]}) } "
    "admin.dropUser('%(setup)s')"
) % {"setup": SETUP_USER, "user": USER, "db": store_module.DATABASE}
PORT_TAKEN = ("port is already allocated", "address already in use", "ports are not available")
READY_ATTEMPTS = 60


class SetupError(Exception):
    pass


def pinned_driver() -> str:
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("pymongo=="):
            return line.split("==", 1)[1].strip()
    raise SetupError("%s does not pin pymongo" % REQUIREMENTS)


def run_command(cmd: List[str], input: Optional[str] = None, timeout: int = 60) -> Tuple[int, str]:
    try:
        done = subprocess.run(cmd, input=input, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return 124, "timed out after %d s" % timeout
    return done.returncode, (done.stdout + done.stderr).strip()


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "posix":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ignore connections still closing
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def check_database(uri: str) -> str:
    """'ok', 'auth' (it answers and refuses the login) or 'down'."""
    try:
        with contextlib.closing(store_module.MongoStore(uri)) as database:
            database.check()
    except store_module.AuthFailed:
        return "auth"
    except store_module.Unavailable:
        return "down"
    return "ok"


def create_indexes(uri: str) -> bool:
    with contextlib.closing(store_module.MongoStore(uri)) as database:
        return database.ensure_indexes()


def _last(text: str) -> str:
    return text.strip().splitlines()[-1][:300] if text.strip() else "no output"


class Setup:
    def __init__(self, env: Mapping[str, str], run: Callable = run_command, check: Callable = check_database,
                 ensure_indexes: Callable = create_indexes, port_free: Callable = port_is_free,
                 sleep: Callable = time.sleep, log: Callable = print):
        self.env = env
        self._run = run
        self.check = check
        self.ensure_indexes = ensure_indexes
        self.port_free = port_free
        self.sleep = sleep
        self.log = log
        self.container = env.get(ENV_CONTAINER) or CONTAINER
        self.volume = self.container + "-data"

    def run(self, port: Optional[int] = None) -> bool:
        """Make memory ready; True when anything had to change."""
        if port is not None and not 1 <= port <= 65535:
            raise SetupError("the port must be between 1 and 65535")
        changed = self._environment()
        memconfig.add_driver_path(self.env)
        uri = self.env.get(memconfig.ENV_URI)
        if uri:
            self.log("Using the database in %s; Docker is left alone." % memconfig.ENV_URI)
            state = self.check(uri)
            if state != "ok":
                raise SetupError("the database in %s %s" % (memconfig.ENV_URI, "refuses the login"
                                                            if state == "auth" else "does not answer"))
            changed = self._indexes(uri) or changed
        else:
            changed = self._database(port) or changed
        self.log("Memory is ready. Restart the session so the memory tools load it." if changed
                 else "Nothing changed. Memory is ready.")
        return changed

    def _environment(self) -> bool:
        """The private Python environment holding the pinned driver."""
        directory = memconfig.venv_dir(self.env)
        python = memconfig.python_in(directory)
        wanted = pinned_driver()
        probe = [str(python), "-c", "import pymongo; print(pymongo.version)"]
        if python.exists() and self._run(probe) == (0, wanted):
            return False
        self.log("Installing pymongo %s into %s" % (wanted, directory))
        code, out = self._run([sys.executable, "-m", "venv", "--clear", str(directory)], timeout=120)
        if code != 0:
            if "ensurepip" in out:
                raise SetupError("this Python cannot create environments. On Debian or Ubuntu run "
                                 "`sudo apt install python3-venv`, then run setup again")
            raise SetupError("could not create %s: %s" % (directory, _last(out)))
        code, out = self._run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                               "-r", str(REQUIREMENTS)], timeout=300)
        if code != 0 or self._run(probe) != (0, wanted):
            raise SetupError("could not install pymongo %s: %s" % (wanted, _last(memconfig.redact(out))))
        return True

    def _docker(self, *args: str, **kwargs) -> Tuple[int, str]:
        try:
            return self._run(["docker", *args], **kwargs)
        except FileNotFoundError:
            raise SetupError("Docker is not installed. Install it, then run setup again")

    def _inspect(self) -> Optional[Tuple[bool, int, str]]:
        """(running, published port, our label) of the container, or None when there is none."""
        code, out = self._docker("container", "inspect", "--format", INSPECT, self.container)
        if code != 0:
            if "no such" in out.lower():
                return None
            raise SetupError("cannot inspect the container %s: %s" % (self.container, _last(out)))
        running, port, label = _last(out).split("|", 2)
        return running == "true", int(port) if port.isdigit() else 0, label

    def _require_free(self, port: int) -> None:
        if not self.port_free(port):
            raise self._taken(port)

    def _taken(self, port: int) -> SetupError:
        return SetupError("port %d is taken; choose another with --port N" % port)

    def _database(self, port: Optional[int]) -> bool:
        code, out = self._docker("version", "--format", "{{.Server.Version}}")
        if code != 0:
            raise SetupError("Docker does not answer: is it running, and may you use it? (%s)" % _last(out))
        try:
            config = memconfig.load(self.env)
        except memconfig.ConfigError as exc:
            raise SetupError("%s. Fix it or move it away. Nothing was deleted" % exc)
        found = self._inspect()
        if found and found[2] != "1":
            raise SetupError("a container named %s exists that setup did not create; rename or remove it, "
                             "then run setup again" % self.container)
        password = urlsplit(config["uri"]).password if config.get("uri") else None
        if not password:
            if found or self._docker("volume", "inspect", self.volume)[0] == 0:
                raise SetupError(
                    "the data volume %s exists but its stored password is lost (%s has none). Restore that "
                    "file, or set %s. Removing the volume yourself starts over and destroys the memories. "
                    "Nothing was deleted" % (self.volume, memconfig.config_path(self.env), memconfig.ENV_URI))
            password = secrets.token_urlsafe(24)
        port = port or config.get("port") or DEFAULT_PORT
        uri = "mongodb://%s:%s@127.0.0.1:%d/%s?authSource=admin&directConnection=true" % (
            USER, password, port, store_module.DATABASE)
        changed = False

        if found and found[1] != port:
            self._require_free(port)  # before the working container is touched
            self.log("Moving MongoDB to port %d; the data stays in %s." % (port, self.volume))
            code, out = self._docker("rm", "-f", self.container)  # no -v: the volume is kept
            if code != 0:
                raise SetupError("could not replace the container: %s" % _last(out))
            found = None
        if not found:
            self._require_free(port)
        wanted = {"uri": uri, "port": port}
        if config != wanted:
            memconfig.save(wanted, self.env)  # before the database exists, so a broken run can resume
            changed = True
        if not found:
            self._create(port)
            changed = True
        elif not found[0]:
            self.log("Starting the container %s." % self.container)
            code, out = self._docker("start", self.container)
            if code != 0:
                if any(phrase in out.lower() for phrase in PORT_TAKEN):
                    raise self._taken(port)
                raise SetupError("could not start the container: %s" % _last(out))
            changed = True

        self._wait()
        state = self._state(uri)
        if state == "auth":  # no user yet: MongoDB lets the first one be created from inside the container
            code, out = self._docker("exec", "-i", self.container, "mongosh", "--quiet", "--eval", CREATE_USER,
                                     input=password + "\n")
            if code != 0:
                raise SetupError(
                    "could not create the database user. Most likely the stored password does not match the data "
                    "in volume %s: restore the matching %s. Nothing was deleted. MongoDB said: %s"
                    % (self.volume, memconfig.config_path(self.env), _last(out.replace(password, "***"))))
            self.log("Created the database user.")
            changed = True
            state = self._state(uri)
        if state != "ok":
            raise SetupError("MongoDB runs but cannot be used (%s). See `docker logs %s`"
                             % ("login refused" if state == "auth" else "no answer on port %d" % port,
                                self.container))
        return self._indexes(uri) or changed

    def _create(self, port: int) -> None:
        self.log("Starting MongoDB on 127.0.0.1:%d (the first run downloads %s)." % (port, IMAGE))
        code, out = self._docker(
            "run", "-d", "--name", self.container, "--label", LABEL + "=1", "--restart", "unless-stopped",
            "-p", "127.0.0.1:%d:27017" % port, "-v", self.volume + ":/data/db",
            "-v", self.container + "-config:/data/configdb", IMAGE, "--auth", timeout=600)
        if code != 0:
            if any(phrase in out.lower() for phrase in PORT_TAKEN):
                self._docker("rm", "-f", self.container)  # the half-made container; the volume stays
                raise self._taken(port)
            raise SetupError("could not start MongoDB: %s" % _last(out))

    def _wait(self) -> None:
        for _ in range(READY_ATTEMPTS):
            code, out = self._docker("exec", self.container, "mongosh", "--quiet", "--eval",
                                     "db.adminCommand('ping').ok")
            if code == 0 and out.strip().endswith("1"):
                return
            self.sleep(1)
        raise SetupError("MongoDB did not start. See `docker logs %s`" % self.container)

    def _state(self, uri: str) -> str:
        for _ in range(10):
            state = self.check(uri)
            if state != "down":
                return state
            self.sleep(1)
        return "down"

    def _indexes(self, uri: str) -> bool:
        try:
            created = self.ensure_indexes(uri)
        except store_module.Unavailable as exc:
            raise SetupError("could not create the indexes: %s" % exc)
        if created:
            self.log("Created the indexes.")
        return created


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, help="the port on 127.0.0.1 (default %d)" % DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        Setup(os.environ).run(port=args.port)
    except SetupError as exc:
        print("memory setup stopped: %s." % str(exc).rstrip("."), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
