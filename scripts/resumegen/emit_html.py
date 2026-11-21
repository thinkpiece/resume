"""Turn a filtered `Document` into one self-contained HTML file.

Placeholder: the HTML writer replaces the body of emit_html().
"""

from __future__ import annotations

from .model import Document


def emit_html(doc: Document) -> str:
    """The whole HTML file, as text (the caller encodes it as UTF-8)."""
    raise NotImplementedError("the HTML writer is not built yet")
