#!/usr/bin/env python3
"""A script that travels with the skill.

Scripts inside a skill directory are copied wherever the skill is installed, on
every target. Scripts in the plugin-level scripts/ directory only ship with
bundle targets — so if a skill needs it, put it here.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="world")
    args = parser.parse_args()
    print("hello, %s" % args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
