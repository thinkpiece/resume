"""Data model shared by the loader, parser, variant filter and emitter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VARIANTS = frozenset({"full", "short"})


@dataclass(frozen=True)
class Line:
    text: str                 # no newline, no BOM, tabs expanded to 4 spaces
    path: Path                # file that physically holds the line
    lineno: int               # 1-based line number in that file
    scope: frozenset[str]     # variants allowed by enclosing @include markers


@dataclass
class Meta:
    name: str
    title: str | None
    lang: str                 # "en" | "ko"
    paper: str                # Typst paper name, e.g. "us-letter", "a4"
    fonts: list[str]
    highlight: str | None
    contacts: list[tuple[str, str]]   # (kind, value) in front-matter order


@dataclass
class Item:
    text: str
    date: str | None
    details: list[str]
    variants: frozenset[str]
    origin: Line


@dataclass
class Paragraph:
    text: str
    variants: frozenset[str]
    origin: Line


@dataclass
class Entry:
    title: str
    date: str | None
    subtitle: str | None
    side: str | None
    subtitle_variants: frozenset[str]
    items: list[Item]
    variants: frozenset[str]
    origin: Line


@dataclass
class Section:
    title: str
    children: list[Entry | Item | Paragraph]
    variants: frozenset[str]
    origin: Line


@dataclass
class Document:
    meta: Meta
    sections: list[Section]
    warnings: list[str]       # "<path>:<line>: <message>"
