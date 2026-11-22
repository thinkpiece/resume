"""The Markdown examples in README.md, copied as-is, give the documented result.

Each example in the README is a ```markdown (or ```json) block preceded by an
`<!-- example: NAME -->` line. The `paper` example is one item of
content/shared/publications.json.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from resumegen.emit import emit_typst  # noqa: E402
from resumegen.model import Entry, Item, Paragraph  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.source import load_lines  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

_EXAMPLE_RE = re.compile(r"^<!-- example: (\S+) -->\n```(?:markdown|json)\n(.*?)^```",
                         re.M | re.S)


def readme_examples() -> dict:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    return {name: body for name, body in _EXAMPLE_RE.findall(text)}


def publications_file(*items: str) -> str:
    """A publications.json holding the README's item examples."""
    return ('{"schema": 1, "owner": "Junyoung Park", "publications": [\n'
            + ",\n".join(items) + "]}\n")


class ReadmeExamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ex = readme_examples()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def doc(self, *names, variant=None, rel="en/resume.md"):
        root = self.write(rel, "".join(self.ex[n] for n in names))
        doc = parse(load_lines(root))
        return filter_variant(doc, variant) if variant else doc

    def test_all_examples_found(self):
        self.assertEqual(set(self.ex),
                         {"front-matter", "body", "variants", "include", "talk", "paper"})

    def test_no_annotations_after_markers(self):   # D1
        for name, body in self.ex.items():
            for line in body.splitlines():
                self.assertNotIn("←", line, f"{name}: {line}")
                for marker in ("{.full}", "{.short}"):
                    if marker in line:
                        self.assertTrue(line.rstrip().endswith(marker), f"{name}: {line}")

    def test_front_matter(self):
        m = self.doc("front-matter").meta
        self.assertEqual((m.name, m.lang, m.paper, m.fonts, m.highlight),
                         ("Junyoung Park", "en", "us-letter", ["Charter", "NanumMyeongjo"],
                          "Junyoung Park"))
        self.assertEqual([k for k, _ in m.contacts],
                         ["location", "phone", "email", "homepage", "linkedin", "github"])

    def test_body(self):
        doc = self.doc("front-matter", "body")
        self.assertEqual(doc.warnings, [])
        self.assertEqual([s.title for s in doc.sections],
                         ["Work Experience", "Journal Papers", "Summary"])
        work, papers, summary = doc.sections
        e = work.children[0]
        self.assertIsInstance(e, Entry)
        self.assertEqual((e.title, e.date, e.subtitle, e.side),
                         ("UX Factory, Inc.", "Aug. 2015 - Present",
                          "Co-founder and Chief Executive Officer", "Seoul"))
        self.assertEqual([(i.text, i.date) for i in e.items],
                         [("Founded a company that delivers AI solutions", None),
                          ("Gave a keynote", "Dec. 2025")])
        p = papers.children[0]
        self.assertIsInstance(p, Item)
        self.assertEqual(p.details, ["S. Park, Junyoung Park, H.-J. Yoo.",
                                     "- presented and demonstrated at ISSCC"])
        self.assertEqual(len(summary.children), 1)
        self.assertIsInstance(summary.children[0], Paragraph)
        self.assertEqual(summary.children[0].text,
                         "A plain line directly under a section is a paragraph.")

    def _variant_table(self, variant):
        doc = self.doc("front-matter", "variants", variant=variant)
        return {s.title: [c.text for c in s.children] for s in doc.sections}

    def test_variants_full(self):
        self.assertEqual(self._variant_table("full"), {
            "Awards": ["Best Paper Award", "Eun Jong-Kwan Scholarship Award"],
            "Activities": ["Technical Program Committee, ISSCC"],
            "Invited Talks": ["AI Semiconductor Strategies, *Kyung Hee University*, Nov., 2024."],
        })

    def test_variants_short(self):
        self.assertEqual(self._variant_table("short"), {
            "Awards": ["Best Paper Award"],
            "Activities": ["Over 20 invited talks on AI semiconductors.",
                           "Technical Program Committee, ISSCC"],
            "Research Output": ["10 journal and 25 conference papers, 18 registered patents"],
        })

    def test_include_and_shared_paper(self):
        self.write("shared/publications.json", publications_file(self.ex["paper"]))
        full = self.doc("front-matter", "include", variant="full")
        self.assertEqual([s.title for s in full.sections], ["Publications"])
        entry = full.sections[0].children[0]
        self.assertEqual(entry.title, "Journal Papers")
        self.assertEqual([(i.text, i.details) for i in entry.items], [(
            "Title of the Paper, *IEEE Journal of Solid-State Circuits*, vol.1, pp.1-10, "
            "Jan. 2026.",
            ["A. Kim, Junyoung Park, and B. Lee."])])
        self.assertIn('#hl("Junyoung Park")', emit_typst(full))
        self.assertEqual(self.doc("front-matter", "include", variant="short").sections, [])

    def test_talk(self):
        self.write("shared/talks.md", self.ex["talk"])
        self.write("en/resume.md", self.ex["front-matter"] + "## Talks\n@../shared/talks.md\n")
        doc = parse(load_lines(self.d / "en" / "resume.md"))
        self.assertEqual([i.text for i in doc.sections[0].children],
                         ["Title of the Talk, *Venue Name*, Dec., 2026."])

    @unittest.skipUnless(shutil.which("typst"), "typst is not installed")
    def test_examples_build_pdfs(self):
        root = self.d / "repo"
        template = REPO / "template"
        if (template / "resume.typ").exists():
            shutil.copytree(template, root / "template")
        else:
            (root / "template").mkdir(parents=True)
            shutil.copy(REPO / "tests" / "fixtures" / "cli" / "stub_template.typ",
                        root / "template" / "resume.typ")
        (root / "content" / "shared").mkdir(parents=True)
        (root / "content" / "shared" / "publications.json").write_text(
            publications_file(self.ex["paper"]), encoding="utf-8")
        (root / "content" / "en").mkdir()
        src = root / "content" / "en" / "resume.md"
        src.write_text("".join(self.ex[n] for n in ("front-matter", "body", "variants", "include")),
                       encoding="utf-8")
        env = dict(os.environ, RESUME_ROOT=str(root))
        for variant in ("full", "short"):
            with self.subTest(variant=variant):
                out = root / "build" / f"readme_{variant}.pdf"
                r = subprocess.run([sys.executable, str(REPO / "scripts" / "build_resume.py"),
                                    str(src), "--variant", variant, "-o", str(out)],
                                   capture_output=True, text=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stderr, "")
                self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
