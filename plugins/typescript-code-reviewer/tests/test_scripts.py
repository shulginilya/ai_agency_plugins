#!/usr/bin/env python3
"""Smoke tests for the scripts the typescript-code-reviewer plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "typescript-review" / "scripts"
SCOPE = SCRIPTS / "ts_scope.py"
REPORT = SCRIPTS / "review_report.py"
sys.path.insert(0, str(SCRIPTS))
import review_report  # noqa: E402
import ts_scope  # noqa: E402

TSCONFIG = """{
  // the app's config; strictness comes from the base
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "paths": { "@/*": ["src/*"] }, /* a string that looks like a comment */
    "noUncheckedIndexedAccess": false,
  },
}
"""


def write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
         "-c", "core.autocrlf=false", *args],
        cwd=str(root), check=True, capture_output=True, text=True)
    return out.stdout.strip()


def commit(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


class Repo:
    """A TypeScript repo with a feature branch: committed, uncommitted and untracked changes."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        write(self.root, "package.json", json.dumps({
            "name": "app", "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint .", "test": "vitest"},
            "devDependencies": {"typescript": "^6.0.0"}}))
        write(self.root, "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
        write(self.root, "tsconfig.base.json", '{"compilerOptions": {"strict": true}}\n')
        write(self.root, "tsconfig.json", TSCONFIG)
        write(self.root, "src/server.ts", "import express from 'express';\nexport const app = express();\n")
        write(self.root, "src/util.ts", "export const x = 1;\n")
        write(self.root, "README.md", "app\n")
        commit(self.root, "base")
        git(self.root, "checkout", "-q", "-b", "feature")
        write(self.root, "src/server.ts", "import express from 'express';\nexport const app = express();\n"
                                          "// @ts-ignore\nconst body = req.body as any;\n")
        write(self.root, "src/App.tsx", "import { useState } from 'react';\n"
                                        "const text = document.getElementById('x')!.textContent;\n")
        write(self.root, "src/util.test.ts", "import { x } from './util';\n// @ts-expect-error\n"
                                             "const y: string = x;\n")
        write(self.root, "README.md", "app, changed\n")
        commit(self.root, "feature")
        write(self.root, "src/util.ts", "export const x = 1;\nexport const z: Record<string, any> = {};\n")
        write(self.root, "src/new.ts", "const v = foo as unknown as Bar; // eslint-disable-line\n")

    def close(self) -> None:
        self.tmp.cleanup()


class ScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Repo()
        cls.result = ts_scope.scope(cls.repo.root, "main")

    @classmethod
    def tearDownClass(cls):
        cls.repo.close()

    def files(self):
        return {f["path"]: f for f in self.result["files"]}

    def test_lists_committed_uncommitted_and_untracked_code_only(self):
        files = self.files()
        self.assertEqual(set(files), {"src/App.tsx", "src/new.ts", "src/server.ts", "src/util.test.ts", "src/util.ts"})
        self.assertEqual(files["src/App.tsx"]["status"], "A")
        self.assertEqual(files["src/server.ts"]["status"], "M")
        self.assertEqual(files["src/util.ts"]["status"], "M", "an uncommitted change counts")
        self.assertEqual(files["src/new.ts"]["status"], "?")
        self.assertEqual((files["src/server.ts"]["added"], files["src/server.ts"]["deleted"]), (2, 0))
        self.assertTrue(self.result["uncommitted"])

    def test_tags_and_passes(self):
        files = self.files()
        self.assertEqual(files["src/App.tsx"]["tags"], ["react"])
        self.assertEqual(files["src/server.ts"]["tags"], ["node"])
        self.assertEqual(files["src/util.test.ts"]["tags"], ["test"])
        self.assertEqual(files["src/util.ts"]["tags"], [])
        self.assertEqual(self.result["passes"], ["types", "correctness", "tests", "react", "node"])

    def test_package_checks_for_its_manager(self):
        [package] = self.result["packages"]
        self.assertEqual(package["dir"], ".")
        self.assertEqual(package["manager"], "pnpm")
        self.assertEqual(package["checks"], {"typecheck": "pnpm run typecheck", "lint": "pnpm run lint",
                                             "test": "CI=true pnpm run test"})
        self.assertEqual(package["install"], {"dir": ".", "command": "pnpm install --frozen-lockfile"})

    def test_strictness_follows_extends_through_jsonc(self):
        [report] = self.result["packages"][0]["tsconfigs"]
        self.assertEqual(report["config"], "tsconfig.json")
        self.assertIs(report["flags"]["strict"], True)
        self.assertIs(report["flags"]["strictNullChecks"], True)
        self.assertIs(report["flags"]["noUncheckedIndexedAccess"], False)
        self.assertEqual(report["unresolved"], [])
        self.assertEqual(report["gaps"], [ts_scope.GAPS["noUncheckedIndexedAccess"],
                                          ts_scope.GAPS["exactOptionalPropertyTypes"]])

    def test_escape_hatches_with_working_tree_line_numbers(self):
        found = {(h["file"], h["line"], h["kind"]) for h in self.result["hatches"]}
        self.assertEqual(found, {
            ("src/server.ts", 3, "@ts-ignore"),
            ("src/server.ts", 4, "any"),
            ("src/App.tsx", 2, "non-null !"),
            ("src/util.test.ts", 2, "@ts-expect-error with no reason"),
            ("src/util.ts", 2, "any"),
            ("src/new.ts", 1, "as unknown as"),
            ("src/new.ts", 1, "eslint-disable"),
        })

    def test_cli_text_and_json(self):
        text = subprocess.run([sys.executable, str(SCOPE), "--base", "main", "--repo", str(self.repo.root)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("passes: types, correctness, tests, react, node", text.stdout)
        self.assertIn("src/new.ts (untracked)", text.stdout)
        self.assertIn("typecheck: (cd . && pnpm run typecheck)", text.stdout)
        self.assertIn("tsc will not catch: arr[i] and record[key]", text.stdout)
        self.assertIn("src/server.ts:3  @ts-ignore", text.stdout)
        data = subprocess.run([sys.executable, str(SCOPE), "--base", "main", "--json", "--repo", str(self.repo.root)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(json.loads(data.stdout)["passes"], self.result["passes"])

    def test_bad_base_exits_2(self):
        done = subprocess.run([sys.executable, str(SCOPE), "--base", "no-such-ref", "--repo", str(self.repo.root)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no-such-ref", done.stderr)


class NothingToReviewTest(unittest.TestCase):
    def test_no_code_or_config_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            write(root, "src/a.ts", "export const a = 1;\n")
            write(root, "README.md", "x\n")
            commit(root, "base")
            git(root, "checkout", "-q", "-b", "docs")
            write(root, "README.md", "y\n")
            result = ts_scope.scope(root)  # no --base: falls back to main
            self.assertEqual(result["base"], "main")
            self.assertEqual((result["files"], result["passes"], result["packages"]), ([], [], []))
            self.assertIn("nothing to review", ts_scope.render(result))

    def test_config_only_change_is_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            write(root, "tsconfig.json", '{"compilerOptions": {"strict": true}}\n')
            commit(root, "base")
            git(root, "checkout", "-q", "-b", "loosen")
            write(root, "tsconfig.json", '{"compilerOptions": {"strict": false}}\n')
            result = ts_scope.scope(root, "main")
            self.assertEqual([f["tags"] for f in result["files"]], [["config"]])
            self.assertEqual(result["passes"], ["types", "correctness", "tests"])
            flags = result["packages"][0]["tsconfigs"][0]["flags"]
            self.assertIs(flags["strictNullChecks"], False)


class TsconfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_jsonc_keeps_comment_like_strings_and_drops_trailing_commas(self):
        data = ts_scope.parse_jsonc(TSCONFIG)
        self.assertEqual(data["compilerOptions"]["paths"], {"@/*": ["src/*"]})
        self.assertEqual(ts_scope.parse_jsonc('{"a": [1, 2, /* c */ ], "b": "x//y", // end\n}'),
                         {"a": [1, 2], "b": "x//y"})
        self.assertEqual(ts_scope.parse_jsonc('{"a": "say \\"hi\\" // not a comment",}'),
                         {"a": 'say "hi" // not a comment'})

    def test_extends_a_package_and_an_array_and_reports_what_it_cannot_find(self):
        write(self.root, "node_modules/@tsconfig/strictest/tsconfig.json",
              '{"compilerOptions": {"strict": true, "noUncheckedIndexedAccess": true}}')
        write(self.root, "local.json", '{"compilerOptions": {"exactOptionalPropertyTypes": true}}')
        write(self.root, "tsconfig.json",
              '{"extends": ["@tsconfig/strictest/tsconfig.json", "./local", "@missing/config"]}')
        report = ts_scope.strictness(self.root / "tsconfig.json", self.root)
        self.assertIs(report["flags"]["strict"], True)
        self.assertIs(report["flags"]["noUncheckedIndexedAccess"], True)
        self.assertIs(report["flags"]["exactOptionalPropertyTypes"], True)
        self.assertEqual(report["gaps"], [])
        self.assertEqual(report["unresolved"], ["@missing/config"])

    def test_unset_strict_follows_the_installed_typescript(self):
        write(self.root, "tsconfig.json", "{}")
        report = ts_scope.strictness(self.root / "tsconfig.json", self.root)
        self.assertIsNone(report["flags"]["strict"])
        self.assertIn("installed: unknown", report["notes"][0])
        for version, expected in (("5.9.3", False), ("6.0.1", True)):
            write(self.root, "node_modules/typescript/package.json", json.dumps({"version": version}))
            report = ts_scope.strictness(self.root / "tsconfig.json", self.root)
            self.assertIs(report["flags"]["strict"], expected, version)
            self.assertIs(report["flags"]["strictNullChecks"], expected, version)

    def test_solution_style_config_checks_its_references_with_tsc_b(self):
        write(self.root, "package.json", json.dumps({"scripts": {"build": "tsc -b && vite build"}}))
        write(self.root, "package-lock.json", "{}")
        write(self.root, "tsconfig.json", '{"files": [], "references": [{"path": "./tsconfig.app.json"}]}')
        write(self.root, "tsconfig.app.json", '{"compilerOptions": {"strict": true}}')
        report = ts_scope.package_report(self.root, self.root)
        self.assertEqual(report["manager"], "npm")
        self.assertEqual(report["checks"]["typecheck"], "npx --no tsc -b")
        self.assertEqual([c["config"] for c in report["tsconfigs"]], ["tsconfig.json", "tsconfig.app.json"])
        self.assertTrue(report["tsconfigs"][0]["solution"])
        self.assertIs(report["tsconfigs"][1]["flags"]["strict"], True)
        self.assertEqual(report["install"], {"dir": ".", "command": "npm ci"})
        self.assertTrue(any("typescript is not in package.json" in n for n in report["notes"]))


class PackageTest(unittest.TestCase):
    def test_npm_placeholder_test_and_tsc_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({
                "scripts": {"test": 'echo "Error: no test specified" && exit 1'},
                "devDependencies": {"typescript": "5.9.0"}}))
            write(root, "tsconfig.json", "{}")
            (root / "node_modules").mkdir()
            report = ts_scope.package_report(root, root)
            self.assertEqual(report["checks"], {"typecheck": "npx --no tsc --noEmit -p tsconfig.json",
                                                "lint": None, "test": None})
            self.assertIsNone(report["install"])

    def test_workspace_package_uses_the_root_lockfile_and_yarn_berry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({"private": True, "workspaces": ["packages/*"]}))
            write(root, "yarn.lock", "")
            write(root, ".yarnrc.yml", "nodeLinker: node-modules\n")
            write(root, "packages/api/package.json", json.dumps({"name": "api", "scripts": {"lint": "eslint ."}}))
            self.assertEqual(ts_scope.package_dir_of("packages/api/src/a.ts", root), root / "packages" / "api")
            report = ts_scope.package_report(root / "packages" / "api", root)
            self.assertEqual((report["dir"], report["manager"]), ("packages/api", "yarn"))
            self.assertEqual(report["checks"]["lint"], "yarn run lint")
            self.assertEqual(report["install"], {"dir": ".", "command": "yarn install --immutable"})


class ClassifyTest(unittest.TestCase):
    def test_tags(self):
        self.assertEqual(ts_scope.tags_of("app/api/users/route.ts", "export async function GET() {}"), ["node"])
        self.assertEqual(ts_scope.tags_of("src/hooks.ts", "'use client';\nexport const a = 1;"), ["react"])
        self.assertEqual(ts_scope.tags_of("src/actions.ts", '"use server"\nexport async function save() {}'),
                         ["node"])
        self.assertEqual(ts_scope.tags_of("src/q.ts", "import { useQuery } from '@tanstack/react-query'"), ["react"])
        self.assertEqual(ts_scope.tags_of("src/fs.ts", "import { readFile } from 'node:fs/promises'"), ["node"])
        self.assertEqual(ts_scope.tags_of("src/mw.ts", "import { NextResponse } from 'next/server'"), ["node"])
        self.assertEqual(ts_scope.tags_of("types/env.d.ts", ""), ["declaration"])
        self.assertEqual(ts_scope.tags_of("src/__tests__/a.ts", ""), ["test"])
        self.assertEqual(ts_scope.tags_of("apps/web/tsconfig.app.json", ""), ["config"])

    def test_hatches_ignore_strings_comments_and_comparisons(self):
        quiet = ['const s = "type: any";', "// accepts any value: any", "if (a !== b) {}", "const ok = !x;",
                 "// @ts-expect-error -- the library's types are wrong", "let n!: number;"]
        self.assertEqual(ts_scope.hatches_in("a.ts", list(enumerate(quiet, 1))), [])
        loud = ["fn(x as any);", "const xs: any[] = [];", "const p: Promise<any> = f();", "user!.name;",
                "{/* @ts-expect-error */}", "/* eslint-disable */"]
        kinds = [h["kind"] for h in ts_scope.hatches_in("a.tsx", list(enumerate(loud, 1)))]
        self.assertEqual(kinds, ["any", "any", "any", "non-null !", "@ts-expect-error with no reason",
                                 "eslint-disable"])


def finding(severity, failure="res.json() returns {user: null} -> TypeError", **extra):
    return dict({"severity": severity, "pass": "types", "file": "src/a.ts", "line": 12, "claim": "the cast drops null",
                 "why": "the API returns null for deleted users", "failure": failure, "fix": "parse with zod"}, **extra)


def findings(*items, passes=("types", "correctness", "tests"), checks=()):
    return {"target": "PR #43", "commit": "abc1234", "passes": list(passes), "checks": list(checks),
            "findings": list(items)}


def run_report(data, *args):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "findings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return subprocess.run([sys.executable, str(REPORT), str(path), *args], capture_output=True, text=True,
                              check=False)


class ReportTest(unittest.TestCase):
    def test_any_blocker_or_major_requests_changes(self):
        for severity in ("blocker", "major"):
            result = review_report.judge(review_report.load(findings(finding("minor"), finding(severity))))
            self.assertEqual(result["verdict"], "request-changes", severity)
            self.assertEqual(result["findings"][0]["severity"], severity, "most severe first")

    def test_minor_and_nit_approve(self):
        result = review_report.judge(review_report.load(findings(finding("minor"), finding("nit", failure=""))))
        self.assertEqual(result["verdict"], "approve")
        body = review_report.render(result)
        self.assertIn("TypeScript review: **APPROVE** — PR #43", body)
        self.assertIn("**minor** (types) `src/a.ts:12`", body)
        self.assertIn("Nits (optional, never blocking)", body)

    def test_refuses_hunches_missing_passes_unknown_passes_and_red_checks_without_a_blocker(self):
        bad = [
            (findings(finding("major", failure="")), "hunch"),
            (findings(passes=("types", "correctness")), "tests"),
            (findings(passes=("types", "correctness", "tests", "security")), "unknown pass"),
            (findings(finding("minor", **{"pass": "css"})), "unknown pass"),
            (findings(checks=[{"name": "typecheck", "result": "fail"}]), "red check is a blocker"),
            (findings(checks=[{"name": "lint", "result": "green"}]), "result must be one of"),
        ]
        for data, message in bad:
            with self.assertRaises(review_report.ReportError) as caught:
                review_report.load(data)
            self.assertIn(message, str(caught.exception))

    def test_red_check_with_its_blocker_requests_changes(self):
        data = findings(finding("blocker", file="package.json", claim="typecheck fails", failure="pnpm run "
                                "typecheck -> src/a.ts(3,7): error TS2322"),
                        checks=[{"name": "typecheck", "command": "pnpm run typecheck", "result": "fail"},
                                {"name": "test", "result": "not run"}])
        result = review_report.judge(review_report.load(data))
        self.assertEqual(result["verdict"], "request-changes")
        self.assertIn("Checks: typecheck fail (`pnpm run typecheck`); test not run.", review_report.render(result))

    def test_cli_exit_codes_marker_and_commit_override(self):
        approve = run_report(findings(), "--commit", "def5678")
        self.assertEqual(approve.returncode, 0, approve.stderr)
        self.assertEqual(review_report.verdict_of(approve.stdout), {"verdict": "approve", "commit": "def5678"})
        self.assertIn("No findings that would break", approve.stdout)
        changes = run_report(findings(finding("blocker")), "--json")
        self.assertEqual(changes.returncode, 1)
        self.assertEqual(json.loads(changes.stdout)["counts"]["blocker"], 1)
        refused = run_report(findings(finding("minor", failure="  ")))
        self.assertEqual(refused.returncode, 2)
        self.assertIn("prove it or drop it", refused.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
