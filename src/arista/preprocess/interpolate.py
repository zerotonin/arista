# ─────────────────────────────────────────────────────────────────
#  arista.preprocess.interpolate  « stage B »
# ─────────────────────────────────────────────────────────────────
"""Fill DAQ-dropped frames via linear interpolation."""

from __future__ import annotations

import pandas as pd


def interpolate_missing_frames(per_frame: pd.DataFrame) -> pd.DataFrame:
    """Linearly interpolate NaN values in a per-frame dataframe.

    Replicates ``aristaSingleCellData.interpolateMissingFrames``: any
    NaN values left after :func:`arista.preprocess.align.collapse_to_frames`
    has reindexed the per-frame table to a contiguous integer range are
    filled by ``DataFrame.interpolate(method="linear")``.

    Args:
        per_frame: DataFrame whose index is the integer frame number.
            Typical columns are ``epoch_time`` / ``sensor_t_c`` /
            ``target_t_c`` / ``drive_t_c`` but the function is agnostic.

    Returns:
        A new DataFrame with NaNs filled. The index is preserved.
    """
    return per_frame.interpolate(method="linear")
