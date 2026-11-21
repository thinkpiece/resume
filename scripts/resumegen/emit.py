"""Turn a filtered `Document` into a Typst file for template/resume.typ.

Text reaches Typst only as string literals (`#"..."`), combined with
`#strong[...]`, `#emph[...]`, `#link("...")[...]` and `#hl("...")`. Every
piece starts with `#` and pieces are written without whitespace between
them, so no resume text is ever read as Typst markup (spec §8).
"""

from __future__ import annotations

import re
import string

from .model import Document, Entry, Item, Paragraph, Section

TEMPLATE_IMPORT = '#import "/template/resume.typ": *'

_PUNCT = frozenset(string.punctuation)


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


def contact_url(kind: str, value: str) -> str | None:
    if kind == "email":
        return "mailto:" + value
    if kind == "phone":
        lead = "+" if value.strip().startswith("+") else ""
        return "tel:" + lead + re.sub(r"\D", "", value)
    if kind == "location":
        return None
    return value


# --------------------------------------------------------------------------
# Inline Markdown

def inline_to_typst(text: str, highlight: str | None = None) -> str:
    """Inline Markdown (spec §4.3) → a Typst content block `[...]`."""
    return "[" + "".join(_render(n, highlight) for n in _Inline(text).parse()) + "]"


def _render(node, highlight: str | None) -> str:
    kind = node[0]
    if kind == "text":
        return _text_run(node[1], highlight)
    inner = "".join(_render(n, highlight) for n in node[-1])
    if kind == "strong":
        return f"#strong[{inner}]"
    if kind == "emph":
        return f"#emph[{inner}]"
    return f"#link({typst_string(node[1])})[{inner}]"     # link


def _text_run(text: str, highlight: str | None) -> str:
    if not highlight or highlight not in text:
        return "#" + typst_string(text)
    out = []
    for i, part in enumerate(text.split(highlight)):
        if i:
            out.append(f"#hl({typst_string(highlight)})")
        if part:
            out.append("#" + typst_string(part))
    return "".join(out)


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


class _Inline:
    """Left-to-right tokenizer for **bold**, *italic*, _italic_, [text](url).

    Nodes: ("text", str), ("strong", [nodes]), ("emph", [nodes]),
    ("link", url, [nodes]). Unclosed or space-padded delimiters stay literal.
    """

    def __init__(self, text: str):
        self.t = text

    def parse(self, start: int = 0, end: int | None = None) -> list:
        t = self.t
        end = len(t) if end is None else end
        nodes: list = []
        buf: list[str] = []

        def flush():
            if buf:
                nodes.append(("text", "".join(buf)))
                buf.clear()

        i = start
        while i < end:
            c = t[i]
            if c == "\\":
                if i + 1 < end and t[i + 1] in _PUNCT:
                    buf.append(t[i + 1])
                    i += 2
                else:
                    buf.append(c)
                    i += 1
                continue
            if c == "[":
                link = self._link_at(i, end)
                if link:
                    label_end, url, after = link
                    flush()
                    nodes.append(("link", url, self.parse(i + 1, label_end)))
                    i = after
                    continue
            if c == "*" and self._opens(i, "**", end):
                close = self._close(i + 2, "**", end)
                if close is not None:
                    flush()
                    nodes.append(("strong", self.parse(i + 2, close)))
                    i = close + 2
                    continue
            if c in "*_" and self._opens(i, c, end):
                close = self._close(i + 1, c, end)
                if close is not None:
                    flush()
                    nodes.append(("emph", self.parse(i + 1, close)))
                    i = close + 1
                    continue
            buf.append(c)
            i += 1
        flush()
        return nodes

    # -- delimiters --------------------------------------------------------

    def _opens(self, i: int, delim: str, end: int) -> bool:
        t = self.t
        if t[i:i + len(delim)] != delim:
            return False
        nxt = i + len(delim)
        if nxt >= end or t[nxt].isspace() or t[nxt] == delim[0]:
            return False
        if delim == "_" and i > 0 and _is_word(t[i - 1]):
            return False
        if delim == "*" and i > 0 and t[i - 1] == "*":
            return False
        return True

    def _closes(self, j: int, delim: str, start: int, end: int) -> bool:
        t = self.t
        if j <= start or t[j:j + len(delim)] != delim or j + len(delim) > end:
            return False
        prev = t[j - 1]
        if prev.isspace() or prev == delim[0]:
            return False
        after = j + len(delim)
        if delim == "_" and after < end and _is_word(t[after]):
            return False
        if delim == "*" and after < end and t[after] == "*":
            return False
        return True

    def _close(self, start: int, delim: str, end: int) -> int | None:
        """Index of the closing `delim`, skipping escapes, links and nested strong."""
        t = self.t
        j = start
        while j < end:
            c = t[j]
            if c == "\\" and j + 1 < end and t[j + 1] in _PUNCT:
                j += 2
                continue
            if c == "[":
                link = self._link_at(j, end)
                if link:
                    j = link[2]
                    continue
            if self._closes(j, delim, start, end):
                return j
            if delim == "*" and self._opens(j, "**", end):
                inner = self._close(j + 2, "**", end)
                if inner is not None:
                    j = inner + 2
                    continue
            j += 1
        return None

    def _link_at(self, i: int, end: int) -> tuple[int, str, int] | None:
        """For "[label](url)" at i: (index of "]", url, index after ")")."""
        t = self.t
        j = i + 1
        while j < end:
            c = t[j]
            if c == "\\" and j + 1 < end and t[j + 1] in _PUNCT:
                j += 2
                continue
            if c == "[":
                return None
            if c == "]":
                break
            j += 1
        else:
            return None
        label_end = j
        if label_end + 1 >= end or t[label_end + 1] != "(":
            return None
        depth = 0
        k = label_end + 2
        while k < end:
            c = t[k]
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    url = t[label_end + 2:k].strip()
                    return (label_end, url, k + 1) if url else None
                depth -= 1
            k += 1
        return None


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
