"""Read resume Markdown files: normalize, strip comments, resolve @includes.

An "@<file>.json ..." include stands for lines that publications.py formats
from the JSON file; they keep the JSON file's path and item line numbers.

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
from .publications import MALFORMED_INCLUDE, include_lines

INCLUDE_RE = re.compile(r"^@(\S+\.md)(?:\s+\{\.(full|short)\})?\s*$")

# "@<path>.json <words> [{.full}|{.short}]" (publications spec §5). The path
# may hold braces; the words are checked by publications.include_lines.
JSON_INCLUDE_RE = re.compile(
    r"^@(\S*\.json)((?:\s+[^\s{]+)*)(?:\s+\{\.(full|short)\})?\s*$")
# A first word that ends in ".json", or in ".json{..." (a glued marker): a .json
# include attempt, which must then fit JSON_INCLUDE_RE (clarification 17).
_JSON_ATTEMPT_RE = re.compile(r"^@\S*\.json(?:\{\S*)?(?:\s|$)")

# "@path.md{.full}": an include whose marker is glued to the path.
_GLUED_INCLUDE_RE = re.compile(r"^@\S+\.md\{[^{}]*\}\s*$")
_TRAILING_BRACES_RE = re.compile(r"\{([^{}]*)\}$")

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
        if _JSON_ATTEMPT_RE.match(text):
            m = JSON_INCLUDE_RE.match(text)
            if not m:
                raise at(line, MALFORMED_INCLUDE)
            target = Path(os.path.normpath(path.parent / m.group(1)))
            sub_scope = scope & frozenset({m.group(3)}) if m.group(3) else scope
            out.extend(include_lines(target, m.group(2).split(), line, sub_scope))
            continue
        if text.startswith("@"):
            stripped = text.rstrip()
            if _GLUED_INCLUDE_RE.match(stripped):
                raise at(line, "put a space between the include path and its marker")
            found = trailing_marker(stripped)
            if found and found[1] is None:
                raise at(line, invalid_marker_message(stripped[found[0]:]))
        out.append(line)
    return out


def trailing_marker(text: str) -> tuple[int, str | None] | None:
    """Find a variant marker attempt at the end of `text` (already rstripped).

    Returns None when the text does not end in a marker attempt, else
    (start index of "{", variant) where variant is "full"/"short" for a valid
    marker and None for an invalid attempt. A trailing "{...}" is an attempt
    when its content, with spaces removed, starts with "." or equals
    full/short in any letter case. An escaped "\\{" never starts one.
    """
    m = _TRAILING_BRACES_RE.search(text)
    if not m or _escaped(text, m.start()):
        return None
    inner = "".join(m.group(1).split())
    if not (inner.startswith(".") or inner.lower() in ("full", "short")):
        return None
    if m.group(1) in (".full", ".short"):
        return m.start(), m.group(1)[1:]
    return m.start(), None


def invalid_marker_message(bad: str) -> str:
    return f"invalid variant marker '{bad}'; write {{.full}} or {{.short}}"


def _escaped(text: str, i: int) -> bool:
    """True when text[i] is preceded by an odd number of backslashes."""
    n = 0
    while i - n - 1 >= 0 and text[i - n - 1] == "\\":
        n += 1
    return n % 2 == 1


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
