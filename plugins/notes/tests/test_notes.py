#!/usr/bin/env python3
"""Smoke tests for notes.py: parsing, lossless organize, capture, export and link-back."""

from __future__ import annotations

import json
import re
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "skills" / "note-keeping" / "scripts" / "notes.py"
sys.path.insert(0, str(SCRIPT.parent))
import notes  # noqa: E402

MESSY = """---
repo: me/app
board: 2
---
# Crew

Talked about the crew today.
- [x] crew-only deploy → #26
TODO: write the cache ticket
- [ ] add designer to the diagram
  - needs a lane

  - and a RACI column

## Deploy
- [/] wire designer
Remember the bashrc change.
- [-] separate config dir

### 2026-10-13
WIP: notes plugin
"""


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False, env=env)


class ParseTest(unittest.TestCase):
    def test_items_statuses_lines_children_and_front_matter(self):
        note = notes.parse(MESSY, "crew.md")
        self.assertEqual(note["meta"], {"repo": "me/app", "board": "2"})
        got = [(i["status"], i["text"], i["line"], i["loose"]) for i in note["items"]]
        self.assertEqual(got, [
            ("done", "crew-only deploy", 8, False),
            ("todo", "write the cache ticket", 9, True),
            ("todo", "add designer to the diagram", 10, False),
            ("wip", "wire designer", 16, False),
            ("dropped", "separate config dir", 18, False),
            ("wip", "notes plugin", 21, True),
        ])
        self.assertEqual(note["items"][0]["ticket"], "#26")
        self.assertEqual([c.strip() for c in note["items"][2]["children"] if c.strip()],
                         ["- needs a lane", "- and a RACI column"])
        self.assertEqual(note["items"][3]["group"], "Deploy")


class OrganizeTest(unittest.TestCase):
    def test_regroups_without_losing_a_line_and_is_stable(self):
        after = notes.organize_text(MESSY, "crew.md")
        self.assertEqual(notes.compare(MESSY, after), {"lost": [], "added": []})
        self.assertEqual(notes.organize_text(after, "crew.md"), after, "a second organize changes nothing")
        order = [line for line in after.splitlines() if line.startswith("## ")]
        self.assertEqual(order, ["## In progress", "## TODO", "## Done", "## Dropped", "## Notes", "## Deploy"])
        self.assertIn("- [ ] write the cache ticket", after)
        self.assertIn("### Deploy\n- [/] wire designer", after)
        self.assertTrue(after.startswith("---\nrepo: me/app\nboard: 2\n---\n# Crew\n"))

    def test_check_names_lost_and_added_lines(self):
        diff = notes.compare("- [ ] a\nprose\n", "- [ ] a\nprose\nprose\n- [x] b\n")
        self.assertEqual(diff, {"lost": [], "added": ["- [x] b", "prose"]})

    def test_organize_write_keeps_a_backup_and_cli_check_fails_on_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "crew.md"
            note.write_text(MESSY, encoding="utf-8")
            result = run("--root", tmp, "organize", "--file", "crew.md", "--write")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(tmp) / "crew.md.bak").read_text(encoding="utf-8"), MESSY)
            self.assertEqual(run("check", Path(tmp) / "crew.md.bak", note).returncode, 0)
            lost = Path(tmp) / "lost.md"
            lost.write_text(note.read_text(encoding="utf-8").replace("Remember the bashrc change.\n", ""),
                            encoding="utf-8")
            result = run("check", Path(tmp) / "crew.md.bak", lost)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Remember the bashrc change.", result.stderr)


class AddTest(unittest.TestCase):
    def test_new_topic_existing_section_and_same_day_notes(self):
        text = notes.add_to("", "Observatory", "wip", "fixtures", "2026-10-14")
        text = notes.add_to(text, "Observatory", "todo", "error filter", "2026-10-14")
        text = notes.add_to(text, "Observatory", "todo", "second todo", "2026-10-14")
        text = notes.add_to(text, "Observatory", "note", "first note", "2026-10-14")
        text = notes.add_to(text, "Observatory", "note", "second note", "2026-10-14")
        self.assertEqual(text, "# Observatory\n\n## In progress\n- [/] fixtures\n\n## TODO\n- [ ] error filter\n"
                               "- [ ] second todo\n\n## Notes\n### 2026-10-14\nfirst note\nsecond note\n")


class RootTest(unittest.TestCase):
    def test_flag_beats_env_beats_saved_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_CONFIG_HOME=tmp)
            env.pop("NOTES_DIR", None)
            self.assertEqual(run("where", env=env).returncode, 2, "nothing set yet")
            self.assertEqual(run("set-root", tmp, env=env).returncode, 0)
            self.assertEqual(json.loads(run("where", env=env).stdout)["from"], str(Path(tmp) / "ai-agency" / "notes.json"))
            env["NOTES_DIR"] = tmp
            self.assertEqual(json.loads(run("where", env=env).stdout)["from"], "$NOTES_DIR")
            self.assertEqual(json.loads(run("--root", tmp, "where", env=env).stdout)["from"], "--root")

    @unittest.skipIf(os.name == "nt", "WSL mapping only applies outside native Windows")
    def test_windows_paths_map_to_wsl_mounts(self):
        with mock.patch.object(notes.Path, "is_dir", return_value=True):
            self.assertEqual(notes.normalize_path(r"C:\Users\Ilya Shulgin\notes"),
                             Path("/mnt/c/Users/Ilya Shulgin/notes"))
        self.assertEqual(notes.normalize_path("/home/me/notes"), Path("/home/me/notes"))

    @unittest.skipUnless(os.name == "nt", "native Windows only")
    def test_native_windows_keeps_drive_paths(self):
        self.assertEqual(notes.normalize_path(r"C:\Users\Ilya Shulgin\notes"),
                         Path(r"C:\Users\Ilya Shulgin\notes"))


class ExportAndLinkTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "notes"
        self.root.mkdir()
        (self.root / "crew.md").write_text(MESSY, encoding="utf-8")
        (self.root / "loose.md").write_text("# Loose\n- [ ] needs a repo\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_open_unfiled_items_grouped_by_repo_board_and_column(self):
        plans = notes.export(self.root, ["todo", "wip"], "crew", None, None, notes.DEFAULT_COLUMNS)
        by_column = {p["column"]: [i["title"] for i in p["issues"]] for p in plans}
        self.assertEqual(by_column, {"Backlog": ["write the cache ticket", "add designer to the diagram"],
                                     "In progress": ["wire designer", "notes plugin"]})
        self.assertTrue(all(p["repo"] == "me/app" and p["board"] == 2 for p in plans))
        body = next(i["body"] for p in plans for i in p["issues"] if i["title"] == "add designer to the diagram")
        self.assertIn("crew.md", body)
        self.assertIn("- needs a lane", body)

    def test_a_topic_without_a_repo_is_refused_not_guessed(self):
        with self.assertRaisesRegex(notes.NotesError, "loose.md: no repo"):
            notes.export(self.root, ["todo"], None, None, None, notes.DEFAULT_COLUMNS)
        plans = notes.export(self.root, ["todo"], "loose", "me/other", None, notes.DEFAULT_COLUMNS)
        self.assertEqual(plans[0]["repo"], "me/other")

    def test_link_back_marks_items_and_they_are_not_exported_again(self):
        plans = notes.export(self.root, ["todo", "wip"], "crew", None, None, notes.DEFAULT_COLUMNS, after_filing="link")
        for n, plan in enumerate(plans):
            numbers = {k: 100 + 10 * n + i for i, k in enumerate(plan["sources"])}
            notes.link_back(self.root, plan, numbers)
        text = (self.root / "crew.md").read_text(encoding="utf-8")
        self.assertIn("TODO: write the cache ticket → #100", text)
        self.assertIn("- [/] wire designer → #110", text)
        self.assertEqual(notes.export(self.root, ["todo", "wip"], "crew", None, None, notes.DEFAULT_COLUMNS), [])

    def test_link_uses_the_full_ref_when_the_repo_came_from_the_flag(self):
        plan = notes.export(self.root, ["todo"], "loose", "me/other", None, notes.DEFAULT_COLUMNS, after_filing="link")[0]
        notes.link_back(self.root, plan, {k: 7 for k in plan["sources"]})
        self.assertIn("- [ ] needs a repo → me/other#7", (self.root / "loose.md").read_text(encoding="utf-8"))

    def test_file_refuses_without_approval(self):
        result = run("--root", self.root, "file", "--plans", self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("show the export to the user first", result.stderr)


INLINE = """# Ideas
Talked to the team. We should "add an error filter"(todo) and maybe "try Neon branches"(TODO).
Someday "add a dark mode"(Optional).
Currently "wiring the board"(WIP) and "fixing the export"(wip); "shipped the notes plugin"(+) and
"wrote the README"(DONE), also "made the board"(done).
- [ ] "checkbox with a marker"(todo)

- [ ] a plain checkbox
- [x] old done checkbox

```
"inside a fence"(todo)
```
"""


class InlineMarkerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "notes"
        self.root.mkdir()
        (self.root / "ideas.md").write_text(INLINE, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def export(self, statuses=("todo", "wip", "done"), assignee="@me", after_filing="link"):
        return notes.export(self.root, list(statuses), None, "me/tasks", 5, notes.DEFAULT_COLUMNS, assignee,
                            after_filing=after_filing)

    def test_markers_found_mid_line_in_any_case_and_not_in_fences(self):
        found = [(i["status"], i["text"]) for i in notes.inline_items(INLINE)]
        self.assertEqual(found, [
            ("todo", "add an error filter"), ("todo", "try Neon branches"), ("todo", "add a dark mode"),
            ("wip", "wiring the board"), ("wip", "fixing the export"), ("done", "shipped the notes plugin"),
            ("done", "wrote the README"), ("done", "made the board"), ("todo", "checkbox with a marker"),
        ])

    def test_columns_assignee_and_close_per_status(self):
        plans = {p["status"]: p for p in self.export()}
        self.assertEqual(plans["todo"]["column"], "Backlog")
        self.assertEqual(plans["optional"]["column"], "In Definition")
        self.assertEqual([i["title"] for i in plans["optional"]["issues"]], ["add a dark mode"])
        self.assertIn("Marked optional", plans["optional"]["issues"][0]["body"])
        self.assertIn("line 3, Optional)", plans["optional"]["issues"][0]["body"])
        self.assertEqual(plans["wip"]["column"], "In progress")
        self.assertEqual(plans["done"]["column"], "Done")
        self.assertTrue(plans["done"]["close"])
        self.assertFalse(plans["todo"]["close"] or plans["optional"]["close"] or plans["wip"]["close"])
        titles = [i["title"] for i in plans["todo"]["issues"]]
        self.assertEqual(titles, ["add an error filter", "try Neon branches",
                                  "checkbox with a marker", "a plain checkbox"], "a checkbox holding a marker is filed once")
        self.assertNotIn("Marked optional", plans["todo"]["issues"][0]["body"])
        self.assertNotIn("old done checkbox", [i["title"] for i in plans["done"]["issues"]])
        self.assertTrue(all(i["assignees"] == ["@me"] for p in plans.values() for i in p["issues"]))
        self.assertTrue(all(p["repo"] == "me/tasks" and p["board"] == 5 for p in plans.values()))

    def test_no_assignee_when_set_to_none(self):
        self.assertTrue(all("assignees" not in i for p in self.export(assignee="none") for i in p["issues"]))

    def test_link_back_after_the_marker_and_never_filed_twice(self):
        for n, plan in enumerate(self.export()):
            notes.link_back(self.root, plan, {k: 50 + 10 * n + i for i, k in enumerate(plan["sources"])})
        text = (self.root / "ideas.md").read_text(encoding="utf-8")
        self.assertIn('We should "add an error filter"(todo) → me/tasks#50 and maybe', text)
        self.assertIn('"wrote the README"(DONE) → me/tasks#', text)
        self.assertIn('- [ ] "checkbox with a marker"(todo) → me/tasks#', text)
        self.assertEqual(self.export(), [])
        scan = notes.scan_items(self.root, None)
        self.assertTrue(all(r["ticket"] for r in scan if r["status"] != "done" or r["inline"]))

    def test_organize_keeps_every_marker(self):
        after = notes.organize_text(INLINE, "ideas.md")
        self.assertEqual(notes.compare(INLINE, after), {"lost": [], "added": []})
        self.assertEqual(len(notes.inline_items(after)), len(notes.inline_items(INLINE)))

    def test_file_closes_created_done_tickets(self):
        out = Path(self._tmp.name) / "plans"
        notes.write_plans(self.export(statuses=("done",)), out)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if "batch" in cmd:
                plan = json.loads(Path(cmd[cmd.index("--plan") + 1]).read_text())
                issues = [{"key": i["key"], "number": 70 + n, "title": i["title"], "created": n != 0}
                          for n, i in enumerate(plan["issues"])]
                return mock.Mock(returncode=0, stdout=json.dumps({"created": 2, "skipped": 1, "issues": issues}),
                                 stderr="")
            return mock.Mock(returncode=0, stdout="{}", stderr="")

        with mock.patch.object(notes.subprocess, "run", fake_run):
            result = notes.file_plans(self.root, out)[0]
        batch = next(c for c in calls if "batch" in c)
        self.assertEqual(batch[batch.index("--status") + 1], "Done")
        closes = [c[c.index("--issue") + 1] for c in calls if "close" in c]
        self.assertEqual(closes, ["71", "72"], "only newly created tickets are closed")
        self.assertEqual(result["closed"], [71, 72])


SCOPED = """# Importer
We need "build the importer"(todo) soon
- parse the CSV
\u2013 map the columns
\u2022 [x] pick a library
- [ ] write tests
not a bullet, so the scope ended
- [ ] a separate checkbox

"second"(wip)
- step one

- after a blank line
## Later
- [ ] "move me"(todo)
- with this step
"""


class ScopeTest(unittest.TestCase):
    def test_bullet_and_dash_lines_after_a_marker_are_its_scope(self):
        items = {i["text"]: i["scope"] for i in notes.inline_items(SCOPED)}
        self.assertEqual(items["build the importer"],
                         ["- parse the CSV", "\u2013 map the columns", "\u2022 [x] pick a library", "- [ ] write tests"])
        self.assertEqual(items["second"], ["- step one"], "a blank line ends the scope")
        self.assertEqual(items["move me"], ["- with this step"])

    def test_scope_becomes_a_task_list_and_is_not_filed_on_its_own(self):
        note = notes.parse(SCOPED, "importer.md")
        plain = [i["text"] for i in notes.note_items(note, SCOPED) if not i["inline"]]
        self.assertEqual(plain, ["a separate checkbox"])
        body = notes.ticket_body("Importer", "importer.md", notes.inline_items(SCOPED)[0])
        self.assertIn("**Checklist**\n\n- [ ] parse the CSV\n- [ ] map the columns\n- [x] pick a library\n- [ ] write tests",
                      body)

    def test_organize_keeps_each_scope_under_its_marker(self):
        after = notes.organize_text(SCOPED, "importer.md")
        self.assertEqual(notes.compare(SCOPED, after), {"lost": [], "added": []})
        self.assertIn('- [ ] "move me"(todo)\n- with this step', after)
        self.assertEqual({i["text"]: i["scope"] for i in notes.inline_items(after)},
                         {i["text"]: i["scope"] for i in notes.inline_items(SCOPED)})

    def test_export_lists_the_scope_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n"
            root.mkdir()
            (root / "importer.md").write_text(SCOPED, encoding="utf-8")
            plans = notes.export(root, ["todo"], None, "me/tasks", 5, notes.DEFAULT_COLUMNS, "@me")
            items = notes.write_plans(plans, Path(tmp) / "plans")[0]["items"]
        self.assertIn("build the importer (4 scope items)", items)
        self.assertIn("a separate checkbox", items)


OUTCOMES = """---
repo: me/app
---
# Importer

"build the importer"(todo)
- parse the CSV
- "a 10k-row file imports in under 5 seconds"(OUTCOME)
- "bad rows are reported with their line number"(outcome)

"add an error filter"(todo) "only errors are shown"(outcome)

- [ ] add dark mode
  - toggle in the header
Done when "contrast passes AA"(outcome)
- [ ] filed already → #3
- "added after filing"(outcome)

"belongs to nothing"(outcome)

```
"in a fence"(outcome)
```
"""


class OutcomeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "notes"
        self.root.mkdir()
        self.path = self.root / "importer.md"
        self.path.write_text(OUTCOMES, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def export(self, warnings=None, after_filing="remove"):
        return notes.export(self.root, ["todo"], None, None, None, notes.DEFAULT_COLUMNS, "@me", None,
                            after_filing, warnings)

    def bodies(self):
        return {i["title"]: i["body"] for p in self.export() for i in p["issues"]}

    def test_an_outcome_never_files_a_ticket_and_never_counts_as_an_item(self):
        self.assertEqual(sorted(self.bodies()), ["add an error filter", "add dark mode", "build the importer"])
        scan = [it["text"] for it in notes.note_items(notes.parse(OUTCOMES), OUTCOMES)]
        self.assertNotIn("belongs to nothing", " ".join(scan))

    def test_each_outcome_joins_its_own_line_its_scope_or_the_item_above(self):
        bodies = self.bodies()
        self.assertIn("**Acceptance criteria**\n\n- [ ] a 10k-row file imports in under 5 seconds\n"
                      "- [ ] bad rows are reported with their line number", bodies["build the importer"])
        self.assertIn("**Acceptance criteria**\n\n- [ ] only errors are shown", bodies["add an error filter"])
        self.assertIn("**Acceptance criteria**\n\n- [ ] contrast passes AA", bodies["add dark mode"])

    def test_outcomes_leave_the_checklist_and_the_details(self):
        bodies = self.bodies()
        self.assertIn("**Checklist**\n\n- [ ] parse the CSV\n\n**Acceptance criteria**", bodies["build the importer"])
        self.assertNotIn("(outcome)", "".join(bodies.values()))
        self.assertEqual(bodies["add dark mode"].count("contrast passes AA"), 1)

    def test_export_counts_outcomes_and_warns_about_those_no_ticket_gets(self):
        warnings = []
        items = notes.write_plans(self.export(warnings), Path(self._tmp.name) / "plans")[0]["items"]
        self.assertIn("build the importer (1 scope item, 2 outcomes)", items)
        self.assertIn("add an error filter (1 outcome)", items)
        self.assertEqual(len(warnings), 2, warnings)
        self.assertIn("'belongs to nothing' belongs to no item", warnings[0])
        self.assertIn("'added after filing' is under #3, which is already filed", warnings[1])

    def link(self, after_filing):
        plans = self.export(after_filing=after_filing)
        numbers = {k: n for n, k in enumerate(plans[0]["sources"], 10)}
        return notes.link_back(self.root, plans[0], numbers)

    def test_link_mode_marks_every_outcome_with_its_ticket(self):
        self.link("link")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn('- "a 10k-row file imports in under 5 seconds"(OUTCOME) → #10', text)
        self.assertIn('"add an error filter"(todo) → #11 "only errors are shown"(outcome)\n', text)
        self.assertIn('Done when "contrast passes AA"(outcome) → #12', text)
        warnings = []
        self.assertEqual(self.export(warnings), [])
        self.assertEqual(len(warnings), 2, "filed outcomes warn no more")

    def test_remove_mode_takes_outcomes_out_with_their_item(self):
        report = self.link("remove")
        text = self.path.read_text(encoding="utf-8")
        for gone in ("10k-row", "only errors", "contrast", "toggle"):
            self.assertNotIn(gone, text)
        self.assertIn('"belongs to nothing"(outcome)', text)
        self.assertIn('"in a fence"(outcome)', text)
        self.assertFalse(any("removed: its outcome" in r for r in report), "each went out with its item's block")

    def test_remove_mode_removes_an_outcome_line_that_prose_kept_apart_from_its_item(self):
        self.path.write_text('---\nrepo: me/app\n---\n"ship it"(todo)\nSome context that stays.\n'
                             '"it is shipped"(outcome)\n', encoding="utf-8")
        report = self.link("remove")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "---\nrepo: me/app\n---\n"
                         "→ [#10 ship it](https://github.com/me/app/issues/10)\nSome context that stays.\n")
        self.assertIn("importer.md:6 removed: its outcome is in the ticket (previous version in importer.md.bak)",
                      report)

    def test_organize_keeps_outcomes_with_their_item(self):
        after = notes.organize_text(OUTCOMES, "importer.md")
        self.assertEqual(notes.compare(OUTCOMES, after), {"lost": [], "added": []})
        self.assertIn("- [ ] add dark mode\n  - toggle in the header\nDone when", after)


class FileArgumentTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.tmp / "cfg"))
        self.env.pop("NOTES_DIR", None)
        self.elsewhere = self.tmp / "elsewhere" / "meeting.md"
        self.elsewhere.parent.mkdir()
        self.elsewhere.write_text('# Meeting\n"call the vendor"(todo)\n- ask about pricing\n', encoding="utf-8")
        self.root = self.tmp / "notes"
        self.root.mkdir()
        (self.root / "crew.md").write_text('# Crew\n"not this one"(todo)\n', encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_file_anywhere_needs_no_notes_folder(self):
        result = run("export", "--file", self.elsewhere, "--repo", "me/tasks", "--out", self.tmp / "plans", env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)["plans"][0]
        self.assertEqual(plan["items"], ["call the vendor (1 scope item)"])
        scan = json.loads(run("scan", "--file", self.elsewhere, "--json", env=self.env).stdout)
        self.assertEqual([r["text"] for r in scan], ["call the vendor"])

    def test_a_bare_name_is_looked_up_in_the_notes_folder(self):
        result = run("--root", self.root, "scan", "--file", "crew.md", "--json", env=self.env)
        self.assertEqual([r["text"] for r in json.loads(result.stdout)], ["not this one"])

    def test_a_missing_file_is_bad_input(self):
        result = run("--root", self.root, "export", "--file", "nope.md", "--repo", "me/t", "--out", self.tmp / "p",
                     env=self.env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)

    def test_filing_links_back_into_the_named_file_not_the_notes_folder(self):
        out = self.tmp / "plans"
        root, files = notes.select_files(str(self.root), str(self.elsewhere))
        notes.write_plans(notes.export(root, ["todo"], None, "me/tasks", None, notes.DEFAULT_COLUMNS, "@me", files), out)
        before = self.elsewhere.read_text(encoding="utf-8")

        def fake_run(cmd, **kwargs):
            plan = json.loads(Path(cmd[cmd.index("--plan") + 1]).read_text())
            issues = [{"key": i["key"], "number": 9, "title": i["title"], "created": True} for i in plan["issues"]]
            return mock.Mock(returncode=0, stdout=json.dumps({"created": 1, "skipped": 0, "issues": issues}), stderr="")

        with mock.patch.object(notes.subprocess, "run", fake_run):
            notes.file_plans(None, out)
        self.assertEqual(self.elsewhere.read_text(encoding="utf-8"),
                         "# Meeting\n→ [#9 call the vendor](https://github.com/me/tasks/issues/9)\n",
                         "item and scope replaced by a link to the ticket")
        self.assertEqual(Path(str(self.elsewhere) + ".bak").read_text(encoding="utf-8"), before)
        self.assertNotIn("→", (self.root / "crew.md").read_text(encoding="utf-8"))


REMOVE = """# Planning

Planning call today.
We agreed to "add an error filter"(todo)
- filter by status
- filter by agent

Nice to have: "dark mode"(optional) and "keep this"(todo)
Prose that stays.

## TODO
- [ ] plain checkbox
  - its detail
- [ ] another checkbox
- [x] done stays

"shipped it"(+)
"""


class RemoveAfterFilingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "notes"
        self.root.mkdir()
        self.path = self.root / "planning.md"
        self.path.write_text(REMOVE, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def file(self, statuses, keep=None, after_filing="remove"):
        """Simulate a successful filing: number every exported item, then settle the note."""
        plans = notes.export(self.root, statuses, None, "me/tasks", 5, notes.DEFAULT_COLUMNS, "@me",
                             after_filing=after_filing)
        n = 20
        backed_up = set()
        for plan in plans:
            numbers = {}
            for key, src in plan["sources"].items():
                if keep and src["text"] in keep:
                    continue  # this one "failed": it must stay in the note untouched
                numbers[key] = n
                n += 1
            notes.link_back(self.root, plan, numbers, backed_up)
        return self.path.read_text(encoding="utf-8")

    def test_filed_items_are_replaced_by_a_link_and_the_rest_stays(self):
        after = self.file(["todo", "wip", "done"], keep={"keep this"})
        link = r"→ \[#\d+ %s\]\(https://github\.com/me/tasks/issues/\d+\)"
        for title in ("add an error filter", "plain checkbox", "another checkbox", "shipped it"):
            self.assertRegex(after, "(?m)^" + link % re.escape(title) + "$")
        self.assertNotIn("We agreed to", after, "the marked line itself goes")
        self.assertNotIn("filter by status", after, "scope lines go with their marker")
        self.assertNotIn("its detail", after, "indented details go with their item")
        self.assertNotIn("- [ ] plain checkbox", after)
        self.assertEqual(notes.export(self.root, ["todo", "wip", "done"], None, "me/tasks", 5, notes.DEFAULT_COLUMNS,
                                      "@me")[0]["sources"].__len__(), 1, "only 'keep this' is left to file; links never are")
        self.assertIn('"dark mode"(optional) → me/tasks#', after,
                      "a line with an unfiled marker stays; its filed marker is linked")
        self.assertIn('and "keep this"(todo)\n', after, "the unfiled marker is untouched, not linked")
        for kept in ("Planning call today.", "Prose that stays.", "- [x] done stays", "## TODO"):
            self.assertIn(kept, after)
        self.assertNotIn("\n\n\n", after)
        self.assertEqual((self.root / "planning.md.bak").read_text(encoding="utf-8"), REMOVE,
                         "the .bak is the note before the run, though four plans each changed it")
        self.assertRegex(after, r"- \[x\] done stays\n\n→ \[#\d+ shipped it\]\([^)]+\)\n$",
                         "the last item's link ends the note, with no trailing blank line")

    def test_the_line_goes_once_its_last_marker_is_filed(self):
        first = self.file(["todo"], keep={"keep this"})   # "dark mode" filed, "keep this" not
        self.assertIn('Nice to have: "dark mode"(optional) → me/tasks#', first)
        after = self.file(["todo"])                         # now "keep this" is filed too
        self.assertNotIn("Nice to have", after)
        self.assertRegex(after, r"→ \[#\d+ dark mode\]\(https://github\.com/me/tasks/issues/\d+\)\n"
                                r"→ \[#\d+ keep this\]\(https://github\.com/me/tasks/issues/\d+\)\n",
                         "a line with two filed markers becomes one link per ticket")
        self.assertIn("Prose that stays.", after)

    def test_link_mode_keeps_every_item(self):
        after = self.file(["todo", "wip", "done"], after_filing="link")
        self.assertIn('"add an error filter"(todo) → me/tasks#', after)
        self.assertIn("- filter by status", after)
        self.assertIn("- [ ] plain checkbox → me/tasks#", after)
        self.assertFalse((self.root / "planning.md.bak").exists())

    def test_after_filing_is_a_saved_setting_and_keep_overrides_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_CONFIG_HOME=tmp)
            env.pop("NOTES_DIR", None)
            self.assertEqual(json.loads(run("defaults", env=env).stdout)["after_filing"], "remove")
            self.assertEqual(run("defaults", "--after-filing", "delete", env=env).returncode, 2)
            run("defaults", "--after-filing", "link", "--repo", "me/tasks", env=env)
            out = Path(tmp) / "p"
            run("--root", self.root, "export", "--out", out, env=env)
            metas = [json.loads(m.read_text()) for m in out.glob("*.meta.json")]
            self.assertTrue(metas and all(m["after_filing"] == "link" for m in metas))
            run("defaults", "--after-filing", "remove", env=env)
            run("--root", self.root, "export", "--keep", "--out", Path(tmp) / "q", env=env)
            metas = [json.loads(m.read_text()) for m in (Path(tmp) / "q").glob("*.meta.json")]
            self.assertTrue(metas and all(m["after_filing"] == "link" for m in metas))


LONG = ("We need to add another team member: a DevOps agent. General DevOps, plus ability to set up a full "
        "CI/CD workflow for each given repo, including a review link builder for each PR")
TITLES = '# AI\n1.2. "%s" (todo)\n\n2.1. "Introduce plugin evals" (todo)\n\n"shipped it"(+)\n' % LONG


class TitleAndChecklistTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.note = self.tmp / "ai.txt"
        self.note.write_text(TITLES, encoding="utf-8")
        self.out = self.tmp / "plans"
        root, files = notes.select_files(None, str(self.note))
        self.summary = notes.write_plans(notes.export(root, ["todo", "done"], None, "me/tasks", 5,
                                                      notes.DEFAULT_COLUMNS, "@me", files), self.out)

    def tearDown(self):
        self._tmp.cleanup()

    def issues(self):
        return {i["key"]: i for f in self.out.glob("*.json") if not f.name.endswith(".meta.json")
                for i in json.loads(f.read_text())["issues"]}

    def test_export_flags_text_too_long_for_a_title(self):
        flagged = [n for plan in self.summary for n in plan["needs_short_title"]]
        self.assertEqual([n["text"] for n in flagged], [LONG])
        self.assertEqual(flagged[0]["chars"], len(LONG))
        self.assertTrue(flagged[0]["title_now"].endswith("…"), "the cut stays only as a fallback")

    def test_retitle_sets_a_short_title_and_keeps_the_full_text_in_the_body(self):
        key = next(n["key"] for plan in self.summary for n in plan["needs_short_title"])
        notes.retitle(self.out, key, "Add a DevOps agent with CI/CD and PR review links")
        issue = self.issues()[key]
        self.assertEqual(issue["title"], "Add a DevOps agent with CI/CD and PR review links")
        self.assertIn(LONG, issue["body"], "full text in the description")
        self.assertIn("**Checklist**\n\n- [ ] " + LONG, issue["body"], "and as the checklist")
        meta = json.loads(next(self.out.glob("*todo.meta.json")).read_text())
        self.assertEqual(meta["sources"][key]["title"], "Add a DevOps agent with CI/CD and PR review links")

    def test_retitle_refuses_long_empty_duplicate_or_unknown(self):
        key = next(n["key"] for plan in self.summary for n in plan["needs_short_title"])
        for title, pattern in (("x" * 81, "keep it to 80"), ("  ", "empty"),
                               ("Introduce plugin evals", "already has the title")):
            with self.assertRaisesRegex(notes.NotesError, pattern):
                notes.retitle(self.out, key, title)
        with self.assertRaisesRegex(notes.NotesError, "no exported item"):
            notes.retitle(self.out, "n-nope", "fine")

    def test_a_short_item_without_scope_gets_its_title_as_the_checklist(self):
        bodies = {i["title"]: i["body"] for i in self.issues().values()}
        self.assertIn("**Checklist**\n\n- [ ] Introduce plugin evals", bodies["Introduce plugin evals"])
        self.assertIn("**Checklist**\n\n- [x] shipped it", bodies["shipped it"], "a done item is checked")

    def test_the_link_left_in_the_note_uses_the_short_title(self):
        key = next(n["key"] for plan in self.summary for n in plan["needs_short_title"])
        notes.retitle(self.out, key, "Add a DevOps agent")

        def fake_run(cmd, **kwargs):
            if "--plan" not in cmd:
                return mock.Mock(returncode=0, stdout="{}", stderr="")
            plan = json.loads(Path(cmd[cmd.index("--plan") + 1]).read_text())
            issues = [{"key": i["key"], "number": 40 + n, "title": i["title"], "created": True}
                      for n, i in enumerate(plan["issues"])]
            return mock.Mock(returncode=0, stdout=json.dumps({"created": len(issues), "skipped": 0, "issues": issues}),
                             stderr="")

        with mock.patch.object(notes.subprocess, "run", fake_run):
            notes.file_plans(None, self.out)
        text = self.note.read_text(encoding="utf-8")
        self.assertRegex(text, r"→ \[#\d+ Add a DevOps agent\]\(https://github\.com/me/tasks/issues/\d+\)")
        self.assertNotIn("…", text)


class DefaultsTest(unittest.TestCase):
    def test_defaults_are_saved_beside_the_root_and_used_by_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "notes"
            root.mkdir()
            (root / "t.md").write_text('# T\n"do it"(todo)\n', encoding="utf-8")
            env = dict(os.environ, XDG_CONFIG_HOME=tmp)
            env.pop("NOTES_DIR", None)
            self.assertEqual(run("set-root", root, env=env).returncode, 0)
            shown = json.loads(run("defaults", env=env).stdout)
            self.assertEqual((shown["repo"], shown["board"], shown["assignee"]), (None, None, "@me"))
            self.assertEqual(run("defaults", "--repo", "me/tasks", "--board", "5", env=env).returncode, 0)
            self.assertEqual(run("defaults", "--repo", "not a repo", env=env).returncode, 2)
            self.assertEqual(run("set-root", root, env=env).returncode, 0, "set-root keeps the defaults")
            out = Path(tmp) / "plans"
            result = json.loads(run("export", "--out", out, env=env).stdout)
            plan = result["plans"][0]
            self.assertEqual((plan["repo"], plan["board"], plan["column"], plan["assignees"]),
                             ("me/tasks", 5, "Backlog", ["@me"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
