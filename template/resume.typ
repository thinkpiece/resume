// Resume template: classic black-and-white layout, based on the earlier
// LaTeX English resume (resume.cls), lightly refreshed.
//
// The generator (scripts/build_resume.py) emits a .typ file that imports this
// file and calls only the functions below. Layout lives here; content lives in
// content/*.md. Spec: docs/superpowers/specs/2026-11-21-md-resume-generator-design.md §6.
//
// Public API (fixed; see the plan's "Shared interfaces"):
//   resume(name:, title:, lang:, paper:, fonts:, contacts:, body)
//   section(title, body)                 title: content
//   entry(title:, date:, subtitle:, side:, body)
//   item(body, date:, details:)          details: array of content
//   paragraph(body)
//   hl(name)                             name: str

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------

#let _size = 10pt              // body text
#let _detail-size = 0.92em     // continuation ("detail") lines under a bullet
#let _name-size = 20pt
#let _title-size = 11.5pt      // job title under the name
#let _section-size = 11.5pt
#let _entry-size = 11pt
#let _gray = luma(60)          // dates and side text: the only non-black ink
#let _rule = 0.6pt + black     // section rule
#let _marker-width = 1em       // bullet column
#let _date-gap = 1.5em         // minimum space between text and a right-aligned date
#let _icon-height = 0.85em

// Line boxes run from a fixed height above the baseline down to the baseline,
// whatever the font reports (Typst reads Charter's cap height as about 0.98em,
// which would add ~3pt to every line). Pitch between lines = _top-edge + leading.
#let _top-edge = 0.7em
#let _leading = (en: 0.5em, ko: 0.7em)    // Hangul is taller and denser

// Vertical rhythm. Adjacent block spacings collapse to the larger one; a weak
// v() replaces the block spacing next to it.
#let _header-below = 1.15em
#let _section-above = 1.35em
#let _section-below = 0.65em   // rule to the section's first child, whatever it is
#let _entry-above = 0.85em
#let _entry-below = 0.5em
#let _item-extra = 0.1em       // bullets sit slightly further apart than lines

#let _icons = (
  location: "icons/location.svg",
  phone: "icons/phone.svg",
  email: "icons/email.svg",
  homepage: "icons/homepage.svg",
  linkedin: "icons/linkedin.svg",
  github: "icons/github.svg",
)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Left text with optional right-aligned text (a date or an entry's side text).
// The right part sits in its own column, bottom-aligned: a long left part
// wraps before reaching it (never overlaps it), and the right part shares the
// baseline of the left part's last line.
#let _row(left, right) = {
  if right == none {
    left
  } else {
    grid(
      columns: (1fr, auto),
      column-gutter: _date-gap,
      align: bottom,
      left, text(fill: _gray, right),
    )
  }
}

#let _contact(c) = {
  assert(c.kind in _icons, message: "unknown contact kind: " + repr(c.kind))
  let icon = box(baseline: 0.12em, image(_icons.at(c.kind), height: _icon-height))
  let piece = box[#icon#h(0.45em)#c.text]
  if c.at("url", default: none) == none { piece } else { link(c.url, piece) }
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

#let resume(
  name: "",
  title: none,
  lang: "en",
  paper: "us-letter",
  fonts: ("Charter",),
  contacts: (),
  body,
) = {
  set document(title: name, author: name)
  set page(
    paper: paper,
    margin: (left: 0.6in, right: 0.6in, top: 0.5in, bottom: 0.5in),
    numbering: none,
  )
  set text(
    font: fonts,
    lang: lang,
    size: _size,
    hyphenate: false,
    top-edge: _top-edge,
    bottom-edge: "baseline",
  )
  let leading = _leading.at(lang, default: _leading.en)
  set par(justify: false, leading: leading, spacing: leading + _item-extra)
  set underline(offset: 0.18em, stroke: 0.045em)

  // Break lines containing Hangul only at spaces ("keep-all"), as Korean
  // typesetting expects; by default every Hangul syllable is a break point.
  show regex("\\S*\\p{Hangul}\\S*"): box

  // Header: name, job title, then one wrapping line of contact items.
  // The name is uppercased only in English; elsewhere it prints as written
  // (owner: the Korean header reads "박준영 (Junyoung Park)").
  block(width: 100%, below: _header-below, {
    let shown = if lang == "en" { upper(name) } else { name }
    text(size: _name-size, weight: "bold", tracking: 0.03em, shown)
    if title != none {
      v(0.75em, weak: true)
      text(size: _title-size, title)
    }
    if contacts.len() > 0 {
      v(0.95em, weak: true)
      contacts.map(_contact).join(h(1.6em, weak: true))
    }
  })

  body
}

// ---------------------------------------------------------------------------
// Body elements
// ---------------------------------------------------------------------------

// Section: bold uppercase title over a thin full-width rule. The title block
// sticks to the section's first child, so it never ends a page alone.
#let section(title, body) = {
  block(
    sticky: true,
    width: 100%,
    above: _section-above,
    inset: (bottom: 0.35em),
    stroke: (bottom: _rule),
    text(size: _section-size, weight: "bold", tracking: 0.04em, upper(title)),
  )
  // Overrides the first child's own `above`, so the gap under the rule is the
  // same for an entry, a bullet or a paragraph.
  v(_section-below, weak: true)
  body
}

// Entry: bold title left, date right; optional italic subtitle with optional
// right-aligned side text. The header sticks to the entry's first item.
#let entry(title: none, date: none, subtitle: none, side: none, body) = {
  let has-head = title != none or date != none
  let has-sub = subtitle != none or side != none
  if has-head or has-sub {
    block(sticky: true, breakable: false, width: 100%, above: _entry-above, below: _entry-below, context {
      let gap = par.leading
      if has-head {
        block(width: 100%, below: gap, _row(text(size: _entry-size, weight: "bold", title), date))
      }
      if has-sub {
        block(width: 100%, above: gap, _row(emph(subtitle), side))
      }
    })
  }
  body
}

// Bullet item: small middle-dot marker; optional date right-aligned on the
// last line of the text; optional detail lines (slightly smaller) below. An
// item is never split across pages.
#let item(body, date: none, details: ()) = context {
  let gap = par.leading
  let main = block(width: 100%, below: gap, _row(body, date))
  let rest = if details.len() > 0 {
    block(width: 100%, above: gap, {
      set text(size: _detail-size)
      details.join(linebreak())
    })
  }
  block(
    breakable: false,
    width: 100%,
    above: gap + _item-extra,
    below: gap + _item-extra,
    grid(columns: (_marker-width, 1fr), align(center)[·], main + rest),
  )
}

// Paragraph: plain text directly under a section.
#let paragraph(body) = context block(
  width: 100%,
  above: par.spacing,
  below: par.spacing,
  body,
)

// Highlighted author name in publication lists: bold and underlined.
#let hl(name) = underline(strong(name))
