# ─────────────────────────────────────────────────────────────────
#  Tests for arista.viz._raincloud primitives
# ─────────────────────────────────────────────────────────────────
"""Half-violin + box + jittered strip primitives."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from arista.viz._raincloud import (  # noqa: E402
    boxplot_at,
    half_violin,
    jittered_strip,
    raincloud,
)

# ─────────────────────────────────────────────────────────────────
#  half_violin
# ─────────────────────────────────────────────────────────────────


def test_half_violin_adds_a_polygon() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, size=50)
    before = len(ax.collections)
    half_violin(ax, values, position=1.0, color="#abcdef")
    after = len(ax.collections)
    assert after > before  # fill_betweenx adds a PolyCollection
    plt.close(fig)


def test_half_violin_silently_skips_tiny_sample() -> None:
    fig, ax = plt.subplots()
    before = len(ax.collections)
    half_violin(ax, np.array([0.5]), position=1.0)
    half_violin(ax, np.array([]), position=2.0)
    half_violin(ax, np.array([np.nan, np.nan]), position=3.0)
    assert len(ax.collections) == before
    plt.close(fig)


def test_half_violin_silently_skips_zero_variance() -> None:
    fig, ax = plt.subplots()
    before = len(ax.collections)
    half_violin(ax, np.full(20, 0.7), position=1.0)
    assert len(ax.collections) == before
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  boxplot_at
# ─────────────────────────────────────────────────────────────────


def test_boxplot_at_adds_artists() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    boxplot_at(ax, rng.normal(0, 1, size=20), position=2.0)
    assert len(ax.patches) >= 1
    plt.close(fig)


def test_boxplot_at_silently_skips_empty() -> None:
    fig, ax = plt.subplots()
    boxplot_at(ax, np.array([]), position=2.0)
    boxplot_at(ax, np.array([np.nan, np.nan]), position=3.0)
    assert len(ax.patches) == 0
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  jittered_strip
# ─────────────────────────────────────────────────────────────────


def test_jittered_strip_places_n_points() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = np.linspace(0, 1, 25)
    jittered_strip(ax, values, position=1.0, rng=rng)
    # Last PathCollection corresponds to the scatter call we just made.
    collection = ax.collections[-1]
    assert collection.get_offsets().shape[0] == 25
    plt.close(fig)


def test_jittered_strip_respects_side() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = np.array([0.5] * 30)
    jittered_strip(ax, values, position=1.0, side="right", rng=rng, width=0.2)
    xs = ax.collections[-1].get_offsets()[:, 0]
    assert (xs >= 1.0).all() and (xs <= 1.2).all()
    plt.close(fig)

    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    jittered_strip(ax, values, position=1.0, side="left", rng=rng, width=0.2)
    xs = ax.collections[-1].get_offsets()[:, 0]
    assert (xs <= 1.0).all() and (xs >= 0.8).all()
    plt.close(fig)


def test_jittered_strip_with_marker_array_splits_by_glyph() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = np.linspace(0, 1, 6)
    markers = np.array(["<", ">", "o", "<", ">", "o"])
    before = len(ax.collections)
    jittered_strip(ax, values, position=1.0, rng=rng, markers=markers)
    after = len(ax.collections)
    assert after - before == 3  # one scatter per unique glyph
    plt.close(fig)


def test_jittered_strip_silently_skips_empty() -> None:
    fig, ax = plt.subplots()
    before = len(ax.collections)
    jittered_strip(ax, np.array([np.nan, np.nan]), position=1.0)
    assert len(ax.collections) == before
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────
#  raincloud compound
# ─────────────────────────────────────────────────────────────────


def test_raincloud_renders_all_three_layers() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = rng.normal(0.1, 0.05, size=40)
    n_collections_before = len(ax.collections)
    n_patches_before = len(ax.patches)
    raincloud(ax, values, position=1.0, color="#0072B2", rng=rng)
    # Half-violin adds a PolyCollection; strip adds a PathCollection;
    # boxplot adds a Patch.
    assert len(ax.collections) >= n_collections_before + 2
    assert len(ax.patches) > n_patches_before
    plt.close(fig)


def test_raincloud_with_hemisphere_array_uses_arrow_markers() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    values = np.linspace(0, 0.2, 6)
    hemispheres = np.array(["l", "l", "r", "r", None, None])
    n_before = len(ax.collections)
    raincloud(ax, values, position=1.0, color="#E69F00",
              rng=rng, hemispheres=hemispheres)
    # 1 violin + 3 strip scatters (one per unique marker: <, >, o)
    assert len(ax.collections) - n_before >= 4
    plt.close(fig)


def test_raincloud_handles_tiny_sample_without_crashing() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    raincloud(ax, np.array([0.3]), position=1.0,
              color="#222222", rng=rng)
    # No assertion needed — we only require that it doesn't raise
    plt.close(fig)


def test_raincloud_empty_values_no_op() -> None:
    fig, ax = plt.subplots()
    rng = np.random.default_rng(0)
    n_before = (len(ax.collections), len(ax.patches))
    raincloud(ax, np.array([]), position=1.0,
              color="#222222", rng=rng)
    assert (len(ax.collections), len(ax.patches)) == n_before
    plt.close(fig)
