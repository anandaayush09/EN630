"""Tests for the hourly simulation: energy balance, limiting cases and monotonic behaviour."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from en630 import fuel, load
from en630.config import load_config
from en630.simulate import collector_heat_mj, daily_energy, demand_series, simulate
from en630.weather import IIT_BOMBAY, clean_dni, read_tmy_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wx() -> pd.DataFrame:
    df = read_tmy_csv(ROOT / "data" / "pvgis_tmy_iitb.csv")
    df["dni"] = clean_dni(df, IIT_BOMBAY, "centre")
    return df


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# ------------------------------------------------------------------ load profile
def test_meals_add_up_to_the_table_total(cfg):
    cyl = fuel.cylinder_energy_mj(cfg["fuel"]["cylinder_mass_kg"], cfg["fuel"]["calorific_value_mj_kg"])
    meals = load.meal_heat_mj(cfg["load"], cyl)
    assert sum(meals.values()) == pytest.approx(load.demand_table(cfg["load"], cyl)["total"], rel=1e-12)
    assert sum(meals.values()) == pytest.approx(939.86, rel=1e-4)


def test_hourly_profile_sums_to_the_design_steam_heat(cfg):
    cyl = fuel.cylinder_energy_mj(cfg["fuel"]["cylinder_mass_kg"], cfg["fuel"]["calorific_value_mj_kg"])
    profile = load.hourly_steam_profile(
        load.meal_heat_mj(cfg["load"], cyl),
        cfg["schedule"],
        cfg["load"]["safety_factor"],
        cfg["load"]["pot_efficiency"],
    )
    assert len(profile) == 24
    assert sum(profile) == pytest.approx(1435.89, rel=1e-4)


def test_demand_follows_the_schedule_in_local_hours(wx, cfg):
    d = demand_series(wx.index, IIT_BOMBAY, cfg, "centre")
    local_hour = (wx.index.tz_convert("Asia/Kolkata") - pd.Timedelta(minutes=30)).hour
    scheduled = {h for hours in cfg["schedule"].values() for h in hours}
    assert set(np.unique(local_hour[d.to_numpy() > 0])) == scheduled
    assert d.sum() / 365 == pytest.approx(1435.89, rel=1e-4)


# ------------------------------------------------------------------ collector
def test_collector_is_zero_below_threshold_and_at_night(wx, cfg):
    per = collector_heat_mj(wx, IIT_BOMBAY, cfg)
    assert (per >= 0).all()
    assert (per[wx.dni < cfg["collector"]["minimum_dni_w_m2"]] == 0).all()


def test_collector_output_is_plausible_per_dish(wx, cfg):
    per = collector_heat_mj(wx, IIT_BOMBAY, cfg)
    # About 4.5 kW at 665 W/m2 for an hour is about 16 MJ; the hourly maximum must be of that order.
    assert 10 < per.max() < 25


# ------------------------------------------------------------------ energy balance
def _balances(r):
    h = r.hourly
    assert np.allclose(h.collected_mj, h.direct_mj + h.stored_in_mj + h.curtailed_mj, atol=1e-9)
    assert np.allclose(h.demand_mj, h.direct_mj + h.from_store_mj + h.lpg_backup_mj, atol=1e-9)


@pytest.mark.parametrize("storage", [0.0, 500.0, 3000.0])
def test_hourly_energy_balances_close(wx, cfg, storage):
    _balances(simulate(wx, IIT_BOMBAY, cfg, 14, storage))


def test_store_balance_is_exact_without_losses(wx, cfg):
    lossless = {
        **cfg,
        "storage": {
            **cfg["storage"],
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "standing_loss_per_hour": 0.0,
        },
    }
    r = simulate(wx, IIT_BOMBAY, lossless, 14, 1500.0)
    h = r.hourly
    assert (h.stored_in_mj.sum() - h.from_store_mj.sum()) == pytest.approx(
        h.store_level_mj.iloc[-1], abs=1e-6
    )


def test_store_level_stays_within_its_capacity(wx, cfg):
    r = simulate(wx, IIT_BOMBAY, cfg, 14, 800.0)
    assert r.hourly.store_level_mj.min() >= -1e-9
    assert r.hourly.store_level_mj.max() <= 800.0 + 1e-9


# ------------------------------------------------------------------ limiting cases
def test_no_dishes_means_all_lpg(wx, cfg):
    r = simulate(wx, IIT_BOMBAY, cfg, 0, 2000.0)
    assert r.annual["solar_fraction"] == 0.0
    assert r.annual["lpg_backup_mj"] == pytest.approx(r.annual["demand_mj"])
    assert r.annual["cylinders_displaced"] == 0.0


def test_no_storage_means_the_store_is_never_used(wx, cfg):
    r = simulate(wx, IIT_BOMBAY, cfg, 14, 0.0)
    assert (r.hourly.stored_in_mj == 0).all() and (r.hourly.from_store_mj == 0).all()


def test_a_very_large_field_with_a_large_store_meets_almost_everything(wx, cfg):
    r = simulate(wx, IIT_BOMBAY, cfg, 300, 200_000.0)
    assert r.annual["solar_fraction"] > 0.98


def test_solar_fraction_rises_with_dishes_and_with_storage(wx, cfg):
    by_dishes = [simulate(wx, IIT_BOMBAY, cfg, n, 1000.0).annual["solar_fraction"] for n in (4, 8, 14, 24)]
    by_store = [simulate(wx, IIT_BOMBAY, cfg, 14, c).annual["solar_fraction"] for c in (0, 500, 1000, 4000)]
    assert by_dishes == sorted(by_dishes)
    assert by_store == sorted(by_store)


def test_cylinders_and_co2_follow_solar_heat(wx, cfg):
    r = simulate(wx, IIT_BOMBAY, cfg, 14, 1000.0)
    cyl_mj = fuel.cylinder_energy_mj(cfg["fuel"]["cylinder_mass_kg"], cfg["fuel"]["calorific_value_mj_kg"])
    assert r.annual["cylinders_displaced"] == pytest.approx(r.annual["solar_to_load_mj"] / cyl_mj / 0.6)
    assert r.annual["co2_avoided_t"] == pytest.approx(r.annual["cylinders_displaced"] * 42.6 / 1000, rel=1e-3)


@pytest.mark.parametrize(
    ("kwargs", "match"), [({"n_dishes": -1}, "dishes"), ({"n_dishes": 3, "storage_mj": -5.0}, "storage")]
)
def test_invalid_inputs_are_rejected(wx, cfg, kwargs, match):
    with pytest.raises(ValueError, match=match):
        simulate(wx, IIT_BOMBAY, cfg, **kwargs)


def test_daily_energy_has_one_row_per_day(wx, cfg):
    de = daily_energy(simulate(wx, IIT_BOMBAY, cfg, 14, 0.0), IIT_BOMBAY)
    assert len(de) in (365, 366)  # UTC-stamped year spills 5.5 h into the next local day


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(n=st.integers(0, 40), cap=st.floats(0, 5000), eta=st.floats(0.5, 1.0), loss=st.floats(0, 0.05))
def test_flows_are_non_negative_and_balanced_for_any_design(wx, cfg, n, cap, eta, loss):
    c = {
        **cfg,
        "storage": {
            **cfg["storage"],
            "charge_efficiency": eta,
            "discharge_efficiency": eta,
            "standing_loss_per_hour": loss,
        },
    }
    r = simulate(wx.iloc[:2000], IIT_BOMBAY, c, n, cap)
    assert (r.hourly.drop(columns="store_level_mj") >= -1e-9).all().all()
    assert 0.0 <= r.annual["solar_fraction"] <= 1.0 + 1e-12
    _balances(r)
