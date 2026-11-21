import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen import ResumeError  # noqa: E402
from resumegen.model import VARIANTS, Entry, Item, Paragraph  # noqa: E402
from resumegen.parse import parse, split_marker, split_right  # noqa: E402
from resumegen.source import load_lines  # noqa: E402

FM = "---\nname: Test Person\n---\n"   # 3 lines of front matter
FULL = frozenset({"full"})
SHORT = frozenset({"short"})


class ParseTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def doc(self, body, fm=FM, **files):
        for rel, text in files.items():
            self.write(rel.replace("__", "/"), text)
        root = self.write("root.md", fm + body)
        return parse(load_lines(root))

    def assertParseError(self, body, regex, fm=FM, **files):
        with self.assertRaisesRegex(ResumeError, regex):
            self.doc(body, fm=fm, **files)


class FrontMatterTest(ParseTestBase):
    def test_front_matter(self):
        doc = self.doc("", fm=(
            "---\n"
            "name: Junyoung Park\n"
            "title: AI & SoC  # note\n"
            "font: Charter, NanumMyeongjo\n"
            "location: Seongnam-si\n"
            "email: a@b.c\n"
            "---\n"))
        m = doc.meta
        self.assertEqual(m.name, "Junyoung Park")
        self.assertEqual(m.fonts, ["Charter", "NanumMyeongjo"])
        self.assertEqual(m.contacts, [("location", "Seongnam-si"), ("email", "a@b.c")])
        self.assertEqual(m.title, "AI & SoC")
        self.assertEqual(doc.sections, [])

    def test_defaults(self):
        m = self.doc("").meta
        self.assertEqual((m.title, m.lang, m.paper, m.fonts, m.highlight, m.contacts),
                         (None, "en", "us-letter", ["Charter"], None, []))

    def test_all_keys(self):
        m = self.doc("", fm=(
            "---\nname: N\nlang: ko\npaper: a4\nfont: Pretendard\n"
            "highlight: Junyoung Park\nphone: +82-10\nhomepage: http://x.y/#a\n"
            "linkedin: https://l.in/p\ngithub: https://gh.com/p\n---\n")).meta
        self.assertEqual((m.lang, m.paper, m.fonts, m.highlight),
                         ("ko", "a4", ["Pretendard"], "Junyoung Park"))
        self.assertEqual([k for k, _ in m.contacts], ["phone", "homepage", "linkedin", "github"])
        self.assertEqual(m.contacts[1], ("homepage", "http://x.y/#a"))

    def test_unknown_front_matter_key(self):
        self.assertParseError("", r":3: unknown front matter key 'colour'",
                              fm="---\nname: N\ncolour: red\n---\n")

    def test_missing_name(self):
        self.assertParseError("", r":1: front matter must set 'name'",
                              fm="---\ntitle: T\n---\n")

    def test_missing_front_matter(self):
        self.assertParseError("## S\n", r":1: missing front matter", fm="")

    def test_unclosed_front_matter(self):
        self.assertParseError("", r":1: front matter is not closed", fm="---\nname: N\n")

    def test_line_without_colon(self):
        self.assertParseError("", r":2: expected 'key: value'", fm="---\njust text\nname: N\n---\n")

    def test_duplicate_key(self):
        self.assertParseError("", r":3: duplicate front matter key 'name'",
                              fm="---\nname: A\nname: B\n---\n")

    def test_bad_lang(self):
        self.assertParseError("", r":3: lang must be 'en' or 'ko'",
                              fm="---\nname: A\nlang: english\n---\n")

    def test_empty_font_list(self):
        self.assertParseError("", r":3: font needs at least one font name",
                              fm="---\nname: A\nfont: ,\n---\n")

    def test_front_matter_in_included_file_errors(self):
        self.assertParseError("@a.md\n", r"a\.md:1: front matter is only allowed in the root file",
                              **{"a.md": "---\nname: X\n---\n"})

    def test_front_matter_in_file_included_first_errors(self):
        with self.assertRaisesRegex(ResumeError, r"fm\.md:1: front matter is only allowed"):
            self.write("fm.md", "---\nname: X\n---\n")
            parse(load_lines(self.write("root.md", "@fm.md\n## S\n")))

    def test_included_line_inside_front_matter_errors(self):   # clarification 12
        self.write("t.md", "title: T\n")
        root = self.write("root.md", "---\nname: N\n@t.md\n---\n")
        with self.assertRaisesRegex(
                ResumeError, rf"^{re.escape(str(self.d / 't.md'))}:1: front matter lines must come from the root file"):
            parse(load_lines(root))

    def test_stray_rule_in_body_errors(self):
        self.assertParseError("## S\n---\n", r":5: '---' is only allowed")


class BodyTest(ParseTestBase):
    def test_entry_title_date_subtitle_side(self):
        doc = self.doc("## Work\n### UX Factory, Inc. | Aug. 2015 - Present\nCEO | Seoul\n- did x")
        s = doc.sections[0]
        self.assertEqual(s.title, "Work")
        e = s.children[0]
        self.assertIsInstance(e, Entry)
        self.assertEqual((e.title, e.date, e.subtitle, e.side),
                         ("UX Factory, Inc.", "Aug. 2015 - Present", "CEO", "Seoul"))
        self.assertEqual(e.items[0].text, "did x")
        self.assertEqual(e.items[0].date, None)
        self.assertEqual(e.origin.lineno, 5)
        self.assertEqual(e.items[0].origin.lineno, 7)

    def test_entry_without_date_or_subtitle(self):
        e = self.doc("## A\n### Awards\n- x\n").sections[0].children[0]
        self.assertEqual((e.title, e.date, e.subtitle, e.side), ("Awards", None, None, None))

    def test_subtitle_after_blank_line(self):
        e = self.doc("## A\n### E\n\nRole\n- x\n").sections[0].children[0]
        self.assertEqual(e.subtitle, "Role")

    def test_split_right_uses_last_pipe_and_escape(self):
        self.assertEqual(split_right("A | B | 2020"), ("A | B", "2020"))
        self.assertEqual(split_right(r"A \| B"), ("A | B", None))
        self.assertEqual(split_right("A|B"), ("A|B", None))   # pipe needs spaces
        self.assertEqual(split_right(r"A | B \| C"), ("A", "B | C"))
        self.assertEqual(split_right(r"\*x\* | 1"), (r"\*x\*", "1"))  # other escapes kept
        self.assertEqual(split_right("A |"), ("A |", None))

    def test_escaped_pipe_in_bullet(self):
        item = self.doc("## S\n- a \\| b | 2020\n").sections[0].children[0]
        self.assertEqual((item.text, item.date), ("a | b", "2020"))

    def test_continuation_lines_literal(self):
        item = self.doc("## P\n- Title\n  S. Park, Junyoung Park\n  - presented at ISSCC\n"
                        ).sections[0].children[0]
        self.assertEqual(item.text, "Title")
        self.assertEqual(item.details, ["S. Park, Junyoung Park", "- presented at ISSCC"])

    def test_continuation_keeps_pipes(self):
        item = self.doc("## P\n- T\n  a | b \\| c\n").sections[0].children[0]
        self.assertEqual(item.details, ["a | b | c"])

    def test_tab_indented_continuation(self):
        item = self.doc("## P\n- T\n\tdetail\n").sections[0].children[0]
        self.assertEqual(item.details, ["detail"])

    def test_indented_line_without_bullet_errors(self):
        self.assertParseError("## P\n  orphan\n", r":5: continuation line without a bullet")

    def test_indented_line_after_subtitle_errors(self):
        self.assertParseError("## P\n### E\nRole\n  orphan\n",
                              r":7: continuation line without a bullet")

    def test_continuation_from_other_file_errors(self):   # clarification 5
        self.assertParseError("## P\n- T\n@a.md\n", r"a\.md:1: continuation line without a bullet",
                              **{"a.md": "  detail\n"})

    def test_marker_on_continuation_errors(self):   # clarification 5
        self.assertParseError("## P\n- T\n  d {.full}\n",
                              r":6: markers are not allowed on continuation lines")

    def test_marker_after_date(self):
        item = self.doc("## A\n- Award | Apr. 2009 {.full}\n").sections[0].children[0]
        self.assertEqual((item.text, item.date, item.variants),
                         ("Award", "Apr. 2009", FULL))

    def test_split_marker(self):
        line = load_lines(self.write("x.md", "x"))[0]
        self.assertEqual(split_marker("- a {.short}", line), ("- a", SHORT))
        self.assertEqual(split_marker("- a{.full}", line), ("- a", FULL))
        self.assertEqual(split_marker("- a", line), ("- a", VARIANTS))
        # clarification 11: other trailing braces are ordinary text
        self.assertEqual(split_marker("- set {x} here", line), ("- set {x} here", VARIANTS))
        self.assertEqual(split_marker("- set {x}", line), ("- set {x}", VARIANTS))
        self.assertEqual(split_marker("- f(a) = {1, 2}", line), ("- f(a) = {1, 2}", VARIANTS))
        # an escaped brace is never a marker
        self.assertEqual(split_marker("- a \\{.full}", line), ("- a \\{.full}", VARIANTS))

    def test_bad_markers_error(self):   # Review Focus 2, clarification 11
        for bad in ["- x {.ful}", "- x {full}", "- x { .full }", "## S {.Full}",
                    "- x {FULL}", "- x {Short}", "- x {. short}", "- x {.full .short}",
                    "- x {.5}", "- x {.full} {.short}", "- x {.full} {.ful}"]:
            with self.subTest(bad=bad):
                self.assertParseError("## Z\n" + bad + "\n", r":5: invalid variant marker")

    def test_bad_marker_on_entry_and_subtitle(self):
        self.assertParseError("## Z\n### E {short}\n", r":5: invalid variant marker")
        self.assertParseError("## Z\n### E\nRole {.shrt}\n", r":6: invalid variant marker")

    def test_effective_variants_intersect_and_warn(self):
        doc = self.doc("## S {.full}\n- x {.short}\n- y\n")
        s = doc.sections[0]
        self.assertEqual(s.variants, FULL)
        self.assertEqual(s.children[0].variants, frozenset())
        self.assertEqual(s.children[1].variants, FULL)
        self.assertEqual(len(doc.warnings), 1)
        self.assertRegex(doc.warnings[0], r"root\.md:5: .*can never appear")

    def test_include_conflict_warns_once_on_first_line(self):   # clarification 13
        doc = self.doc("## S {.full}\n@a.md {.short}\n- z\n", **{"a.md": "- x\n- y\n"})
        kids = doc.sections[0].children
        self.assertEqual([k.variants for k in kids], [frozenset(), frozenset(), FULL])
        self.assertEqual(len(doc.warnings), 1, doc.warnings)
        self.assertRegex(doc.warnings[0], r"a\.md:1: .*can never appear")

    def test_nested_empty_include_warns_once(self):   # clarification 13
        doc = self.doc("@a.md {.full}\n", **{"a.md": "@b.md {.short}\n",
                                             "b.md": "## Q\n- q\n### E\n- r\n"})
        self.assertEqual(doc.sections[0].variants, frozenset())
        self.assertEqual(len(doc.warnings), 1, doc.warnings)
        self.assertRegex(doc.warnings[0], r"b\.md:1: .*can never appear")

    def test_heading_from_include_owns_following_root_lines(self):   # clarification 13
        doc = self.doc("@a.md\n- root bullet\n", **{"a.md": "## From A\n"})
        self.assertEqual([k.text for k in doc.sections[0].children], ["root bullet"])

    def test_at_sign_is_ordinary_text(self):   # clarification 10
        doc = self.doc("## S\n@KAIST lab\n@notes.md is a file\n### Researcher @ KAIST\n"
                       "Mail a@b.c\n- @home\n")
        kids = doc.sections[0].children
        self.assertEqual([k.text for k in kids[:2]], ["@KAIST lab", "@notes.md is a file"])
        self.assertEqual((kids[2].title, kids[2].subtitle, kids[2].items[0].text),
                         ("Researcher @ KAIST", "Mail a@b.c", "@home"))

    def test_variants_through_include_scope(self):
        doc = self.doc("## S\n@a.md {.full}\n", **{"a.md": "### E\nRole {.full}\n- x {.full}\n"})
        e = doc.sections[0].children[0]
        self.assertEqual((e.variants, e.subtitle_variants, e.items[0].variants),
                         (FULL, FULL, FULL))
        self.assertEqual(doc.warnings, [])

    def test_subtitle_variants(self):
        e = self.doc("## S\n### E {.full}\nRole {.short}\n").sections[0].children[0]
        self.assertEqual((e.variants, e.subtitle_variants), (FULL, frozenset()))
        e = self.doc("## S\n### E\nRole {.short}\n").sections[0].children[0]
        self.assertEqual((e.variants, e.subtitle_variants), (VARIANTS, SHORT))

    def test_bullets_and_paragraphs_directly_under_section(self):
        doc = self.doc("## Summary\nA paragraph.\n- a bullet | 2020\nAnother paragraph {.short}\n")
        kids = doc.sections[0].children
        self.assertEqual([type(k) for k in kids], [Paragraph, Item, Paragraph])
        self.assertEqual(kids[0].text, "A paragraph.")
        self.assertEqual((kids[1].text, kids[1].date), ("a bullet", "2020"))
        self.assertEqual((kids[2].text, kids[2].variants), ("Another paragraph", SHORT))

    def test_paragraph_keeps_pipe(self):
        p = self.doc("## S\nA | B\n").sections[0].children[0]
        self.assertEqual(p.text, "A | B")

    def test_text_before_any_section_errors(self):
        self.assertParseError("hello\n", r":4: text before the first section")
        self.assertParseError("- x\n", r":4: text before the first section")
        self.assertParseError("### E\n", r":4: entry before the first section")

    def test_second_plain_line_in_entry_errors(self):
        doc_body = "## S\n### E\nsub\nmore\n"
        self.assertParseError(doc_body, r":7: unexpected text in entry; start it with '- '")

    def test_plain_line_after_bullet_in_entry_errors(self):
        self.assertParseError("## S\n### E\n- a\nrole\n", r":7: unexpected text in entry")

    def test_other_heading_levels_error(self):
        self.assertParseError("# Title\n", r":4: unsupported heading level")
        self.assertParseError("## S\n#### Deep\n", r":5: unsupported heading level")

    def test_hash_without_space_is_text(self):
        p = self.doc("## S\n#1 in class\n").sections[0].children[0]
        self.assertEqual(p.text, "#1 in class")

    def test_other_bullet_styles_error(self):
        self.assertParseError("## S\n* x\n", r":5: use '- ' for bullets")
        self.assertParseError("## S\n+ x\n", r":5: use '- ' for bullets")

    def test_empty_headings_and_bullets_error(self):
        self.assertParseError("##\n", r":4: empty section title")
        self.assertParseError("## S\n###  {.full}\n", r":5: empty entry title")
        self.assertParseError("## S\n-\n", r":5: empty bullet")

    def test_marker_only_line_errors(self):
        self.assertParseError("## S\n{.full}\n", r":5: marker without text")
        self.assertParseError("## S\n### E\n{.short}\n", r":6: marker without text")

    def test_hangul_and_special_characters(self):
        doc = self.doc("## 수상 경력\n### 은종관 장학상 | 2009년 3월\n- R&D 100% #1 $5 @x <y> ~z μW\n")
        e = doc.sections[0].children[0]
        self.assertEqual((doc.sections[0].title, e.title, e.date),
                         ("수상 경력", "은종관 장학상", "2009년 3월"))
        self.assertEqual(e.items[0].text, "R&D 100% #1 $5 @x <y> ~z μW")

    def test_section_children_from_included_bullets(self):
        doc = self.doc("## Journals\n@j.md {.full}\n", **{"j.md": "- p1\n  A. B\n- p2\n"})
        kids = doc.sections[0].children
        self.assertEqual([(k.text, k.details, k.variants) for k in kids],
                         [("p1", ["A. B"], FULL), ("p2", [], FULL)])
        self.assertEqual(kids[0].origin.path, self.d / "j.md")

    def test_errors_carry_included_file_and_line(self):
        self.assertParseError("## S\n@a.md\n", rf"^{re.escape(str(self.d / 'a.md'))}:2: ",
                              **{"a.md": "- ok\n- bad {.ful}\n"})


if __name__ == "__main__":
    unittest.main()
