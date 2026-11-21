import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen import ResumeError  # noqa: E402
from resumegen.model import VARIANTS  # noqa: E402
from resumegen.source import INCLUDE_RE, load_lines  # noqa: E402


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

    def test_bad_include_marker_errors(self):
        root = self.write("root.md", "@a.md {.ful}")
        self.write("a.md", "y")
        with self.assertRaisesRegex(
                ResumeError, rf"^{re.escape(str(root))}:1: invalid variant marker"):
            load_lines(root)


if __name__ == "__main__":
    unittest.main()
