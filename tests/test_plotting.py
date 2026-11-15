"""Tests for the shared figure style (en630.plotting)."""

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from en630.plotting import SEQ_BLUE, SERIES, SURFACE, apply_theme, save


def test_theme_sets_surface_and_series_cycle():
    apply_theme()
    assert mpl.rcParams["figure.facecolor"] == SURFACE
    cycle = [c["color"] for c in mpl.rcParams["axes.prop_cycle"]]
    assert cycle[:3] == SERIES


def test_series_colours_are_distinct():
    assert len(set(SERIES)) == len(SERIES)


def test_sequential_ramp_gets_monotonically_darker():
    # A magnitude ramp must be ordered by lightness or the heatmaps mislead.
    rgb = SEQ_BLUE(np.linspace(0, 1, 32))[:, :3]
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722])
    assert (np.diff(luminance) < 0).all()


def test_save_creates_folder_and_file(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    out = save(fig, tmp_path / "nested" / "fig.png")
    plt.close(fig)
    assert out.exists() and out.stat().st_size > 0
