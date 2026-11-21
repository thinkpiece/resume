import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen.model import Meta  # noqa: E402
from resumegen.render import (LOOK, PAGE_MARGINS_IN, Emph, Highlight, Link,  # noqa: E402
                              Strong, Text, contact_url, header_name, paper_size_mm,
                              parse_inline, plain_text)


class ParseInlineTest(unittest.TestCase):
    def test_plain_text_is_one_node(self):
        self.assertEqual(parse_inline('R&D 100% #1 <y> "q" 산업'),
                         (Text('R&D 100% #1 <y> "q" 산업'),))

    def test_empty(self):
        self.assertEqual(parse_inline(""), ())

    def test_bold_italic_link(self):
        self.assertEqual(parse_inline("**B** and *i* [t](http://x.y)"), (
            Strong((Text("B"),)), Text(" and "), Emph((Text("i"),)), Text(" "),
            Link("http://x.y", (Text("t"),))))

    def test_nesting(self):
        self.assertEqual(parse_inline("*a **b** c*"),
                         (Emph((Text("a "), Strong((Text("b"),)), Text(" c"))),))
        self.assertEqual(parse_inline("[*Nature*, 2020](https://n.com)"),
                         (Link("https://n.com", (Emph((Text("Nature"),)), Text(", 2020"))),))

    def test_escapes_are_resolved(self):
        self.assertEqual(parse_inline(r"\*not\* \| C:\dir"), (Text(r"*not* | C:\dir"),))

    def test_literal_delimiters(self):
        for text in ("**open", "2 * 3 * 4", "snake_case_name", "[text](unclosed", "****"):
            with self.subTest(text=text):
                self.assertEqual(parse_inline(text), (Text(text),))

    def test_highlight_at_any_depth_never_in_url(self):
        self.assertEqual(
            parse_inline("S. Park, **A B** [A B](http://x/A B), A B.", "A B"),
            (Text("S. Park, "), Strong((Highlight("A B"),)), Text(" "),
             Link("http://x/A B", (Highlight("A B"),)), Text(", "), Highlight("A B"),
             Text(".")))

    def test_highlight_absent_or_unset(self):
        self.assertEqual(parse_inline("nobody", "A B"), (Text("nobody"),))
        self.assertEqual(parse_inline("A B", None), (Text("A B"),))
        self.assertEqual(parse_inline("A B", ""), (Text("A B"),))

    def test_plain_text(self):
        nodes = parse_inline("**B** *i* [t](http://x.y) N, \\*", "N")
        self.assertEqual(plain_text(nodes), "B i t N, *")


class HeaderAndPageTest(unittest.TestCase):
    def meta(self, name, lang):
        return Meta(name=name, title=None, lang=lang, paper="a4", fonts=["Charter"],
                    highlight=None, contacts=[])

    def test_header_name(self):
        self.assertEqual(header_name(self.meta("Junyoung Park", "en")), "JUNYOUNG PARK")
        self.assertEqual(header_name(self.meta("박준영 (Junyoung Park)", "ko")),
                         "박준영 (Junyoung Park)")

    def test_contact_url(self):
        self.assertEqual(contact_url("email", "a@b.c"), "mailto:a@b.c")
        self.assertEqual(contact_url("phone", "+82-10-2542-5500"), "tel:+821025425500")
        self.assertEqual(contact_url("homepage", "http://x.y"), "http://x.y")
        self.assertIsNone(contact_url("location", "Seongnam-si"))

    def test_paper_sizes(self):
        self.assertEqual(paper_size_mm("a4"), (210.0, 297.0))
        self.assertEqual(paper_size_mm("us-letter"), (215.9, 279.4))
        self.assertEqual(paper_size_mm("us-tabloid"), (279.4, 431.8))
        self.assertEqual(paper_size_mm("iso-b5"), (176.0, 250.0))
        self.assertEqual(paper_size_mm("jis-b5"), (210.0, 297.0))   # not in the table: A4

    def test_paper_table_names_are_typst_papers(self):
        from resumegen.parse import TYPST_PAPERS
        from resumegen.render import PAPER_SIZES_MM
        self.assertLessEqual(set(PAPER_SIZES_MM), TYPST_PAPERS)

    def test_look_matches_template(self):
        typ = (Path(__file__).resolve().parents[1] / "template" / "resume.typ").read_text(
            encoding="utf-8")
        self.assertIn(f"#let _size = {LOOK.text_pt:g}pt", typ)
        self.assertIn(f"#let _name-size = {LOOK.name_pt:g}pt", typ)
        self.assertIn(f"#let _section-size = {LOOK.section_pt:g}pt", typ)
        self.assertIn(f"#let _entry-size = {LOOK.entry_pt:g}pt", typ)
        self.assertIn(f"#let _detail-size = {LOOK.detail_em:g}em", typ)
        self.assertIn(f"#let _gray = luma({int(LOOK.gray[:2], 16)})", typ)
        self.assertIn(f"margin: (left: {PAGE_MARGINS_IN['left']}in, "
                      f"right: {PAGE_MARGINS_IN['right']}in, top: {PAGE_MARGINS_IN['top']}in, "
                      f"bottom: {PAGE_MARGINS_IN['bottom']}in)", typ)


if __name__ == "__main__":
    unittest.main()
