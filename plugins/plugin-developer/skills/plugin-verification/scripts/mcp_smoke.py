#!/usr/bin/env python3
"""Start a plugin's MCP servers and prove they answer.

For every stdio server declared in `mcp/servers.json` (portable source, with
`{{PLUGIN_ROOT}}` resolved to the plugin directory), this:

    1. starts the process,
    2. sends `initialize` and `notifications/initialized`,
    3. asks for `tools/list`,
    4. calls every tool once with no arguments,
    5. checks the process is still alive afterwards.

Step 4 is not a correctness test -- the plugin's own tests are. It checks the
convention that a server survives its own tools: a tool called with bad input
must answer with an error, not take the server down.

    mcp_smoke.py plugins/NAME [--timeout 10]

Exits:

    0  every server answered and survived every tool
    1  a server failed to start, answered badly, or died
    2  servers.json is missing or malformed
    3  nothing could be checked (no servers, only URL servers, or the
       launcher named in the config is not installed here)
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL = "2025-06-18"
PYTHON_NAMES = {"python", "python3", "py"}


class Unusable(Exception):
    pass


def load_servers(plugin_dir: Path) -> Dict[str, Dict[str, Any]]:
    path = Path(plugin_dir) / "mcp" / "servers.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Unusable("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise Unusable("%s is not valid JSON: %s" % (path, exc))
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise Unusable("%s has no 'mcpServers' object" % path)
    return servers


def resolve(value: str, plugin_dir: Path) -> str:
    return value.replace("{{PLUGIN_ROOT}}", str(Path(plugin_dir).resolve()))


def command_line(server: Dict[str, Any], plugin_dir: Path) -> List[str]:
    command = resolve(str(server.get("command", "")), plugin_dir)
    args = [resolve(str(a), plugin_dir) for a in server.get("args") or []]
    if command in PYTHON_NAMES:
        command = sys.executable
    return [command] + args


class Session:
    """Newline-delimited JSON-RPC over a child's stdio, with timeouts that work on Windows."""

    def __init__(self, argv: List[str], env: Dict[str, str], cwd: Path, timeout: float):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.lines: "queue.Queue[Optional[str]]" = queue.Queue()
        self.stderr: List[str] = []
        threading.Thread(target=self._pump, args=(self.proc.stdout, self.lines), daemon=True).start()
        threading.Thread(target=self._drain, daemon=True).start()
        self.next_id = 1

    @staticmethod
    def _pump(stream, sink) -> None:
        for line in stream:
            sink.put(line)
        sink.put(None)

    def _drain(self) -> None:
        for line in self.proc.stderr:
            self.stderr.append(line.rstrip())

    def send(self, message: Dict[str, Any]) -> None:
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rid = self.next_id
        self.next_id += 1
        message: Dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
        while True:
            try:
                line = self.lines.get(timeout=self.timeout)
            except queue.Empty:
                raise RuntimeError("no answer to %s within %ss" % (method, self.timeout))
            if line is None:
                raise RuntimeError("server exited while answering %s" % method)
            line = line.strip()
            if not line:
                continue
            try:
                reply = json.loads(line)
            except ValueError:
                raise RuntimeError("non-JSON on stdout while answering %s: %r" % (method, line[:120]))
            if isinstance(reply, dict) and reply.get("id") == rid:
                if "result" not in reply and "error" not in reply:
                    raise RuntimeError("%s reply has neither result nor error" % method)
                return reply
            # a notification or a reply to something else -- keep reading

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def smoke_server(name: str, server: Dict[str, Any], plugin_dir: Path, timeout: float) -> Dict[str, Any]:
    result: Dict[str, Any] = {"server": name, "status": "fail", "detail": "", "tools": []}
    if "url" in server and "command" not in server:
        result.update(status="skip", detail="URL server -- nothing to start locally")
        return result
    argv = command_line(server, plugin_dir)
    if not argv[0] or (shutil.which(argv[0]) is None and not Path(argv[0]).is_file()):
        result.update(status="unavailable", detail="launcher %r is not installed here" % argv[0])
        return result
    env = dict(os.environ)
    env.update({str(k): resolve(str(v), plugin_dir) for k, v in (server.get("env") or {}).items()})
    try:
        session = Session(argv, env, Path(plugin_dir), timeout)
    except OSError as exc:
        result["detail"] = "could not start: %s" % exc
        return result
    try:
        init = session.request("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "plugin-developer-smoke", "version": "1"},
        })
        if "error" in init:
            raise RuntimeError("initialize failed: %s" % init["error"])
        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = session.request("tools/list", {})
        if "error" in listed:
            raise RuntimeError("tools/list failed: %s" % listed["error"])
        tools = (listed.get("result") or {}).get("tools") or []
        for tool in tools:
            tool_name = str(tool.get("name"))
            reply = session.request("tools/call", {"name": tool_name, "arguments": {}})
            outcome = "error" if "error" in reply or (reply.get("result") or {}).get("isError") else "ok"
            result["tools"].append({"name": tool_name, "empty_call": outcome})
        if session.proc.poll() is not None:
            raise RuntimeError("server exited after its tools were called")
        result.update(status="pass", detail="%d tool(s) listed and called" % len(tools))
    except (RuntimeError, OSError, ValueError) as exc:
        tail = "; ".join(session.stderr[-3:])
        result["detail"] = str(exc) + (" | stderr: " + tail if tail else "")
    finally:
        session.close()
    return result


def smoke(plugin_dir: Path, timeout: float = 10.0) -> List[Dict[str, Any]]:
    servers = load_servers(plugin_dir)
    return [smoke_server(str(n), s if isinstance(s, dict) else {}, Path(plugin_dir), timeout)
            for n, s in servers.items()]


def verdict(results: List[Dict[str, Any]]) -> int:
    statuses = [r["status"] for r in results]
    if "fail" in statuses:
        return 1
    if not statuses or "pass" not in statuses:
        return 3
    if "unavailable" in statuses:
        return 3
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        results = smoke(args.plugin_dir, args.timeout)
    except Unusable as exc:
        print("UNUSABLE: %s" % exc, file=sys.stderr)
        return 2
    for r in results:
        print("%-12s %s  %s" % (r["status"].upper(), r["server"], r["detail"]))
        for tool in r["tools"]:
            print("             - %s (empty call: %s)" % (tool["name"], tool["empty_call"]))
    return verdict(results)


if __name__ == "__main__":
    raise SystemExit(main())
