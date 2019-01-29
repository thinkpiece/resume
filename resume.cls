% JUNYOUNG PARK RESUME TEX TEMPLATE
% Author: Junyoung Park (mail@jyp.me)
% History:
%   2015/07/21 - first version in KAIST
%   2019/01/26 - second major update in UXFactory, Inc.

\ProvidesClass{resume}[2013/01/13 v1.0 Resume class]

\LoadClass[10pt,letterpaper]{article} % Font size and paper type

\usepackage[parfill]{parskip} % remove paragraph indentation
\usepackage{array} % required for boldface (\bf and \bfseries) tabular columns
\usepackage{ifthen} % required for ifthenelse statements
\usepackage{tabularx} % required for tabularx
\usepackage{fontawesome} % required for icon
\usepackage{xcolor}
\pagestyle{empty} % suppress page numbers

%---------------------------------------------------------------------------
% HEADINGS COMMANDS: Commands for printing name and address
%---------------------------------------------------------------------------

% brand color
\colorlet{accent}{black}

% fontawesome icons
\newcommand{\emailsymbol}{\faEnvelope}
\newcommand{\phonesymbol}{\faPhone}
\newcommand{\homepagesymbol}{\faLink}
\newcommand{\locationsymbol}{\faMapMarker}
\newcommand{\linkedinsymbol}{\faLinkedin}

\newcommand{\printinfo}[2]{\mbox{\textcolor{accent}{#1}\hspace{0.5em}#2\hspace{2em}}}

% personal info fields
% name and job title
\newcommand{\name}[1]{\def\@name{#1}}
\newcommand{\job}[1]{\def\@job{#1}}
% contact info
\newcommand{\email}[1]{\printinfo{\emailsymbol}{#1}}
\newcommand{\phone}[1]{\printinfo{\phonesymbol}{#1}}
\newcommand{\homepage}[1]{\printinfo{\homepagesymbol}{#1}}
\newcommand{\location}[1]{\printinfo{\locationsymbol}{#1}}
\newcommand{\linkedin}[1]{\printinfo{\linkedinsymbol}{#1}}

\newcommand{\contactinfo}[1]{\def\@contactinfo{#1}}

% \printname is used to print the name as a page header
\newcommand \makecvheader {
  \begingroup
    \raggedright
    {\namesize\bfseries\MakeUppercase{\@name}\par}
    {\large\@job\par}
    \nameskip
    {\@contactinfo\par}
    \contactskip
  \endgroup
}

%---------------------------------------------------------------------------
%	SECTION FORMATTING
%---------------------------------------------------------------------------

% Defines the Section environment for the large sections within the CV
\renewenvironment{section}[1]{ % 1 input argument - section name
  \sectionskip
  {\large\bfseries\MakeUppercase{#1}\par} % section title
  \sectionlineskip
  \hrule % Horizontal line
  \begin{list}{}{ % List for each individual item in the section
    \setlength{\leftmargin}{0.5em} % Margin within the section
  }
  \item[]
}{
  \end{list}
}

%---------------------------------------------------------------------------
%	WORK EXPERIENCE FORMATTING
%---------------------------------------------------------------------------
% TODO: need to update the location field for better place - currently not used
\renewenvironment{subsection}[4]{ % 4 input arguments - company name, year(s) employed, job title and location
  {\large\bfseries{#1}} \ifthenelse{\equal{#2}{}}{}{\hfill {#2}} % Bold company name and date on the right
  \ifthenelse{\equal{#3}{}}{}{ % If the third argument is not specified, don't print the job title and location line
  \\
  {\em #3}\hfill {#4} % Italic job title and normal location
  } %\smallskip
  \begin{list}{$\cdot$}{\leftmargin=1.0em} % \cdot used for bullets, no indentation
   \itemsep -0.5em \vspace{-0.5em} % Compress items in list together for aesthetics
  }{
  \end{list}
}

% The below commands define the whitespace after certain things in the document - they can be \smallskip, \medskip or \bigskip
\newcommand\namesize{\LARGE} % Size of the name at the top of the document
\newcommand\contactskip{\smallskip} % The space between the two address (or phone/email) lines
\newcommand\sectionlineskip{\medskip} % The space above the horizontal line for each section 
\newcommand\nameskip{\medskip} % The space after your name at the top
\newcommand\sectionskip{\medskip} % The space after the heading section
