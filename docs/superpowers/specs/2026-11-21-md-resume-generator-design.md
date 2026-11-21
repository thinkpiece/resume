# Markdown Resume Generator — Design

Date: 2026-11-21
Status: approved by owner on 2026-11-21 (PDF policy 1b, git flow 2a)

## 1. Intent

The owner maintains an English and a Korean resume as hand-written LaTeX
(`resume_junyoungpark.tex` + `resume.cls`, `resume_junyoungpark_ko.tex` +
`resume-ko.cls`). Editing content means editing LaTeX, and each language has
only one length: the English file is effectively a long (3-page) resume, the
Korean file is a 1-page summary.

Target: the owner writes resume **content only, in Markdown**. A generator turns
each Markdown resume into PDF, in two variants — **full** (long) and **short**
(1 page) — chosen by markers written next to the content. The owner will keep
adding talks, journal and conference papers to the full version later, so the
long lists must live in separate Markdown files that the main file pulls in
with `@file.md`.

## 2. Goals, non-goals, anti-goals

Goals
- One Markdown source per language produces both variants:
  `build/Resume_JunyoungPark_{en,ko}_{full,short}.pdf`.
- Full/short selection is written inline in the Markdown (section 5).
- `@path.md` lines pull other Markdown files in, recursively.
- Rendering with **Typst**; layout based on the **current English resume**
  (classic, black-and-white, uppercase section titles with a rule), lightly
  refreshed.
- All visible content of both existing resumes is migrated; nothing is lost.

Non-goals
- No HTML/web output. `scripts/publication_formatter.py` (BibTeX → HTML) stays
  as it is and is not integrated.
- No general-purpose Markdown renderer: only the resume dialect in section 4.
- No automatic shrinking to fit one page.

Anti-goals (failure even if it "works")
- The Korean resume's current look: navy accent color, left accent bars,
  colored role lines. The owner called it an "AI-generated look". The new
  template must not carry any of it over.
- Writing LaTeX/Typst by hand to change content. Content edits must only touch
  `content/`.
- Silent content loss: a malformed line must produce an error with file and
  line number, never be dropped quietly.

## 3. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| A | Markdown → Python → `.tex` → LuaLaTeX (reuse `resume.cls`) | No new install, but LaTeX escaping and design changes stay in LaTeX. |
| B | Markdown → HTML/CSS → headless Chrome PDF | Easy styling, but weak page-break control and output depends on the Chrome version. |
| **C (chosen)** | Markdown → Python → `.typ` → Typst | New tool (`brew install typst`, 0.15.x), but fast, clean templating, good CJK support, and the redesign is easier. |

The owner chose **C** because the setup is new anyway and the design needs to
change.

## 4. The Markdown dialect

### 4.1 Front matter (root file only)

```markdown
---
name: Junyoung Park
title: AI System-on-Chip Startup Founder & Director & Engineer
lang: en                 # en | ko  (sets hyphenation / line breaking)
paper: us-letter         # Typst paper name: us-letter | a4
font: Charter, NanumMyeongjo     # comma-separated fallback list
highlight: Junyoung Park # author name to bold+underline everywhere
location: Seongnam-si 13105, Gyeonggi-do, Republic of Korea
phone: +82-10-2542-5500
email: junyoung@uxf.ai
homepage: http://www.junyoungpark.com
linkedin: https://www.linkedin.com/in/parkjunyoung
---
```

- Flat `key: value` lines only; `#` starts a comment when preceded by a space.
  Parsed with the Python standard library (no PyYAML).
- Recognized contact keys, printed in the order they appear, each with an
  icon: `location`, `phone`, `email`, `homepage`, `linkedin`, `github`.
  `email` → `mailto:` link, `phone` → `tel:` link, URLs → links.
- Unknown keys → error. Front matter in an included file → error.

### 4.2 Body

| Markdown | Meaning |
|---|---|
| `## Work Experience` | Section (uppercase title + full-width rule). |
| `### UX Factory, Inc. \| Aug. 2015 - Present` | Entry: bold title, right-aligned date. Date part optional. |
| plain line right after `###` | Entry subtitle (role), italic; optional `\| right text` (location). |
| `- text` | Bullet item. |
| `- text \| Dec. 2025` | Bullet with a right-aligned date. |
| indented line (2+ spaces) under a bullet | Continuation: a line break inside that bullet, rendered as a slightly smaller "detail" line (publication authors, venue notes). Taken literally, so a leading `- ` prints as a dash (the English education entries use "- presented and demonstrated at …"). |
| plain line directly under `##` (no `###`) | Paragraph. |
| blank lines | Ignored (only separate blocks). |
| `<!-- ... -->` | Comment, removed before parsing (may span lines). |

- The right-aligned part is split at the **last** ` | ` (pipe with spaces). A
  literal pipe is written `\|`.
- A `###` may contain only bullets and no subtitle (e.g. `### Awards`).
- Bullets may appear directly under `##` without any `###`.
- There are no nested bullets: an indented `  - ` line is a continuation line
  (lead's call, so the existing "- presented …" lines migrate unchanged).
- An indented line with no bullet above it → error with file and line.

### 4.3 Inline formatting

`**bold**`, `*italic*` (also `_italic_`), `[text](url)`, and backslash escapes
(`\*`, `\_`, `\|`, `\\`). Everything else is literal text: `&`, `%`, `#`, `$`,
`@`, `<`, `>`, `~` and non-ASCII (Hangul, `μ`) print as typed.

The `highlight` name from the front matter is bolded and underlined wherever it
appears in the body (publication author lines).

### 4.4 Includes

- A line consisting only of `@relative/path.md` (optionally followed by a
  variant marker) is replaced by that file's content.
- Paths are relative to the **including** file's directory.
- Includes are textual and happen before parsing, so an included file may hold
  a whole section, a few entries, or just bullet lines under a heading written
  in the including file.
- Includes nest. A cycle → error naming the chain. Missing file → error naming
  the including file and line.
- Line numbers in all errors refer to the original file that holds the line.

## 5. Full / short selection

Default: every line is in **both** variants. Exceptions are marked at the end of
a line:

- `{.full}` — only in the full variant.
- `{.short}` — only in the short variant.

Scope of a marker depends on the line it ends:

| Marked line | Scope |
|---|---|
| `## Section {.full}` | the whole section, up to the next `##` |
| `### Entry {.full}` | the whole entry, up to the next `###` or `##` |
| `- bullet {.full}` | that bullet with its continuation lines |
| subtitle / paragraph line | that line |
| `@file.md {.full}` | everything the file (and its includes) contributes |

Rules:
- Markers nest by intersection: content shows only if every enclosing marker
  allows the variant. A `{.short}` inside a `{.full}` scope can never show →
  warning naming the file and line.
- An entry or section is dropped together with its heading only when filtering
  removed everything under it. An entry or section that was empty in the source
  (e.g. `### B.S. in EE, KAIST | Feb. 2009` with nothing below) is kept.
- The marker is written after the date part: `- Award name | Apr. 2009 {.full}`.
- `{.short}` exists for summary lines that replace a long list in the short
  variant (e.g. "10 journal and 27 conference papers").

Alternatives rejected: a separate short-manifest file (two files to keep in
sync); HTML-comment markers (invisible in Markdown preview, hard to audit).

## 6. Layout (Typst template)

Base: the current English PDF (`Resume_JunyoungPark.pdf`), refreshed lightly.

- Header: name large, bold, uppercase (uppercase has no effect on Hangul); title
  line below; one wrapped line of contact items, each `icon + text`, black.
- Section: bold uppercase title, a thin full-width black rule below.
- Entry: bold title left, date right (regular weight); subtitle italic on the
  next line with optional right text.
- Bullets: small middle-dot marker, tight spacing, as in the English PDF.
- Bullet date: right-aligned on the bullet's line.
- Continuation lines: slightly smaller size.
- Colors: black text only. Dates may use a dark gray. No accent colors, no side
  bars.
- No page numbers.
- Margins: 0.6 in left/right, 0.5 in top/bottom (as now).
- Icons: Font Awesome Free icons vendored into the repo as SVG (envelope, phone,
  link, map-marker, linkedin, github), sized to the text; include the
  Font Awesome Free license file. (The FA5 OTFs exist only inside the owner's
  texmf tree, so the template must not depend on them.)
- Korean italics: Hangul fonts have no italic; the subtitle stays upright in
  that case. That is acceptable.

Fonts (owner: English must not use Pretendard):
- English resume: `Charter` (installed with macOS; a more modern classic serif
  than Times New Roman), Hangul fallback `NanumMyeongjo` for the Korean patent
  titles and venue names that appear in the English resume. NanumMyeongjo is
  an on-demand macOS font under `/System/Library/AssetsV2/…Font8/`; check with
  `typst fonts` that Typst finds it. If it does not, pass that directory with
  `--font-path`, or fall back to `AppleMyungjo` (what the LaTeX version used).
- Korean resume: `Pretendard` for both Hangul and Latin.
- Both lists come from front matter, so the owner can switch fonts without
  touching the template. The build must fail (not substitute silently) if the
  first font of the list is missing — Typst warns on unknown fonts; turn that
  warning into an error in the generator.

## 7. Repository layout

```
content/
  en/resume.md             # English root
  ko/resume.md             # Korean root
  shared/journals.md       # journal papers (bullets only, English)
  shared/conferences.md    # conference papers (bullets only, English)
  shared/talks.md          # invited talks (bullets only)
  shared/patents.md        # patents (bullets only)
template/
  resume.typ               # Typst template (layout only)
  icons/*.svg, icons/LICENSE.txt
scripts/
  build_resume.py          # generator CLI (stdlib only)
  publication_formatter.py # unchanged
tests/
  test_build_resume.py     # unittest
  fixtures/...
build/                     # generated .typ and .pdf, git-ignored
Makefile
README.md                  # rewritten for the new workflow
docs/superpowers/specs/... # this document
```

Shared lists hold only bullets; headings stay in each language's root file, so
the Korean resume can title them in Korean.

Git flow (owner decision 2a):
1. The untracked Korean LaTeX files and the pending `Makefile` edit are committed
   on `master` as a baseline, so they stay in git history.
2. All work happens on branch `md-resume`.
3. After the owner approves the rendered pages, the LaTeX files (`*.tex`,
   `*.cls`, LaTeX build artifacts) are deleted and `md-resume` is merged into
   `master`. Nothing is pushed.

PDF policy (owner decision 1b): the repository keeps **no** PDF. The tracked
`Resume_JunyoungPark.pdf` and `resume_junyoungpark_ko.pdf` are deleted with the
LaTeX files; generated PDFs live only in the git-ignored `build/`.

## 8. Generator

`python3 scripts/build_resume.py content/en/resume.md --variant full -o build/Resume_JunyoungPark_en_full.pdf`

Pipeline: read root → strip comments → resolve includes (keeping origin
file/line for every line) → parse front matter and body into a tree → filter by
variant → emit `build/<name>.typ` that imports `template/resume.typ` → run
`typst compile --root <repo>` → check page count.

- Text reaches Typst **only as string literals** (escape `\` and `"`), combined
  with `strong()`, `emph()`, `underline()`, `link()` calls. Never as Typst
  markup, so no Typst markup escaping bugs are possible.
- `--variant full|short` (required), `-o/--output`, `--typ-only` (write the
  `.typ`, skip compiling).
- Short variant: if the PDF has more than one page, print a warning with the
  page count (exit code 0).
- Missing `typst` binary → clear error suggesting `brew install typst`.
- Python standard library only; works on Python 3.10+.

Makefile:
- `make` / `make all` → the four PDFs.
- `make en-full`, `make en-short`, `make ko-full`, `make ko-short`.
- `make test` → `python3 -m unittest discover -s tests`.
- `make clean` → remove `build/`.
- PDFs rebuild when any file under `content/`, `template/` or the generator
  changes.

## 9. Content migration

Source of truth: the visible text of the existing `.tex` files. Commented-out
LaTeX lines are not migrated.

English (`content/en/resume.md`)
- Full = everything visible in the current English PDF, same order, same
  wording. Lists for talks, journals, conferences and patents move to
  `content/shared/` and are included `{.full}`.
- Short (new, draft for owner review) mirrors the Korean short structure:
  Summary (English rendering of the Korean "핵심 요약", in both variants), Work
  Experience, Education, the four awards the Korean short keeps, Activities
  (TPC ×2, evaluation committee, plus a `{.short}` line summarizing invited
  talks), and a `{.short}` research-output summary.

Korean (`content/ko/resume.md`)
- Short = everything visible in the current Korean PDF, same wording.
- Full (new, draft) = short + the two awards missing from the Korean file
  (translated), invited talks, journals, conferences and patents from
  `content/shared/`, all `{.full}`; the "연구 실적 요약" section is `{.short}`.

Known data inconsistencies to report to the owner, not to fix silently:
- Korean summary says 37 papers / 27 conference papers / 20 patents; the English
  file lists 10 journals, says "25 papers in total" for conferences, and lists
  18 patents. Copy the numbers as they are; the owner fixes them in Markdown.

## 10. Acceptance criteria

1. With Typst installed, `make` builds the four PDFs from `content/` only,
   without errors or font warnings.
2. Unit tests cover: markers on `##`, `###`, bullet, subtitle and `@` lines;
   intersection of nested markers; dropping empty entries/sections; includes
   (relative paths, nesting, cycle error, missing-file error with line);
   pipe split and `\|`; inline bold/italic/link; highlight name; special
   characters `& % # $ @ < > _ * " \`; Hangul text; errors carry file:line.
3. `pdftotext` of the English full PDF contains every visible text line of the
   old English PDF; the Korean short PDF contains every visible text line of the
   old Korean PDF (whitespace-normalized comparison; differences listed and
   explained).
4. Both short PDFs are one page.
5. No missing glyphs (Typst reports none; spot-check rendered PNGs).
6. Rendered pages follow section 6 and carry none of the anti-goal styling;
   the owner sees rendered images before the work is called done.
7. README explains the workflow and the Markdown dialect with examples.

## 11. Left to the builder

- Exact Typst function signatures and spacing values in the template.
- Internal data structures of the generator.
- How page count is read (e.g. `pdfinfo`, or counting pages in the PDF).
- Icon SVG source (Font Awesome Free 5.x from the npm package via a CDN is fine).
