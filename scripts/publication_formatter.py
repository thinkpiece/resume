"""
Copyright (c) 2015 Junyoung Park

Publication Formatter from BibTeX files.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
from typing import Any, Dict, Iterable, List, Optional, Set

import bibtexparser

DEFAULT_HIGHLIGHT_NAME = os.environ.get("HIGHLIGHT_NAME", "Junyoung Park")
Publication = Dict[str, Any]


def _year_key(paper: Publication) -> int:
    try:
        return int(paper.get("year", 0))
    except (TypeError, ValueError):
        return 0


class PublicationFormatter:
    def __init__(
        self,
        publication_list: Iterable[Publication],
        highlight_name: str = DEFAULT_HIGHLIGHT_NAME,
    ):
        self.highlight_name = highlight_name
        normalized = [self._normalize_entry(entry) for entry in publication_list]
        self.conference_list = self._extract(normalized, {"inproceedings"})
        self.journal_list = self._extract(normalized, {"article"})

    def _extract(
        self, publication_list: List[Publication], allowed_types: Set[str]
    ) -> List[Publication]:
        filtered = [
            paper for paper in publication_list if paper.get("entrytype") in allowed_types
        ]
        return sorted(filtered, key=_year_key, reverse=True)

    def _normalize_entry(self, entry: Publication) -> Publication:
        normalized = dict(entry)
        entry_type = entry.get("ENTRYTYPE") or entry.get("type") or ""
        normalized["entrytype"] = entry_type.lower()

        authors = entry.get("author")
        if authors:
            normalized["author"] = ", ".join(
                self._refine_author_name(name.strip())
                for name in authors.split("and")
                if name.strip()
            )

        return normalized

    def _refine_author_name(self, name: str) -> str:
        """Emphasize my name and use initials for co-authors."""
        if not name:
            return name
        if name == self.highlight_name:
            return f"<u>{name}</u>"
        return re.sub(r"\b([A-Z])[A-Za-z]*([ -])", r"\1.\2", name)

    def _format_month_year(self, publication: Publication) -> str:
        month = publication.get("month", "")
        month = month.rstrip(". ")
        year = publication.get("year", "")
        if month and year:
            return f"{month}. {year}"
        return year or month

    def _render_html_item(self, publication: Publication) -> str:
        url = publication.get("bdsk-url-1") or publication.get("url")
        link_html = (
            f' <a href="{url}"><span class="glyphicon glyphicon-link"></span></a>'
            if url
            else ""
        )
        venue = publication.get("booktitle") or publication.get("journal") or "#empty#"
        schedule = self._format_month_year(publication)
        schedule = f", {schedule}" if schedule else ""
        authors = publication.get("author", "#empty#")

        return textwrap.dedent(
            f"""\
            <li>
              <dl>
                <dt>{publication.get("title", "#empty#")}</dt>
                <dd><em>{venue}</em>{schedule}{link_html}<br>
                  {authors}.
                </dd>
              </dl>
            </li>"""
        )

    def _export_publications(
        self, publications: Iterable[Publication], output
    ) -> None:
        for publication in publications:
            output.write(self._render_html_item(publication))
            output.write("\n")

    def export_conference(self, output) -> None:
        self._export_publications(self.conference_list, output)

    def export_journal(self, output) -> None:
        self._export_publications(self.journal_list, output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert BibTeX entries to an HTML list for the resume."
    )
    parser.add_argument("bibfile", help="Path to the BibTeX file.")
    parser.add_argument(
        "-o",
        "--output",
        default="html_output.html",
        help="Path to write the HTML output (default: %(default)s).",
    )
    parser.add_argument(
        "--highlight-name",
        default=DEFAULT_HIGHLIGHT_NAME,
        help="Author name to underline in the output.",
    )
    parser.add_argument(
        "--section",
        choices=["conference", "journal", "all"],
        default="conference",
        help="Which publication category to export.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.path.exists(args.bibfile):
        parser.error(f"BibTeX file {args.bibfile!r} was not found")

    with open(args.bibfile, encoding="utf-8") as bibtex_file:
        bibtex_database = bibtexparser.load(bibtex_file)

    formatter = PublicationFormatter(
        bibtex_database.entries, highlight_name=args.highlight_name
    )

    with open(args.output, "w", encoding="utf-8") as export_html_file:
        if args.section in ("conference", "all"):
            formatter.export_conference(export_html_file)
        if args.section in ("journal", "all"):
            formatter.export_journal(export_html_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
