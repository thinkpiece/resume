"""Turn a filtered Document into an editable Word document."""

from __future__ import annotations

import re
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .model import Document, Entry, Item, Meta, Paragraph
from .render import (LOOK, PAGE_MARGINS_IN, Emph, Highlight, Link, Node, Strong,
                     Text, contact_url, header_name, paper_size_mm, parse_inline)

_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006"
_MIME = "application/vnd.openxmlformats-officedocument"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_INVALID_XML = re.compile(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]")
_RUN_BREAKS = re.compile(r"(\r\n|[\t\r\n])")
_ASCII_LETTER = re.compile(r"[A-Za-z]")
_XML_WHITESPACE = {9: "&#9;", 10: "&#10;", 13: "&#13;"}

_CONTENT_TYPES = f"""<Types xmlns="{_PKG}/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="{_MIME}.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="{_MIME}.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="{_MIME}.wordprocessingml.settings+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="{_MIME}.extended-properties+xml"/>
</Types>"""

_PACKAGE_RELS = f"""<Relationships xmlns="{_PKG}/relationships">
  <Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="{_PKG}/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="{_REL}/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

_APP_PROPERTIES = """<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Resume generator</Application>
</Properties>"""


def _xml(text: str) -> str:
    return escape(_INVALID_XML.sub("", text), quote=True).translate(_XML_WHITESPACE)


def _size(points: float) -> str:
    half_points = round(points * 2)
    return f'<w:sz w:val="{half_points}"/><w:szCs w:val="{half_points}"/>'


def _paragraph(style: str, runs: str, *, keep_next: bool = False) -> str:
    keep = "<w:keepNext/>" if keep_next else ""
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{keep}</w:pPr>{runs}</w:p>'


class _Body:
    def __init__(self, meta: Meta):
        self.highlight = meta.highlight
        self.korean = meta.lang == "ko"
        self.links: dict[str, str] = {}

    def _run(self, text: str, properties: str = "") -> str:
        parts = []
        for part in _RUN_BREAKS.split(text):
            if part == "\t":
                parts.append("<w:tab/>")
            elif part in ("\r\n", "\r", "\n"):
                parts.append("<w:br/>")
            elif part:
                parts.append(f'<w:t xml:space="preserve">{_xml(part)}</w:t>')
        # Give English words their own break rules in mixed-script Korean resumes.
        if self.korean and _ASCII_LETTER.search(text):
            properties += '<w:lang w:val="en-US" w:eastAsia="ko-KR"/>'
        props = f"<w:rPr>{properties}</w:rPr>" if properties else ""
        return f'<w:r>{props}{"".join(parts)}</w:r>'

    def _link(self, url: str, runs: str) -> str:
        rel_id = self.links.setdefault(url, f"rId{len(self.links) + 3}")
        return f'<w:hyperlink r:id="{rel_id}">{runs}</w:hyperlink>'

    def _inline(self, nodes: tuple[Node, ...], *, bold: bool = False,
                italic: bool = False, aside: bool = False) -> str:
        runs = []
        for node in nodes:
            if isinstance(node, (Text, Highlight)):
                highlight = isinstance(node, Highlight)
                props = ""
                if bold or highlight:
                    props += "<w:b/><w:bCs/>"
                elif aside:
                    props += '<w:b w:val="0"/><w:bCs w:val="0"/>'
                if italic:
                    props += "<w:i/><w:iCs/>"
                elif aside:
                    props += '<w:i w:val="0"/><w:iCs w:val="0"/>'
                if aside:
                    props += f'<w:color w:val="{LOOK.gray}"/>' + _size(LOOK.text_pt)
                if highlight:
                    props += '<w:u w:val="single"/>'
                runs.append(self._run(node.text, props))
            else:
                inner = self._inline(node.children, bold=bold or isinstance(node, Strong),
                                     italic=italic or isinstance(node, Emph), aside=aside)
                runs.append(self._link(node.url, inner) if isinstance(node, Link) else inner)
        return "".join(runs)

    def _text(self, text: str | None, *, aside: bool = False) -> str:
        return "" if text is None else self._inline(parse_inline(text, self.highlight), aside=aside)

    def _row(self, left: str | None, right: str | None, prefix: str = "") -> str:
        runs = prefix + self._text(left)
        if right is not None:
            runs += self._run("\t") + self._text(right, aside=True)
        return runs

    def _item(self, item: Item) -> list[str]:
        runs = self._row(item.text, item.date, self._run(LOOK.marker + "\t"))
        paragraphs = [_paragraph("ResumeItem", runs, keep_next=bool(item.details))]
        for index, detail in enumerate(item.details, start=1):
            paragraphs.append(_paragraph("ResumeDetail", self._text(detail),
                                         keep_next=index < len(item.details)))
        return paragraphs

    def paragraphs(self, doc: Document) -> list[str]:
        meta = doc.meta
        paragraphs = [_paragraph("ResumeName", self._run(header_name(meta)))]
        if meta.title is not None:
            paragraphs.append(_paragraph("ResumeTitle", self._run(meta.title)))
        if meta.contacts:
            contacts = []
            for kind, value in meta.contacts:
                url = contact_url(kind, value)
                runs = self._run(value)
                contacts.append(runs if url is None else self._link(url, runs))
            paragraphs.append(_paragraph("ResumeContacts", self._run(" · ").join(contacts)))

        for section in doc.sections:
            paragraphs.append(_paragraph("ResumeSection", self._text(section.title)))
            for child in section.children:
                if isinstance(child, Entry):
                    paragraphs.append(_paragraph("ResumeEntry", self._row(child.title, child.date)))
                    if child.subtitle is not None or child.side is not None:
                        paragraphs.append(_paragraph("ResumeSubtitle", self._row(child.subtitle, child.side)))
                    for item in child.items:
                        paragraphs.extend(self._item(item))
                elif isinstance(child, Item):
                    paragraphs.extend(self._item(child))
                elif isinstance(child, Paragraph):
                    paragraphs.append(_paragraph("ResumeParagraph", self._text(child.text)))
                else:  # The parser only builds the three kinds above.
                    raise TypeError(f"unexpected section child {child!r}")
        return paragraphs

    def relationships(self) -> str:
        parts = [
            f'<Relationship Id="rId1" Type="{_REL}/styles" Target="styles.xml"/>',
            f'<Relationship Id="rId2" Type="{_REL}/settings" Target="settings.xml"/>',
        ]
        for url, rel_id in self.links.items():
            parts.append(f'<Relationship Id="{rel_id}" Type="{_REL}/hyperlink" '
                         f'Target="{_xml(url)}" TargetMode="External"/>')
        return f'<Relationships xmlns="{_PKG}/relationships">{"".join(parts)}</Relationships>'


def _style(name: str, paragraph: str, run: str = "") -> str:
    run_properties = f"<w:rPr>{run}</w:rPr>" if run else ""
    return (f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/>'
            f'<w:basedOn w:val="Normal"/><w:pPr>{paragraph}</w:pPr>{run_properties}</w:style>')


def _styles(meta: Meta, lang: str, text_width: int) -> str:
    main = _xml(meta.fonts[0])
    east_asia = _xml(meta.fonts[1]) if len(meta.fonts) > 1 else main
    right_tab = f'<w:tab w:val="right" w:pos="{text_width}"/>'
    marker_width = round(LOOK.text_pt * 20)
    marker_tab = f'<w:tab w:val="left" w:pos="{marker_width}"/>'
    keep = "<w:keepNext/><w:keepLines/>"
    bold = "<w:b/><w:bCs/>"
    rule = 'w:val="single" w:sz="5" w:space="3" w:color="000000"'
    defaults = f"""<w:docDefaults>
  <w:rPrDefault><w:rPr>
    <w:rFonts w:ascii="{main}" w:hAnsi="{main}" w:eastAsia="{east_asia}" w:cs="{main}"/>
    <w:color w:val="000000"/>{_size(LOOK.text_pt)}
    <w:lang w:val="{lang}" w:eastAsia="ko-KR"/>
  </w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr>
    <w:wordWrap w:val="1"/><w:spacing w:after="0" w:line="220" w:lineRule="auto"/>
  </w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>"""
    styles = [
        _style("ResumeName", keep + '<w:spacing w:after="85"/>', bold + _size(LOOK.name_pt)),
        _style("ResumeTitle", keep + '<w:spacing w:after="95"/>', _size(LOOK.title_pt)),
        _style("ResumeContacts", keep + '<w:spacing w:after="70"/>'),
        _style("ResumeSection", keep + f'<w:pBdr><w:bottom {rule}/><w:between {rule}/></w:pBdr>'
               '<w:spacing w:before="170" w:after="85"/><w:outlineLvl w:val="0"/>',
               bold + "<w:caps/>" + _size(LOOK.section_pt)),
        _style("ResumeEntry", keep + f"<w:tabs>{right_tab}</w:tabs>"
               '<w:spacing w:before="75" w:after="22"/><w:outlineLvl w:val="1"/>',
               bold + _size(LOOK.entry_pt)),
        _style("ResumeSubtitle", keep + f"<w:tabs>{right_tab}</w:tabs>"
               '<w:spacing w:after="35"/>', "<w:i/><w:iCs/>"),
        _style("ResumeItem", f"<w:keepLines/><w:tabs>{marker_tab}{right_tab}</w:tabs>"
               f'<w:spacing w:before="20"/><w:ind w:left="{marker_width}" w:hanging="{marker_width}"/>'),
        _style("ResumeDetail", f'<w:keepLines/><w:ind w:left="{marker_width}"/>',
               _size(LOOK.text_pt * LOOK.detail_em)),
        _style("ResumeParagraph", '<w:spacing w:before="30" w:after="35"/>'),
    ]
    return f'<w:styles xmlns:w="{_WORD}">{defaults}{"".join(styles)}</w:styles>'


def emit_docx(doc: Document) -> bytes:
    """Return a complete, deterministic .docx ZIP package."""
    meta = doc.meta
    lang = "ko-KR" if meta.lang == "ko" else "en-US"
    width_mm, height_mm = paper_size_mm(meta.paper)
    width, height = round(width_mm * 1440 / 25.4), round(height_mm * 1440 / 25.4)
    margins = {side: round(inches * 1440) for side, inches in PAGE_MARGINS_IN.items()}
    text_width = width - margins["left"] - margins["right"]
    page_margins = " ".join(f'w:{side}="{margins[side]}"' for side in ("top", "right", "bottom", "left"))
    section = (f'<w:sectPr><w:pgSz w:w="{width}" w:h="{height}"/>'
               f'<w:pgMar {page_margins} w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')

    body = _Body(meta)
    paragraphs = "\n".join(body.paragraphs(doc))
    document = (f'<w:document xmlns:w="{_WORD}" xmlns:r="{_REL}">\n'
                f'<w:body>\n{paragraphs}\n{section}\n</w:body>\n</w:document>')
    settings = (f'<w:settings xmlns:w="{_WORD}"><w:autoHyphenation w:val="0"/>'
                f'<w:themeFontLang w:val="{lang}" w:eastAsia="ko-KR"/></w:settings>')
    name = _xml(meta.name)
    core = (f'<cp:coreProperties xmlns:cp="{_PKG}/metadata/core-properties" '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:title>{name}</dc:title><dc:creator>{name}</dc:creator></cp:coreProperties>')
    parts = (
        ("[Content_Types].xml", _CONTENT_TYPES),
        ("_rels/.rels", _PACKAGE_RELS),
        ("word/document.xml", document),
        ("word/styles.xml", _styles(meta, lang, text_width)),
        ("word/settings.xml", settings),
        ("word/_rels/document.xml.rels", body.relationships()),
        ("docProps/core.xml", core),
        ("docProps/app.xml", _APP_PROPERTIES),
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for path, xml in parts:
            entry = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 0
            archive.writestr(entry, (_XML_DECL + xml).encode("utf-8"), compress_type=ZIP_DEFLATED)
    return output.getvalue()
