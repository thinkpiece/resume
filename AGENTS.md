# AGENTS.md

Instructions for any coding agent in this repository, whether it works alone
or leads a team. Codex reads this file directly; Claude Code reads it through
`CLAUDE.md`, which only imports it, so edit this one. Point any other agent to
this file through its own instruction mechanism. `README.md` is the user
manual: read the parts your task touches.

## The project

The owner's resume, written in `content/` as Markdown plus one JSON data file.
`scripts/build_resume.py` builds it into twelve files: English and Korean, full
and short variants, each as a PDF (through Typst), a self-contained HTML page
and a DOCX. README "Folder layout", "Build" and "Prerequisites" cover the files
and commands; the code is laid out like this:

| Path | What it holds |
|---|---|
| `scripts/resumegen/source.py` | Reads files, strips comments, resolves `@file.md` and `@file.json <type>` includes |
| `scripts/resumegen/publications.py` | Loads, validates and formats `content/shared/publications.json` |
| `scripts/resumegen/parse.py`, `variants.py`, `model.py` | Markdown dialect to `Document`; the full/short filter |
| `scripts/resumegen/render.py` | Shared by all writers: inline Markdown, `LOOK` (sizes, gray), `PAGE_MARGINS_IN`, `PAPER_SIZES_MM` |
| `scripts/resumegen/emit.py`, `emit_html.py`, `emit_docx.py` | Typst, HTML and DOCX writers |
| `template/resume.typ` | PDF layout |
| `tests/` | `unittest` suite; `test_readme.py` builds the README's `<!-- example: … -->` blocks, `test_render.py` checks `LOOK` against the template |
| `docs/superpowers/` | Designs (`specs/`) and plans (`plans/`) of larger changes; read the one for the area you change, when there is one |

`make test` must pass before any claim of done; `make` builds all twelve files
into `build/` (git-ignored, never committed).

## Rules from the owner

Every agent and every team member follows these. Put them into any brief you
give a member.

- **No new dependency without asking.** The resume build uses the Python
  standard library and `typst` (for the PDF). Ask the owner before adding any
  package, tool or service. (`scripts/publication_formatter.py`, a separate
  BibTeX helper, imports `bibtexparser`; the build never imports it.)
- **English** in code, comments, docstrings, messages, commit messages and
  docs. The Korean text in `content/ko/` is intended; keep it. Talk with the
  owner in the language they write in (usually Korean).
- **Privacy.** Never put the owner's email, phone, address or other personal
  details into a web search, API call, URL or header. Look papers up by DOI or
  title, send a generic User-Agent such as `resume-publications-check/1.0`,
  and leave out contact parameters (`mailto=` and the like). The repository is
  public: add no personal data beyond what `content/` and the README already
  show, and no tokens or local secrets.
- **Git.** Work on a branch, not on `master`. Push, merge into `master` or
  rewrite pushed history only when the owner asks.
- **The owner's uncommitted edits.** Run `git status` before you start.
  Changes you did not make are the owner's: never stash, reset, overwrite or
  commit them. Commit only files whose changes are all yours, with
  `git add <paths> && git commit -m "<msg>" -- <paths>`. If your task must
  change a file that already holds such edits, ask the owner first: a commit
  of that file would carry their edits too.
- **Read-only elsewhere.** `~/workspace/jyp.me` (the homepage, which still
  keeps its own copy of the publication data) is read-only from here. Write
  outside this folder only where the task says so.
- **Errors** at a source line read `<path>:<line>: <message>`. Raise
  `at(line, message)` from `resumegen/errors.py` when a `Line` is available;
  otherwise follow the existing messages in `source.py` (Markdown files) and
  `publications.py` (JSON). A malformed line is an error, never printed text.

## Changing things

- **Content** changes touch only `content/`. The resume's wording is the
  owner's: change only what the task asks for.
- **Layout.** A change meant for all three formats goes into
  `template/resume.typ` and the matching settings in `render.py` or in the
  HTML and DOCX writers. A fix for one format changes only that format's files
  (for the PDF, `template/resume.typ` or `emit.py`) and checks that format.
- **Behavior.** Update the README in the same change; its examples are tests.
- **Output comparison.** Note the starting commit. When output should not
  change (a refactor, a parser change), build both the starting and the
  finished commit from clean copies (`git archive <commit> | tar -x -C <dir>`,
  then `make` there), so that uncommitted edits in the working folder count
  for neither side. Compare each variant's `.typ`, `.html` and `.docx` with
  `cmp` (the DOCX writer fixes ZIP timestamps, so equal input gives equal
  bytes) and explain every difference. When output should change, the same
  comparison shows which files changed; then look at the change itself. A
  template change leaves every `.typ` file equal, so compare the rendered PDF
  pages (`pdftotext`, or images of the pages); for a DOCX, compare the changed
  XML parts inside the ZIP.
- **Paper counts are written by hand** in three places per language, six in
  all. After adding, removing or reclassifying a paper, check all six and edit
  those that changed:
  - the Summary bullet: all papers;
  - the Conference Papers heading: all conference papers, although the list
    under it shows only first-authored ones;
  - the short variant's Research Output bullet: journal and conference
    papers separately.

## Publication data

`publications.json` will later move to a central place and feed the homepage
and other generators, so:

- Write strict standard JSON (no `NaN`, no comments) and keep every text
  field on one line. README "Publications data" says what the loader checks.
- An `id` never changes once written; other tools key on it.
- Never write a value that no source supports. When the resume, the homepage
  and the web disagree, or a value comes only from the web, check it on the
  web and give it to the owner as a labeled proposal; write it once the owner
  accepts.
- Save the text of every page or API response you rely on as
  `research/publications/<id>-<source>.<ext>`. Crossref, Semantic Scholar,
  OpenAlex and PubMed answered automated requests; DBLP and IEEE Xplore
  refused them (November 2026).
- `research/` and `.worktrees/` stay out of Git through the local exclude
  file; a fresh clone needs the two patterns added. Before using either, run
  `git check-ignore research/x .worktrees/x`; for a path it does not print,
  add `/research/` or `/.worktrees/` to the file that
  `git rev-parse --git-path info/exclude` names.

## How a change goes

1. Read the code and the README part you touch. Check the branch and
   `git status`, and note the starting commit.
2. A new feature or format: write a short design
   (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) and a plan
   (`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`), and get the owner's
   approval before building. A small fix needs only clear acceptance
   criteria.
3. Write the test first where behavior changes. Run `make test` and `make`
   before you call it done.
4. Report to the owner: what changed, the commits, the checks you ran and
   their results, and what is left or uncertain. Opening a changed DOCX in
   Word or Pages is the owner's check: ask for it.

## Leading a team

The lead may be Claude Code or Codex. With the cmux team kit (started with
`cmux-agents claude` or `cmux-agents codex`), the lead receives the kit's
instructions and team notes and uses the `cmux-team` command; follow them.
This section adds what is specific to this repository. Without the kit, work
alone or with your agent's own subagents and do the checks of "How a change
goes" yourself; the rest of this file still applies.

- **When a team pays.** One file, or steps that wait on each other: no team.
  Seams where members can work at once without sharing a file:
  - one writer each: Typst (`emit.py`, `template/`), HTML (`emit_html.py`),
    DOCX (`emit_docx.py`);
  - code (`scripts/`, `tests/`, README) apart from data
    (`content/shared/*.json`, `research/`);
  - a decision others build on (the inline model in `render.py`, the include
    grammar in `source.py`, the JSON schema) is its own task that comes first.
- **Brief file first.** Before the first member starts, write one brief in the
  team files folder: the spec and plan paths or the acceptance criteria, the
  owner's rules above, each member's scope, and what counts as done. Later
  rule changes go at its end as numbered clarifications; tell every member.
- **Verification** is its own task, for a member started for it from a
  provider that built none of the work under check: Codex builders get a
  Claude verifier and the other way round, whichever agent leads. If no such
  provider is available, tell the owner which check is still open. Give the
  verifier the spec or acceptance criteria while the builders build. It works
  read-only in its own detached worktree (`.worktrees/verify-<topic>`), which
  the lead moves to each commit to check.
- **Git.** The lead owns branches and merges. Members whose files don't
  overlap share the project folder and commit only their own paths; a member
  that needs isolation gets a worktree under `.worktrees/`. A done message
  names the commit id that the member's own `git commit` printed (on a shared
  branch `git log -1` may already show a teammate's commit); a review names
  the commit it reviewed. Check the commit and its changed paths before
  relaying it.
- **Owner decisions** (data values, dependencies, pushing, design approval) go
  to the owner as labeled proposals with a machine-readable list, so the owner
  can answer by label.
- **Dialogs** (a Codex member's sandbox approval, a trust prompt, opening a
  file in Word or Pages) are the owner's to answer. Tell the owner and go on.
- **The last check is the lead's.** On the integrated branch, run `make test`
  and `make` yourself and the output comparison above, then report.
