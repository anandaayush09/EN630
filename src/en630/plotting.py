"""Shared figure style: one palette, one theme, so every plot in the project reads as a set.

Design rules (data-visualisation practice, kept deliberately small):

* **Colour has one job per chart.** Two data sources are blue and orange, always in that
  order (``SERIES``); a third is aqua. Magnitudes use a single-hue light-to-dark blue ramp
  (``SEQ_BLUE``), never a rainbow. Diverging data (residuals) uses blue and red around a
  neutral grey (``DIVERGING``).
* **Text is never coloured by series**; a coloured mark next to ink-coloured text carries
  the identity.
* **Quiet chrome:** hairline grid, no top/right spines, thin marks, direct labels where a
  line ends instead of a legend wherever there is room.
* The palette values were checked with a colour-vision-deficiency separation test
  (adjacent and all-pairs, light surface): worst CVD separation 9.2 on the OKLab x100 scale
  (target 8 or more), worst normal-vision separation 24.0 (floor 15).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import seaborn as sns
from cycler import cycler
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

__all__ = ["DIVERGING", "INK", "SEQ_BLUE", "SERIES", "SURFACE", "apply_theme", "direct_label", "save"]

SURFACE = "#fcfcfb"
INK = {"primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781"}
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"

# Categorical slots in fixed order: blue, orange, aqua.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

# Sequential blue, light to dark (steps 100 to 700 of the blue ramp).
_BLUE_STEPS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_BLUE = LinearSegmentedColormap.from_list("en630_blue", _BLUE_STEPS)

# Diverging: blue <-> neutral grey <-> red.
DIVERGING = LinearSegmentedColormap.from_list(
    "en630_div", ["#184f95", "#6da7ec", "#f0efec", "#ee8a89", "#b53030"]
)


def apply_theme() -> None:
    """Install the project theme into matplotlib and seaborn (idempotent)."""
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": _AXIS,
            "axes.labelcolor": INK["secondary"],
            "axes.titlecolor": INK["primary"],
            "axes.titleweight": "semibold",
            "axes.titlesize": 12.5,
            "axes.titlelocation": "left",
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": _GRID,
            "grid.linewidth": 0.8,
            "xtick.color": INK["muted"],
            "ytick.color": INK["muted"],
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "text.color": INK["primary"],
            "font.family": ["sans-serif"],
            "font.sans-serif": ["Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2.0,
            "figure.dpi": 110,
            "savefig.dpi": 200,
        },
    )
    mpl.rcParams["axes.prop_cycle"] = cycler(color=SERIES)


def direct_label(ax, x, y, text: str, color: str, dx: float = 0.0, dy: float = 0.0) -> None:
    """Label a line at its end in the series colour of the *mark*, text in ink.

    The text itself stays in secondary ink; a small coloured dot carries the identity.
    """
    ax.annotate(
        text,
        (x, y),
        xytext=(8 + dx, dy),
        textcoords="offset points",
        va="center",
        fontsize=9,
        color=INK["secondary"],
    )
    ax.plot(
        [x],
        [y],
        marker="o",
        markersize=6,
        color=color,
        markeredgecolor=SURFACE,
        markeredgewidth=1.5,
        zorder=5,
    )


def save(fig: Figure, path: str | Path) -> Path:
    """Save a figure tightly cropped, creating the folder if needed, then return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15)
    return path
