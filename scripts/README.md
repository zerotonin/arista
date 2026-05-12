# `scripts/` — runners and one-off helpers

Standalone scripts that exercise the package against real data. Each
script is a thin orchestrator on top of `arista.preprocess` (and, where
historical comparison is useful, the preserved `_legacy/` code).

Outputs from these runners go to **gitignored** directories by default
(`preprocessed_output/`, `figures/_build/`, …) so the repo stays small.

## Catalogue

| Script | What it does | Default input | Default output |
|---|---|---|---|
| `preprocess_alex_data.py` | Walks an Alex-style Drosophila arista Ca²⁺ tree recursively, runs `arista.preprocess` end-to-end (read → align → drift-correct → write CSV) on every recording. | `data/raw/alex/` | `preprocessed_output/alex/` |

## `preprocess_alex_data.py`

Headless (`matplotlib.use("Agg")`), runs in CI / over SSH /
without a desktop session. Uses **`arista.preprocess`** — no legacy
dependency. Drift correction is AIC-picked by default per recording.

### Usage

```bash
# Default: process the bundled tree, AIC-pick drift per recording
python scripts/preprocess_alex_data.py

# Verbose (DEBUG-level logging + full tracebacks on failure)
python scripts/preprocess_alex_data.py -v

# Process the full HCS archive (handles the deeper layout
# <genotype>/<date>/<exp>/Arista_<side>/ automatically)
python scripts/preprocess_alex_data.py --source /mnt/hcs/Alex/CalciumImaging

# Force a specific drift method (matches the legacy pytci chooser keys)
python scripts/preprocess_alex_data.py --drift-method poly

# Skip drift correction (useful for byte-comparison with legacy)
python scripts/preprocess_alex_data.py --drift-method none

# Custom output dir (e.g. for a scratch volume)
python scripts/preprocess_alex_data.py --output /mnt/scratch/alex_preproc
```

### Discovery

The runner walks `<source>` recursively and treats any directory
containing both:

- exactly one `temperature_data_*.mat` sensor file
- at least one Fiji ΔF/F CSV (`is_fiji_csv()` accepts `l_CC01.csv`,
  `r_HC02.csv`, `CC_01.csv`, `HC_02.csv`, `CC01.csv`, `HC02.csv` and
  lower-case variants)

as a recording session, **regardless of nesting depth**. The bundled
flat layout (`data/raw/alex/641/WT_NN_sex/`) and the HCS deep layout
(`<genotype>/<date>/<exp>/Arista_<side>/`) are both handled by the
same code path.

Output mirrors the input directory structure under `<output>` —
e.g. `data/raw/alex/641/WT_01_f/l_CC01.csv` →
`preprocessed_output/alex/641/WT_01_f/l_CC01.csv`. The output CSV
carries a `# drift_method: <method>` header line so provenance
travels with the data and `arista.preprocess.read_recording_csv` can
round-trip it.

### Coverage on real corpora

| Corpus | Eligible sessions | Cells | Skipped sessions |
|---|---|---|---|
| `data/raw/alex/` (in-repo subset) | 2 | 12 | 4 (no MAT in repo — MATs live on HCS) |
| `/mnt/hcs/Alex/CalciumImaging/` | 9 | 30 | 5 (MAT present but no Fiji CSVs — incomplete sessions) |

Skipped sessions are listed in the startup banner with the reason so
the coverage gap is always visible.

### Library API

The runner is a thin wrapper; everything it does is also available as
a library:

```python
from arista.preprocess import (
    read_fiji_csv, read_sensor_mat,
    assemble_recording, correct_drift,
    write_recording_csv,
)

fiji   = read_fiji_csv("my_data/HC01.csv")
sensor = read_sensor_mat("my_data/temperature_data_2025_03_01-12_00.mat")
rec    = assemble_recording(fiji, sensor)
rec    = correct_drift(rec, method="auto")   # AIC-picked
write_recording_csv(rec, "out/my_data_HC01.csv")
```

See `src/arista/preprocess/__init__.py` for the full public surface.
