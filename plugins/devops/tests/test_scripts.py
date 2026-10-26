#!/usr/bin/env python3
"""Smoke tests for the scripts the devops plugin ships."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "ci-setup" / "scripts"
TRIAGE = PLUGIN / "skills" / "pipeline-triage" / "scripts" / "triage.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TRIAGE.parent))
import scaffold  # noqa: E402
import stack_scan  # noqa: E402
import triage  # noqa: E402


def run(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, check=False, cwd=cwd)


def project(tmp, name, files):
    root = Path(tmp) / name
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if isinstance(text, str) else json.dumps(text))
    root.mkdir(parents=True, exist_ok=True)
    return root


VITE = {"package.json": {"name": "shop", "scripts": {"build": "vite build", "test": "vitest run", "lint": "eslint ."},
                         "devDependencies": {"vite": "^7"}},
        "package-lock.json": "{}", ".nvmrc": "v22\n"}
FASTAPI = {"requirements.txt": "fastapi\nuvicorn\npytest\n", "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n"}


class StackScanTest(unittest.TestCase):
    def test_each_stack_gets_its_kind_and_commands(self):
        cases = {
            "vite": (VITE, "static", "vite", {"build": "npm run build", "output_dir": "dist", "node_version": "22",
                                              "install": "npm ci"}),
            "next-export": ({"package.json": {"scripts": {"build": "next build"}, "dependencies": {"next": "15"}},
                             "pnpm-lock.yaml": "", "next.config.mjs": "export default { output: 'export' }\n"},
                            "static", "next", {"output_dir": "out", "build": "pnpm run build",
                                               "install": "pnpm install --frozen-lockfile"}),
            "next-server": ({"package.json": {"scripts": {"build": "next build", "start": "next start"},
                                              "dependencies": {"next": "15"}}, "yarn.lock": ""},
                            "server", "next", {"start": "yarn start"}),
            "express": ({"package.json": {"scripts": {"start": "node server.js",
                                                      "test": "echo \"Error: no test specified\" && exit 1"},
                                          "dependencies": {"express": "5"}}, "package-lock.json": "{}"},
                        "server", "express", {"start": "npm run start", "test": None}),
            "fastapi": (FASTAPI, "server", "fastapi",
                        {"start": "uvicorn app.main:app --host 0.0.0.0 --port $PORT", "test": "pytest",
                         "install": "pip install -r requirements.txt"}),
            "django": ({"pyproject.toml": "[project]\ndependencies = [\"django\", \"gunicorn\"]\n", "uv.lock": "",
                        "manage.py": "", "shop/wsgi.py": ""},
                       "server", "django", {"start": "uv run gunicorn shop.wsgi --bind 0.0.0.0:$PORT",
                                            "install": "uv sync --frozen"}),
            "plain": ({"index.html": "<h1>hi</h1>"}, "static", "plain", {"output_dir": "."}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, (files, kind, framework, expected) in cases.items():
                with self.subTest(name):
                    facts = stack_scan.scan(project(tmp, name, files))
                    self.assertEqual((facts["kind"], facts["framework"]), (kind, framework), facts)
                    for key, value in expected.items():
                        self.assertEqual(facts.get(key), value, key)

    def test_says_what_it_cannot_tell_and_exits_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = project(tmp, "empty", {"notes.txt": "x"})
            result = run(SCRIPTS / "stack_scan.py", empty)
            self.assertEqual(result.returncode, 3)
            self.assertIn("UNKNOWN", result.stdout)
            flask = stack_scan.scan(project(tmp, "flask", {"requirements.txt": "flask\n"}))
            self.assertEqual(flask["kind"], "server")
            self.assertTrue(any("start command is unknown" in u for u in flask["unknowns"]))
            self.assertIsNone(flask.get("start"))


class ScaffoldTest(unittest.TestCase):
    def scaffold(self, root, *args):
        return run(SCRIPTS / "scaffold.py", *args, "--root", root)

    def test_ci_runs_the_repos_own_commands_with_least_privilege(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "vite", VITE)
            self.assertEqual(self.scaffold(root, "ci", "--branch", "main").returncode, 0)
            text = (root / ".github" / "workflows" / "ci.yml").read_text()
            for line in ("permissions:\n  contents: read", "run: npm ci", "run: npm run lint", "run: npm run test",
                         "run: npm run build", "branches: [main]", "timeout-minutes:", "cancel-in-progress: true",
                         'node-version: "22"', "cache: npm"):
                self.assertIn(line, text)
            self.assertNotIn("pull_request_target", text)
            self.assertLess(text.index("npm run lint"), text.index("npm run test"))

    def test_cloudflare_preview_publishes_the_contract_and_skips_forks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "vite", VITE)
            result = self.scaffold(root, "preview", "--project", "shop")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / ".github" / "workflows" / "preview.yml").read_text()
            self.assertIn("types: [opened, synchronize, reopened, closed]", text)
            self.assertIn("pages deploy dist --project-name=shop", text)
            self.assertIn("preview-pr-${pr.number}", text)
            self.assertIn("environment_url: url", text)
            self.assertIn("state: 'inactive'", text)
            self.assertIn(scaffold.MARKER, text)
            self.assertNotIn("pull_request_target", text)
            same = "github.event.pull_request.head.repo.full_name == github.repository"
            self.assertIn("if: github.event.action != 'closed' && %s" % same, text)
            self.assertIn("!(%s)" % same, text)
            # secrets by name only, and only the two the deploy needs
            self.assertEqual(sorted(set(re.findall(r"secrets\.([A-Z_]+)", text))),
                             ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"])
            self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", result.stdout)

    def test_render_blueprint_turns_on_pr_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "api", FASTAPI)
            result = self.scaffold(root, "preview")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / "render.yaml").read_text()
            for line in ("runtime: python", "plan: free", "startCommand: uvicorn app.main:app",
                         "previews:\n      generation: automatic"):
                self.assertIn(line, text)
            self.assertFalse((root / ".github").exists(), "Render needs no workflow")

    def test_refuses_to_guess_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            flask = project(tmp, "flask", {"requirements.txt": "flask\n"})
            result = self.scaffold(flask, "preview")
            self.assertEqual(result.returncode, 3)
            self.assertIn("start", result.stderr)
            self.assertEqual(self.scaffold(flask, "preview", "--start", "gunicorn app:app").returncode, 0)
            server = project(tmp, "server", FASTAPI)
            self.assertEqual(self.scaffold(server, "preview", "--provider", "cloudflare-pages",
                                           "--project", "x").returncode, 3, "Pages can't host a server")
            vite = project(tmp, "vite", VITE)
            workflow = vite / ".github" / "workflows" / "ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: mine\n")
            self.assertEqual(self.scaffold(vite, "ci").returncode, 1)
            self.assertEqual(workflow.read_text(), "name: mine\n")

    def test_yaml_values_that_would_misparse_are_quoted(self):
        self.assertEqual(scaffold.scalar("npm run build"), "npm run build")
        self.assertEqual(scaffold.scalar('echo "a: b"'), '"echo \\"a: b\\""')
        self.assertTrue(scaffold.scalar("*.js").startswith('"'))

    @unittest.skipUnless(shutil.which("actionlint"), "actionlint not installed")
    def test_actionlint_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "vite", VITE)
            self.scaffold(root, "ci")
            self.scaffold(root, "preview", "--project", "shop")
            files = sorted(str(f) for f in (root / ".github" / "workflows").glob("*.yml"))
            result = subprocess.run(["actionlint", "-shellcheck=", "-pyflakes=", *files], cwd=root,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


LOG = textwrap.dedent("""\
    2026-10-22T12:57:06.26Z ##[group]Run actions/checkout@v7
    2026-10-22T12:57:06.27Z ##[endgroup]
    2026-10-22T12:57:08.74Z ##[group]Run python -m unittest
    2026-10-22T12:57:10.29Z test_ok (t.T.test_ok) ... ok
    2026-10-22T12:57:36.15Z FAIL: test_total (t.CartTest.test_total)
    2026-10-22T12:57:36.16Z AssertionError: 1 != 3
    2026-10-22T12:57:36.17Z FAILED (failures=1)
    2026-10-22T12:57:36.64Z ##[error]Process completed with exit code 1.
    2026-10-22T12:57:36.70Z ##[group]Run actions/upload-artifact@v4
    """)


class TriageTest(unittest.TestCase):
    CASES = [
        ("FAIL: test_total (t.CartTest.test_total)\nAssertionError: 1 != 3", "test"),
        ("Tests:  2 failed, 10 passed, 12 total", "test"),
        ("src/cart.ts(3,7): error TS2322: Type 'string' is not assignable", "build"),
        ("/repo/src/a.js\n  3:1  error  'x' is not defined  no-undef\n\n✖ 1 problem (1 error, 0 warnings)", "lint"),
        ("npm error code ERESOLVE\nnpm error ERESOLVE unable to resolve dependency tree", "dependency"),
        ("ERR_PNPM_OUTDATED_LOCKFILE Cannot install with frozen-lockfile", "dependency"),
        ("##[error]Input required and not supplied: apiToken", "workflow"),
        ("HttpError: Resource not accessible by integration", "workflow"),
        ("##[error]The runner has received a shutdown signal.", "infra"),
        ("Error: connect ETIMEDOUT 140.82.112.3:443", "infra"),
        ("something odd happened\n##[error]Process completed with exit code 2.", "unknown"),
    ]

    def test_each_failure_gets_its_category_and_owner(self):
        for text, category in self.CASES:
            with self.subTest(text[:40]):
                result = triage.classify(text.splitlines())
                self.assertEqual(result["category"], category, result)
                self.assertEqual(result["owner"], triage.OWNER[category])
                self.assertTrue(result["evidence"])

    def test_cuts_the_failed_step_out_of_a_real_log(self):
        result = triage.triage_log(LOG)
        self.assertEqual(result["step"], "python -m unittest")
        self.assertEqual(result["category"], "test")
        self.assertEqual(result["evidence"][0], "FAIL: test_total (t.CartTest.test_total)")
        self.assertFalse(any(line.endswith("... ok") for line in result["evidence"]))

    def test_offline_log_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "job.log"
            path.write_text(LOG)
            result = run(TRIAGE, "--log", path, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)[0]["jobs"][0]["owner"], "developer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
