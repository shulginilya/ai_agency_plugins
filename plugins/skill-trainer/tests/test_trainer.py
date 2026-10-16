#!/usr/bin/env python3
"""Smoke tests for trainer.py: settings that change without losing history, both plans, spaced review, the hook."""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN / "skills" / "training-plan" / "scripts" / "trainer.py"
HOOK = PLUGIN / "scripts" / "due_watch.py"
sys.path.insert(0, str(SCRIPT.parent))
import trainer  # noqa: E402

MONDAY = dt.date(2026, 10, 19)


class Home:
    """A throwaway training folder, with the config dir isolated too."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "training"
        self.env = {**os.environ, "SKILL_TRAINER_HOME": str(self.home),
                    "XDG_CONFIG_HOME": str(Path(self.tmp.name) / "cfg")}
        self.patch = mock.patch.dict(os.environ, self.env)
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()
        self.tmp.cleanup()

    def run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True,
                              text=True, check=False, env=self.env)

    def state(self):
        return trainer.read_state(self.home)


class SettingsTest(unittest.TestCase):
    def test_defaults_are_the_users_stack_and_languages(self):
        with Home() as h:
            self.assertEqual(h.run("init").returncode, 0)
            s = h.state()["settings"]
            self.assertEqual(s["stack"], ["React", "TypeScript", "Node", "Python"])
            self.assertEqual(s["interview_languages"], ["Node", "Python", "React"])
            self.assertEqual(s["cadence"], "daily")

    def test_stack_and_language_change_later_without_losing_history(self):
        with Home() as h:
            h.run("init")
            self.assertEqual(h.run("log", "--topic", "react-rendering", "--score", "4",
                                   "--date", "2026-10-19").returncode, 0)
            self.assertEqual(h.run("config", "set", "stack", "TypeScript,Go").returncode, 0)
            self.assertEqual(h.run("config", "set", "interview-languages", "Python,Go").returncode, 0)
            state = h.state()
            self.assertEqual(state["settings"]["stack"], ["TypeScript", "Go"])
            self.assertEqual(state["settings"]["interview_languages"], ["Python", "Go"])
            self.assertIn("react-rendering", state["progress"])
            active = {t["id"] for t in trainer.active_topics(state)}
            self.assertNotIn("react-rendering", active, "a dropped technology stops coming up")
            self.assertIn("go-internals", active, "an unknown technology gets generated deep-dives")
            h.run("config", "set", "stack", "React")
            self.assertIn("react-rendering", {t["id"] for t in trainer.active_topics(h.state())})

    def test_coding_items_rotate_through_the_interview_languages(self):
        with Home() as h:
            h.run("init")
            mondays = [MONDAY + dt.timedelta(days=7 * n) for n in range(4)]  # Monday is a coding day
            langs = {trainer.session_for(h.state(), d)["items"][0]["language"] for d in mondays}
            self.assertEqual(langs, {"Node", "Python"}, "React is a framework, not an algorithm language")
            h.run("config", "set", "interview-languages", "TypeScript")
            self.assertEqual(trainer.session_for(h.state(), MONDAY)["items"][0]["language"], "TypeScript")

    def test_react_adds_ui_builds_and_leaving_it_out_removes_them(self):
        with Home() as h:
            h.run("init")
            coding = [t["id"] for t in trainer.new_topics(h.state(), "coding")]
            self.assertTrue(any(i.startswith("react-ui-") for i in coding[:4]), "a UI build comes early")
            self.assertFalse(coding[0].startswith("react-ui-"))
            ui = dict(trainer.topic_by_id(h.state(), "react-ui-form"))
            self.assertEqual(trainer.coding_language(h.state()["settings"], MONDAY, ui), "React (TypeScript)")
            h.run("config", "set", "interview-languages", "Node,Python")
            self.assertFalse(any(t["id"].startswith("react-ui-") for t in trainer.active_topics(h.state())))

    def test_a_single_saved_language_is_migrated_to_a_list(self):
        with Home() as h:
            h.run("init")
            raw = json.loads((h.home / "state.json").read_text())
            del raw["settings"]["interview_languages"]
            raw["settings"]["interview_language"] = "Python"
            (h.home / "state.json").write_text(json.dumps(raw))
            self.assertEqual(h.state()["settings"]["interview_languages"], ["Python"])

    def test_bad_values_are_refused(self):
        with Home() as h:
            h.run("init")
            for key, value in (("cadence", "hourly"), ("focus", "fun"), ("weekly-sessions", "9"),
                               ("interview-date", "next week"), ("colour", "blue")):
                self.assertEqual(h.run("config", "set", key, value).returncode, 2, key)

    def test_refuses_a_foreign_state_file(self):
        with Home() as h:
            h.home.mkdir(parents=True)
            (h.home / "state.json").write_text('{"kind": "interview-state"}')
            result = h.run("status")
            self.assertEqual(result.returncode, 2)
            self.assertIn("refusing", result.stderr)

    def test_set_home_accepts_a_path_and_where_reports_it(self):
        with Home() as h:
            env = dict(h.env)
            env.pop("SKILL_TRAINER_HOME")
            target = Path(h.tmp.name) / "elsewhere"
            subprocess.run([sys.executable, str(SCRIPT), "set-home", str(target)], env=env, check=True,
                           capture_output=True)
            out = subprocess.run([sys.executable, str(SCRIPT), "where"], env=env, capture_output=True,
                                 text=True).stdout
            self.assertIn(str(target), out)


class PlanTest(unittest.TestCase):
    def test_daily_and_weekly_plans_both_exist(self):
        with Home() as h:
            h.run("init", "--weekly-sessions", "3")
            result = h.run("plan", "--write", "--date", MONDAY.isoformat())
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (h.home / "plan.md").read_text()
            self.assertIn("## Daily plan", text)
            self.assertIn("## Weekly plan (3 sessions", text)

    def test_interview_focus_schedules_only_coding_and_design(self):
        with Home() as h:
            h.run("init", "--focus", "interview")
            areas = set()
            for offset in range(14):
                for item in trainer.session_for(h.state(), MONDAY + dt.timedelta(days=offset))["items"]:
                    areas.add(item["area"])
            self.assertEqual(areas, {"coding", "design"})

    def test_weekly_sessions_advance_through_the_week(self):
        with Home() as h:
            h.run("init", "--cadence", "weekly")
            first = trainer.session_for(h.state(), MONDAY)
            h.run("log", "--topic", first["items"][0]["id"], "--score", "4", "--date", MONDAY.isoformat())
            second = trainer.session_for(h.state(), MONDAY + dt.timedelta(days=2))
            self.assertIn("session 1", first["label"])
            self.assertIn("session 2", second["label"])


class ReviewTest(unittest.TestCase):
    def test_a_weak_result_returns_sooner_than_a_strong_one(self):
        with Home() as h:
            h.run("init")
            h.run("log", "--topic", "sliding-window", "--score", "2", "--date", MONDAY.isoformat())
            h.run("log", "--topic", "two-pointers", "--score", "5", "--date", MONDAY.isoformat())
            p = h.state()["progress"]
            self.assertEqual(p["sliding-window"]["due"], "2026-10-20")
            self.assertLess(p["sliding-window"]["due"], p["two-pointers"]["due"])

    def test_intervals_grow_with_repeated_success_and_reset_on_a_lapse(self):
        prog = None
        intervals = []
        for score in (4, 4, 4):
            interval = trainer.next_interval(prog, score)
            intervals.append(interval)
            prog = {"reps": len(intervals), "interval": interval}
        self.assertEqual(intervals, sorted(intervals))
        self.assertGreater(intervals[-1], intervals[0])
        self.assertEqual(trainer.next_interval(prog, 1), 1)

    def test_due_reviews_come_first_and_status_exits_1(self):
        with Home() as h:
            h.run("init")
            h.run("log", "--topic", "sd-chat", "--score", "2", "--date", MONDAY.isoformat())
            tuesday = MONDAY + dt.timedelta(days=1)
            session = trainer.session_for(h.state(), tuesday)
            self.assertEqual(session["items"][0]["id"], "sd-chat")
            self.assertEqual(h.run("status", "--date", tuesday.isoformat()).returncode, 1)

    def test_weak_areas_come_first_among_new_topics(self):
        with Home() as h:
            h.run("init", "--weak-areas", "dp-2d-strings")
            self.assertEqual(trainer.new_topics(h.state(), "coding")[0]["id"], "dp-2d-strings")

    def test_log_rejects_unknown_topics_scores_and_vague_dates(self):
        with Home() as h:
            h.run("init")
            self.assertEqual(h.run("log", "--topic", "nope", "--score", "3").returncode, 2)
            self.assertEqual(h.run("log", "--topic", "greedy", "--score", "7").returncode, 2)
            self.assertEqual(h.run("log", "--topic", "greedy", "--score", "3", "--date", "yesterday").returncode, 2)


class InterviewTest(unittest.TestCase):
    def test_interview_track_is_coding_and_design_without_screening(self):
        with Home() as h:
            h.run("init")
            report = trainer.interview_report(h.state(), MONDAY)
            self.assertEqual(set(report["areas"]), {"coding", "design"})
            self.assertGreaterEqual(len(report["areas"]["coding"]), 15)
            self.assertGreaterEqual(len(report["areas"]["design"]), 12)

    def test_mocks_are_counted(self):
        with Home() as h:
            h.run("init")
            h.run("log", "--topic", "sd-news-feed", "--score", "3", "--kind", "mock", "--date", MONDAY.isoformat())
            rows = {r["id"]: r for r in trainer.interview_report(h.state(), MONDAY)["areas"]["design"]}
            self.assertEqual(rows["sd-news-feed"]["mocks"], 1)


class CatalogTest(unittest.TestCase):
    def test_ids_are_unique_and_areas_known(self):
        topics = trainer.load_catalog()["topics"]
        ids = [t["id"] for t in topics]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({t["area"] for t in topics} <= set(trainer.AREAS))


class HookTest(unittest.TestCase):
    def hook(self, env):
        return subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True,
                              env=env, check=False)

    def test_silent_without_state_and_speaks_once_a_day(self):
        with Home() as h:
            first = self.hook(h.env)
            self.assertEqual((first.returncode, first.stdout), (0, ""))
            h.run("init")
            nudge = self.hook(h.env)
            self.assertEqual(nudge.returncode, 0)
            self.assertIn("/skill-trainer:today", nudge.stdout)
            self.assertEqual(self.hook(h.env).stdout, "", "at most once a day")

    def test_silent_once_today_is_logged(self):
        with Home() as h:
            h.run("init")
            h.run("log", "--topic", "greedy", "--score", "3")
            self.assertEqual(self.hook(h.env).stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
