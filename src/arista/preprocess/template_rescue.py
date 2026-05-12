# ─────────────────────────────────────────────────────────────────
#  arista.preprocess.template_rescue  « broken-MAT detection »
# ─────────────────────────────────────────────────────────────────
"""Detect a broken / truncated sensor MAT file.

In Robert's original pytci pipeline a ``temperature_data_*.mat`` with
fewer than 1000 rows was treated as corrupt; the sensor trace was
then substituted from a pre-computed median template stored in
``_legacy/pytci/brokenTempFile_adap.pkl`` (only the ``adaptation``
protocol template was ever generated).

For v0.1 we only ship the **detection** half — actual substitution
needs the per-protocol templates regenerated against the corpus, which
is a sprint-7 task once the DB exists. Calling :func:`load_template`
today raises :class:`NotImplementedError` and points the user at the
issue tracker.
"""

from __future__ import annotations

from arista.preprocess.io import SensorRecord

_BROKEN_MAT_ROW_THRESHOLD: int = 1000


def is_broken_sensor(
    sensor: SensorRecord,
    min_rows: int = _BROKEN_MAT_ROW_THRESHOLD,
) -> bool:
    """Return True if a sensor MAT file looks truncated.

    The heuristic mirrors pytci: a full recording logs the sensor at
    a much higher rate than the imaging frame rate, so an honest MAT
    file has thousands of rows. Anything substantially smaller is
    almost certainly a partially-written file from a crashed
    acquisition.

    Args:
        sensor: Sensor record from :func:`arista.preprocess.io.read_sensor_mat`.
        min_rows: Threshold below which we declare the file broken
            (default 1000, matching pytci).
    """
    return sensor.n_samples < min_rows


def load_template(stimulus_name: str) -> SensorRecord:
    """Substitute a median-template sensor trace for a broken MAT.

    Not yet implemented in v0.1; raises with a clear pointer to the
    sprint plan rather than silently returning bogus data.

    Args:
        stimulus_name: Canonical stimulus name (e.g. ``"adaptation"``).
    """
    raise NotImplementedError(
        f"Template rescue for stimulus {stimulus_name!r} is not implemented "
        f"in v0.1. Regenerate the per-protocol median templates from the "
        f"corpus once the DB is populated (sprint 7) and re-enable this "
        f"function. Until then, recordings with broken sensor MATs must be "
        f"manually flagged with qc_flag='broken_temp' on ingest."
    )
