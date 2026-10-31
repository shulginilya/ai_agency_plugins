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
NEXT_EXPORT = {"package.json": {"scripts": {"build": "next build", "start": "next start"}, "dependencies": {"next": "16"}},
               "pnpm-lock.yaml": "", "next.config.ts": "export default { output: \"export\" };\n"}
NEXT_SERVER_CONFIG = "export default {};\n"  # output: "export" dropped, e.g. for a database


def pkg(deps, scripts=None, dev=None):
    return {"package.json": {"scripts": dict({"build": "x build", "start": "x start"}, **(scripts or {})),
                             "dependencies": deps, "devDependencies": dev or {}}, "package-lock.json": "{}"}


# Each stack the scan knows, before and after the change that makes it outgrow a static host:
# (before, after: files written over it, the kind now, words the error's reason must carry)
FLIPS = {
    "next": (NEXT_EXPORT, {"next.config.ts": NEXT_SERVER_CONFIG}, "server", "output: 'export'"),
    "sveltekit": (pkg({"@sveltejs/kit": "2", "@sveltejs/adapter-static": "3"}),
                  pkg({"@sveltejs/kit": "2", "@sveltejs/adapter-node": "5"}), "server", "adapter-static"),
    "astro": (dict(pkg({"astro": "5"}), **{"astro.config.mjs": "export default {}\n"}),
              {"astro.config.mjs": "export default { output: 'server' }\n"}, "server", "server adapter"),
    "nuxt": (pkg({"nuxt": "4"}, {"generate": "nuxt generate"}), pkg({"nuxt": "4"}), "server", "generate script"),
    "vite": (pkg({"react": "19"}, dev={"vite": "7"}), pkg({"react": "19", "express": "5"}, dev={"vite": "7"}),
             "static+api", "vite plus express"),
    "plain": ({"index.html": "<h1>hi</h1>"}, FASTAPI, "server", "fastapi"),
}


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


class ExpectTest(unittest.TestCase):
    """stack_scan.py --expect: the per-PR check that the stack still fits its preview host."""

    def expect(self, root, kind, host):
        return run(SCRIPTS / "stack_scan.py", root, "--expect", kind, "--host", host)

    def test_unchanged_kind_passes_quietly(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, files, kind, host in (("vite", VITE, "static", "cloudflare-pages"),
                                            ("next", NEXT_EXPORT, "static", "cloudflare-pages"),
                                            ("api", FASTAPI, "server", "render")):
                with self.subTest(name):
                    result = self.expect(project(tmp, name, files), kind, host)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn("::error", result.stdout)
                    self.assertNotIn(stack_scan.DRIFT, result.stdout)

    def test_static_to_server_fails_naming_the_new_kind_and_the_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "next", NEXT_EXPORT)
            (root / "next.config.ts").write_text(NEXT_SERVER_CONFIG)
            result = self.expect(root, "static", "cloudflare-pages")
            self.assertEqual(result.returncode, 4)
            line = result.stdout.strip()
            self.assertTrue(line.startswith("::error title=Preview host no longer fits the stack::"), line)
            for part in ("devops:stack-changed recorded=static now=server host=cloudflare-pages",
                         "output: 'export'", "needs Render", "/devops:preview"):
                self.assertIn(part, line)

    def test_server_to_static_fails_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "api", dict(FASTAPI, **VITE))  # a package.json frontend took over the root
            result = self.expect(root, "server", "render")
            self.assertEqual(result.returncode, 4)
            self.assertIn("recorded=server now=static host=render", result.stdout)
            self.assertIn("needs Cloudflare Pages", result.stdout)

    def test_every_known_stack_that_outgrows_static_hosting_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, (before, after, now, reason) in FLIPS.items():
                with self.subTest(name):
                    root = project(tmp, name, before)
                    self.assertEqual(self.expect(root, "static", "cloudflare-pages").returncode, 0,
                                     "%s starts static" % name)
                    for rel, text in after.items():
                        (root / rel).parent.mkdir(parents=True, exist_ok=True)
                        (root / rel).write_text(text if isinstance(text, str) else json.dumps(text))
                    result = self.expect(root, "static", "cloudflare-pages")
                    self.assertEqual(result.returncode, 4, result.stdout)
                    self.assertIn("recorded=static now=%s " % now, result.stdout)
                    self.assertIn(reason, result.stdout)
                    self.assertIn("/devops:preview", result.stdout)

    def test_a_dev_only_server_is_not_an_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "vite", pkg({"react": "19"}, dev={"vite": "7", "express": "5"}))
            self.assertEqual(self.expect(root, "static", "cloudflare-pages").returncode, 0)

    def test_the_same_host_is_not_called_a_new_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "next", NEXT_EXPORT)
            (root / "next.config.ts").write_text(NEXT_SERVER_CONFIG)
            result = self.expect(root, "static", "render")  # a Render static site that became a server
            self.assertEqual(result.returncode, 4)
            self.assertNotIn("needs Render", result.stdout)
            self.assertIn("The host stays Render", result.stdout)
            self.assertIn("rewrites this preview's files for kind=server", result.stdout)

    def test_a_scan_that_cannot_tell_only_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.expect(project(tmp, "empty", {"notes.txt": "x"}), "static", "cloudflare-pages")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout.startswith("::warning"), result.stdout)


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
            # secrets by name only: the two the deploy needs, and the zone for a review domain
            self.assertEqual(sorted(set(re.findall(r"secrets\.([A-Z_]+)", text))),
                             ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID"])
            self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", result.stdout)
            self.assertIn("gh secret set CLOUDFLARE_ZONE_ID -R <owner>/<repo>   # only with a review domain",
                          result.stdout)
            # the review domain is opt-in, by a variable, and the ticket comment needs issues: write
            self.assertIn("REVIEW_DOMAIN: ${{ vars.REVIEW_DOMAIN }}", text)
            self.assertEqual(text.count("if: env.REVIEW_DOMAIN != ''"), 2)
            self.assertIn("  issues: write", text)
            self.assertIn("steps.review.outputs.url ||", text)

    def test_render_blueprint_turns_on_pr_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "api", FASTAPI)
            result = self.scaffold(root, "preview")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / "render.yaml").read_text()
            for line in ("runtime: python", "plan: free", "startCommand: uvicorn app.main:app",
                         "previews:\n      generation: automatic"):
                self.assertIn(line, text)
            workflows = sorted(p.name for p in (root / ".github" / "workflows").iterdir())
            self.assertEqual(workflows, ["review-link.yml"], "Render deploys itself; only the ticket comment is ours")
            ticket = (root / ".github" / "workflows" / "review-link.yml").read_text()
            self.assertNotIn("secrets.", ticket)
            self.assertIn("deployment_status:", ticket)
            # the ticket job still only marks links down on close; pushes run the stack check
            self.assertIn("github.event_name == 'pull_request' && github.event.action == 'closed'", ticket)
            self.assertIn("if: github.event_name == 'pull_request' && github.event.action != 'closed'", ticket)

    def test_preview_files_record_their_kind_and_check_it_on_every_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            vite = project(tmp, "vite", VITE)
            self.assertEqual(self.scaffold(vite, "preview", "--project", "shop").returncode, 0)
            text = (vite / ".github" / "workflows" / "preview.yml").read_text()
            self.assertTrue(text.startswith("# devops:preview kind=static provider=cloudflare-pages\n"))
            check = "run: python3 .github/devops/stack_scan.py . --expect static --host cloudflare-pages"
            self.assertIn(check, text)
            self.assertLess(text.index("actions/checkout"), text.index(check))
            self.assertLess(text.index(check), text.index("run: npm ci"), "fail before spending a build")
            copied = vite / ".github" / "devops" / "stack_scan.py"
            source = (SCRIPTS / "stack_scan.py").read_text()
            self.assertTrue(copied.read_text().startswith("#!/usr/bin/env python3\n# Copied by the devops plugin"))
            self.assertEqual(copied.read_text().replace(scaffold.SCANNER_HEADER, ""), source)
            for skip in ("# flake8: noqa", "# ruff: noqa", "# fmt: off"):  # the repo's own lint stays green
                self.assertIn(skip + "\n", scaffold.SCANNER_HEADER)
            self.assertEqual(run(copied, vite, "--expect", "static", "--host", "cloudflare-pages").returncode, 0,
                             "the copy runs on its own, without the plugin")

            api = project(tmp, "api", FASTAPI)
            self.assertEqual(self.scaffold(api, "preview").returncode, 0)
            self.assertTrue((api / "render.yaml").read_text().startswith("# devops:preview kind=server provider=render\n"))
            review = (api / ".github" / "workflows" / "review-link.yml").read_text()
            self.assertTrue(review.startswith("# devops:preview kind=server provider=render\n"))
            self.assertIn("run: python3 .github/devops/stack_scan.py . --expect server --host render", review)
            self.assertTrue((api / ".github" / "devops" / "stack_scan.py").is_file())

    def check_passes(self, root, workflow):
        """Run the copied scanner exactly as the written workflow does, and assert it is green."""
        line = next(l for l in (root / ".github" / "workflows" / workflow).read_text().splitlines()
                    if "--expect" in l)
        args = line.split("python3 ", 1)[1].split()
        result = run(root / args[0], root, *args[2:])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("::error", result.stdout)

    def test_switching_host_replaces_the_old_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "next", NEXT_EXPORT)
            self.assertEqual(self.scaffold(root, "preview", "--project", "obs").returncode, 0)
            (root / "next.config.ts").write_text(NEXT_SERVER_CONFIG)
            dry = self.scaffold(root, "preview", "--dry-run")
            self.assertIn("would remove .github/workflows/preview.yml", dry.stdout)
            self.assertTrue((root / ".github" / "workflows" / "preview.yml").exists(), "a dry run removes nothing")
            result = self.scaffold(root, "preview")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("removed .github/workflows/preview.yml", result.stdout)
            self.assertIn("onrender.com", result.stdout)
            self.assertEqual(sorted(p.name for p in (root / ".github" / "workflows").iterdir()), ["review-link.yml"])
            self.assertTrue((root / "render.yaml").read_text().startswith("# devops:preview kind=server"))
            self.check_passes(root, "review-link.yml")

            # and back: the Render files go, the Pages workflow comes
            (root / "next.config.ts").write_text(NEXT_EXPORT["next.config.ts"])
            result = self.scaffold(root, "preview", "--project", "obs")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "render.yaml").exists())
            self.assertEqual(sorted(p.name for p in (root / ".github" / "workflows").iterdir()), ["preview.yml"])
            self.check_passes(root, "preview.yml")

    def test_a_new_kind_on_the_same_host_rewrites_its_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "next", NEXT_EXPORT)
            self.assertEqual(self.scaffold(root, "preview", "--provider", "render").returncode, 0)
            self.assertTrue((root / "render.yaml").read_text().startswith("# devops:preview kind=static provider=render"))
            (root / "next.config.ts").write_text(NEXT_SERVER_CONFIG)
            result = self.scaffold(root, "preview")  # no --force: these are the script's own files
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("rewrote render.yaml (it was set up for kind=static)", result.stdout)
            blueprint = (root / "render.yaml").read_text()
            self.assertTrue(blueprint.startswith("# devops:preview kind=server provider=render"))
            self.assertIn("runtime: node", blueprint)
            self.check_passes(root, "review-link.yml")

    def test_a_static_frontend_that_grows_an_api_keeps_pages_and_says_where_the_api_goes(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after = FLIPS["vite"][:2]
            root = project(tmp, "vite", before)
            self.assertEqual(self.scaffold(root, "preview", "--project", "shop").returncode, 0)
            root.joinpath("package.json").write_text(json.dumps(after["package.json"]))
            result = self.scaffold(root, "preview", "--project", "shop")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("rewrote .github/workflows/preview.yml (it was set up for kind=static)", result.stdout)
            self.assertIn("the API (express) isn't previewed by this workflow", result.stdout)
            self.check_passes(root, "preview.yml")

    def test_a_file_it_did_not_record_is_still_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "api", FASTAPI)
            mine = root / "render.yaml"
            mine.write_text("services: []  # the team's own\n")
            self.assertEqual(self.scaffold(root, "preview").returncode, 1)
            self.assertEqual(mine.read_text(), "services: []  # the team's own\n")

    def test_never_removes_files_it_did_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "vite", dict(VITE, **{"render.yaml": "services: []  # the team's own\n"}))
            self.assertEqual(self.scaffold(root, "preview", "--project", "shop").returncode, 0)
            self.assertEqual((root / "render.yaml").read_text(), "services: []  # the team's own\n")

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


# A fake GitHub and Cloudflare for the workflows' github-script steps: run each
# script under node, record what it writes, and check QA reads it back.
NODE_HARNESS = r"""
const fs = require('fs');
const [scriptFile, scenarioFile] = process.argv.slice(2);
const sc = JSON.parse(fs.readFileSync(scenarioFile, 'utf8'));
const calls = [], outputs = {}, notices = [];
let failed = null;
const comments = sc.comments || {};
const github = {
  graphql: async () => ({ repository: { pullRequest: { closingIssuesReferences: { nodes: sc.closes } } } }),
  paginate: async (fn, args) => fn === github.rest.issues.listComments ? (comments[args.issue_number] || []) : [],
  rest: {
    issues: {
      listComments: () => {},
      createComment: async a => { calls.push(['createComment', a]); },
      updateComment: async a => { calls.push(['updateComment', a]); },
    },
    repos: {
      createDeployment: async a => { calls.push(['createDeployment', a]); return { data: { id: 7 } }; },
      createDeploymentStatus: async a => { calls.push(['createDeploymentStatus', a]); },
      listDeployments: () => {},
      listPullRequestsAssociatedWithCommit: async () => ({ data: sc.prs || [] }),
    },
  },
};
const core = { setOutput: (k, v) => { outputs[k] = v; }, setFailed: m => { failed = m; }, notice: m => notices.push(m) };
const context = Object.assign({ repo: { owner: 'me', repo: 'shop' }, serverUrl: 'https://github.com', runId: 9 },
                              sc.context);
global.fetch = async (url, init) => {
  calls.push(['cf', init.method, url.replace('https://api.cloudflare.com/client/v4', ''), init.body ? JSON.parse(init.body) : null]);
  const exists = (sc.cf_exists || []).some(p => url.endsWith(p));
  const ok = init.method !== 'GET' || exists;
  const result = url.includes('dns_records?') ? (sc.dns || []) : {};
  return { ok, json: async () => ({ success: ok, result }) };
};
Object.assign(process.env, sc.env || {});
const body = fs.readFileSync(scriptFile, 'utf8');
(async () => {
  await (new Function('github', 'context', 'core', 'require', `return (async () => {\n${body}\n})();`))(github, context, core, require);
  console.log(JSON.stringify({ calls, outputs, notices, failed }));
})().catch(e => { console.log(JSON.stringify({ error: String(e.stack || e) })); });
"""

PR = {"number": 43, "head": {"ref": "79-Feat/Review_Links", "sha": "abc1234def", "repo": {"full_name": "me/shop"}},
      "merged": False}
QA_SCRIPTS = PLUGIN.parent / "qa" / "skills" / "acceptance-testing" / "scripts"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class WorkflowScriptTest(unittest.TestCase):
    """The github-script steps, run for real against a fake GitHub and Cloudflare."""

    def steps(self, root, workflow):
        """Each named step's env and script, read from the YAML as written (no YAML library in CI)."""
        found, current, block = {}, None, None
        for line in (root / ".github" / "workflows" / workflow).read_text().splitlines():
            if line.startswith("      - name: "):
                current = found.setdefault(line[len("      - name: "):], {"env": {}, "with": {}})
                block = None
            elif current is None:
                continue
            elif line == "        env:":
                block = "env"
            elif line == "          script: |":
                block, current["with"]["script"] = "script", ""
            elif block == "script" and (line.startswith(" " * 12) or not line.strip()):
                current["with"]["script"] += line[12:] + "\n"
            elif block == "env" and line.startswith(" " * 10) and ": " in line:
                key, value = line.strip().split(": ", 1)
                current["env"][key] = value
            elif line.strip() and not line.startswith(" " * 10):
                block = None
        return found

    def node(self, tmp, script, scenario):
        js, sc, harness = Path(tmp, "step.js"), Path(tmp, "scenario.json"), Path(tmp, "harness.js")
        js.write_text(script)
        sc.write_text(json.dumps(scenario))
        harness.write_text(NODE_HARNESS)
        done = subprocess.run(["node", str(harness), str(js), str(sc)], capture_output=True, text=True, check=False)
        out = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out

    def cloudflare(self, tmp):
        root = project(tmp, "vite", VITE)
        self.assertEqual(run(SCRIPTS / "scaffold.py", "preview", "--project", "shop", "--root", root).returncode, 0)
        return self.steps(root, "preview.yml")

    def test_the_review_domain_step_adds_the_pages_domain_and_a_cname_to_the_branch_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            step = self.cloudflare(tmp)["Serve it on the review domain"]
            env = dict(step["env"], REVIEW_DOMAIN="review.example.dev", REVIEW_SLUG="Shop", PAGES_PROJECT="shop",
                       CLOUDFLARE_ACCOUNT_ID="acc", CLOUDFLARE_ZONE_ID="zone", CLOUDFLARE_API_TOKEN="t")
            out = self.node(tmp, step["with"]["script"], {"env": env, "context": {"payload": {"pull_request": PR}}})
            host = "79-feat-review-links.shop.review.example.dev"
            self.assertIsNone(out["failed"])
            self.assertEqual(out["outputs"], {"url": "https://" + host})
            writes = [c for c in out["calls"] if c[1] != "GET"]
            self.assertEqual(writes[0][1:3], ["POST", "/accounts/acc/pages/projects/shop/domains"])
            self.assertEqual(writes[0][3], {"name": host})
            self.assertEqual(writes[1][1:3], ["POST", "/zones/zone/dns_records"])
            self.assertEqual((writes[1][3]["content"], writes[1][3]["proxied"]), ("pr-43.shop.pages.dev", True))

            env["ACTION"] = "down"
            out = self.node(tmp, step["with"]["script"], {"env": env, "context": {"payload": {"pull_request": PR}},
                                                          "dns": [{"id": "rec1"}]})
            deletes = [c[2] for c in out["calls"] if c[1] == "DELETE"]
            self.assertEqual(deletes, ["/accounts/acc/pages/projects/shop/domains/" + host, "/zones/zone/dns_records/rec1"])

    def test_the_ticket_comment_the_workflow_writes_is_the_one_qa_reads(self):
        sys.path.insert(0, str(QA_SCRIPTS))
        import review_link  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            steps = self.cloudflare(tmp)
            link = "https://79-feat-review-links.shop.review.example.dev"
            scenario = {"env": {"PREVIEW_URL": link}, "context": {"payload": {"pull_request": PR}},
                        "closes": [{"number": 42, "repository": {"nameWithOwner": "me/shop"}},
                                   {"number": 5, "repository": {"nameWithOwner": "other/repo"}}]}
            out = self.node(tmp, steps["Publish the review link"]["with"]["script"], scenario)
            posted = [c[1] for c in out["calls"] if c[0] == "createComment" and c[1]["issue_number"] == 42]
            self.assertEqual(len(posted), 1, out["calls"])
            self.assertTrue(any("other/repo" in n for n in out["notices"]), "a ticket in another repo is skipped, said")
            body = posted[0]["body"]
            seen = review_link.decide("", [{"body": body, "created_at": "2026-10-26T01:00:00Z", "url": "c1"}],
                                      commit="abc1234def", domain="review.example.dev")
            self.assertEqual((seen["action"], seen["link"], seen["serves"]), ("test", link, "abc1234def"))
            self.assertEqual(review_link.decide("", [{"body": body, "created_at": "x", "url": "c1"}],
                                                commit="fff9999")["action"], "wait")

            # the next deploy edits that comment instead of adding one; closing the PR marks it down
            mine = {"id": 11, "user": {"type": "Bot"}, "body": body}
            scenario["comments"] = {"42": [mine]}
            out = self.node(tmp, steps["Publish the review link"]["with"]["script"], scenario)
            on_ticket = [c[0] for c in out["calls"] if c[0] == "createComment" and c[1]["issue_number"] == 42]
            on_ticket += [c[0] for c in out["calls"] if c[0] == "updateComment" and c[1]["comment_id"] == 11]
            self.assertEqual(on_ticket, ["updateComment"])
            out = self.node(tmp, steps["Take the review link down"]["with"]["script"], scenario)
            down = [c[1]["body"] for c in out["calls"] if c[0] == "updateComment" and c[1]["comment_id"] == 11]
            self.assertEqual(len(down), 1)
            self.assertEqual(review_link.decide("", [{"body": down[0], "created_at": "x", "url": "c1"}])["action"], "none")

    def test_render_deploys_reach_the_tickets_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "api", FASTAPI)
            self.assertEqual(run(SCRIPTS / "scaffold.py", "preview", "--root", root).returncode, 0)
            script = self.steps(root, "review-link.yml")["Post the review link to the PR's tickets"]["with"]["script"]
            scenario = {"context": {"eventName": "deployment_status", "payload": {
                "deployment": {"sha": "abc1234def"},
                "deployment_status": {"environment_url": "https://api-pr-43.onrender.com", "log_url": "L"}}},
                "prs": [{"number": 43, "state": "open"}, {"number": 40, "state": "closed"}],
                "closes": [{"number": 42, "repository": {"nameWithOwner": "me/shop"}}]}
            out = self.node(tmp, script, scenario)
            posted = [c[1] for c in out["calls"] if c[0] == "createComment"]
            self.assertEqual([p["issue_number"] for p in posted], [42])
            self.assertIn("link=https://api-pr-43.onrender.com commit=abc1234def pr=43 state=live", posted[0]["body"])


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
        ("##[error]devops:stack-changed recorded=static now=server host=cloudflare-pages. This repo's previews"
         "\n##[error]Process completed with exit code 4.", "stack"),
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

    def test_a_stack_change_is_devops_job_not_a_code_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "next", NEXT_EXPORT)
            (root / "next.config.ts").write_text(NEXT_SERVER_CONFIG)
            check = run(SCRIPTS / "stack_scan.py", root, "--expect", "static", "--host", "cloudflare-pages")
            # how Actions logs it: the workflow command becomes ##[error], then the step's exit code
            log = "\n".join(["##[group]Run python3 .github/devops/stack_scan.py . --expect static",
                             check.stdout.strip().replace("::error title=Preview host no longer fits the stack::",
                                                          "##[error]"),
                             "##[error]Process completed with exit code 4."])
            result = triage.triage_log(log)
            self.assertEqual((result["category"], result["owner"]), ("stack", "devops"))
            self.assertIn("now=server", result["evidence"][0])

    def test_offline_log_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "job.log"
            path.write_text(LOG)
            result = run(TRIAGE, "--log", path, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)[0]["jobs"][0]["owner"], "developer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
