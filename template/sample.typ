// Hand-written exercise of the template API in the shape the generator emits
// (plan, "Shared interfaces"). Uses real lines from the English resume.
// Compile from the repo root:
//   typst compile --root . --font-path <each /System/Library/AssetsV2/com_apple_MobileAsset_Font* dir> \
//     template/sample.typ build/sample.pdf
#import "/template/resume.typ": *
#show: resume.with(
  name: "Junyoung Park",
  title: "AI System-on-Chip Startup Founder & Director & Engineer",
  lang: "en",
  paper: "us-letter",
  fonts: ("Charter", "NanumMyeongjo"),
  contacts: (
    (kind: "location", text: "Seongnam-si 13105, Gyeonggi-do, Republic of Korea", url: none),
    (kind: "phone", text: "+82-10-2542-5500", url: "tel:+821025425500"),
    (kind: "email", text: "junyoung@uxf.ai", url: "mailto:junyoung@uxf.ai"),
    (kind: "homepage", text: "http://www.junyoungpark.com", url: "http://www.junyoungpark.com"),
    (kind: "linkedin", text: "https://www.linkedin.com/in/parkjunyoung", url: "https://www.linkedin.com/in/parkjunyoung"),
    (kind: "github", text: "https://github.com/example", url: "https://github.com/example"),
  ),
)
#section([#"Summary"])[
  #paragraph([#"AI SoC specialist with a Ph.D. in Electrical Engineering from KAIST; founded "#strong[#"UX Factory"]#" in 2015 and has led it since. Paragraphs like this one run directly under a section, wrap at the margin, and are left-aligned, not justified."])
]
#section([#"Work Experience"])[
  #entry(title: [#"UX Factory, Inc."], date: [#"Aug. 2015 - Present"], subtitle: [#"Co-founder and Chief Executive Officer"], side: [#"Seongnam, Korea"])[
    #item([#"Founded a company that delivers the world's leading AI solutions derived from System-on-Chip technology"])
    #item([#"Participated in 20+ R&D projects for AI & SoC with major Korean fabless companies"])
  ]
  #entry(title: [#"KAIST"], date: [#"Jan. 2015 - Aug. 2015"], subtitle: [#"Postdoctoral Fellow"], side: none)[
    #item([#"SoC architecture exploration for Vision & Deep Learning in the hardware-software codesign methodology"])
  ]
  #entry(title: [#"Samsung Mobile Processor Innovation Lab, with an artificially long entry title that must wrap before its date"], date: [#"Spt. 2014 - Dec. 2014"], subtitle: [#"Research Intern"], side: none)[
    #item([#"Established a System-C TLM based simulator for early top-level system exploration in many-core SoCs"])
  ]
]
#section([#"Education"])[
  #entry(title: [#"Ph.D. in Electrical Engineering, KAIST"], date: [#"Aug. 2014"], subtitle: none, side: none)[
    #item([#"Thesis: Energy-efficient Context-aware Real-Time Object Recognition Processor"])
    #item([#"Designed and implemented an energy-efficient vision SoC for context-aware object recognition"], details: ([#"- presented and demonstrated at "#emph[#"IEEE International Solid-State Circuits Conference"]],))
  ]
  #entry(title: [#"B.S. in Electrical Engineering, KAIST"], date: [#"Feb. 2009"], subtitle: none, side: none)[
    #item([#"Graduated with "#emph[#"Summa Cum Laude"]])
  ]
]
#section([#"Awards and Activities"])[
  #entry(title: [#"Awards"], date: none, subtitle: none, side: none)[
    #item([#"Critical Assessment of Genome Interpretation (CAGI7) Challenges TSC2 Top-performer"], date: [#"Dec. 2025"])
    #item([#"Kim Choong-Ki Scholarship Award for Outstanding Research Accomplishments"], date: [#"Apr. 2013"])
    #item([#"Korean Science & Technology Research Scholarship Award"], date: [#"Feb. 2009 - Feb. 2011"])
    #item([#"Critical Assessment of Genome Interpretation (CAGI7) Challenges TSC2 Top-performer, an artificially longer award line that must wrap before the date column"], date: [#"Feb. 2009 - Feb. 2011"])
  ]
  #entry(title: [#"Invited Talks"], date: none, subtitle: none, side: none)[
    #item([#"AI Semiconductor Strategies: Lessons from Global AI Chip Companies, "#emph[#"ICT Industry Outlook Conference (ICT산업전망컨퍼런스)"]#", Nov., 2023."])
    #item([#"On-sensor AI Semiconductor for AIoT Devices, "#emph[#"The Institute of Electronics and Information Engineers (대한전자공학회)"]#", Nov., 2022."])
  ]
]
#section([#"Publications"])[
  #entry(title: [#"Journal Papers"], date: none, subtitle: none, side: none)[
    #item([#"A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor for Micro Air Vehicle Navigation, "#emph[#"IEEE Transactions on Circuits and Systems I: Regular Papers"]#", vol.63, no.3, pp.359-369, Mar. 2016."], details: ([#"Y. Kim, I. Hong, "#hl("Junyoung Park")#", H.-J. Yoo."], [#"Second detail line: "#link("https://doi.org/10.1109/TCSI.2016.2525078")[#"doi.org/10.1109/TCSI.2016.2525078"]]))
    #item([#"A 92-mW Real-Time Traffic Sign Recognition System With Robust Illumination Adaptation and Support Vector Machine, "#emph[#"IEEE Journal of Solid-State Circuits"]#", vol.47, no.11, pp.2711-2723, Nov. 2012."], details: ([#hl("Junyoung Park")#", J. Kwon, J. Oh, S. Lee, J.-Y. Kim, and H.-J. Yoo."],))
  ]
  #entry(title: [#"Patents"], date: none, subtitle: none, side: none)[
    #item([#"KR102735092 이미지 분석을 위한 파생 이미지를 생성하기 위한 방법, 시스템 및 비일시성의 컴퓨터 판독 가능한 기록 매체"])
    #item([#"KR102619956 ToF 센서를 이용한 자동 개폐 안전 시스템 및 이의 제어방법"])
  ]
]
