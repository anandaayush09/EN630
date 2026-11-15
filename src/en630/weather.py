"""Weather data for the study: loading, fetching and validating hourly series.

Why this module exists
----------------------
The original coursework used a file whose header names Jodhpur although the study site is
IIT Bombay, and that file has no DNI column. Everything downstream (design DNI, dish
sizing, annual energy) depends on the weather, so the first job of the re-analysis is to
get a series for the right site and prove it is physically sane before any model uses it.

Conventions
-----------
* Standard column names: ``ghi``, ``dhi`` (and ``dni`` when available) in W/m2,
  ``temp_air`` in degC, ``wind_speed`` in m/s.
* PVGIS series are indexed in UTC (typical-meteorological-year months come from different
  real years; PVGIS relabels them to 1990). The NSRDB-style course file is indexed in
  local standard time (UTC+5.5). Use :func:`to_local` before grouping by hour of day.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pandera.pandas as pa
from pvlib import solarposition
from pvlib.iotools import get_pvgis_hourly, get_pvgis_tmy
from pvlib.irradiance import get_extra_radiation

__all__ = [
    "COURSE_FILE_SITE",
    "IIT_BOMBAY",
    "Site",
    "clean_dni",
    "dni_artefact_mask",
    "dni_from_ghi_dhi",
    "fetch_pvgis_multiyear",
    "fetch_pvgis_tmy",
    "load_nsrdb",
    "read_multiyear_csv",
    "read_tmy_csv",
    "to_local",
    "validate",
]


@dataclass(frozen=True)
class Site:
    """A location on Earth with the time zone used to read clock times."""

    name: str
    latitude: float
    longitude: float
    tz: str = "Asia/Kolkata"


# Coordinates of Hostel-17 as stated in both reports: 19.15 N, 72.95 E.
IIT_BOMBAY = Site("IIT Bombay, Mumbai", 19.15, 72.95)
# What the header of data/weather_file_nsrdb.csv actually says (NSRDB location 20013).
COURSE_FILE_SITE = Site("Jodhpur (course file header)", 26.35, 73.05)

_STANDARD_COLUMNS = ["ghi", "dhi", "dni", "temp_air", "wind_speed"]
_HOURS_PER_YEAR = 8760
_IST_OFFSET = "+05:30"


# --------------------------------------------------------------------------- schema
# Basic per-column bounds. They are deliberately generous: they exist to catch unit
# mistakes, sign errors and corrupt rows, not to second-guess real weather.
_SCHEMA = pa.DataFrameSchema(
    {
        "ghi": pa.Column(float, pa.Check.in_range(0, 1500), nullable=False),
        "dhi": pa.Column(float, pa.Check.in_range(0, 1000), nullable=False),
        "dni": pa.Column(float, pa.Check.in_range(0, 1500), nullable=False, required=False),
        "temp_air": pa.Column(float, pa.Check.in_range(-10, 55), nullable=False),
        "wind_speed": pa.Column(float, pa.Check.in_range(0, 60), nullable=False),
    },
    # The extra PVGIS columns (humidity, pressure, ...) are allowed but not required.
    strict=False,
    coerce=True,
)


def validate(df: pd.DataFrame, site: Site, timestamp: Literal["start", "centre"] = "start") -> pd.DataFrame:
    """Check a weather table and return it unchanged, or raise ``ValueError``.

    Checks
    ------
    1. exactly 8760 rows, unique increasing hourly timestamps (a typical year);
    2. column bounds from the schema above (no NaN, no negative irradiance);
    3. diffuse never exceeds global by more than 1 W/m2 (rounding tolerance);
    4. no irradiance at night: ``ghi`` <= 1 W/m2 whenever the sun is more than 6 degrees
       below the horizon (civil twilight; skylight persists until then, so a smaller
       margin would flag real twilight diffuse of 1-2 W/m2) at the middle of the hour;
    5. clear-sky index ``ghi / (extraterrestrial * cos zenith)`` <= 1.2 when the sun is
       above ~12 degrees. Above 1 is possible for short cloud-enhancement spikes; above
       1.2 in a monthly-mean-type series signals a unit or time-shift error.

    ``timestamp`` says what each index value labels: the ``"start"`` of the averaging hour
    (the course file, read that way by :func:`load_nsrdb`) or its ``"centre"`` (PVGIS TMY).
    For PVGIS the centre reading is the one consistent with the data: the first and last
    sunny hours of January fall on Mumbai's sunrise and sunset, and under an hour-start
    reading 58 hours would show 1-2 W/m2 of irradiance with the sun 4-5 degrees down.
    These checks cannot tell Jodhpur from Mumbai (both pass for the course file), so they
    guard against corrupt or shifted data, not against a wrong location.
    """
    problems: list[str] = []

    if len(df) != _HOURS_PER_YEAR:
        problems.append(f"expected {_HOURS_PER_YEAR} rows, found {len(df)}")
    if not (
        isinstance(df.index, pd.DatetimeIndex) and df.index.is_unique and df.index.is_monotonic_increasing
    ):
        problems.append("index must be a unique, increasing DatetimeIndex")
    else:
        steps = df.index.to_series().diff().dropna().unique()
        if len(steps) != 1 or steps[0] != pd.Timedelta(hours=1):
            problems.append("timestamps are not strictly hourly (gaps or duplicates)")

    try:
        _SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:  # collect every failure, not just the first
        fails = exc.failure_cases[["column", "check"]].drop_duplicates()
        problems += [f"schema: {r.column}: {r.check}" for r in fails.itertuples()]

    if not problems:  # the checks below need a clean frame
        if (df["dhi"] - df["ghi"]).max() > 1.0:
            problems.append("dhi exceeds ghi by more than 1 W/m2")

        sun = _solar_geometry(df.index, site, timestamp)
        night = sun["elevation"] < -6.0
        if (df.loc[night.values, "ghi"] > 1.0).any():
            problems.append("irradiance found while the sun is below the horizon (time-zone shift?)")

        day = sun["elevation"] > 12.0
        kt = df["ghi"][day.values] / (sun["extra_h"][day.values])
        if (kt > 1.2).any():
            problems.append(f"clear-sky index above 1.2 (max {kt.max():.2f})")

    if problems:
        raise ValueError(f"weather data for {site.name} failed validation:\n  - " + "\n  - ".join(problems))
    return df


def _solar_geometry(
    index: pd.DatetimeIndex, site: Site, timestamp: Literal["start", "centre"] = "start"
) -> pd.DataFrame:
    """Solar elevation and extraterrestrial irradiance on a horizontal plane.

    Evaluated at the *middle* of each hour, because hourly irradiance is an average over
    the hour and the sun at the hour mark would misclassify sunrise and sunset hours.
    """
    mid = index + pd.Timedelta(minutes=30) if timestamp == "start" else index
    pos = solarposition.get_solarposition(mid, site.latitude, site.longitude)
    extra = get_extra_radiation(mid)
    cosz = np.cos(np.radians(pos["apparent_zenith"].clip(upper=90)))
    return pd.DataFrame(
        {"elevation": pos["apparent_elevation"].to_numpy(), "extra_h": (extra * cosz).to_numpy()},
        index=index,
    )


# --------------------------------------------------------------------------- loading
def read_tmy_csv(path: str | Path) -> pd.DataFrame:
    """Read a table written by :func:`fetch_pvgis_tmy` (UTC index, standard columns)."""
    df = pd.read_csv(path, index_col="time_utc", parse_dates=["time_utc"])
    return df


def load_nsrdb(path: str | Path) -> pd.DataFrame:
    """Load the NSRDB-format course file ``data/weather_file_nsrdb.csv``.

    The file has a two-line site header, a blank line, then a column header and 8760 rows
    labelled ``Hour`` 1..8760. We read ``Hour h`` as the interval ``[h-1, h)`` in local
    standard time (the first non-zero GHI appears in label 9 and the last in label 18, a
    plausible daylight window). This is an *assumption* made because the file does not
    say; the night check in :func:`validate` would flag a wrong shift of more than an hour.
    The file has no DNI column, so the returned frame has none.
    """
    raw = pd.read_csv(path, skiprows=3, usecols=range(5))
    raw = raw.rename(
        columns={
            "Hour": "hour",
            "GHI": "ghi",
            "DHI": "dhi",
            "Temperature": "temp_air",
            "Wind Speed": "wind_speed",
        }
    )
    raw = raw.dropna(subset=["hour"]).astype({"hour": int})
    index = pd.date_range("2001-01-01 00:00", periods=len(raw), freq="h", tz=_IST_OFFSET, name="time_local")
    out = raw[["ghi", "dhi", "temp_air", "wind_speed"]].astype(float)
    out.index = index
    return out


def to_local(df: pd.DataFrame, site: Site) -> pd.DataFrame:
    """Return a copy indexed in the site's local time with ``month`` and ``hour`` columns.

    PVGIS TMY rows are in UTC, so the last 5.5 hours of the year land on 1 January of the
    next year after conversion; group by ``month`` and ``hour`` (not by year) and this is
    harmless.
    """
    out = df.copy()
    out.index = out.index.tz_convert(site.tz) if out.index.tz is not None else out.index
    out["month"] = out.index.month
    out["hour"] = out.index.hour
    return out


def dni_from_ghi_dhi(
    df: pd.DataFrame, site: Site, timestamp: Literal["start", "centre"] = "start", min_cos_zenith: float = 0.1
) -> pd.Series:
    """Beam normal irradiance from the closure relation ``dni = (ghi - dhi) / cos(zenith)``.

    This is the simplest way to fill the missing DNI column of the course file. It is a
    *diagnostic baseline*, not the final method: the division amplifies errors when the sun
    is low, so hours with ``cos(zenith) < min_cos_zenith`` (sun below about 6 degrees) are
    set to zero, and results are capped at 1400 W/m2. ``irradiance.decompose`` offers the
    Erbs and DIRINT models as alternatives; notebook 03 compares them.
    """
    sun = _solar_geometry(df.index, site, timestamp)
    cos_z = np.sin(np.radians(sun["elevation"]))
    ok = cos_z >= min_cos_zenith
    dni = ((df["ghi"] - df["dhi"]) / cos_z.where(ok)).clip(lower=0, upper=1400).fillna(0.0)
    dni.name = "dni"
    return dni


def dni_artefact_mask(
    df: pd.DataFrame, site: Site, timestamp: Literal["start", "centre"] = "start", max_ratio: float = 0.75
) -> pd.Series:
    """Flag hours whose DNI is physically impossible, mostly sunrise hours at a low sun.

    Beam irradiance cannot exceed a fraction of the extraterrestrial normal irradiance
    (about 1360 to 1410 W/m2 over the year); the best clear-sky ratios are about 0.7 to
    0.75, and near the horizon the air mass is so large that the ratio should be far lower.
    A series computed as ``(ghi - dhi) / cos(zenith)`` blows up when ``cos(zenith)`` is
    small, which is exactly what the PVGIS file shows at about 07:00 on winter mornings
    (sun 3 to 4 degrees up, DNI above 1100 W/m2). The closure check ``ghi = dhi + dni *
    cos z`` cannot catch this, because the error is multiplied back by the same small cosine.

    ``max_ratio`` = 0.75 is a generic best-site clear-sky limit. On the committed PVGIS
    file the ratio never exceeds 0.69 once the sun is above 20 degrees, so the bound does not
    touch genuine data; it flags 50 hours, all with the sun below 6.5 degrees. Values between
    the true limit and the bound still pass, so the mask under-reports rather than
    over-reports.
    """
    mid = df.index + pd.Timedelta(minutes=30) if timestamp == "start" else df.index
    extra = get_extra_radiation(mid).to_numpy()
    mask = df["dni"].to_numpy() > max_ratio * extra
    return pd.Series(mask, index=df.index, name="dni_artefact")


def clean_dni(
    df: pd.DataFrame, site: Site, timestamp: Literal["start", "centre"] = "start", max_ratio: float = 0.75
) -> pd.Series:
    """DNI with flagged hours set to zero.

    Zero is the conservative choice for this study: a dish with the sun 3 degrees above
    the horizon (shaded by buildings and with a very long air path) delivers nothing
    useful, and any positive value would only inflate the collected energy.
    """
    bad = dni_artefact_mask(df, site, timestamp, max_ratio)
    return df["dni"].where(~bad, 0.0).rename("dni_clean")


# --------------------------------------------------------------------------- fetching
def fetch_pvgis_tmy(site: Site, out_csv: str | Path | None = None, timeout: int = 60) -> pd.DataFrame:
    """Download a typical meteorological year (TMY) for ``site`` from PVGIS.

    Why PVGIS: it is free, needs no key, covers India, and its TMY includes measured-model
    DNI, which the course file lacked. Only the coordinates are sent to the service.

    Output is the standard column set plus ``relative_humidity`` and ``pressure``, indexed
    by UTC time. When ``out_csv`` is given the table is written there together with a
    ``.meta.json`` sidecar (source database, years used for each month, retrieval date)
    so the file stays interpretable without the network.
    """
    data, meta = get_pvgis_tmy(site.latitude, site.longitude, map_variables=True, timeout=timeout)
    df = data.rename(columns={"IR(h)": "ir_h"})
    keep = ["ghi", "dhi", "dni", "temp_air", "wind_speed", "relative_humidity", "pressure"]
    df = df[keep].astype(float)
    df.index = df.index.rename("time_utc")

    if out_csv is not None:
        out_csv = Path(out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv, float_format="%.2f")
        sidecar = {
            "source": "PVGIS typical meteorological year (EC Joint Research Centre)",
            "retrieved": date.today().isoformat(),
            "site": {"name": site.name, "latitude": site.latitude, "longitude": site.longitude},
            "inputs": meta.get("inputs", {}).get("meteo_data", {}),
            "location_used": meta.get("inputs", {}).get("location", {}),
            "months_selected": meta.get("months_selected", []),
            "index": "UTC, hourly, year 1990 (PVGIS relabelling); stamps label the centre of the hour",
        }
        out_csv.with_suffix(".meta.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return df


def fetch_pvgis_multiyear(
    site: Site, start: int = 2005, end: int = 2023, out_csv: str | Path | None = None, timeout: int = 300
) -> pd.DataFrame:
    """Download several real years of hourly beam irradiance and air temperature from PVGIS.

    The typical year hides year-to-year variability, which matters for a system whose output
    depends on beam sunshine. PVGIS does not return DNI directly in its hourly series, but for a
    surface that tracks the sun on two axes the 'direct' plane-of-array irradiance *is* the beam
    normal irradiance, so that mode is requested. Stamps are at hh:30 UTC, the centre of the hour.
    29 February is dropped so every year has 8760 hours.

    Output columns: ``dni`` (W/m2, as downloaded, not cleaned) and ``temp_air`` (degC), UTC index.
    Written gzip-compressed when ``out_csv`` ends in ``.gz``.
    """
    data, _meta = get_pvgis_hourly(
        site.latitude,
        site.longitude,
        start=start,
        end=end,
        raddatabase="PVGIS-ERA5",
        components=True,
        surface_tilt=0,
        surface_azimuth=180,
        trackingtype=2,
        map_variables=True,
        timeout=timeout,
    )
    df = data[["poa_direct", "temp_air"]].rename(columns={"poa_direct": "dni"}).astype(float)
    df = df[~((df.index.month == 2) & (df.index.day == 29))]
    df.index = df.index.rename("time_utc")
    if out_csv is not None:
        out_csv = Path(out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv, float_format="%.2f")
    return df


def read_multiyear_csv(path: str | Path) -> pd.DataFrame:
    """Read a table written by :func:`fetch_pvgis_multiyear`."""
    return pd.read_csv(path, index_col="time_utc", parse_dates=["time_utc"])
