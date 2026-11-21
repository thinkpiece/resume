import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_resume.py"
FIXTURES = REPO / "tests" / "fixtures" / "cli"
REAL_TEMPLATE_DIR = REPO / "template"

sys.path.insert(0, str(REPO / "scripts"))
import build_resume  # noqa: E402


class CliTestBase(unittest.TestCase):
    """Each test gets a temporary repo root holding a template/ folder.

    The real template is used when template/resume.typ exists; until then the
    stub in tests/fixtures/cli/ stands in for it. RESUME_ROOT points the CLI
    at the temporary root, so nothing is written inside the repository.
    """

    real_template = True   # False: always use the stub

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        if self.real_template and (REAL_TEMPLATE_DIR / "resume.typ").exists():
            shutil.copytree(REAL_TEMPLATE_DIR, self.root / "template")
        else:
            (self.root / "template").mkdir()
            shutil.copy(FIXTURES / "stub_template.typ", self.root / "template" / "resume.typ")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, src, *args, path=None):
        env = dict(os.environ, RESUME_ROOT=str(self.root))
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(SCRIPT), str(src), *args],
                              capture_output=True, text=True, env=env, cwd=self.root)

    def write_src(self, body, fm="---\nname: Test Person\n---\n", name="src.md"):
        p = self.root / name
        p.write_text(fm + body, encoding="utf-8")
        return p


@unittest.skipUnless(shutil.which("typst"), "typst is not installed")
class CliBuildTest(CliTestBase):
    def test_builds_pdf(self):
        out = self.root / "build" / "Fixture_full.pdf"
        r = self.run_cli(FIXTURES / "resume.md", "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertTrue(out.exists())
        typ = self.root / "build" / "Fixture_full.typ"
        self.assertTrue(typ.exists())
        self.assertIn('#section([#"Publications"])[', typ.read_text(encoding="utf-8"))
        if shutil.which("pdftotext"):
            text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True,
                                  text=True).stdout
            for needle in ["Example, Inc.", "은종관 장학상", "54 μW", "snake_case_words",
                           "R&D 100% #1 $5 @x <y> ~z", "escaped | pipe", "Long-only bullet"]:
                self.assertIn(needle, text)
            self.assertNotIn("Short-only summary line", text)

    def test_short_variant(self):
        out = self.root / "build" / "Fixture_short.pdf"
        r = self.run_cli(FIXTURES / "resume.md", "--variant", "short", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        typ = (self.root / "build" / "Fixture_short.typ").read_text(encoding="utf-8")
        self.assertIn("Short-only summary line", typ)
        self.assertNotIn("Long-only bullet", typ)
        self.assertNotIn("Publications", typ)
        self.assertNotIn("Old Lab", typ)

    @unittest.skipUnless(shutil.which("pdffonts"), "pdffonts is not installed")
    def test_hangul_fallback_font_is_embedded(self):   # clarification 1
        out = self.root / "build" / "Fixture_full.pdf"
        r = self.run_cli(FIXTURES / "resume.md", "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        fonts = subprocess.run(["pdffonts", str(out)], capture_output=True, text=True).stdout
        self.assertIn("Charter", fonts)
        self.assertIn("NanumMyeongjo", fonts)

    def test_default_output_path(self):
        src = self.write_src("## S\n- x\n", name="cv.md")
        r = self.run_cli(src, "--variant", "short")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "build" / "cv_short.pdf").exists())
        self.assertTrue((self.root / "build" / "cv_short.typ").exists())

    def test_output_outside_root(self):   # clarification 7
        with tempfile.TemporaryDirectory() as other:
            out = Path(other) / "deep" / "Out.pdf"
            r = self.run_cli(FIXTURES / "resume.md", "--variant", "full", "-o", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.exists())
            self.assertFalse((Path(other) / "deep" / "Out.typ").exists())
            self.assertTrue((self.root / "build" / "Out.typ").exists())

    def test_short_page_warning(self):
        body = "## Many\n" + "".join(f"- bullet number {i}\n" for i in range(120))
        out = self.root / "build" / "long_short.pdf"
        r = self.run_cli(self.write_src(body), "--variant", "short", "-o", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stderr, r"warning: short variant has ([2-9]|\d\d+) pages")
        self.assertTrue(out.exists())

    def test_short_page_warning_without_pdfinfo(self):
        bindir = self.root / "bin"
        bindir.mkdir()
        (bindir / "typst").symlink_to(shutil.which("typst"))
        body = "## Many\n" + "".join(f"- bullet number {i}\n" for i in range(120))
        r = self.run_cli(self.write_src(body), "--variant", "short", path=str(bindir))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stderr, r"warning: short variant has ([2-9]|\d\d+) pages")

    def test_full_variant_never_warns_about_pages(self):
        body = "## Many\n" + "".join(f"- bullet number {i}\n" for i in range(120))
        r = self.run_cli(self.write_src(body), "--variant", "full")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("pages", r.stderr)

    def test_unknown_font_fails(self):   # clarification 2, D2
        out = self.root / "build" / "font.pdf"
        src = self.write_src("## S\n- x\n", fm="---\nname: N\nfont: NoSuchFont123, Charter\n---\n")
        r = self.run_cli(src, "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith(f"{src}:3: "), r.stderr)
        self.assertIn("'NoSuchFont123'", r.stderr)
        self.assertNotIn("unknown font family", r.stderr)   # caught before Typst compiles
        self.assertFalse(out.exists())

    def test_unknown_fallback_font_fails(self):
        src = self.write_src("## S\n- x\n",
                             fm="---\nname: N\nlang: en\nfont: Charter, NoSuchFallback9\n---\n")
        r = self.run_cli(src, "--variant", "full")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith(f"{src}:4: "), r.stderr)
        self.assertIn("'NoSuchFallback9'", r.stderr)
        self.assertNotIn("'Charter'", r.stderr)

    def test_font_names_match_case_insensitively(self):
        src = self.write_src("## S\n- x\n", fm="---\nname: N\nfont: charter\n---\n")
        r = self.run_cli(src, "--variant", "full")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")

    def test_default_font_error_points_at_front_matter_start(self):
        # Hide every font from Typst, so even the default Charter is missing.
        env_root = self.root / "bin"
        env_root.mkdir()
        wrapper = env_root / "typst"
        wrapper.write_text(f"#!/bin/sh\nTYPST_IGNORE_SYSTEM_FONTS=true TYPST_IGNORE_EMBEDDED_FONTS=true "
                           f"exec {shutil.which('typst')} \"$@\"\n")
        wrapper.chmod(0o755)
        src = self.write_src("## S\n- x\n")
        r = self.run_cli(src, "--variant", "full", path=f"{env_root}:/usr/bin:/bin")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith(f"{src}:1: "), r.stderr)
        self.assertIn("'Charter'", r.stderr)

    def test_unknown_template_font_fails(self):   # clarification 2
        stub = (FIXTURES / "stub_template.typ").read_text(encoding="utf-8")
        broken = stub.replace("set text(font: fonts,", 'set text(font: ("NoTemplateFont7",) + fonts,')
        self.assertNotEqual(stub, broken)
        (self.root / "template" / "resume.typ").write_text(broken, encoding="utf-8")
        out = self.root / "build" / "tf.pdf"
        r = self.run_cli(self.write_src("## S\n- x\n"), "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertRegex(r.stderr, r"(?m)^error: Typst could not find font 'notemplatefont7'")
        self.assertFalse(out.exists())

    def test_stale_pdf_removed_when_font_check_fails(self):   # D3
        out = self.root / "build" / "stale.pdf"
        out.parent.mkdir()
        out.write_bytes(b"%PDF-old")
        src = self.write_src("## S\n", fm="---\nname: N\nfont: NoSuchFont123\n---\n")
        r = self.run_cli(src, "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(out.exists())

    def test_stale_pdf_removed_when_build_fails(self):
        out = self.root / "build" / "stale.pdf"
        out.parent.mkdir()
        out.write_bytes(b"%PDF-old")
        (self.root / "template" / "resume.typ").write_text("#let resume = 1 +\n", encoding="utf-8")
        r = self.run_cli(self.write_src("## S\n- x\n"), "--variant", "full", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertRegex(r.stderr, r"(?m)^error: typst could not compile")
        self.assertFalse(out.exists())


@unittest.skipUnless(shutil.which("typst"), "typst is not installed")
class CliStubTemplateTest(CliTestBase):
    """The stub must keep matching the template API, whatever the real template does."""

    real_template = False

    def test_fixture_builds_with_stub(self):
        for variant in ("full", "short"):
            with self.subTest(variant=variant):
                out = self.root / "build" / f"stub_{variant}.pdf"
                r = self.run_cli(FIXTURES / "resume.md", "--variant", variant, "-o", out)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stderr, "")
                self.assertTrue(out.exists())


class CliNoTypstTest(CliTestBase):
    """Behavior that does not need Typst to run."""

    def test_unknown_paper_fails_before_typst(self):   # D2
        out = self.root / "build" / "paper.pdf"
        src = self.write_src("## S\n- x\n", fm="---\nname: N\npaper: typo-letter\n---\n")
        r = self.run_cli(src, "--variant", "full", "-o", out, path="/nonexistent")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith(f"{src}:3: unknown paper 'typo-letter'"), r.stderr)
        self.assertFalse(out.exists())

    def test_failed_runs_leave_no_pdf(self):   # D3
        self.write_src("- a\n", fm="", name="inc.md")
        cases = {
            "parse": ("## S\n- x {.ful}\n", None),
            "include": ("## S\n@missing.md\n", None),
            "paper": ("## S\n", "---\nname: N\npaper: typo-letter\n---\n"),
            "no typst": ("## S\n@inc.md\n", None),
        }
        for name, (body, fm) in cases.items():
            with self.subTest(case=name):
                out = self.root / "out" / "stale.pdf"
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(b"%PDF-old")
                src = self.write_src(body, **({"fm": fm} if fm else {}))
                r = self.run_cli(src, "--variant", "full", "-o", out, path="/nonexistent")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertFalse(out.exists(), r.stderr)

    def test_failed_run_removes_dangling_output_symlink(self):
        for name in ("link.pdf", "link.html", "link.docx"):
            with self.subTest(name=name):
                out = self.root / name
                out.symlink_to(self.root / "nowhere" / name)
                r = self.run_cli(self.write_src("## S\n- x {.ful}\n"), "--variant", "full",
                                 "-o", out, path="/nonexistent")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertFalse(out.is_symlink())

    def test_parse_error_format(self):
        src = self.write_src("## S\n- x {.ful}\n")
        r = self.run_cli(src, "--variant", "full")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith(f"{src}:5: "), r.stderr)
        self.assertIn("invalid variant marker", r.stderr)

    def test_relative_source_path_in_errors(self):
        self.write_src("## S\n- x {.ful}\n", name="rel.md")
        r = self.run_cli("rel.md", "--variant", "full")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("rel.md:5: "), r.stderr)

    def test_missing_source(self):
        r = self.run_cli(self.root / "nope.md", "--variant", "full")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nope.md", r.stderr)

    def test_typ_only_needs_no_typst(self):
        src = self.write_src("## S\n- x\n")
        r = self.run_cli(src, "--variant", "full", "--typ-only", path="/nonexistent")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "build" / "src_full.typ").exists())
        self.assertFalse((self.root / "build" / "src_full.pdf").exists())

    def test_typ_only_keeps_existing_pdf(self):   # T10: --typ-only does not touch the PDF
        out = self.root / "out" / "keep.pdf"
        out.parent.mkdir()
        for body in ("## S\n- x\n", "## S\n- x {.ful}\n"):
            with self.subTest(body=body):
                out.write_bytes(b"%PDF-keep")
                r = self.run_cli(self.write_src(body), "--variant", "full", "-o", out,
                                 "--typ-only", path="/nonexistent")
                self.assertEqual(r.returncode, 0 if "ful}" not in body else 1, r.stderr)
                self.assertEqual(out.read_bytes(), b"%PDF-keep")

    def test_partial_pdf_removed_after_typst_failure(self):   # T10
        bindir = self.root / "bin"
        bindir.mkdir()
        fake = bindir / "typst"
        # Lists every font the source asks for; "compile" writes its output
        # (the last argument) and then fails.
        fake.write_text('#!/bin/sh\n'
                        'if [ "$1" = fonts ]; then echo Charter; exit 0; fi\n'
                        'for last; do :; done\n'
                        'printf "%%PDF-partial" > "$last"\n'
                        'echo "error: fake failure" >&2\n'
                        'exit 1\n')
        fake.chmod(0o755)
        out = self.root / "out" / "partial.pdf"
        r = self.run_cli(self.write_src("## S\n- x\n"), "--variant", "full", "-o", out,
                         path=f"{bindir}:/usr/bin:/bin")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("fake failure", r.stderr)
        self.assertRegex(r.stderr, r"(?m)^error: typst could not compile")
        self.assertFalse(out.exists())

    def test_crlf_bom_twin_emits_same_typ(self):   # Review Focus 1
        twin = self.root / "twin"
        shutil.copytree(FIXTURES, twin)
        for md in twin.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            md.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
        for src, out in [(FIXTURES / "resume.md", "lf.pdf"), (twin / "resume.md", "crlf.pdf")]:
            r = self.run_cli(src, "--variant", "full", "-o", out, "--typ-only")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / "build" / "lf.typ").read_text(encoding="utf-8"),
                         (self.root / "build" / "crlf.typ").read_text(encoding="utf-8"))

    def test_warnings_printed(self):
        src = self.write_src("## S {.full}\n- x {.short}\n- y\n")
        r = self.run_cli(src, "--variant", "full", "--typ-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stderr, rf"warning: {re.escape(str(src))}:5: .*can never appear")

    def test_output_extension_picks_format(self):
        self.assertEqual(build_resume.output_format(Path("a/b.pdf")), "pdf")
        self.assertEqual(build_resume.output_format(Path("b.HTML")), "html")
        self.assertEqual(build_resume.output_format(Path("b.Docx")), "docx")
        for name in ("b.htm", "b.doc", "b", "b.pdf.txt"):
            with self.subTest(name=name):
                self.assertIsNone(build_resume.output_format(Path(name)))

    def test_unknown_output_extension_names_the_three(self):
        for name in ("x.png", "x.htm", "x"):
            with self.subTest(name=name):
                r = self.run_cli(self.write_src("## S\n"), "--variant", "full", "-o", name)
                self.assertEqual(r.returncode, 2)
                self.assertIn(".pdf, .html or .docx", r.stderr)
                self.assertFalse((self.root / name).exists())

    def test_typ_only_needs_pdf_output(self):
        for name in ("x.html", "x.docx"):
            with self.subTest(name=name):
                r = self.run_cli(self.write_src("## S\n"), "--variant", "full", "-o", name,
                                 "--typ-only")
                self.assertEqual(r.returncode, 2)
                self.assertIn("--typ-only", r.stderr)
                self.assertFalse((self.root / "build").exists())

    def test_count_pdf_pages_fallback(self):
        pdf = self.root / "x.pdf"
        pdf.write_bytes(b"%PDF-1.7\n1 0 obj\n<< /Type /Pages /Count 2 >>\nendobj\n"
                        b"2 0 obj\n<< /Type /Page >>\nendobj\n3 0 obj\n<</Type/Page/Parent 1 0 R>>\n")
        self.assertEqual(build_resume.count_pdf_pages(pdf, use_pdfinfo=False), 2)

    def test_font_paths_are_existing_dirs(self):   # clarification 1
        for p in build_resume.font_paths():
            self.assertTrue(Path(p).is_dir(), p)

    def test_missing_typst_message(self):
        r = self.run_cli(self.write_src("## S\n- x\n"), "--variant", "full", path="/nonexistent")
        self.assertEqual(r.returncode, 1)
        self.assertIn("brew install typst", r.stderr)


if __name__ == "__main__":
    unittest.main()
