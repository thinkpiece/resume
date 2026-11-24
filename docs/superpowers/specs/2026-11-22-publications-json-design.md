# Publications from JSON — Design

Date: 2026-11-22
Status: draft; data shape B (structured fields) chosen by the owner on 2026-11-22.
Branch: `publications`, started from `formats` (3cbe394).

## 1. Intent

The owner's journal and conference papers live in two places today, and they
already disagree:

- the resume: `content/shared/journals.md` (10 papers) and
  `content/shared/conferences.md` (6 first-authored papers), as Markdown bullets;
- the homepage: `~/workspace/jyp.me/src/data/publications.json` (10 journal and
  25 conference papers), as display strings (`venue`, `detail`).

The owner wants **one JSON file** of publications that every generator reads
and takes only what it needs: this resume generator now, the homepage and a
government-project document generator later. Later the file moves to a central
place outside this repo. Now it lives in this repo, and the resume reads its
publication lists from it.

Because several generators will pull different pieces out of it (year, volume,
pages, short venue name, first-authored only, …), the file holds **structured
fields**, not pre-formatted strings. Each generator formats them its own way.

## 2. Goals, non-goals, anti-goals

Goals
- `content/shared/publications.json` holds all journal and conference papers
  as structured items (section 4).
- The resume Markdown pulls a filtered, formatted list from it with one include
  line (section 5). PDF, HTML and DOCX, English and Korean, all get it, because
  the lines enter before parsing.
- The printed resume lists stay as they look today (section 6), except for
  differences the owner approves in the migration table (section 7).
- A broken data file fails the build with the file, the line and the item.
- Standard library only.

Non-goals (now)
- Invited talks and patents: they stay in `talks.md` and `patents.md`. The
  schema leaves room for them (a `type` per item).
- The homepage: `jyp.me` is not touched and keeps its own copy until the file
  is centralized; it will then need a small change to read this schema.
- Computing the paper counts that the resumes write by hand. They stay hand
  written; but if the settled data (section 7) changes a total, the numbers are
  corrected by hand in the same change, so the resume never contradicts its
  data. The places: `content/en/resume.md` lines 18 ("35 international journal
  and conference papers"), 74 ("25 Papers in Total"), 83 ("10 … and 25 …");
  `content/ko/resume.md` lines 17 ("논문 35편"), 72 ("총 25편"), 81
  ("10편 … 25편"). *(Designer's call.)*
- Moving the file to a central repository.

Anti-goals
- A second copy of the data (generated `.md` files kept next to the JSON).
- Data that only one consumer can read: no resume-specific Markdown, no
  pre-formatted strings in the JSON.
- Breaking the short variants: they contain no publications and must not change.

## 3. Approaches considered

Data shape (owner picked B)
- A. Keep the homepage shape (`venue`, `detail` display strings). Fastest, the
  homepage reads it unchanged, but volume, issue, pages, month and year are
  locked inside one string; nothing can sort by date or fill a form field.
- **B. Structured fields** (`year`, `month`, `volume`, `issue`, `pages`, venue
  name and short name, `doi`, …). Every generator formats its own way. Costs a
  one-time migration of 36 items and, later, a small homepage change.

JSON to resume (owner accepted the recommendation)
- **Build-time include.** The loader reads the JSON where the Markdown has an
  include line and turns each selected item into the same Markdown bullet lines
  that the `.md` lists hold today. Parsing, variant filtering and the three
  writers stay unchanged. One source, nothing to regenerate.
- Generate `.md` from JSON and commit it: two copies that drift when someone
  forgets to regenerate; against the intent.
- Writers read the JSON directly: three writers change, and variant markers,
  highlighting and escaping would be re-implemented three times.

## 4. The data file

Path: `content/shared/publications.json` (content edits stay inside
`content/`). UTF-8, standard JSON.

```json
{
  "$schema": "./publications.schema.json",
  "schema": 1,
  "owner": "Junyoung Park",
  "publications": [
    {
      "id": "tcas1-2016-kim",
      "type": "journal",
      "title": "A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor for Micro Air Vehicle Navigation",
      "authors": ["Youchang Kim", "Injoon Hong", "Junyoung Park", "Hoi-Jun Yoo"],
      "venue": {"name": "IEEE Transactions on Circuits and Systems I: Regular Papers", "short": "TCAS-I"},
      "year": 2016, "month": 3,
      "volume": "63", "issue": "3", "pages": "359-369",
      "url": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7420681&isnumber=7447839"
    },
    {
      "id": "isscc-2013-park",
      "type": "conference",
      "title": "A 646GOPS/W multi-classifier many-core processor with cortex-like architecture for super-resolution recognition",
      "authors": ["Junyoung Park", "I. Hong", "G. Kim", "Y. Kim", "K. Lee", "S. Park", "K. Bong", "H.-J. Yoo"],
      "venue": {"name": "IEEE International Solid-State Circuits Conference", "short": "ISSCC"},
      "year": 2013, "month": 2,
      "doi": "10.1109/ISSCC.2013.6487685",
      "url": "https://dx.doi.org/10.1109/ISSCC.2013.6487685"
    }
  ]
}
```

Top level
- `schema` (integer, required): `1`. A reader rejects a version it does not know.
- `owner` (string, required): the person the file belongs to, exactly as the
  name appears in `authors`. Used by the `first-author` filter.
- `publications` (array, required).
- `$schema` (optional): points editors at the JSON Schema file below.

Item fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string, `[a-z0-9-]+`, unique | yes | Stable key other generators can refer to; never changes once written. Pattern `<short venue>-<year>-<first author family name>`, `-2`, `-3` on a clash. |
| `type` | `"journal"` or `"conference"` | yes | |
| `title` | string | yes | As published. |
| `authors` | array of strings, at least one | yes | Paper order. Full name when known (`"Seongwook Park"`), otherwise as known (`"S. Park"`). The owner always exactly as `owner`. |
| `venue.name` | string | yes | Full name in natural order: `IEEE Journal of Solid-State Circuits`, `IEEE International Solid-State Circuits Conference`. |
| `venue.short` | string | no | `JSSC`, `ISSCC`, … |
| `year` | integer | yes | |
| `month` | integer 1–12 | no | |
| `month_end` | integer, greater than `month` | no | Last month of a multi-month issue (IEEE Micro "Nov.-Dec. 2012": `month` 11, `month_end` 12). Only with `month`. *(Designer's call.)* |
| `volume`, `issue`, `pages` | string | no | `"63"`, `"3"`, `"359-369"`; strings because of values like `"PP"`. |
| `location` | string | no | Conference city. |
| `doi` | string | no | Without a URL prefix. |
| `url` | string | no | |

- Unknown fields are ignored, so other generators can add their own (for
  example a SCI(E) flag for government forms) without breaking the resume.
- `content/shared/publications.schema.json` (JSON Schema 2020-12) documents the
  same contract for other generators and for editor validation. A test keeps
  its required and known fields equal to the Python validator's.
- Validation happens on every build that includes the file. Errors:
  - syntax: `content/shared/publications.json:12: invalid JSON: <message>`
    (line from `json.JSONDecodeError`);
  - content: `content/shared/publications.json:41: tcas1-2016-kim: "month" must be 1-12`,
    where the line is that of the item's `"id"` (section 5).

## 5. The include line

```markdown
### Journal Papers
@../shared/publications.json journal {.full}

### Conference Papers (First Authored Only - 25 Papers in Total)
@../shared/publications.json conference first-author {.full}
```

- Form: `@<path>.json <type> [first-author] [{.full}|{.short}]`. `<type>` is
  required. `first-author` keeps items whose first author equals `owner`.
  The marker works as for `.md` includes.
- Any other word, a missing type, or a `.json` include without arguments is an
  error at the include line. `.md` includes are unchanged.
- Order: newest first by (`year`, `month`, items without a month last within
  their year); ties keep file order.
- Each generated line is a `Line` whose `path` is the JSON file and whose
  `lineno` is the line of that item's `"id"` key in the JSON text (1 if it
  cannot be found), with the include's variant scope. Parser errors and
  warnings then point into the JSON.

## 6. How an item prints in the resume

Two lines per item, the same shape as today's `.md` lists:

```markdown
- <title>, *<venue.name>*, vol.<volume>, no.<issue>, pp.<pages>, <date>.
  <authors>.
```

- Parts whose field is missing are left out with their label and comma.
  Journals and conferences use the same template.
- `<date>`: `<Mon> <year>`, months as `Jan. Feb. Mar. Apr. May June July Aug.
  Sept. Oct. Nov. Dec.`; `<Mon>-<Mon> <year>` with `month_end`
  (`Nov.-Dec. 2012`); only `<year>` without a month. (Today's lists mix
  `Spt.`, `Feb., 2013`, `July.`; this normalizes them. Day ranges such as
  `16-20 Spt. 2013` are dropped.)
- `<authors>`: comma-separated, `and` before the last of three or more
  (`A, B, and C`), `A and B` for two. The owner prints as written (and the
  front-matter `highlight` bolds it as today). Every other full name prints as
  initials plus family name: `Seongwook Park` → `S. Park`, `Hoi-Jun Yoo` →
  `H.-J. Yoo`, `Kyuho Jason Lee` → `K. J. Lee`. The family name is the last
  word; a name that is already abbreviated prints unchanged.
- All JSON text is escaped for the Markdown dialect before it is wrapped:
  backslash, `*`, `_`, `[`, `]`, `|` and `{` get a backslash, so a title prints
  literally and never ends in something that looks like a variant marker.
  A test round-trips every ASCII punctuation character through
  `parse_inline` and `plain_text`.
- The Korean resume prints the same English lines, as today.

## 7. Migration of the data

1. Start from the homepage JSON (10 journal, 25 conference papers) and add what
   only the resume `.md` lists have: the COOL Chips 2013 paper "A
   multi-granularity parallelism object recognition processor with
   content-aware fine-grained task scheduling" and the ESSCIRC 2013 pages.
2. Split `detail` strings into `volume`, `issue`, `pages`, `month`, `year`;
   rewrite venues in natural order with short names; derive `doi` from
   `dx.doi.org` URLs. A throwaway script does this; it is not committed.
3. Make a conflict table of every field where the two sources disagree and
   show it to the owner before committing the data. Known so far:
   - ISCAS 2010 stereo matching paper: March (resume) or May (homepage);
   - JSSC 2016 visual attention paper: early access `vol.PP, no.99, pp.1-9`,
     or its final volume and pages;
   - conference titles: Title Case (resume) or IEEE Xplore sentence case;
   - the conference total: 25 in the homepage file without the COOL Chips 2013
     paper, 25 written in the resumes with it;
   - full names for conference co-authors, known only as initials today.
   Values that neither source has (the JSSC 2016 final volume and pages,
   co-authors' full names) are looked up and shown in the table as options with
   their source; the builder never enters them unconfirmed.
4. Commit the data only after the owner settles the table. If the settled
   totals differ from the hand-written counts, correct those counts (section 2)
   in the same change. `jyp.me` is not changed.

## 8. Other changes

- `content/en/resume.md`, `content/ko/resume.md`: the two include lines change
  (section 5); `journals.md` and `conferences.md` are deleted.
- Code: `scripts/resumegen/publications.py` (load, validate, filter, sort,
  format); `source.py` dispatches `.json` includes to it.
- README: a "Publications data" section — the file, its fields, the include
  line, how to add a paper.

## 9. Acceptance criteria

- `make` builds all 12 files; `make test` passes.
- The journal and conference lists in all three formats, English and Korean,
  come from `publications.json`; `journals.md` and `conferences.md` are gone.
- The short variants (`en_short`, `ko_short`) as `.typ`, `.html` and `.docx` are
  byte-identical to `formats` (3cbe394), except the count line of section 2 if
  a total changed.
- In the full variants, the only text differences against `formats` are in the
  two publication lists and the count lines of section 2, and each one is in
  the owner-approved table or is a formatting rule of section 6.
- A syntax error, a missing required field and a bad include argument each
  fail the build with `<file>:<line>:`.
- No new Python dependency; `jyp.me` unchanged.

## 10. Designer's calls (for the owner to check)

- File location `content/shared/publications.json`, with a JSON Schema file
  next to it, and `schema`/`owner` at the top level.
- One flat list with a `type` per item instead of the homepage's groups.
- Unknown fields are ignored.
- Newest-first order computed from the dates, not file order.
- Printed format: IEEE month abbreviations, `A, B, and C` authors, co-authors
  as initials, day ranges dropped.
- `month_end` for multi-month issues.
- Hand-written counts corrected if the data changes a total.
- Talks and patents later, with the same mechanism.

## 11. Left to the builder

- The exact `id` of each item, within the pattern of section 4.
- Code structure inside `publications.py` and the tests' layout.
- How the throwaway migration script parses the `detail` strings.
