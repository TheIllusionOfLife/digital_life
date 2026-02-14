.PHONY: all figures paper clean

all: figures paper

figures:
	cd .. && uv run python scripts/generate_figures.py

paper: figures
	tectonic main.tex

clean:
	rm -f *.aux *.bbl *.blg *.log *.out main.pdf
	rm -f figures/*.pdf
