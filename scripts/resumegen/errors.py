"""Error type shared by every stage of the resume generator."""


class ResumeError(Exception):
    """A problem in the resume sources, reported as "<path>:<line>: <message>"."""


def at(line, message: str) -> ResumeError:
    """Build a ResumeError located at a `Line` (anything with .path and .lineno)."""
    return ResumeError(f"{line.path}:{line.lineno}: {message}")
