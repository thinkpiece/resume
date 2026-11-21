"""Turn a filtered `Document` into a Word document (.docx).

Placeholder: the DOCX writer replaces the body of emit_docx().
"""

from __future__ import annotations

from .model import Document


def emit_docx(doc: Document) -> bytes:
    """The whole .docx file (a ZIP package), as bytes."""
    raise NotImplementedError("the DOCX writer is not built yet")
