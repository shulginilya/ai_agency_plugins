#!/usr/bin/env python3
"""Tests for the scripts and the Stop hook the plugin-developer plugin ships.

Covers requirements.py, req_trace.py, scaffold.py, gate.py, mcp_smoke.py and
scripts/stop_gate.py. The scaffold and gate tests build a throwaway copy of the
repo's toolkit (tools/apkit, targets/, plugins/_template) and skip when they
are not run from inside the repo.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REPO = PLUGIN.parent.parent
ANALYSIS = PLUGIN / "skills" / "requirements-analysis" / "scripts"
SCAFFOLDING = PLUGIN / "skills" / "plugin-scaffolding" / "scripts"
VERIFICATION = PLUGIN / "skills" / "plugin-verification" / "scripts"
REQUIREMENTS = ANALYSIS / "requirements.py"
SCAFFOLD = SCAFFOLDING / "scaffold.py"
REQ_TRACE = VERIFICATION / "req_trace.py"
GATE = VERIFICATION / "gate.py"
MCP_SMOKE = VERIFICATION / "mcp_smoke.py"
STOP_HOOK = PLUGIN / "scripts" / "stop_gate.py"

for directory in (ANALYSIS, SCAFFOLDING, VERIFICATION):
    sys.path.insert(0, str(directory))

import gate  # noqa: E402
import mcp_smoke  # noqa: E402
import req_trace  # noqa: E402


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def py(script, *args, **kwargs):
    return run([sys.executable, str(script)] + [str(a) for a in args], **kwargs)


@contextmanager
def temp_dir():
    """mkdtemp + rmtree that clears read-only bits, so cleanup works on Windows."""
    path = tempfile.mkdtemp()

    def clear(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    try:
        yield Path(path)
    finally:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=clear)
        else:
            shutil.rmtree(path, onerror=clear)


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


PLAN = {
    "schema": 1,
    "plugin": {
        "name": "greeter",
        "display_name": "Greeter",
        "description": "Greets people by name. Use when the user asks to greet someone.",
    },
    "prompt": "Make a plugin that greets a person by name, always in the same format.",
    "requirements": [
        {"id": "R1", "kind": "action", "text": "Greet a person by name on request",
         "acceptance": "/greet Ada replies with a line containing Ada"},
        {"id": "R2", "kind": "computation", "text": "The greeting has the same format every time",
         "acceptance": "greet.py --name Ada prints 'hello, Ada' and exits 0; an empty name exits 2"},
    ],
    "assumptions": [],
    "open_questions": [],
    "components": [
        {"type": "skill", "name": "greeting", "covers": ["R1"], "why": "the method behind a greeting"},
        {"type": "command", "name": "greet", "covers": ["R1"], "why": "the user starts a greeting"},
        {"type": "script", "name": "skills/greeting/scripts/greet.py", "covers": ["R2"],
         "why": "the format must be identical every time"},
        {"type": "test", "name": "tests/test_greet.py", "verifies": ["skills/greeting/scripts/greet.py"],
         "why": "verifies the format and the refusal"},
    ],
}


def plan(**changes):
    data = copy.deepcopy(PLAN)
    data.update(changes)
    return data


GREETER_FILES = {
    "skills/greeting/SKILL.md": (
        "---\nname: greeting\ndescription: Greets a person by name in a fixed format. "
        "Use when the user asks to greet someone.\nlicense: MIT\n---\n\n# Greeting\n\n"
        "Run `python scripts/greet.py --name <name>` and reply with its output.\n"
    ),
    "skills/greeting/scripts/greet.py": (
        "#!/usr/bin/env python3\n\"\"\"Print a greeting. Exit 0 greeted, 2 empty name.\"\"\"\n"
        "from __future__ import annotations\nimport argparse\n\n\n"
        "def main() -> int:\n    p = argparse.ArgumentParser()\n    p.add_argument('--name', default='')\n"
        "    a = p.parse_args()\n    if not a.name.strip():\n        return 2\n"
        "    print('hello, %s' % a.name)\n    return 0\n\n\n"
        "if __name__ == '__main__':\n    raise SystemExit(main())\n"
    ),
    "commands/greet.md": (
        "---\ndescription: Greet a person by name in the house format. Use when the user asks to greet, welcome or say hello to someone.\n"
        "argument_hint: \"[name]\"\n---\n\n"
        "Greet {{ARGS}} by following the `greeting` skill. With no name, ask for one.\n"
    ),
    "tests/test_greet.py": (
        "#!/usr/bin/env python3\nimport subprocess, sys, unittest\nfrom pathlib import Path\n"
        "SCRIPT = Path(__file__).resolve().parent.parent / 'skills' / 'greeting' / 'scripts' / 'greet.py'\n\n\n"
        "class GreetTest(unittest.TestCase):\n"
        "    def test_greets(self):\n"
        "        out = subprocess.run([sys.executable, str(SCRIPT), '--name', 'Ada'], capture_output=True, text=True)\n"
        "        self.assertEqual(out.returncode, 0)\n        self.assertIn('hello, Ada', out.stdout)\n\n"
        "    def test_refuses_empty(self):\n"
        "        out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)\n"
        "        self.assertEqual(out.returncode, 2)\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n"
    ),
}


def mini_repo(root: Path) -> bool:
    """A throwaway repo with the real toolkit and template; False outside the repo."""
    if not (REPO / "tools" / "apkit").is_dir() or not (REPO / "plugins" / "_template").is_dir():
        return False
    (root / "tools").mkdir()
    shutil.copy2(REPO / "tools" / "__init__.py", root / "tools" / "__init__.py")
    shutil.copytree(REPO / "tools" / "apkit", root / "tools" / "apkit",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "targets", root / "targets")
    shutil.copytree(REPO / "plugins" / "_template", root / "plugins" / "_template",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return True


# ---- requirements.py ----------------------------------------------------------

class RequirementsTest(unittest.TestCase):
    def test_new_keeps_the_prompt_verbatim_and_a_skeleton_is_not_ready(self):
        with temp_dir() as root:
            (root / "plugins").mkdir()
            prompt = "Build a thing.\n  Keep  spacing\n"
            result = py(REQUIREMENTS, "new", "thing", "--prompt", prompt, "--root", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            path = root / ".plugin-dev" / "thing" / "requirements.json"
            self.assertEqual(py(REQUIREMENTS, "prompt", path).stdout, prompt + "\n")
            self.assertEqual(py(REQUIREMENTS, "check", path).returncode, 1)

    def test_new_refuses_a_taken_name(self):
        with temp_dir() as root:
            (root / "plugins" / "thing").mkdir(parents=True)
            result = py(REQUIREMENTS, "new", "thing", "--prompt", "x", "--root", root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("already exists", result.stderr)

    def test_a_complete_file_is_ready(self):
        with temp_dir() as root:
            path = write_json(root / "r.json", plan())
            result = py(REQUIREMENTS, "check", path)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("READY", result.stdout)

    def test_an_uncheckable_acceptance_test_is_an_issue(self):
        with temp_dir() as root:
            data = plan()
            data["requirements"][0]["acceptance"] = "the greeting works properly"
            result = py(REQUIREMENTS, "check", write_json(root / "r.json", data))
            self.assertEqual(result.returncode, 1)
            self.assertIn("'properly'", result.stdout)

    def test_a_number_makes_a_vague_word_checkable(self):
        data = plan()
        data["requirements"][0]["acceptance"] = "replies fast, within 2 seconds"
        sys.path.insert(0, str(ANALYSIS))
        import requirements as reqs
        self.assertEqual(reqs.issues(data), [])

    def test_open_questions_stop_planning(self):
        with temp_dir() as root:
            path = write_json(root / "r.json", plan(open_questions=["Which language?"]))
            result = py(REQUIREMENTS, "check", path)
            self.assertEqual(result.returncode, 3)
            self.assertIn("Which language?", result.stdout)

    def test_malformed_json_is_unusable(self):
        with temp_dir() as root:
            path = root / "r.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(py(REQUIREMENTS, "check", path).returncode, 2)

    def test_duplicate_ids_and_unknown_kinds_are_issues(self):
        with temp_dir() as root:
            data = plan()
            data["requirements"][1]["id"] = "R1"
            data["requirements"][1]["kind"] = "magic"
            result = py(REQUIREMENTS, "check", write_json(root / "r.json", data))
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate id", result.stdout)
            self.assertIn("'magic'", result.stdout)


# ---- req_trace.py -------------------------------------------------------------

class TraceTest(unittest.TestCase):
    def check(self, data, *extra):
        with temp_dir() as root:
            return py(REQ_TRACE, "check", write_json(root / "r.json", data), *extra)

    def test_a_complete_plan_passes(self):
        result = self.check(plan())
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_an_uncovered_requirement_is_a_gap(self):
        data = plan()
        data["components"] = [c for c in data["components"] if c["type"] != "script"]
        data["components"] = [c for c in data["components"] if c["type"] != "test"]
        result = self.check(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("R2 is not covered", result.stdout)

    def test_a_component_without_a_reason_is_a_gap(self):
        data = plan()
        data["components"][0]["why"] = ""
        self.assertIn("no 'why'", self.check(data).stdout)

    def test_a_hook_for_a_user_action_is_over_building(self):
        data = plan()
        data["components"].append({"type": "hook", "name": "PostToolUse", "covers": ["R1"], "why": "x"})
        result = self.check(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("only justified by a requirement of kind event", result.stdout)

    def test_an_mcp_server_needs_an_integration_requirement(self):
        data = plan()
        data["components"].append({"type": "mcp", "name": "greeter", "covers": ["R2"], "why": "x"})
        result = self.check(data)
        self.assertIn("kind integration", result.stdout)
        self.assertIn("mcp greeter: no test verifies it", result.stdout)

    def test_a_script_without_a_test_is_a_gap(self):
        data = plan()
        data["components"] = [c for c in data["components"] if c["type"] != "test"]
        self.assertIn("no test verifies it", self.check(data).stdout)

    def test_nothing_planned_is_cannot_tell(self):
        self.assertEqual(self.check(plan(components=[])).returncode, 3)

    def test_unreadable_file_is_unusable(self):
        with temp_dir() as root:
            self.assertEqual(py(REQ_TRACE, "check", root / "missing.json").returncode, 2)

    def test_disk_and_plan_are_compared_both_ways(self):
        with temp_dir() as root:
            plugin = root / "greeter"
            for rel, text in GREETER_FILES.items():
                (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
                (plugin / rel).write_text(text, encoding="utf-8")
            data = plan()
            self.assertEqual(req_trace.issues(data, plugin), [])

            (plugin / "agents").mkdir()
            (plugin / "agents" / "extra.md").write_text("---\nname: extra\n---\n", encoding="utf-8")
            (plugin / "commands" / "greet.md").unlink()
            problems = "\n".join(req_trace.issues(data, plugin))
            self.assertIn("agent extra is in the plugin but not in the plan", problems)
            self.assertIn("command greet is planned but not in", problems)

    def test_a_test_that_never_names_its_script_is_hollow(self):
        with temp_dir() as root:
            plugin = root / "greeter"
            for rel, text in GREETER_FILES.items():
                (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
                (plugin / rel).write_text(text, encoding="utf-8")
            (plugin / "tests" / "test_greet.py").write_text("import unittest\n", encoding="utf-8")
            problems = "\n".join(req_trace.issues(plan(), plugin))
            self.assertIn("never names it", problems)

    def test_the_readme_table_round_trips(self):
        with temp_dir() as root:
            readme = root / "README.md"
            readme.write_text("# Greeter\n\nIntro.\n", encoding="utf-8")
            self.assertIsNone(req_trace.readme_is_current(readme, plan()))
            req_trace.write_readme(readme, plan())
            self.assertTrue(req_trace.readme_is_current(readme, plan()))
            text = readme.read_text(encoding="utf-8")
            self.assertIn("Intro.", text)
            self.assertIn("**R1**", text)
            changed = plan()
            changed["components"][0]["why"] = "a different reason"
            self.assertFalse(req_trace.readme_is_current(readme, changed))
            req_trace.write_readme(readme, changed)
            self.assertEqual(readme.read_text(encoding="utf-8").count(req_trace.README_START), 1)

    def test_this_plugin_traces_its_own_requirements(self):
        result = py(REQ_TRACE, "check", PLUGIN / "requirements.json", "--plugin-dir", PLUGIN)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(req_trace.readme_is_current(PLUGIN / "README.md",
                                                    req_trace.load(PLUGIN / "requirements.json")))


# ---- gate.py parsers ------------------------------------------------------------

DETAILS_OUTPUT = """Code Review (code-review) 0.1.1
  Description: Structured code review and repository audit.
  Source: code-review@inline

Component inventory
  Skills (4)  code-review, pr-audit, review, review-pr
  Agents (1)  reviewer
  Hooks (1)  PostToolUse  (harness-only — no model context cost)
  MCP servers (1)  code-review  (tool schemas resolved at runtime; not counted)
  LSP servers (0)

Projected token cost
  Always-on:   ~409 tok   added to every session
"""

BUILD_OUTPUT = """built code-review -> dist/claude-code/code-review  (17 artifacts)
built code-review -> dist/codex/code-review  (12 artifacts)
      skip hooks: Codex has no hook system equivalent.
built code-review -> dist/opencode/code-review  (7 artifacts)
      skip hooks: Use OpenCode plugins/CI for equivalent enforcement.
      skip scripts: plugin-level scripts/ only ships with bundle targets
"""


class GateParserTest(unittest.TestCase):
    def test_inventory_from_real_details_output(self):
        found = gate.parse_inventory(DETAILS_OUTPUT)
        self.assertEqual(found["Skills"], {"code-review", "pr-audit", "review", "review-pr"})
        self.assertEqual(found["Agents"], {"reviewer"})
        self.assertEqual(found["Hooks"], {"PostToolUse"})
        self.assertEqual(found["MCP servers"], {"code-review"})
        self.assertEqual(found["LSP servers"], set())

    def test_unrecognised_details_output_is_not_a_pass(self):
        self.assertIsNone(gate.parse_inventory("claude: only `claude -p \"<prompt>\"` is supported"))

    def test_degradations_keep_their_target(self):
        found = gate.parse_degradations(BUILD_OUTPUT)
        self.assertEqual([d["target"] for d in found], ["codex", "opencode", "opencode"])
        self.assertEqual(found[2]["component"], "scripts")

    def test_a_marker_in_backticks_is_documentation_not_a_stub(self):
        self.assertIsNone(gate.STUB.search("replace every `%s` stub" % gate.MARKER))
        self.assertIsNotNone(gate.STUB.search("description: %s say what it does" % gate.MARKER))

    def test_json_is_found_around_other_output(self):
        self.assertEqual(gate.json_in('warning: x\n[{"id": "a@inline"}]\n'), [{"id": "a@inline"}])
        self.assertTrue(gate.claude_unavailable(2, "claude: only `claude -p \"<prompt>\"` is supported"))


# ---- scaffold.py + gate.py, end to end ------------------------------------------

class ScaffoldAndGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = temp_dir()
        self.root = self._tmp.__enter__()
        if not mini_repo(self.root):
            self._tmp.__exit__(None, None, None)
            self.skipTest("not inside the plugins repo")
        self.plugin = self.root / "plugins" / "greeter"
        self.plan_file = write_json(self.root / ".plugin-dev" / "greeter" / "requirements.json", plan())

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def scaffold(self):
        return py(SCAFFOLD, "greeter", "--root", self.root, cwd=self.root)

    def gate(self, *args):
        return py(GATE, *(list(args) + ["--root", self.root]), cwd=self.root)

    def test_a_plan_with_gaps_is_not_scaffolded(self):
        data = plan()
        data["components"] = data["components"][:2]
        write_json(self.plan_file, data)
        result = self.scaffold()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("R2 is not covered", result.stdout)
        self.assertFalse(self.plugin.exists())

    def test_scaffold_writes_only_the_plan_and_the_gate_holds_it_to_account(self):
        result = self.scaffold()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # exactly the planned components, as marked stubs; no template leftovers
        self.assertEqual(req_trace.on_disk(self.plugin), {
            ("skill", "greeting"), ("command", "greet"),
            ("script", "skills/greeting/scripts/greet.py"), ("test", "tests/test_greet.py")})
        self.assertFalse((self.plugin / "skills" / "example-skill").exists())
        self.assertIn(gate.MARKER, (self.plugin / "commands" / "greet.md").read_text(encoding="utf-8"))
        manifest = json.loads((self.plugin / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "greeter")
        self.assertEqual(manifest["description"], PLAN["plugin"]["description"])
        # the plan moved into the plugin, the README carries its table, the session is open
        self.assertTrue((self.plugin / "requirements.json").is_file())
        self.assertFalse(self.plan_file.exists())
        self.assertTrue(req_trace.readme_is_current(self.plugin / "README.md", plan()))
        self.assertEqual(gate.active(self.root)["plugin"], "greeter")
        self.assertEqual(self.scaffold().returncode, 2)  # never over an existing plugin

        # stubs fail the gate at the first step
        stubbed = self.gate("run", "greeter", "--no-claude")
        self.assertEqual(stubbed.returncode, 1, stubbed.stdout)
        self.assertIn("markers", stubbed.stdout)
        self.assertEqual(self.gate("close", "greeter").returncode, 1)

        # the real files: every local step passes; without claude the result is incomplete
        for rel, text in GREETER_FILES.items():
            (self.plugin / rel).write_text(text, encoding="utf-8")
        done = self.gate("run", "greeter", "--no-claude")
        self.assertEqual(done.returncode, 3, done.stdout)
        record = json.loads((self.root / ".plugin-dev" / "greeter" / "gate.json").read_text(encoding="utf-8"))
        statuses = {s["name"]: s["status"] for s in record["steps"]}
        for step in ("markers", "trace", "readme", "validate", "build", "tests"):
            self.assertEqual(statuses[step], "pass", (step, record))
        for step in ("claude-validate", "load", "inventory"):
            self.assertEqual(statuses[step], "unavailable")
        self.assertEqual(statuses["mcp"], "skip")
        self.assertEqual(self.gate("status", "greeter").returncode, 3)

        # an edit after the run makes it stale
        skill = self.plugin / "skills" / "greeting" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nOne more line.\n", encoding="utf-8")
        self.assertEqual(gate.freshness(self.root, "greeter")[0], "stale")
        self.assertEqual(self.gate("close", "greeter").returncode, 1)

        self.assertEqual(self.gate("run", "greeter", "--no-claude").returncode, 3)
        self.assertEqual(self.gate("close", "greeter").returncode, 0)
        self.assertIsNone(gate.active(self.root))

    def test_a_failing_plugin_test_fails_the_gate(self):
        self.assertEqual(self.scaffold().returncode, 0)
        for rel, text in GREETER_FILES.items():
            (self.plugin / rel).write_text(text, encoding="utf-8")
        test = self.plugin / "tests" / "test_greet.py"
        test.write_text(test.read_text(encoding="utf-8").replace("hello, Ada", "goodbye, Ada"), encoding="utf-8")
        result = self.gate("run", "greeter", "--no-claude")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("tests", result.stdout)

    def test_gate_outside_the_repo_is_unusable(self):
        with temp_dir() as elsewhere:
            result = py(GATE, "run", "greeter", cwd=elsewhere)
            self.assertEqual(result.returncode, 2)


# ---- mcp_smoke.py ---------------------------------------------------------------

SERVER = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    method = msg.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "t", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        if CRASH:
            sys.exit(1)
        result = {"content": [{"type": "text", "text": "missing argument"}], "isError": True}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "no"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
'''


def mcp_plugin(root: Path, crash: bool = False, servers=None) -> Path:
    plugin = root / "p"
    (plugin / "mcp").mkdir(parents=True)
    (plugin / "mcp" / "server.py").write_text("CRASH = %r\n" % crash + SERVER, encoding="utf-8")
    write_json(plugin / "mcp" / "servers.json", {"mcpServers": servers if servers is not None else {
        "t": {"command": "python", "args": ["{{PLUGIN_ROOT}}/mcp/server.py"]}}})
    return plugin


class McpSmokeTest(unittest.TestCase):
    def test_a_server_that_answers_and_survives_passes(self):
        with temp_dir() as root:
            result = py(MCP_SMOKE, mcp_plugin(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("echo (empty call: error)", result.stdout)

    def test_a_server_that_dies_on_a_tool_call_fails(self):
        with temp_dir() as root:
            results = mcp_smoke.smoke(mcp_plugin(root, crash=True), timeout=10)
            self.assertEqual(mcp_smoke.verdict(results), 1)
            self.assertIn("exited", results[0]["detail"])

    def test_missing_config_is_unusable(self):
        with temp_dir() as root:
            self.assertEqual(py(MCP_SMOKE, root).returncode, 2)

    def test_url_servers_and_missing_launchers_cannot_be_told(self):
        with temp_dir() as root:
            plugin = mcp_plugin(root, servers={
                "remote": {"url": "https://example.com/mcp"},
                "odd": {"command": "no-such-launcher-xyz", "args": []}})
            results = mcp_smoke.smoke(plugin)
            self.assertEqual(sorted(r["status"] for r in results), ["skip", "unavailable"])
            self.assertEqual(mcp_smoke.verdict(results), 3)


# ---- scripts/stop_gate.py -------------------------------------------------------

class StopHookTest(unittest.TestCase):
    def fire(self, root: Path, **event):
        event.setdefault("cwd", str(root))
        return run([sys.executable, str(STOP_HOOK)], input=json.dumps(event))

    def repo(self, root: Path) -> Path:
        (root / "tools" / "apkit").mkdir(parents=True)
        plugin = root / "plugins" / "greeter"
        plugin.mkdir(parents=True)
        (plugin / "plugin.json").write_text("{}", encoding="utf-8")
        return plugin

    def test_silent_without_a_build_session(self):
        with temp_dir() as root:
            self.repo(root)
            result = self.fire(root)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_blocks_once_when_the_gate_never_ran(self):
        with temp_dir() as root:
            self.repo(root)
            gate.open_session(root, "greeter")
            result = self.fire(root)
            self.assertEqual(result.returncode, 0)
            decision = json.loads(result.stdout)
            self.assertEqual(decision["decision"], "block")
            self.assertIn("not verified", decision["reason"])
            self.assertIn("gate.py", decision["reason"])
            again = self.fire(root, stop_hook_active=True)
            self.assertEqual(again.stdout.strip(), "")

    def test_a_fresh_pass_lets_the_session_end_and_an_edit_does_not(self):
        with temp_dir() as root:
            plugin = self.repo(root)
            gate.open_session(root, "greeter")
            write_json(root / ".plugin-dev" / "greeter" / "gate.json", {
                "plugin": "greeter", "result": "pass", "steps": [], "finished": "now",
                "fingerprint": gate.fingerprint(plugin)})
            self.assertEqual(self.fire(root).stdout.strip(), "")
            (plugin / "plugin.json").write_text('{"changed": true}', encoding="utf-8")
            decision = json.loads(self.fire(root).stdout)
            self.assertIn("changed after the last gate run", decision["reason"])

    def test_garbage_on_stdin_never_breaks_the_session(self):
        with temp_dir() as root:
            self.repo(root)
            result = run([sys.executable, str(STOP_HOOK)], input="not json", cwd=str(root))
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
