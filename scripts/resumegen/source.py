"""Read resume Markdown files: normalize, strip comments, resolve @includes.

The result is a flat list of `Line`s. Every line remembers the file and line
number that physically hold it, and the variants its enclosing `@include`
markers allow.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .errors import ResumeError, at
from .model import VARIANTS, Line

INCLUDE_RE = re.compile(r"^@(\S+\.md)(?:\s+\{\.(full|short)\})?\s*$")

# A line that starts like an include ("@something.md") but is not a valid one.
_INCLUDE_ATTEMPT_RE = re.compile(r"^@\S+\.md(?:\s|$)")

# A trailing "{...}" that looks like an attempt to write a variant marker,
# e.g. "{.ful}", "{full}", "{ .full }", "{.Full}".
MARKER_ATTEMPT_RE = re.compile(r"\{\s*\.?\s*[A-Za-z]+\s*\}$")
MARKER_RE = re.compile(r"\s\{\.(full|short)\}$")

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def load_lines(root: Path) -> list[Line]:
    """Load `root` and everything it includes as a flat list of lines."""
    root = Path(os.path.normpath(root))
    base = root.resolve().parent
    return _load(root, VARIANTS, chain=[], base=base, include_line=None)


def _load(path: Path, scope: frozenset[str], chain: list[Path], base: Path,
          include_line: Line | None) -> list[Line]:
    resolved = path.resolve()
    if resolved in chain:
        names = [_display(p, base) for p in chain + [resolved]]
        raise at(include_line, "include cycle: " + " -> ".join(names))
    texts = _read(path, include_line)
    chain = chain + [resolved]

    out: list[Line] = []
    for i, text in enumerate(texts, start=1):
        line = Line(text=text, path=path, lineno=i, scope=scope)
        if include_line is not None and i == 1 and text.rstrip() == "---":
            raise at(line, "front matter is only allowed in the root file")
        m = INCLUDE_RE.match(text)
        if m:
            target = Path(os.path.normpath(path.parent / m.group(1)))
            sub_scope = scope & frozenset({m.group(2)}) if m.group(2) else scope
            out.extend(_load(target, sub_scope, chain, base, include_line=line))
            continue
        if _INCLUDE_ATTEMPT_RE.match(text):
            rest = text.rstrip()
            if MARKER_ATTEMPT_RE.search(rest):
                bad = MARKER_ATTEMPT_RE.search(rest).group(0)
                raise at(line, f"invalid variant marker '{bad}'; "
                               "use {.full} or {.short}")
            raise at(line, "invalid include line; expected '@path.md' "
                           "optionally followed by {.full} or {.short}")
        out.append(line)
    return out


def _read(path: Path, include_line: Line | None) -> list[str]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        if include_line is None:
            raise ResumeError(f"{path}: file not found") from None
        raise at(include_line, f"included file not found: {path}") from None
    except OSError as e:
        where = f"{path}" if include_line is None else \
            f"{include_line.path}:{include_line.lineno}"
        raise ResumeError(f"{where}: cannot read {path}: {e.strerror}") from None

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        offset = e.start
        lineno = data.count(b"\n", 0, offset) + 1
        raise ResumeError(f"{path}:{lineno}: invalid UTF-8 text") from None

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_comments(text, path)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [l.expandtabs(4) for l in lines]


def _strip_comments(text: str, path: Path) -> str:
    """Remove <!-- ... --> spans, keeping the newlines they contained."""
    text = _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    start = text.find("<!--")
    if start != -1:
        lineno = text.count("\n", 0, start) + 1
        raise ResumeError(f"{path}:{lineno}: unclosed comment '<!--'")
    return text


def _display(p: Path, base: Path) -> str:
    return os.path.relpath(p, base)
