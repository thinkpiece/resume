Resume
======

A repository for my personal resume written in LaTeX, plus a small helper to
export publication entries from a BibTeX file to HTML.

## Prerequisites
- LuaLaTeX (recommended for `fontspec`)
- `bibtexparser` if you plan to run the publication formatter (`pip install bibtexparser`)

## Build the PDF
```
make pdf            # builds all top-level .tex files with lualatex
make ENGINE=xelatex # switch engine if needed
```

## Korean text
Use `\ko{...}` for Korean strings so they render with a Hangul-capable font.
```tex
\item 발표: \ko{산업전망컨퍼런스}
```

## Format publications from BibTeX
The helper prints an HTML `<li>` list you can embed in the resume site.
```
python scripts/publication_formatter.py path/to/publications.bib \
  --section conference --output html_output.html
```

Use `--section journal` or `--section all` to switch categories, and
`--highlight-name` to mark a different author.
