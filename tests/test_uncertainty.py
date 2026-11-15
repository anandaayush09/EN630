"""Tests for the economics extensions, the multi-year data and the uncertainty analysis."""

import copy
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from en630 import economics, weather
from en630.config import load_config
from en630.uncertainty import (
    Evaluator,
    _inverse_cdf,
    load_distributions,
    modes,
    monte_carlo,
    pareto_front,
    sizing_sweep,
    sobol_indices,
)
from en630.weather import IIT_BOMBAY, read_multiyear_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def dists():
    return load_distributions()


@pytest.fixture(scope="module")
def years():
    my = read_multiyear_csv(ROOT / "data" / "pvgis_dni_2005_2023_iitb.csv.gz")
    return {y: g for y, g in my.groupby(my.index.year)}


@pytest.fixture(scope="module")
def ev(years, cfg, dists):
    return Evaluator(years, IIT_BOMBAY, cfg, dists)


# --------------------------------------------------------------- economics additions
def test_escalating_annuity_reduces_to_the_plain_annuity_without_growth():
    assert economics.escalating_annuity_factor(0.10, 15, 0.0) == pytest.approx(
        economics.annuity_factor(0.10, 15)
    )


def test_escalating_annuity_handles_growth_equal_to_the_discount_rate():
    assert economics.escalating_annuity_factor(0.07, 10, 0.07) == pytest.approx(10 / 1.07)


def test_escalating_annuity_matches_a_direct_sum():
    direct = sum((1.03) ** (t - 1) / (1.09) ** t for t in range(1, 21))
    assert economics.escalating_annuity_factor(0.09, 20, 0.03) == pytest.approx(direct, rel=1e-12)


def test_general_irr_agrees_with_the_final_report_irr():
    flows = [-5_600_000] + [1_199_631.57] * 14 + [1_199_631.57 + 280_000]
    assert economics.irr_of_flows(flows) == pytest.approx(
        economics.irr(5_600_000, 1_199_631.57, 280_000, 15), abs=1e-9
    )
    assert economics.npv_of_flows(flows, economics.irr_of_flows(flows)) == pytest.approx(0.0, abs=1e-3)


def test_irr_of_flows_rejects_flows_without_a_sign_change():
    with pytest.raises(ValueError):
        economics.irr_of_flows([100.0, 50.0, 50.0])


def test_lcoh_equals_discounted_cost_over_discounted_heat():
    af = economics.annuity_factor(0.1, 15)
    expected = (1_000_000 + 20_000 * af - 50_000 / 1.1**15) / (af * 400_000)
    assert economics.lcoh_inr_per_mj(1_000_000, 20_000, 50_000, 0.1, 15, 400_000) == pytest.approx(expected)
    assert math.isinf(economics.lcoh_inr_per_mj(1_000_000, 20_000, 50_000, 0.1, 15, 0.0))


# --------------------------------------------------------------- multi-year data
def test_committed_multiyear_file_has_nineteen_complete_years(years):
    assert sorted(years) == list(range(2005, 2024))
    assert all(len(g) == 8760 for g in years.values())
    assert all(not ((g.index.month == 2) & (g.index.day == 29)).any() for g in years.values())


def test_multiyear_beam_energy_is_close_to_the_typical_year(years):
    totals = np.array([g.dni.sum() / 1000 for g in years.values()])
    assert 1800 < totals.min() < totals.max() < 2200
    assert totals.std() / totals.mean() < 0.06  # about 4 % year to year


def test_multiyear_fetch_without_network(monkeypatch, tmp_path):
    idx = pd.date_range("2019-01-01 00:30", "2020-12-31 23:30", freq="h", tz="UTC")
    fake = pd.DataFrame({"poa_direct": 100.0, "temp_air": 25.0}, index=idx)
    monkeypatch.setattr(weather, "get_pvgis_hourly", lambda *a, **k: (fake, {}))
    out = tmp_path / "m.csv.gz"
    df = weather.fetch_pvgis_multiyear(IIT_BOMBAY, 2019, 2020, out)
    assert len(df) == 2 * 8760  # the leap day of 2020 is dropped
    assert list(df.columns) == ["dni", "temp_air"]
    assert read_multiyear_csv(out).shape == df.shape


# --------------------------------------------------------------- distributions
@pytest.mark.parametrize("name", ["uniform", "triangular", "integer_uniform"])
def test_samples_stay_within_their_bounds(name):
    spec = {"dist": name, "low": 2.0, "mode": 3.0, "high": 7.0}
    u = np.random.default_rng(0).random(5000)
    x = _inverse_cdf(spec, u)
    assert x.min() >= 2.0 and x.max() <= 7.0


def test_triangular_mean_matches_theory():
    spec = {"dist": "triangular", "low": 0.0, "mode": 1.0, "high": 4.0}
    x = _inverse_cdf(spec, np.random.default_rng(1).random(200_000))
    assert x.mean() == pytest.approx((0 + 1 + 4) / 3, abs=0.02)


def test_integer_uniform_covers_every_value_evenly():
    x = _inverse_cdf(
        {"dist": "integer_uniform", "low": -2, "high": 1}, np.random.default_rng(2).random(40_000)
    )
    vals, counts = np.unique(x, return_counts=True)
    assert list(vals) == [-2, -1, 0, 1]
    assert counts.min() / counts.max() > 0.9


def test_unknown_distribution_is_rejected():
    with pytest.raises(ValueError, match="gamma"):
        _inverse_cdf({"dist": "gamma", "low": 0, "high": 1}, np.array([0.5]))


def test_every_parameter_has_a_documented_reason(dists):
    for name, spec in dists["parameters"].items():
        assert len(spec["why"]) > 20, name
        assert (
            spec["low"] <= spec["mode"] <= spec["high"]
            if "mode" in spec and spec["dist"] != "uniform"
            else True
        )


# --------------------------------------------------------------- evaluator
def test_no_dishes_no_storage_costs_and_earns_nothing(ev, dists):
    r = ev.evaluate(modes(dists), 0, 0.0)
    assert r["capex_inr"] == 0 and r["npv_inr"] == pytest.approx(0.0)
    assert math.isinf(r["simple_payback_years"]) and r["solar_fraction"] == 0.0


def test_capex_follows_the_inputs(ev, dists):
    p = modes(dists)
    r = ev.evaluate(p, 14, 1000.0)
    expected = (
        14 * 16.0 * p["dish_cost_per_m2_inr"] * (1 + p["retrofit_fraction"])
        + 1000.0 * p["storage_cost_per_mj_inr"]
    )
    assert r["capex_inr"] == pytest.approx(expected)


def test_unknown_weather_year_is_an_error_not_a_silent_fallback(ev, dists):
    with pytest.raises(ValueError, match="no weather data"):
        ev.evaluate({**modes(dists), "weather_year": 1999}, 14, 0.0)


def test_economic_inputs_move_the_npv_the_right_way(ev, dists):
    p = modes(dists)
    base = ev.evaluate(p, 14, 1000.0)["npv_inr"]
    assert ev.evaluate({**p, "lpg_price_inr": p["lpg_price_inr"] * 1.3}, 14, 1000.0)["npv_inr"] > base
    assert ev.evaluate({**p, "lpg_escalation": 0.05}, 14, 1000.0)["npv_inr"] > base
    assert ev.evaluate({**p, "discount_rate": 0.12}, 14, 1000.0)["npv_inr"] < base
    assert ev.evaluate({**p, "dish_cost_per_m2_inr": 32000.0}, 14, 1000.0)["npv_inr"] < base


def test_solar_fraction_does_not_fall_with_a_larger_store(ev, dists):
    p = modes(dists)
    sf = [ev.evaluate(p, 14, s)["solar_fraction"] for s in (0, 500, 1000, 3000)]
    assert sf == sorted(sf)


def test_irr_is_consistent_with_a_positive_npv(ev, dists):
    p = modes(dists)
    r = ev.evaluate(p, 14, 1000.0)
    irr = ev.irr(p, 14, 1000.0)
    assert (r["npv_inr"] > 0) == (irr > p["discount_rate"])


# --------------------------------------------------------------- Monte Carlo
def test_monte_carlo_is_reproducible_from_its_seed(ev):
    a = monte_carlo(ev, 14, 1000.0, n=30, seed=7)
    b = monte_carlo(ev, 14, 1000.0, n=30, seed=7)
    c = monte_carlo(ev, 14, 1000.0, n=30, seed=8)
    pd.testing.assert_frame_equal(a, b)
    assert not a["npv_inr"].equals(c["npv_inr"])


def test_monte_carlo_collapses_to_the_deterministic_case_without_spread(years, cfg, dists):
    flat = copy.deepcopy(dists)
    for spec in flat["parameters"].values():
        spec["low"] = spec["high"] = spec["mode"]
    flat["parameters"]["weather_year"]["low"] = flat["parameters"]["weather_year"]["high"] = 2014
    ev_flat = Evaluator(years, IIT_BOMBAY, cfg, flat)
    mc = monte_carlo(ev_flat, 14, 1000.0, n=10, seed=3)
    det = ev_flat.evaluate(modes(flat), 14, 1000.0)["npv_inr"]
    assert np.allclose(mc["npv_inr"], det)


def test_percentiles_are_ordered(ev):
    mc = monte_carlo(ev, 14, 1000.0, n=120, seed=4)
    q = mc["npv_inr"].quantile([0.1, 0.5, 0.9])
    assert q.iloc[0] < q.iloc[1] < q.iloc[2]


# --------------------------------------------------------------- Sobol
def test_inputs_that_cannot_matter_have_zero_sobol_index(ev):
    # With no store, the store's efficiency, loss and cost cannot affect the NPV.
    s = sobol_indices(ev, 14, 0.0, "npv_inr", n_base=16, seed=0)
    for name in ("storage_efficiency", "standing_loss_per_hour", "storage_cost_per_mj_inr"):
        assert abs(s.loc[name, "ST"]) < 1e-9, name
    assert s.loc["dish_cost_per_m2_inr", "ST"] > 0.05  # an input that obviously matters


def test_sobol_total_index_is_at_least_the_first_order_index(ev):
    s = sobol_indices(ev, 14, 1000.0, "npv_inr", n_base=32, seed=1)
    assert (s["ST"] >= s["S1"] - 0.15).all()  # estimator noise allowance at this small sample


# --------------------------------------------------------------- sizing
def test_sweep_has_one_row_per_design(ev, dists):
    sw = sizing_sweep(ev, modes(dists), [6, 10, 14], [0.0, 500.0])
    assert len(sw) == 6 and set(sw.n_dishes) == {6, 10, 14}


def test_pareto_front_drops_dominated_designs():
    df = pd.DataFrame(
        {"solar_fraction": [0.3, 0.5, 0.4, 0.8, 0.7], "lcoh_inr_per_mj": [2.0, 3.0, 4.0, 5.0, 6.0]}
    )
    front = pareto_front(df)
    assert list(front.index) == [0, 1, 3]  # (0.4, 4.0) and (0.7, 6.0) are beaten
