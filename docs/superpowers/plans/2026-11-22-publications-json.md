# Publications from JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The resume's journal and conference lists come from one structured `content/shared/publications.json`, pulled in by an include line, for PDF, HTML and DOCX in English and Korean.

**Architecture:** A new module `scripts/resumegen/publications.py` loads and validates the JSON, selects and sorts items, and formats each one as the two Markdown lines the `.md` lists hold today. `source.py` hands `@<file>.json <type> [first-author] [marker]` include lines to it, so parsing, variant filtering and the three writers stay unchanged.

**Tech Stack:** Python 3.10+ standard library (`json`, `re`, `dataclasses`), `unittest`, GNU Make.

**Spec:** `docs/superpowers/specs/2026-11-22-publications-json-design.md` (read it first; section numbers below refer to it).

## Global Constraints

- Python standard library only; no new dependency, no `pip install`.
- English in code, comments, docstrings, error and warning messages.
- Errors are `ResumeError("<path>:<line>: <message>")`, as `resumegen.errors.at()` builds them.
- Work on branch `publications`; commit only your own paths (`git commit -m "<msg>" -- <paths>`); never push.
- `~/workspace/jyp.me` is read-only.
- Short variants (`en_short`, `ko_short`) as `.typ`, `.html`, `.docx` stay byte-identical to `formats` (3cbe394), except a count line if a total changes (spec §2).
- Never send the owner's email or other personal details to a web service; use a generic User-Agent.

## Review Focus

1. A title or venue holding Markdown-special characters, ` | `, or ending in `{.full}` prints literally and never changes the variant (Task 2 round-trip test).
2. Non-ASCII names (`Émile Zola`, Hangul) abbreviate by their first letter without crashing (Task 2).
3. A JSON file saved with a BOM or CRLF line endings loads, and error line numbers still match the file (Task 1).
4. The owner's name spelled differently in one item (`J. Park`) is an error, not a silently missing first-authored paper (Task 1: owner must be among the authors).
5. `"year": true` or `"month": "3"` is rejected rather than printed (Task 1).

---

### Task 1: Load and validate the data file

**Files:**
- Create: `scripts/resumegen/publications.py`
- Create: `content/shared/publications.schema.json`
- Test: `tests/test_publications.py`

**Interfaces:**
- Produces:
  - `SCHEMA_VERSION = 1`, `TYPES = ("journal", "conference")`
  - `REQUIRED_FIELDS = frozenset({"id", "type", "title", "authors", "venue", "year"})`
  - `KNOWN_FIELDS = REQUIRED_FIELDS | {"month", "month_end", "volume", "issue", "pages", "location", "doi", "url"}`
  - `@dataclass(frozen=True) class Venue: name: str; short: str | None`
  - `@dataclass(frozen=True) class Publication:` fields `id, type, title: str; authors: tuple[str, ...]; venue: Venue; year: int; month, month_end: int | None; volume, issue, pages, location, doi, url: str | None; lineno: int` (line of the item's `"id"` key, 1 if not found)
  - `@dataclass(frozen=True) class Publications: path: Path; owner: str; items: tuple[Publication, ...]`
  - `load_publications(path: Path, include_line: Line | None = None) -> Publications`, raising `ResumeError`

- [ ] **Step 1: Write the failing tests** in `tests/test_publications.py` (`LoadTest`, writing JSON into a temp dir like `tests/test_source.py`):
  - `test_loads_minimal_file`: two items → `owner == "Junyoung Park"`, `items[1].venue == Venue("IEEE International Solid-State Circuits Conference", "ISSCC")`, `items[1].lineno` equals the 1-based line of its `"id"`.
  - `test_unknown_fields_ignored`: `"sci": true` on an item and `"$schema"` at the top load without error.
  - `test_bom_and_crlf`: the same file with `﻿` and `\r\n` loads; an error in it still names the right line.
  - `test_invalid_json`: `{\n  "schema": 1,\n  oops\n}` → message starts with `f"{path}:3: invalid JSON"`.
  - `test_errors` (subTest per case; each asserts the full message `f"{path}:{line}: {label}: {text}"`, label = the item's id, or `publications[i]` without a valid id):
    - schema `2` → line 1, label omitted: `unsupported schema version 2; this build reads 1`
    - missing `owner` → line 1: `missing "owner"`
    - item without `venue` → `missing "venue"`
    - `"type": "book"` → `"type" must be journal or conference`
    - `"id": "X_1"` → `"id" must match [a-z0-9-]+`
    - second item with the same id → at the second item's line: `duplicate id "isscc-2013-park"`
    - `"year": true` → `"year" must be an integer`; `"month": "3"` → `"month" must be an integer 1-12`; `"month": 13` → same
    - `"month_end": 12` without `month` → `"month_end" needs "month"`; `"month": 11, "month_end": 11` → `"month_end" must be after "month"`
    - `"authors": []` → `"authors" must be a non-empty list of names`; `"pages": ""` → `"pages" must not be empty`
    - authors without the owner → `owner "Junyoung Park" is not among the authors`
  - `test_missing_file`: with an `include_line`, message is `f"{line.path}:{line.lineno}: included file not found: {path}"`.
  - `test_schema_file_matches_validator`: in `content/shared/publications.schema.json`, the item's `required` equals `REQUIRED_FIELDS` and its `properties` keys equal `KNOWN_FIELDS`; top-level `required` is `["schema", "owner", "publications"]`.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_publications -v` — expected: FAIL (`ModuleNotFoundError: resumegen.publications`).

- [ ] **Step 3: Implement** `load_publications` and the dataclasses. Read bytes, decode `utf-8-sig`, normalize newlines, `json.loads`; do not strip `<!-- -->` (titles are data). Find each item's line with the first match of `"id"\s*:\s*"<re.escape(id)>"` in the text. Reject `bool` where an integer is required. Write `publications.schema.json` (JSON Schema 2020-12) from spec §4, `additionalProperties` left open.

- [ ] **Step 4: Run** `python3 -m unittest tests.test_publications -v` — expected: PASS.

- [ ] **Step 5: Commit** `git commit -m "Load and validate publications.json" -- scripts/resumegen/publications.py content/shared/publications.schema.json tests/test_publications.py` (after `git add` of the same paths).

### Task 2: Select, sort and format items

**Files:**
- Modify: `scripts/resumegen/publications.py`
- Test: `tests/test_publications.py`

**Interfaces:**
- Consumes: `Publication`, `Publications` (Task 1)
- Produces:
  - `select(pubs: Publications, type_: str, first_author: bool) -> list[Publication]` — newest first by year, then month (items without a month last within their year); stable for ties.
  - `format_item(pub: Publication, owner: str) -> tuple[str, str]` — the bullet line (`"- …"`) and the detail line (`"  …"`).
  - `short_name(name: str) -> str`, `escape(text: str) -> str`

- [ ] **Step 1: Write the failing tests** (`FormatTest`):
  - `test_select_order`: file order 2012-11, 2013 (no month), 2013-02 "a", 2013-09, 2013-02 "b" → ids in order 2013-09, 2013-02 "a", 2013-02 "b", 2013, 2012-11; `first_author=True` keeps only items whose `authors[0] == owner`; `type_` filters.
  - `test_journal_line`: the TCAS-I item of spec §4 → `("- A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor for Micro Air Vehicle Navigation, *IEEE Transactions on Circuits and Systems I: Regular Papers*, vol.63, no.3, pp.359-369, Mar. 2016.", "  Y. Kim, I. Hong, Junyoung Park, and H.-J. Yoo.")`
  - `test_conference_line`: the ISSCC item of spec §4 → `"- A 646GOPS/W multi-classifier many-core processor with cortex-like architecture for super-resolution recognition, *IEEE International Solid-State Circuits Conference*, Feb. 2013."` and `"  Junyoung Park, I. Hong, G. Kim, Y. Kim, K. Lee, S. Park, K. Bong, and H.-J. Yoo."`
  - `test_dates`: `month=11, month_end=12, year=2012` → ends `Nov.-Dec. 2012.`; no month → `2012.`; all twelve months give `Jan. Feb. Mar. Apr. May June July Aug. Sept. Oct. Nov. Dec.`
  - `test_authors`: one author → `"  Junyoung Park."`; two → `"  Junyoung Park and H.-J. Yoo."`
  - `test_short_name`: `Seongwook Park→S. Park`, `Hoi-Jun Yoo→H.-J. Yoo`, `Kyuho Jason Lee→K. J. Lee`, `H.-J. Yoo` and `K.J. Lee` unchanged, `Émile Zola→É. Zola`, `Plato→Plato`; the owner is never abbreviated by `format_item`.
  - `test_escape_round_trip`: for every `c` in `string.punctuation`, a title `f"a{c}b {c} c{c}"` and a title ending in `" {.full}"` go through `format_item`, then `parse()` (minimal front matter + `## S` + the two lines, built as `Line`s) and `filter_variant(..., "short")`; the item exists, and `plain_text(parse_inline(item.text))` equals `f"{title}, {venue}, Feb. 2013."` with the title unchanged.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_publications -v` — expected: the new tests FAIL.

- [ ] **Step 3: Implement** `select`, `format_item`, `short_name`, `escape`. `escape` puts a backslash before `\ * _ [ ] | {` (spec §6). Missing `volume`/`issue`/`pages` drop their label and comma. `short_name`: unchanged if any word but the last ends in `.`; otherwise each earlier word → first letter + `.`, hyphenated parts each (`Hoi-Jun` → `H.-J.`).

- [ ] **Step 4: Run** `python3 -m unittest tests.test_publications -v` — expected: PASS.

- [ ] **Step 5: Commit** `-- scripts/resumegen/publications.py tests/test_publications.py`, message `Select and format publications as resume lines`.

### Task 3: The `.json` include line

**Files:**
- Modify: `scripts/resumegen/source.py` (`INCLUDE_RE` area and `_load`)
- Modify: `scripts/resumegen/publications.py`
- Test: `tests/test_source.py`

**Interfaces:**
- Consumes: `load_publications`, `select`, `format_item` (Tasks 1–2)
- Produces: `include_lines(path: Path, words: list[str], include_line: Line, scope: frozenset[str]) -> list[Line]` in `publications.py`; each item gives two `Line`s with `path=path`, `lineno=item.lineno`, `scope=scope`.

- [ ] **Step 1: Write the failing tests** in `tests/test_source.py`:
  - `test_json_include_lines`: `en/resume.md` has `@../shared/p.json conference first-author {.full}` → the loaded lines are the formatted lines of the first-authored conference items, newest first, with `path` ending `shared/p.json`, `lineno` of each item's `"id"`, `scope == {"full"}`.
  - `test_json_include_end_to_end`: with `highlight: Junyoung Park`, `parse` + `filter_variant(..., "full")` give a section whose items' text and details match `format_item`, and the short variant drops them.
  - `test_json_include_errors` (subTest; each message is `f"{md}:{line}: {text}"`): no words → `a .json include needs a type: journal or conference`; `journal conference` → `a .json include takes one type`; `conference selected` → `unknown word "selected" in a .json include; use journal, conference or first-author`; missing file → `included file not found: …`.
  - `test_json_error_points_into_json`: a bad `month` in the JSON → message starts with the JSON path and the item's line.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_source -v` — expected: new tests FAIL.

- [ ] **Step 3: Implement.** Add `_JSON_INCLUDE_RE = re.compile(r"^@(\S+\.json)((?:\s+[^\s{]\S*)*)(?:\s+\{\.(full|short)\})?\s*$")` beside `INCLUDE_RE`; in `_load`, a match resolves the path like `.md` includes, narrows the scope with the marker, and extends `out` with `include_lines(...)`. `.md` behavior is unchanged (existing tests stay green).

- [ ] **Step 4: Run** `make test` — expected: all tests pass.

- [ ] **Step 5: Commit** `-- scripts/resumegen/source.py scripts/resumegen/publications.py tests/test_source.py`, message `Include publication lists from a JSON file`.

### Task 4: The data file (research, owner gate)

**Files:**
- Create: `content/shared/publications.json`
- Create (not committed, excluded in `.git/info/exclude`): `research/publications/` — saved source pages and API responses, and `review.md`

- [ ] **Step 1: Collect.** Read `~/workspace/jyp.me/src/data/publications.json`, `content/shared/journals.md`, `content/shared/conferences.md`. For each of the 36 papers, look the paper up on the web. Sources, in this order: Crossref (`https://api.crossref.org/works/<doi>`, or `https://api.crossref.org/works?query.bibliographic=<title>&rows=3`), DBLP (`https://dblp.org/search/publ/api?q=<title>&format=json`), IEEE Xplore. Save every response or page you rely on under `research/publications/<id>-<source>.json|html`.
- [ ] **Step 2: Build** `content/shared/publications.json` by spec §4: ids `<short venue>-<year>-<first author family name>`, venue names in natural order with short names, `detail` split into fields, `doi` from `dx.doi.org` URLs or Crossref.
- [ ] **Step 3: Write `research/publications/review.md`:** one row per value where the resume `.md`, the homepage JSON and the web disagree, or that only the web gives (co-author full names, JSSC 2016 final volume and pages): `id | field | resume .md | homepage | web (source, saved file) | proposal`. Include the conference total question of spec §7 and every printed change the new data makes to today's resume lists. Send the lead a short message with the path.
- [ ] **Step 4: Owner gate.** The lead shows the table to the owner and sends back the decisions; apply them.
- [ ] **Step 5: Verify** `python3 -c "import sys; sys.path.insert(0,'scripts'); from pathlib import Path; from resumegen.publications import load_publications; print(len(load_publications(Path('content/shared/publications.json')).items))"` — expected: the approved paper count, no error.
- [ ] **Step 6: Commit** `-- content/shared/publications.json`, message `Add publications.json: journal and conference papers`.

### Task 5: Switch the resumes to the JSON

**Files:**
- Modify: `content/en/resume.md:72,75`, `content/ko/resume.md:70,73` (include lines); count lines of spec §2 only if the approved totals differ
- Delete: `content/shared/journals.md`, `content/shared/conferences.md`
- Modify: `README.md` (new "Publications data" section; the `include` and `paper` examples and "Add a talk or paper"), `tests/test_readme.py`

- [ ] **Step 1: Baseline.** `git archive 3cbe394 | tar -x -C "$SCRATCH/base" && make -C "$SCRATCH/base" all` (with `RESUME_ROOT="$SCRATCH/base"`).
- [ ] **Step 2: Update the README examples and `tests/test_readme.py`** so the documented include is the JSON form and "add a paper" adds a JSON item; run `python3 -m unittest tests.test_readme -v` — expected: FAIL until Step 3.
- [ ] **Step 3: Edit** the include lines to `@../shared/publications.json journal {.full}` and `@../shared/publications.json conference first-author {.full}`; delete the two `.md` lists; write the README section (file, fields table, include line, how to add a paper).
- [ ] **Step 4: Run** `make test` and `make` — expected: all tests pass, 12 files built.
- [ ] **Step 5: Compare** with the baseline: `cmp` the six short files (`.typ`, `.html`, `.docx`); `diff` the `pdftotext -layout` text of the full PDFs. Expected: short files identical (or only the approved count line); full differences only in the two lists and approved count lines.
- [ ] **Step 6: Commit** the content, README and test paths, message `Read journal and conference papers from publications.json`.

### Task 6: Independent verification

**Files:** read-only; report `VERIFY-publications.md` in the verifier's own folder.

- [ ] Check every acceptance criterion of spec §9 on the final `publications` commit with its own commands, including: each approved table decision is in the JSON; ten random items' printed lines match `format_item` by hand; the error cases of Tasks 1 and 3 from the CLI; `make test`; `git diff 3cbe394 --stat` touches only the files this plan names.
