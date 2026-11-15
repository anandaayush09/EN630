"""Regression tests: the numbers printed in the final report must come out of the stated inputs.

Rows marked expect="gap" are places where the report does not follow from its own inputs.
They are tested too, so a documented gap cannot silently turn into a match or vice versa.
"""

import math

import pytest

from en630 import dish, economics, fuel, load
from en630.config import get, load_config
from en630.reproduce import reproduce_final_report


@pytest.fixture(scope="module")
def table():
    return reproduce_final_report()


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# ------------------------------------------------------------ the whole comparison table
def test_every_expected_match_reproduces(table):
    bad = table[(table.expect == "match") & (table.verdict != "reproduces")]
    assert bad.empty, bad[["quantity", "reported", "recomputed", "rel_diff", "tolerance"]].to_string()


def test_every_documented_gap_is_a_real_gap(table):
    fixed = table[(table.expect == "gap") & (table.verdict == "reproduces")]
    assert fixed.empty, fixed[["quantity", "reported", "recomputed"]].to_string()


def test_every_gap_has_an_explanation(table):
    gaps = table[table.expect == "gap"]
    assert len(gaps) >= 7
    assert (gaps.note.str.len() > 20).all()


def test_table_covers_all_groups(table):
    assert set(table.group) == {"geometry", "optics", "receiver", "load", "sizing", "fuel", "economics"}


# ------------------------------------------------------------ headline numbers
def test_headline_efficiencies_and_dishes(table):
    v = table.set_index("quantity").recomputed
    assert v["optical efficiency (reflectivity 0.92 as multiplied)"] == pytest.approx(0.607821, abs=1e-6)
    assert v["receiver thermal efficiency"] == pytest.approx(0.8687, abs=1e-4)
    assert v["overall efficiency"] == pytest.approx(0.528, abs=1e-3)
    assert v["dishes required (rounded)"] == 14


def test_headline_economics(table):
    v = table.set_index("quantity").recomputed
    assert v["NPV of the project"] == pytest.approx(3_591_518, abs=10)
    assert v["internal rate of return"] == pytest.approx(20.116, abs=1e-3)
    assert v["simple payback"] == pytest.approx(4.269, abs=1e-3)


def test_conclusion_of_fourteen_dishes_survives_the_efficiency_inconsistency(table):
    v = table.set_index("quantity").recomputed
    assert round(v["dishes with the derived receiver efficiency 0.8687"]) == 14


# ------------------------------------------------------------ dish functions
def test_declination_extremes():
    assert dish.declination_deg(172) == pytest.approx(23.45, abs=0.05)  # June solstice
    assert dish.declination_deg(355) == pytest.approx(-23.45, abs=0.05)  # December solstice


def test_hour_angle_is_zero_at_solar_noon_on_standard_meridian():
    # On the standard meridian, clock time 12 - E/60 is solar noon.
    e = dish.equation_of_time_min(100)
    omega = dish.hour_angle_deg(100, 12 - e / 60, 82.5, 82.5)
    assert omega == pytest.approx(0.0, abs=1e-9)


def test_cos_incidence_flat_surface_equals_cos_zenith():
    # beta = 0: incidence angle on a horizontal plane is the zenith angle (final report equation 8).
    phi, delta, omega = 19.15, 10.0, 25.0
    cos_z = math.cos(math.radians(phi)) * math.cos(math.radians(delta)) * math.cos(
        math.radians(omega)
    ) + math.sin(math.radians(phi)) * math.sin(math.radians(delta))
    assert dish.cos_incidence(0.0, 0.0, delta, omega, phi) == pytest.approx(cos_z, abs=1e-12)


def test_zero_dni_gives_zero_absorbed_power_and_no_dishes_help():
    assert dish.absorbed_power_w(0.0, 11.65, 0.6) == 0.0


def test_receiver_efficiency_with_no_absorbed_power_is_undefined():
    with pytest.raises(ZeroDivisionError):
        dish.receiver_efficiency(0.0, 100.0)


def test_loss_grows_with_receiver_temperature():
    low = dish.receiver_heat_loss_w(0.13, 25, 400, 300, 290, 0.2)
    high = dish.receiver_heat_loss_w(0.13, 25, 500, 300, 290, 0.2)
    assert high > low > 0


def test_zero_receiver_area_means_zero_loss():
    assert dish.receiver_heat_loss_w(0.0, 25, 473, 301, 298, 0.2) == 0.0


# ------------------------------------------------------------ load, fuel, economics
def test_load_demand_scales_with_safety_factor(cfg):
    base = load.design_steam_heat_mj(939.86, 1.0, 0.72)
    assert load.design_steam_heat_mj(939.86, 1.1, 0.72) == pytest.approx(base * 1.1)


def test_demand_table_total_is_sum_of_parts(cfg):
    cyl = fuel.cylinder_energy_mj(get(cfg, "fuel.cylinder_mass_kg"), get(cfg, "fuel.calorific_value_mj_kg"))
    t = load.demand_table(cfg["load"], cyl)
    assert t["total"] == pytest.approx(sum(v for k, v in t.items() if k != "total"))


def test_annuity_factor_edge_cases():
    assert economics.annuity_factor(0.0, 15) == 15
    assert economics.annuity_factor(0.10, 15) == pytest.approx(7.606079506, abs=1e-8)


def test_irr_makes_npv_zero():
    r = economics.irr(5_600_000, 1_199_631.57, 280_000, 15)
    assert economics.npv_at_rate(5_600_000, 1_199_631.57, 280_000, r, 15) == pytest.approx(0.0, abs=1e-2)


def test_irr_is_negative_when_the_project_does_not_pay_back():
    assert economics.irr(5_000_000, 100_000, 0.0, 15) < 0


def test_irr_rejects_a_project_with_no_positive_cash_flow():
    with pytest.raises(ValueError):
        economics.irr(1e6, 0.0, 0.0, 15)


def test_co2_factor_matches_stoichiometry():
    assert fuel.co2_per_cylinder_kg(14.2, 36 / 44, 44 / 12) == pytest.approx(42.6, abs=1e-9)


def test_config_override_changes_result(cfg):
    cheaper = load_config()
    cheaper["economics"]["cost_per_m2_inr"] = 18000.0  # the performance report's cost basis
    base_npv = reproduce_final_report(cfg).set_index("quantity").recomputed["NPV of the project"]
    new_npv = reproduce_final_report(cheaper).set_index("quantity").recomputed["NPV of the project"]
    assert new_npv > base_npv
