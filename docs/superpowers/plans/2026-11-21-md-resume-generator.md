# Markdown Resume Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `content/{en,ko}/resume.md` (+ `@`-included files) into
`build/Resume_JunyoungPark_{en,ko}_{full,short}.pdf` through a Python generator
and a Typst template.

**Architecture:** `scripts/resumegen/` (Python, stdlib only) reads Markdown,
resolves `@includes`, parses the resume dialect into a tree, filters it by
variant, and emits a `.typ` file that only calls functions from
`template/resume.typ`. `scripts/build_resume.py` is the CLI that writes the
`.typ`, runs `typst compile`, and checks the page count. Layout lives only in
the template; content lives only in `content/`.

**Tech Stack:** Python ≥ 3.10 standard library, `unittest`; Typst 0.15.x
(`brew install typst`); GNU Make; poppler `pdftotext`/`pdftoppm` for checks.

**Spec:** `docs/superpowers/specs/2026-11-21-md-resume-generator-design.md`
(section numbers below, "§n", refer to it). Read it before any task.

## Global Constraints

- Python standard library only; must run on Python 3.10+. No PyYAML, no Markdown library.
- Do not modify `scripts/publication_formatter.py`.
- Errors are raised as `ResumeError` with the message `"<path>:<line>: <message>"`; the CLI prints it to stderr and exits 1.
- Text reaches Typst only as string literals (escape `\` and `"`), never as Typst markup (§8).
- Output names: `build/Resume_JunyoungPark_{en,ko}_{full,short}.pdf`; generated `.typ` files go next to them in `build/`.
- `build/` is git-ignored; no PDF is committed anywhere (§7, owner decision 1b).
- Layout: black text, dates may be dark gray; no accent color, no side bars, no colored role lines (§2 anti-goals, §6).
- Margins 0.6in left/right, 0.5in top/bottom; no page numbers.
- English resume never uses Pretendard; English fonts `Charter, NanumMyeongjo`; Korean fonts `Pretendard` (§6).
- English in all code, comments, help text, and messages. Resume content keeps its language.
- Work on branch `md-resume` in `/Users/jy/workspace/resume`. Commit only the files in your task's scope. Never push.

## Review Focus

1. Editor artifacts: a UTF-8 BOM, CRLF line endings, or tab indentation in a `.md` file must parse the same as clean LF/space input (Task 1).
2. Marker typos such as `{.ful}`, `{full}`, `{ .full }` at the end of a line must be an error with file:line, never printed as text (Task 2).
3. Underscores inside words and URLs (`snake_case`, `https://a.com/a_b_c`, `junyoung_park@x.com`) must stay literal; only `_x_` delimited by non-word characters is italic (Task 4).
4. Page breaks must never leave an entry title (or section title) alone at the bottom of a page, separated from its first line (Task 5).
5. A long bullet or title with a right-aligned date must wrap without the text overlapping the date (Task 5).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `scripts/resumegen/__init__.py` | package marker, exports `ResumeError` | 1 |
| `scripts/resumegen/errors.py` | `ResumeError` | 1 |
| `scripts/resumegen/source.py` | read files, strip comments, normalize, resolve includes → `list[Line]` | 1 |
| `scripts/resumegen/model.py` | dataclasses for the tree | 2 |
| `scripts/resumegen/parse.py` | front matter + body + markers → `Document` | 2 |
| `scripts/resumegen/variants.py` | filter `Document` by variant | 3 |
| `scripts/resumegen/emit.py` | inline Markdown → Typst content; `Document` → `.typ` text | 4 |
| `scripts/build_resume.py` | CLI: build one PDF | 4 |
| `tests/test_source.py`, `test_parse.py`, `test_variants.py`, `test_emit.py`, `test_cli.py` | unittest suites; each inserts `scripts/` into `sys.path` | 1–4 |
| `Makefile`, `.gitignore`, `README.md` | build targets, ignore `build/`, docs | 4 |
| `template/resume.typ` | all layout | 5 |
| `template/icons/{location,phone,email,homepage,linkedin,github}.svg`, `template/icons/LICENSE.txt` | contact icons (Font Awesome Free 5.15.4, CC BY 4.0) | 5 |
| `template/sample.typ`, `template/tests/pagebreak.typ` | hand-written exercises of the template API | 5 |
| `content/en/resume.md`, `content/ko/resume.md`, `content/shared/{journals,conferences,talks,patents}.md` | resume content | 6 |
| `docs/reports/content-notes.md`, `docs/reports/verification.md` | member reports (not committed) | 6, 7 |

## Shared interfaces (fixed here; every task builds against these)

### Python data model (`scripts/resumegen/model.py`)

```python
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
    text: str; date: str | None; details: list[str]
    variants: frozenset[str]; origin: Line

@dataclass
class Paragraph:
    text: str; variants: frozenset[str]; origin: Line

@dataclass
class Entry:
    title: str; date: str | None
    subtitle: str | None; side: str | None
    subtitle_variants: frozenset[str]
    items: list[Item]; variants: frozenset[str]; origin: Line

@dataclass
class Section:
    title: str
    children: list[Entry | Item | Paragraph]
    variants: frozenset[str]; origin: Line

@dataclass
class Document:
    meta: Meta
    sections: list[Section]
    warnings: list[str]       # "<path>:<line>: <message>"
```

`variants` is always the **effective** set: the line's own marker ∩ the line's
include `scope` ∩ the parent's `variants`. Text fields hold raw inline Markdown
(markers and the right-aligned part already removed, `\|` already turned into `|`).

### Typst template API (`template/resume.typ`)

```typst
#let resume(name: "", title: none, lang: "en", paper: "us-letter",
            fonts: ("Charter",), contacts: (), body) = ...
// contacts: array of (kind: str, text: str, url: str or none)
#let section(title, body) = ...                 // title: content
#let entry(title: none, date: none, subtitle: none, side: none, body) = ...
#let item(body, date: none, details: ()) = ...  // details: array of content
#let paragraph(body) = ...
#let hl(name) = ...                             // name: str; bold + underline
```

### Emitted `.typ` shape (Task 4 writes it, Task 5 must render it)

```typst
#import "/template/resume.typ": *
#show: resume.with(
  name: "Junyoung Park",
  title: "AI System-on-Chip Startup Founder & Director & Engineer",
  lang: "en",
  paper: "us-letter",
  fonts: ("Charter", "NanumMyeongjo"),
  contacts: (
    (kind: "email", text: "junyoung@uxf.ai", url: "mailto:junyoung@uxf.ai"),
    (kind: "location", text: "Seongnam-si 13105", url: none),
  ),
)
#section([#"Work Experience"])[
  #entry(title: [#"UX Factory, Inc."], date: [#"Aug. 2015 - Present"], subtitle: [#"Co-founder and Chief Executive Officer"], side: none)[
    #item([#"Founded a company"])
    #item([#"Thesis"], date: [#"2014"], details: ([#"- presented at "#emph[#"ISSCC"]],))
  ]
]
```

Inline content is always a content block built only from `#"…"` string
literals, `#strong[…]`, `#emph[…]`, `#link("url")[…]`, and `#hl("…")`, with no
whitespace between pieces. The project is compiled with `--root` = repo root.

---

### Task 0 (lead): Toolchain

- [ ] `brew install typst` then `typst --version` → `typst 0.15.x`.
- [ ] `typst fonts | grep -E "^(Charter|NanumMyeongjo|Pretendard|AppleMyungjo)$"` → record which are found in the team brief. If NanumMyeongjo is missing, test `typst fonts --font-path "/System/Library/AssetsV2/com_apple_MobileAsset_Font8"`; record the outcome as a clarification (Task 4 then passes `--font-path`, or the English fallback becomes `AppleMyungjo`).

### Task 1: Source loading and includes

**Files:** Create `scripts/resumegen/{__init__,errors,model,source}.py` (model.py exactly as in Shared interfaces), `tests/test_source.py`.

**Interfaces:**
- Produces: `class ResumeError(Exception)`; `load_lines(root: Path) -> list[Line]`; `INCLUDE_RE` matching `^@(\S+\.md)(?:\s+\{\.(full|short)\})?\s*$`.

- [ ] **Step 1: Write failing tests** (each writes files into a `tempfile.TemporaryDirectory`)

```python
def test_include_relative_and_nested(self):
    # root.md: "a\n@sub/one.md\nz"; sub/one.md: "b\n@two.md"; sub/two.md: "c"
    lines = load_lines(root)
    self.assertEqual([l.text for l in lines], ["a", "b", "c", "z"])
    self.assertEqual(lines[2].path, d / "sub" / "two.md")
    self.assertEqual(lines[2].lineno, 1)

def test_include_marker_sets_scope(self):
    # root.md: "@a.md {.full}\nx"; a.md: "y"
    self.assertEqual([l.scope for l in load_lines(root)],
                     [frozenset({"full"}), VARIANTS])

def test_nested_include_scopes_intersect(self):
    # root: "@a.md {.full}"; a.md: "@b.md {.short}"; b.md: "q"
    self.assertEqual(load_lines(root)[0].scope, frozenset())

def test_include_cycle_error(self):
    # root.md: "@a.md"; a.md: "@root.md"
    with self.assertRaisesRegex(ResumeError, r"include cycle: root\.md -> a\.md -> root\.md"): ...

def test_missing_include_reports_file_and_line(self):
    # root.md: "x\n\n@missing.md"
    with self.assertRaisesRegex(ResumeError, rf"^{re.escape(str(root))}:3: .*missing\.md"): ...

def test_comments_removed_line_numbers_kept(self):
    # root.md: "a <!-- x\ny -->b\nc"
    lines = load_lines(root)
    self.assertEqual([(l.text, l.lineno) for l in lines], [("a ", 1), ("b", 2), ("c", 3)])

def test_bom_crlf_and_tabs_normalized(self):   # Review Focus 1
    # root.md bytes: b"\xef\xbb\xbf- a\r\n\tb\r\n"
    self.assertEqual([l.text for l in load_lines(root)], ["- a", "    b"])
```

- [ ] **Step 2:** `python3 -m unittest tests/test_source.py -v` → errors (module missing).
- [ ] **Step 3: Implement `load_lines`.** Decode as `utf-8-sig`, split with `splitlines()`, expand tabs (4). Strip `<!-- … -->` over the whole file text, replacing each removed span with only the newlines it contained, before splitting. Resolve include paths against the including file's directory, `.resolve()` them for cycle detection, and show chain names relative to the root's directory.
- [ ] **Step 4:** Run the suite → all pass.
- [ ] **Step 5: Commit** `git add scripts/resumegen tests/test_source.py && git commit -m "Add Markdown source loader with includes"`.

### Task 2: Parser

**Files:** Create `scripts/resumegen/parse.py`, `tests/test_parse.py`.

**Interfaces:**
- Consumes: `Line`, `load_lines`, `ResumeError`, model classes.
- Produces: `parse(lines: list[Line]) -> Document`; `split_right(text: str) -> tuple[str, str | None]`; `split_marker(text: str, line: Line) -> tuple[str, frozenset[str]]`.

Rules (§4.1, §4.2, §5): front matter = lines between a first-line `---` and the next `---`. Allowed keys: `name, title, lang, paper, font, highlight, location, phone, email, homepage, linkedin, github`; `name` required; defaults `lang=en`, `paper=us-letter`, `font=Charter`. A ` #` starts a comment in values. Front matter whose first line comes from a non-root file is an error. Body line kinds: `## ` section, `### ` entry, `- ` bullet, indented (≥ 2 spaces) continuation, `@`-free plain text (subtitle when it is the first non-blank line after `###` with no bullets yet, paragraph when directly under `##` with no `###` open, otherwise an error), blank.

- [ ] **Step 1: Write failing tests**

```python
def test_front_matter(self):
    m = doc.meta
    self.assertEqual(m.fonts, ["Charter", "NanumMyeongjo"])
    self.assertEqual(m.contacts, [("location", "Seongnam-si"), ("email", "a@b.c")])
    self.assertEqual(m.title, "AI & SoC")   # value "AI & SoC  # note"

def test_unknown_front_matter_key(self):   # "colour: red" on line 3
    with self.assertRaisesRegex(ResumeError, r":3: unknown front matter key 'colour'"): ...

def test_front_matter_in_included_file_errors(self): ...

def test_entry_title_date_subtitle_side(self):
    # "## Work\n### UX Factory, Inc. | Aug. 2015 - Present\nCEO | Seoul\n- did x"
    e = doc.sections[0].children[0]
    self.assertEqual((e.title, e.date, e.subtitle, e.side), ("UX Factory, Inc.", "Aug. 2015 - Present", "CEO", "Seoul"))
    self.assertEqual(e.items[0].text, "did x")

def test_split_right_uses_last_pipe_and_escape(self):
    self.assertEqual(split_right("A | B | 2020"), ("A | B", "2020"))
    self.assertEqual(split_right(r"A \| B"), ("A | B", None))
    self.assertEqual(split_right("A|B"), ("A|B", None))   # pipe needs spaces

def test_continuation_lines_literal(self):
    # "- Title\n  S. Park, Junyoung Park\n  - presented at ISSCC"
    self.assertEqual(item.details, ["S. Park, Junyoung Park", "- presented at ISSCC"])

def test_indented_line_without_bullet_errors(self): ...   # ":2: continuation line without a bullet"

def test_marker_after_date(self):
    # "- Award | Apr. 2009 {.full}"
    self.assertEqual((item.text, item.date, item.variants), ("Award", "Apr. 2009", frozenset({"full"})))

def test_bad_markers_error(self):   # Review Focus 2
    for bad in ["- x {.ful}", "- x {full}", "- x { .full }", "## S {.Full}"]:
        with self.assertRaisesRegex(ResumeError, r":\d+: invalid variant marker"): ...
    # but "- set {x}" without a leading dot or word-only braces in the middle stays text:
    # rule: a trailing "{...}" whose content matches r"\s*\.?\s*[A-Za-z]+\s*" is a marker attempt.

def test_effective_variants_intersect_and_warn(self):
    # "## S {.full}\n- x {.short}"
    self.assertEqual(item.variants, frozenset())
    self.assertRegex(doc.warnings[0], r":2: .*can never appear")

def test_bullets_and_paragraphs_directly_under_section(self): ...
def test_text_before_any_section_errors(self): ...
def test_second_plain_line_in_entry_errors(self): ...   # ":4: unexpected text in entry; start it with '- '"
```

- [ ] **Step 2:** Run → fail.
- [ ] **Step 3: Implement `parse`, `split_right`, `split_marker`.** Order per line: strip trailing whitespace → `split_marker` (marker must be the last token) → `split_right` → unescape `\|`. Subtitle variants go into `Entry.subtitle_variants` (intersected with the entry's variants). Warn once per line whose effective set is empty because of a marker.
- [ ] **Step 4:** Run → pass.
- [ ] **Step 5: Commit** `git add scripts/resumegen/parse.py tests/test_parse.py && git commit -m "Add resume Markdown parser"`.

### Task 3: Variant filter

**Files:** Create `scripts/resumegen/variants.py`, `tests/test_variants.py`.

**Interfaces:**
- Consumes: `Document` from `parse`.
- Produces: `filter_variant(doc: Document, variant: str) -> Document` (new object; input untouched; `variant` not in `VARIANTS` → `ValueError`).

- [ ] **Step 1: Write failing tests** (documents built with `parse(load_lines(...))`)

```python
def test_section_marker_removes_subtree(self):      # "## Talks {.full}\n- t1"
    self.assertEqual([s.title for s in filter_variant(doc, "short").sections], ["Work"])

def test_entry_bullet_subtitle_markers(self): ...   # each removed in short, kept in full; reverse for {.short}

def test_include_marker_applies(self):              # "## Pubs\n@j.md {.full}" where j.md = "- p1\n- p2"
    self.assertEqual(filter_variant(doc, "short").sections, [])   # section emptied by filtering → dropped

def test_emptied_entry_dropped_source_empty_entry_kept(self):
    # "## Edu\n### PhD | 2014\n- x {.full}\n### BS | 2009"
    self.assertEqual([e.title for e in filter_variant(doc, "short").sections[0].children], ["BS"])

def test_never_visible_item_absent_from_both(self): ...
```

- [ ] **Step 2:** Run → fail. **Step 3:** Implement. **Step 4:** Run → pass.
- [ ] **Step 5: Commit** `git add scripts/resumegen/variants.py tests/test_variants.py && git commit -m "Add full/short variant filter"`.

### Task 4: Typst emitter, CLI, Makefile, README

**Files:** Create `scripts/resumegen/emit.py`, `scripts/build_resume.py`, `tests/test_emit.py`, `tests/test_cli.py`, `tests/fixtures/cli/` (tiny resume sources); modify `Makefile` (replace entirely), `.gitignore` (add `build/`), `README.md` (rewrite).

**Interfaces:**
- Consumes: `load_lines`, `parse`, `filter_variant`; template API and emitted shape from Shared interfaces.
- Produces: `inline_to_typst(text: str, highlight: str | None = None) -> str`; `emit_typst(doc: Document) -> str`; CLI `python3 scripts/build_resume.py SRC --variant {full,short} [-o OUT.pdf] [--typ-only]` (default OUT: `build/<stem>_<variant>.pdf`; the `.typ` is written to OUT with suffix `.typ`).

Contact URL rules: `email` → `mailto:`, `phone` → `tel:` + the value with everything except digits and a leading `+` removed, `homepage`/`linkedin`/`github` → value, `location` → `none`.

- [ ] **Step 1: Write failing tests**

```python
def test_plain_and_escapes(self):
    self.assertEqual(inline_to_typst('a "q" \\ b'), '[#"a \\"q\\" \\\\ b"]')

def test_special_characters_stay_in_strings(self):
    out = inline_to_typst("R&D 100% #1 $5 @x <y> ~z // c 54 μW 산업")
    self.assertEqual(out, '[#"R&D 100% #1 $5 @x <y> ~z // c 54 μW 산업"]')

def test_bold_italic_link(self):
    self.assertEqual(inline_to_typst("**B** and *i* [t](http://x.y)"),
                     '[#strong[#"B"]#" and "#emph[#"i"]#" "#link("http://x.y")[#"t"]]')

def test_underscores_literal_inside_words_and_urls(self):   # Review Focus 3
    self.assertEqual(inline_to_typst("snake_case_name"), '[#"snake_case_name"]')
    self.assertEqual(inline_to_typst("[a](https://a.com/a_b_c)"), '[#link("https://a.com/a_b_c")[#"a"]]')
    self.assertEqual(inline_to_typst("mail junyoung_park@x.com"), '[#"mail junyoung_park@x.com"]')
    self.assertEqual(inline_to_typst("an _it_ word"), '[#"an "#emph[#"it"]#" word"]')

def test_backslash_escapes(self):
    self.assertEqual(inline_to_typst(r"\*not\* \_x\_"), '[#"*not* _x_"]')

def test_highlight(self):
    self.assertEqual(inline_to_typst("S. Park, Junyoung Park, H. Yoo.", "Junyoung Park"),
                     '[#"S. Park, "#hl("Junyoung Park")#", H. Yoo."]')

def test_emit_document_shape(self):
    out = emit_typst(doc)
    self.assertTrue(out.startswith('#import "/template/resume.typ": *\n'))
    self.assertIn('fonts: ("Charter", "NanumMyeongjo"),', out)
    self.assertIn('(kind: "phone", text: "+82-10-2542-5500", url: "tel:+821025425500"),', out)
    self.assertIn('#section([#"Work"])[', out)
    self.assertIn('#entry(title: [#"UX"], date: [#"2015"], subtitle: none, side: none)[', out)
```

`tests/test_cli.py` (skip the class with `unittest.skipUnless(shutil.which("typst"), ...)` except the last test). It uses a stub template only if the real one is absent: copy `tests/fixtures/cli/stub_template.typ` (implements the API with plain text, no styling) to a temp repo root so Task 4 does not wait for Task 5; pass `--root` via the `RESUME_ROOT` environment variable (default: repo root).

```python
def test_builds_pdf(self):            # exit 0, PDF exists, .typ next to it
def test_short_page_warning(self):    # 120 short bullets → stderr has "warning: short variant has 2 pages" (or more), exit 0
def test_unknown_font_fails(self):    # font: NoSuchFont123 → exit 1, stderr mentions "NoSuchFont123"
def test_parse_error_format(self):    # bad marker → exit 1, stderr starts with "<path>:<line>: "
def test_missing_typst_message(self): # PATH="/nonexistent" → exit 1, stderr contains "brew install typst"
```

- [ ] **Step 2:** `python3 -m unittest tests/test_emit.py tests/test_cli.py -v` → fail.
- [ ] **Step 3: Implement `inline_to_typst` and `emit_typst`.** Tokenize left to right: backslash escape → literal next char; `**…**` → strong; `*…*` → emph; `_…_` → emph only when the opening `_` is not preceded by a word character and the closing `_` is not followed by one; `[text](url)` → link; everything else accumulates into the current string. Apply `highlight` on the plain-text runs only. Unclosed delimiters stay literal. Emit sections/entries/items in document order with the Shared-interfaces shape; `title`/`date`/`subtitle`/`side` that are `None` → `none`.
- [ ] **Step 4: Implement `scripts/build_resume.py`.** `load_lines` → `parse` → `filter_variant` → print `doc.warnings` to stderr → write `.typ` → unless `--typ-only`, run `typst compile --root <root> [--font-path …] X.typ X.pdf`; treat any `unknown font family` in Typst's stderr as an error (delete the PDF, exit 1); for `short`, count pages (`pdfinfo` if on PATH, else count `/Type /Page` objects) and warn when > 1. `ResumeError` → stderr, exit 1. Missing `typst` → `error: typst not found; install it with: brew install typst`.
- [ ] **Step 5: Makefile.** Targets `all` (default, four PDFs), `en-full`, `en-short`, `ko-full`, `ko-short`, `test` (`python3 -m unittest discover -s tests -v`), `clean` (`rm -rf build`). Each PDF depends on `$(shell find content template scripts/resumegen -type f) scripts/build_resume.py`. Output names per Global Constraints.
- [ ] **Step 6: README.** Replace the LaTeX instructions: prerequisites (`brew install typst`, Python 3.10+), `make` targets, folder layout (§7), the dialect (§4) and markers (§5) with a short example, how to add a talk or paper to a shared list, how to switch fonts. Keep the existing "Format publications from BibTeX" section.
- [ ] **Step 7:** Run `make test` → all pass (CLI tests may skip only if `typst` is absent; it is installed by Task 0, so they must run).
- [ ] **Step 8: Commit** `git add scripts tests Makefile .gitignore README.md && git commit -m "Add Typst emitter, build CLI, Makefile and README"`.

### Task 5: Typst template

**Files:** Create `template/resume.typ`, `template/icons/*.svg`, `template/icons/LICENSE.txt`, `template/sample.typ`, `template/tests/pagebreak.typ`.

**Interfaces:**
- Produces: the Typst template API in Shared interfaces, exactly those names and parameters; must render the emitted shape.

Design (§6): based on the old English PDF (`git show master:Resume_JunyoungPark.pdf > /tmp/x.pdf` or the file in the repo root), refreshed lightly. Header: name large, bold, `upper()`; title line; contact items `icon + text` in one wrapping line, icons ≈ 0.85em tall, black. Section: bold `upper()` title, thin black full-width rule below. Entry: bold title left, date right; italic subtitle with optional right `side`. Item: small middle-dot marker; date right-aligned on the item's last line; `details` each on its own line at ≈ 0.92× size. Text 10pt (adjust ±0.5pt only if it improves the look). Dates and `side` may be dark gray (`luma(70)` or darker); nothing else colored. Base `text(font: fonts, lang: lang)`; paragraphs left-aligned, not justified.

- [ ] **Step 1: Icons.** Download Font Awesome Free 5.15.4 SVGs from `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@5.15.4/svgs/`: `solid/map-marker-alt.svg` → `location.svg`, `solid/phone.svg` → `phone.svg`, `solid/envelope.svg` → `email.svg`, `solid/link.svg` → `homepage.svg`, `brands/linkedin.svg` → `linkedin.svg`, `brands/github.svg` → `github.svg`; save the license text (`LICENSE.txt` from the same package) as `template/icons/LICENSE.txt`.
- [ ] **Step 2: `template/sample.typ`.** Hand-write a document in the emitted shape (Shared interfaces) that exercises every function and parameter, using real lines from the English resume: header with all six contact kinds, an entry with subtitle and side, an entry without subtitle, an item with a date, an item with two `details`, a `paragraph`, `hl("Junyoung Park")` in an author line, and the longest award line with its date (`Critical Assessment of Genome Interpretation (CAGI7) Challenges TSC2 Top-performer | Dec. 2025`) plus an artificially longer one that must wrap (Review Focus 5). Add a second sample block with `lang: "ko"`, `fonts: ("Pretendard",)`, `paper: "a4"` as `template/sample-ko.typ`.
- [ ] **Step 3: Implement `template/resume.typ`.** Keep each entry header together with its first item and each section title together with its first child (Review Focus 4): wrap the header in `block(sticky: true)` (Typst ≥ 0.12).
- [ ] **Step 4: Page-break test (Review Focus 4).** `template/tests/pagebreak.typ`: a section of filler items sized so that the next entry header falls at the bottom of page 1. Run `typst compile --root . template/tests/pagebreak.typ build/pagebreak.pdf && pdftotext -f 1 -l 1 build/pagebreak.pdf - | tail -3` → the last text lines of page 1 must not be the entry title `ORPHAN CHECK ENTRY`. Record the filler count used in a comment in the file.
- [ ] **Step 5: Compile and look.** `typst compile --root . template/sample.typ build/sample.pdf` and the Korean sample → exit 0 and no warnings on stderr. Render `pdftoppm -r 110 -png build/sample.pdf build/sample` and compare with the old English PDF rendered the same way. Check: no overlap between wrapped text and dates; dot bullets aligned; header contact line wraps cleanly; nothing colored except gray dates; Korean sample has no tofu boxes.
- [ ] **Step 6: Commit** `git add template && git commit -m "Add Typst resume template"`.

### Task 6: Content migration

**Files:** Create `content/en/resume.md`, `content/ko/resume.md`, `content/shared/{journals,conferences,talks,patents}.md`; write `docs/reports/content-notes.md` (not committed).

**Interfaces:**
- Consumes: the dialect in §4 and §5 only (the generator may not exist yet).
- Produces: sources that `python3 scripts/build_resume.py content/{en,ko}/resume.md --variant {full,short} --typ-only` accepts.

Sources: `resume_junyoungpark.tex` (English) and `resume_junyoungpark_ko.tex` (Korean) in the repo root; the rendered PDFs next to them show what is visible. Conversion rules: drop LaTeX-commented lines; `\&` → `&`; `\emph{x}`/`\textit{x}` → `*x*`; `\underline{\bf Junyoung Park}` → `Junyoung Park` (the generator highlights it); `{\small …}` → its text; `\ko{x}` → `x`; `\hfill date` → ` | date`; LaTeX `--` → `–` (U+2013), a single `-` stays `-`; `\\` inside a bullet → a continuation line; `Spt.` and other suspicious spellings stay as they are but are listed in the notes file.

Structure (§9):
- `content/shared/journals.md`, `conferences.md`, `talks.md`, `patents.md`: bullets only, in the English file's order. Publication bullets: `- Title, *Venue*, details, date.` then the author line as a continuation. Talk bullets: `- Title, *Venue*, date.` Patent bullets: `- KR102888862 전기차 화재 관리 장치 및 이의 동작 방법`.
- `content/en/resume.md`: front matter as in §4.1 (fonts `Charter, NanumMyeongjo`, paper `us-letter`, the five contact fields of the English file). Sections in the English order. Full = all visible English content. Short additions (draft): `## Summary` (both variants) translating the three Korean summary bullets; awards other than the four the Korean short keeps → `{.full}`; Invited Talks, Journal Papers, Conference Papers, Patents → `{.full}` includes under `## Publications {.full}` / `### Invited Talks {.full}`; a `{.short}` activity bullet summarizing invited talks; a `## Research Output {.short}` section translating "연구 실적 요약".
- `content/ko/resume.md`: front matter with Korean values from the Korean file (fonts `Pretendard`, paper `a4`, four contact fields). Short = all visible Korean content, same wording and order. Full additions, all `{.full}`: the two awards missing from the Korean file, translated (`은종관 장학상 (석사 신입생 수석)`, `국가과학기술 연구장학생`) with their dates; `### 초청 강연` including `../shared/talks.md`; `## 연구 실적` with `### 국제 저널 논문`, `### 국제 학회 논문 (주저자)`, `### 특허` including the shared lists; `## 연구 실적 요약` gets `{.short}`.

- [ ] **Step 1:** Write the shared lists; count bullets: journals 10, conferences 6, talks 22, patents 18.
- [ ] **Step 2:** Write `content/en/resume.md` and `content/ko/resume.md`.
- [ ] **Step 3: Parity check.** `pdftotext -layout Resume_JunyoungPark.pdf -` and the Korean PDF: tick every visible line against the Markdown; write unmatched lines (should be none) and every wording decision to `docs/reports/content-notes.md`, including the numbers mismatch in §9.
- [ ] **Step 4:** When `scripts/build_resume.py` exists on the branch, run it with `--typ-only` for all four combinations → exit 0, no warnings. Until then, report this step as pending to the lead.
- [ ] **Step 5: Commit** `git add content && git commit -m "Migrate resume content to Markdown"`.

### Task 7: Verification (independent member, other provider)

**Files:** read-only except `docs/reports/verification.md`.

- [ ] `make clean && make` → four PDFs, exit 0, no warnings.
- [ ] `make test` → all pass, none skipped.
- [ ] Acceptance criteria §10.3: whitespace-normalized line comparison of `pdftotext` old English PDF vs new `en_full`, old Korean PDF vs new `ko_short`; list each difference and whether the spec explains it.
- [ ] §10.4: `pdfinfo build/*_short.pdf | grep Pages` → `1` for both.
- [ ] §10.5–6: render all four PDFs with `pdftoppm -r 110`, inspect every page for tofu, overlaps, orphaned headings, any color besides gray dates, any trace of the old Korean styling.
- [ ] Review Focus 1–5: confirm each has a passing test or a check.
- [ ] Try to break it: a marker typo, an include cycle, a missing include, a CRLF file, a font that does not exist — each must give a clear `path:line:` error.
- [ ] Write findings to `docs/reports/verification.md`: per criterion PASS/FAIL with evidence (command + output excerpt), then defects ranked by severity.

### Task 8 (lead): Owner review, cleanup, merge

- [ ] Check the combined result against §10 myself; render the four PDFs and show them to the owner.
- [ ] Apply the owner's design feedback (template or content tasks reopened as needed).
- [ ] After approval: `git rm` `resume_junyoungpark.tex` (tracked as `Resume_JunyoungPark.tex`), `resume_junyoungpark_ko.tex`, `resume.cls`, `resume-ko.cls`, `Resume_JunyoungPark.pdf`, `resume_junyoungpark_ko.pdf`; delete local LaTeX artifacts; remove LaTeX lines from `.gitignore` only if nothing else needs them; commit; merge `md-resume` into `master` (no push).
