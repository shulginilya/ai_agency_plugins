#!/usr/bin/env python3
"""Smoke tests for the scripts, hook and MCP server the job-hunter plugin ships."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
TRIAGE = PLUGIN / "skills" / "opportunity-triage" / "scripts"
PIPELINE_DIR = PLUGIN / "skills" / "application-pipeline" / "scripts"
PORTFOLIO_DIR = PLUGIN / "skills" / "portfolio-case-study" / "scripts"
FIT = TRIAGE / "fit.py"
PIPELINE = PIPELINE_DIR / "pipeline.py"
FACTS = PORTFOLIO_DIR / "project_facts.py"
SEARCH_LOG = PLUGIN / "skills" / "platform-search" / "scripts" / "search_log.py"
HOOK = PLUGIN / "scripts" / "pipeline_status.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

sys.path.insert(0, str(TRIAGE))
sys.path.insert(0, str(PIPELINE_DIR))

PROFILE = {
    "titles": ["Senior AI Engineer"],
    "must_have": ["typescript", "react", "node"],
    "nice_to_have": ["aws"],
    "markets": {"onsite": ["Berlin"], "remote": ["eu"]},
    "tracks": ["contract"],
    "deal_breakers": ["relocation required"],
    "min_must_have_ratio": 0.6,
}

GOOD = "Senior AI Engineer, contract, fully remote within the EU. TypeScript, React, Node. AWS a plus. EUR 700/day."
BREAKER = "Senior AI Engineer, contract, remote EU. TypeScript, React, Node. Relocation required."
THIN = "PHP developer wanted, permanent, on-site in Munich."
VAGUE = "We want an engineer. TypeScript, React and Node are the stack."


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def workspace(tmp: str) -> Path:
    root = Path(tmp)
    (root / ".jobhunt").mkdir(parents=True, exist_ok=True)
    (root / ".jobhunt" / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
    return root


class FitTest(unittest.TestCase):
    def _verdict(self, root: Path, posting: str):
        target = root / "posting.txt"
        target.write_text(posting, encoding="utf-8")
        result = run([sys.executable, str(FIT), str(target), "--json"], cwd=root)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}

    def test_the_four_verdicts_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)

            code, report = self._verdict(root, GOOD)
            self.assertEqual((code, report["verdict"]), (0, "pursue"))

            code, report = self._verdict(root, BREAKER)
            self.assertEqual((code, report["verdict"]), (1, "skip"))
            self.assertIn("relocation required", report["deal_breakers_hit"])

            code, report = self._verdict(root, THIN)
            self.assertEqual((code, report["verdict"]), (1, "skip"))

            code, report = self._verdict(root, VAGUE)
            self.assertEqual((code, report["verdict"]), (3, "unclear"),
                             "a posting that omits track and location is unclear, not a fit")

    def test_a_missing_profile_is_exit_two_not_a_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            posting = Path(tmp) / "p.txt"
            posting.write_text(GOOD, encoding="utf-8")
            result = run([sys.executable, str(FIT), str(posting)], cwd=tmp)
            self.assertEqual(result.returncode, 2)
            self.assertIn("no profile", result.stderr)

    def test_an_empty_posting_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            (root / "empty.txt").write_text("   \n", encoding="utf-8")
            result = run([sys.executable, str(FIT), str(root / "empty.txt")], cwd=root)
            self.assertEqual(result.returncode, 2)

    def test_short_terms_are_word_bounded(self):
        import fit

        profile = dict(PROFILE, must_have=["go"], min_must_have_ratio=1.0)
        report = fit.assess("We use Django and Node here. Contract, remote EU.", profile)
        self.assertEqual(report["must_have"]["present"], [],
                         "'go' must not match inside 'Django'")


class PipelineTest(unittest.TestCase):
    def _run(self, root: Path, *args):
        return run([sys.executable, str(PIPELINE)] + list(args), cwd=root)

    def _seed(self, root: Path):
        self._run(root, "init")
        self._run(root, "add", "--company", "Acme", "--role", "Senior AI Engineer",
                  "--next", "send proposal", "--due", "2026-09-04")
        self._run(root, "add", "--company", "Globex", "--role", "AI Engineer",
                  "--stage", "applied", "--next", "follow up", "--due", "2026-09-20")

    def test_add_move_and_list_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            moved = self._run(root, "move", "Acme", "--to", "screening", "--next", "prep call",
                              "--due", "2026-09-11")
            self.assertEqual(moved.returncode, 0, moved.stderr)

            listed = self._run(root, "--json", "list")
            rows = {r["Company"]: r for r in json.loads(listed.stdout)}
            self.assertEqual(rows["Acme"]["Stage"], "screening")
            self.assertEqual(rows["Acme"]["Due"], "2026-09-11")
            self.assertEqual(rows["Globex"]["Stage"], "applied")

    def test_due_separates_overdue_from_missing_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            self._run(root, "add", "--company", "Initech", "--role", "Platform", "--stage", "applied")

            result = self._run(root, "--json", "due", "--as-of", "2026-09-06")
            self.assertEqual(result.returncode, 1, "something needs action, so this must exit 1")
            report = json.loads(result.stdout)
            self.assertEqual([r["Company"] for r in report["overdue"]], ["Acme"])
            self.assertEqual([r["Company"] for r in report["needs_attention"]], ["Initech"])
            self.assertEqual([r["Company"] for r in report["upcoming"]], [])

    def test_nothing_due_exits_zero_and_closed_rows_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run(root, "init")
            self._run(root, "add", "--company", "Acme", "--role", "R",
                      "--next", "chase", "--due", "2026-12-31")
            result = self._run(root, "due", "--as-of", "2026-09-06")
            self.assertEqual(result.returncode, 0)

            self._run(root, "add", "--company", "Dead", "--role", "R")
            self._run(root, "move", "Dead", "--to", "closed")
            result = self._run(root, "--json", "due", "--as-of", "2026-09-06")
            report = json.loads(result.stdout)
            self.assertNotIn("Dead", [r["Company"] for r in report["needs_attention"]])

    def test_a_malformed_table_is_refused_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = root / "broken.md"
            original = "| Company | Role |\n| --- | --- |\n| Acme | Dev |\n"
            broken.write_text(original, encoding="utf-8")
            result = self._run(root, "--file", str(broken), "list")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(broken.read_text(encoding="utf-8"), original,
                             "a table it cannot parse must be left exactly as found")

    def test_a_non_iso_due_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run(root, "init")
            result = self._run(root, "add", "--company", "Acme", "--role", "R", "--due", "next week")
            self.assertEqual(result.returncode, 2)
            self.assertIn("ISO date", result.stderr)

    def test_duplicates_are_refused_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            again = self._run(root, "add", "--company", "Acme", "--role", "Other")
            self.assertEqual(again.returncode, 2)


class HookTest(unittest.TestCase):
    def test_speaks_only_when_something_needs_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run([sys.executable, str(PIPELINE), "init"], cwd=root)
            run([sys.executable, str(PIPELINE), "add", "--company", "Acme", "--role", "R",
                 "--next", "chase", "--due", "2020-01-01"], cwd=root)
            result = run([sys.executable, str(HOOK)], input="{}", cwd=root)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Acme", result.stdout)

    def test_silent_with_no_pipeline_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(HOOK)], input="{}", cwd=tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

            result = run([sys.executable, str(HOOK)], input="not json", cwd=tmp)
            self.assertEqual(result.returncode, 0)


def make_project(root: Path, readme: bool = True) -> Path:
    project = root / "shop"
    (project / "src").mkdir(parents=True)
    (project / "node_modules" / "junk").mkdir(parents=True)
    (project / "node_modules" / "junk" / "index.js").write_text("x\n" * 50, encoding="utf-8")
    (project / "package.json").write_text(json.dumps({
        "name": "shop", "description": "Booking app for clinics",
        "dependencies": {"next": "14", "react": "18", "stripe": "1", "@aws-sdk/client-s3": "3"},
        "devDependencies": {"vitest": "1"},
    }), encoding="utf-8")
    (project / "src" / "app.tsx").write_text("export const a = 1\n", encoding="utf-8")
    (project / "src" / "app.test.ts").write_text("test('a', () => {})\n", encoding="utf-8")
    (project / "Dockerfile").write_text("FROM node\n", encoding="utf-8")
    (project / ".github" / "workflows").mkdir(parents=True)
    (project / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    if readme:
        (project / "README.md").write_text(
            "# Shop\n\n![badge](https://img.shields.io/x.svg)\n\nPatients book physio sessions online.\n\n"
            "Live at https://shop.example.com.\n", encoding="utf-8")
    return project


def git_commit(project: Path, name: str) -> bool:
    if shutil.which("git") is None:
        return False
    env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": "%s@example.com" % name.lower(),
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": "c@example.com"}
    import os
    full = dict(os.environ, **env)
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        if run(["git"] + args, cwd=project, env=full).returncode != 0:
            return False
    return True


class ProjectFactsTest(unittest.TestCase):
    def _facts(self, *args, cwd=None):
        result = run([sys.executable, str(FACTS)] + [str(a) for a in args] + ["--json"], cwd=cwd)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}, result.stderr

    def test_technologies_carry_their_source_and_vendored_code_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            code, report, _ = self._facts(project)
            self.assertEqual((code, report["verdict"]), (0, "usable"))
            tech = report["manifest"]["technologies"]
            for label in ("Next.js", "React", "Stripe", "AWS SDK", "Vitest"):
                self.assertEqual(tech.get(label), ["package.json"], label)
            self.assertEqual(report["manifest"]["description"], "Booking app for clinics")
            self.assertIn("Docker", report["tree"]["infrastructure"])
            self.assertEqual(report["tree"]["ci"], ["GitHub Actions"])
            self.assertEqual(report["tree"]["tests"]["files"], 1)
            langs = {l["language"]: l["files"] for l in report["tree"]["languages"]}
            self.assertNotIn("JavaScript", langs, "node_modules must not be counted")
            self.assertEqual(report["readme"]["first_paragraph"], "Patients book physio sessions online.")
            self.assertIn("https://shop.example.com", report["readme"]["links"])
            self.assertFalse(any("shields.io" in u for u in report["readme"]["links"]))

    def test_outcomes_are_always_left_for_the_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, report, _ = self._facts(make_project(Path(tmp)))
            self.assertTrue(any("outcomes" in q for q in report["ask_the_user"]))

    def test_nothing_saying_what_it_is_is_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "bare"
            project.mkdir()
            (project / "main.py").write_text("print(1)\n", encoding="utf-8")
            code, report, _ = self._facts(project)
            self.assertEqual((code, report["verdict"]), (3, "thin"))

    def test_the_users_share_comes_from_history_and_a_stranger_is_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            if not git_commit(project, "Ilya"):
                self.skipTest("git unavailable")
            code, report, _ = self._facts(project, "--author", "ilya")
            self.assertEqual(code, 0)
            self.assertEqual(report["git"]["mine"]["commits"], 1)
            self.assertEqual(report["git"]["mine"]["share"], 1.0)

            code, report, _ = self._facts(project, "--author", "someone-else")
            self.assertEqual((code, report["verdict"]), (3, "thin"),
                             "no commits by the user means the role cannot be read from history")

    def test_a_page_gives_hints_not_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "home.html"
            page.write_text('<html><head><title>Shop</title><meta name="description" content="Book physio">'
                            '</head><body><script src="/_next/static/x.js"></script>'
                            '<script src="https://js.stripe.com/v3"></script></body></html>', encoding="utf-8")
            code, report, _ = self._facts("--page", page)
            self.assertEqual(code, 0)
            self.assertEqual(report["title"], "Shop")
            self.assertIn("Next.js", report["stack_hints"])
            self.assertIn("Stripe", report["stack_hints"])
            self.assertIn("confirm", report["note"])

    def test_a_missing_directory_or_empty_page_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = self._facts(Path(tmp) / "nope")
            self.assertEqual(code, 2)
            self.assertIn("not a directory", err)
            empty = Path(tmp) / "empty.html"
            empty.write_text("  ", encoding="utf-8")
            code, _, _ = self._facts("--page", empty)
            self.assertEqual(code, 2)


SEARCH_PROFILE = dict(
    PROFILE,
    titles=["Senior Full-Stack Engineer", "Senior AI Engineer"],
    rate_floor={"currency": "USD", "per": "hour", "amount": 45},
    search={"platforms": ["upwork", "arc"], "results_per_run": 5, "mode": "draft"},
)


def hourly(job_id, title, low, high, client=None, **extra):
    posting = {"id": job_id, "title": title, "client": client,
               "rate": {"min": low, "max": high, "currency": "USD", "per": "hour"}}
    posting.update(extra)
    return posting


class SearchLogTest(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        (root / ".jobhunt").mkdir()
        (root / ".jobhunt" / "profile.json").write_text(json.dumps(SEARCH_PROFILE), encoding="utf-8")
        return root

    def _run(self, root, *args, stdin=None):
        return run([sys.executable, str(SEARCH_LOG)] + list(args), cwd=root, input=stdin)

    def test_plan_builds_role_queries_from_titles(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(self._root(tmp), "plan", "upwork")
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["queries"][:2], ["Full-Stack Engineer", "Full-Stack Developer"])
            self.assertIn("AI Developer", plan["queries"])
            self.assertEqual((plan["limit"], plan["mode"], plan["rate_floor"]["amount"]), (5, "draft", 45.0))

    def test_plan_without_profile_or_with_unknown_platform_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(Path(tmp), "plan", "upwork").returncode, 2)
            self.assertEqual(self._run(self._root(tmp), "plan", "fiverr").returncode, 2)

    def test_filter_applies_the_real_floor_and_collapses_reposts(self):
        found = [
            hourly("1", "AI Developer", 40, 75, client="c1"),
            hourly("2", "Full-Stack Developer", 25, 40, client="c2"),       # max under floor
            hourly("3", "Senior Engineer", 65, 120, client="c3"),
            hourly("4", "Senior  engineer!", 65, 120, client="c3"),         # same client, same job
            hourly("5", "Frontend Developer", None, None),                  # no rate: kept, flagged
            hourly("6", "AI Engineer", 50, 90, applied=True),
            hourly("7", "Node Developer", 60, 90, summary="Relocation required to Dubai"),
            {"id": "8", "title": "Fixed build", "rate": {"min": 3000, "per": "fixed"}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            result = self._run(root, "filter", "upwork", "-", stdin=json.dumps(found))
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual([p["id"] for p in out["kept"]], ["1", "3", "5", "8"])
            reasons = {p["id"]: p["note"] for p in out["dropped"]}
            self.assertIn("below floor", reasons["2"])
            self.assertIn("re-posted", reasons["4"])
            self.assertEqual(reasons["6"], "already applied")
            self.assertIn("deal-breaker", reasons["7"])
            flags = {p["id"]: " ".join(p["flags"]) for p in out["kept"]}
            self.assertIn("no rate stated", flags["5"])
            self.assertIn("fixed-price", flags["8"])
            self.assertIn("1 more time", flags["3"])

    def test_record_marks_seen_so_the_next_run_only_shows_new_postings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            first = [hourly("1", "AI Developer", 40, 75, verdict="pursue", note="best fit", url="https://x/1"),
                     hourly("2", "Full-Stack Developer", 25, 40)]
            filtered = self._run(root, "filter", "upwork", "-", stdin=json.dumps(first))
            (root / "filtered.json").write_text(filtered.stdout, encoding="utf-8")
            recorded = self._run(root, "record", "upwork", "filtered.json", "--date", "2026-10-04")
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertEqual(json.loads(recorded.stdout)["newly_seen"], 2)
            report = (root / ".jobhunt" / "searches" / "2026-10-04-upwork.md").read_text(encoding="utf-8")
            self.assertIn("[AI Developer](https://x/1)", report)
            self.assertIn("PURSUE", report)
            self.assertIn("below floor", report)

            again = self._run(root, "filter", "upwork", "-",
                              stdin=json.dumps(first + [hourly("9", "AI Engineer", 50, 90)]))
            self.assertEqual([p["id"] for p in json.loads(again.stdout)["kept"]], ["9"])
            # seen is per platform: the same id on another platform is new
            other = self._run(root, "filter", "arc", "-", stdin=json.dumps(first[:1]))
            self.assertEqual(other.returncode, 0)

    def test_nothing_new_exits_1_and_a_corrupt_seen_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            low = [hourly("2", "Full-Stack Developer", 25, 40)]
            self.assertEqual(self._run(root, "filter", "upwork", "-", stdin=json.dumps(low)).returncode, 1)
            seen = root / ".jobhunt" / "searches" / "seen.json"
            seen.parent.mkdir(parents=True)
            seen.write_text("not json", encoding="utf-8")
            result = self._run(root, "record", "upwork", "-", stdin=json.dumps(low))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(seen.read_text(encoding="utf-8"), "not json")

    def test_postings_without_id_or_title_are_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(self._root(tmp), "filter", "upwork", "-", stdin='[{"title": "x"}]')
            self.assertEqual(result.returncode, 2)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_and_list_tools(self):
        responses = self._rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "job-hunter")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"pipeline_status", "score_fit", "project_facts", "hunt_playbook"})

    def test_score_fit_uses_the_skills_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            responses = self._rpc([{
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "score_fit", "arguments": {"posting": BREAKER}},
            }], cwd=root)
            result = responses[0]["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(json.loads(result["content"][0]["text"])["verdict"], "skip")

    def test_project_facts_uses_the_skills_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            responses = self._rpc([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "project_facts", "arguments": {"path": str(project)}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "project_facts", "arguments": {}}},
            ])
            first = responses[0]["result"]
            self.assertFalse(first["isError"])
            self.assertIn("Next.js", json.loads(first["content"][0]["text"])["manifest"]["technologies"])
            self.assertTrue(responses[1]["result"]["isError"])

    def test_playbook_returns_a_reference(self):
        responses = self._rpc([{
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "hunt_playbook", "arguments": {"topic": "cadence"}},
        }])
        self.assertIn("Follow-up cadence", responses[0]["result"]["content"][0]["text"])

    def test_playbook_serves_the_platform_references(self):
        responses = self._rpc([{
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "hunt_playbook", "arguments": {"topic": "platform-upwork"}},
        }])
        self.assertIn("range overlap", responses[0]["result"]["content"][0]["text"])

    def test_a_bad_file_is_a_tool_error_and_the_server_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._rpc([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "pipeline_status", "arguments": {"file": "nope.md"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "ping"},
            ], cwd=tmp)
            self.assertTrue(responses[0]["result"]["isError"])
            self.assertEqual(responses[1]["result"], {}, "the server must still be alive")

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
