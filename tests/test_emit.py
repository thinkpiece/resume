import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen.emit import contact_url, emit_typst, inline_to_typst, typst_string  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402


class InlineTest(unittest.TestCase):
    def test_plain_and_escapes(self):
        self.assertEqual(inline_to_typst('a "q" \\ b'), '[#"a \\"q\\" \\\\ b"]')

    def test_empty(self):
        self.assertEqual(inline_to_typst(""), "[]")

    def test_special_characters_stay_in_strings(self):
        out = inline_to_typst("R&D 100% #1 $5 @x <y> ~z // c 54 μW 산업")
        self.assertEqual(out, '[#"R&D 100% #1 $5 @x <y> ~z // c 54 μW 산업"]')

    def test_typst_markup_characters_are_inert(self):
        out = inline_to_typst("= h `raw` ]x[ #let a = 1 /* c */ 'q' - + = :smile:")
        self.assertEqual(out, '[#"= h `raw` ]x[ #let a = 1 /* c */ \'q\' - + = :smile:"]')

    def test_bold_italic_link(self):
        # The plan's literal dropped the space before the link; the space is content.
        self.assertEqual(inline_to_typst("**B** and *i* [t](http://x.y)"),
                         '[#strong[#"B"]#" and "#emph[#"i"]#" "#link("http://x.y")[#"t"]]')
        self.assertEqual(inline_to_typst("**B** and *i*[t](http://x.y)"),
                         '[#strong[#"B"]#" and "#emph[#"i"]#link("http://x.y")[#"t"]]')

    def test_underscore_italic(self):
        self.assertEqual(inline_to_typst("_it_"), '[#emph[#"it"]]')

    def test_nested_bold_in_italic_and_link_label(self):
        self.assertEqual(inline_to_typst("*a **b** c*"),
                         '[#emph[#"a "#strong[#"b"]#" c"]]')
        self.assertEqual(inline_to_typst("[*Nature*, 2020](https://n.com)"),
                         '[#link("https://n.com")[#emph[#"Nature"]#", 2020"]]')

    def test_underscores_literal_inside_words_and_urls(self):   # Review Focus 3
        self.assertEqual(inline_to_typst("snake_case_name"), '[#"snake_case_name"]')
        self.assertEqual(inline_to_typst("[a](https://a.com/a_b_c)"),
                         '[#link("https://a.com/a_b_c")[#"a"]]')
        self.assertEqual(inline_to_typst("mail junyoung_park@x.com"),
                         '[#"mail junyoung_park@x.com"]')
        self.assertEqual(inline_to_typst("an _it_ word"), '[#"an "#emph[#"it"]#" word"]')
        self.assertEqual(inline_to_typst("see https://a.com/a_b_c now"),
                         '[#"see https://a.com/a_b_c now"]')
        self.assertEqual(inline_to_typst("_snake_case_"), '[#emph[#"snake_case"]]')

    def test_stars_in_urls_and_link_labels(self):
        self.assertEqual(inline_to_typst("*see [x](http://a/*)*"),
                         '[#emph[#"see "#link("http://a/*")[#"x"]]]')

    def test_link_url_with_parentheses_and_quotes(self):
        self.assertEqual(inline_to_typst('[w](https://en.wikipedia.org/wiki/A_(b)) "q"'),
                         '[#link("https://en.wikipedia.org/wiki/A_(b)")[#"w"]#" \\"q\\""]')

    def test_backslash_escapes(self):
        self.assertEqual(inline_to_typst(r"\*not\* \_x\_"), '[#"*not* _x_"]')
        self.assertEqual(inline_to_typst(r"\[a\](b) \\ \{.full}"), '[#"[a](b) \\\\ {.full}"]')

    def test_backslash_before_non_punctuation_is_literal(self):   # clarification 6
        self.assertEqual(inline_to_typst(r"C:\dir \한 end\ "), '[#"C:\\\\dir \\\\한 end\\\\ "]')
        self.assertEqual(inline_to_typst("x\\"), '[#"x\\\\"]')

    def test_unclosed_and_spaced_delimiters_stay_literal(self):
        self.assertEqual(inline_to_typst("**open"), '[#"**open"]')
        self.assertEqual(inline_to_typst("a *b"), '[#"a *b"]')
        self.assertEqual(inline_to_typst("2 * 3 * 4"), '[#"2 * 3 * 4"]')
        self.assertEqual(inline_to_typst("[text] (x)"), '[#"[text] (x)"]')
        self.assertEqual(inline_to_typst("[text](unclosed"), '[#"[text](unclosed"]')
        self.assertEqual(inline_to_typst("****"), '[#"****"]')

    def test_highlight(self):
        self.assertEqual(inline_to_typst("S. Park, Junyoung Park, H. Yoo.", "Junyoung Park"),
                         '[#"S. Park, "#hl("Junyoung Park")#", H. Yoo."]')

    def test_highlight_at_any_depth_never_in_url(self):   # clarification 9
        self.assertEqual(
            inline_to_typst("**Junyoung Park** [Junyoung Park](http://x/Junyoung Park)",
                            "Junyoung Park"),
            '[#strong[#hl("Junyoung Park")]#" "'
            '#link("http://x/Junyoung Park")[#hl("Junyoung Park")]]')

    def test_highlight_twice_and_absent(self):
        self.assertEqual(inline_to_typst("A, B, A", "A"), '[#hl("A")#", B, "#hl("A")]')
        self.assertEqual(inline_to_typst("nobody", "A B"), '[#"nobody"]')

    def test_typst_string(self):
        self.assertEqual(typst_string('a"b\\c'), '"a\\"b\\\\c"')
        self.assertEqual(typst_string("t\tx\n"), '"t\\tx\\n"')


class ContactTest(unittest.TestCase):
    def test_contact_urls(self):   # clarification 4
        self.assertEqual(contact_url("email", "a@b.c"), "mailto:a@b.c")
        self.assertEqual(contact_url("phone", "+82-10-2542-5500"), "tel:+821025425500")
        self.assertEqual(contact_url("phone", "(010) 2542 5500"), "tel:01025425500")
        self.assertEqual(contact_url("homepage", "http://x.y"), "http://x.y")
        self.assertEqual(contact_url("linkedin", "https://l.in/p"), "https://l.in/p")
        self.assertEqual(contact_url("github", "https://github.com/p"), "https://github.com/p")
        self.assertIsNone(contact_url("location", "Seongnam-si"))


class EmitDocumentTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def doc(self, text, variant="full"):
        root = self.d / "root.md"
        root.write_text(text, encoding="utf-8")
        return filter_variant(parse(load_lines(root)), variant)

    def test_emit_document_shape(self):
        doc = self.doc(
            "---\nname: Junyoung Park\ntitle: AI \"SoC\" Founder\nfont: Charter, NanumMyeongjo\n"
            "phone: +82-10-2542-5500\nemail: junyoung@uxf.ai\nlocation: Seongnam-si 13105\n---\n"
            "## Work\n### UX | 2015\n- did *x* | 2016\n  - presented at *ISSCC*\n  second\n")
        out = emit_typst(doc)
        self.assertTrue(out.startswith('#import "/template/resume.typ": *\n'))
        self.assertIn('#show: resume.with(\n', out)
        self.assertIn('  name: "Junyoung Park",\n', out)
        self.assertIn('  title: "AI \\"SoC\\" Founder",\n', out)
        self.assertIn('  lang: "en",\n  paper: "us-letter",\n', out)
        self.assertIn('fonts: ("Charter", "NanumMyeongjo"),', out)
        self.assertIn('(kind: "phone", text: "+82-10-2542-5500", url: "tel:+821025425500"),', out)
        self.assertIn('(kind: "email", text: "junyoung@uxf.ai", url: "mailto:junyoung@uxf.ai"),', out)
        self.assertIn('(kind: "location", text: "Seongnam-si 13105", url: none),', out)
        self.assertLess(out.index('kind: "phone"'), out.index('kind: "email"'))
        self.assertIn('#section([#"Work"])[', out)
        self.assertIn('#entry(title: [#"UX"], date: [#"2015"], subtitle: none, side: none)[', out)
        self.assertIn('#item([#"did "#emph[#"x"]], date: [#"2016"], '
                      'details: ([#"- presented at "#emph[#"ISSCC"]], [#"second"]))', out)

    def test_exact_output(self):
        doc = self.doc(
            "---\nname: N\nlang: ko\npaper: a4\nfont: Pretendard\nhighlight: N\n---\n"
            "## 요약\n문단입니다.\n- 항목 | 2020\n### 회사 | 2015 - 현재\n대표 | 서울\n- 일\n  N 외\n"
            "### 빈 항목\n")
        self.assertEqual(emit_typst(doc), (
            '#import "/template/resume.typ": *\n'
            '#show: resume.with(\n'
            '  name: "N",\n'
            '  title: none,\n'
            '  lang: "ko",\n'
            '  paper: "a4",\n'
            '  fonts: ("Pretendard",),\n'
            '  contacts: (),\n'
            ')\n'
            '#section([#"요약"])[\n'
            '  #paragraph([#"문단입니다."])\n'
            '  #item([#"항목"], date: [#"2020"])\n'
            '  #entry(title: [#"회사"], date: [#"2015 - 현재"], subtitle: [#"대표"], side: [#"서울"])[\n'
            '    #item([#"일"], details: ([#hl("N")#" 외"],))\n'
            '  ]\n'
            '  #entry(title: [#"빈 항목"], date: none, subtitle: none, side: none)[\n'
            '  ]\n'
            ']\n'))

    def test_short_variant_emits_only_short_content(self):
        text = "---\nname: N\n---\n## A {.full}\n- long\n## B\n- s {.short}\n- f {.full}\n"
        out = emit_typst(self.doc(text, "short"))
        self.assertNotIn('"A"', out)
        self.assertNotIn('"long"', out)
        self.assertNotIn('"f"', out)
        self.assertIn('#item([#"s"])', out)


if __name__ == "__main__":
    unittest.main()
