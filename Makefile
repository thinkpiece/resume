# Build .pdf files from .tex sources
ENGINE ?= lualatex
ENGINE_FLAGS ?= -interaction=nonstopmode -halt-on-error -file-line-error

TEX_SRCS := $(wildcard *.tex)
PDFS := $(TEX_SRCS:.tex=.pdf)

.PHONY: all pdf clean

all: pdf

pdf: $(PDFS)
	@echo "Successfully generated .pdf files from the corresponding .tex files."

%.pdf: %.tex resume.cls
	@$(ENGINE) $(ENGINE_FLAGS) $<

clean:
	@rm -f *.aux *.log *.out *.synctex.gz *.fdb_latexmk *.fls texput.log
