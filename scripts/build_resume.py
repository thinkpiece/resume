#!/usr/bin/env python3
"""Build one resume as PDF, HTML or DOCX from a Markdown source.

    python3 scripts/build_resume.py content/en/resume.md --variant full \
        -o build/Resume_JunyoungPark_en_full.pdf

The extension of -o picks the format: .pdf, .html or .docx.

Pipeline: read Markdown (with @includes) -> parse -> keep one variant ->
  PDF:        write <root>/build/<OUT stem>.typ -> typst compile -> check the page count
  HTML, DOCX: write OUT directly (no Typst needed)
The repo root (Typst --root) is this script's parent folder, or RESUME_ROOT.
Python standard library only.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from resumegen import ResumeError  # noqa: E402
from resumegen.emit import emit_typst  # noqa: E402
from resumegen.emit_docx import emit_docx  # noqa: E402
from resumegen.emit_html import emit_html  # noqa: E402
from resumegen.model import VARIANTS  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

# macOS on-demand fonts (e.g. NanumMyeongjo) live here; Typst finds them only
# when each folder is passed with --font-path.
FONT_DIR_GLOB = "/System/Library/AssetsV2/com_apple_MobileAsset_Font*"

_UNKNOWN_FONT_RE = re.compile(r"unknown font family: ([^\n]+)")

# Output format by the extension of -o (compared case-insensitively).
FORMATS = {".pdf": "pdf", ".html": "html", ".docx": "docx"}


def output_format(path: Path) -> str | None:
    """"pdf", "html" or "docx" for an output path; None for any other extension."""
    return FORMATS.get(path.suffix.lower())


def repo_root() -> Path:
    env = os.environ.get("RESUME_ROOT")
    return Path(env).resolve() if env else Path(__file__).resolve().parent.parent


def font_paths() -> list[str]:
    return [d for d in sorted(glob.glob(FONT_DIR_GLOB)) if os.path.isdir(d)]


def typst_font_flags() -> list[str]:
    flags: list[str] = []
    for d in font_paths():
        flags += ["--font-path", d]
    return flags


def missing_fonts(typst: str, fonts: list[str]) -> list[str]:
    """Fonts from `fonts` that `typst fonts` does not list (case-insensitive).

    Returns [] when `typst fonts` itself fails; the compile step still turns
    Typst's "unknown font family" warning into an error.
    """
    r = subprocess.run([typst, "fonts", *typst_font_flags()], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return []
    known = {line.strip().lower() for line in r.stdout.splitlines() if line.strip()}
    return [f for f in fonts if f.lower() not in known]


def count_pdf_pages(pdf: Path, use_pdfinfo: bool = True) -> int:
    """Number of pages in `pdf`, via pdfinfo when available."""
    pdfinfo = shutil.which("pdfinfo") if use_pdfinfo else None
    if pdfinfo:
        r = subprocess.run([pdfinfo, str(pdf)], capture_output=True, text=True)
        m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.MULTILINE)
        if r.returncode == 0 and m:
            return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", pdf.read_bytes()))


def _remove(path: Path) -> None:
    # unlink, not exists(): a dangling symlink at the output path goes too.
    path.unlink(missing_ok=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="build_resume.py",
        description="Build a resume as PDF (through Typst), HTML or DOCX from Markdown.")
    ap.add_argument("src", help="root Markdown file, e.g. content/en/resume.md")
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS),
                    help="which variant to build")
    ap.add_argument("-o", "--output", type=Path,
                    help="output file; its extension picks the format: .pdf, .html or "
                         ".docx (default: <root>/build/<src stem>_<variant>.pdf)")
    ap.add_argument("--typ-only", action="store_true",
                    help="PDF only: write the .typ file; do not run Typst")
    args = ap.parse_args(argv)
    if args.output is None:
        args.format = "pdf"
    else:
        args.format = output_format(args.output)
        if args.format is None:
            ap.error(f"output must end in .pdf, .html or .docx: {args.output}")
    if args.typ_only and args.format != "pdf":
        ap.error(f"--typ-only works only with PDF output: {args.output}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = repo_root()
    out = args.output or root / "build" / f"{Path(args.src).stem}_{args.variant}.pdf"
    # Typst only reads sources under --root, so the .typ always goes there.
    typ = root / "build" / f"{out.stem}.typ"
    # Remove the old output first, so a failed build never leaves one behind.
    # --typ-only produces no PDF, so it leaves the output path alone.
    if not args.typ_only:
        _remove(out)

    try:
        doc = filter_variant(parse(load_lines(Path(args.src))), args.variant)
    except ResumeError as e:
        print(e, file=sys.stderr)
        return 1
    for w in doc.warnings:
        print(f"warning: {w}", file=sys.stderr)

    if args.format != "pdf":
        return _write_document(doc, args.format, out)

    typ.parent.mkdir(parents=True, exist_ok=True)
    typ.write_text(emit_typst(doc), encoding="utf-8")
    if args.typ_only:
        return 0

    typst = shutil.which("typst")
    if typst is None:
        print("error: typst not found; install it with: brew install typst", file=sys.stderr)
        return 1

    missing = missing_fonts(typst, doc.meta.fonts)
    if missing:
        line = doc.meta.origins["font"]
        names = ", ".join(f"'{f}'" for f in missing)
        print(f"{line.path}:{line.lineno}: font not found: {names}; "
              "`typst fonts` lists the fonts Typst can use", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [typst, "compile", "--root", str(root), *typst_font_flags(), str(typ), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        _remove(out)   # Typst may have written part of a PDF before failing
        print(f"error: typst could not compile {typ}", file=sys.stderr)
        return 1

    unknown = [name.strip() for name in _UNKNOWN_FONT_RE.findall(r.stderr)]
    if unknown:
        _remove(out)
        names = ", ".join(f"'{n}'" for n in unknown)
        print(f"error: Typst could not find font {names} (used by the template)",
              file=sys.stderr)
        return 1

    if args.variant == "short":
        pages = count_pdf_pages(out)
        if pages > 1:
            print(f"warning: short variant has {pages} pages: {out}", file=sys.stderr)
    return 0


def _write_document(doc, fmt: str, out: Path) -> int:
    """Write the HTML or DOCX file for `doc` at `out`."""
    data = emit_html(doc).encode("utf-8") if fmt == "html" else emit_docx(doc)
    # Write a uniquely named sibling file and rename it, so an interrupted
    # write never leaves part of a file at the output path.
    tmp: Path | None = None
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
        tmp = Path(name)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        tmp.chmod(0o666 & ~_umask())   # mkstemp makes 0600; give the usual mode
        os.replace(tmp, out)
    except OSError as e:
        if tmp is not None:
            _remove(tmp)
        print(f"error: could not write {out}: {e.strerror or e}", file=sys.stderr)
        return 1
    return 0


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


if __name__ == "__main__":
    sys.exit(main())
