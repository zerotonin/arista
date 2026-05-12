# arista

[![tests](https://github.com/zerotonin/arista/actions/workflows/tests.yml/badge.svg)](https://github.com/zerotonin/arista/actions/workflows/tests.yml)
[![docs](https://github.com/zerotonin/arista/actions/workflows/docs.yml/badge.svg)](https://zerotonin.github.io/arista)
[![release](https://github.com/zerotonin/arista/actions/workflows/release.yml/badge.svg)](https://github.com/zerotonin/arista/releases)
[![python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/arista-thermosensation/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/placeholder.svg)](https://zenodo.org/record/placeholder)

*Calcium-imaging corpus and analysis package for the thermosensory
neurons of the *Drosophila melanogaster* arista.*

The package brings ~700 calcium-imaging recordings spanning three students
(Robert Kossen, Niko, Laurin Büld) and twelve years of data acquisition
into a single SQLite database, ships a headless preprocessing CLI that
reproduces the original `pytci` pipeline on user-supplied raw data, and
rebuilds the publication figures supporting the role of **NompC** in
*Drosophila* thermosensation.

## Why this package exists

1. **One database.** Eight years of calcium-imaging recordings of the
   three hot cells and three cold cells of the *Drosophila* arista,
   normalised into a single SQLite file.
2. **Reproducible preprocessing.** `arista-preprocess` takes a Fiji
   ΔF/F₀ export and a MATLAB sensor MAT and produces the same
   drift-corrected, frame-aligned CSV that the original `pytci` package
   produced for our paper — without the matplotlib drift-fit chooser
   that blocked headless / batch / CI operation.
3. **Re-derivable figures.** `arista-figs` rebuilds every published
   figure from the database in a single command.

The reproducibility track exists specifically so reviewers can rerun
the preprocessing on their own raw Ca²⁺ data, not just inspect our
outputs.

## Quickstart

```bash
# install
pip install arista-thermosensation
# or, from a Zenodo source bundle:
pip install -e .

# preprocess one recording on the shipped fixtures
arista-preprocess align \
    data/fiji/HC01.csv \
    data/sensor/temperature_data_2021_12_20-12_40.mat \
    -o aligned.csv
arista-preprocess drift aligned.csv -o corrected.csv --method auto

# walk a directory of your own raw Ca²⁺ data
arista-preprocess batch my_raw_data/ -o preprocessed/ --layout generic

# build the database and rebuild figures
arista-ingest --root preprocessed/ --db arista.db
arista-figs   --db arista.db --output figures/
```

Full tutorial: <https://zerotonin.github.io/arista/quickstart.html>

## Repository layout

```
src/arista/
├── constants.py          Wong palette, stimulus dict, save_figure helper
├── preprocess/           headless rebuild of the pytci pipeline (sprints 2-3)
├── ingest/               loads preprocessed CSVs into SQLite      (sprints 5-6)
├── processing/           per-step response medians, adaptation τ (sprint 7)
├── fitting/              sigmoid + linear-fit gain               (sprint 8)
├── viz/                  publication figure builders             (sprint 8)
├── db/                   SQLite schema, seeds, queries           (sprint 2)
└── cli/                  arista-preprocess / -ingest / -figs

data/                     demo fixtures (Fiji + sensor + reference output)
tests/                    fixture-based unit + smoke tests
docs/                     Sphinx with RTD theme (deployed to GitHub Pages)
_legacy/                  preserved original code (Robert's pytci + 2014 scripts)
```

## Scientific provenance

The corpus consolidates:

- **Robert Kossen** (PhD, Göttingen 2019), *"Thermosensory Transduction
  Mechanisms in Drosophila melanogaster"* — 562 recordings spanning
  thirteen genotypes and seven stimulus protocols.
- **Niko** (MSc, Göttingen 2016) — sixteen wildtype `ascAmp` recordings
  that became Robert's `NSybLexALexOpGCamp6/` baseline.
- **Laurin Büld** (MSc, Göttingen 2020-21) — 116 `adaptation` recordings
  in `nompC` mutants, never previously combined with Robert's data.
- **Alexander Busch** (post-BSc lab work, Göttingen 2021-22) — ~35 raw
  recordings in three genotypes (`605`, `641`, `nomp_C`) preprocessed
  here through `arista-preprocess` for the first time. Contributed
  `aristaSingleCellData.py` (preserved in `_legacy/`).

Each recording carries provenance back to its source file via sha256,
ingest timestamp, and a path reference in the `source_files` table.

## Development

```bash
git clone https://github.com/zerotonin/arista.git
cd arista
pip install -e ".[dev]"
pytest
```

Build the docs locally with the exact CI command:

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs/ docs/_build/html
```

## Citation

If you use this software or the bundled dataset, please cite as in
[`CITATION.cff`](CITATION.cff) — the GitHub UI will render a
"Cite this repository" widget, and `pip install cffconvert` can
produce BibTeX or other formats. The Zenodo DOI tagged to each
`vX.Y.Z` release is the preferred archival citation.

## Licence

[MIT](LICENSE). © 2026 Bart R. H. Geurten.
