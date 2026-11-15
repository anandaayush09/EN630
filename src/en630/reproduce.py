"""Rebuild every number the final report prints from the inputs it states, and compare.

The result is a table, one row per printed figure: the reported value, the value recomputed
here, the relative difference and a verdict. Each row also carries ``expect``:

* ``"match"``: the report's number should come out within the tolerance that its printed
  precision justifies (for example 1e-6 for a figure given to six places);
* ``"gap"``: the report's number does **not** follow from its own stated inputs. These are
  kept as rows, never tuned away, and ``note`` says why.

The tests assert the expectation of every row, so a future edit that makes a gap vanish or a
match break is caught.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import dish, economics, fuel, load
from .config import load_config

__all__ = ["reproduce_final_report"]


def _row(group, quantity, unit, reported, recomputed, tol, expect, note=""):
    rel = abs(recomputed - reported) / abs(reported) if reported else float("nan")
    verdict = "reproduces" if rel <= tol else "differs"
    return {
        "group": group,
        "quantity": quantity,
        "unit": unit,
        "reported": reported,
        "recomputed": recomputed,
        "rel_diff": rel,
        "tolerance": tol,
        "verdict": verdict,
        "expect": expect,
        "note": note,
    }


def reproduce_final_report(cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Return the comparison table for all the final report figures that can be recomputed."""
    cfg = cfg or load_config()
    rows: list[dict[str, Any]] = []
    add = rows.append

    # ------------------------------------------------------------------ geometry (p.10)
    dd, site, op, rc = cfg["design_day"], cfg["site"], cfg["optics"], cfg["receiver"]
    delta = dish.declination_deg(dd["day_of_year"])
    add(_row("geometry", "declination, 17 May", "deg", 19.263625, delta, 1e-6, "match"))

    omega = dish.hour_angle_deg(
        dd["day_of_year"], dd["clock_time_h"], site["longitude_deg"], site["standard_longitude_deg"]
    )
    add(
        _row(
            "geometry",
            "hour angle, 12:30 IST",
            "deg",
            dd["hour_angle_reported_deg"],
            omega,
            1e-3,
            "gap",
            "Recomputed from the report's own equations; changes cos(theta) by less than 1e-5, so the "
            "optical efficiency is unaffected.",
        )
    )

    cos_t = dish.cos_incidence(
        dd["tilt_deg"], dd["azimuth_deg"], delta, dd["hour_angle_reported_deg"], dd["latitude_used_deg"]
    )
    add(_row("geometry", "cos(theta), 17 May 12:30", "-", 0.943822, cos_t, 1e-6, "match"))

    # ------------------------------------------------------------------ optics and receiver
    cr = dish.concentration_ratio(op["reflector_area_m2"], op["receiver_area_m2"])
    add(
        _row(
            "optics",
            "concentration ratio",
            "-",
            90.3091,
            cr,
            1e-3,
            "gap",
            "11.65 / 0.1294 = 90.0309; the printed 90.3091 looks like two transposed digits.",
        )
    )

    eta_opt = dish.optical_efficiency(cos_t, op["reflectivity_used"], op["receiver_absorptivity"])
    add(
        _row(
            "optics",
            "optical efficiency (reflectivity 0.92 as multiplied)",
            "-",
            0.607821,
            eta_opt,
            1e-6,
            "match",
        )
    )
    eta_opt_text = dish.optical_efficiency(cos_t, op["reflectivity_text"], op["receiver_absorptivity"])
    add(
        _row(
            "optics",
            "optical efficiency (reflectivity 0.9 as listed)",
            "-",
            0.607821,
            eta_opt_text,
            1e-3,
            "gap",
            "The text lists reflectivity 0.9 but the printed product uses 0.92.",
        )
    )

    t_sky = dish.sky_temperature_k(rc["ambient_temperature_k"], rc["sky_coefficient"], rc["sky_offset_k"])
    add(
        _row(
            "receiver",
            "sky temperature",
            "K",
            298.0,
            t_sky,
            5e-3,
            "match",
            "Printed coefficient 0.00553 corrected to 0.0553.",
        )
    )

    q_loss = dish.receiver_heat_loss_w(
        op["receiver_area_m2"],
        rc["convection_coeff_w_m2k"],
        rc["receiver_temperature_k"],
        rc["ambient_temperature_k"],
        t_sky,
        rc["emissivity"],
        rc["stefan_boltzmann"],
    )
    add(_row("receiver", "receiver heat loss", "W", 618.29, q_loss, 5e-4, "match"))

    absorbed = dish.absorbed_power_w(op["design_dni_w_m2"], op["reflector_area_m2"], eta_opt)
    add(_row("receiver", "energy absorbed by receiver", "W", 4708.9, absorbed, 1e-4, "match"))

    eta_rcv = dish.receiver_efficiency(absorbed, q_loss)
    add(_row("receiver", "receiver thermal efficiency", "-", 0.8687, eta_rcv, 1e-3, "match"))
    add(_row("receiver", "overall efficiency", "-", 0.528, eta_opt * eta_rcv, 2e-3, "match"))

    # ------------------------------------------------------------------ load (pp.11-12)
    ld, fu = cfg["load"], cfg["fuel"]
    cyl_mj = fuel.cylinder_energy_mj(fu["cylinder_mass_kg"], fu["calorific_value_mj_kg"])
    add(_row("load", "energy in one LPG cylinder", "MJ", 654.6, cyl_mj, 1e-4, "match"))

    pot = load.rice_pot_mj(ld["rice_pot"], ld["ambient_c"])
    add(
        _row(
            "load",
            "heat for one rice pot",
            "MJ",
            ld["rice_pot"]["reported_pot_mj"],
            pot,
            2e-3,
            "match",
            "0.08 % low: the report does not state the specific heat of water it used (4.186 assumed).",
        )
    )
    add(
        _row(
            "load",
            "heat for one 150 L milk batch",
            "MJ",
            41.84,
            load.milk_batch_mj(ld["milk"], ld["ambient_c"]),
            1e-4,
            "match",
        )
    )

    hw = ld["hot_water"]
    hw_day = load.sensible_heat_mj(
        hw["mass_kg"], hw["cp_kj_kgk"], hw["final_temperature_c"] - ld["ambient_c"]
    )
    add(_row("load", "hot water, whole day (100 kg, cp 4.186)", "MJ", 31.40, hw_day, 1e-3, "match"))
    printed = load.sensible_heat_mj(100 * ld["milk"]["density_kg_l"], ld["milk"]["cp_kj_kgk"], 75.0)
    add(
        _row(
            "load",
            "hot water, whole day (100 L x 1.035 x cp 3.85 as printed)",
            "MJ",
            31.40,
            printed,
            1e-3,
            "gap",
            "The inputs printed beside this result give 29.89 MJ, not 31.40 MJ.",
        )
    )

    table = load.demand_table(ld, cyl_mj)
    add(
        _row(
            "load",
            "curry and dal, whole day",
            "MJ",
            589.14,
            table["curry_and_dal"],
            1e-4,
            "match",
            "The report rounds the cylinder energy to 654.6 MJ (14.2 x 46.1 = 654.62).",
        )
    )
    add(_row("load", "daily total (Table 4)", "MJ", 939.86, table["total"], 1e-4, "match"))
    steam = load.design_steam_heat_mj(table["total"], ld["safety_factor"], ld["pot_efficiency"])
    add(_row("load", "design steam heat", "MJ", 1435.89, steam, 1e-4, "match"))

    # ------------------------------------------------------------------ sizing (p.12)
    sz = cfg["sizing"]
    per_dish = dish.heat_per_dish_j(
        op["design_dni_w_m2"],
        op["reflector_area_m2"],
        sz["seconds_per_hour"],
        sz["design_hours_per_day"],
        sz["receiver_efficiency_used"],
        0.6078,
    )
    n_exact = dish.dishes_required(steam * 1e6, per_dish)
    add(
        _row(
            "sizing",
            "dishes required (unrounded)",
            "-",
            14.02,
            n_exact,
            1e-3,
            "match",
            "Printed 14.02, recomputed 14.028 (report truncates).",
        )
    )
    add(_row("sizing", "dishes required (rounded)", "-", 14, float(round(n_exact)), 0.0, "match"))
    per_dish_derived = dish.heat_per_dish_j(
        op["design_dni_w_m2"],
        op["reflector_area_m2"],
        sz["seconds_per_hour"],
        sz["design_hours_per_day"],
        eta_rcv,
        0.6078,
    )
    n_derived = dish.dishes_required(steam * 1e6, per_dish_derived)
    add(
        _row(
            "sizing",
            "dishes with the derived receiver efficiency 0.8687",
            "-",
            14.02,
            n_derived,
            1e-3,
            "gap",
            f"The product uses 0.8626, not the derived 0.8687. With 0.8687 the unrounded count is "
            f"{n_derived:.2f}, which still rounds to {round(n_derived)}: the conclusion does not depend on "
            "the inconsistency.",
        )
    )

    # ------------------------------------------------------------------ fuel and CO2 (p.13)
    cyl_eq = fuel.cylinders_equivalent(1436.0, 655.0)
    add(_row("fuel", "LPG-equivalent cylinders (1436 / 655)", "cylinders/day", 2.2, cyl_eq, 5e-3, "match"))
    saved = cyl_eq / 0.6
    add(
        _row(
            "fuel",
            "cylinders saved per day (/ stove efficiency 0.6)",
            "cylinders/day",
            3.67,
            saved,
            5e-3,
            "match",
        )
    )
    add(_row("fuel", "LPG saved per day", "kg", 52.06, saved * fu["cylinder_mass_kg"], 5e-3, "match"))
    co2_cyl = fuel.co2_per_cylinder_kg(
        fu["cylinder_mass_kg"], fu["carbon_mass_per_propane_mass"], fu["co2_per_carbon_mass"]
    )
    add(_row("fuel", "CO2 per cylinder", "kg", 42.6, co2_cyl, 1e-3, "match"))
    add(
        _row(
            "fuel",
            "CO2 saved per year (975 cylinders)",
            "t",
            41.5,
            co2_cyl * fu["cylinders_per_year_implied"] / 1000,
            1e-3,
            "match",
        )
    )
    add(
        _row(
            "fuel",
            "cylinders per year implied by the fuel saving",
            "cylinders",
            975,
            1311631.57 / fu["cylinder_price_inr"],
            5e-4,
            "match",
        )
    )
    add(
        _row(
            "fuel",
            "cylinders per year from 3.67 per day",
            "cylinders",
            975,
            saved * 365,
            5e-2,
            "gap",
            "3.67 cylinders a day for 365 days is about 1340 a year, not 975: the final report's CO2 and "
            "saving figures use a different, unexplained basis from its own daily figure.",
        )
    )

    # ------------------------------------------------------------------ economics (p.14-15)
    ec = cfg["economics"]
    dish_cost = ec["dish_area_for_cost_m2"] * ec["cost_per_m2_inr"]
    capital = ec["number_of_dishes"] * dish_cost
    add(_row("economics", "cost of one 16 m2 dish", "INR", 400000, dish_cost, 1e-9, "match"))
    add(
        _row(
            "economics",
            "total system cost, 14 dishes",
            "INR",
            5600000,
            capital,
            1e-9,
            "match",
            "Equals 14 x 400,000: excludes the retrofit allowance.",
        )
    )
    with_retrofit = capital * (1 + ec["retrofit_fraction"])
    add(
        _row(
            "economics",
            "total system cost including the stated 30 % retrofit",
            "INR",
            5600000,
            with_retrofit,
            1e-3,
            "gap",
            "The report lists a 120,000-per-dish retrofit just above the total but does not add it.",
        )
    )

    saving = ec["annual_fuel_saving_inr"]
    spp = economics.simple_payback_years(capital, saving)
    add(
        _row("economics", "simple payback", "years", 4.269, spp, 2e-4, "match", "4.2695 is printed as 4.269.")
    )
    add(_row("economics", "return on investment", "%", 23.42, economics.roi_percent(spp), 1e-3, "match"))

    om, salvage = ec["om_fraction"] * capital, ec["salvage_fraction"] * capital
    add(_row("economics", "annual O&M", "INR", 112000, om, 1e-9, "match"))
    add(_row("economics", "salvage value", "INR", 280000, salvage, 1e-9, "match"))

    parts = economics.npv_project(capital, saving, om, salvage, ec["discount_rate"], ec["life_years"])
    add(_row("economics", "PV of fuel saving", "INR", 9976370, parts["pv_saving"], 1e-6, "match"))
    add(_row("economics", "PV of O&M", "INR", 851881, parts["pv_om"], 1e-6, "match"))
    add(_row("economics", "PV of salvage", "INR", 67029.77, parts["pv_salvage"], 1e-6, "match"))
    add(
        _row(
            "economics",
            "NPV of the project",
            "INR",
            3591518,
            parts["npv"],
            1e-5,
            "match",
            "Differs by about 5 rupees: the report rounds the PV of the saving.",
        )
    )
    add(
        _row(
            "economics",
            "benefit-cost ratio",
            "-",
            1.556,
            economics.benefit_cost_ratio(parts, capital),
            1e-3,
            "match",
            "1.5567 is printed as 1.556 (truncated, not rounded).",
        )
    )
    irr_value = economics.irr(capital, saving - om, salvage, ec["life_years"])
    add(_row("economics", "internal rate of return", "%", 20.116, irr_value * 100, 1e-4, "match"))

    return pd.DataFrame(rows)
