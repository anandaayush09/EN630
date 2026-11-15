"""Tests for en630.weather: committed datasets, validation rules and the fetch routine."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from en630 import weather
from en630.weather import (
    COURSE_FILE_SITE,
    IIT_BOMBAY,
    clean_dni,
    dni_artefact_mask,
    dni_from_ghi_dhi,
    fetch_pvgis_tmy,
    load_nsrdb,
    read_tmy_csv,
    to_local,
    validate,
)

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def pvgis() -> pd.DataFrame:
    return read_tmy_csv(DATA / "pvgis_tmy_iitb.csv")


@pytest.fixture(scope="module")
def course() -> pd.DataFrame:
    return load_nsrdb(DATA / "weather_file_nsrdb.csv")


# ---------------------------------------------------------------- committed datasets
def test_pvgis_tmy_passes_validation(pvgis):
    validate(pvgis, IIT_BOMBAY, timestamp="centre")
    assert len(pvgis) == 8760


def test_pvgis_tmy_has_beam_irradiance(pvgis):
    # The reason PVGIS replaces the course file: it provides DNI directly.
    assert "dni" in pvgis and pvgis["dni"].max() > 800


def test_pvgis_noon_is_near_local_noon(pvgis):
    local = to_local(pvgis, IIT_BOMBAY)
    peak_hour = local.groupby("hour")["ghi"].mean().idxmax()
    assert peak_hour in (12, 13)  # Mumbai solar noon is about 12:35 IST


def test_course_file_loads_with_expected_shape(course):
    assert course.shape == (8760, 4)
    assert "dni" not in course  # documented gap in the course file
    assert str(course.index[0]) == "2001-01-01 00:00:00+05:30"


def test_course_file_passes_validation(course):
    validate(course, COURSE_FILE_SITE, timestamp="start")


def test_course_file_first_sunny_hour_label(course):
    # Documented assumption in load_nsrdb: label 9 is the first non-zero GHI of the year.
    assert course["ghi"].iloc[:24].gt(0).idxmax().hour == 8


# ---------------------------------------------------------------- validation rules
def test_rejects_wrong_row_count(pvgis):
    with pytest.raises(ValueError, match="8760"):
        validate(pvgis.iloc[:-1], IIT_BOMBAY, "centre")


def test_rejects_negative_irradiance(pvgis):
    bad = pvgis.copy()
    bad.iloc[1000, bad.columns.get_loc("ghi")] = -5.0
    with pytest.raises(ValueError, match="ghi"):
        validate(bad, IIT_BOMBAY, "centre")


def test_rejects_diffuse_above_global(pvgis):
    bad = pvgis.copy()
    i = bad["ghi"].gt(100).idxmax()
    bad.loc[i, "dhi"] = bad.loc[i, "ghi"] + 50
    with pytest.raises(ValueError, match="dhi exceeds ghi"):
        validate(bad, IIT_BOMBAY, "centre")


def test_rejects_time_shifted_data(pvgis):
    # Rolling by 6 h puts sunshine at night: the classic time-zone mistake.
    bad = pvgis.copy()
    bad[["ghi", "dhi", "dni"]] = bad[["ghi", "dhi", "dni"]].shift(6).bfill()
    with pytest.raises(ValueError, match="below the horizon"):
        validate(bad, IIT_BOMBAY, "centre")


def test_rejects_gap_in_timestamps(pvgis):
    bad = pvgis.drop(pvgis.index[100:103])
    bad = pd.concat([bad, bad.iloc[-3:]])  # restore the row count, keep the gap
    bad.index = bad.index.sort_values()
    with pytest.raises(ValueError):
        validate(bad, IIT_BOMBAY, "centre")


# ---------------------------------------------------------------- derived DNI
def test_derived_dni_is_bounded_and_zero_at_night(course):
    dni = dni_from_ghi_dhi(course, COURSE_FILE_SITE, "start")
    assert dni.between(0, 1400).all()
    assert dni.iloc[:6].eq(0).all()  # 00:00-06:00 on 1 January


def test_derived_dni_equals_closure_at_midday():
    # Hand-built hour: sun almost overhead, ghi = dhi + dni*cos(z) must invert exactly.
    idx = pd.date_range("2001-06-21 12:00", periods=1, freq="h", tz="+05:30")
    site = weather.Site("test", 0.0, 82.5)  # equator, standard meridian -> sun high at noon
    probe = pd.DataFrame({"ghi": [900.0], "dhi": [100.0]}, index=idx)
    dni = dni_from_ghi_dhi(probe, site, "start")
    sun = weather._solar_geometry(idx, site, "start")
    expected = 800.0 / math.sin(math.radians(float(sun["elevation"].iloc[0])))
    assert dni.iloc[0] == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------- DNI artefacts
def test_artefact_mask_flags_only_low_sun_spikes_in_pvgis(pvgis):
    mask = dni_artefact_mask(pvgis, IIT_BOMBAY, "centre")
    assert 40 <= int(mask.sum()) <= 60  # 50 on the committed file
    elevation = weather._solar_geometry(pvgis.index, IIT_BOMBAY, "centre")["elevation"]
    assert (elevation[mask.to_numpy()] < 7).all()  # all of them are sunrise hours


def test_clean_dni_zeroes_flagged_hours_and_keeps_the_rest(pvgis):
    cleaned = clean_dni(pvgis, IIT_BOMBAY, "centre")
    mask = dni_artefact_mask(pvgis, IIT_BOMBAY, "centre")
    assert (cleaned[mask] == 0).all()
    pd.testing.assert_series_equal(cleaned[~mask], pvgis["dni"][~mask], check_names=False)
    assert cleaned.max() < 1060  # nothing above the clear-sky limit survives


def test_artefact_mask_flags_an_impossible_value_at_noon():
    idx = pd.date_range("2001-06-21 12:00", periods=1, freq="h", tz="+05:30")
    probe = pd.DataFrame({"ghi": [900.0], "dhi": [100.0], "dni": [1500.0]}, index=idx)
    assert bool(dni_artefact_mask(probe, IIT_BOMBAY, "start").iloc[0])
    probe["dni"] = 900.0
    assert not bool(dni_artefact_mask(probe, IIT_BOMBAY, "start").iloc[0])


# ---------------------------------------------------------------- fetch (no network)
def test_fetch_writes_csv_and_metadata(monkeypatch, tmp_path, pvgis):
    """Replace the PVGIS client with the committed data in pvlib's column layout."""
    fake = pvgis.rename(columns={})
    fake = fake.assign(**{"IR(h)": 400.0, "wind_direction": 180.0})

    def fake_get(lat, lon, **kwargs):
        meta = {
            "inputs": {"meteo_data": {"radiation_db": "PVGIS-ERA5"}, "location": {"latitude": lat}},
            "months_selected": [{"month": 1, "year": 2015}],
        }
        return fake, meta

    monkeypatch.setattr(weather, "get_pvgis_tmy", fake_get)
    out = tmp_path / "sub" / "tmy.csv"
    df = fetch_pvgis_tmy(IIT_BOMBAY, out)

    assert list(df.columns) == [
        "ghi",
        "dhi",
        "dni",
        "temp_air",
        "wind_speed",
        "relative_humidity",
        "pressure",
    ]
    assert out.exists()
    meta = json.loads(out.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert meta["site"]["latitude"] == IIT_BOMBAY.latitude
    assert meta["inputs"]["radiation_db"] == "PVGIS-ERA5"
    reread = read_tmy_csv(out)
    pd.testing.assert_frame_equal(reread, pvgis.round(2), check_freq=False, atol=0.01)
