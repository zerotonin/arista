# `_legacy/` — preserved historical code

This directory holds the original preprocessing and analysis code that
predates the `arista` Python package refactor. It is **not** importable
by the package, **not** exercised by the test suite, and **not**
shipped as part of the release wheel.

It exists only so the scientific provenance of the analysis pipeline
remains in the same git repository as the code that supersedes it.

## Contents

| Path | Python | Author / era | Notes |
|---|---|---|---|
| `aristaSingleCellData.py` | 3 | Alexander Busch (with Bart edits), 2022 | Single-class duplicate of pytci's alignment + plotting logic that Alex wrote to preprocess his own Drosophila arista Ca²⁺-imaging recordings (commits 2022-01-20 → 2022-05-05 on the `Alex` git branch). Used to produce the `data/preprocessed/WT_CC_F_L_*` reference fixtures from his 641 / 2021-12-20 session. Retired once `arista.preprocess` reaches parity (sprint 2). |
| `pytci/` | 3 | Robert Kossen (2018-2021) | The active preprocessing package during Robert's PhD and Laurin Büld's MSc. Modules `tempFileIO`, `tciAnalysis`, `tciPlot`, `metaRegister`, `massiveAligner`, `autoMetaFinder`, `CLI_userDialogs`, `fileDialog`. **This is the reference implementation** that the new `arista.preprocess` module is a headless, type-hinted rewrite of. |
| `oldScripts/` | 2 | Robert Kossen (2014-2017) | Earliest pre-`pytci` work. Contains `print x` syntax, `reload()` without import, and `%matplotlib wx` IPython magic — **Python 2 only**. Paths inside reference `/home/rkossen/CalciumImagingData/...` which no longer exists. Preserved purely for archival reasons; not running again. |

## Why keep it?

1. Reviewers comparing the new pipeline against published figures from
   Kossen (2019) can audit the legacy maths directly.
2. The `pytci` code is the source of truth for column orders, default
   parameters, and the broken-MAT template rescue behaviour that the
   new module faithfully reproduces.
3. Git blame on the legacy tree continues to attribute work to its
   original authors.

## Why not just delete it after the refactor?

We will, eventually. The plan is to retire `aristaSingleCellData.py`
as soon as `tests/test_preprocess_against_legacy.py` passes (sprint 2)
and to retire `pytci/` as soon as all of its functionality is mirrored
in `arista.preprocess` with equivalent unit-test coverage (sprint 3).
`oldScripts/` stays indefinitely as a Python-2 archival snapshot.

## Will it run?

- `aristaSingleCellData.py` and `pytci/` will run under Python 3.11
  given their original dependencies (pandas, scipy, PyQt5, dill,
  matplotlib). PyQt5 file dialogs and the matplotlib drift-fit chooser
  block on a GUI — these are the parts the new `arista.preprocess`
  CLI removes.
- `oldScripts/` will **not** run under any modern Python. If you need
  to inspect its output, refer to `Robert Kossen — Master Thesis - Characerization of the T1 Neuron in Drosophila melanogaster.pdf`
  (in the lab Archive on `/mnt/hcs/Archive/Thesis/`).
