"""Turn a filtered `Document` into one self-contained HTML file.

The page carries the PDF's content in the PDF's order (header, then each
section: title, children; entry: title, date, subtitle, side, items; item:
marker, text, date, details) and mirrors template/resume.typ through
render.LOOK and render.PAGE_MARGINS_IN: one centered paper-width column on
screen, the PDF's paper size and margins in print.

No source text is ever read as markup: every piece of text and every
attribute value goes through html.escape(quote=True), and the only source
text inside <style> is font names, written by css_string() with every
character other than a letter, digit, space, "-", "_" or "." as a CSS escape.
The file has one inline <style> and nothing else that loads: no scripts, no
links to stylesheets or fonts, no images.
"""

from __future__ import annotations

from html import escape
from itertools import groupby

from .model import Document, Entry, Item, Meta, Paragraph, Section
from .render import (LOOK, PAGE_MARGINS_IN, Emph, Highlight, Node, Strong, Text, contact_url,
                     header_name, paper_size_mm, parse_inline)


def _esc(text: str) -> str:
    return escape(text, quote=True)


def _num(x: float) -> str:
    """A CSS number without float noise or trailing zeros: 0.35, 215.9, 10."""
    return f"{round(x, 4):g}"


# --------------------------------------------------------------------------
# Inline Markdown

def inline_html(text: str, highlight: str | None = None, italic: bool = False) -> str:
    """Inline Markdown (spec §4.3) → escaped HTML phrasing content.

    `italic` is the style of the line the text sits on (an entry subtitle is
    italic); see nodes_html().
    """
    return nodes_html(parse_inline(text, highlight), italic)


def nodes_html(nodes: tuple[Node, ...], italic: bool = False) -> str:
    """Inline nodes → escaped HTML, on a line that is `italic` or upright.

    Emphasis flips the current style, as Typst's emph does (clarification 7):
    an <em> in upright text is italic, and one in italic text gets class
    "upright". Every <em> thus states its own style, so any depth of nesting
    follows (italic of the line) XOR (odd number of Emph ancestors). Strong
    does not toggle: bold inside bold stays bold.
    """
    return "".join(_node(n, italic) for n in nodes)


def _node(node: Node, italic: bool) -> str:
    if isinstance(node, Text):
        return _esc(node.text)
    if isinstance(node, Highlight):
        return f'<strong class="hl"><u>{_esc(node.text)}</u></strong>'
    if isinstance(node, Emph):
        cls = ' class="upright"' if italic else ""
        return f"<em{cls}>{nodes_html(node.children, not italic)}</em>"
    inner = nodes_html(node.children, italic)
    if isinstance(node, Strong):
        return f"<strong>{inner}</strong>"
    return f'<a href="{_esc(node.url)}">{inner}</a>'     # Link


# --------------------------------------------------------------------------
# CSS

_CSS_PLAIN = frozenset(" -_.")

# The generic family is used only when none of the fonts is installed: sans
# for a main font that looks like one (Pretendard, Noto Sans KR, ...), serif
# otherwise (the template's default font, Charter, is a serif).
_SANS_HINTS = ("sans", "gothic", "고딕", "pretendard", "helvetica", "arial")


def css_string(text: str) -> str:
    """A double-quoted CSS string holding `text` exactly.

    Letters, digits, space, "-", "_" and "." are written as they are; any
    other character becomes a hex escape ended by a space (`"` → `\\22 `,
    `\\` → `\\5C `, `<` → `\\3C `, newline → `\\A `), so the string can never
    end early or close the <style> element.
    """
    out = ['"']
    for c in text:
        out.append(c if c.isalnum() or c in _CSS_PLAIN else f"\\{ord(c):X} ")
    out.append('"')
    return "".join(out)


def font_family(fonts: list[str]) -> str:
    """CSS font-family value: every font quoted, in order, then a generic family."""
    main = fonts[0].lower() if fonts else ""
    generic = "sans-serif" if any(h in main for h in _SANS_HINTS) else "serif"
    return ", ".join([css_string(f) for f in fonts] + [generic])


# Vertical rhythm of template/resume.typ. Typst measures a gap from the
# baseline of one line to the top edge (0.7em above the baseline) of the
# next, so between two lines of a paragraph the gap is the leading. CSS line
# boxes already leave that much between consecutive lines, so a Typst gap g
# becomes a CSS margin of g - leading. Lengths are in rem: the root font size
# is the body size, so 1rem is Typst's 1em of body text.
_TOP_EDGE = 0.7
_LEADING = {"en": 0.5, "ko": 0.7}     # Hangul is taller and denser
# Under the section rule Typst leaves 0.65em to the next line's top edge,
# where a CSS line box already starts about 0.42em lower (measured in Chrome
# with Charter and Pretendard), so the CSS margin is the rest.
_RULE_TO_TEXT = 0.23


def _rule(selector: str, decls: list[str], indent: str = "") -> list[str]:
    return ([f"{indent}{selector} {{"] + [f"{indent}  {d};" for d in decls]
            + [f"{indent}}}"])


def _css(meta: Meta) -> str:
    width, height = paper_size_mm(meta.paper)
    m = PAGE_MARGINS_IN
    margins = " ".join(f"{_num(m[side])}in" for side in ("top", "right", "bottom", "left"))
    leading = _LEADING.get(meta.lang, _LEADING["en"])
    line_height = _num(_TOP_EDGE + leading)
    gray = "#" + LOOK.gray

    def gap(typst_em: float) -> str:
        return f"{_num(max(typst_em - leading, 0))}rem"

    def pt(size: float) -> str:
        return f"{_num(size)}pt"

    item_gap = gap(leading + 0.1)        # bullets sit slightly further apart than lines
    rules = [
        ("@page", [f"size: {_num(width)}mm {_num(height)}mm", f"margin: {margins}"]),
        ("html", ["color-scheme: light", f"font-size: {pt(LOOK.text_pt)}",
                  "-webkit-text-size-adjust: 100%", "text-size-adjust: 100%"]),
        ("body", ["margin: 0", "background: #fff", "color: #000",
                  f"font-family: {font_family(meta.fonts)}", f"line-height: {line_height}",
                  "word-break: keep-all", "overflow-wrap: break-word",
                  # Like Typst, never fake bold or italic: a font without an
                  # italic (Pretendard, Hangul fallbacks) prints upright.
                  "font-synthesis: none"]),
        ("h1, h2, h3, p, ul", ["margin: 0", "padding: 0", "font: inherit"]),
        ("ul", ["list-style: none"]),
        ("strong", ["font-weight: bold"]),
        ("em", ["font-style: italic"]),
        ("em.upright", ["font-style: normal"]),     # emphasis inside italic text
        ("a", ["color: inherit", "text-decoration: none"]),
        (".hl u", ["text-decoration: underline", "text-underline-offset: 0.18em",
                   "text-decoration-thickness: 0.045em"]),
        (".page", ["box-sizing: border-box", f"max-width: {_num(width)}mm",
                   "margin: 0 auto", f"padding: {margins}"]),
        # Header: name, job title, one wrapping line of contacts.
        (".resume-header", [f"margin-bottom: {gap(1.15)}"]),
        (".name", [f"font-size: {pt(LOOK.name_pt)}", "font-weight: bold",
                   "letter-spacing: 0.03em", "line-height: 1"]),
        (".title", [f"font-size: {pt(LOOK.title_pt)}", f"margin-top: {gap(0.75)}"]),
        # Typst leaves 0.95em above the contacts, measured to their icons; the
        # HTML has no icons, so its text starts about 0.1em higher.
        (".contacts", ["display: flex", "flex-wrap: wrap", "column-gap: 1.6rem",
                       f"margin-top: {gap(0.85)}"]),
        # Section: bold uppercase title over a thin rule.
        ("section", [f"margin-top: {gap(1.35)}"]),
        ("h2", [f"font-size: {pt(LOOK.section_pt)}", "font-weight: bold",
                "text-transform: uppercase", "letter-spacing: 0.04em", "line-height: 1.2",
                "padding-bottom: 0.1rem", "border-bottom: 0.6pt solid #000",
                f"margin-bottom: {_num(_RULE_TO_TEXT)}rem",
                "break-after: avoid"]),
        # As in Typst, the gap under the rule replaces the first child's own.
        ("h2 + .entry, h2 + .paragraph", ["margin-top: 0"]),
        # Left text with a right-aligned date or side text, which keeps its own
        # column and shares the baseline of the left text's last line.
        (".row", ["display: flex", "align-items: flex-end", "align-items: last baseline",
                  "column-gap: 1.5rem"]),
        (".row > h3, .row > .subtitle, .row > .text", ["flex: 1 1 0", "min-width: 0"]),
        (".aside", ["flex: 0 1 auto", "margin-left: auto", "text-align: right",
                    f"color: {gray}"]),
        # Entry: bold title and date; optional italic subtitle with upright side text.
        (".entry", [f"margin-top: {gap(0.85)}"]),
        (".entry-head", ["break-inside: avoid", "break-after: avoid"]),
        # A bold 11pt title sits about 0.125rem higher in its CSS line box than
        # Typst sets it; move it down without changing the pitch of the lines.
        (".entry-head > .row:first-child", ["padding-top: 0.125rem",
                                            "margin-bottom: -0.125rem"]),
        ("h3", [f"font-size: {pt(LOOK.entry_pt)}", "font-weight: bold", "line-height: 1.2"]),
        (".subtitle", ["font-style: italic"]),
        # Bullet item: centered marker column; detail lines slightly smaller.
        (".item", ["display: grid", "grid-template-columns: 1rem minmax(0, 1fr)",
                   f"margin-top: {item_gap}", "break-inside: avoid"]),
        (".marker", ["text-align: center"]),
        (".detail", [f"font-size: {_num(LOOK.detail_em)}em"]),
        (".row + .detail", ["margin-top: 0.1rem"]),     # Typst: one leading at body size
        (".paragraph", [f"margin-top: {item_gap}"]),
    ]
    out: list[str] = []
    for selector, decls in rules:
        out += _rule(selector, decls)
    out.append("@media screen and (max-width: 40em) {")
    out += _rule(".page", ["padding: 1.5rem 1rem"], "  ")
    out.append("}")
    out.append("@media print {")
    out += _rule(".page", ["max-width: none", "padding: 0"], "  ")
    out.append("}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Document

class _Lines:
    """Output lines, indented by element depth."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.depth = 0

    def add(self, text: str) -> None:
        self.lines.append("  " * self.depth + text)

    def open(self, text: str) -> None:
        self.add(text)
        self.depth += 1

    def close(self, text: str) -> None:
        self.depth -= 1
        self.add(text)


def emit_html(doc: Document) -> str:
    """The whole HTML file, as text (the caller encodes it as UTF-8)."""
    meta = doc.meta
    out = _Lines()
    for line in ("<!DOCTYPE html>",
                 f'<html lang="{_esc(meta.lang)}">',
                 "<head>",
                 '<meta charset="utf-8">',
                 '<meta name="viewport" content="width=device-width, initial-scale=1">',
                 f'<meta name="author" content="{_esc(meta.name)}">',
                 f"<title>{_esc(meta.name)}</title>",
                 "<style>",
                 _css(meta),
                 "</style>",
                 "</head>",
                 "<body>"):
        out.add(line)
    out.open('<article class="page">')
    _header(meta, out)
    for section in doc.sections:
        _section(section, meta.highlight, out)
    out.close("</article>")
    out.add("</body>")
    out.add("</html>")
    return "\n".join(out.lines) + "\n"


def _header(meta: Meta, out: _Lines) -> None:
    """Name, job title and contacts: front matter, printed as written (no Markdown)."""
    out.open('<header class="resume-header">')
    out.add(f'<h1 class="name">{_esc(header_name(meta))}</h1>')
    if meta.title is not None:
        out.add(f'<p class="title">{_esc(meta.title)}</p>')
    if meta.contacts:
        out.open('<ul class="contacts">')
        for kind, value in meta.contacts:
            url = contact_url(kind, value)
            text = _esc(value) if url is None else f'<a href="{_esc(url)}">{_esc(value)}</a>'
            out.add(f"<li>{text}</li>")
        out.close("</ul>")
    out.close("</header>")


def _section(section: Section, hl: str | None, out: _Lines) -> None:
    out.open("<section>")
    out.add(f"<h2>{inline_html(section.title, hl)}</h2>")
    # Bullets directly under the section: each run of them is one list.
    for is_item, run in groupby(section.children, key=lambda c: isinstance(c, Item)):
        if is_item:
            _items(list(run), hl, out)
            continue
        for child in run:
            if isinstance(child, Entry):
                _entry(child, hl, out)
            elif isinstance(child, Paragraph):
                out.add(f'<p class="paragraph">{inline_html(child.text, hl)}</p>')
            else:   # pragma: no cover - the parser only builds the three kinds
                raise TypeError(f"unexpected section child {child!r}")
    out.close("</section>")


def _row(main: str, right: str | None, hl: str | None) -> str:
    """Left content, then the right-aligned gray date or side text if there is one."""
    aside = "" if right is None else f'<span class="aside">{inline_html(right, hl)}</span>'
    return f'<div class="row">{main}{aside}</div>'


def _entry(entry: Entry, hl: str | None, out: _Lines) -> None:
    out.open('<div class="entry">')
    out.open('<div class="entry-head">')
    out.add(_row(f"<h3>{inline_html(entry.title, hl)}</h3>", entry.date, hl))
    if entry.subtitle is not None or entry.side is not None:
        sub = ("" if entry.subtitle is None
               else f'<p class="subtitle">{inline_html(entry.subtitle, hl, italic=True)}</p>')
        out.add(_row(sub, entry.side, hl))
    out.close("</div>")
    _items(entry.items, hl, out)
    out.close("</div>")


def _items(items: list[Item], hl: str | None, out: _Lines) -> None:
    if not items:
        return
    out.open('<ul class="items">')
    for item in items:
        out.open('<li class="item">')
        out.add(f'<span class="marker" aria-hidden="true">{_esc(LOOK.marker)}</span>')
        out.open('<div class="item-body">')
        out.add(_row(f'<span class="text">{inline_html(item.text, hl)}</span>', item.date, hl))
        for detail in item.details:
            out.add(f'<p class="detail">{inline_html(detail, hl)}</p>')
        out.close("</div>")
        out.close("</li>")
    out.close("</ul>")
