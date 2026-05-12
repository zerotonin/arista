# `scripts/` — proof-of-concept runners and one-off helpers

Standalone scripts that exercise the package against real data. Each
script is a thin orchestrator on top of code in `src/arista/` (or, for
v0.x, the legacy code under `_legacy/` while the rewrite is in flight).

Outputs from these runners go to **gitignored** directories by default
(`preprocessed_output/`, `figures/_build/`, etc.) so the repo stays
small.

## Catalogue

| Script | What it does | Default input | Default output |
|---|---|---|---|
| `preprocess_alex_data.py` | Runs the legacy `aristaSingleCellData.py` pipeline on every Fiji ΔF/F + temperature MAT pair under Alex Busch's bundled tree. Proof of concept for the preprocessing track. | `data/raw/alex/` | `preprocessed_output/alex/` |

## `preprocess_alex_data.py`

Headless (`matplotlib.use("Agg")`), so it runs in CI / over SSH /
without a desktop session. Outputs CSV + PNG per cell, named per
Alex's `getpropertiesFromOutPutFile()` convention:
`<strain>_<animalNum>_<sex>_<hemisphere>_<cellType>_<cellNum>_<date>.{csv,png}`.

```bash
# Default: process the bundled tree, write to preprocessed_output/alex/
python scripts/preprocess_alex_data.py

# Verbose (DEBUG-level logging + full tracebacks on failure)
python scripts/preprocess_alex_data.py -v

# Point at the HCS archive (note: HCS uses a different nested layout
# that scripts/preprocess_alex_data.py only partially handles; full
# coverage lands with arista-preprocess batch --layout alex in Phase 2)
python scripts/preprocess_alex_data.py --source /mnt/hcs/Alex/CalciumImaging

# Custom output dir (e.g. for a scratch volume)
python scripts/preprocess_alex_data.py --output /mnt/scratch/alex_preproc
```

### What's processed today

The runner walks `<source>/<genotype>/<animal>/` and processes any
animal directory that contains:
- at least one `temperature_data_*.mat` sensor file
- at least one `[lr]_*.csv` Fiji ROI export

In the **in-repo** `data/raw/alex/641/` tree this means **WT_01_f**
(4 cells) and **WT_02_m** (8 cells) — twelve cells total. The other
four animals (WT_03_f, WT_04_f, WT_05_f, WT_06_m) only have CSVs in
the repo; their sensor MATs live on `/mnt/hcs/Alex/CalciumImaging/641/`
under a deeper, time-stamped layout that the POC runner does not yet
walk. Skipped animals are listed in the runner's startup banner.

### What `arista-preprocess` will add (Phase 2)

The POC uses the legacy pipeline as-is, which means:
- **no drift correction** (`aristaSingleCellData.py` does alignment +
  Butterworth filter on the sensor T trace only — drift correction
  lives in `_legacy/pytci/tciAnalysis.py` and was not folded into
  Alex's class)
- **single-layout walker** (only `<genotype>/<animal>/[lr]_*.csv`)
- **filenames not metadata-rich** (genotype dir name is collapsed into
  the date stamp; e.g. genotype `641` does not appear in the output
  filename, only `Wildtype`)

The Phase 2 `arista-preprocess batch --layout alex` command supersedes
this script with: drift correction via AIC-picked fit, full HCS layout
support (`<genotype>/<date>/<exp>/Arista_<side>/`), and per-recording
metadata that flows through to the SQLite ingester.
