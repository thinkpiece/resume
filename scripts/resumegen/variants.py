"""Select the full or short variant of a parsed resume (spec §5)."""

from __future__ import annotations

import copy

from .model import VARIANTS, Document, Entry, Item, Paragraph, Section


def filter_variant(doc: Document, variant: str) -> Document:
    """Return a new Document holding only what `variant` shows.

    An entry or section is dropped when filtering removed everything under it;
    one that was already empty in the source is kept. `doc` is not modified.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected one of {sorted(VARIANTS)}")
    sections = []
    for section in doc.sections:
        kept = _section(section, variant)
        if kept is not None:
            sections.append(kept)
    return Document(meta=copy.deepcopy(doc.meta), sections=sections,
                    warnings=list(doc.warnings))


def _section(section: Section, variant: str) -> Section | None:
    if variant not in section.variants:
        return None
    children: list[Entry | Item | Paragraph] = []
    for child in section.children:
        if variant not in child.variants:
            continue
        if isinstance(child, Entry):
            entry = _entry(child, variant)
            if entry is not None:
                children.append(entry)
        else:
            children.append(copy.deepcopy(child))
    if section.children and not children:
        return None
    return Section(title=section.title, children=children,
                   variants=section.variants, origin=section.origin)


def _entry(entry: Entry, variant: str) -> Entry | None:
    items = [copy.deepcopy(i) for i in entry.items if variant in i.variants]
    has_subtitle = entry.subtitle is not None and variant in entry.subtitle_variants
    had_content = entry.subtitle is not None or entry.items
    if had_content and not items and not has_subtitle:
        return None
    return Entry(title=entry.title, date=entry.date,
                 subtitle=entry.subtitle if has_subtitle else None,
                 side=entry.side if has_subtitle else None,
                 subtitle_variants=entry.subtitle_variants,
                 items=items, variants=entry.variants, origin=entry.origin)
