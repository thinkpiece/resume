% Resume LaTex Template
% Author: Junyoung Park (junyoung.park@kaist.ac.kr)
% Date: 2013/01/14

\ProvidesClass{resume}[2013/01/13 v1.0 Resume class]

\LoadClass[10pt,letterpaper]{article} % Font size and paper type

\usepackage[parfill]{parskip} % Remove paragraph indentation
\usepackage{array} % Required for boldface (\bf and \bfseries) tabular columns
\usepackage{ifthen} % Required for ifthenelse statements
\usepackage{tabularx} % Required for tabularx

\pagestyle{empty} % Suppress page numbers

%---------------------------------------------------------------------------
% HEADINGS COMMANDS: Commands for printing name and address
%---------------------------------------------------------------------------

% Defines the \name, \email, \phone, \address command to set name
\def \name#1{\def\@name{#1}}
\def \email#1{\def\@email{#1}}
\def \phone#1{\def\@phone{#1}}
\def \webpage#1{\def\@webpage{#1}}

% One, two or three address lines can be specified 
\let \@addressone \relax
\let \@addresstwo \relax
\let \@addressthree \relax

% \address command can be used to set the first, second, and third address (last 2 optional)
\def \address#1{
  \@ifundefined{@addressone}{
    \def \@addressone {#1}
  }{
  \@ifundefined{@addresstwo}{
    \def \@addresstwo {#1}
  }{
     \def \@addressthree {#1}
  }}
}

% Sets the followings to empty by default
\def \@name {}
\def \@email {}
\def \@phone {}
\def \@webpage {}
\def \addressSep {$\diamond$} % Set default address separator to a diamond

% \printname is used to print the name as a page header
\newcommand \printname {
  \begingroup
    \MakeUppercase{\namesize\bf \@name}
    \nameskip \\
  \endgroup
}

\newcommand \printcontacts {
  \begin{tabularx}{\textwidth}{ l>{\raggedleft\arraybackslash}X }
    \@addressone & \@phone\\
    \@addresstwo & \@email\\
    \@addressthree & \@webpage\\
  \end{tabularx}
  \addressskip
}
%---------------------------------------------------------------------------
% PRINT THE HEADING LINES
%---------------------------------------------------------------------------

\let\ori@document=\document
\renewcommand{\document}{
  \ori@document  % Begin document
  \printname     % Print the name specified with \name
  \printcontacts % Print the contact information 
}

%---------------------------------------------------------------------------
%	SECTION FORMATTING
%---------------------------------------------------------------------------

% Defines the Section environment for the large sections within the CV
\renewenvironment{section}[1]{ % 1 input argument - section name
  \sectionskip
  \MakeUppercase{\bf #1} % section title
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
\renewenvironment{subsection}[4]{ % 4 input arguments - company name, year(s) employed, job title and location
  {\bf #1} \ifthenelse{\equal{#2}{}}{}{\hfill {#2}} % Bold company name and date on the right
  \ifthenelse{\equal{#3}{}}{}{ % If the third argument is not specified, don't print the job title and location line
  \\
  {\em #3} \hfill {\em #4} % Italic job title and location
  } %\smallskip
  \begin{list}{$\cdot$}{\leftmargin=1.0em} % \cdot used for bullets, no indentation
   \itemsep -0.5em \vspace{-0.5em} % Compress items in list together for aesthetics
  }{
  \end{list}
}

% The below commands define the whitespace after certain things in the document - they can be \smallskip, \medskip or \bigskip
\newcommand\namesize{\Large} % Size of the name at the top of the document
\newcommand\addressskip{\smallskip} % The space between the two address (or phone/email) lines
\newcommand\sectionlineskip{\medskip} % The space above the horizontal line for each section 
\newcommand\nameskip{\medskip} % The space after your name at the top
\newcommand\sectionskip{\medskip} % The space after the heading section
