"""Tests for the HTML writer (scripts/resumegen/emit_html.py).

Every check parses the writer's own output with html.parser into a small
element tree, so structure, text and attributes are read the way a browser
reads them rather than by matching strings.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_resume.py"
FIXTURE = REPO / "tests" / "fixtures" / "cli" / "resume.md"

sys.path.insert(0, str(REPO / "scripts"))

from resumegen.emit_html import emit_html  # noqa: E402
from resumegen.model import Document, Entry, Item, Line, Meta, Paragraph, Section  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.render import (LOOK, PAGE_MARGINS_IN, Highlight, Link, Node,  # noqa: E402
                              contact_url, header_name, paper_size_mm, parse_inline,
                              plain_text)
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

SOURCES = {
    "fixture": FIXTURE,
    "en": REPO / "content" / "en" / "resume.md",
    "ko": REPO / "content" / "ko" / "resume.md",
}
VARIANT_NAMES = ("full", "short")


def load(name: str, variant: str) -> Document:
    return filter_variant(parse(load_lines(SOURCES[name])), variant)


def all_docs():
    for name in SOURCES:
        for variant in VARIANT_NAMES:
            yield name, variant, load(name, variant)


# --------------------------------------------------------------------------
# A tiny DOM built with html.parser

VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                  "meta", "source", "track", "wbr"})


class El:
    def __init__(self, tag: str, attrs: list, parent: "El | None"):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children: list = []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, El):
                yield from c.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list["El"]:
        return [e for e in self.iter()
                if e is not self and (tag is None or e.tag == tag)
                and (cls is None or cls in e.classes)]

    def find(self, tag: str | None = None, cls: str | None = None) -> "El":
        found = self.find_all(tag, cls)
        if not found:
            raise AssertionError(f"no <{tag or '*'} class={cls}> under <{self.tag}>")
        return found[0]

    def child_elements(self) -> list["El"]:
        return [c for c in self.children if isinstance(c, El)]

    def chunks(self) -> list[str]:
        out = []
        for c in self.children:
            out.extend(c.chunks() if isinstance(c, El) else [c])
        return out

    def text(self) -> str:
        return "".join(self.chunks())

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("#document", [], None)
        self.stack = [self.root]
        self.decls: list[str] = []
        self.comments: list[str] = []
        self.order: list[str] = []      # "decl", "data:<x>", "<tag>" in source order

    def handle_decl(self, decl):
        self.decls.append(decl)
        self.order.append("decl")

    def handle_starttag(self, tag, attrs):
        self.order.append(f"<{tag}>")
        el = El(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.order.append(f"<{tag}>")
        self.stack[-1].children.append(El(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        if tag in VOID:
            raise AssertionError(f"end tag for void element </{tag}>")
        top = self.stack.pop()
        if top.tag != tag:
            raise AssertionError(f"</{tag}> closes <{top.tag}>")

    def handle_data(self, data):
        if data.strip():
            self.order.append("data")
        self.stack[-1].children.append(data)

    def handle_comment(self, data):
        self.comments.append(data)

    def handle_pi(self, data):
        raise AssertionError(f"processing instruction: {data!r}")

    def unknown_decl(self, data):
        raise AssertionError(f"unknown declaration: {data!r}")


class Page:
    """Parsed HTML output with shortcuts to the parts the tests look at."""

    def __init__(self, source: str):
        b = _TreeBuilder()
        b.feed(source)
        b.close()
        if b.stack != [b.root]:
            raise AssertionError("unclosed elements: " + ", ".join(e.tag for e in b.stack[1:]))
        self.source = source
        self.builder = b
        self.root = b.root
        tops = b.root.child_elements()
        if [e.tag for e in tops] != ["html"]:
            raise AssertionError(f"top-level elements: {[e.tag for e in tops]}")
        self.html = tops[0]
        heads = [e.tag for e in self.html.child_elements()]
        if heads != ["head", "body"]:
            raise AssertionError(f"<html> children: {heads}")
        self.head, self.body = self.html.child_elements()

    @property
    def css(self) -> str:
        return "".join(s.text() for s in self.root.find_all("style"))

    def visible(self) -> str:
        return self.body.text()


def css_rules(css: str) -> list[tuple[str, list[str], str]]:
    """(media, selectors, declarations) of every rule; media is "" at top level."""
    out = []

    def block(text, media):
        i = 0
        while True:
            start = text.find("{", i)
            if start < 0:
                return
            prelude = text[i:start].strip()
            depth, j = 1, start + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            inner = text[start + 1:j - 1]
            if prelude.startswith("@media"):
                block(inner, prelude)
            else:
                out.append((media, [s.strip() for s in prelude.split(",")], inner))
            i = j

    block(css, "")
    return out


def css_rule(css: str, selector: str, media: str = "") -> str:
    """Declarations of every rule (under `media`) whose selector list holds `selector`."""
    found = [decls for m, selectors, decls in css_rules(css)
             if m == media and selector in selectors]
    if not found:
        raise AssertionError(f"no CSS rule for {selector!r} in {media or 'top level'}")
    return "\n".join(found)


def squash(text: str) -> str:
    return " ".join(text.split())


# --------------------------------------------------------------------------
# What the Document says should be printed, in the order emit.py walks it

def body_pieces(doc: Document) -> list[tuple[str, str]]:
    """(kind, plain text) for every printed body piece, in document order."""
    hl = doc.meta.highlight

    def p(text):
        return plain_text(parse_inline(text, hl))

    def item(it: Item, out):
        out.append(("marker", LOOK.marker))
        out.append(("item", p(it.text)))
        if it.date is not None:
            out.append(("date", p(it.date)))
        out.extend(("detail", p(d)) for d in it.details)

    out: list[tuple[str, str]] = []
    for section in doc.sections:
        out.append(("section", p(section.title)))
        for child in section.children:
            if isinstance(child, Entry):
                out.append(("entry", p(child.title)))
                if child.date is not None:
                    out.append(("date", p(child.date)))
                if child.subtitle is not None:
                    out.append(("subtitle", p(child.subtitle)))
                if child.side is not None:
                    out.append(("side", p(child.side)))
                for it in child.items:
                    item(it, out)
            elif isinstance(child, Item):
                item(child, out)
            else:
                out.append(("paragraph", p(child.text)))
    return out


def header_pieces(doc: Document) -> list[tuple[str, str]]:
    meta = doc.meta
    out = [("name", header_name(meta))]
    if meta.title is not None:
        out.append(("title", meta.title))
    out.extend(("contact", value) for _, value in meta.contacts)
    return out


def body_fields(doc: Document) -> list[str]:
    """Every body text field as written, in document order."""
    out: list[str] = []
    for section in doc.sections:
        out.append(section.title)
        for child in section.children:
            if isinstance(child, Entry):
                out += [f for f in (child.title, child.date, child.subtitle, child.side)
                        if f is not None]
                items = child.items
            elif isinstance(child, Item):
                items = [child]
            else:
                out.append(child.text)
                items = []
            for it in items:
                out += [it.text] + ([it.date] if it.date is not None else []) + it.details
    return out


def walk_nodes(nodes: tuple[Node, ...]):
    for n in nodes:
        yield n
        if hasattr(n, "children"):
            yield from walk_nodes(n.children)


# --------------------------------------------------------------------------
# Hand-built documents

LINE = Line(text="", path=Path("t.md"), lineno=1, scope=frozenset({"full", "short"}))
BOTH = frozenset({"full", "short"})


def make_meta(**kw) -> Meta:
    base = dict(name="Test Person", title=None, lang="en", paper="a4", fonts=["Charter"],
                highlight=None, contacts=[])
    base.update(kw)
    return Meta(**base)


def make_item(text, date=None, details=()):
    return Item(text=text, date=date, details=list(details), variants=BOTH, origin=LINE)


def make_entry(title, date=None, subtitle=None, side=None, items=()):
    return Entry(title=title, date=date, subtitle=subtitle, side=side, subtitle_variants=BOTH,
                 items=list(items), variants=BOTH, origin=LINE)


def make_section(title, children=()):
    return Section(title=title, children=list(children), variants=BOTH, origin=LINE)


def make_doc(sections=(), **meta) -> Document:
    return Document(meta=make_meta(**meta), sections=list(sections), warnings=[])


# --------------------------------------------------------------------------
# Content: every piece, in order, nothing added or dropped

class ContentOrderTest(unittest.TestCase):
    def test_every_piece_in_document_order(self):
        for name, variant, doc in all_docs():
            with self.subTest(source=name, variant=variant):
                page = Page(emit_html(doc))
                visible = squash(page.visible())
                pos = 0
                for kind, piece in header_pieces(doc) + body_pieces(doc):
                    want = squash(piece)
                    at = visible.find(want, pos)
                    self.assertGreaterEqual(at, 0, f"{kind} {want!r} missing after "
                                                   f"{visible[max(0, pos - 60):pos]!r}")
                    pos = at + len(want)

    def test_nothing_added_nothing_dropped(self):
        # Without whitespace, the visible text is exactly the pieces joined in order.
        for name, variant, doc in all_docs():
            with self.subTest(source=name, variant=variant):
                page = Page(emit_html(doc))
                want = "".join(p for _, p in header_pieces(doc) + body_pieces(doc))
                self.assertEqual("".join(page.visible().split()), "".join(want.split()))

    def test_structure_follows_the_document(self):
        for name, variant, doc in all_docs():
            with self.subTest(source=name, variant=variant):
                page = Page(emit_html(doc))
                hl = doc.meta.highlight

                def p(text):
                    return squash(plain_text(parse_inline(text, hl)))

                sections = page.body.find_all("section")
                self.assertEqual(len(sections), len(doc.sections))
                for el, section in zip(sections, doc.sections):
                    self.assertEqual(squash(el.find("h2").text()), p(section.title))
                    entries = [c for c in section.children if isinstance(c, Entry)]
                    heads = el.find_all("h3")
                    self.assertEqual([squash(h.text()) for h in heads],
                                     [p(e.title) for e in entries])
                    items = [c for c in section.children if isinstance(c, Item)]
                    for e in entries:
                        items += e.items
                    lis = el.find_all("li", "item")
                    self.assertEqual(len(lis), len(items))
                    paragraphs = [c for c in section.children if isinstance(c, Paragraph)]
                    self.assertEqual([squash(x.text()) for x in el.find_all("p", "paragraph")],
                                     [p(x.text) for x in paragraphs])

    def test_items_are_list_elements(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        lis = page.body.find_all("li", "item")
        self.assertTrue(lis)
        for li in lis:
            self.assertEqual(li.parent.tag, "ul")
            self.assertEqual(li.find(cls="marker").text(), LOOK.marker)
            self.assertEqual(li.find(cls="marker").attrs.get("aria-hidden"), "true")

    def test_dates_and_sides_are_gray_and_right_aligned(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        asides = [squash(e.text()) for e in page.body.find_all(cls="aside")]
        want = [p for kind, p in body_pieces(doc) if kind in ("date", "side")]
        self.assertEqual(asides, want)
        rule = css_rule(page.css, ".aside")
        self.assertIn(f"color: #{LOOK.gray}", rule)
        self.assertIn("text-align: right", rule)
        self.assertIn("margin-left: auto", rule)

    def test_details_each_on_own_line_and_smaller(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        details = page.body.find_all("p", "detail")
        want = [p for kind, p in body_pieces(doc) if kind == "detail"]
        self.assertEqual([squash(d.text()) for d in details], want)
        self.assertEqual(len(want), 3)   # "A. Kim, ...", "presented at ISSCC", "Test Person."
        self.assertIn(f"font-size: {LOOK.detail_em:g}em", css_rule(page.css, ".detail"))

    def test_entry_subtitle_and_side(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        entry = page.body.find_all("div", "entry")[0]
        self.assertEqual(entry.find("h3").text(), "Example, Inc.")
        self.assertEqual(entry.find(cls="subtitle").text(), "Founder and CEO")
        heads = entry.find(cls="entry-head").find_all(cls="aside")
        self.assertEqual([h.text() for h in heads], ["Aug. 2015 - Present", "Seoul"])
        self.assertIn("font-style: italic", css_rule(page.css, ".subtitle"))
        old_lab = page.body.find_all("div", "entry")[1]
        self.assertEqual(old_lab.find_all(cls="subtitle"), [])
        self.assertEqual(len(old_lab.find(cls="entry-head").find_all(cls="row")), 1)

    def test_side_without_subtitle_gets_second_line(self):
        doc = make_doc([make_section("S", [make_entry("E", side="Seoul")])])
        page = Page(emit_html(doc))
        rows = page.body.find(cls="entry-head").find_all(cls="row")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].find(cls="aside").text(), "Seoul")
        self.assertEqual(rows[1].find_all(cls="subtitle"), [])

    def test_empty_section_and_entry_keep_their_headings(self):
        doc = make_doc([make_section("Empty"),
                        make_section("Has entry", [make_entry("Lonely", date="2020")])])
        page = Page(emit_html(doc))
        self.assertEqual([h.text() for h in page.body.find_all("h2")], ["Empty", "Has entry"])
        self.assertEqual([h.text() for h in page.body.find_all("h3")], ["Lonely"])
        self.assertEqual(page.body.find_all("ul", "items"), [])
        self.assertEqual(page.body.find_all("section")[0].child_elements()[0].tag, "h2")

    def test_items_and_paragraphs_keep_mixed_order(self):
        doc = make_doc([make_section("S", [
            make_item("one"), make_item("two"), Paragraph("para", BOTH, LINE),
            make_item("three"), make_entry("E", items=[make_item("four")]),
            make_item("five"),
        ])])
        page = Page(emit_html(doc))
        section = page.body.find("section")
        kinds = []
        for el in section.child_elements():
            if el.tag == "ul":
                kinds.append([li.find(cls="text").text() for li in el.find_all("li")])
            else:
                kinds.append(el.tag + ":" + "".join(el.text().split()))
        self.assertEqual(kinds, ["h2:S", ["one", "two"], "p:para", ["three"],
                                 "div:E·four", ["five"]])


# --------------------------------------------------------------------------
# Header

class HeaderTest(unittest.TestCase):
    def test_uppercase_name_in_english_only(self):
        en = Page(emit_html(load("fixture", "full")))
        self.assertEqual(en.body.find("h1").text(), "TEST PERSON")
        ko_doc = load("ko", "full")
        ko = Page(emit_html(ko_doc))
        self.assertNotEqual(ko_doc.meta.name, ko_doc.meta.name.upper())
        self.assertEqual(ko.body.find("h1").text(), ko_doc.meta.name)
        hangul = Page(emit_html(make_doc(name="박준영 (Junyoung Park)", lang="ko")))
        self.assertEqual(hangul.body.find("h1").text(), "박준영 (Junyoung Park)")
        self.assertNotIn("text-transform", css_rule(ko.css, ".name"))

    def test_title_and_contacts(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        header = page.body.find("header")
        self.assertEqual(header.find("p", "title").text(), "Chip Designer & Founder")
        lis = header.find("ul", "contacts").find_all("li")
        self.assertEqual([li.text() for li in lis], [v for _, v in doc.meta.contacts])
        for li, (kind, value) in zip(lis, doc.meta.contacts):
            links = li.find_all("a")
            url = contact_url(kind, value)
            if url is None:
                self.assertEqual(links, [], kind)
            else:
                self.assertEqual([a.attrs["href"] for a in links], [url], kind)
        hrefs = [a.attrs["href"] for a in header.find_all("a")]
        self.assertIn("tel:+821000000000", hrefs)
        self.assertIn("mailto:test_person@example.com", hrefs)

    def test_no_title_no_contacts(self):
        page = Page(emit_html(make_doc([make_section("S")])))
        header = page.body.find("header")
        self.assertEqual([e.tag for e in header.child_elements()], ["h1"])

    def test_front_matter_is_literal(self):   # clarification 2
        doc = make_doc(name="A *b* [c](d)", title="**t** Test",
                       contacts=[("location", "_x_ Test")], highlight="Test")
        page = Page(emit_html(doc))
        header = page.body.find("header")
        self.assertEqual(header.find("h1").text(), "A *B* [C](D)")
        self.assertEqual(header.find("p", "title").text(), "**t** Test")
        self.assertEqual(header.find("ul", "contacts").find("li").text(), "_x_ Test")
        for tag in ("strong", "em", "a", "u"):
            self.assertEqual(header.find_all(tag), [], tag)


# --------------------------------------------------------------------------
# Inline Markdown, escaping, highlight, links

class InlineTest(unittest.TestCase):
    def test_special_characters_print_as_typed(self):
        page = Page(emit_html(load("fixture", "full")))
        self.assertIn('Builds low-power chips; R&D 100% #1 $5 @x <y> ~z "q" \\ μW.',
                      page.visible())
        self.assertIn("R&amp;D", page.source)
        self.assertIn("&lt;y&gt;", page.source)
        self.assertIn("&quot;q&quot;", page.source)
        self.assertNotIn("<y>", page.source)
        self.assertIn("Award with escaped | pipe", page.visible())
        self.assertIn("snake_case_words", page.visible())

    def test_bold_and_italic(self):
        doc = make_doc([make_section("S", [Paragraph("**B** and *i* and _u_ *a **n** c*",
                                                     BOTH, LINE)])])
        page = Page(emit_html(doc))
        para = page.body.find("p", "paragraph")
        self.assertEqual([e.text() for e in para.find_all("strong")], ["B", "n"])
        self.assertEqual([e.text() for e in para.find_all("em")], ["i", "u", "a n c"])
        self.assertEqual(para.find_all("em")[2].find("strong").text(), "n")
        page = Page(emit_html(load("fixture", "full")))
        ems = [e.text() for e in page.body.find_all("em")]
        self.assertIn("low-power", ems)
        self.assertIn("IEEE JSSC", ems)
        self.assertIn("snake_case", ems)

    def test_highlight_is_bold_and_underlined(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        want = sum(isinstance(n, Highlight)
                   for f in body_fields(doc)
                   for n in walk_nodes(parse_inline(f, doc.meta.highlight)))
        self.assertEqual(want, 2)
        hls = page.body.find_all(cls="hl")
        self.assertEqual(len(hls), want)
        for el in hls:
            self.assertEqual(el.tag, "strong")
            self.assertEqual([c.tag for c in el.child_elements()], ["u"])
            self.assertEqual(el.text(), "Test Person")
        # The name in the header is front matter: never highlighted.
        self.assertEqual(page.body.find("header").find_all(cls="hl"), [])

    def test_highlight_inside_link_and_emphasis(self):
        doc = make_doc([make_section("S", [make_item("*by Test* [Test](https://t.est/Test)")])],
                       highlight="Test")
        page = Page(emit_html(doc))
        li = page.body.find("li", "item")
        self.assertEqual(li.find("em").find("strong", "hl").text(), "Test")
        a = li.find("a")
        self.assertEqual(a.attrs["href"], "https://t.est/Test")
        self.assertEqual(a.find("strong", "hl").text(), "Test")

    def test_body_links(self):
        doc = load("fixture", "full")
        page = Page(emit_html(doc))
        want = [(n.url, plain_text(n.children))
                for f in body_fields(doc)
                for n in walk_nodes(parse_inline(f, doc.meta.highlight))
                if isinstance(n, Link)]
        self.assertEqual(want, [("https://isscc.org/a_b", "ISSCC")])
        got = [(a.attrs["href"], a.text()) for a in page.body.find_all("a")
               if not any(p.tag == "header" for p in a.ancestors())]
        self.assertEqual(got, want)

    def test_links_look_like_text(self):
        css = Page(emit_html(load("fixture", "full"))).css
        rule = css_rule(css, "a")
        self.assertIn("color: inherit", rule)
        self.assertIn("text-decoration: none", rule)

    def test_hostile_text_is_never_markup(self):
        nasty = '<script>alert(1)</script> & "q" \'s\' ]]> <!-- c --> </style> &amp;'
        url = 'https://e.com/?a=1&b="2"><script>'
        doc = make_doc(
            [make_section(nasty, [
                make_entry(nasty, date=nasty, subtitle=nasty, side=nasty, items=[
                    make_item(f"{nasty} [a <b> & \"c\"]({url})", date=nasty,
                              details=[nasty])]),
                Paragraph(nasty, BOTH, LINE)])],
            name=nasty, title=nasty, lang="en",
            fonts=['Evil"</style><script>x()</script>', "a\\b\nc", "url(x)"],
            contacts=[("homepage", url), ("email", nasty), ("location", nasty)])
        source = emit_html(doc)
        page = Page(source)
        self.assertNotIn("<script", source.lower())
        self.assertNotIn("<!-- c", source)
        self.assertEqual(page.builder.comments, [])
        allowed = {"html", "head", "meta", "title", "style", "body", "article", "header",
                   "h1", "p", "ul", "li", "a", "section", "h2", "div", "h3", "span",
                   "strong", "em", "u"}
        self.assertLessEqual({e.tag for e in page.root.iter() if e is not page.root}, allowed)
        self.assertEqual(page.head.find("title").text(), nasty)
        self.assertEqual(page.head.find("meta", None).attrs.get("charset"), "utf-8")
        hrefs = [a.attrs["href"] for a in page.body.find_all("a")]
        self.assertEqual(hrefs, [url, "mailto:" + nasty, url])
        want = "".join(p for _, p in header_pieces(doc) + body_pieces(doc))
        self.assertEqual("".join(page.visible().split()), "".join(want.split()))
        self.assertEqual(len(page.root.find_all("style")), 1)
        self.assertNotIn("</", page.css)
        self.assertNotIn("<", page.css)
        self.assertNotIn("url(", page.css.lower())
        self.assertIn("\\3C ", page.css)
        # The CSS strings decode back to the font names.
        self.assertEqual(font_family(page.css)[:3], doc.meta.fonts)


def _css_unescape(s: str) -> str:
    return re.sub(r"\\([0-9A-Fa-f]{1,6}) ?|\\(.)",
                  lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), s)


def font_family(css: str) -> list[str]:
    """The body font-family as a list: decoded quoted names, then the generic family."""
    rule = css_rule(css, "body")
    m = re.search(r"font-family: ((?:\"(?:[^\"\\]|\\.)*\", )*)([a-z-]+);", rule)
    if not m:
        raise AssertionError(f"no font-family in {rule!r}")
    names = re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1))
    return [_css_unescape(n) for n in names] + [m.group(2)]


# --------------------------------------------------------------------------
# Format rules: self-contained page, look, page size, fonts, language

class FormatTest(unittest.TestCase):
    def test_self_contained(self):
        for name, variant, doc in all_docs():
            with self.subTest(source=name, variant=variant):
                source = emit_html(doc)
                page = Page(source)
                self.assertTrue(source.startswith("<!DOCTYPE html>\n"))
                self.assertEqual(page.builder.decls, ["DOCTYPE html"])
                self.assertEqual(page.html.attrs.get("lang"), doc.meta.lang)
                metas = page.head.find_all("meta")
                self.assertIn({"charset": "utf-8"}, [m.attrs for m in metas])
                self.assertEqual(metas[0].attrs, {"charset": "utf-8"})
                viewport = [m.attrs.get("content") for m in metas
                            if m.attrs.get("name") == "viewport"]
                self.assertEqual(viewport, ["width=device-width, initial-scale=1"])
                self.assertEqual([t.text() for t in page.root.find_all("title")],
                                 [doc.meta.name])
                styles = page.root.find_all("style")
                self.assertEqual(len(styles), 1)
                self.assertIs(styles[0].parent, page.head)
                for tag in ("script", "link", "img", "iframe", "object", "embed", "source",
                            "video", "audio", "picture", "svg", "base", "form", "input",
                            "noscript", "template", "frame"):
                    self.assertEqual(page.root.find_all(tag), [], tag)
                for el in page.root.iter():
                    for attr in el.attrs:
                        self.assertNotIn(attr, ("src", "srcset", "style", "background",
                                                "poster", "data", "action"), el.tag)
                        self.assertFalse(attr.startswith("on"), (el.tag, attr))
                    if el.tag != "a":
                        self.assertNotIn("href", el.attrs, el.tag)
                css = page.css.lower()
                self.assertNotIn("@import", css)
                self.assertNotIn("url(", css)
                self.assertNotIn("@font-face", css)
                self.assertEqual(page.builder.comments, [])

    def test_semantic_layout(self):
        page = Page(emit_html(load("en", "full")))
        resume = page.body.child_elements()
        self.assertEqual([e.tag for e in resume], ["article"])
        tops = [e.tag for e in resume[0].child_elements()]
        self.assertEqual(tops[0], "header")
        self.assertEqual(set(tops[1:]), {"section"})
        self.assertEqual(len(page.body.find_all("h1")), 1)
        for section in page.body.find_all("section"):
            self.assertEqual(section.child_elements()[0].tag, "h2")
            self.assertEqual(len(section.find_all("h2")), 1)

    def test_look(self):
        css = Page(emit_html(load("en", "full"))).css
        self.assertIn(f"font-size: {LOOK.text_pt:g}pt", css_rule(css, "html"))
        body = css_rule(css, "body")
        self.assertIn("color: #000", body)
        self.assertIn("background: #fff", body)
        self.assertIn("font-synthesis: none", body)   # upright Hangul, as in the PDF
        name = css_rule(css, ".name")
        self.assertIn(f"font-size: {LOOK.name_pt:g}pt", name)
        self.assertIn("font-weight: bold", name)
        self.assertIn(f"font-size: {LOOK.title_pt:g}pt", css_rule(css, ".title"))
        h2 = css_rule(css, "h2")
        self.assertIn(f"font-size: {LOOK.section_pt:g}pt", h2)
        self.assertIn("font-weight: bold", h2)
        self.assertIn("text-transform: uppercase", h2)
        self.assertRegex(h2, r"border-bottom: [\d.]+pt solid #000")
        h3 = css_rule(css, "h3")
        self.assertIn(f"font-size: {LOOK.entry_pt:g}pt", h3)
        self.assertIn("font-weight: bold", h3)
        hl = css_rule(css, ".hl u")
        self.assertIn("text-decoration: underline", hl)
        # The only colors are black, white and the gray of dates and side text.
        colors = set(c.lower() for c in re.findall(r"#[0-9A-Fa-f]{3,6}\b", css))
        self.assertEqual(colors, {"#000", "#fff", "#" + LOOK.gray.lower()})

    def test_section_title_stays_as_written(self):
        page = Page(emit_html(load("fixture", "full")))
        titles = [h.text() for h in page.body.find_all("h2")]
        self.assertIn("Work Experience", titles)
        self.assertNotIn("WORK EXPERIENCE", titles)

    def test_page_size_and_margins(self):
        for doc, paper in ((load("fixture", "full"), "us-letter"), (make_doc(paper="a4"), "a4")):
            with self.subTest(paper=paper):
                self.assertEqual(doc.meta.paper, paper)
                css = Page(emit_html(doc)).css
                w, h = paper_size_mm(paper)
                m = PAGE_MARGINS_IN
                margin = f"{m['top']:g}in {m['right']:g}in {m['bottom']:g}in {m['left']:g}in"
                page_rule = css_rule(css, "@page")
                self.assertIn(f"size: {w:g}mm {h:g}mm", page_rule)
                self.assertIn(f"margin: {margin}", page_rule)
                column = css_rule(css, ".page")
                self.assertIn(f"max-width: {w:g}mm", column)
                self.assertIn(f"padding: {margin}", column)
                self.assertIn("margin: 0 auto", column)
        self.assertEqual(paper_size_mm("a4"), (210.0, 297.0))

    def test_fonts_in_order_then_generic(self):
        fixture = Page(emit_html(load("fixture", "full"))).css
        self.assertEqual(font_family(fixture), ["Charter", "NanumMyeongjo", "serif"])
        self.assertIn('font-family: "Charter", "NanumMyeongjo", serif;', fixture)
        sans = Page(emit_html(make_doc(fonts=["Pretendard"], lang="ko"))).css
        self.assertEqual(font_family(sans), ["Pretendard", "sans-serif"])
        for name in ("en", "ko"):
            doc = load(name, "full")
            self.assertEqual(font_family(Page(emit_html(doc)).css)[:-1], doc.meta.fonts)
        odd = Page(emit_html(make_doc(fonts=["Noto Sans KR", "Font-Name_1.0"]))).css
        self.assertEqual(font_family(odd), ["Noto Sans KR", "Font-Name_1.0", "sans-serif"])
        self.assertIn('"Noto Sans KR", "Font-Name_1.0"', odd)

    def test_css_escapes_in_font_names(self):   # clarification 4
        css = Page(emit_html(make_doc(fonts=['a"b\\c<d\ne']))).css
        self.assertIn('"a\\22 b\\5C c\\3C d\\A e"', css)

    def test_korean_breaks_only_at_spaces(self):
        for name in ("ko", "en"):
            with self.subTest(source=name):
                body = css_rule(Page(emit_html(load(name, "full"))).css, "body")
                self.assertIn("word-break: keep-all", body)

    def test_language(self):
        self.assertEqual(Page(emit_html(load("ko", "short"))).html.attrs["lang"], "ko")
        self.assertEqual(Page(emit_html(load("en", "short"))).html.attrs["lang"], "en")

    def test_title_and_author_metadata(self):
        doc = make_doc(name="박준영 (Junyoung Park)", lang="ko")
        page = Page(emit_html(doc))
        self.assertEqual(page.head.find("title").text(), "박준영 (Junyoung Park)")
        authors = [m.attrs["content"] for m in page.head.find_all("meta")
                   if m.attrs.get("name") == "author"]
        self.assertEqual(authors, [doc.meta.name])

    def test_print_rules(self):
        css = Page(emit_html(load("en", "full"))).css
        self.assertIn("padding: 0", css_rule(css, ".page", "@media print"))
        self.assertIn("break-inside: avoid", css_rule(css, ".item"))
        self.assertIn("break-after: avoid", css_rule(css, "h2"))
        self.assertIn("break-after: avoid", css_rule(css, ".entry-head"))

    def test_deterministic(self):
        for name, variant, doc in all_docs():
            with self.subTest(source=name, variant=variant):
                first = emit_html(doc)
                self.assertEqual(emit_html(doc), first)
                self.assertEqual(emit_html(load(name, variant)), first)

    def test_does_not_modify_the_document(self):
        doc = load("fixture", "full")
        before = repr(doc)
        emit_html(doc)
        self.assertEqual(repr(doc), before)


# --------------------------------------------------------------------------
# CLI

class CliHtmlTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, src, *args):
        env = dict(os.environ, RESUME_ROOT=str(self.root), PATH="/nonexistent")
        return subprocess.run([sys.executable, str(SCRIPT), str(src), *args],
                              capture_output=True, text=True, env=env, cwd=self.root)

    def test_builds_html_without_typst(self):
        for name in ("fixture", "ko"):
            for variant in VARIANT_NAMES:
                with self.subTest(source=name, variant=variant):
                    out = self.root / "out" / f"{name}_{variant}.html"
                    r = self.run_cli(SOURCES[name], "--variant", variant, "-o", out)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(r.stderr, "")
                    self.assertTrue(out.exists())
                    self.assertEqual(out.read_bytes(),
                                     emit_html(load(name, variant)).encode("utf-8"))
        self.assertFalse((self.root / "build").exists())   # no .typ for HTML

    def test_uppercase_extension(self):
        out = self.root / "X.HTML"
        r = self.run_cli(FIXTURE, "--variant", "short", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))

    def test_parse_error_removes_stale_html(self):
        src = self.root / "bad.md"
        src.write_text("---\nname: N\n---\n## S\n- x {.ful}\n", encoding="utf-8")
        out = self.root / "out" / "stale.html"
        out.parent.mkdir()
        out.write_text("<p>old</p>", encoding="utf-8")
        r = self.run_cli(src, "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("invalid variant marker", r.stderr)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
