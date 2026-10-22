#!/usr/bin/env python3
"""The shared test-driven-development skill: a red is a test that failed, never a load error or an empty run."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit.build import build
from tools.apkit.model import load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "_shared" / "skills" / "test-driven-development"
SCRIPT = SKILL / "scripts" / "tdd.py"
sys.path.insert(0, str(SCRIPT.parent))
import tdd  # noqa: E402

UNITTEST = "%s -m unittest discover -s tests -t ." % sys.executable


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False, cwd=cwd)


class ClassifyTest(unittest.TestCase):
    CASES = [
        # (runner output, exit code, state, failed_how)
        ("5 passed in 0.12s", 0, "GREEN", None),
        ("  10 passing (20ms)", 0, "GREEN", None),  # "10 passing" is not "0 passing"
        ("E       assert 1 == 2\nFAILED tests/test_cart.py::test_total - assert 1 == 2\n1 failed", 1,
         "RED", "assertion"),
        ("E       NameError: name 'total' is not defined\n    assert total([]) == 0\n"
         "FAILED tests/test_cart.py::test_total - NameError\n1 failed", 1, "RED", "exception"),
        ("ERROR collecting tests/test_cart.py\nImportError while importing test module\n"
         "!!! Interrupted: 1 error during collection !!!", 2, "ERRORED", None),
        ("no tests ran in 0.01s", 5, "ERRORED", None),
        ("FAIL: test_total (tests.test_cart.T)\nTraceback (most recent call last):\n"
         "AssertionError: 1 != 2\n\nRan 1 test\n\nFAILED (failures=1)", 1, "RED", "assertion"),
        ("\nRan 0 tests in 0.000s\n\nOK", 0, "ERRORED", None),
        ("Tests:       1 failed, 3 passed, 4 total\n  ● Cart › totals\n    expect(received).toBe(expected)", 1,
         "RED", "assertion"),
        ("No test files found, exiting with code 1", 1, "ERRORED", None),
        ("--- FAIL: TestTotal (0.00s)\n    cart_test.go:12: got 1, want 2\nFAIL", 1, "RED", "assertion"),
        ("./cart.go:3:2: undefined: Total\nFAIL\tshop/cart [build failed]", 1, "ERRORED", None),
        ("test cart::totals ... FAILED\n\nfailures:\n", 101, "RED", "assertion"),
        ("Traceback (most recent call last):\n  File \"x\"\nImportError: Start directory is not importable", 1,
         "ERRORED", None),  # the runner crashed: no failing test, so no verdict
        ("/usr/bin/python3: No module named pytest", 1, "UNUSABLE", None),
        ("sh: 1: vitest: not found", 127, "UNUSABLE", None),
    ]

    def test_each_runner_output_gets_its_state(self):
        for output, code, state, how in self.CASES:
            with self.subTest(output=output[:40]):
                result = tdd.classify(code, output)
                self.assertEqual(result["state"], state, result["reason"])
                if how:
                    self.assertEqual(result["failed_how"], how)

    def test_failing_tests_are_named(self):
        self.assertEqual(tdd.failing_names("FAILED tests/test_cart.py::test_total - x\nFAILED (failures=1)"),
                         ["tests/test_cart.py::test_total"])
        self.assertEqual(tdd.failing_names("--- FAIL: TestTotal (0.00s)"), ["TestTotal"])
        self.assertEqual(tdd.failing_names("✖ adds (1.2ms)\n✖ failing tests:\n✖ adds (1.2ms)"), ["adds"])


class RealRunTest(unittest.TestCase):
    """Real unittest projects, run through the CLI the way an agent runs a cycle."""

    TEST = textwrap.dedent("""\
        import unittest
        %s
        class CartTest(unittest.TestCase):
            def test_total(self):
                self.assertEqual(%s, 3)
        """)

    def project(self, tmp, name, calc, test):
        root = Path(tmp) / name
        (root / "tests").mkdir(parents=True)
        (root / "tests" / "__init__.py").write_text("")
        (root / "calc.py").write_text(calc)
        if test is not None:
            (root / "tests" / "test_calc.py").write_text(test)
        return root

    def check(self, root, *extra):
        result = run("check", "--cmd", UNITTEST, "--json", *extra, cwd=root)
        return result.returncode, json.loads(result.stdout)

    def test_the_four_outcomes_of_a_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "green": ("def add(a, b):\n    return a + b\n", self.TEST % ("from calc import add", "add(1, 2)"),
                          "GREEN", None),
                "red": ("def add(a, b):\n    return 0\n", self.TEST % ("from calc import add", "add(1, 2)"),
                        "RED", "assertion"),
                "missing": ("", self.TEST % ("import calc", "calc.add(1, 2)"), "RED", "exception"),
                "broken": ("", self.TEST % ("from nosuchmodule import add", "add(1, 2)"), "ERRORED", None),
                "empty": ("x = 1\n", None, "ERRORED", None),
            }
            for name, (calc, test, state, how) in cases.items():
                with self.subTest(name):
                    code, result = self.check(self.project(tmp, name, calc, test))
                    self.assertEqual(result["state"], state, result["reason"])
                    self.assertEqual(code, tdd.EXIT[state])
                    if how:
                        self.assertEqual(result["failed_how"], how)
                        self.assertEqual(result["failing"], ["test_total (tests.test_calc.CartTest)"])

    def test_expect_gates_each_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            red = self.project(tmp, "red", "def add(a, b):\n    return 0\n",
                               self.TEST % ("from calc import add", "add(1, 2)"))
            self.assertEqual(self.check(red, "--expect", "red")[0], 0, "red earned")
            code, result = self.check(red, "--expect", "green")
            self.assertEqual(code, 1)
            self.assertIn("never edit the test", result["advice"])
            green = self.project(tmp, "green", "def add(a, b):\n    return a + b\n",
                                 self.TEST % ("from calc import add", "add(1, 2)"))
            code, result = self.check(green, "--expect", "red")
            self.assertEqual(code, 1, "a test that passes at once specifies nothing")
            self.assertIn("not collected", result["advice"])
            empty = self.project(tmp, "empty", "x = 1\n", None)
            self.assertEqual(self.check(empty, "--expect", "red")[0], 3, "an empty run is never a red")

    def test_no_command_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run("check", "--json", cwd=tmp)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["state"], "UNUSABLE")


class DetectTest(unittest.TestCase):
    def test_reads_what_the_repo_declares_and_invents_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(tdd.detect(root), [])
            (root / "package.json").write_text(json.dumps({"scripts": {"test": "echo \"Error: no test specified\""}}))
            self.assertEqual(tdd.detect(root), [], "npm's placeholder is not a test command")
            (root / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}))
            (root / "go.mod").write_text("module shop\n")
            self.assertEqual(tdd.detect(root), ["npm test --silent", "go test ./..."])
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
            self.assertIn("python -m pytest -q", tdd.detect(root))


class BundleTest(unittest.TestCase):
    def test_skill_is_spec_shaped(self):
        head = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
        self.assertIn("name: test-driven-development", head)
        description = next(l for l in head.splitlines() if l.startswith("description:"))
        self.assertLessEqual(len(description) - len("description: "), 1024)

    def test_developer_ships_the_skill_with_its_script(self):
        plugin = load_plugin(ROOT / "plugins" / "developer")
        self.assertIn("test-driven-development", [s.name for s in plugin.skills])
        target = {t.id: t for t in load_targets(ROOT / "targets")}["claude-code"]
        with tempfile.TemporaryDirectory() as tmp:
            build(plugin, target, Path(tmp))
            bundle = Path(tmp) / "claude-code" / "developer" / "skills" / "test-driven-development"
            self.assertTrue((bundle / "scripts" / "tdd.py").is_file())
            self.assertTrue((bundle / "references" / "cycle.md").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
