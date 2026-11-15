"""Radiation on tilted and tracking surfaces, and splitting global radiation into beam and diffuse.

Corrects the defects of the original script (``legacy/original_radiation_script.py``,
listed in appendix B of ``docs/report.md``):

* B1: the beam factor was ``1/cos(zenith)`` whatever the tilt. Here a fixed surface uses
  ``cos(theta)/cos(zenith)`` with the true incidence angle; the old factor is exactly the
  beam on a surface that always faces the sun (two-axis tracking) and is available as such.
* B2, B3: letters and menu numbers that crashed the script on a wrong answer are replaced by
  a signed longitude and named models that raise ``ValueError`` with the valid choices.
* B4: the standard longitude is a parameter and is used.
* B5: nothing divides by zero; at night every irradiance is zero.
* B6: the extraterrestrial irradiance uses the day angle in degrees converted correctly.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from pvlib import irradiance as pvl

from .solar import Declination, Timestamp, course_geometry
from .weather import Site

__all__ = [
    "SOLAR_CONSTANT",
    "decompose",
    "extraterrestrial_normal",
    "tilted_irradiance",
    "tracker_beam",
]

SOLAR_CONSTANT = 1367.0  # W/m2, the value used in the final report (equation 15)
MAX_DNI_RATIO = 0.75  # largest believable beam / extraterrestrial beam, as in weather.dni_artefact_mask
_MIN_COS_Z = 0.05  # below about 3 degrees of sun height the ratios blow up; treat as night

Model = Literal["isotropic", "hdkr"]
Tracker = Literal["two_axis", "polar"]


def extraterrestrial_normal(day_of_year) -> np.ndarray:
    """Beam irradiance outside the atmosphere on a normal surface, with the Earth-Sun distance factor.

    ``Isc (1 + 0.033 cos(360 n / 365))``. The original script put the angle into ``cos`` in
    radians instead of degrees (B6), so its value was wrong.
    """
    n = np.asarray(day_of_year, dtype=float)
    return SOLAR_CONSTANT * (1.0 + 0.033 * np.cos(np.radians(360.0 * n / 365.0)))


def _cos_incidence_fixed(tilt, azimuth, delta_deg, omega_deg, phi_deg):
    """Cosine of the incidence angle on a fixed tilted surface (final report equation 7), vectorised."""
    b, g, d, w, p = (np.radians(x) for x in (tilt, azimuth, delta_deg, omega_deg, phi_deg))
    return (
        np.sin(b) * np.cos(g) * (np.cos(d) * np.cos(w) * np.sin(p) - np.sin(d) * np.cos(p))
        + np.sin(b) * np.sin(g) * np.cos(d) * np.sin(w)
        + np.cos(b) * (np.cos(d) * np.cos(w) * np.cos(p) + np.sin(d) * np.sin(p))
    )


def tilted_irradiance(
    weather: pd.DataFrame,
    site: Site,
    tilt_deg: float,
    azimuth_deg: float = 0.0,
    albedo: float = 0.2,
    model: Model = "isotropic",
    timestamp: Timestamp = "start",
    standard_longitude_deg: float = 82.5,
    declination_method: Declination = "spencer",
) -> pd.DataFrame:
    """Plane-of-array irradiance on a fixed surface from hourly ``ghi``, ``dhi`` and ``dni``.

    ``declination_method`` is ``"spencer"`` (accurate) or ``"cooper"`` (the course equation).
    ``azimuth_deg`` is measured from south, east negative (the final report's gamma; 0 faces the equator in
    the northern hemisphere). Models:

    * ``"isotropic"``: ``Ib Rb + Id (1 + cos b)/2 + Ig rho (1 - cos b)/2``;
    * ``"hdkr"`` (Hay-Davies-Klucher-Reindl, final report equation 14): the diffuse part is split into a
      circumsolar share ``Ai`` that behaves like beam and an isotropic remainder with a
      horizon-brightening factor ``1 + sqrt(Ib/Ig) sin^3(b/2)``; ``Ai = Ib / Io``.

    Beam on the horizontal is ``Ib = DNI cos(zenith)``. Hours with the sun lower than about 3
    degrees (and every night hour) return zero for all components, which removes the
    division-by-zero and negative-factor failures of the original script (B5).
    """
    if model not in ("isotropic", "hdkr"):
        raise ValueError(f"unknown model {model!r}; choose 'isotropic' or 'hdkr'")
    if not 0.0 <= tilt_deg <= 90.0:
        raise ValueError("tilt must be between 0 and 90 degrees")
    for col in ("ghi", "dhi", "dni"):
        if col not in weather:
            raise ValueError(f"weather needs a '{col}' column")

    geo = course_geometry(weather.index, site, standard_longitude_deg, timestamp, declination_method)
    cos_z = geo["cos_zenith"].to_numpy()
    up = cos_z >= _MIN_COS_Z  # sun high enough for ratios to be meaningful

    ghi = np.where(up, weather["ghi"].to_numpy(dtype=float), 0.0)
    dhi = np.where(up, weather["dhi"].to_numpy(dtype=float), 0.0)
    dni = np.where(up, weather["dni"].to_numpy(dtype=float), 0.0)
    ib = dni * np.where(up, cos_z, 0.0)  # beam on the horizontal

    cos_theta = _cos_incidence_fixed(
        tilt_deg,
        azimuth_deg,
        geo["declination_deg"].to_numpy(),
        geo["hour_angle_deg"].to_numpy(),
        site.latitude,
    )
    rb = np.where(up, np.clip(cos_theta, 0.0, None) / np.where(up, cos_z, 1.0), 0.0)
    beta = np.radians(tilt_deg)
    rd = 0.5 * (1.0 + np.cos(beta))
    rr = 0.5 * (1.0 - np.cos(beta)) * albedo

    if model == "isotropic":
        beam = ib * rb
        sky = dhi * rd
    else:
        io = extraterrestrial_normal(geo["day_of_year"].to_numpy()) * np.where(up, cos_z, 0.0)
        ai = np.divide(ib, io, out=np.zeros_like(ib), where=io > 0).clip(0.0, 1.0)
        f = np.sqrt(np.divide(ib, ghi, out=np.zeros_like(ib), where=ghi > 0).clip(0.0, 1.0))
        beam = (ib + ai * dhi) * rb
        sky = dhi * (1.0 - ai) * rd * (1.0 + f * np.sin(beta / 2.0) ** 3)
    ground = ghi * rr

    return pd.DataFrame(
        {"beam": beam, "sky_diffuse": sky, "ground": ground, "total": beam + sky + ground},
        index=weather.index,
    )


def tracker_beam(
    weather: pd.DataFrame,
    site: Site,
    kind: Tracker = "polar",
    timestamp: Timestamp = "start",
    standard_longitude_deg: float = 82.5,
    declination_method: Declination = "spencer",
) -> pd.Series:
    """Beam irradiance on the aperture of a tracking collector, in W/m2.

    * ``"two_axis"``: the aperture always faces the sun, so it receives the full DNI. This is
      what the original script's factor ``1/cos(zenith)`` actually computed.
    * ``"polar"``: rotation about an axis parallel to the Earth's, at 15 degrees per hour, with a
      fixed inclination (single-axis tracking as in the final report). The incidence angle then depends only
      on the declination: ``cos(theta) = cos(delta)``, constant through the day.

    This is the geometry of an idealised single-axis polar tracker. The reflector-specific
    cosine loss of a Scheffler dish, whose mirror shape follows the declination, is not modelled
    here (see LIMITATIONS_AND_FUTURE_SCOPE.md).
    """
    if kind not in ("two_axis", "polar"):
        raise ValueError(f"unknown tracker {kind!r}; choose 'two_axis' or 'polar'")
    geo = course_geometry(weather.index, site, standard_longitude_deg, timestamp, declination_method)
    up = geo["cos_zenith"].to_numpy() >= _MIN_COS_Z
    factor = 1.0 if kind == "two_axis" else np.cos(np.radians(geo["declination_deg"].to_numpy()))
    return pd.Series(
        np.where(up, weather["dni"].to_numpy(dtype=float) * factor, 0.0),
        index=weather.index,
        name="beam_aperture",
    )


def decompose(
    ghi: pd.Series,
    site: Site,
    method: Literal["erbs", "dirint"] = "erbs",
    timestamp: Timestamp = "start",
) -> pd.DataFrame:
    """Estimate ``dni`` and ``dhi`` from global horizontal irradiance alone (pvlib models).

    Used for weather files that carry only GHI. ``erbs`` is a clearness-index correlation;
    ``dirint`` adds persistence and is usually better on hourly data. Both are validated
    against the PVGIS values in notebook 03, which says how large their errors are.
    """
    from .solar import spa_position  # local import: keeps module import order simple

    pos = spa_position(ghi.index, site, timestamp)
    zenith = pos["zenith_deg"]
    mid = ghi.index + pd.Timedelta(minutes=30) if timestamp == "start" else ghi.index
    if method == "erbs":
        out = pvl.erbs(ghi.to_numpy(dtype=float), zenith.to_numpy(), mid)
        dni, dhi = out["dni"].to_numpy(), out["dhi"].to_numpy()
    elif method == "dirint":
        dni = pvl.dirint(pd.Series(ghi.to_numpy(dtype=float), index=mid), zenith.set_axis(mid), mid)
        dni = dni.fillna(0.0).to_numpy()
        cos_z = np.cos(np.radians(zenith.to_numpy()))
        dhi = np.clip(ghi.to_numpy(dtype=float) - dni * np.clip(cos_z, 0.0, None), 0.0, None)
    else:
        raise ValueError(f"unknown method {method!r}; choose 'erbs' or 'dirint'")

    # Both models divide by a small cosine at low sun and can return a beam value above what the
    # sun can deliver (the same artefact as in the PVGIS file, see weather.dni_artefact_mask).
    # Those hours get zero beam and all their radiation as diffuse.
    too_high = dni > MAX_DNI_RATIO * extraterrestrial_normal(pd.DatetimeIndex(mid).dayofyear)
    dni = np.where(too_high, 0.0, dni)
    dhi = np.where(too_high, ghi.to_numpy(dtype=float), dhi)
    return pd.DataFrame({"dni": dni, "dhi": dhi}, index=ghi.index)
