"""Read publications.json (publications spec §4-§6).

- load_publications(): read, check and locate every item of the data file.
- select(): the items of one type, newest first.
- format_item(): one item as the two Markdown lines of the resume lists.

Every item remembers the line of its own "id" key (or of its opening "{" when
it has none), so errors point into the JSON file.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .errors import ResumeError, at
from .model import Line

SCHEMA_VERSION = 1
TYPES = ("journal", "conference")
REQUIRED_FIELDS = frozenset({"id", "type", "title", "authors", "venue", "year"})
KNOWN_FIELDS = REQUIRED_FIELDS | {"month", "month_end", "volume", "issue", "pages",
                                  "location", "doi", "url"}
_OPTIONAL_TEXT = ("volume", "issue", "pages", "location", "doi", "url")

_ID_RE = re.compile(r"[a-z0-9-]+")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WS_RE = re.compile(r"[ \t\n\r]*")
_DECODER = json.JSONDecoder()

MONTHS = ("Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.",
          "Oct.", "Nov.", "Dec.")
# Characters the resume Markdown dialect gives a meaning (spec §6).
_SPECIAL = frozenset("\\*_[]|{")


@dataclass(frozen=True)
class Venue:
    name: str
    short: str | None = None


@dataclass(frozen=True)
class Publication:
    id: str
    type: str
    title: str
    authors: tuple[str, ...]
    venue: Venue
    year: int
    month: int | None = None
    month_end: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    location: str | None = None
    doi: str | None = None
    url: str | None = None
    lineno: int = 1           # line of the item's "id" key, or of its "{"


@dataclass(frozen=True)
class Publications:
    path: Path
    owner: str
    items: tuple[Publication, ...]


class _Invalid(Exception):
    """A problem in one value; the caller adds the file, line and item."""


def load_publications(path: Path, include_line: Line | None = None) -> Publications:
    """Read and check the publications file at `path`.

    `include_line` is the Markdown line that includes the file; a missing file
    is reported there. Every other problem is reported in the JSON file.
    """
    text = _read(path, include_line)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ResumeError(f"{path}:{e.lineno}: invalid JSON: {e.msg}") from None

    def top_error(message: str) -> ResumeError:
        return ResumeError(f"{path}:1: {message}")

    if not isinstance(data, dict):
        raise top_error("the top level must be a JSON object")
    if "schema" not in data:
        raise top_error('missing "schema"')
    if not _is_int(data["schema"]) or data["schema"] != SCHEMA_VERSION:
        raise top_error(f"unsupported schema version {json.dumps(data['schema'])}; "
                        f"this build reads {SCHEMA_VERSION}")
    for key in ("owner", "publications"):
        if key not in data:
            raise top_error(f'missing "{key}"')
    try:
        owner = _text(data["owner"], "owner")
    except _Invalid as e:
        raise top_error(str(e)) from None
    if not isinstance(data["publications"], list):
        raise top_error('"publications" must be a list')

    lines = _item_lines(text)
    items: list[Publication] = []
    seen: set[str] = set()
    for index, (raw, lineno) in enumerate(zip(data["publications"], lines, strict=True)):
        label = f"publications[{index}]"
        try:
            if not isinstance(raw, dict):
                raise _Invalid("must be an object")
            if "id" not in raw:
                raise _Invalid('missing "id"')
            if not isinstance(raw["id"], str) or not _ID_RE.fullmatch(raw["id"]):
                raise _Invalid('"id" must match [a-z0-9-]+')
            label = raw["id"]
            if label in seen:
                raise _Invalid(f'duplicate id "{label}"')
            seen.add(label)
            items.append(_publication(raw, owner, lineno))
        except _Invalid as e:
            raise ResumeError(f"{path}:{lineno}: {label}: {e}") from None
    return Publications(path=path, owner=owner, items=tuple(items))


def _publication(raw: dict, owner: str, lineno: int) -> Publication:
    for key in ("type", "title", "authors", "venue", "year"):
        if key not in raw:
            raise _Invalid(f'missing "{key}"')
    if raw["type"] not in TYPES:
        raise _Invalid('"type" must be journal or conference')
    title = _text(raw["title"], "title")
    authors = _authors(raw["authors"])
    venue = _venue(raw["venue"])
    if not _is_int(raw["year"]):
        raise _Invalid('"year" must be an integer')
    month = raw.get("month")
    if "month" in raw and not (_is_int(month) and 1 <= month <= 12):
        raise _Invalid('"month" must be an integer 1-12')
    month_end = raw.get("month_end")
    if "month_end" in raw:
        if "month" not in raw:
            raise _Invalid('"month_end" needs "month"')
        if not (_is_int(month_end) and month < month_end <= 12):
            raise _Invalid('"month_end" must be after "month" and at most 12')
    optional = {key: _text(raw[key], key) for key in _OPTIONAL_TEXT if key in raw}
    if owner not in authors:
        raise _Invalid(f'owner "{owner}" is not among the authors')
    return Publication(id=raw["id"], type=raw["type"], title=title, authors=authors,
                       venue=venue, year=raw["year"], month=month,
                       month_end=month_end, lineno=lineno, **optional)


def _authors(value) -> tuple[str, ...]:
    bad = _Invalid('"authors" must be a non-empty list of names')
    if not isinstance(value, list) or not value:
        raise bad
    for name in value:
        if not isinstance(name, str) or not name.strip():
            raise bad
        _text(name, "authors")
    return tuple(value)


def _venue(value) -> Venue:
    if not isinstance(value, dict):
        raise _Invalid('"venue" must be an object')
    if "name" not in value:
        raise _Invalid('missing "venue.name"')
    name = _text(value["name"], "venue.name")
    short = _text(value["short"], "venue.short") if "short" in value else None
    return Venue(name, short)


def _text(value, name: str) -> str:
    """A one-line string field (clarification 11)."""
    if not isinstance(value, str):
        raise _Invalid(f'"{name}" must be a string')
    if not value.strip():
        raise _Invalid(f'"{name}" must not be empty')
    if _CONTROL_RE.search(value):
        raise _Invalid(f'"{name}" must be one line without control characters')
    if value != value.strip():
        raise _Invalid(f'"{name}" must not start or end with a space')
    return value


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# --------------------------------------------------------------------------
# Selecting and formatting

def select(pubs: Publications, type_: str, first_author: bool) -> list[Publication]:
    """The items of `type_`, newest first; with `first_author`, only those whose
    first author is the owner. Items without a month come last within their
    year; ties keep file order."""
    chosen = [p for p in pubs.items
              if p.type == type_ and (not first_author or p.authors[0] == pubs.owner)]
    return sorted(chosen, key=lambda p: (p.year, p.month or 0), reverse=True)


def format_item(pub: Publication, owner: str) -> tuple[str, str]:
    """The bullet line and the indented author line of one item (spec §6)."""
    parts = [escape(pub.title), _emphasis(escape(pub.venue.name))]
    for label, value in (("vol.", pub.volume), ("no.", pub.issue), ("pp.", pub.pages)):
        if value is not None:
            parts.append(label + escape(value))
    parts.append(_date(pub))
    names = [escape(a if a == owner else short_name(a)) for a in pub.authors]
    return "- " + ", ".join(parts) + ".", "  " + _join_names(names) + "."


def short_name(name: str) -> str:
    """Initials plus family name: "Hoi-Jun Yoo" -> "H.-J. Yoo".

    The family name is the last word. A one-word name, or one whose earlier
    words already end in ".", is returned unchanged.
    """
    words = name.split()
    if len(words) < 2 or any(w.endswith(".") for w in words[:-1]):
        return name
    return " ".join([_initials(w) for w in words[:-1]] + [words[-1]])


def escape(text: str) -> str:
    """Backslash every character the resume Markdown dialect would interpret."""
    return "".join("\\" + c if c in _SPECIAL else c for c in text)


def _initials(word: str) -> str:
    return "-".join(_first_letter(part) + "." if part else part
                    for part in word.split("-"))


def _first_letter(part: str) -> str:
    """The first character with any combining marks that follow it."""
    end = 1
    while end < len(part) and unicodedata.combining(part[end]):
        end += 1
    return part[:end]


def _emphasis(text: str) -> str:
    # The inline parser never closes "*" right after another "*", even an
    # escaped one, so a venue ending in "*" is wrapped in "_" instead.
    delim = "_" if text.endswith("*") else "*"
    return delim + text + delim


def _date(pub: Publication) -> str:
    if pub.month is None:
        return str(pub.year)
    month = MONTHS[pub.month - 1]
    if pub.month_end is not None:
        month += "-" + MONTHS[pub.month_end - 1]
    return f"{month} {pub.year}"


def _join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


# --------------------------------------------------------------------------
# Reading and locating

def _read(path: Path, include_line: Line | None) -> str:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        if include_line is None:
            raise ResumeError(f"{path}: file not found") from None
        raise at(include_line, f"included file not found: {path}") from None
    except OSError as e:
        where = f"{path}" if include_line is None else \
            f"{include_line.path}:{include_line.lineno}"
        raise ResumeError(f"{where}: cannot read {path}: {e.strerror}") from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        lineno = data.count(b"\n", 0, e.start) + 1
        raise ResumeError(f"{path}:{lineno}: invalid UTF-8 text") from None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _item_lines(text: str) -> list[int]:
    """The line of each item of the top-level "publications" array.

    An item's line is that of its own direct "id" key, or of its first
    character when it has none. `text` must be valid JSON holding an object.
    Like json.loads, the last of repeated keys wins.
    """
    lines: list[int] = []
    for key, _, value_at in _members(text, _WS_RE.match(text).end()):
        if key != "publications" or text[value_at] != "[":
            continue
        lines = []
        for start in _elements(text, value_at):
            where = start
            if text[start] == "{":
                for item_key, key_at, _ in _members(text, start):
                    if item_key == "id":
                        where = key_at
            lines.append(text.count("\n", 0, where) + 1)
    return lines


def _members(text: str, i: int):
    """Yield (key, key index, value index) for the JSON object at text[i]."""
    i = _WS_RE.match(text, i + 1).end()
    while text[i] != "}":
        key_at = i
        key, i = _DECODER.raw_decode(text, i)
        i = _WS_RE.match(text, _WS_RE.match(text, i).end() + 1).end()   # ":"
        yield key, key_at, i
        _, i = _DECODER.raw_decode(text, i)
        i = _WS_RE.match(text, i).end()
        if text[i] == ",":
            i = _WS_RE.match(text, i + 1).end()


def _elements(text: str, i: int):
    """Yield the index of each element of the JSON array at text[i]."""
    i = _WS_RE.match(text, i + 1).end()
    while text[i] != "]":
        yield i
        _, i = _DECODER.raw_decode(text, i)
        i = _WS_RE.match(text, i).end()
        if text[i] == ",":
            i = _WS_RE.match(text, i + 1).end()
