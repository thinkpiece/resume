import io
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/cli/resume.md"
sys.path.insert(0, str(REPO / "scripts"))

from resumegen.emit_docx import emit_docx  # noqa: E402
from resumegen.model import Entry, Item  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.render import LOOK, contact_url, parse_inline, plain_text  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "dc": "http://purl.org/dc/elements/1.1/",
}
W = "{" + NS["w"] + "}"
R = "{" + NS["r"] + "}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _parts(data):
    with ZipFile(io.BytesIO(data)) as archive:
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()}


def _text(element):
    fragments = []
    for node in element.iter():
        if node.tag == W + "t":
            fragments.append(node.text or "")
        elif node.tag == W + "tab":
            fragments.append("\t")
        elif node.tag == W + "br":
            fragments.append("\n")
    return "".join(fragments)


def _paragraphs(document):
    return document.findall("w:body/w:p", NS)


def _expected_paragraphs(doc):
    meta = doc.meta

    def inline(text):
        return plain_text(parse_inline(text or "", meta.highlight))

    def row(left, right):
        return inline(left) + ("\t" + inline(right) if right is not None else "")

    def item_lines(item):
        yield LOOK.marker + "\t" + row(item.text, item.date)
        yield from map(inline, item.details)

    yield meta.name.upper() if meta.lang == "en" else meta.name
    if meta.title is not None:
        yield meta.title
    if meta.contacts:
        yield " · ".join(value for _, value in meta.contacts)
    for section in doc.sections:
        yield inline(section.title)
        for child in section.children:
            if isinstance(child, Entry):
                yield row(child.title, child.date)
                if child.subtitle is not None or child.side is not None:
                    yield row(child.subtitle, child.side)
                for item in child.items:
                    yield from item_lines(item)
            elif isinstance(child, Item):
                yield from item_lines(child)
            else:
                yield inline(child.text)


class DocxTest(unittest.TestCase):
    def test_filtered_document_content_and_order(self):
        for path in (FIXTURE, REPO / "content/en/resume.md", REPO / "content/ko/resume.md"):
            source = parse(load_lines(path))
            for variant in ("full", "short"):
                with self.subTest(source=path.relative_to(REPO), variant=variant):
                    doc = filter_variant(source, variant)
                    document = _parts(emit_docx(doc))["word/document.xml"]
                    self.assertEqual([_text(p) for p in _paragraphs(document)],
                                     list(_expected_paragraphs(doc)))

    def test_xml_escaping_and_literal_front_matter(self):
        doc = parse(load_lines(FIXTURE))
        doc.meta.name = 'Test Person & "Name" <q>\x00'
        doc.meta.title = '**Title** & "quotes" <y>\x08'
        source_text = '  <y> & "quotes" ]]>\x00\x1f\ud800\uffff\tthen\nnext  '
        doc.sections[0].children[0].text = source_text
        doc.meta.fonts[0] = 'Font "A" & <B>'
        data = emit_docx(doc)
        parts = _parts(data)
        document = parts["word/document.xml"]
        name, title, _, _, paragraph, *_ = _paragraphs(document)
        self.assertEqual(_text(name), 'TEST PERSON & "NAME" <Q>')
        self.assertEqual(_text(title), '**Title** & "quotes" <y>')
        self.assertEqual(_text(paragraph), '  <y> & "quotes" ]]>\tthen\nnext  ')
        self.assertTrue(all(t.get(XML_SPACE) == "preserve" for t in document.iter(W + "t")))
        with ZipFile(io.BytesIO(data)) as archive:
            self.assertIn(b'&lt;y&gt; &amp; &quot;quotes&quot; ]]&gt;',
                          archive.read("word/document.xml"))
        core = parts["docProps/core.xml"]
        for tag in ("title", "creator"):
            self.assertEqual(core.findtext(f"dc:{tag}", namespaces=NS), 'Test Person & "Name" <q>')
        fonts = parts["word/styles.xml"].find(".//w:rFonts", NS)
        self.assertEqual(fonts.get(W + "ascii"), doc.meta.fonts[0])

    def test_inline_styles_include_dates_and_links(self):
        doc = parse(load_lines(FIXTURE))
        section = doc.sections[1]
        entry = section.children[0]
        section.title = "**Work** Experience"
        entry.title = "_Example_, Inc."
        entry.date = '[**2016**](https://example.com/?a=1&b="2")'
        entry.subtitle = "**Founder** and CEO"
        entry.side = "*Seoul*"
        entry.items[0].text = r"Led \*a\* team"
        entry.items[0].date = "**2009**"
        entry.items[0].details = ["_Detail_"]
        parts = _parts(emit_docx(doc))
        document = parts["word/document.xml"]
        runs = {_text(run): run for run in document.iter(W + "r")}
        for text, tag in (("Work", "b"), ("Example", "i"), ("Founder", "b"),
                          ("low-power", "i"), ("Detail", "i"), ("2009", "b")):
            with self.subTest(text=text):
                self.assertIsNotNone(runs[text].find(f"w:rPr/w:{tag}", NS))
        highlight = runs["Test Person"]
        self.assertIsNotNone(highlight.find("w:rPr/w:b", NS))
        self.assertEqual(highlight.find("w:rPr/w:u", NS).get(W + "val"), "single")
        self.assertIn("Led *a* team", runs)
        for date_or_side, emphasis in (("Seoul", "i"), ("2016", "b"), ("2009", "b")):
            props = runs[date_or_side].find("w:rPr", NS)
            self.assertEqual(props.find("w:color", NS).get(W + "val"), LOOK.gray)
            self.assertIsNotNone(props.find(f"w:{emphasis}", NS))

        relationships = parts["word/_rels/document.xml.rels"]
        by_id = {rel.get("Id"): rel for rel in relationships if rel.get("TargetMode") == "External"}
        actual = []
        for link in document.iter(W + "hyperlink"):
            rel = by_id[link.get(R + "id")]
            self.assertEqual(rel.get("Type"), NS["r"] + "/hyperlink")
            actual.append((_text(link), rel.get("Target")))
        expected = [(value, contact_url(kind, value)) for kind, value in doc.meta.contacts
                    if kind != "location"]
        expected.extend([("2016", 'https://example.com/?a=1&b="2"'),
                         ("ISSCC", "https://isscc.org/a_b")])
        self.assertEqual(actual, expected)

    def test_empty_headings_and_side_without_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / "empty.md"
            src.write_text("---\nname: Name\n---\n## First\n## Second\n### Entry\n",
                           encoding="utf-8")
            doc = filter_variant(parse(load_lines(src)), "short")
        entry = doc.sections[-1].children[-1]
        entry.side = "Right"
        document = _parts(emit_docx(doc))["word/document.xml"]
        self.assertEqual([_text(p) for p in _paragraphs(document)],
                         ["NAME", "First", "Second", "Entry", "\tRight"])
        entry.side = None
        document = _parts(emit_docx(doc))["word/document.xml"]
        self.assertEqual([_text(p) for p in _paragraphs(document)],
                         ["NAME", "First", "Second", "Entry"])

    def test_latin_runs_in_korean_documents_have_english_wrap_language(self):
        doc = parse(load_lines(REPO / "content/ko/resume.md"))
        document = _parts(emit_docx(doc))["word/document.xml"]
        runs = {_text(run): run for run in document.iter(W + "r")}
        self.assertIsNone(runs["핵심 요약"].find("w:rPr/w:lang", NS))
        self.assertEqual(runs["KAIST"].find("w:rPr/w:lang", NS).attrib,
                         {W + "val": "en-US", W + "eastAsia": "ko-KR"})

    def test_deterministic_package_and_content_types(self):
        doc = parse(load_lines(FIXTURE))
        data = emit_docx(doc)
        self.assertEqual(data, emit_docx(doc))
        parts = _parts(data)
        with ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), [
                "[Content_Types].xml", "_rels/.rels", "word/document.xml",
                "word/styles.xml", "word/settings.xml", "word/_rels/document.xml.rels",
                "docProps/core.xml", "docProps/app.xml",
            ])
            for entry in archive.infolist():
                self.assertEqual(entry.compress_type, ZIP_DEFLATED)
                self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
        content_types = parts["[Content_Types].xml"]
        defaults = {n.get("Extension"): n.get("ContentType") for n in content_types.findall("ct:Default", NS)}
        self.assertEqual(defaults["rels"], "application/vnd.openxmlformats-package.relationships+xml")
        overrides = {n.get("PartName"): n.get("ContentType") for n in content_types.findall("ct:Override", NS)}
        self.assertEqual(set(overrides), {"/" + name for name in parts if name.startswith(("word/", "docProps/"))
                                         and name.endswith(".xml")})
        self.assertEqual(overrides["/docProps/core.xml"],
                         "application/vnd.openxmlformats-package.core-properties+xml")
        self.assertEqual({n.get("Target") for n in parts["_rels/.rels"]},
                         {"word/document.xml", "docProps/core.xml", "docProps/app.xml"})
        self.assertEqual(len(parts["docProps/core.xml"]), 2)

    def test_dimensions_fonts_and_named_styles(self):
        for path, size, lang, east_asia in (
            (FIXTURE, (12240, 15840), "en-US", "NanumMyeongjo"),
            (REPO / "content/ko/resume.md", (11906, 16838), "ko-KR", "Pretendard"),
        ):
            with self.subTest(source=path.relative_to(REPO)):
                doc = parse(load_lines(path))
                parts = _parts(emit_docx(doc))
                document = parts["word/document.xml"]
                sec = document.find("w:body/w:sectPr", NS)
                page = sec.find("w:pgSz", NS)
                self.assertEqual(tuple(int(page.get(W + k)) for k in ("w", "h")), size)
                margins = sec.find("w:pgMar", NS)
                self.assertEqual(tuple(int(margins.get(W + k)) for k in ("top", "right", "bottom", "left")),
                                 (720, 864, 720, 864))
                styles = parts["word/styles.xml"]
                defaults = styles.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
                fonts = defaults.find("w:rFonts", NS)
                for tag in ("ascii", "hAnsi", "cs"):
                    self.assertEqual(fonts.get(W + tag), doc.meta.fonts[0])
                self.assertEqual(fonts.get(W + "eastAsia"), east_asia)
                self.assertEqual(defaults.find("w:lang", NS).attrib,
                                 {W + "val": lang, W + "eastAsia": "ko-KR"})
                self.assertEqual(styles.find(".//w:wordWrap", NS).get(W + "val"), "1")
                self.assertEqual(defaults.find("w:sz", NS).get(W + "val"), "20")
                self.assertEqual(defaults.find("w:color", NS).get(W + "val"), "000000")
                by_name = {n.get(W + "styleId"): n for n in styles.findall("w:style", NS)}
                self.assertEqual(set(by_name), {"Normal", "ResumeName", "ResumeTitle", "ResumeContacts",
                                               "ResumeSection", "ResumeEntry", "ResumeSubtitle", "ResumeItem",
                                               "ResumeDetail", "ResumeParagraph"})
                for style, points in (("ResumeName", 40), ("ResumeTitle", 23), ("ResumeSection", 23),
                                      ("ResumeEntry", 22), ("ResumeDetail", 18)):
                    self.assertEqual(by_name[style].find("w:rPr/w:sz", NS).get(W + "val"), str(points))
                self.assertIsNotNone(by_name["ResumeSection"].find("w:rPr/w:caps", NS))
                self.assertIsNotNone(by_name["ResumeSection"].find("w:pPr/w:pBdr/w:bottom", NS))
                for style in ("ResumeSection", "ResumeEntry", "ResumeSubtitle"):
                    self.assertIsNotNone(by_name[style].find("w:pPr/w:keepNext", NS))
                for style in ("ResumeEntry", "ResumeSubtitle", "ResumeItem"):
                    tab = by_name[style].find('w:pPr/w:tabs/w:tab[@w:val="right"]', NS)
                    self.assertEqual(int(tab.get(W + "pos")), size[0] - 1728)
                self.assertEqual(by_name["ResumeItem"].find("w:pPr/w:ind", NS).get(W + "hanging"), "200")


class DocxCliTest(unittest.TestCase):
    def test_builds_without_typst_and_removes_stale_output_on_parse_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "build" / "resume.docx"
            bad = root / "bad.md"
            bad.write_text("---\nname: Test\n---\n## S\n- x {.ful}\n", encoding="utf-8")
            env = dict(os.environ, RESUME_ROOT=str(root), PATH="/nonexistent")
            cli = [sys.executable, str(REPO / "scripts/build_resume.py")]
            args = ["--variant", "full", "-o", str(out)]
            built = subprocess.run(cli + [str(FIXTURE)] + args, env=env, cwd=root,
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertIn("word/document.xml", _parts(out.read_bytes()))
            self.assertFalse(out.with_suffix(".typ").exists())
            failed = subprocess.run(cli + [str(bad)] + args, env=env, cwd=root,
                                    capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("invalid variant marker", failed.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
