"""Solar geometry from the course equations, vectorised over a whole year of hourly stamps.

The equations are those of the final report (declination from Cooper's formula, the equation of time as a
Spencer-type series, hour angle from local apparent time). They are written as numpy functions
so a full year is one call, and ``spa_position`` provides pvlib's high-accuracy solar position
algorithm as the reference to test them against.

Longitudes are signed: east is positive. The original script asked for the letters E or W, which
produced two separate branches (one unverified, issue B7 in appendix B of ``docs/report.md``); a signed
longitude has only one formula.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from pvlib import solarposition

from .weather import Site

__all__ = [
    "STANDARD_LONGITUDE_INDIA",
    "Declination",
    "course_geometry",
    "declination_deg",
    "equation_of_time_min",
    "hour_angle_deg",
    "spa_position",
]

STANDARD_LONGITUDE_INDIA = 82.5  # degrees east, the Indian Standard Time meridian

Timestamp = Literal["start", "centre"]


Declination = Literal["cooper", "spencer"]


def declination_deg(day_of_year, method: Declination = "cooper"):
    """Solar declination in degrees (accepts arrays).

    ``"cooper"`` is the course equation, 23.45 sin(360 (284 + n) / 365) (final report equation 2): simple
    but off by up to about 1 degree in October, which shows up as up to 1.2 degrees of zenith
    error. ``"spencer"`` is the 1971 Fourier series, accurate to a few hundredths of a degree
    here; it brings the zenith error against the reference algorithm below 0.3 degrees.
    """
    n = np.asarray(day_of_year, dtype=float)
    if method == "cooper":
        return 23.45 * np.sin(np.radians(360.0 * (284.0 + n) / 365.0))
    if method == "spencer":
        g = 2.0 * np.pi * (n - 1.0) / 365.0
        rad = (
            0.006918
            - 0.399912 * np.cos(g)
            + 0.070257 * np.sin(g)
            - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g)
            - 0.002697 * np.cos(3 * g)
            + 0.00148 * np.sin(3 * g)
        )
        return np.degrees(rad)
    raise ValueError(f"unknown declination method {method!r}; choose 'cooper' or 'spencer'")


def equation_of_time_min(day_of_year):
    """Equation of time in minutes (Spencer-type series, as in final report equation 4)."""
    b = np.radians(360.0 * (np.asarray(day_of_year, dtype=float) - 1.0) / 365.0)
    return 229.18 * (
        0.000075
        + 0.001868 * np.cos(b)
        - 0.032077 * np.sin(b)
        - 0.014615 * np.cos(2 * b)
        - 0.04089 * np.sin(2 * b)
    )


def hour_angle_deg(day_of_year, clock_hours, longitude_deg, standard_longitude_deg=STANDARD_LONGITUDE_INDIA):
    """Hour angle in degrees: 15 degrees per hour from local apparent solar noon.

    Local apparent time = clock time + (longitude - standard longitude)/15 + E/60. With east
    longitudes positive this one formula covers both hemispheres.
    """
    lat_h = (
        np.asarray(clock_hours, dtype=float)
        + (longitude_deg - standard_longitude_deg) / 15.0
        + equation_of_time_min(day_of_year) / 60.0
    )
    return (lat_h - 12.0) * 15.0


def course_geometry(
    index: pd.DatetimeIndex,
    site: Site,
    standard_longitude_deg: float = STANDARD_LONGITUDE_INDIA,
    timestamp: Timestamp = "start",
    declination_method: Declination = "spencer",
) -> pd.DataFrame:
    """Declination, hour angle, ``cos_zenith`` and zenith angle for each timestamp.

    Evaluated at the middle of the hour (``timestamp='start'`` adds 30 minutes; ``'centre'``
    leaves the stamp), the same convention as ``weather.validate``. The index must be
    timezone-aware; it is converted to the site's standard time before reading the clock.
    ``cos_zenith`` may be negative at night: callers decide what that means.
    """
    if index.tz is None:
        raise ValueError("the index must be timezone-aware (UTC or a fixed offset)")
    mid = index + pd.Timedelta(minutes=30) if timestamp == "start" else index
    local = mid.tz_convert(site.tz)
    day = np.asarray(local.dayofyear, dtype=float)
    clock = np.asarray(local.hour + local.minute / 60.0, dtype=float)

    delta = declination_deg(day, declination_method)
    omega = hour_angle_deg(day, clock, site.longitude, standard_longitude_deg)
    phi, d, w = np.radians(site.latitude), np.radians(delta), np.radians(omega)
    cos_z = np.cos(phi) * np.cos(d) * np.cos(w) + np.sin(phi) * np.sin(d)
    return pd.DataFrame(
        {
            "day_of_year": day.astype(int),
            "declination_deg": delta,
            "hour_angle_deg": omega,
            "cos_zenith": cos_z,
            "zenith_deg": np.degrees(np.arccos(np.clip(cos_z, -1.0, 1.0))),
        },
        index=index,
    )


def spa_position(index: pd.DatetimeIndex, site: Site, timestamp: Timestamp = "start") -> pd.DataFrame:
    """Reference solar position from pvlib (high-accuracy SPA), at mid-hour like the course version.

    Returns ``zenith_deg`` (true, no refraction) and ``azimuth_deg`` (from north, clockwise).
    """
    mid = index + pd.Timedelta(minutes=30) if timestamp == "start" else index
    pos = solarposition.get_solarposition(mid, site.latitude, site.longitude)
    return pd.DataFrame(
        {"zenith_deg": pos["zenith"].to_numpy(), "azimuth_deg": pos["azimuth"].to_numpy()}, index=index
    )
