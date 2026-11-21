// Page-break test (plan Review Focus 4): an entry header or a section title
// must never be the last thing on a page, separated from its first line.
//
// Four scenarios, each sized with one-line filler items so that, WITHOUT the
// template's `sticky` blocks, the checked heading would end the page alone:
//   1. page 1: entry header (title + subtitle) fits, its first item does not.
//      Filler count 49: without sticky, page 1 ends with
//      "ORPHAN CHECK ENTRY / Subtitle line".
//   2. new page: only the entry's title row fits, not its subtitle.
//      Filler count 52: without sticky and with a breakable header, the page
//      ends with "SPLIT CHECK ENTRY".
//   3. new page: only the section title fits after the filler.
//      Filler count 51: without sticky, the page ends with "ORPHAN CHECK SECTION".
//   4. new page: section title and entry header fit, the first item does not
//      (sticky blocks must chain).
//      Filler count 50: without sticky, the page ends with "CHAIN CHECK SECTION"
//      and "Chain check entry".
// Counts were calibrated with Typst 0.15.1 and the template spacing of
// 2026-11-21 against a copy of template/resume.typ with `sticky: false`.
// After changing spacing, recalibrate with --input n1=.. (and n2..n4).
//
// Run from the repo root:
//   typst compile --root . template/tests/pagebreak.typ build/pagebreak.pdf
//   pdftotext -f 1 -l 1 build/pagebreak.pdf - | tail -3
//     -> must not end with the entry title "ORPHAN CHECK ENTRY".
// Full check (every scenario, every page): a page that shows a check heading
// must also show that heading's first item:
//   for p in $(seq 1 $(pdfinfo build/pagebreak.pdf | awk '/^Pages/{print $2}')); do
//     t=$(pdftotext -f $p -l $p build/pagebreak.pdf -)
//     for k in "ORPHAN CHECK ENTRY:First item of ORPHAN" "SPLIT CHECK ENTRY:First item of SPLIT" \
//              "ORPHAN CHECK SECTION:First item of SECTION" "CHAIN CHECK SECTION:First item of CHAIN"; do
//       if grep -q "${k%%:*}" <<<"$t" && ! grep -q "${k#*:}" <<<"$t"; then echo "FAIL page $p: ${k%%:*}"; fi
//     done
//   done
#import "/template/resume.typ": *

#let n1 = int(sys.inputs.at("n1", default: "49"))
#let n2 = int(sys.inputs.at("n2", default: "52"))
#let n3 = int(sys.inputs.at("n3", default: "51"))
#let n4 = int(sys.inputs.at("n4", default: "50"))
#let filler(n) = for i in range(n) { item([#("Filler item " + str(i + 1))]) }

#show: resume.with(name: "Page Break Test", fonts: ("Charter",))

// Scenario 1
#section([#"Scenario one"])[
  #entry(title: [#"Filler Entry"], date: [#"2026"])[
    #filler(n1)
  ]
  #entry(title: [#"ORPHAN CHECK ENTRY"], date: [#"2026"], subtitle: [#"Subtitle line"], side: [#"Side"])[
    #item([#"First item of ORPHAN check entry"])
    #item([#"Second item of ORPHAN check entry"])
  ]
]

// Scenario 2
#pagebreak()
#section([#"Scenario two"])[
  #entry(title: [#"Filler Entry"], date: [#"2026"])[
    #filler(n2)
  ]
  #entry(title: [#"SPLIT CHECK ENTRY"], date: [#"2026"], subtitle: [#"Subtitle line"], side: [#"Side"])[
    #item([#"First item of SPLIT check entry"])
  ]
]

// Scenario 3
#pagebreak()
#section([#"Scenario three"])[
  #entry(title: [#"Filler Entry"], date: [#"2026"])[
    #filler(n3)
  ]
]
#section([#"Orphan check section"])[
  #entry(title: [#"Entry under the checked section"], date: [#"2026"])[
    #item([#"First item of SECTION check"])
  ]
]

// Scenario 4
#pagebreak()
#section([#"Scenario four"])[
  #entry(title: [#"Filler Entry"], date: [#"2026"])[
    #filler(n4)
  ]
]
#section([#"Chain check section"])[
  #entry(title: [#"Chain check entry"], date: [#"2026"])[
    #item([#"First item of CHAIN check"])
  ]
]
