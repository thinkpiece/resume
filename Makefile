# Build the resume from content/ (Markdown) as PDF (through Typst), HTML and DOCX.
#   make            all twelve files in build/ (en, ko × full, short × pdf, html, docx)
#   make pdf        the four PDFs (also: make html, make docx)
#   make en-short   one variant in all three formats (en-full, en-short, ko-full, ko-short)
#   make test       unit tests
#   make clean      remove build/

PYTHON ?= python3
BUILD := build
NAME := Resume_JunyoungPark

VARIANTS := en_full en_short ko_full ko_short
PDFS  := $(VARIANTS:%=$(BUILD)/$(NAME)_%.pdf)
HTMLS := $(VARIANTS:%=$(BUILD)/$(NAME)_%.html)
DOCXS := $(VARIANTS:%=$(BUILD)/$(NAME)_%.docx)

.PHONY: all pdf html docx en-full en-short ko-full ko-short test clean FORCE

all: $(PDFS) $(HTMLS) $(DOCXS)

pdf: $(PDFS)
html: $(HTMLS)
docx: $(DOCXS)

en-full:  $(addprefix $(BUILD)/$(NAME)_en_full.,pdf html docx)
en-short: $(addprefix $(BUILD)/$(NAME)_en_short.,pdf html docx)
ko-full:  $(addprefix $(BUILD)/$(NAME)_ko_full.,pdf html docx)
ko-short: $(addprefix $(BUILD)/$(NAME)_ko_short.,pdf html docx)

# Every output always rebuilds: each takes well under a second, and a
# file-list prerequisite would miss a deleted or renamed @include.
# The stem is <lang>_<variant>.<ext>, e.g. ko_short.docx; build_resume.py
# picks the format from the extension.
$(BUILD)/$(NAME)_%: FORCE
	$(PYTHON) scripts/build_resume.py content/$(word 1,$(subst _, ,$*))/resume.md \
		--variant $(basename $(word 2,$(subst _, ,$*))) -o $@

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf $(BUILD)

FORCE:
