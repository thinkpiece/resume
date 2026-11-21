Resume
======

My resume, written as Markdown and rendered to PDF with [Typst](https://typst.app).
One Markdown file per language produces two variants: **full** (the long,
multi-page resume) and **short** (a one-page summary).

```
content/en/resume.md ─┐                        build/Resume_JunyoungPark_en_full.pdf
content/ko/resume.md ─┼─ scripts/build_resume.py ─ template/resume.typ ─ typst ─▶ …_en_short.pdf
content/shared/*.md  ─┘        (Python)              (layout)                   …_ko_full.pdf / …_ko_short.pdf
```

Content edits only ever touch `content/`. Layout lives only in `template/resume.typ`.

## Prerequisites

- Typst 0.15 or later: `brew install typst`
- Python 3.10 or later (standard library only, nothing to `pip install`)
- Optional: poppler (`brew install poppler`) for `pdfinfo` / `pdftotext` checks

## Build

```
make            # all four PDFs in build/
make en-full    # or en-short, ko-full, ko-short
make test       # unit tests
make clean      # remove build/
```

The PDFs always rebuild (Typst takes well under a second). Output:
`build/Resume_JunyoungPark_{en,ko}_{full,short}.pdf`, next to the generated
`.typ` files. `build/` is git-ignored; no PDF is committed.

One PDF by hand:

```
python3 scripts/build_resume.py content/en/resume.md --variant short -o build/en_short.pdf
python3 scripts/build_resume.py content/en/resume.md --variant full --typ-only   # write the .typ only
```

The build fails with `<file>:<line>: <message>` on any malformed line, on a
`paper` name Typst does not know, and on a `font` that Typst cannot find; the
last two point at their front-matter line. A failed build leaves no PDF at
the output path. A short variant longer than one page still builds, with a
warning that gives the page count.

## Folder layout

```
content/
  en/resume.md            English resume (root file)
  ko/resume.md            Korean resume (root file)
  shared/journals.md      journal papers      (bullets only, included by both)
  shared/conferences.md   conference papers   (bullets only)
  shared/talks.md         invited talks       (bullets only)
  shared/patents.md       patents             (bullets only)
template/
  resume.typ              Typst layout
  icons/                  Font Awesome Free contact icons and their license
scripts/
  build_resume.py         the build command
  resumegen/              loader, parser, variant filter, Typst emitter
  publication_formatter.py  BibTeX → HTML helper (see below)
tests/                    unit tests (python3 -m unittest discover -s tests)
build/                    generated .typ and .pdf files (git-ignored)
```

## Writing the Markdown

### Front matter

Every root file starts with flat `key: value` lines between `---` lines.
` #` starts a comment. Included files must not have front matter.

<!-- example: front-matter -->
```markdown
---
name: Junyoung Park
title: AI System-on-Chip Startup Founder & Director & Engineer
lang: en                        # en | ko
paper: us-letter                # Typst paper name: us-letter | a4
font: Charter, NanumMyeongjo    # first font, then fallbacks
highlight: Junyoung Park        # bold + underline this name everywhere
location: Seongnam-si 13105, Gyeonggi-do, Republic of Korea
phone: +82-10-2542-5500
email: junyoung@uxf.ai
homepage: http://www.junyoungpark.com
linkedin: https://www.linkedin.com/in/parkjunyoung
github: https://github.com/example
---
```

`name` is required. Defaults: `lang: en`, `paper: us-letter`, `font: Charter`.
The contact keys (`location`, `phone`, `email`, `homepage`, `linkedin`,
`github`) print with an icon in the order written; email, phone and URLs
become links. Any other key is an error.

### Body

<!-- example: body -->
```markdown
## Work Experience

### UX Factory, Inc. | Aug. 2015 - Present
Co-founder and Chief Executive Officer | Seoul
- Founded a company that delivers AI solutions
- Gave a keynote | Dec. 2025

## Journal Papers
- A 54 μW Chip, *IEEE JSSC*, 2014.
  S. Park, Junyoung Park, H.-J. Yoo.
  - presented and demonstrated at ISSCC

## Summary
A plain line directly under a section is a paragraph.

<!-- comments are removed, and may span lines -->
```

This prints:

- **WORK EXPERIENCE**: a section, with an uppercase title and a rule below it.
- **UX Factory, Inc.** in bold with `Aug. 2015 - Present` on the right. The
  first plain line after an entry is its subtitle, in italics, here with
  `Seoul` on the right. Then two bullets; the second has `Dec. 2025` on the right.
- **JOURNAL PAPERS**: bullets may sit directly under a section. The indented
  lines are smaller detail lines of the bullet above them. They are taken
  literally, so `- presented …` prints its dash.
- **SUMMARY**: a plain line directly under a section is a paragraph. The
  comment prints nothing.

| You write | You get |
|---|---|
| `## Title` | section |
| `### Title \| date` | entry; the date part is optional |
| plain line right after `###` | subtitle, optionally `\| right text` |
| `- text` / `- text \| date` | bullet / bullet with a date |
| indented line (2+ spaces) under a bullet | detail line of that bullet (no nested bullets) |
| plain line under `##` (no `###` open) | paragraph |
| `<!-- … -->` | comment |

- The right-aligned part is split at the **last** ` | ` (pipe with spaces).
  Write a literal ` | ` as `\|`.
- Inline: `**bold**`, `*italic*` or `_italic_`, `[text](url)`. Underscores
  inside words and URLs stay literal (`snake_case`, `a_b@x.com`).
- A backslash before ASCII punctuation makes it literal: `\*`, `\_`, `\|`,
  `\\`, `\{`. Everything else prints as typed: `& % # $ @ < > ~`, Hangul, `μ`.
- Blank lines are ignored.

### Full and short variants

Every line is in **both** variants unless it ends with a marker. The marker
must be the last thing on the line, after the date part:

- `{.full}`: only in the full variant
- `{.short}`: only in the short variant

| Marked line | What the marker covers |
|---|---|
| `## Section {.full}` | the whole section, up to the next `##` |
| `### Entry {.full}` | the whole entry, up to the next `###` or `##` |
| `- bullet {.full}` | the bullet and its detail lines |
| subtitle or paragraph | that line |
| `@file.md {.full}` | everything the file (and its includes) brings in |

<!-- example: variants -->
```markdown
## Awards
- Best Paper Award | Apr. 2009
- Eun Jong-Kwan Scholarship Award | Apr. 2009 {.full}

## Activities
- Over 20 invited talks on AI semiconductors. {.short}
- Technical Program Committee, ISSCC | 2024

## Invited Talks {.full}
- AI Semiconductor Strategies, *Kyung Hee University*, Nov., 2024.

## Research Output {.short}
- 10 journal and 25 conference papers, 18 registered patents
```

| Section | Full PDF | Short PDF |
|---|---|---|
| Awards | both awards | Best Paper Award only |
| Activities | the committee bullet only | the talks summary and the committee bullet |
| Invited Talks | shown | left out |
| Research Output | left out | shown |

- Markers nest by intersection. A `{.short}` inside a `{.full}` section can
  never appear; the build warns with file and line.
- A section or entry disappears with its heading only when the filter removed
  everything under it. A heading that is empty in the source stays.
- A typo such as `{.ful}`, `{full}` or `{ .full }` is an error, never printed.
  Other trailing braces (`- set {x}`) are ordinary text.

### Includes

A line holding only `@path.md` (optionally followed by a marker) is replaced
by that file's lines. Paths are relative to the including file. Includes nest;
a cycle or a missing file is an error that names the file and line.

<!-- example: include -->
```markdown
## Publications {.full}
### Journal Papers
@../shared/journals.md {.full}
```

Written in `content/en/resume.md`, this pulls in every bullet of
`content/shared/journals.md`, in the full PDF only. The shared lists hold
bullets only, so each language writes its own headings (`### 국제 저널 논문`
in the Korean file includes the same `journals.md`).

## Common edits

**Add a talk or paper.** Add one bullet to the shared list, newest first; both
languages pick it up on the next `make`:

<!-- example: talk -->
```markdown
- Title of the Talk, *Venue Name*, Dec., 2026.
```

Papers take the author line as an indented detail line (your name is
highlighted automatically):

<!-- example: paper -->
```markdown
- Title of the Paper, *IEEE Journal of Solid-State Circuits*, vol. 1, pp. 1-10, 2026.
  A. Kim, Junyoung Park, B. Lee.
```

Then update the counts in the summary lines (`{.short}`) if they mention them.

**Switch fonts.** Change the `font:` line of the root file, e.g.
`font: Charter, NanumMyeongjo` (English) or `font: Pretendard` (Korean). The
first font is the main one; later fonts fill in missing glyphs (Hangul in the
English resume). `typst fonts` lists what Typst can see. macOS on-demand fonts
such as NanumMyeongjo live under `/System/Library/AssetsV2/com_apple_MobileAsset_Font*`;
the build passes those folders to Typst automatically. A font Typst cannot
find fails the build instead of silently using another one.

**Change the layout.** Edit `template/resume.typ` only (spacing, sizes, the
gray of the dates); the content files stay untouched.

## Format publications from BibTeX
The helper prints an HTML `<li>` list you can embed in the resume site.
```
python scripts/publication_formatter.py path/to/publications.bib \
  --section conference --output html_output.html
```

Use `--section journal` or `--section all` to switch categories, and
`--highlight-name` to mark a different author.
