import json
import os
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resumegen import ResumeError  # noqa: E402
from resumegen.model import VARIANTS, Line  # noqa: E402
from resumegen.parse import parse  # noqa: E402
from resumegen.publications import (KNOWN_FIELDS, REQUIRED_FIELDS,  # noqa: E402
                                    Publication, Publications, Venue, escape,
                                    format_item, load_publications, select,
                                    short_name)
from resumegen.render import Emph, Text, parse_inline, plain_text  # noqa: E402
from resumegen.variants import filter_variant  # noqa: E402

OWNER = "Junyoung Park"
TCAS_ID = '"id": "tcas1-2016-kim"'
ISSCC_ID = '"id": "isscc-2013-park"'
DROP = object()


def tcas(**changes):
    return _changed({
        "id": "tcas1-2016-kim",
        "type": "journal",
        "title": "A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor "
                 "for Micro Air Vehicle Navigation",
        "authors": ["Youchang Kim", "Injoon Hong", "Junyoung Park", "Hoi-Jun Yoo"],
        "venue": {"name": "IEEE Transactions on Circuits and Systems I: Regular Papers",
                  "short": "TCAS-I"},
        "year": 2016, "month": 3,
        "volume": "63", "issue": "3", "pages": "359-369",
        "url": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7420681"
               "&isnumber=7447839",
    }, changes)


def isscc(**changes):
    return _changed({
        "id": "isscc-2013-park",
        "type": "conference",
        "title": "A 646GOPS/W multi-classifier many-core processor with cortex-like "
                 "architecture for super-resolution recognition",
        "authors": ["Junyoung Park", "I. Hong", "G. Kim", "Y. Kim", "K. Lee",
                    "S. Park", "K. Bong", "H.-J. Yoo"],
        "venue": {"name": "IEEE International Solid-State Circuits Conference",
                  "short": "ISSCC"},
        "year": 2013, "month": 2,
        "doi": "10.1109/ISSCC.2013.6487685",
        "url": "https://dx.doi.org/10.1109/ISSCC.2013.6487685",
    }, changes)


def _changed(item, changes):
    for key, value in changes.items():
        if value is DROP:
            item.pop(key, None)
        else:
            item[key] = value
    return item


def document(*items, **top):
    return _changed({"schema": 1, "owner": OWNER, "publications": list(items)}, top)


def dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def line_of(text: str, needle: str, nth: int = 1) -> int:
    """1-based line of the nth line of `text` that contains `needle`."""
    found = [n for n, line in enumerate(text.split("\n"), start=1) if needle in line]
    if len(found) < nth:
        raise AssertionError(f"{needle!r} occurs fewer than {nth} times")
    return found[nth - 1]


def item_start(text: str, index: int) -> int:
    """Line of the "{" that opens publications[index] in `dump` output."""
    return [n for n, line in enumerate(text.split("\n"), start=1)
            if line == "    {"][index]


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, content):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
        return p


class LoadTest(TempDirTest):
    def test_loads_minimal_file(self):
        text = dump(document(tcas(), isscc()))
        pubs = load_publications(self.write("p.json", text))
        self.assertEqual(pubs.path, self.d / "p.json")
        self.assertEqual(pubs.owner, "Junyoung Park")
        self.assertEqual(len(pubs.items), 2)
        self.assertEqual(pubs.items[1].venue, Venue(
            "IEEE International Solid-State Circuits Conference", "ISSCC"))
        self.assertEqual(pubs.items[1].lineno, line_of(text, ISSCC_ID))
        self.assertEqual(pubs.items[0], Publication(
            id="tcas1-2016-kim", type="journal",
            title="A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor "
                  "for Micro Air Vehicle Navigation",
            authors=("Youchang Kim", "Injoon Hong", "Junyoung Park", "Hoi-Jun Yoo"),
            venue=Venue("IEEE Transactions on Circuits and Systems I: Regular Papers",
                        "TCAS-I"),
            year=2016, month=3, month_end=None,
            volume="63", issue="3", pages="359-369", location=None, doi=None,
            url="https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7420681"
                "&isnumber=7447839",
            lineno=line_of(text, TCAS_ID)))

    def test_venue_short_is_optional(self):
        text = dump(document(isscc(venue={"name": "IEEE CICC"})))
        pubs = load_publications(self.write("p.json", text))
        self.assertEqual(pubs.items[0].venue, Venue("IEEE CICC", None))

    def test_item_lines_follow_the_structure(self):   # clarification 9
        # A nested unknown field holding the same "id" comes before the item's
        # own key; the second item's id is written with a JSON escape.
        first = {"extra": {"id": "isscc-2013-park"}, **isscc()}
        text = dump(document(first, tcas()))
        own = line_of(text, ISSCC_ID, 2)
        self.assertLess(line_of(text, ISSCC_ID), own)   # the nested one
        escaped = text.replace(TCAS_ID, '"id": "\\u0074cas1-2016-kim"')
        self.assertNotIn(TCAS_ID, escaped)
        pubs = load_publications(self.write("p.json", escaped))
        self.assertEqual([(p.id, p.lineno) for p in pubs.items],
                         [("isscc-2013-park", own),
                          ("tcas1-2016-kim", line_of(text, TCAS_ID))])
        # A third item repeats the first id: the error names its own line.
        text = dump(document(first, tcas(), isscc()))
        with self.assertRaises(ResumeError) as cm:
            load_publications(self.write("q.json", text))
        self.assertEqual(str(cm.exception),
                         f'{self.d / "q.json"}:{line_of(text, ISSCC_ID, 3)}: '
                         'isscc-2013-park: duplicate id "isscc-2013-park"')

    def test_item_without_id_key_points_at_its_brace(self):
        text = dump(document(tcas(), isscc(id=DROP)))
        with self.assertRaises(ResumeError) as cm:
            load_publications(self.write("p.json", text))
        self.assertEqual(str(cm.exception),
                         f'{self.d / "p.json"}:{item_start(text, 1)}: '
                         'publications[1]: missing "id"')

    def test_unknown_fields_ignored(self):
        text = dump(document(isscc(sci=True), **{"$schema": "./publications.schema.json"}))
        pubs = load_publications(self.write("p.json", text))
        self.assertEqual([p.id for p in pubs.items], ["isscc-2013-park"])

    def test_comment_like_text_is_kept(self):
        title = "A <!-- not a comment --> title"
        text = dump(document(isscc(title=title)))
        self.assertEqual(load_publications(self.write("p.json", text)).items[0].title, title)

    def test_bom_and_crlf(self):   # Review Focus 3
        text = dump(document(tcas(), isscc()))
        data = b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8")
        pubs = load_publications(self.write("p.json", data))
        self.assertEqual(pubs.items[1].lineno, line_of(text, ISSCC_ID))

        text = dump(document(tcas(), isscc(month=13)))
        path = self.write("q.json", b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode())
        with self.assertRaises(ResumeError) as cm:
            load_publications(path)
        self.assertEqual(str(cm.exception),
                         f'{path}:{line_of(text, ISSCC_ID)}: isscc-2013-park: '
                         '"month" must be an integer 1-12')

    def test_invalid_json(self):
        path = self.write("p.json", '{\n  "schema": 1,\n  oops\n}\n')
        with self.assertRaises(ResumeError) as cm:
            load_publications(path)
        self.assertTrue(str(cm.exception).startswith(f"{path}:3: invalid JSON"),
                        str(cm.exception))

    def test_invalid_utf8(self):
        path = self.write("p.json", b'{\n  "owner": "\xff"\n}\n')
        with self.assertRaises(ResumeError) as cm:
            load_publications(path)
        self.assertEqual(str(cm.exception), f"{path}:2: invalid UTF-8 text")

    def test_missing_file(self):
        path = self.d / "nope.json"
        include = Line(text="@nope.json journal", path=self.d / "r.md", lineno=4,
                       scope=VARIANTS)
        with self.assertRaises(ResumeError) as cm:
            load_publications(path, include)
        self.assertEqual(str(cm.exception),
                         f"{include.path}:{include.lineno}: included file not found: {path}")
        with self.assertRaises(ResumeError) as cm:
            load_publications(path)
        self.assertEqual(str(cm.exception), f"{path}: file not found")

    def test_errors(self):
        no_owner = document(isscc())
        del no_owner["owner"]
        # (case name, data, where, label, message). `where` is a line number, a
        # needle whose first line counts, (needle, nth), or ("item", index).
        cases = [
            ("schema 2", document(isscc(), schema=2), 1, None,
             "unsupported schema version 2; this build reads 1"),
            ("schema string", document(isscc(), schema="1"), 1, None,
             'unsupported schema version "1"; this build reads 1'),
            ("schema missing", document(isscc(), schema=DROP), 1, None,
             'missing "schema"'),
            ("owner missing", no_owner, 1, None, 'missing "owner"'),
            ("owner empty", document(isscc(), owner=""), 1, None,
             '"owner" must not be empty'),
            ("owner number", document(isscc(), owner=5), 1, None,
             '"owner" must be a string'),
            ("publications missing", document(publications=DROP), 1, None,
             'missing "publications"'),
            ("publications object", document(publications={}), 1, None,
             '"publications" must be a list'),
            ("top level array", [isscc()], 1, None,
             "the top level must be a JSON object"),
            ("item not an object", document(tcas(), "x"), '    "x"', "publications[1]",
             "must be an object"),
            ("venue missing", document(tcas(), isscc(venue=DROP)), ISSCC_ID,
             "isscc-2013-park", 'missing "venue"'),
            ("id missing", document(tcas(), isscc(id=DROP)), ("item", 1),
             "publications[1]", 'missing "id"'),
            ("id pattern", document(tcas(), isscc(id="X_1")), '"id": "X_1"',
             "publications[1]", '"id" must match [a-z0-9-]+'),
            ("id number", document(tcas(), isscc(id=7)), '"id": 7',
             "publications[1]", '"id" must match [a-z0-9-]+'),
            ("duplicate id", document(isscc(), tcas(), isscc(title="Other")),
             (ISSCC_ID, 2), "isscc-2013-park", 'duplicate id "isscc-2013-park"'),
            ("type book", document(isscc(type="book")), ISSCC_ID, "isscc-2013-park",
             '"type" must be journal or conference'),
            ("title empty", document(isscc(title="")), ISSCC_ID, "isscc-2013-park",
             '"title" must not be empty'),
            ("title number", document(isscc(title=3)), ISSCC_ID, "isscc-2013-park",
             '"title" must be a string'),
            ("title line break", document(isscc(title="a\nb")), ISSCC_ID,
             "isscc-2013-park", '"title" must be one line without control characters'),
            ("title tab", document(isscc(title="a\tb")), ISSCC_ID,
             "isscc-2013-park", '"title" must be one line without control characters'),
            ("title delete", document(isscc(title="a\x7fb")), ISSCC_ID,
             "isscc-2013-park", '"title" must be one line without control characters'),
            ("title padded", document(isscc(title=" a")), ISSCC_ID, "isscc-2013-park",
             '"title" must not start or end with a space'),
            ("title padded end", document(isscc(title="a\u00a0")), ISSCC_ID,
             "isscc-2013-park", '"title" must not start or end with a space'),
            ("venue name padded", document(isscc(venue={"name": "V "})), ISSCC_ID,
             "isscc-2013-park", '"venue.name" must not start or end with a space'),
            ("url line break", document(isscc(url="https://x\n")), ISSCC_ID,
             "isscc-2013-park", '"url" must be one line without control characters'),
            ("owner padded", document(isscc(), owner="Junyoung Park "), 1, None,
             '"owner" must not start or end with a space'),
            ("year true", document(isscc(year=True)), ISSCC_ID, "isscc-2013-park",
             '"year" must be an integer'),
            ("year float", document(isscc(year=2013.0)), ISSCC_ID, "isscc-2013-park",
             '"year" must be an integer'),
            ("year string", document(isscc(year="2013")), ISSCC_ID, "isscc-2013-park",
             '"year" must be an integer'),
            ("month string", document(isscc(month="3")), ISSCC_ID, "isscc-2013-park",
             '"month" must be an integer 1-12'),
            ("month 13", document(isscc(month=13)), ISSCC_ID, "isscc-2013-park",
             '"month" must be an integer 1-12'),
            ("month 0", document(isscc(month=0)), ISSCC_ID, "isscc-2013-park",
             '"month" must be an integer 1-12'),
            ("month true", document(isscc(month=True)), ISSCC_ID, "isscc-2013-park",
             '"month" must be an integer 1-12'),
            ("month null", document(isscc(month=None)), ISSCC_ID, "isscc-2013-park",
             '"month" must be an integer 1-12'),
            ("month_end without month", document(isscc(month=DROP, month_end=12)),
             ISSCC_ID, "isscc-2013-park", '"month_end" needs "month"'),
            ("month_end equal", document(isscc(month=11, month_end=11)), ISSCC_ID,
             "isscc-2013-park", '"month_end" must be after "month" and at most 12'),
            ("month_end before", document(isscc(month=11, month_end=10)), ISSCC_ID,
             "isscc-2013-park", '"month_end" must be after "month" and at most 12'),
            ("month_end 13", document(isscc(month=11, month_end=13)), ISSCC_ID,
             "isscc-2013-park", '"month_end" must be after "month" and at most 12'),
            ("month_end string", document(isscc(month=11, month_end="12")), ISSCC_ID,
             "isscc-2013-park", '"month_end" must be after "month" and at most 12'),
            ("authors empty", document(isscc(authors=[])), ISSCC_ID, "isscc-2013-park",
             '"authors" must be a non-empty list of names'),
            ("authors string", document(isscc(authors="Junyoung Park")), ISSCC_ID,
             "isscc-2013-park", '"authors" must be a non-empty list of names'),
            ("authors empty name", document(isscc(authors=["Junyoung Park", ""])),
             ISSCC_ID, "isscc-2013-park", '"authors" must be a non-empty list of names'),
            ("authors number", document(isscc(authors=["Junyoung Park", 3])),
             ISSCC_ID, "isscc-2013-park", '"authors" must be a non-empty list of names'),
            ("authors line break", document(isscc(authors=["Junyoung Park", "A\nB"])),
             ISSCC_ID, "isscc-2013-park",
             '"authors" must be one line without control characters'),
            ("authors padded", document(isscc(authors=["Junyoung Park", "A "])),
             ISSCC_ID, "isscc-2013-park", '"authors" must not start or end with a space'),
            ("owner not an author", document(isscc(authors=["J. Park", "H.-J. Yoo"])),
             ISSCC_ID, "isscc-2013-park",
             'owner "Junyoung Park" is not among the authors'),
            ("venue string", document(isscc(venue="ISSCC")), ISSCC_ID,
             "isscc-2013-park", '"venue" must be an object'),
            ("venue name missing", document(isscc(venue={"short": "ISSCC"})), ISSCC_ID,
             "isscc-2013-park", 'missing "venue.name"'),
            ("venue short empty", document(isscc(venue={"name": "X", "short": ""})),
             ISSCC_ID, "isscc-2013-park", '"venue.short" must not be empty'),
            ("pages empty", document(isscc(pages="")), ISSCC_ID, "isscc-2013-park",
             '"pages" must not be empty'),
            ("pages blank", document(isscc(pages="  ")), ISSCC_ID, "isscc-2013-park",
             '"pages" must not be empty'),
            ("pages number", document(isscc(pages=359)), ISSCC_ID, "isscc-2013-park",
             '"pages" must be a string'),
            ("doi null", document(isscc(doi=None)), ISSCC_ID, "isscc-2013-park",
             '"doi" must be a string'),
        ]
        for name, data, where, label, message in cases:
            with self.subTest(name):
                text = dump(data)
                path = self.write("p.json", text)
                if isinstance(where, int):
                    line = where
                elif isinstance(where, str):
                    line = line_of(text, where)
                elif where[0] == "item":
                    line = item_start(text, where[1])
                else:
                    line = line_of(text, *where)
                prefix = f"{path}:{line}: " + (f"{label}: " if label else "")
                with self.assertRaises(ResumeError) as cm:
                    load_publications(path)
                self.assertEqual(str(cm.exception), prefix + message)

    def test_schema_file_matches_validator(self):
        schema = json.loads((ROOT / "content/shared/publications.schema.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["required"], ["schema", "owner", "publications"])
        item = schema["properties"]["publications"]["items"]
        if "$ref" in item:
            item = schema["$defs"][item["$ref"].removeprefix("#/$defs/")]
        self.assertEqual(set(item["required"]), REQUIRED_FIELDS)
        self.assertEqual(set(item["properties"]), KNOWN_FIELDS)


class StrictJsonTest(TempDirTest):   # clarification 16
    def cases(self):
        """(name, file text, line, message) for each non-standard input."""
        # The first title holds "NaN" inside a string, with escaped quotes.
        nan = dump(document(tcas(title='Not "NaN" here'), isscc(sci=float("nan"))))
        inf = dump(document(isscc(year=float("inf"))))
        minus_inf = dump(document(isscc(), extra=float("-inf")))
        surrogate = dump(document(tcas(), isscc(title="Title X"))).replace(
            "Title X", "Title \\ud800")
        author = dump(document(isscc(authors=["Junyoung Park", "A X"]))).replace(
            "A X", "A \\udfff")
        venue = dump(document(isscc(venue={"name": "V X"}))).replace("V X", "V \\udc00")
        schema = dump(document(isscc(), **{"$schema": 1}))
        return [
            ("NaN in an extension field", nan, line_of(nan, '"sci": NaN'),
             "invalid JSON: NaN is not standard JSON"),
            ("Infinity", inf, line_of(inf, '"year": Infinity'),
             "invalid JSON: Infinity is not standard JSON"),
            ("-Infinity at the top", minus_inf, line_of(minus_inf, '"extra": -Infinity'),
             "invalid JSON: -Infinity is not standard JSON"),
            ("lone surrogate in a title", surrogate, line_of(surrogate, ISSCC_ID),
             'isscc-2013-park: "title" must not hold a lone surrogate'),
            ("lone surrogate in an author", author, line_of(author, ISSCC_ID),
             'isscc-2013-park: "authors" must not hold a lone surrogate'),
            ("lone surrogate in a venue", venue, line_of(venue, ISSCC_ID),
             'isscc-2013-park: "venue.name" must not hold a lone surrogate'),
            ("numeric $schema", schema, 1, '"$schema" must be a string'),
        ]

    def test_errors(self):
        for name, text, line, message in self.cases():
            with self.subTest(name):
                path = self.write("p.json", text)
                with self.assertRaises(ResumeError) as cm:
                    load_publications(path)
                self.assertEqual(str(cm.exception), f"{path}:{line}: {message}")

    def test_cli_exits_1_with_the_message(self):
        md = self.write("en/resume.md", "---\nname: Junyoung Park\n---\n## P\n"
                        "### Papers\n@../shared/p.json conference\n")
        env = dict(os.environ, RESUME_ROOT=str(self.d))
        for name, text, line, message in self.cases():
            with self.subTest(name):
                path = self.write("shared/p.json", text)
                r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_resume.py"),
                                    str(md), "--variant", "full",
                                    "-o", str(self.d / "out.html")],
                                   capture_output=True, text=True, env=env, cwd=self.d)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stderr, f"{path}:{line}: {message}\n")

    def test_standard_look_alikes_load(self):
        title = 'NaN, -Infinity and \\"Infinity\\" \U0001F600'
        text = dump(document(isscc(title=title, sci="NaN", note=["Infinity"])))
        pubs = load_publications(self.write("p.json", text))
        self.assertEqual(pubs.items[0].title, title)
        pair = dump(document(isscc(title="T X"))).replace("T X", "T \\ud83d\\ude00")
        self.assertEqual(load_publications(self.write("q.json", pair)).items[0].title,
                         "T \U0001F600")
        text = dump(document(isscc(), **{"$schema": "./publications.schema.json"}))
        self.assertEqual(len(load_publications(self.write("r.json", text)).items), 1)

    def test_real_data_file_loads(self):
        pubs = load_publications(ROOT / "content" / "shared" / "publications.json")
        self.assertEqual(len(pubs.items), 36)


def pub(**fields) -> Publication:
    """A conference paper by the owner, Feb. 2013, with `fields` changed."""
    base = dict(id="isscc-2013-park", type="conference", title="Title",
                authors=(OWNER,), venue=Venue("Venue"), year=2013, month=2)
    base.update(fields)
    return Publication(**base)


TCAS_PUB = Publication(
    id="tcas1-2016-kim", type="journal",
    title="A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor "
          "for Micro Air Vehicle Navigation",
    authors=("Youchang Kim", "Injoon Hong", "Junyoung Park", "Hoi-Jun Yoo"),
    venue=Venue("IEEE Transactions on Circuits and Systems I: Regular Papers", "TCAS-I"),
    year=2016, month=3, volume="63", issue="3", pages="359-369",
    url="https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7420681&isnumber=7447839")

ISSCC_PUB = Publication(
    id="isscc-2013-park", type="conference",
    title="A 646GOPS/W multi-classifier many-core processor with cortex-like "
          "architecture for super-resolution recognition",
    authors=("Junyoung Park", "I. Hong", "G. Kim", "Y. Kim", "K. Lee", "S. Park",
             "K. Bong", "H.-J. Yoo"),
    venue=Venue("IEEE International Solid-State Circuits Conference", "ISSCC"),
    year=2013, month=2, doi="10.1109/ISSCC.2013.6487685",
    url="https://dx.doi.org/10.1109/ISSCC.2013.6487685")


def parsed_items(*lines: str, variant: str = "short"):
    """Parse `lines` as the body of a one-section resume; return its items."""
    texts = ["---", "name: Test Person", "---", "## S", *lines]
    path = Path("p.json")
    doc = parse([Line(text=t, path=path, lineno=n, scope=VARIANTS)
                 for n, t in enumerate(texts, start=1)])
    return [child for section in filter_variant(doc, variant).sections
            for child in section.children]


class FormatTest(unittest.TestCase):
    def test_select_order(self):
        items = (pub(id="nov-2012", year=2012, month=11),
                 pub(id="y-2013", month=None),
                 pub(id="feb-a", month=2),
                 pub(id="sep-2013", month=9),
                 pub(id="journal", type="journal", year=2020),
                 pub(id="not-first", authors=("A. Kim", OWNER), year=2019),
                 pub(id="feb-b", month=2))
        pubs = Publications(path=Path("p.json"), owner=OWNER, items=items)
        self.assertEqual([p.id for p in select(pubs, "conference", False)],
                         ["not-first", "sep-2013", "feb-a", "feb-b", "y-2013",
                          "nov-2012"])
        self.assertEqual([p.id for p in select(pubs, "conference", True)],
                         ["sep-2013", "feb-a", "feb-b", "y-2013", "nov-2012"])
        self.assertEqual([p.id for p in select(pubs, "journal", False)], ["journal"])

    def test_journal_line(self):
        self.assertEqual(format_item(TCAS_PUB, OWNER), (
            "- A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor for Micro Air "
            "Vehicle Navigation, *IEEE Transactions on Circuits and Systems I: Regular "
            "Papers*, vol.63, no.3, pp.359-369, Mar. 2016.",
            "  Y. Kim, I. Hong, Junyoung Park, and H.-J. Yoo."))

    def test_conference_line(self):
        self.assertEqual(format_item(ISSCC_PUB, OWNER), (
            "- A 646GOPS/W multi-classifier many-core processor with cortex-like "
            "architecture for super-resolution recognition, *IEEE International "
            "Solid-State Circuits Conference*, Feb. 2013.",
            "  Junyoung Park, I. Hong, G. Kim, Y. Kim, K. Lee, S. Park, K. Bong, "
            "and H.-J. Yoo."))

    def test_missing_parts_drop_label_and_comma(self):
        self.assertEqual(format_item(pub(pages="1-3"), OWNER)[0],
                         "- Title, *Venue*, pp.1-3, Feb. 2013.")
        self.assertEqual(format_item(pub(volume="PP", issue="99"), OWNER)[0],
                         "- Title, *Venue*, vol.PP, no.99, Feb. 2013.")

    def test_dates(self):
        self.assertTrue(format_item(pub(year=2012, month=11, month_end=12), OWNER)[0]
                        .endswith(", Nov.-Dec. 2012."))
        self.assertTrue(format_item(pub(year=2012, month=None), OWNER)[0]
                        .endswith("*Venue*, 2012."))
        names = [format_item(pub(month=m), OWNER)[0].split(", ")[-1].removesuffix(" 2013.")
                 for m in range(1, 13)]
        self.assertEqual(" ".join(names),
                         "Jan. Feb. Mar. Apr. May June July Aug. Sept. Oct. Nov. Dec.")

    def test_authors(self):
        self.assertEqual(format_item(pub(authors=(OWNER,)), OWNER)[1], "  Junyoung Park.")
        self.assertEqual(format_item(pub(authors=(OWNER, "Hoi-Jun Yoo")), OWNER)[1],
                         "  Junyoung Park and H.-J. Yoo.")
        self.assertEqual(format_item(pub(authors=("Hoi-Jun Yoo", OWNER)), "Hoi-Jun Yoo")[1],
                         "  Hoi-Jun Yoo and J. Park.")

    def test_short_name(self):   # Review Focus 2
        cases = {
            "Seongwook Park": "S. Park",
            "Hoi-Jun Yoo": "H.-J. Yoo",
            "Kyuho Jason Lee": "K. J. Lee",
            "H.-J. Yoo": "H.-J. Yoo",
            "K.J. Lee": "K.J. Lee",
            "Émile Zola": "É. Zola",
            "E\u0301mile Zola": "E\u0301. Zola",     # decomposed accent
            "Plato": "Plato",
            "홍 길동": "홍. 길동",
            "박준영": "박준영",
            "Jean--Paul Sartre": "J.--P. Sartre",
        }
        for name, short in cases.items():
            with self.subTest(name):
                self.assertEqual(short_name(name), short)

    def test_escape(self):
        self.assertEqual(escape("a\\b*c_d[e]f|g{h}i"), "a\\\\b\\*c\\_d\\[e\\]f\\|g\\{h}i")

    def test_escape_round_trip(self):   # Review Focus 1, clarifications 3 and 12
        probes = [("Title {.full}", "Venue {.full}"), ("Venue*", "Venue*"),
                  ("*Venue", "*Venue"), ("_Venue_", "_Venue_"), ("a | b", "c | d")]
        for c in string.punctuation:
            probes += [(f"a{c}b {c} c{c}", "Venue"), ("Title", f"a{c}b {c} c{c}"),
                       (f"{c}Title{c}", f"{c}Venue{c}"), (c, c), (c * 2, c * 2)]
        for title, venue in probes:
            with self.subTest(title=title, venue=venue):
                bullet, detail = format_item(pub(title=title, venue=Venue(venue)), OWNER)
                items = parsed_items(bullet, detail)
                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertIsNone(item.date)
                self.assertEqual(item.details, ["Junyoung Park."])
                nodes = parse_inline(item.text)
                self.assertEqual(nodes, (Text(f"{title}, "), Emph((Text(venue),)),
                                         Text(", Feb. 2013.")))
                self.assertEqual(plain_text(nodes), f"{title}, {venue}, Feb. 2013.")

    def test_escaped_marker_at_line_end_stays(self):   # clarification 12
        items = parsed_items("- " + escape("Title {.full}"), "  " + escape("A {.short}"))
        self.assertEqual(len(items), 1)
        self.assertEqual(plain_text(parse_inline(items[0].text)), "Title {.full}")
        self.assertEqual(plain_text(parse_inline(items[0].details[0])), "A {.short}")


if __name__ == "__main__":
    unittest.main()
