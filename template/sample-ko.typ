// Korean exercise of the template API (lang "ko", Pretendard, A4), in the shape
// the generator emits. Uses real lines from the Korean resume, plus bullets
// directly under a section and a shared English publication line.
// Compile from the repo root:
//   typst compile --root . template/sample-ko.typ build/sample-ko.pdf
#import "/template/resume.typ": *
#show: resume.with(
  name: "박준영 (Junyoung Park)",
  title: "AI 시스템 반도체(SoC) 스타트업 대표이사",
  lang: "ko",
  paper: "a4",
  fonts: ("Pretendard",),
  contacts: (
    (kind: "location", text: "경기도 성남시 (13105)", url: none),
    (kind: "phone", text: "+82-10-2542-5500", url: "tel:+821025425500"),
    (kind: "email", text: "junyoung@uxf.ai", url: "mailto:junyoung@uxf.ai"),
    (kind: "homepage", text: "http://www.junyoungpark.com", url: "http://www.junyoungpark.com"),
  ),
)
#section([#"핵심 요약"])[
  #item([#"KAIST 전기및전자공학 박사 출신 AI 반도체(SoC) 전문가, 창업 후 10년간 기업 경영 (2015 – 현재)"])
  #item([#"저전력 AI·비전 SoC 설계 전문: 국제 저널·학회 논문 37편, 등록 특허 20건, ISSCC 발표 및 시연"])
  #item([#"연구개발과 사업화를 잇는 실행력: 산·학·연 R&D 프로젝트 20건 이상 주도, 초청강연 20여 회"])
]
#section([#"경력"])[
  #entry(title: [#"(주)유엑스팩토리 (UX Factory, Inc.)"], date: [#"2015.08 – 현재"], subtitle: [#"공동창업자 및 대표이사 (CEO)"], side: [#"경기도 성남시"])[
    #item([#"AI SoC(시스템 반도체) 기술 기반의 AI 솔루션 전문 기업 창업 및 경영"])
    #item([#"국내외 주요 기업, 대학 및 연구소와 AI·SoC 분야 R&D 프로젝트 20건 이상 수행"])
  ]
  #entry(title: [#"KAIST"], date: [#"2015.01 – 2015.08"], subtitle: [#"박사후연구원"], side: none)[
    #item([#"하드웨어–소프트웨어 통합설계 방법론 기반 비전·딥러닝용 SoC 아키텍처 연구"])
  ]
]
#section([#"학력"])[
  #entry(title: [#"KAIST 전기및전자공학과 박사"], date: [#"2014.08"], subtitle: none, side: none)[
    #item([#"학위논문: 에너지 효율적인 상황인지 실시간 객체인식 프로세서"])
    #item([#"저전력 비전 SoC 설계·구현, IEEE ISSCC(국제고체회로학회) 발표 및 시연"])
  ]
  #entry(title: [#"KAIST 전기및전자공학과 학사"], date: [#"2009.02"], subtitle: none, side: none)[
    #item([#"최우등 졸업 (Summa Cum Laude)"])
  ]
]
#section([#"수상 및 활동"])[
  #entry(title: [#"주요 수상"], date: none, subtitle: none, side: none)[
    #item([#"CAGI7 국제 유전체 해석 챌린지 TSC2 부문 Top-performer"], date: [#"2025.12"])
    #item([#"김충기 장학상 (우수 연구 업적)"], date: [#"2013.04"])
  ]
  #entry(title: [#"학술 및 대외 활동"], date: none, subtitle: none, side: none)[
    #item([#"IEEE Asian Solid-State Circuits Conference 기술프로그램위원(TPC)"], date: [#"2018 – 현재"])
    #item([#"국가연구개발사업 평가위원 (범부처통합연구지원시스템), 줄바꿈을 확인하기 위해 일부러 길게 늘인 활동 항목으로 날짜 열 앞에서 어절 단위로 줄이 바뀌어야 함"], date: [#"2017 – 현재"])
    #item([#"AI 반도체 관련 초청강연 20여 회 이상 (KAIST, ETRI, 반도체산업협회, 대한전자공학회 등)"])
  ]
]
#section([#"연구 실적"])[
  #paragraph([#"국제 저널 논문 10편 (IEEE JSSC 등), 국제 학회 논문 27편 (ISSCC, CICC, A-SSCC 등). 아래는 공유 목록에서 가져온 영문 항목입니다."])
  #entry(title: [#"국제 저널 논문"], date: none, subtitle: none, side: none)[
    #item([#"A 0.5 V 54 μW Ultra-Low-Power Object Matching Processor for Micro Air Vehicle Navigation, "#emph[#"IEEE Transactions on Circuits and Systems I: Regular Papers"]#", vol.63, no.3, pp.359-369, Mar. 2016."], details: ([#"Y. Kim, I. Hong, "#hl("Junyoung Park")#", H.-J. Yoo."],))
  ]
  #entry(title: [#"특허"], date: none, subtitle: none, side: none)[
    #item([#"KR102735092 이미지 분석을 위한 파생 이미지를 생성하기 위한 방법, 시스템 및 비일시성의 컴퓨터 판독 가능한 기록 매체"])
  ]
]
