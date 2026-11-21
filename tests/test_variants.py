import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from resumegen.parse import parse  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

FM = "---\nname: Test Person\n---\n"


class VariantTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def doc(self, body, **files):
        for rel, text in files.items():
            (self.d / rel).write_text(text, encoding="utf-8")
        root = self.d / "root.md"
        root.write_text(FM + body, encoding="utf-8")
        return parse(load_lines(root))

    @staticmethod
    def titles(doc):
        return [s.title for s in doc.sections]

    @staticmethod
    def texts(children):
        out = []
        for c in children:
            out.append(getattr(c, "title", None) or c.text)
        return out

    def test_section_marker_removes_subtree(self):
        doc = self.doc("## Work\n- w\n## Talks {.full}\n- t1\n")
        self.assertEqual(self.titles(filter_variant(doc, "short")), ["Work"])
        self.assertEqual(self.titles(filter_variant(doc, "full")), ["Work", "Talks"])

    def test_entry_bullet_subtitle_markers(self):
        doc = self.doc("## S\n### E1 {.full}\n- a\n### E2\nRole {.full}\n- b {.full}\n- c\n")
        short = filter_variant(doc, "short").sections[0].children
        self.assertEqual([e.title for e in short], ["E2"])
        self.assertEqual((short[0].subtitle, [i.text for i in short[0].items]), (None, ["c"]))
        full = filter_variant(doc, "full").sections[0].children
        self.assertEqual([e.title for e in full], ["E1", "E2"])
        self.assertEqual((full[1].subtitle, [i.text for i in full[1].items]), ("Role", ["b", "c"]))

    def test_short_markers_reverse(self):
        doc = self.doc("## S {.short}\n### E | 2020\nRole | Seoul {.short}\n- x {.short}\n"
                       "## T\n- summary {.short}\n- long\n")
        full = filter_variant(doc, "full")
        self.assertEqual(self.titles(full), ["T"])
        self.assertEqual(self.texts(full.sections[0].children), ["long"])
        short = filter_variant(doc, "short")
        e = short.sections[0].children[0]
        self.assertEqual((e.subtitle, e.side, [i.text for i in e.items]), ("Role", "Seoul", ["x"]))
        self.assertEqual(self.texts(short.sections[1].children), ["summary", "long"])

    def test_dropped_subtitle_clears_side(self):
        doc = self.doc("## S\n### E\nRole | Seoul {.full}\n- x\n")
        e = filter_variant(doc, "short").sections[0].children[0]
        self.assertEqual((e.subtitle, e.side), (None, None))

    def test_include_marker_applies(self):
        doc = self.doc("## Pubs\n@j.md {.full}\n", **{"j.md": "- p1\n- p2\n"})
        self.assertEqual(filter_variant(doc, "short").sections, [])   # emptied by filtering → dropped
        self.assertEqual(self.texts(filter_variant(doc, "full").sections[0].children), ["p1", "p2"])

    def test_emptied_entry_dropped_source_empty_entry_kept(self):
        doc = self.doc("## Edu\n### PhD | 2014\n- x {.full}\n### BS | 2009\n")
        self.assertEqual([e.title for e in filter_variant(doc, "short").sections[0].children], ["BS"])
        self.assertEqual([e.title for e in filter_variant(doc, "full").sections[0].children],
                         ["PhD", "BS"])

    def test_entry_with_surviving_subtitle_kept(self):
        doc = self.doc("## W\n### Co | 2015\nCEO\n- a {.full}\n")
        e = filter_variant(doc, "short").sections[0].children[0]
        self.assertEqual((e.title, e.subtitle, e.items), ("Co", "CEO", []))

    def test_source_empty_section_kept(self):
        doc = self.doc("## Empty\n## Other {.full}\n- x\n")
        self.assertEqual(self.titles(filter_variant(doc, "short")), ["Empty"])

    def test_section_emptied_through_entries_dropped(self):
        doc = self.doc("## S\n### A {.full}\n### B\n- b {.full}\n## T\n- t\n")
        self.assertEqual(self.titles(filter_variant(doc, "short")), ["T"])

    def test_paragraph_markers(self):
        doc = self.doc("## Sum\nLong text. {.full}\nShort text. {.short}\nBoth.\n")
        self.assertEqual(self.texts(filter_variant(doc, "full").sections[0].children),
                         ["Long text.", "Both."])
        self.assertEqual(self.texts(filter_variant(doc, "short").sections[0].children),
                         ["Short text.", "Both."])

    def test_never_visible_item_absent_from_both(self):
        doc = self.doc("## S {.full}\n- x {.short}\n- y\n")
        for v in ("full", "short"):
            texts = [t for s in filter_variant(doc, v).sections
                     for t in self.texts(s.children)]
            self.assertNotIn("x", texts)
        self.assertEqual(len(doc.warnings), 1)

    def test_details_follow_their_bullet(self):
        doc = self.doc("## P\n- p1 {.full}\n  authors\n- p2\n  more\n")
        items = filter_variant(doc, "short").sections[0].children
        self.assertEqual([(i.text, i.details) for i in items], [("p2", ["more"])])

    def test_input_untouched_and_warnings_kept(self):
        doc = self.doc("## S {.full}\n- x {.short}\n### E\nR {.full}\n- y {.full}\n- z\n")
        before = copy.deepcopy(doc)
        out = filter_variant(doc, "short")
        self.assertEqual(doc, before)
        self.assertIsNot(out, doc)
        self.assertEqual(out.warnings, doc.warnings)
        self.assertEqual(out.meta, doc.meta)
        out_full = filter_variant(doc, "full")
        out_full.sections[0].children[0].items.append(None)
        out_full.sections[0].children[0].items[0].details.append("mutated")
        self.assertEqual(doc, before)

    def test_bad_variant_raises_value_error(self):
        doc = self.doc("## S\n- x\n")
        with self.assertRaises(ValueError):
            filter_variant(doc, "long")


if __name__ == "__main__":
    unittest.main()
