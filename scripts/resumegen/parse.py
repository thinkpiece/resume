"""Parse the resume Markdown dialect (spec §4, §5) into a `Document`."""

from __future__ import annotations

import re
import string

from .errors import ResumeError, at
from .model import (VARIANTS, Document, Entry, Item, Line, Meta, Paragraph,
                    Section)
from .source import invalid_marker_message, trailing_marker

CONTACT_KEYS = ("location", "phone", "email", "homepage", "linkedin", "github")
FRONT_MATTER_KEYS = frozenset(
    ("name", "title", "lang", "paper", "font", "highlight") + CONTACT_KEYS)
LANGS = ("en", "ko")
# Paper names Typst 0.15 accepts for page(paper: ...), as listed in its error
# message for an unknown name.
TYPST_PAPERS = frozenset("""
a0 a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11
iso-b1 iso-b2 iso-b3 iso-b4 iso-b5 iso-b6 iso-b7 iso-b8
iso-c3 iso-c4 iso-c5 iso-c6 iso-c7 iso-c8
din-d3 din-d4 din-d5 din-d6 din-d7 din-d8 sis-g5 sis-e5
ansi-a ansi-b ansi-c ansi-d ansi-e arch-a arch-b arch-c arch-d arch-e1 arch-e
jis-b0 jis-b1 jis-b2 jis-b3 jis-b4 jis-b5 jis-b6 jis-b7 jis-b8 jis-b9 jis-b10 jis-b11
sac-d0 sac-d1 sac-d2 sac-d3 sac-d4 sac-d5 sac-d6 iso-id-1 iso-id-2 iso-id-3
asia-f4 jp-shiroku-ban-4 jp-shiroku-ban-5 jp-shiroku-ban-6 jp-kiku-4 jp-kiku-5
jp-business-card cn-business-card eu-business-card
fr-tellière fr-couronne-écriture fr-couronne-édition fr-raisin fr-carré fr-jésus
uk-brief uk-draft uk-foolscap uk-quarto uk-crown uk-book-a uk-book-b
us-letter us-legal us-tabloid us-executive us-foolscap-folio us-statement
us-ledger us-oficio us-gov-letter us-gov-legal us-business-card us-digest
us-trade newspaper-compact newspaper-berliner newspaper-broadsheet
presentation-16-9 presentation-4-3
""".split())

_HEADING_RE = re.compile(r"^(#+)(?:\s+(.*))?$")
_BULLET_RE = re.compile(r"^-(?:\s+(.*))?$")
_OTHER_BULLET_RE = re.compile(r"^[*+]\s")
_PUNCT = frozenset(string.punctuation)


def split_marker(text: str, line: Line) -> tuple[str, frozenset[str]]:
    """Remove a trailing {.full}/{.short} marker; return (text, own variants).

    `text` must already be stripped of trailing whitespace. An invalid marker
    attempt (clarification 11) raises ResumeError at `line`.
    """
    found = trailing_marker(text)
    if found is None:
        return text, VARIANTS
    start, variant = found
    if variant is None:
        raise at(line, invalid_marker_message(text[start:]))
    rest = text[:start].rstrip()
    again = trailing_marker(rest)
    if again is not None:
        raise at(line, "invalid variant marker: a line takes only one marker "
                       f"('{rest[again[0]:]}' and '{text[start:]}')")
    return rest, frozenset({variant})


def split_right(text: str) -> tuple[str, str | None]:
    """Split at the last unescaped " | "; unescape "\\|" in both parts."""
    cut = None
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in _PUNCT:
            i += 2
            continue
        if c == "|" and 0 < i < len(text) - 1 and text[i - 1] == " " and text[i + 1] == " ":
            cut = i
        i += 1
    if cut is None:
        return _unescape_pipes(text), None
    return _unescape_pipes(text[:cut].strip()), _unescape_pipes(text[cut + 1:].strip())


def _unescape_pipes(text: str) -> str:
    """Turn "\\|" into "|"; keep every other backslash escape for the emitter."""
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in _PUNCT:
            out.append("|" if text[i + 1] == "|" else text[i:i + 2])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse(lines: list[Line]) -> Document:
    if not lines:
        raise ResumeError("resume is empty; it must start with front matter")
    meta, body_start = _parse_front_matter(lines)
    parser = _BodyParser(lines)
    for line in lines[body_start:]:
        parser.feed(line)
    return Document(meta=meta, sections=parser.sections, warnings=parser.warnings)


# --------------------------------------------------------------------------
# Front matter

def _parse_front_matter(lines: list[Line]) -> tuple[Meta, int]:
    first = lines[0]
    if first.text.rstrip() != "---" or first.lineno != 1:
        raise at(first, "missing front matter; the root file must start with a '---' line")
    end = next((i for i in range(1, len(lines)) if lines[i].text.rstrip() == "---"), None)
    if end is None:
        raise at(first, "front matter is not closed; add a '---' line after it")

    values: dict[str, tuple[str, Line]] = {}
    contacts: list[tuple[str, str]] = []
    for line in lines[1:end]:
        if line.path != first.path:
            raise at(line, "front matter lines must come from the root file")
        raw = line.text.strip()
        if not raw or raw.startswith("#"):
            continue
        key, sep, value = raw.partition(":")
        key = key.strip()
        if not sep or not key:
            raise at(line, "expected 'key: value' in front matter")
        if key not in FRONT_MATTER_KEYS:
            raise at(line, f"unknown front matter key '{key}'; known keys: "
                           + ", ".join(sorted(FRONT_MATTER_KEYS)))
        if key in values:
            raise at(line, f"duplicate front matter key '{key}'")
        value = _strip_value(value)
        if not value:
            raise at(line, f"front matter key '{key}' has no value")
        values[key] = (value, line)
        if key in CONTACT_KEYS:
            contacts.append((key, value))

    if "name" not in values:
        raise at(first, "front matter must set 'name'")
    lang = values.get("lang", ("en", first))
    if lang[0] not in LANGS:
        raise at(lang[1], "lang must be 'en' or 'ko'")
    paper = values.get("paper", ("us-letter", first))
    if paper[0] not in TYPST_PAPERS:
        raise at(paper[1], f"unknown paper '{paper[0]}'; use a Typst paper name "
                           "such as us-letter or a4")
    font = values.get("font", ("Charter", first))
    fonts = [f.strip() for f in font[0].split(",") if f.strip()]
    if not fonts:
        raise at(font[1], "font needs at least one font name")

    meta = Meta(
        name=values["name"][0],
        title=values["title"][0] if "title" in values else None,
        lang=lang[0],
        paper=paper[0],
        fonts=fonts,
        highlight=values["highlight"][0] if "highlight" in values else None,
        contacts=contacts,
        origins={**{k: first for k in ("lang", "paper", "font")},
                 **{k: line for k, (_, line) in values.items()}},
    )
    return meta, end + 1


def _strip_value(value: str) -> str:
    """Remove a " # comment" and one pair of surrounding quotes."""
    m = re.search(r"\s#", value)
    if m:
        value = value[:m.start()]
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


# --------------------------------------------------------------------------
# Body

class _BodyParser:
    def __init__(self, lines: list[Line]):
        self.sections: list[Section] = []
        self.warnings: list[str] = []
        self.section: Section | None = None
        self.entry: Entry | None = None
        self.item: Item | None = None          # target for continuation lines
        self.subtitle_open = False             # next plain line is the subtitle
        # Lines with the same include scope in a row form one "run"; an
        # include-caused warning is given once per run (clarification 13).
        self._run_of: dict[int, int] = {}
        run = 0
        for i, line in enumerate(lines):
            if i and line.scope != lines[i - 1].scope:
                run += 1
            self._run_of[id(line)] = run
        self._warned_runs: set[int] = set()

    # -- helpers -----------------------------------------------------------

    def _effective(self, line: Line, own: frozenset[str],
                   parent: frozenset[str]) -> frozenset[str]:
        eff = own & line.scope & parent
        if not eff and parent:
            if line.scope & parent:
                self.warnings.append(
                    f"{line.path}:{line.lineno}: this line can never appear: its "
                    "variant marker conflicts with an enclosing marker")
            else:
                run = self._run_of.get(id(line))
                if run not in self._warned_runs:
                    self._warned_runs.add(run)
                    self.warnings.append(
                        f"{line.path}:{line.lineno}: this included content can never "
                        "appear: its include markers allow neither full nor short")
        return eff

    def _parent_variants(self) -> frozenset[str]:
        if self.entry is not None:
            return self.entry.variants
        return self.section.variants

    # -- dispatch ----------------------------------------------------------

    def feed(self, line: Line) -> None:
        text = line.text.rstrip()
        if not text.strip():
            return
        indent = len(text) - len(text.lstrip(" "))
        if indent >= 2:
            self._continuation(text.strip(), line)
            return
        text = text.lstrip(" ")
        if text == "---":
            raise at(line, "'---' is only allowed around the front matter at the "
                           "top of the root file")

        heading = _HEADING_RE.match(text)
        if heading:
            level = len(heading.group(1))
            body = (heading.group(2) or "").strip()
            if level == 2:
                self._section(body, line)
            elif level == 3:
                self._entry(body, line)
            else:
                raise at(line, "unsupported heading level; use '## ' for sections "
                               "and '### ' for entries")
            return

        bullet = _BULLET_RE.match(text)
        if bullet:
            self._bullet((bullet.group(1) or "").strip(), line)
            return
        if _OTHER_BULLET_RE.match(text):
            raise at(line, "use '- ' for bullets")
        self._plain(text, line)

    # -- line kinds --------------------------------------------------------

    def _section(self, body: str, line: Line) -> None:
        title, own = split_marker(body, line)
        if not title:
            raise at(line, "empty section title")
        self.section = Section(title=_unescape_pipes(title), children=[],
                               variants=self._effective(line, own, VARIANTS),
                               origin=line)
        self.sections.append(self.section)
        self.entry = None
        self.item = None
        self.subtitle_open = False

    def _entry(self, body: str, line: Line) -> None:
        if self.section is None:
            raise at(line, "entry before the first section; add a '## ' heading first")
        text, own = split_marker(body, line)
        title, date = split_right(text)
        if not title:
            raise at(line, "empty entry title")
        variants = self._effective(line, own, self.section.variants)
        self.entry = Entry(title=title, date=date, subtitle=None, side=None,
                           subtitle_variants=variants, items=[],
                           variants=variants, origin=line)
        self.section.children.append(self.entry)
        self.item = None
        self.subtitle_open = True

    def _bullet(self, body: str, line: Line) -> None:
        if self.section is None:
            raise at(line, "text before the first section; add a '## ' heading first")
        text, own = split_marker(body, line)
        text, date = split_right(text)
        if not text:
            raise at(line, "empty bullet")
        item = Item(text=text, date=date, details=[],
                    variants=self._effective(line, own, self._parent_variants()),
                    origin=line)
        if self.entry is not None:
            self.entry.items.append(item)
        else:
            self.section.children.append(item)
        self.item = item
        self.subtitle_open = False

    def _continuation(self, text: str, line: Line) -> None:
        if self.item is None or self.item.origin.path != line.path:
            raise at(line, "continuation line without a bullet")
        if trailing_marker(text) is not None:
            raise at(line, "markers are not allowed on continuation lines")
        self.item.details.append(_unescape_pipes(text))

    def _plain(self, text: str, line: Line) -> None:
        if self.section is None:
            raise at(line, "text before the first section; add a '## ' heading first")
        self.item = None
        if self.entry is not None and not self.subtitle_open:
            raise at(line, "unexpected text in entry; start it with '- '")
        text, own = split_marker(text, line)
        if not text:
            raise at(line, "marker without text")
        if self.entry is not None:
            subtitle, side = split_right(text)
            self.entry.subtitle = subtitle
            self.entry.side = side
            self.entry.subtitle_variants = self._effective(line, own, self.entry.variants)
            self.subtitle_open = False
            return
        self.section.children.append(Paragraph(
            text=_unescape_pipes(text),
            variants=self._effective(line, own, self.section.variants),
            origin=line))
