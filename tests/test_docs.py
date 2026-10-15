#!/usr/bin/env python3
"""The handbook is generated from source, so it must name what the source declares."""

from __future__ import annotations

import datetime
import os
import tempfile
import unittest
from pathlib import Path

import _helpers  # noqa: F401
from tools.apkit import docs
from tools.apkit.cli import build_parser
from tools.apkit.model import discover, load_plugin
from tools.apkit.targets import load_targets

ROOT = Path(__file__).resolve().parent.parent


class MarkdownTest(unittest.TestCase):
    def test_tables_code_and_lists(self):
        out = docs.markdown(
            "# Title\n\n| a | b |\n| --- | --- |\n| `x` | **y** |\n\n"
            "```bash\necho <hi>\n```\n\n- one\n- two\n",
            shift=1,
        )
        self.assertIn("<h2>Title</h2>", out)
        self.assertIn("<td><code>x</code></td><td><strong>y</strong></td>", out)
        self.assertIn("echo &lt;hi&gt;", out)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)

    def test_relative_links_become_text_and_absolute_stay_links(self):
        out = docs.inline("[guide](docs/a.md) and [`spec`](https://x.io)")
        self.assertIn("guide and", out)
        self.assertIn('<a href="https://x.io"><code>spec</code></a>', out)

    def test_readme_section_ignores_headings_inside_fences(self):
        text = "## Quick start\n\n```\n## not a heading\n```\nbody\n\n## Next\nno"
        section = docs.readme_section(text, "quick start")
        self.assertIn("body", section)
        self.assertNotIn("no", section.split("body")[-1])


class SourceReaderTest(unittest.TestCase):
    def test_mcp_tools_read_without_importing_the_server(self):
        names = [n for n, _ in docs.mcp_tools(load_plugin(ROOT / "plugins" / "scrum-master"))]
        self.assertTrue(names)

    def test_hooks_name_their_script(self):
        rows = docs.hook_rows(load_plugin(ROOT / "plugins" / "scrum-master"))
        self.assertEqual(rows[0][0], "SessionStart")
        self.assertTrue(rows[0][2].endswith(".py"))


class RenderTest(unittest.TestCase):
    def test_every_command_and_agent_appears(self):
        plugins = discover(ROOT / "plugins")
        page = docs.render_html(
            ROOT, plugins, load_targets(ROOT / "targets"), build_parser(),
            today=datetime.date(2026, 1, 1),
        )
        self.assertIn("Generated 2026-01-01", page)
        self.assertIn("apkit docs", page)
        for plugin in plugins:
            for command in plugin.commands:
                self.assertIn("/" + command.name, page)
            for agent in plugin.agents:
                self.assertIn(str(agent.meta.get("name") or agent.name), page)


class BrowserTest(unittest.TestCase):
    def test_explicit_browser_that_does_not_exist_is_not_guessed_past(self):
        missing = os.path.join(tempfile.gettempdir(), "no-such-browser-apkit")
        self.assertIsNone(docs.find_browser(missing))


if __name__ == "__main__":
    unittest.main()
