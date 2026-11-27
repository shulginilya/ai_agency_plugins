#!/usr/bin/env python3
"""Which project a directory is (AC5) and where the connection string lives (AC4)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import isolated_env
import memconfig
import memproject


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=str(root), check=True, capture_output=True)


class RemoteTests(unittest.TestCase):
    def test_every_form_of_one_repository_is_one_project(self):
        forms = [
            "git@github.com:Owner/Repo.git", "https://github.com/owner/repo", "https://github.com/owner/repo.git/",
            "ssh://git@github.com/owner/repo.git", "ssh://git@github.com:22/owner/repo",
            "git://github.com/owner/repo.git", "HTTPS://GitHub.com/Owner/Repo",
        ]
        for url in forms:
            with self.subTest(url=url):
                self.assertEqual(memproject.normalize_remote(url, Path("/x")), "github.com/owner/repo")

    def test_credentials_in_a_remote_are_dropped(self):
        got = memproject.normalize_remote("https://me:" + "s3cretpw@github.com/o/r.git", Path("/x"))
        self.assertEqual(got, "github.com/o/r")
        got = memproject.normalize_remote("https://me:p@ss@gitlab.example.com/g/sub/r", Path("/x"))
        self.assertEqual(got, "gitlab.example.com/g/sub/r")

    def test_different_repositories_differ(self):
        a = memproject.normalize_remote("git@github.com:o/a.git", Path("/x"))
        b = memproject.normalize_remote("git@gitlab.com:o/a.git", Path("/x"))
        self.assertNotEqual(a, b)

    def test_a_local_path_remote_is_a_path_not_a_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = memproject.normalize_remote("../bare.git", Path(tmp) / "work")
            self.assertTrue(got.startswith("path:"), got)
            self.assertIn("bare", got)
        self.assertTrue(memproject.normalize_remote("C:\\repos\\x", Path("/x")).startswith("path:"))


class DirectoryTests(unittest.TestCase):
    def test_the_origin_remote_names_the_project_from_any_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "remote", "add", "origin", "git@github.com:o/r.git")
            (root / "a" / "b").mkdir(parents=True)
            self.assertEqual(memproject.identify(root), "github.com/o/r")
            self.assertEqual(memproject.identify(root / "a" / "b"), "github.com/o/r")

    def test_without_a_remote_it_is_the_root_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git(root, "init", "-q")
            (root / "sub").mkdir()
            expected = "dir:" + root.as_posix()
            self.assertEqual(memproject.identify(root).lower(), expected.lower())
            self.assertEqual(memproject.identify(root / "sub").lower(), expected.lower())

    def test_outside_git_it_is_the_directory_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["GIT_CEILING_DIRECTORIES"] = str(Path(tmp).resolve().parent)
            try:
                got = memproject.identify(Path(tmp))
            finally:
                del os.environ["GIT_CEILING_DIRECTORIES"]
            self.assertEqual(got.lower(), "dir:" + Path(tmp).resolve().as_posix().lower())
            self.assertIsNone(memproject.head_commit(Path(tmp) / "missing"))


class ConfigTests(unittest.TestCase):
    URI = "mongodb://agent_memory:" + "pw-123456@127.0.0.1:27027/agent_memory?authSource=admin"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = isolated_env(Path(self.tmp.name))

    def test_paths_are_under_the_user_directories_never_the_repository(self):
        path = memconfig.config_path(self.env)
        self.assertEqual(path, Path(self.tmp.name) / "config" / "ai-agency" / "memory.json")
        self.assertEqual(memconfig.venv_dir(self.env), Path(self.tmp.name) / "data" / "ai-agency" / "memory" / "venv")
        home = {k: v for k, v in self.env.items() if not k.startswith("XDG_")}
        self.assertEqual(memconfig.config_path(home), Path.home() / ".config" / "ai-agency" / "memory.json")

    def test_save_and_load_and_the_file_is_the_users_only(self):
        self.assertEqual(memconfig.load(self.env), {})
        self.assertIsNone(memconfig.uri(self.env))
        memconfig.save({"uri": self.URI}, self.env)
        memconfig.save({"uri": self.URI, "port": 27027}, self.env)
        self.assertEqual(memconfig.load(self.env), {"uri": self.URI, "port": 27027})
        self.assertEqual(memconfig.uri(self.env), self.URI)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(memconfig.config_path(self.env).stat().st_mode), 0o600)
        self.assertEqual([p.name for p in memconfig.config_path(self.env).parent.iterdir()], ["memory.json"])

    def test_the_environment_variable_wins(self):
        memconfig.save({"uri": self.URI}, self.env)
        env = dict(self.env, AI_AGENCY_MEMORY_URI="mongodb://other/db")
        self.assertEqual(memconfig.uri(env), "mongodb://other/db")

    def test_a_corrupt_file_is_an_error_that_does_not_quote_it(self):
        path = memconfig.config_path(self.env)
        path.parent.mkdir(parents=True)
        for text in ('{"uri": "' + self.URI, '["' + self.URI + '"]', json.dumps({"uri": 5})):
            with self.subTest(text=text[:20]):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(memconfig.ConfigError) as caught:
                    memconfig.uri(self.env)
                self.assertNotIn("pw-123456", str(caught.exception))

    def test_redaction_removes_the_password_from_any_message(self):
        message = "cannot reach %s (password pw-123456)" % self.URI
        clean = memconfig.redact(message, self.URI)
        self.assertNotIn("pw-123456", clean)
        self.assertNotIn("pw-123456", memconfig.redact("failed: " + self.URI))


if __name__ == "__main__":
    unittest.main(verbosity=2)
