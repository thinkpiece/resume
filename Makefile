# Build the resume PDFs from content/ (Markdown) through Typst.
#   make            all four PDFs in build/
#   make en-short   one of them (en-full, en-short, ko-full, ko-short)
#   make test       unit tests
#   make clean      remove build/

PYTHON ?= python3
BUILD := build
NAME := Resume_JunyoungPark

EN_FULL  := $(BUILD)/$(NAME)_en_full.pdf
EN_SHORT := $(BUILD)/$(NAME)_en_short.pdf
KO_FULL  := $(BUILD)/$(NAME)_ko_full.pdf
KO_SHORT := $(BUILD)/$(NAME)_ko_short.pdf
PDFS := $(EN_FULL) $(EN_SHORT) $(KO_FULL) $(KO_SHORT)

.PHONY: all en-full en-short ko-full ko-short test clean FORCE

all: $(PDFS)

en-full: $(EN_FULL)
en-short: $(EN_SHORT)
ko-full: $(KO_FULL)
ko-short: $(KO_SHORT)

# The PDFs always rebuild: Typst takes well under a second, and a file-list
# prerequisite would miss a deleted or renamed @include.
$(BUILD)/$(NAME)_%_full.pdf: FORCE
	$(PYTHON) scripts/build_resume.py content/$*/resume.md --variant full -o $@

$(BUILD)/$(NAME)_%_short.pdf: FORCE
	$(PYTHON) scripts/build_resume.py content/$*/resume.md --variant short -o $@

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf $(BUILD)

FORCE:
