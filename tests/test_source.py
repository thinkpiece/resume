import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen import ResumeError  # noqa: E402
from resumegen.model import VARIANTS  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.publications import (format_item, load_publications,  # noqa: E402
                                    select)
from resumegen.render import Highlight, parse_inline  # noqa: E402
from resumegen.source import INCLUDE_RE, load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

# Item "id" keys on lines 5 (cicc), 8 (asscc), 11 (isscc) and 15 (tcas1).
PUBS_JSON = """{
  "schema": 1,
  "owner": "Junyoung Park",
  "publications": [
    {"id": "cicc-2012-park", "type": "conference", "title": "Online NoC | for *HD*",
     "authors": ["Junyoung Park", "Injoon Hong", "Hoi-Jun Yoo"],
     "venue": {"name": "IEEE Custom Integrated Circuits Conference"}, "year": 2012, "month": 9},
    {"id": "asscc-2012-kim", "type": "conference", "title": "Not first-authored",
     "authors": ["Gyeonghoon Kim", "Junyoung Park"],
     "venue": {"name": "IEEE Asian Solid-State Circuits Conference"}, "year": 2012, "month": 11},
    {"id": "isscc-2013-park", "type": "conference", "title": "A 646GOPS/W processor",
     "authors": ["Junyoung Park", "Hoi-Jun Yoo"],
     "venue": {"name": "IEEE International Solid-State Circuits Conference", "short": "ISSCC"},
     "year": 2013, "month": 2, "pages": "1-3"},
    {"id": "tcas1-2016-kim", "type": "journal", "title": "A journal paper",
     "authors": ["Youchang Kim", "Junyoung Park"],
     "venue": {"name": "IEEE Transactions on Circuits and Systems I: Regular Papers"},
     "year": 2016, "month": 3}
  ]
}
"""
MALFORMED = ("malformed .json include; write "
             "@<file>.json <type> [first-author] [{.full}|{.short}]")


class SourceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")
        return p

    def test_include_relative_and_nested(self):
        root = self.write("root.md", "a\n@sub/one.md\nz")
        self.write("sub/one.md", "b\n@two.md")
        self.write("sub/two.md", "c")
        lines = load_lines(root)
        self.assertEqual([l.text for l in lines], ["a", "b", "c", "z"])
        self.assertEqual(lines[2].path, self.d / "sub" / "two.md")
        self.assertEqual(lines[2].lineno, 1)
        self.assertEqual(lines[3].path, root)
        self.assertEqual(lines[3].lineno, 3)

    def test_include_marker_sets_scope(self):
        root = self.write("root.md", "@a.md {.full}\nx")
        self.write("a.md", "y")
        self.assertEqual([l.scope for l in load_lines(root)],
                         [frozenset({"full"}), VARIANTS])

    def test_nested_include_scopes_intersect(self):
        root = self.write("root.md", "@a.md {.full}")
        self.write("a.md", "@b.md {.short}")
        self.write("b.md", "q")
        self.assertEqual(load_lines(root)[0].scope, frozenset())

    def test_include_cycle_error(self):
        root = self.write("root.md", "@a.md")
        self.write("a.md", "@root.md")
        with self.assertRaisesRegex(
                ResumeError, r"include cycle: root\.md -> a\.md -> root\.md"):
            load_lines(root)

    def test_include_cycle_error_has_location(self):
        root = self.write("root.md", "@a.md")
        a = self.write("a.md", "x\n@root.md")
        with self.assertRaisesRegex(ResumeError, rf"^{re.escape(str(a))}:2: "):
            load_lines(root)

    def test_missing_include_reports_file_and_line(self):
        root = self.write("root.md", "x\n\n@missing.md")
        with self.assertRaisesRegex(
                ResumeError, rf"^{re.escape(str(root))}:3: .*missing\.md"):
            load_lines(root)

    def test_missing_root_file_errors(self):
        with self.assertRaisesRegex(ResumeError, r"nope\.md"):
            load_lines(self.d / "nope.md")

    def test_comments_removed_line_numbers_kept(self):
        root = self.write("root.md", "a <!-- x\ny -->b\nc")
        lines = load_lines(root)
        self.assertEqual([(l.text, l.lineno) for l in lines],
                         [("a ", 1), ("b", 2), ("c", 3)])

    def test_unclosed_comment_errors(self):
        root = self.write("root.md", "a\n<!-- open\nb")
        with self.assertRaisesRegex(
                ResumeError, rf"^{re.escape(str(root))}:2: unclosed comment"):
            load_lines(root)

    def test_bom_crlf_and_tabs_normalized(self):   # Review Focus 1
        root = self.write("root.md", b"\xef\xbb\xbf- a\r\n\tb\r\n")
        self.assertEqual([l.text for l in load_lines(root)], ["- a", "    b"])

    def test_include_line_with_crlf_and_trailing_space(self):
        root = self.write("root.md", b"@a.md {.full}  \r\nx\r\n")
        self.write("a.md", "y")
        lines = load_lines(root)
        self.assertEqual([(l.text, l.scope) for l in lines],
                         [("y", frozenset({"full"})), ("x", VARIANTS)])

    def test_invalid_utf8_errors_with_path(self):
        root = self.write("root.md", b"a\n\xff\n")
        with self.assertRaisesRegex(ResumeError, re.escape(str(root))):
            load_lines(root)

    def test_include_re(self):
        self.assertEqual(INCLUDE_RE.match("@x/y.md").groups(), ("x/y.md", None))
        self.assertEqual(INCLUDE_RE.match("@y.md {.short}").groups(), ("y.md", "short"))
        self.assertIsNone(INCLUDE_RE.match("email me @home"))
        self.assertIsNone(INCLUDE_RE.match("- @a.md"))

    def test_include_like_text_passes_through(self):   # clarification 10
        root = self.write("root.md", "@notes.md is a file\n@KAIST\n")
        self.assertEqual([l.text for l in load_lines(root)],
                         ["@notes.md is a file", "@KAIST"])

    def test_bad_include_marker_errors(self):
        root = self.write("root.md", "@a.md {.ful}")
        self.write("a.md", "y")
        with self.assertRaisesRegex(
                ResumeError, rf"^{re.escape(str(root))}:1: invalid variant marker"):
            load_lines(root)

    # -- .json includes (publications spec §5) ----------------------------

    def test_json_include_lines(self):
        root = self.write("en/resume.md", "@../shared/p.json conference first-author {.full}\n")
        self.write("shared/p.json", PUBS_JSON)
        lines = load_lines(root)
        p = self.d / "shared" / "p.json"
        full = frozenset({"full"})
        self.assertEqual([(l.text, l.path, l.lineno, l.scope) for l in lines], [
            ("- A 646GOPS/W processor, *IEEE International Solid-State Circuits "
             "Conference*, pp.1-3, Feb. 2013.", p, 11, full),
            ("  Junyoung Park and H.-J. Yoo.", p, 11, full),
            ("- Online NoC \\| for \\*HD\\*, *IEEE Custom Integrated Circuits "
             "Conference*, Sept. 2012.", p, 5, full),
            ("  Junyoung Park, I. Hong, and H.-J. Yoo.", p, 5, full),
        ])

    def test_json_include_without_marker_and_with_crlf(self):
        root = self.write("en/resume.md", b"x\r\n@../shared/p.json   journal  \r\n")
        self.write("shared/p.json", PUBS_JSON)
        lines = load_lines(root)
        self.assertEqual([(l.text, l.lineno, l.scope) for l in lines], [
            ("x", 1, VARIANTS),
            ("- A journal paper, *IEEE Transactions on Circuits and Systems I: "
             "Regular Papers*, Mar. 2016.", 15, VARIANTS),
            ("  Y. Kim and Junyoung Park.", 15, VARIANTS),
        ])

    def test_json_include_end_to_end(self):
        root = self.write("en/resume.md", "---\nname: Junyoung Park\n"
                          "highlight: Junyoung Park\n---\n## Publications\n"
                          "### Conference Papers\n"
                          "@../shared/p.json conference first-author {.full}\n")
        json_path = self.write("shared/p.json", PUBS_JSON)
        doc = parse(load_lines(root))
        expected = [format_item(pub, "Junyoung Park") for pub in
                    select(load_publications(json_path), "conference", True)]
        self.assertEqual(len(expected), 2)
        [section] = filter_variant(doc, "full").sections
        [entry] = section.children
        self.assertEqual(len(entry.items), len(expected))
        for item, (bullet, detail) in zip(entry.items, expected):
            # The parser undoes the pipe escape and keeps the others.
            self.assertEqual(item.text, bullet.removeprefix("- ").replace("\\|", "|"))
            self.assertIsNone(item.date)
            self.assertEqual(item.details, [detail.strip()])
            self.assertEqual(item.origin.path, json_path)
            self.assertIn(Highlight("Junyoung Park"),
                          parse_inline(item.details[0], doc.meta.highlight))
        self.assertEqual(entry.items[1].text,
                         "Online NoC | for \\*HD\\*, *IEEE Custom Integrated Circuits "
                         "Conference*, Sept. 2012.")
        self.assertEqual(filter_variant(doc, "short").sections, [])

    def test_json_include_errors(self):   # clarifications 2 and 10
        self.write("shared/p.json", PUBS_JSON)
        cases = [
            ("@../shared/p.json", "a .json include needs a type: journal or conference"),
            ("@../shared/p.json {.full}",
             "a .json include needs a type: journal or conference"),
            ("@../shared/p.json first-author",
             "a .json include needs a type: journal or conference"),
            ("@../shared/p.json journal conference", "a .json include takes one type"),
            ("@../shared/p.json conference selected",
             'unknown word "selected" in a .json include; '
             "use journal, conference or first-author"),
            ("@../shared/nope.json journal",
             f"included file not found: {self.d / 'shared' / 'nope.json'}"),
            ("@../shared/p.json journal {note}", MALFORMED),
            ("@../shared/p.json journal {.full} extra", MALFORMED),
            ("@../shared/p.json journal {.full} {.short}", MALFORMED),
            ("@../shared/p.json{.full}", MALFORMED),
            ("@../shared/p.json conference{.full}", MALFORMED),
            ("@../shared/p.json conference {.ful}", MALFORMED),
            ("@../shared/p.json first-author first-author journal", MALFORMED),
            ("@../shared/p.json journal first-author first-author", MALFORMED),
            ("@../shared/p.json first-author journal", MALFORMED),
            # clarification 17: braces inside the path are part of it; braces
            # glued after the .json suffix are an error, never Markdown.
            ("@../shared/p{x}.json selected",
             'unknown word "selected" in a .json include; '
             "use journal, conference or first-author"),
            ("@../shared/p{x}.json journal",
             f"included file not found: {self.d / 'shared' / 'p{x}.json'}"),
            ("@../shared/p{x}.json{.full}", MALFORMED),
            ("@../shared/p.json{x}", MALFORMED),
            ("@../shared/p.json{x} journal", MALFORMED),
            ("@../shared/p.json{", MALFORMED),
            ("@../shared/p.json{.full} journal", MALFORMED),
            ("@../shared/p.json journal{.full}", MALFORMED),
        ]
        for include, message in cases:
            with self.subTest(include):
                md = self.write("en/resume.md", f"x\n{include}\n")
                with self.assertRaises(ResumeError) as cm:
                    load_lines(md)
                self.assertEqual(str(cm.exception), f"{md}:2: {message}")

    def test_json_include_path_with_braces(self):   # clarification 17
        root = self.write("en/resume.md", "@../shared/papers{archive}.json journal {.short}\n")
        p = self.write("shared/papers{archive}.json", PUBS_JSON)
        self.assertEqual([(l.text, l.path, l.lineno, l.scope) for l in load_lines(root)], [
            ("- A journal paper, *IEEE Transactions on Circuits and Systems I: "
             "Regular Papers*, Mar. 2016.", p, 15, frozenset({"short"})),
            ("  Y. Kim and Junyoung Park.", p, 15, frozenset({"short"})),
        ])

    def test_json_error_points_into_json(self):
        root = self.write("en/resume.md", "@../shared/p.json journal\n")
        p = self.write("shared/p.json", PUBS_JSON.replace(
            '"year": 2012, "month": 9', '"year": 2012, "month": 13'))
        with self.assertRaises(ResumeError) as cm:
            load_lines(root)
        self.assertTrue(str(cm.exception).startswith(f"{p}:5: cicc-2012-park: "),
                        str(cm.exception))

    def test_md_include_with_words_still_passes_through(self):
        root = self.write("root.md", "@a.md journal\n@x.jsonl journal\n")
        self.assertEqual([l.text for l in load_lines(root)],
                         ["@a.md journal", "@x.jsonl journal"])


if __name__ == "__main__":
    unittest.main()
