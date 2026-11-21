"""Format-neutral pieces shared by every writer (Typst, HTML, DOCX).

- parse_inline(): inline Markdown (spec §4.3) as a small tree of nodes, with
  the front-matter `highlight` name already split out of the text runs.
- contact_url(): the link target of a front-matter contact.
- header_name(), paper_size_mm(), PAGE_MARGINS_IN, LOOK: what
  template/resume.typ does to the page and the header, as plain data, so the
  HTML and DOCX writers can follow the PDF without reading Typst.

Nothing here knows about any output format.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Union

from .model import Meta

_PUNCT = frozenset(string.punctuation)


# --------------------------------------------------------------------------
# Inline nodes

@dataclass(frozen=True)
class Text:
    """Literal text; escapes are already resolved. Never empty."""
    text: str


@dataclass(frozen=True)
class Highlight:
    """One occurrence of the front-matter `highlight` name: bold and underlined."""
    text: str


@dataclass(frozen=True)
class Strong:
    children: tuple["Node", ...]


@dataclass(frozen=True)
class Emph:
    children: tuple["Node", ...]


@dataclass(frozen=True)
class Link:
    url: str                  # as written between the parentheses, stripped
    children: tuple["Node", ...]


Node = Union[Text, Highlight, Strong, Emph, Link]


def parse_inline(text: str, highlight: str | None = None) -> tuple[Node, ...]:
    """Inline Markdown → nodes.

    `**bold**` → Strong, `*italic*` / `_italic_` → Emph, `[label](url)` → Link.
    Unclosed or space-padded delimiters stay literal text. Every occurrence of
    `highlight` inside text, at any depth, becomes a Highlight node; a URL is
    never searched. Adjacent nodes are never both Text.
    """
    return _convert(_Inline(text).parse(), highlight)


def plain_text(nodes: tuple[Node, ...]) -> str:
    """The characters the nodes print, without any styling or URL."""
    out = []
    for node in nodes:
        if isinstance(node, (Text, Highlight)):
            out.append(node.text)
        else:
            out.append(plain_text(node.children))
    return "".join(out)


def _convert(raw: list, highlight: str | None) -> tuple[Node, ...]:
    out: list[Node] = []
    for node in raw:
        kind = node[0]
        if kind == "text":
            out.extend(_split_highlight(node[1], highlight))
        elif kind == "strong":
            out.append(Strong(_convert(node[1], highlight)))
        elif kind == "emph":
            out.append(Emph(_convert(node[1], highlight)))
        else:   # link
            out.append(Link(node[1], _convert(node[2], highlight)))
    return tuple(out)


def _split_highlight(text: str, highlight: str | None) -> list[Node]:
    if not highlight or highlight not in text:
        return [Text(text)]
    out: list[Node] = []
    for i, part in enumerate(text.split(highlight)):
        if i:
            out.append(Highlight(highlight))
        if part:
            out.append(Text(part))
    return out


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


class _Inline:
    """Left-to-right tokenizer for **bold**, *italic*, _italic_, [text](url).

    Raw nodes: ("text", str), ("strong", [nodes]), ("emph", [nodes]),
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
# Contacts and header

def contact_url(kind: str, value: str) -> str | None:
    """Link target of a contact: mailto:, tel: (digits only), the URL, or None."""
    if kind == "email":
        return "mailto:" + value
    if kind == "phone":
        lead = "+" if value.strip().startswith("+") else ""
        return "tel:" + lead + re.sub(r"\D", "", value)
    if kind == "location":
        return None
    return value


def header_name(meta: Meta) -> str:
    """The name as the header prints it: uppercase in English, as written otherwise."""
    return meta.name.upper() if meta.lang == "en" else meta.name


# --------------------------------------------------------------------------
# Page and look (mirrors template/resume.typ; the PDF never reads these)

# Width and height in millimetres of the Typst paper names the HTML and DOCX
# writers know: the ISO A, B and C series and the US/ANSI sizes. Typst accepts
# more names (parse.TYPST_PAPERS); those fall back to A4 outside the PDF.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a0": (841.0, 1189.0), "a1": (594.0, 841.0), "a2": (420.0, 594.0),
    "a3": (297.0, 420.0), "a4": (210.0, 297.0), "a5": (148.0, 210.0),
    "a6": (105.0, 148.0), "a7": (74.0, 105.0), "a8": (52.0, 74.0),
    "a9": (37.0, 52.0), "a10": (26.0, 37.0), "a11": (18.0, 26.0),
    "iso-b1": (707.0, 1000.0), "iso-b2": (500.0, 707.0), "iso-b3": (353.0, 500.0),
    "iso-b4": (250.0, 353.0), "iso-b5": (176.0, 250.0), "iso-b6": (125.0, 176.0),
    "iso-b7": (88.0, 125.0), "iso-b8": (62.0, 88.0),
    "iso-c3": (324.0, 458.0), "iso-c4": (229.0, 324.0), "iso-c5": (162.0, 229.0),
    "iso-c6": (114.0, 162.0), "iso-c7": (81.0, 114.0), "iso-c8": (57.0, 81.0),
    "us-letter": (215.9, 279.4), "us-legal": (215.9, 355.6),
    "us-tabloid": (279.4, 431.8), "us-ledger": (431.8, 279.4),
    "us-executive": (184.15, 266.7),
    "ansi-a": (215.9, 279.4), "ansi-b": (279.4, 431.8), "ansi-c": (431.8, 558.8),
    "ansi-d": (558.8, 863.6), "ansi-e": (863.6, 1117.6),
}
FALLBACK_PAPER = "a4"


def paper_size_mm(paper: str) -> tuple[float, float]:
    """(width, height) in mm of a front-matter `paper`; A4 for a name not in the table."""
    return PAPER_SIZES_MM.get(paper, PAPER_SIZES_MM[FALLBACK_PAPER])


PAGE_MARGINS_IN = {"top": 0.5, "right": 0.6, "bottom": 0.5, "left": 0.6}


@dataclass(frozen=True)
class Look:
    text_pt: float = 10.0          # body text
    detail_em: float = 0.92        # detail lines under a bullet, relative to body text
    name_pt: float = 20.0          # header name, bold
    title_pt: float = 11.5         # job title under the name
    section_pt: float = 11.5       # section title: bold, uppercase, rule below
    entry_pt: float = 11.0         # entry title: bold
    gray: str = "3C3C3C"           # dates and side text (Typst luma(60)); all else black
    marker: str = "·"         # bullet marker: middle dot


LOOK = Look()
