# to generate the .pdf files from .tex file

SRCS := $(shell find . -name "*.tex")
PDFS := $(SRCS:%.tex=%.pdf)

pdf: $(PDFS) $(SRCS)
	@echo "Successfully generated .pdf files from the corresponding .tex files."

$(PDFS): %.pdf : %.tex
	@lualatex $<

all: pdf

clean:
	@- rm -rf *.aux *.dvi *.log *.pdf
