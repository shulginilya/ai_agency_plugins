#!/usr/bin/env python3
"""The frontmatter subset parser is load-bearing; hold it to round-tripping."""

from __future__ import annotations

import unittest

import _helpers  # noqa: F401
from tools.apkit import frontmatter


class ParseTest(unittest.TestCase):
    def test_scalars_lists_and_nested_maps(self):
        meta, body = frontmatter.parse(
            "---\n"
            "name: demo\n"
            'description: "Does a thing: carefully"\n'
            "metadata:\n"
            "  author: ilya\n"
            '  version: "1.0"\n'
            "tags: [a, b]\n"
            "---\n"
            "Body\n"
        )
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(meta["description"], "Does a thing: carefully")
        self.assertEqual(meta["metadata"], {"author": "ilya", "version": "1.0"})
        self.assertEqual(meta["tags"], ["a", "b"])
        self.assertEqual(body.strip(), "Body")

    def test_block_lists(self):
        meta, _ = frontmatter.parse("---\nitems:\n  - one\n  - two\n---\n")
        self.assertEqual(meta["items"], ["one", "two"])

    def test_document_without_frontmatter(self):
        meta, body = frontmatter.parse("just a body\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just a body\n")

    def test_unterminated_frontmatter_raises(self):
        with self.assertRaises(frontmatter.FrontmatterError):
            frontmatter.parse("---\nname: x\nno closing delimiter\n")


class RoundTripTest(unittest.TestCase):
    def test_numeric_looking_strings_survive(self):
        original = {"metadata": {"version": "1.0", "flag": "true"}}
        reparsed, _ = frontmatter.parse(frontmatter.compose(original, "body"))
        self.assertEqual(reparsed["metadata"]["version"], "1.0")
        self.assertEqual(reparsed["metadata"]["flag"], "true")

    def test_compose_then_parse_is_identity(self):
        original = {
            "name": "demo-skill",
            "description": "A thing, with a comma: and a colon",
            "tags": ["x", "y"],
        }
        reparsed, body = frontmatter.parse(frontmatter.compose(original, "Hello\n"))
        self.assertEqual(reparsed, original)
        self.assertEqual(body.strip(), "Hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
