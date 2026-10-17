#!/usr/bin/env python3
"""Smoke tests for notes.py: parsing, lossless organize, capture, export and link-back."""

from __future__ import annotations

import json
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
        plans = notes.export(self.root, ["todo", "wip"], "crew", None, None, notes.DEFAULT_COLUMNS)
        for n, plan in enumerate(plans):
            numbers = {k: 100 + 10 * n + i for i, k in enumerate(plan["sources"])}
            notes.link_back(self.root, plan, numbers)
        text = (self.root / "crew.md").read_text(encoding="utf-8")
        self.assertIn("TODO: write the cache ticket → #100", text)
        self.assertIn("- [/] wire designer → #110", text)
        self.assertEqual(notes.export(self.root, ["todo", "wip"], "crew", None, None, notes.DEFAULT_COLUMNS), [])

    def test_link_uses_the_full_ref_when_the_repo_came_from_the_flag(self):
        plan = notes.export(self.root, ["todo"], "loose", "me/other", None, notes.DEFAULT_COLUMNS)[0]
        notes.link_back(self.root, plan, {k: 7 for k in plan["sources"]})
        self.assertIn("- [ ] needs a repo → me/other#7", (self.root / "loose.md").read_text(encoding="utf-8"))

    def test_file_refuses_without_approval(self):
        result = run("--root", self.root, "file", "--plans", self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("show the export to the user first", result.stderr)


INLINE = """# Ideas
Talked to the team. We should "add an error filter"(todo) and maybe "try Neon branches"(TODO).
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

    def export(self, statuses=("todo", "wip", "done"), assignee="@me"):
        return notes.export(self.root, list(statuses), None, "me/tasks", 5, notes.DEFAULT_COLUMNS, assignee)

    def test_markers_found_mid_line_in_any_case_and_not_in_fences(self):
        found = [(i["status"], i["text"]) for i in notes.inline_items(INLINE)]
        self.assertEqual(found, [
            ("todo", "add an error filter"), ("todo", "try Neon branches"),
            ("wip", "wiring the board"), ("wip", "fixing the export"), ("done", "shipped the notes plugin"),
            ("done", "wrote the README"), ("done", "made the board"), ("todo", "checkbox with a marker"),
        ])

    def test_columns_assignee_and_close_per_status(self):
        plans = {p["status"]: p for p in self.export()}
        self.assertEqual(plans["todo"]["column"], "Backlog")
        self.assertEqual(plans["wip"]["column"], "In progress")
        self.assertEqual(plans["done"]["column"], "Done")
        self.assertTrue(plans["done"]["close"])
        self.assertFalse(plans["todo"]["close"] or plans["wip"]["close"])
        titles = [i["title"] for i in plans["todo"]["issues"]]
        self.assertEqual(titles, ["add an error filter", "try Neon branches", "checkbox with a marker",
                                  "a plain checkbox"], "a checkbox holding a marker is filed once")
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
