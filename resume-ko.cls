% JUNYOUNG PARK KOREAN RESUME CLASS
% Author: Junyoung Park (mail@jyp.me)
% A denser, accent-colored layout tuned for Korean resumes (이력서).
% Differences from resume.cls: A4 paper, navy accent color, left-bar section
% titles, colored role line instead of italics (Korean fonts render italics
% poorly), tighter vertical rhythm, slightly increased leading for Hangul.

\ProvidesClass{resume-ko}[2026/08/11 v1.0 Korean resume class]

\LoadClass[10pt,a4paper]{article} % A4 is the standard paper size for Korean resumes

\usepackage[parfill]{parskip} % remove paragraph indentation
\usepackage{array} % required for boldface (\bf and \bfseries) tabular columns
\usepackage{ifthen} % required for ifthenelse statements
\usepackage{tabularx} % required for tabularx
\usepackage{fontawesome5} % required for icon
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref} % clickable links without borders
\urlstyle{same}
\pagestyle{empty} % suppress page numbers

\linespread{1.08} % Hangul glyphs are visually denser; a touch more leading

%---------------------------------------------------------------------------
% COLORS
%---------------------------------------------------------------------------

\definecolor{accent}{HTML}{1F4E79}   % deep navy
\definecolor{textgray}{HTML}{595959} % dates, contact info
\definecolor{rulegray}{HTML}{C9CDD4} % section underline

%---------------------------------------------------------------------------
% HEADINGS COMMANDS: Commands for printing name and address
%---------------------------------------------------------------------------

% fontawesome icons
\newcommand{\emailsymbol}{\faEnvelope}
\newcommand{\phonesymbol}{\faPhone}
\newcommand{\homepagesymbol}{\faLink}
\newcommand{\locationsymbol}{\faMapMarker}
\newcommand{\linkedinsymbol}{\faLinkedin}

\newcommand{\printinfo}[2]{\mbox{\textcolor{accent}{#1}\hspace{0.5em}\textcolor{textgray}{#2}\hspace{1.8em}}}

% personal info fields
% name and job title
\newcommand{\name}[1]{\def\@name{#1}}
\newcommand{\job}[1]{\def\@job{#1}}
% contact info
\newcommand{\email}[1]{\printinfo{\emailsymbol}{\href{mailto:#1}{#1}}}
\newcommand{\phone}[1]{\printinfo{\phonesymbol}{\href{tel:#1}{#1}}}
\newcommand{\homepage}[1]{\printinfo{\homepagesymbol}{\href{#1}{#1}}}
\newcommand{\location}[1]{\printinfo{\locationsymbol}{#1}}
\newcommand{\linkedin}[1]{\printinfo{\linkedinsymbol}{\href{#1}{#1}}}

\newcommand{\contactinfo}[1]{\def\@contactinfo{#1}}

% \makecvheader prints the name block followed by a bold accent rule
\newcommand \makecvheader {
  \begingroup
    \raggedright
    {\namesize\bfseries\@name\par}
    \vspace{2pt}
    {\large\bfseries\color{accent}\@job\par}
    \nameskip
    {\small\@contactinfo\par}
    \contactskip
    {\color{accent}\rule{\linewidth}{1.6pt}\par}
  \endgroup
}

%---------------------------------------------------------------------------
%	SECTION FORMATTING
%---------------------------------------------------------------------------

% Section title: accent bar on the left, thin gray underline
\renewenvironment{section}[1]{ % 1 input argument - section name
  \sectionskip
  {\noindent{\color{accent}\rule[-2.5pt]{3.5pt}{12pt}}\hspace{6pt}{\large\bfseries #1}\par}
  \nobreak\vspace{3pt}
  {\color{rulegray}\hrule height 0.6pt}
  \nobreak\vspace{1pt}
  \begin{list}{}{ % List for each individual item in the section
    \setlength{\leftmargin}{0.5em} % Margin within the section
    \setlength{\topsep}{2pt}
  }
  \item[]
}{
  \end{list}
}

%---------------------------------------------------------------------------
%	WORK EXPERIENCE FORMATTING
%---------------------------------------------------------------------------
% 4 input arguments - company name, year(s) employed, job title and location.
% The role line uses accent color instead of italics: Korean fonts have no
% true italics and slanted Hangul looks broken.
\renewenvironment{subsection}[4]{
  {\bfseries{#1}} \ifthenelse{\equal{#2}{}}{}{\hfill {\small\color{textgray}#2}} % Bold company name and gray date on the right
  \ifthenelse{\equal{#3}{}}{}{ % If the third argument is not specified, don't print the job title and location line
  \\[-1pt]
  {\color{accent}#3}\hfill {\small\color{textgray}#4} % Accent-colored job title and gray location
  }
  \begin{list}{\textcolor{accent}{\small$\cdot$}}{\leftmargin=1.0em % accent \cdot used for bullets
   \itemsep -0.5em \vspace{-0.5em} \topsep=1pt % Compress items in list together for aesthetics
  }
  }{
  \end{list}
  \vspace{1pt}
}

% The below commands define the whitespace after certain things in the document
\newcommand\namesize{\LARGE} % Size of the name at the top of the document
\newcommand\contactskip{\smallskip} % The space between the two address (or phone/email) lines
\newcommand\nameskip{\smallskip} % The space after your name at the top
\newcommand\sectionskip{\medskip} % The space after the heading section
