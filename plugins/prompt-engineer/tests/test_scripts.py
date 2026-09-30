#!/usr/bin/env python3
"""Smoke tests for the scripts, hook and MCP server the prompt-engineer plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN / "skills" / "prompt-crafting" / "scripts"
BRIEF = SCRIPTS / "brief.py"
LINT = SCRIPTS / "prompt_lint.py"
HOOK = PLUGIN / "scripts" / "prompt_file_check.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

sys.path.insert(0, str(SCRIPTS))

import brief  # noqa: E402
import prompt_lint  # noqa: E402

CLEAN_PROMPT = """Summarise the support ticket below for the on-call engineer, who will
use it to decide whether to page the database team.

<ticket>
{{ticket}}
</ticket>

Keep error messages, timestamps and customer IDs exactly as written. If the
ticket does not say when the problem started, write "start time unknown".

Output: 3 bullets, most urgent first, each under 25 words.
"""


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def rules(text):
    return {f["rule"] for f in prompt_lint.lint(text)}


class BriefTest(unittest.TestCase):
    def test_classifies_and_finds_gaps(self):
        result = brief.brief("write a cold email to CTOs about our new API, friendly tone, under 120 words")
        self.assertEqual(result["task"], "writing")
        self.assertIn("audience", result["present"])
        self.assertIn("length", result["present"])
        self.assertIn("tone", result["present"])
        asked = {item["slot"] for item in result["ask"]}
        self.assertIn("success", asked)
        self.assertNotIn("audience", asked)

    def test_system_prompt_is_an_agent_task(self):
        result = brief.brief("draft a system prompt for a support bot that writes friendly replies")
        self.assertEqual(result["task"], "agent")

    def test_extraction_needs_a_schema(self):
        result = brief.brief("extract the vendor and total from each invoice")
        self.assertEqual(result["task"], "extraction")
        self.assertIn("output_format", {item["slot"] for item in result["ask"]})

    def test_no_signal_is_unclear(self):
        result = brief.brief("hmm")
        self.assertEqual(result["task"], "unclear")
        self.assertTrue(result["notes"])

    def test_cli_json_and_empty_input(self):
        ok = run([sys.executable, str(BRIEF), "--text", "summarize this transcript for execs", "--json"])
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["task"], "summarization")
        empty = run([sys.executable, str(BRIEF), "--text", "   "])
        self.assertEqual(empty.returncode, 2)


class LintTest(unittest.TestCase):
    def test_clean_prompt_has_no_errors_or_warnings(self):
        findings = prompt_lint.lint(CLEAN_PROMPT)
        self.assertEqual(
            [f for f in findings if f["severity"] != "info"], [], findings
        )
        self.assertIn("template-variables", rules(CLEAN_PROMPT))

    def test_placeholder_is_an_error(self):
        self.assertIn("unfilled-placeholder", rules("Write a bio for [insert name] in 50 words, as one paragraph."))

    def test_unclosed_and_stray_tags(self):
        found = rules("Answer in one sentence.\n<document>\n{{doc}}\nThen stop.</notes>")
        self.assertIn("unclosed-tag", found)
        self.assertIn("stray-closing-tag", found)

    def test_inline_placeholder_notation_is_not_a_tag(self):
        text = "Run `scan.py <file>`, then reply with one line: <file>:<line> — <the cause>."
        self.assertNotIn("unclosed-tag", rules(text))

    def test_enum_capitals_are_not_shouting(self):
        text = CLEAN_PROMPT + "\nVerdict: CONFIRMED | REFUTED | INCONCLUSIVE. CONFIRMED needs both.\n"
        self.assertNotIn("emphasis-inflation", rules(text))

    def test_dangling_reference(self):
        self.assertIn("dangling-reference", rules("Summarise the email in 3 bullets for my manager.\nHere is the email:"))

    def test_warnings(self):
        text = (
            "IMPORTANT: NEVER use jargon. ALWAYS be CONCISE. You MUST be comprehensive.\n"
            "Do not mention pricing.\nNever apologise.\nAvoid emojis.\n"
            "Write a proper high-quality answer about our roadmap, benefits, etc."
        )
        found = rules(text)
        for rule in ("emphasis-inflation", "negative-only", "conflicting-length", "vague-instruction", "no-output-shape"):
            self.assertIn(rule, found)

    def test_code_fences_are_data(self):
        text = CLEAN_PROMPT + "\n```\nIMPORTANT MUST NEVER ALWAYS SHOUTING etc.\n```\n"
        self.assertNotIn("emphasis-inflation", rules(text))
        self.assertNotIn("vague-instruction", rules(text))

    def test_exit_codes(self):
        bad = run([sys.executable, str(LINT), "--text", "Rewrite [your text here] as a haiku in three lines."])
        self.assertEqual(bad.returncode, 1, bad.stdout)
        good = run([sys.executable, str(LINT), "--text", CLEAN_PROMPT])
        self.assertEqual(good.returncode, 0, good.stdout)
        missing = run([sys.executable, str(LINT), str(PLUGIN / "no-such-file.md")])
        self.assertEqual(missing.returncode, 2)


class HookTest(unittest.TestCase):
    def fire(self, path: Path):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(path)}}
        return run([sys.executable, str(HOOK)], input=json.dumps(event))

    def test_lints_prompt_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "welcome.prompt.md"
            prompt.write_text("Write a welcome email for [insert name].", encoding="utf-8")
            result = self.fire(prompt)
            self.assertEqual(result.returncode, 0)
            self.assertIn("unfilled placeholder", result.stdout)

            doc = Path(tmp) / "notes.md"
            doc.write_text("Write a welcome email for [insert name].", encoding="utf-8")
            self.assertEqual(self.fire(doc).stdout, "")

            folder = Path(tmp) / "prompts"
            folder.mkdir()
            nested = folder / "triage.md"
            nested.write_text("Classify the ticket.\nThe ticket is below:", encoding="utf-8")
            self.assertIn("pointing at material", self.fire(nested).stdout)

    def test_garbage_never_blocks(self):
        result = run([sys.executable, str(HOOK)], input="not json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class McpServerTest(unittest.TestCase):
    def call(self, *messages):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_lists_three_tools(self):
        (reply,) = self.call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {tool["name"] for tool in reply["result"]["tools"]}
        self.assertEqual(names, {"prompt_brief", "prompt_lint", "prompt_guide"})

    def test_tools_answer(self):
        replies = self.call(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "prompt_brief", "arguments": {"text": "classify tickets by urgency"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "prompt_lint", "arguments": {"text": "Fix [insert bug] please, in one diff."}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "prompt_guide", "arguments": {"topic": "patterns"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "prompt_guide", "arguments": {"topic": "nope"}}},
        )
        by_id = {reply["id"]: reply["result"] for reply in replies}
        self.assertEqual(json.loads(by_id[1]["content"][0]["text"])["task"], "classification")
        self.assertEqual(json.loads(by_id[2]["content"][0]["text"])["errors"], 1)
        self.assertIn("## extraction", by_id[3]["content"][0]["text"])
        self.assertTrue(by_id[4]["isError"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
