"""Turn a filtered `Document` into a Typst file for template/resume.typ.

Text reaches Typst only as string literals (`#"..."`), combined with
`#strong[...]`, `#emph[...]`, `#link("...")[...]` and `#hl("...")`. Every
piece starts with `#` and pieces are written without whitespace between
them, so no resume text is ever read as Typst markup (spec §8).
"""

from __future__ import annotations

from .model import Document, Entry, Item, Paragraph, Section
from .render import Emph, Highlight, Node, Strong, Text, contact_url, parse_inline

TEMPLATE_IMPORT = '#import "/template/resume.typ": *'


# --------------------------------------------------------------------------
# Typst values

def typst_string(text: str) -> str:
    """A Typst string literal holding `text` exactly."""
    out = ['"']
    for c in text:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 0x20 or ord(c) == 0x7F:
            out.append(f"\\u{{{ord(c):x}}}")
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def _array(values: list[str]) -> str:
    if not values:
        return "()"
    if len(values) == 1:
        return f"({values[0]},)"
    return "(" + ", ".join(values) + ")"


# --------------------------------------------------------------------------
# Inline Markdown

def inline_to_typst(text: str, highlight: str | None = None) -> str:
    """Inline Markdown (spec §4.3) → a Typst content block `[...]`."""
    return "[" + "".join(_render(n) for n in parse_inline(text, highlight)) + "]"


def _render(node: Node) -> str:
    if isinstance(node, Text):
        return "#" + typst_string(node.text)
    if isinstance(node, Highlight):
        return f"#hl({typst_string(node.text)})"
    inner = "".join(_render(n) for n in node.children)
    if isinstance(node, Strong):
        return f"#strong[{inner}]"
    if isinstance(node, Emph):
        return f"#emph[{inner}]"
    return f"#link({typst_string(node.url)})[{inner}]"     # Link


# --------------------------------------------------------------------------
# Document

def emit_typst(doc: Document) -> str:
    meta = doc.meta
    hl = meta.highlight

    def content(text: str | None) -> str:
        return "none" if text is None else inline_to_typst(text, hl)

    out = [TEMPLATE_IMPORT, "#show: resume.with("]
    out.append(f"  name: {typst_string(meta.name)},")
    out.append(f"  title: {'none' if meta.title is None else typst_string(meta.title)},")
    out.append(f"  lang: {typst_string(meta.lang)},")
    out.append(f"  paper: {typst_string(meta.paper)},")
    out.append(f"  fonts: {_array([typst_string(f) for f in meta.fonts])},")
    if meta.contacts:
        out.append("  contacts: (")
        for kind, value in meta.contacts:
            url = contact_url(kind, value)
            out.append(f"    (kind: {typst_string(kind)}, text: {typst_string(value)}, "
                       f"url: {'none' if url is None else typst_string(url)}),")
        out.append("  ),")
    else:
        out.append("  contacts: (),")
    out.append(")")

    for section in doc.sections:
        _emit_section(section, out, content)
    return "\n".join(out) + "\n"


def _emit_section(section: Section, out: list[str], content) -> None:
    out.append(f"#section({content(section.title)})[")
    for child in section.children:
        if isinstance(child, Entry):
            out.append(f"  #entry(title: {content(child.title)}, date: {content(child.date)}, "
                       f"subtitle: {content(child.subtitle)}, side: {content(child.side)})[")
            for item in child.items:
                out.append("    " + _item(item, content))
            out.append("  ]")
        elif isinstance(child, Item):
            out.append("  " + _item(child, content))
        elif isinstance(child, Paragraph):
            out.append(f"  #paragraph({content(child.text)})")
        else:   # pragma: no cover - the parser only builds the three kinds
            raise TypeError(f"unexpected section child {child!r}")
    out.append("]")


def _item(item: Item, content) -> str:
    args = [content(item.text)]
    if item.date is not None:
        args.append(f"date: {content(item.date)}")
    if item.details:
        args.append(f"details: {_array([content(d) for d in item.details])}")
    return f"#item({', '.join(args)})"
