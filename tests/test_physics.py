"""Tests for solar geometry, tilted/tracking irradiance and decomposition."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pvlib import irradiance as pvl
from pvlib import solarposition as pvsp

from en630.irradiance import decompose, extraterrestrial_normal, tilted_irradiance, tracker_beam
from en630.solar import course_geometry, declination_deg, equation_of_time_min, hour_angle_deg, spa_position
from en630.weather import IIT_BOMBAY, clean_dni, read_tmy_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wx() -> pd.DataFrame:
    df = read_tmy_csv(ROOT / "data" / "pvgis_tmy_iitb.csv")
    df["dni"] = clean_dni(df, IIT_BOMBAY, "centre")
    return df


# ---------------------------------------------------------------- solar geometry
def test_declination_methods_agree_with_references():
    days = np.arange(1, 366)
    assert declination_deg(137) == pytest.approx(19.263625, abs=1e-6)
    spencer = np.degrees(pvsp.declination_spencer71(days))
    assert np.abs(declination_deg(days, "spencer") - spencer).max() < 1e-6
    # The course (Cooper) formula is the cruder of the two: up to about a degree off.
    assert np.abs(declination_deg(days, "cooper") - spencer).max() < 1.5


def test_unknown_declination_method_is_rejected():
    with pytest.raises(ValueError, match="cooper"):
        declination_deg(10, "fourier")


def test_zenith_matches_reference_algorithm(wx):
    spa = spa_position(wx.index, IIT_BOMBAY, "centre")
    day = (spa.zenith_deg < 85).to_numpy()
    for method, limit in (("spencer", 0.3), ("cooper", 1.3)):
        geo = course_geometry(wx.index, IIT_BOMBAY, timestamp="centre", declination_method=method)
        err = (geo.zenith_deg - spa.zenith_deg).to_numpy()[day]
        assert np.abs(err).max() < limit, method


def test_hour_angle_sign_follows_longitude_and_needs_no_hemisphere_letter():
    # East of the standard meridian the sun is ahead of the clock; west of it, behind.
    east = hour_angle_deg(100, 12.0, 90.0, 82.5)
    west = hour_angle_deg(100, 12.0, 75.0, 82.5)
    assert east > west
    assert east - west == pytest.approx(15.0 * (90.0 - 75.0) / 15.0, abs=1e-9)


def test_standard_longitude_is_actually_used():
    # B4: the legacy script ignored the value typed in.
    a = hour_angle_deg(100, 12.0, 72.95, 82.5)
    b = hour_angle_deg(100, 12.0, 72.95, 75.0)
    assert a != b


def test_equation_of_time_stays_within_known_range():
    e = equation_of_time_min(np.arange(1, 366))
    assert -15.0 < e.min() and e.max() < 18.0  # about -14 to +16 minutes in reality


def test_naive_index_is_rejected():
    idx = pd.date_range("2001-01-01", periods=3, freq="h")
    with pytest.raises(ValueError, match="timezone"):
        course_geometry(idx, IIT_BOMBAY)


def test_extraterrestrial_normal_varies_by_about_three_percent():
    e = extraterrestrial_normal(np.arange(1, 366))
    assert 1320 < e.min() < 1330 and 1405 < e.max() < 1415


# ---------------------------------------------------------------- transposition vs pvlib
@pytest.mark.parametrize(("ours", "theirs"), [("isotropic", "isotropic"), ("hdkr", "reindl")])
def test_tilted_models_agree_with_pvlib(wx, ours, theirs):
    mine = tilted_irradiance(wx, IIT_BOMBAY, 19.15, 0.0, 0.2, ours, "centre")["total"]
    spa = spa_position(wx.index, IIT_BOMBAY, "centre")
    ref = pvl.get_total_irradiance(
        19.15,
        180.0,
        spa.zenith_deg,
        spa.azimuth_deg,
        wx.dni,
        wx.ghi,
        wx.dhi,
        dni_extra=pvl.get_extra_radiation(wx.index),
        albedo=0.2,
        model=theirs,
    )["poa_global"].fillna(0.0)
    up = (spa.zenith_deg < 85).to_numpy()
    assert (mine - ref).abs()[up].mean() < 2.0  # W/m2
    assert mine.sum() == pytest.approx(ref.sum(), rel=0.01)


def test_flat_surface_receives_global_radiation(wx):
    # Tilt 0, isotropic: beam on the horizontal plus all diffuse. Compare with GHI where the
    # three components are consistent (daytime hours with the sun well up).
    out = tilted_irradiance(wx, IIT_BOMBAY, 0.0, 0.0, 0.2, "isotropic", "centre")
    geo = course_geometry(wx.index, IIT_BOMBAY, timestamp="centre")
    high = (geo.cos_zenith > 0.3).to_numpy()
    assert (out["total"] - wx.ghi).abs()[high].mean() < 5.0


def test_beam_term_depends_on_tilt_unlike_the_legacy_script(wx):
    # B1 fixed: at midday the south-facing beam falls as the surface tilts away from the sun.
    noon = wx.index[(wx.index.month == 6) & (wx.index.hour == 6) & (wx.dni > 400)][0]  # about 11:30 IST
    one = wx.loc[[noon]]
    flat = tilted_irradiance(one, IIT_BOMBAY, 0.0, 0.0, 0.2, "isotropic", "centre")["beam"].iloc[0]
    steep = tilted_irradiance(one, IIT_BOMBAY, 60.0, 0.0, 0.2, "isotropic", "centre")["beam"].iloc[0]
    assert steep != pytest.approx(flat, rel=0.01)


def test_night_hours_are_exactly_zero_and_nothing_is_nan(wx):
    out = tilted_irradiance(wx, IIT_BOMBAY, 20.0, 0.0, 0.2, "hdkr", "centre")
    geo = course_geometry(wx.index, IIT_BOMBAY, timestamp="centre")
    assert np.isfinite(out.to_numpy()).all()
    assert (out["total"][(geo.cos_zenith < 0).to_numpy()] == 0).all()


def test_zero_global_radiation_in_the_anisotropic_model_does_not_crash():
    # B5: the legacy script divided by Ig = 0.
    idx = pd.date_range("2001-06-21 05:00", periods=8, freq="h", tz="UTC")
    zero = pd.DataFrame({"ghi": 0.0, "dhi": 0.0, "dni": 0.0}, index=idx)
    out = tilted_irradiance(zero, IIT_BOMBAY, 19.0, 0.0, 0.2, "hdkr", "centre")
    assert (out == 0).all().all()


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [({"model": "perez"}, "unknown model"), ({"tilt_deg": 120.0}, "tilt")],
)
def test_invalid_arguments_raise_clear_errors(wx, kwargs, match):
    args = {"weather": wx, "site": IIT_BOMBAY, "tilt_deg": 20.0} | kwargs
    with pytest.raises(ValueError, match=match):
        tilted_irradiance(**args)


def test_missing_column_is_reported(wx):
    with pytest.raises(ValueError, match="dni"):
        tilted_irradiance(wx.drop(columns="dni"), IIT_BOMBAY, 20.0)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(tilt=st.floats(0, 90), albedo=st.floats(0, 1), model=st.sampled_from(["isotropic", "hdkr"]))
def test_components_are_never_negative_and_sum_to_total(wx, tilt, albedo, model):
    out = tilted_irradiance(wx.iloc[:500], IIT_BOMBAY, tilt, 0.0, albedo, model, "centre")
    assert (out >= -1e-9).all().all()
    assert np.allclose(out[["beam", "sky_diffuse", "ground"]].sum(axis=1), out["total"])


# ---------------------------------------------------------------- trackers
def test_two_axis_tracker_gets_full_dni_and_polar_gets_cos_declination(wx):
    two = tracker_beam(wx, IIT_BOMBAY, "two_axis", "centre")
    polar = tracker_beam(wx, IIT_BOMBAY, "polar", "centre")
    geo = course_geometry(wx.index, IIT_BOMBAY, timestamp="centre")
    up = (geo.cos_zenith >= 0.05).to_numpy()
    assert np.allclose(two[up], wx.dni[up])
    assert (polar <= two + 1e-9).all()
    assert polar.sum() < two.sum()
    assert np.allclose(polar[up], (wx.dni * np.cos(np.radians(geo.declination_deg)))[up])


def test_unknown_tracker_is_rejected(wx):
    with pytest.raises(ValueError, match="two_axis"):
        tracker_beam(wx, IIT_BOMBAY, "azimuth")


# ---------------------------------------------------------------- decomposition
@pytest.mark.parametrize("method", ["erbs", "dirint"])
def test_decomposition_is_bounded_and_zero_at_night(wx, method):
    out = decompose(wx.ghi, IIT_BOMBAY, method, "centre")
    geo = course_geometry(wx.index, IIT_BOMBAY, timestamp="centre")
    assert np.isfinite(out.to_numpy()).all()
    assert (out.dni >= 0).all() and (out.dni < 1400).all()
    assert (out.dni[(geo.cos_zenith < 0).to_numpy()] == 0).all()


def test_decomposition_method_is_validated(wx):
    with pytest.raises(ValueError, match="erbs"):
        decompose(wx.ghi, IIT_BOMBAY, "perez")


# ---------------------------------------------------------------- the legacy script
def _legacy(tilt: float) -> float:
    """Run the original script on a fixed set of answers and return its isotropic It."""
    answers = f"137\n72.95\nE\n82.5\n19.15\n12.5\n1\n800\n100\n{tilt}\n0.2\n1\n"
    run = subprocess.run(
        [sys.executable, str(ROOT / "legacy" / "original_radiation_script.py")],
        input=answers,
        capture_output=True,
        text=True,
        check=True,
    )
    return float(run.stdout.rsplit("It Isotropic model:", 1)[1])


def test_legacy_script_beam_term_ignores_tilt_and_the_new_model_does_not():
    # Legacy: the 15 W/m2 change between 0 and 60 degrees is all diffuse and ground reflection.
    assert _legacy(60.0) - _legacy(0.0) == pytest.approx(15.0, abs=0.01)
    # New model, one hour with the same inputs: Ib = Ig - Id = 700 on the horizontal (closure).
    idx = pd.DatetimeIndex(["2001-05-17 12:00:00+05:30"])  # start-of-hour stamp for 12:30
    cos_z = float(course_geometry(idx, IIT_BOMBAY, 82.5, "start", "cooper").cos_zenith.iloc[0])
    wx = pd.DataFrame({"ghi": 800.0, "dhi": 100.0, "dni": 700.0 / cos_z}, index=idx)
    flat = tilted_irradiance(wx, IIT_BOMBAY, 0.0, 0.0, 0.2, "isotropic", "start", 82.5, "cooper")[
        "beam"
    ].iloc[0]
    steep = tilted_irradiance(wx, IIT_BOMBAY, 60.0, 0.0, 0.2, "isotropic", "start", 82.5, "cooper")[
        "beam"
    ].iloc[0]
    assert flat == pytest.approx(700.0, rel=1e-6)  # horizontal beam = Ib
    assert steep != pytest.approx(flat, rel=0.01)  # tilt now matters
