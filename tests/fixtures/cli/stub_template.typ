// Stub of template/resume.typ for the CLI tests: the template API from the
// plan's "Shared interfaces", rendered as plain text with no styling.
#let resume(name: "", title: none, lang: "en", paper: "us-letter",
            fonts: ("Charter",), contacts: (), body) = {
  set page(paper: paper, margin: (x: 0.6in, y: 0.5in), numbering: none)
  set text(font: fonts, lang: lang, size: 10pt)
  [#name]
  if title != none [ -- #title]
  parbreak()
  for c in contacts {
    if c.url == none [#c.text ] else [#link(c.url, c.text) ]
  }
  parbreak()
  body
}
#let section(title, body) = [#strong(upper(title)) #parbreak() #body #parbreak()]
#let entry(title: none, date: none, subtitle: none, side: none, body) = {
  [#title]
  if date != none [ (#date)]
  if subtitle != none [ -- #subtitle]
  if side != none [, #side]
  parbreak()
  body
}
#let item(body, date: none, details: ()) = {
  [- #body]
  if date != none [ (#date)]
  for d in details [ -- #d]
  parbreak()
}
#let paragraph(body) = [#body #parbreak()]
#let hl(name) = underline(strong(name))
