#!/usr/bin/env python3
"""Setup against real Docker and a real MongoDB (AC1-4, AC6).

Runs only when AI_AGENCY_MEMORY_TEST_DOCKER is set: it starts a container of its
own, under a random name, and removes that container and its volumes afterwards.
AI_AGENCY_MEMORY_TEST_DATA_HOME may name a data directory whose environment
already holds the driver, for a Python that cannot create one.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from helpers import SCRIPTS, isolated_env
import memconfig
import setup_db

ENABLED = bool(os.environ.get("AI_AGENCY_MEMORY_TEST_DOCKER"))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipUnless(ENABLED, "Docker setup test skipped: AI_AGENCY_MEMORY_TEST_DOCKER is not set")
class DockerSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.name = "ai-agency-memory-test-" + secrets.token_hex(4)
        extra = {"AI_AGENCY_MEMORY_CONTAINER": self.name, "CLAUDE_PROJECT_DIR": self.tmp.name}
        self.env = isolated_env(Path(self.tmp.name), **extra)
        if os.environ.get("AI_AGENCY_MEMORY_TEST_DATA_HOME"):
            self.env["XDG_DATA_HOME"] = os.environ["AI_AGENCY_MEMORY_TEST_DATA_HOME"]
        self.addCleanup(self.remove)

    def remove(self):
        self.docker("rm", "-f", self.name)
        self.docker("volume", "rm", self.name + "-data", self.name + "-config")

    def docker(self, *args):
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=120, check=False)

    def script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], env=self.env, cwd=self.tmp.name,
                              capture_output=True, text=True, encoding="utf-8", timeout=900, check=False)

    def ready(self, *args):
        done = self.script("setup_db.py", *args)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        password = urlsplit(memconfig.load(self.env)["uri"]).password
        self.assertNotIn(password, done.stdout + done.stderr)
        return done.stdout

    def users(self):
        """'true' when the temporary setup user can still log in, else 'false'."""
        uri = memconfig.load(self.env)["uri"]
        password = urlsplit(uri).password
        script = ("const p = require('fs').readFileSync(0, 'utf8').trim(); const a = db.getSiblingDB('admin'); "
                  "let setup = true; try { a.auth('memory_setup', p) } catch (e) { setup = false }; print(setup)")
        done = subprocess.run(["docker", "exec", "-i", self.name, "mongosh", "--quiet", "--eval", script],
                              input=password + "\n", capture_output=True, text=True, timeout=60, check=False)
        return done.stdout.strip().splitlines()[-1]

    def test_setup_repeat_restart_and_port_change_keep_the_memory(self):
        first = free_port()
        self.ready("--port", str(first))
        self.assertEqual(self.docker("port", self.name).stdout.split("->")[1].strip(), "127.0.0.1:%d" % first)
        self.assertEqual(self.users(), "false", "the temporary setup user must be gone")
        password = urlsplit(memconfig.load(self.env)["uri"]).password
        for where in (self.docker("inspect", self.name), self.docker("logs", self.name)):
            self.assertNotIn(password, where.stdout + where.stderr)
        refused = self.docker("exec", self.name, "mongosh", "--quiet", "--eval",
                              "db.getSiblingDB('agent_memory').memories.findOne()")
        self.assertNotEqual(refused.returncode, 0, "an unauthenticated read must be refused")

        saved = self.script("memory.py", "remember", "--title", "Kept", "--body", "across restarts")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertIn("Nothing changed", self.ready())

        self.docker("stop", self.name)
        down = self.script("memory.py", "status")
        self.assertEqual(down.returncode, 1)
        self.assertIn("does not answer", down.stderr)
        self.ready()

        self.ready("--port", str(free_port()))
        status = self.script("memory.py", "status")
        self.assertIn("memories: 1", status.stdout, status.stderr)

        config = memconfig.config_path(self.env)
        kept = config.read_text(encoding="utf-8")
        config.unlink()
        lost = self.script("setup_db.py")
        self.assertEqual(lost.returncode, 1)
        self.assertIn("password is lost", lost.stderr)
        config.write_text(kept, encoding="utf-8")
        self.assertIn("Nothing changed", self.ready())
        self.assertIn("memories: 1", self.script("memory.py", "status").stdout)

    def test_a_run_interrupted_after_the_temporary_user_is_finished_by_the_next(self):
        self.ready("--port", str(free_port()))
        config = memconfig.load(self.env)
        password = urlsplit(config["uri"]).password
        # start over on empty volumes, then stop where an interrupted run would: only the temporary user exists
        self.remove()
        self.docker("run", "-d", "--name", self.name, "--label", "ai-agency.memory=1",
                    "-p", "127.0.0.1:%d:27017" % config["port"], "-v", self.name + "-data:/data/db",
                    setup_db.IMAGE, "--auth")
        script = ("const p = require('fs').readFileSync(0, 'utf8').trim(); db.getSiblingDB('admin')"
                  ".createUser({user: 'memory_setup', pwd: p, roles: ['userAdminAnyDatabase']})")
        for _ in range(60):
            done = subprocess.run(["docker", "exec", "-i", self.name, "mongosh", "--quiet", "--eval", script],
                                  input=password + "\n", capture_output=True, text=True, timeout=60, check=False)
            if done.returncode == 0:
                break
            time.sleep(1)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Created the database user", self.ready())
        self.assertEqual(self.users(), "false")

    def test_a_taken_port_stops_with_the_port(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            done = self.script("setup_db.py", "--port", str(busy.getsockname()[1]))
            self.assertEqual(done.returncode, 1)
            self.assertIn("is taken", done.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
