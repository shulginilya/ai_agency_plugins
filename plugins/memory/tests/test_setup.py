#!/usr/bin/env python3
"""Setup against a pretend Docker: fresh, repeated, and every way it must stop without deleting data (AC1-4)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from helpers import isolated_env
import memconfig
import setup_db

NAME = setup_db.CONTAINER
VOLUME = setup_db.VOLUME


class Machine:
    """Docker, Python and the database as setup sees them."""

    def __init__(self):
        self.docker = "ok"  # "ok" | "missing" | "stopped"
        self.containers = {}  # name -> {"running", "port", "label"}
        self.volumes = set()
        self.users = {}  # volume -> password: the database's users live in the volume
        self.taken = set()  # ports someone else listens on
        self.driver = None
        self.can_venv = True
        self.indexed = set()
        self.commands = []
        self.inputs = []

    def run(self, cmd, input=None, timeout=None):
        self.commands.append(list(cmd))
        if input:
            self.inputs.append(input)
        if cmd[0] != "docker":
            return self.python(cmd)
        if self.docker == "missing":
            raise FileNotFoundError("docker")
        if self.docker == "stopped":
            return 1, "Cannot connect to the Docker daemon"
        verb = cmd[1]
        if verb == "version":
            return 0, "27.3.1"
        if verb == "volume":
            return (0, "[{}]") if cmd[-1] in self.volumes else (1, "no such volume")
        if verb == "container":
            c = self.containers.get(cmd[-1])
            if c is None:
                return 1, "Error: No such container: %s" % cmd[-1]
            return 0, "%s|%s|%s" % ("true" if c["running"] else "false", c["port"], c["label"])
        if verb == "run":
            name = cmd[cmd.index("--name") + 1]
            port = int(cmd[cmd.index("-p") + 1].split(":")[1])
            self.volumes.add(cmd[cmd.index("-v") + 1].split(":")[0])
            self.containers[name] = {"running": port not in self.taken, "port": port, "label": "1"}
            if port in self.taken:
                return 125, "Bind for 127.0.0.1:%d failed: port is already allocated" % port
            return 0, "abc123"
        if verb == "start":
            c = self.containers[cmd[-1]]
            if c["port"] in self.taken:
                return 1, "listen tcp4 127.0.0.1: bind: address already in use"
            c["running"] = True
            return 0, cmd[-1]
        if verb == "rm":
            del self.containers[cmd[-1]]
            return 0, cmd[-1]
        if verb == "exec":
            if "-i" in cmd:
                if VOLUME in self.users:
                    return 1, "MongoServerError: command createUser requires authentication"
                self.users[VOLUME] = input.strip()
                return 0, ""
            return 0, "1"
        raise AssertionError("unexpected docker command %r" % cmd)

    def python(self, cmd):
        if cmd[1:3] == ["-m", "venv"]:
            if not self.can_venv:
                return 1, "The virtual environment was not created successfully because ensurepip is not available."
            target = Path(cmd[-1])
            python = memconfig.python_in(target)
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_text("", encoding="utf-8")
            self.driver = None
            return 0, ""
        if cmd[1] == "-c":
            return (0, self.driver) if self.driver else (1, "ModuleNotFoundError")
        if cmd[1:4] == ["-m", "pip", "install"]:
            self.driver = setup_db.pinned_driver()
            return 0, "installed"
        raise AssertionError("unexpected command %r" % cmd)

    def check(self, uri):
        parts = urlsplit(uri)
        running = any(c["running"] and c["port"] == parts.port for c in self.containers.values())
        if parts.hostname == "elsewhere":
            return "ok"
        if not running:
            return "down"
        return "ok" if self.users.get(VOLUME) == parts.password else "auth"

    def ensure_indexes(self, uri):
        new = uri not in self.indexed and not self.indexed
        self.indexed.add(uri)
        return new


class SetupCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = isolated_env(Path(self.tmp.name))
        self.machine = Machine()
        self.lines = []

    def setup(self, port=None, env=None):
        self.lines = []
        tool = setup_db.Setup(env or self.env, run=self.machine.run, check=self.machine.check,
                              ensure_indexes=self.machine.ensure_indexes,
                              port_free=lambda p: p not in self.machine.taken,
                              sleep=lambda s: None, log=self.lines.append)
        return tool.run(port=port)

    def fails(self, *phrases, **kwargs):
        with self.assertRaises(setup_db.SetupError) as caught:
            self.setup(**kwargs)
        for phrase in phrases:
            self.assertIn(phrase, str(caught.exception))
        self.assert_no_data_removed()
        return str(caught.exception)

    def assert_no_data_removed(self):
        for cmd in self.machine.commands:
            self.assertNotIn(cmd[1:3], (["volume", "rm"], ["volume", "prune"]), cmd)
            self.assertNotIn("prune", cmd)
            if cmd[1:2] == ["rm"]:
                self.assertFalse({"-v", "--volumes", "-fv", "-vf"} & set(cmd), cmd)

    def password(self):
        return urlsplit(memconfig.load(self.env)["uri"]).password

    def docker_runs(self):
        return [c for c in self.machine.commands if c[:2] == ["docker", "run"]]


class FreshAndRepeatTests(SetupCase):
    def test_a_fresh_setup_builds_everything(self):
        self.assertTrue(self.setup())
        run = self.docker_runs()[0]
        self.assertIn("127.0.0.1:27027:27017", run)
        self.assertIn(VOLUME + ":/data/db", run)
        self.assertEqual(run[-2:], [setup_db.IMAGE, "--auth"])
        self.assertIn("unless-stopped", run)
        self.assertGreaterEqual(len(self.password()), 24)
        self.assertEqual(self.machine.users[VOLUME], self.password())
        self.assertEqual(self.machine.driver, setup_db.pinned_driver())

    def test_the_password_is_in_no_output_and_no_argument(self):
        self.setup()
        password = self.password()
        self.assertNotIn(password, "\n".join(self.lines))
        for cmd in self.machine.commands:
            self.assertNotIn(password, " ".join(cmd))
        self.assertIn(password, "".join(self.machine.inputs))

    def test_running_again_changes_nothing_and_says_so(self):
        self.setup()
        before = (memconfig.load(self.env), len(self.docker_runs()), dict(self.machine.users))
        self.assertFalse(self.setup())
        self.assertIn("Nothing changed", "\n".join(self.lines))
        self.assertEqual((memconfig.load(self.env), len(self.docker_runs()), dict(self.machine.users)), before)

    def test_a_stopped_container_is_started(self):
        self.setup()
        self.machine.containers[NAME]["running"] = False
        self.assertTrue(self.setup())
        self.assertTrue(self.machine.containers[NAME]["running"])
        self.assertEqual(len(self.docker_runs()), 1)

    def test_a_removed_container_is_recreated_on_the_same_data(self):
        self.setup()
        password = self.password()
        del self.machine.containers[NAME]
        self.assertTrue(self.setup())
        self.assertEqual(self.password(), password)
        self.assertEqual(len(self.docker_runs()), 2)

    def test_the_port_can_be_chosen_and_changed_keeping_the_data(self):
        self.setup(port=28001)
        password = self.password()
        self.assertEqual(self.machine.containers[NAME]["port"], 28001)
        self.assertTrue(self.setup(port=28002))
        self.assertEqual(self.machine.containers[NAME]["port"], 28002)
        self.assertEqual(urlsplit(memconfig.load(self.env)["uri"]).port, 28002)
        self.assertEqual(self.password(), password)
        self.assertFalse(self.setup())  # the chosen port is remembered
        self.assert_no_data_removed()

    def test_a_half_finished_run_is_resumed(self):
        self.setup()
        del self.machine.users[VOLUME]  # stopped before the user was created
        self.assertTrue(self.setup())
        self.assertEqual(self.machine.users[VOLUME], self.password())

    def test_with_the_environment_variable_docker_is_left_alone(self):
        env = dict(self.env, AI_AGENCY_MEMORY_URI="mongodb://u:" + "pw-1@elsewhere:27017/db")
        self.machine.docker = "missing"
        self.setup(env=env)
        self.assertFalse([c for c in self.machine.commands if c[0] == "docker"])
        self.assertFalse(memconfig.config_path(env).exists())
        self.assertNotIn("pw-1", "\n".join(self.lines))


class StopTests(SetupCase):
    def test_docker_missing(self):
        self.machine.docker = "missing"
        self.fails("Docker is not installed")

    def test_docker_not_running(self):
        self.machine.docker = "stopped"
        self.fails("Docker does not answer")

    def test_a_taken_port(self):
        self.machine.taken.add(27027)
        self.fails("port 27027 is taken", "--port")
        self.assertTrue(self.setup(port=28005))

    def test_a_port_taken_between_the_check_and_the_run(self):
        self.machine.taken.add(27027)
        tool = setup_db.Setup(self.env, run=self.machine.run, check=self.machine.check,
                              ensure_indexes=self.machine.ensure_indexes, port_free=lambda p: True,
                              sleep=lambda s: None, log=self.lines.append)
        with self.assertRaises(setup_db.SetupError) as caught:
            tool.run()
        self.assertIn("port 27027 is taken", str(caught.exception))
        self.assertNotIn(NAME, self.machine.containers)  # the half-made container is cleared away
        self.assertIn(VOLUME, self.machine.volumes)
        self.assert_no_data_removed()

    def test_a_taken_port_when_starting_again(self):
        self.setup()
        self.machine.containers[NAME]["running"] = False
        self.machine.taken.add(27027)
        self.fails("port 27027 is taken")

    def test_changing_to_a_taken_port_keeps_the_working_container(self):
        self.setup()
        self.machine.taken.add(28009)
        self.fails("port 28009 is taken", port=28009)
        self.assertEqual(self.machine.containers[NAME]["port"], 27027)
        self.assertEqual(memconfig.load(self.env)["port"], 27027)

    def test_a_port_out_of_range(self):
        for port in (0, 65536, -1):
            self.fails("port", port=port)

    def test_a_volume_whose_password_is_lost(self):
        self.setup()
        memconfig.config_path(self.env).unlink()
        del self.machine.containers[NAME]
        self.fails(VOLUME, "password", "Nothing was deleted")
        self.assertIn(VOLUME, self.machine.volumes)
        self.assertFalse(memconfig.config_path(self.env).exists())

    def test_a_password_that_does_not_match_the_volume(self):
        self.setup()
        config = memconfig.load(self.env)
        config["uri"] = config["uri"].replace(self.password(), "x" * 32)
        memconfig.save(config, self.env)
        message = self.fails("does not match", "Nothing was deleted", "requires authentication")
        self.assertNotIn("x" * 32, message)

    def test_a_container_setup_did_not_create(self):
        self.machine.containers[NAME] = {"running": True, "port": 27027, "label": ""}
        self.fails("did not create")
        self.assertIn(NAME, self.machine.containers)

    def test_a_corrupt_config(self):
        path = memconfig.config_path(self.env)
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        self.fails(str(path))
        self.assertEqual(path.read_text(encoding="utf-8"), "{")

    def test_python_that_cannot_make_an_environment(self):
        self.machine.can_venv = False
        self.fails("python3-venv")
        self.assertFalse(self.docker_runs())


class PinTests(unittest.TestCase):
    def test_the_driver_and_the_image_are_pinned(self):
        self.assertRegex(setup_db.pinned_driver(), r"^\d+\.\d+\.\d+$")
        self.assertRegex(setup_db.IMAGE, r"^mongo:\d+\.\d+\.\d+$")
        lines = [line for line in setup_db.REQUIREMENTS.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertEqual(lines, ["pymongo==" + setup_db.pinned_driver()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
