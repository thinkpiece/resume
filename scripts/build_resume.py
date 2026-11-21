#!/usr/bin/env python3
"""Build one resume PDF from a Markdown source.

    python3 scripts/build_resume.py content/en/resume.md --variant full \
        -o build/Resume_JunyoungPark_en_full.pdf

Pipeline: read Markdown (with @includes) -> parse -> keep one variant ->
write <root>/build/<OUT stem>.typ -> typst compile -> check the page count.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from resumegen import ResumeError  # noqa: E402
from resumegen.emit import emit_typst  # noqa: E402
from resumegen.model import VARIANTS  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

# macOS on-demand fonts (e.g. NanumMyeongjo) live here; Typst finds them only
# when each folder is passed with --font-path.
FONT_DIR_GLOB = "/System/Library/AssetsV2/com_apple_MobileAsset_Font*"

_UNKNOWN_FONT_RE = re.compile(r"unknown font family: ([^\n]+)")


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


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="build_resume.py",
        description="Build a resume PDF from Markdown through Typst.")
    ap.add_argument("src", help="root Markdown file, e.g. content/en/resume.md")
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS),
                    help="which variant to build")
    ap.add_argument("-o", "--output", type=Path,
                    help="output PDF (default: <root>/build/<src stem>_<variant>.pdf)")
    ap.add_argument("--typ-only", action="store_true",
                    help="write the .typ file only; do not run Typst")
    args = ap.parse_args(argv)
    if args.output is not None and args.output.suffix.lower() != ".pdf":
        ap.error(f"output must end in .pdf: {args.output}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = repo_root()
    out = args.output or root / "build" / f"{Path(args.src).stem}_{args.variant}.pdf"
    # Typst only reads sources under --root, so the .typ always goes there.
    typ = root / "build" / f"{out.stem}.typ"
    # Remove the old PDF first, so a failed run never leaves one behind.
    if out.exists():
        out.unlink()

    try:
        doc = filter_variant(parse(load_lines(Path(args.src))), args.variant)
    except ResumeError as e:
        print(e, file=sys.stderr)
        return 1
    for w in doc.warnings:
        print(f"warning: {w}", file=sys.stderr)

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
        print(f"error: typst could not compile {typ}", file=sys.stderr)
        return 1

    unknown = [name.strip() for name in _UNKNOWN_FONT_RE.findall(r.stderr)]
    if unknown:
        if out.exists():
            out.unlink()
        names = ", ".join(f"'{n}'" for n in unknown)
        print(f"error: Typst could not find font {names} (used by the template)",
              file=sys.stderr)
        return 1

    if args.variant == "short":
        pages = count_pdf_pages(out)
        if pages > 1:
            print(f"warning: short variant has {pages} pages: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
