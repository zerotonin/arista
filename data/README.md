# Demo data — shipped with the `arista` package

A minimal set of fixtures used by the package's quickstart tutorial,
CI smoke tests, and the unit tests for the preprocessing pipeline.

These files travel with the source distribution and the Zenodo release so
anyone can run `arista-preprocess` end-to-end without `/mnt/hcs` access.

## Provenance

All four input files come from a single recording session on **2021-12-20**
by **Alexander Busch** in the Geurten lab, copied out of
`/mnt/hcs/Alex/CalciumImaging/641/2021_12_20/exp02/Arista_left/`. The fly
was *Drosophila melanogaster* genotype `641` (female, left arista),
imaged at 10 fps on the Zeiss Axio Examiner.D1. Three ROIs were exported
from Fiji on the same image stack: one cold cell (`CC01`) and two hot
cells (`HC01`, `HC02`).

The `preprocessed/WT_CC_F_L_*` reference output was produced by Alex's
own `aristaSingleCellData.py` (now in `_legacy/`) on the same inputs,
and serves as the byte-level regression target for the new
`arista.preprocess` module.

| File | Source | Description |
|---|---|---|
| `fiji/CC01.csv`  | Fiji `Plot Profile` → CSV | 2-column (X = frame, Y = ΔF/F₀) for the cold-cell ROI |
| `fiji/HC01.csv`  | Fiji | Hot-cell ROI #1, same stack |
| `fiji/HC02.csv`  | Fiji | Hot-cell ROI #2, same stack |
| `sensor/temperature_data_2021_12_20-12_40.mat` | MATLAB recording GUI | 5-column array of `[epoch_time, frame, sensor_T, target_T, drive_T]`, continuous logging through the recording |
| `preprocessed/WT_CC_F_L_2021-12-20--12-30-26.csv` | legacy `aristaSingleCellData.py` run | Reference output of the prior pipeline for byte-level regression testing of the new `arista.preprocess` module |
| `preprocessed/WT_CC_F_L_2021-12-20--12-30-26.png` | legacy plotting | Reference figure produced alongside the reference CSV |

## Stimulus protocol

`ascAmp` — ascending-amplitude steps around 22 °C: 22.0, 22.5, 21.5,
23.0, 21.0, 24.0, 20.0, 26.0, 18.0 °C, 60 s per step after a 75 s
baseline. See `arista.constants.STIMULUS_PROTOCOLS` once that module
is populated (sprint 2).

## How the fixtures are used

- **Tests.** `tests/test_smoke.py` resolves these paths via
  `arista.constants.FIJI_FIXTURE_DIR` / `SENSOR_FIXTURE_DIR` and
  asserts at least one CSV and one MAT are present.
- **Tutorial.** `docs/quickstart.rst` and `docs/notebooks/preprocess_demo.ipynb`
  (added in sprint 10) run the full `arista-preprocess` pipeline on
  these files end-to-end.
- **Regression.** `tests/test_preprocess_against_legacy.py` (sprint 2)
  asserts the new `arista.preprocess` output matches the
  `preprocessed/` reference within float tolerance, gating any
  refactor that would otherwise silently change the maths.

## Licence

Released under the same MIT licence as the package source. Anonymous
recording metadata only; no animal identifiers beyond strain / sex /
age in days are retained.
