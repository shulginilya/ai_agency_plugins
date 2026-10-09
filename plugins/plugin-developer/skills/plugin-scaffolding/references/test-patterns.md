# Test patterns

Every script and every MCP server gets a test that names it — `req_trace.py`
checks the name appears in the test file. `apkit test` runs each
`tests/test_*.py` as a standalone script from the repo root.

## Skeleton

```python
#!/usr/bin/env python3
"""Tests for the scripts, hook and MCP server the <name> plugin ships."""

from __future__ import annotations

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
SCRIPT = PLUGIN / "skills" / "<skill>" / "scripts" / "<script>.py"


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=False, **kwargs)


@contextmanager
def temp_dir():
    """mkdtemp + rmtree that clears read-only bits, so git objects delete on Windows."""
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


class ScriptTest(unittest.TestCase):
    def test_every_exit_code(self):
        ...


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

## What to test

- **Every exit code the docstring promises**, not just 0. The "unusable" and
  "cannot tell" answers are the ones that rot.
- **Refusals.** Malformed input is refused and the user's file is untouched.
- **Parsers against literal strings**, not against whatever tool is installed
  locally. If a script reads a CLI's output, paste two real outputs into the
  test.
- **Hooks with a piped event.** Feed the JSON a harness sends on stdin; assert
  the silent case prints nothing and the speaking case prints the message.
- **Git with a throwaway repo**, `skipTest` when git is missing, and the
  `temp_dir()` helper above.

## MCP server

Drive it over stdio the way a harness does:

```python
def mcp(*messages):
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    out = run([sys.executable, str(PLUGIN / "mcp" / "server.py")], input=payload)
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def test_tools_list_and_a_bad_call_survives(self):
    replies = mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "<tool>", "arguments": {}}},
    )
    ...
```

Assert every tool appears in `tools/list`, one real call returns what the
script returns, and a call with bad arguments answers `isError` instead of
ending the process.
