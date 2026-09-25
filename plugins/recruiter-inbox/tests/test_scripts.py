#!/usr/bin/env python3
"""Smoke tests for the scripts, hooks and MCP server the recruiter-inbox plugin ships."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
TRIAGE_DIR = PLUGIN / "skills" / "inbound-triage" / "scripts"
REPLY_DIR = PLUGIN / "skills" / "recruiter-reply" / "scripts"
LEDGER_DIR = PLUGIN / "skills" / "reply-ledger" / "scripts"
INBOUND = TRIAGE_DIR / "inbound.py"
DRAFT_CHECK = REPLY_DIR / "draft_check.py"
THREADS = LEDGER_DIR / "threads.py"
GATE = PLUGIN / "scripts" / "send_gate.py"
STATUS_HOOK = PLUGIN / "scripts" / "inbox_status.py"
MCP_SERVER = PLUGIN / "mcp" / "server.py"

for _directory in (TRIAGE_DIR, REPLY_DIR, LEDGER_DIR):
    sys.path.insert(0, str(_directory))

PROFILE = {
    "titles": ["Senior AI Engineer", "Senior Software Engineer"],
    "must_have": ["typescript", "react", "node"],
    "markets": {"onsite": ["Berlin"], "remote": ["eu"]},
    "tracks": ["permanent", "contract"],
    "deal_breakers": ["relocation required"],
    "min_must_have_ratio": 0.6,
    "replies": {
        "name": "Ilya",
        "languages": ["en", "de"],
        "availability": ["Tue 16:00-18:00"],
        "salary": {"say": "95-110k EUR", "disclose": "on-request"},
        "shareable": {"email": "me@example.com", "links": ["linkedin.com/in/me"]},
        "never_mention": ["Initech"],
    },
}

ENGAGE = ("Hi Ilya, I'm hiring a Senior AI Engineer for our Berlin team (hybrid). Stack is "
          "TypeScript, React and Node. Permanent role. Would you be open to a quick call?")
AGENCY_DE = ("Hallo Ilya, für einen Kunden in Berlin suche ich einen Senior Software Engineer in "
             "Festanstellung. Hätten Sie Interesse an einem kurzen Telefonat? Viele Grüße")
VAGUE = "Hi, I have an exciting opportunity that might interest you. Are you open to new roles?"
BREAKER = "Senior AI Engineer role in Munich, on-site five days, relocation required. Salary 90-110k EUR."
SALES = ("Hi Ilya, we help companies scale with dedicated developers from our nearshore team. "
         "Partnership opportunity - can we book a demo?")
SCAM = ("Congratulations, you are selected for a remote job, no interview needed. Please send your "
        "passport and bank details on Telegram. A small registration fee applies.")
NETWORK = "Hi Ilya, thanks for connecting! Loved your post about agent SDKs."

GOOD_REPLY = ("Hi Anna, thanks for reaching out. The role sounds close to what I do.\n\n"
              "Could you share the salary range and how many office days it has? "
              "Tuesday 16:00 would work for a call.\n\nBest, Ilya")


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


def workspace(tmp: str, profile=None, ledger: bool = True) -> Path:
    root = Path(tmp)
    (root / ".jobhunt").mkdir(parents=True, exist_ok=True)
    (root / ".jobhunt" / "profile.json").write_text(json.dumps(profile or PROFILE), encoding="utf-8")
    if ledger:
        run([sys.executable, str(THREADS), "init"], cwd=root)
    return root


def write(root: Path, name: str, text: str) -> str:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return str(path)


class InboundTest(unittest.TestCase):
    def _assess(self, root: Path, message: str):
        result = run([sys.executable, str(INBOUND), write(root, "m.txt", message), "--json"], cwd=root)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else {}

    def test_the_five_intents_and_their_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp, ledger=False)
            cases = [
                (ENGAGE, 0, "engage", "opportunity"),
                (AGENCY_DE, 0, "engage", "recruiter-agency"),
                (VAGUE, 3, "qualify", "opportunity"),
                (BREAKER, 1, "decline", "opportunity"),
                (SALES, 1, "ignore", "sales"),
                (SCAM, 1, "ignore", "scam-risk"),
                (NETWORK, 3, "personal", "network"),
            ]
            for message, code, intent, kind in cases:
                got_code, report = self._assess(root, message)
                self.assertEqual((got_code, report.get("intent"), report.get("kind")),
                                 (code, intent, kind), message[:40])

    def test_unknowns_name_what_the_message_leaves_out(self):
        import inbound

        report = inbound.assess(AGENCY_DE, dict(inbound.PROFILE_TEMPLATE))
        joined = " ".join(report["unknowns"])
        self.assertIn("compensation", joined)
        self.assertIn("client company", joined)
        self.assertEqual(report["language"], "de")
        self.assertIn("call", report["asks"])

    def test_money_is_parsed_and_bare_numbers_are_not(self):
        import inbound

        self.assertEqual(inbound.money_figures("95-110k EUR"), [95000, 110000])
        self.assertEqual(inbound.money_figures("€95.000 brutto"), [95000])
        self.assertEqual(inbound.money_figures("EUR 700/day"), [700])
        self.assertEqual(inbound.money_figures("$120,000 - $140,000"), [120000, 140000])
        self.assertEqual(inbound.money_figures("I have 10 years and start 2026-10-01"), [])

    def test_no_profile_or_empty_message_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run([sys.executable, str(INBOUND), write(root, "m.txt", ENGAGE)], cwd=root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("no profile", result.stderr)
            workspace(tmp, ledger=False)
            result = run([sys.executable, str(INBOUND), write(root, "e.txt", "  \n")], cwd=root)
            self.assertEqual(result.returncode, 2)

    def test_init_adds_replies_with_a_backup_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / ".jobhunt" / "profile.json"
            profile.parent.mkdir(parents=True)
            profile.write_text(json.dumps({"titles": ["Mine"]}), encoding="utf-8")
            self.assertEqual(run([sys.executable, str(INBOUND), "--init"], cwd=root).returncode, 0)
            data = json.loads(profile.read_text(encoding="utf-8"))
            self.assertEqual(data["titles"], ["Mine"], "the user's own fields must survive")
            self.assertIn("replies", data)
            self.assertTrue(Path(str(profile) + ".bak").is_file())

            profile.write_text("[1, 2]", encoding="utf-8")
            result = run([sys.executable, str(INBOUND), "--init"], cwd=root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(profile.read_text(encoding="utf-8"), "[1, 2]", "refused, not replaced")


class DraftCheckTest(unittest.TestCase):
    def _check(self, draft, inbound_text=ENGAGE, intent="engage", profile=None):
        import draft_check

        merged = dict(PROFILE)
        merged.update(profile or {})
        return draft_check.check(draft, merged, inbound_text, intent)

    def test_a_good_reply_is_clean(self):
        report = self._check(GOOD_REPLY)
        self.assertEqual(report["verdict"], "clean", report)

    def test_what_only_the_user_can_authorise_is_blocked(self):
        blocked = {
            "a number not in salary.say": "I'm looking for around 130k. Can we talk?",
            "a phone number": "Call me on +49 151 23456789 when suits?",
            "an email not shareable": "Write to me at private@example.org, ok?",
            "a link not shareable": "My CV is at https://example.net/cv.pdf - thoughts?",
            "acceptance": "Thanks, I accept the offer. When can we talk?",
            "a placeholder": "Hi [Name], when can we talk?",
            "a guillemet placeholder": "Hi «first name», when can we talk?",
            "never_mention": "I work at Initech right now. When can we talk?",
        }
        for label, draft in blocked.items():
            self.assertEqual(self._check(draft)["verdict"], "blocked", label)

    def test_allowed_contacts_and_dates_are_not_mistaken_for_problems(self):
        draft = ("Profile: https://www.linkedin.com/in/me/ and me@example.com. "
                 "Could we speak on 09/30/2026 at 16:00?")
        self.assertEqual(self._check(draft)["verdict"], "clean")

    def test_disclose_never_blocks_even_the_declared_figure(self):
        profile = {"replies": dict(PROFILE["replies"], salary={"say": "95-110k EUR", "disclose": "never"})}
        report = self._check("My range is 95-110k EUR. When can we talk?", profile=profile)
        self.assertEqual(report["verdict"], "blocked")

    def test_review_items(self):
        stall = self._check("Hi Anna, thanks for reaching out, sounds interesting.")
        self.assertIn("stalls", " ".join(stall["review"]))
        unasked = self._check("My range is 95-110k EUR. When can we talk?")
        self.assertEqual(unasked["verdict"], "review", "a figure nobody asked for")
        language = self._check("Hi, thanks. What is the range? Could we talk Tuesday?", inbound_text=AGENCY_DE)
        self.assertIn("they wrote in de", " ".join(language["review"]))
        no_slots = {"replies": dict(PROFILE["replies"], availability=[])}
        slots = self._check("Could we talk Tuesday at 16:00?", profile=no_slots)
        self.assertIn("no availability", " ".join(slots["review"]))
        tells = self._check("I hope this message finds you well. Could we talk?")
        self.assertIn("template", " ".join(tells["review"]))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp, ledger=False)
            for text, code in ((GOOD_REPLY, 0), ("I accept. Can we talk?", 1),
                               ("Hi Anna, thanks, sounds good.", 3), (" ", 2)):
                result = run([sys.executable, str(DRAFT_CHECK), write(root, "d.txt", text),
                              "--intent", "engage"], cwd=root)
                self.assertEqual(result.returncode, code, text)


class LedgerTest(unittest.TestCase):
    URL = "https://www.linkedin.com/messaging/thread/2-abc==/"

    def _t(self, root: Path, *args):
        return run([sys.executable, str(THREADS)] + list(args), cwd=root)

    def _seed(self, root: Path, message: str = ENGAGE):
        return self._t(root, "seen", "--url", self.URL, "--contact", "Anna", "--company", "Acme",
                       "--intent", "engage", "--at", "2026-09-20T10:00",
                       "--text-file", write(root, "m.txt", message))

    def test_init_keeps_the_ledger_out_of_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self.assertIn("*", (root / ".jobhunt" / "inbox" / ".gitignore").read_text(encoding="utf-8"))
            self.assertEqual(self._t(root, "init").returncode, 2, "init twice is refused")

    def test_a_message_is_recorded_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self.assertEqual(self._seed(root).returncode, 0)
            again = self._t(root, "--json", "seen", "--url", self.URL, "--text-file", str(root / "m.txt"))
            self.assertFalse(json.loads(again.stdout)["new"])
            state = json.loads((root / ".jobhunt" / "inbox" / "threads.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["threads"][0]["messages"]), 1)
            self.assertEqual(state["threads"][0]["id"], "li:2-abc==")

    def test_draft_approve_send_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self._seed(root)
            status = self._t(root, "status", "--as-of", "2026-09-25")
            self.assertEqual(status.returncode, 1)
            self.assertIn("OWE REPLY", status.stdout)

            drafted = self._t(root, "draft", "--thread", "li:2-abc==", "--text-file",
                              write(root, "r.txt", GOOD_REPLY), "--inbound-file", str(root / "m.txt"))
            self.assertEqual(drafted.returncode, 0, drafted.stdout + drafted.stderr)
            self.assertEqual(self._t(root, "sent", "--thread", "Acme").returncode, 2,
                             "a proposed draft is not sent")
            self.assertEqual(self._t(root, "approve", "--thread", "Acme").returncode, 0)

            listed = json.loads(self._t(root, "status", "--json", "--as-of", "2026-09-25").stdout)
            self.assertEqual(len(listed["approved_unsent"]), 1)
            self.assertEqual(listed["approved_texts"][0]["text"], GOOD_REPLY.strip())

            sent = self._t(root, "sent", "--thread", "Acme", "--follow-up", "2026-09-30")
            self.assertEqual(sent.returncode, 0, sent.stderr)
            self.assertEqual(self._t(root, "status", "--as-of", "2026-09-26").returncode, 0)
            due = self._t(root, "status", "--as-of", "2026-10-01")
            self.assertIn("follow-up due", due.stdout)

    def test_a_blocked_draft_needs_the_users_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self._seed(root)
            drafted = self._t(root, "draft", "--thread", "Acme", "--text-file",
                              write(root, "r.txt", "I'm at 130k. Can we talk?"))
            self.assertEqual(drafted.returncode, 1)
            refused = self._t(root, "approve", "--thread", "Acme")
            self.assertEqual(refused.returncode, 2)
            self.assertIn("blocked", refused.stderr)
            allowed = self._t(root, "approve", "--thread", "Acme", "--because", "user: fine to say 130k")
            self.assertEqual(allowed.returncode, 0)

    def test_a_malformed_ledger_is_refused_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            ledger = root / ".jobhunt" / "inbox" / "threads.json"
            ledger.write_text("{not json", encoding="utf-8")
            result = self._seed(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(ledger.read_text(encoding="utf-8"), "{not json")

    def test_a_new_message_reopens_a_closed_thread_and_cancels_the_chase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self._seed(root)
            self._t(root, "close", "--thread", "Acme", "--because", "went quiet")
            self._seed(root, "Hi again Ilya, the role reopened. Still interested?")
            state = json.loads((root / ".jobhunt" / "inbox" / "threads.json").read_text(encoding="utf-8"))
            self.assertEqual(state["threads"][0]["stage"], "qualifying")

    def test_page_strings_arrive_by_file_not_by_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            meta = {"url": self.URL, "contact": "Anna $(touch pwned)", "company": "Acme; rm -rf /",
                    "intent": "engage", "at": "2026-09-20T10:00"}
            result = self._t(root, "seen", "--meta-file", write(root, "meta.json", json.dumps(meta)),
                             "--text-file", write(root, "m.txt", ENGAGE))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "pwned").exists())
            state = json.loads((root / ".jobhunt" / "inbox" / "threads.json").read_text(encoding="utf-8"))
            self.assertEqual(state["threads"][0]["contact"], "Anna $(touch pwned)", "stored, never run")
            bad = self._t(root, "seen", "--meta-file", write(root, "bad.json", json.dumps({"evil": 1})),
                          "--text-file", str(root / "m.txt"))
            self.assertEqual(bad.returncode, 2)

    def test_dates_must_be_iso(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            self._seed(root)
            result = self._t(root, "stage", "--thread", "Acme", "--to", "scheduling",
                             "--follow-up", "next week")
            self.assertEqual(result.returncode, 2)

    def test_approval_matching(self):
        import threads

        state = {"threads": [{"id": "li:x", "draft": {"status": "approved", "text": GOOD_REPLY}}]}
        self.assertTrue(threads.is_approved("Tuesday 16:00 would work for a call.", state))
        self.assertTrue(threads.is_approved("Could you share the salary range and how many office "
                                            "days it has? Tuesday 16:00 would work for a call.", state))
        self.assertFalse(threads.is_approved("Could you share the salary range?", state, whole=True))
        self.assertTrue(threads.is_approved(GOOD_REPLY.replace("\n\n", " "), state, whole=True))
        self.assertFalse(threads.is_approved("Something else entirely.", state))
        proposed = {"threads": [{"id": "li:x", "draft": {"status": "proposed", "text": GOOD_REPLY}}]}
        self.assertFalse(threads.is_approved(GOOD_REPLY, proposed), "proposed is not approved")


def gate(root: Path, tool: str, tool_input) -> dict:
    event = {"cwd": str(root), "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    result = run([sys.executable, str(GATE)], input=json.dumps(event))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else {}


class SendGateTest(unittest.TestCase):
    CHROME = "mcp__claude-in-chrome__computer"

    def _approved(self, tmp: str, profile=None) -> Path:
        root = workspace(tmp, profile=profile)
        run([sys.executable, str(THREADS), "seen", "--thread", "li:1", "--text-file",
             write(root, "m.txt", ENGAGE)], cwd=root)
        run([sys.executable, str(THREADS), "draft", "--thread", "li:1", "--text-file",
             write(root, "r.txt", GOOD_REPLY)], cwd=root)
        run([sys.executable, str(THREADS), "approve", "--thread", "li:1"], cwd=root)
        return root

    def test_an_approved_paragraph_passes_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._approved(tmp)
            paragraph = GOOD_REPLY.split("\n\n")[1]
            self.assertEqual(gate(root, self.CHROME, {"action": "type", "text": paragraph}), {})

    def test_unapproved_text_is_put_to_the_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._approved(tmp)
            out = gate(root, self.CHROME, {"action": "type", "text": "Sure, my expectation is 150k, let's talk soon."})
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("not an approved draft", out["permissionDecisionReason"])

    def test_short_typing_and_other_tools_are_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._approved(tmp)
            self.assertEqual(gate(root, self.CHROME, {"action": "type", "text": "senior ai engineer"}), {})
            self.assertEqual(gate(root, self.CHROME, {"action": "left_click", "coordinate": [1, 2]}), {})
            self.assertEqual(gate(root, "Bash", {"command": "echo " + "x" * 80}), {})

    def test_a_batch_is_checked_action_by_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._approved(tmp)
            batch = {"actions": [
                {"name": "computer", "input": {"action": "type", "text": GOOD_REPLY.split("\n\n")[1]}},
                {"name": "computer", "input": {"action": "type", "text": "And here is my private phone number too."}},
            ]}
            out = gate(root, "mcp__claude-in-chrome__browser_batch", batch)
            self.assertEqual(out["permissionDecision"], "ask")

    def test_mail_must_be_the_whole_approved_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._approved(tmp)
            self.assertEqual(gate(root, "mcp__Gmail__reply", {"messageId": "m", "body": GOOD_REPLY}), {})
            html = "".join("<p>%s</p>" % p for p in GOOD_REPLY.split("\n\n"))
            self.assertEqual(gate(root, "mcp__Gmail__reply", {"messageId": "m", "htmlBody": html}), {})
            part = gate(root, "mcp__Gmail__reply", {"messageId": "m", "body": GOOD_REPLY.split("\n\n")[1]})
            self.assertEqual(part["permissionDecision"], "ask", "a fragment is not the approved mail")
            blind = gate(root, "mcp__Gmail__send_message", {"draftId": "d1"})
            self.assertEqual(blind["permissionDecision"], "ask")
            attached = gate(root, "mcp__Gmail__send_message",
                            {"to": ["a@b.c"], "body": GOOD_REPLY, "attachments": [{"content": "eA=="}]})
            self.assertEqual(attached["permissionDecision"], "ask")
            self.assertEqual(gate(root, "mcp__Gmail__create_draft", {"body": "anything " * 20}), {})

    def test_draft_only_mode_denies(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = dict(PROFILE, replies=dict(PROFILE["replies"], send_mode="draft-only"))
            root = self._approved(tmp, profile=profile)
            out = gate(root, self.CHROME, {"action": "type", "text": GOOD_REPLY.split("\n\n")[1]})
            self.assertEqual(out["permissionDecision"], "deny")

    def test_silent_without_a_ledger_and_cautious_with_a_broken_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp, ledger=False)
            long_text = {"action": "type", "text": "x " * 40}
            self.assertEqual(gate(root, self.CHROME, long_text), {})
            ledger = root / ".jobhunt" / "inbox" / "threads.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("{broken", encoding="utf-8")
            self.assertEqual(gate(root, self.CHROME, long_text)["permissionDecision"], "ask")

    def test_never_fails_the_call(self):
        result = run([sys.executable, str(GATE)], input="not json")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ""))


class StatusHookTest(unittest.TestCase):
    def test_speaks_only_when_someone_is_waiting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            quiet = run([sys.executable, str(STATUS_HOOK)], input=json.dumps({"cwd": str(root)}))
            self.assertEqual((quiet.returncode, quiet.stdout.strip()), (0, ""))
            run([sys.executable, str(THREADS), "seen", "--thread", "li:1", "--contact", "Anna",
                 "--company", "Acme", "--text-file", write(root, "m.txt", ENGAGE)], cwd=root)
            loud = run([sys.executable, str(STATUS_HOOK)], input=json.dumps({"cwd": str(root)}))
            self.assertEqual(loud.returncode, 0)
            self.assertIn("waiting for your reply", loud.stdout)
            self.assertIn("Anna", loud.stdout)

    def test_silent_without_a_ledger_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run([sys.executable, str(STATUS_HOOK)], input="{}", cwd=tmp)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, ""))
            result = run([sys.executable, str(STATUS_HOOK)], input="garbage", cwd=tmp)
            self.assertEqual(result.returncode, 0)


class McpServerTest(unittest.TestCase):
    def _rpc(self, messages, cwd=None):
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        result = run([sys.executable, str(MCP_SERVER)], input=payload, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def _call(self, name, arguments, cwd=None):
        return self._rpc([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}], cwd=cwd)[0]["result"]

    def test_initialize_and_list_tools(self):
        responses = self._rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(responses), 2, "notifications must not get a response")
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "recruiter-inbox")
        names = {tool["name"] for tool in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"assess_message", "check_draft", "thread_status", "reply_playbook"})

    def test_tools_use_the_skills_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace(tmp)
            assessed = self._call("assess_message", {"text": SCAM}, cwd=root)
            self.assertEqual(json.loads(assessed["content"][0]["text"])["intent"], "ignore")
            checked = self._call("check_draft", {"draft": "I accept the offer.", "intent": "engage"}, cwd=root)
            self.assertEqual(json.loads(checked["content"][0]["text"])["verdict"], "blocked")
            status = self._call("thread_status", {"as_of": "2026-09-25"}, cwd=root)
            body = json.loads(status["content"][0]["text"])
            self.assertIn("approved_texts", body)
            self.assertFalse(body["action_needed"])

    def test_every_playbook_topic_resolves(self):
        for topic in ("message-signals", "reply-moves", "negotiation", "reply-cadence", "linkedin", "gmail"):
            result = self._call("reply_playbook", {"topic": topic})
            self.assertFalse(result["isError"], topic)
            self.assertTrue(result["content"][0]["text"].startswith("#"), topic)

    def test_a_bad_file_is_a_tool_error_and_the_server_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = self._rpc([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "thread_status", "arguments": {"file": "nope.json"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "assess_message", "arguments": {"text": ENGAGE}}},
                {"jsonrpc": "2.0", "id": 3, "method": "ping"},
            ], cwd=tmp)
            self.assertTrue(responses[0]["result"]["isError"])
            self.assertTrue(responses[1]["result"]["isError"], "no profile is an error, not a guess")
            self.assertEqual(responses[2]["result"], {}, "the server must still be alive")

    def test_unknown_method_returns_jsonrpc_error(self):
        responses = self._rpc([{"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"}])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main(verbosity=2)
