"""Hour-by-hour simulation of the dish field, a steam store and LPG backup over a typical year.

The final report sizes the field on a daily total and admits it has no storage, so it cannot say how much of
the load is met when. This module answers that: each of the 8760 hours the collectors deliver
heat, the kitchen draws steam, a store (possibly of zero size) absorbs the difference, and LPG
covers whatever solar and the store cannot.

Energy bookkeeping (all in MJ of steam heat, per hour)::

    collected = direct + stored_in_gross + curtailed
    demand    = direct + from_store + lpg_backup

and the store follows ``level_next = (level + stored_in) * (1 - standing_loss) - drawn``, so the
balance closes to rounding (tested).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from . import dish, fuel, load
from .irradiance import tracker_beam
from .weather import Site

__all__ = [
    "Result",
    "annual_from_arrays",
    "collector_heat_from_arrays",
    "collector_heat_mj",
    "daily_energy",
    "demand_array",
    "demand_series",
    "simulate",
]


@dataclass(frozen=True)
class Result:
    """Hourly flows and annual totals of one simulation run."""

    hourly: pd.DataFrame
    annual: dict[str, float]


def collector_heat_from_arrays(
    beam_w_m2: np.ndarray,
    dni_w_m2: np.ndarray,
    temp_air_c: np.ndarray,
    cfg: dict[str, Any],
    reflectivity: float | None = None,
) -> np.ndarray:
    """Useful heat per dish per hour (MJ) from already prepared arrays (the fast path).

    ``beam_w_m2`` is the beam on the aperture (from ``tracker_beam``). Splitting this out of
    :func:`collector_heat_mj` lets the uncertainty analysis reuse the geometry for thousands of runs.
    """
    col, op, rc = cfg["collector"], cfg["optics"], cfg["receiver"]
    rho = col["reflectivity"] if reflectivity is None else reflectivity
    absorbed = beam_w_m2 * col["aperture_area_m2"] * rho * op["receiver_absorptivity"]
    t_amb = temp_air_c + 273.15
    t_sky = dish.sky_temperature_k(t_amb, rc["sky_coefficient"], rc["sky_offset_k"])
    loss = dish.receiver_heat_loss_w(
        op["receiver_area_m2"],
        rc["convection_coeff_w_m2k"],
        rc["receiver_temperature_k"],
        t_amb,
        t_sky,
        rc["emissivity"],
        rc["stefan_boltzmann"],
    )
    useful_w = np.where(dni_w_m2 >= col["minimum_dni_w_m2"], np.clip(absorbed - loss, 0.0, None), 0.0)
    return useful_w * 3600.0 / 1e6


def collector_heat_mj(
    weather: pd.DataFrame, site: Site, cfg: dict[str, Any], timestamp="centre"
) -> pd.Series:
    """Useful heat per dish per hour, in MJ.

    absorbed = (beam on the aperture) x aperture area x reflectivity x absorptivity;
    useful = absorbed - receiver loss, floored at zero. The beam on the aperture comes from the
    tracker model (``cos(declination)`` for the polar tracker). Receiver loss is evaluated at the
    receiver temperature with the hour's own ambient temperature, so it varies through the year.
    Hours with DNI below the threshold (200 W/m2 in both reports) contribute nothing.
    """
    beam = tracker_beam(weather, site, cfg["collector"]["tracker"], timestamp).to_numpy()
    heat = collector_heat_from_arrays(beam, weather["dni"].to_numpy(), weather["temp_air"].to_numpy(), cfg)
    return pd.Series(heat, index=weather.index, name="collector_mj_per_dish")


def demand_array(index: pd.DatetimeIndex, site: Site, cfg: dict[str, Any], timestamp="centre") -> np.ndarray:
    """Steam demand in MJ for each hour of the year, from the meal schedule in the config.

    ``index`` is the weather index; its local hour (the start of the hour in IST) selects the
    profile entry. The same daily profile applies to every day of the year (a mess that runs
    365 days; holidays are ignored).
    """
    fu, ld = cfg["fuel"], cfg["load"]
    cyl = fuel.cylinder_energy_mj(fu["cylinder_mass_kg"], fu["calorific_value_mj_kg"])
    profile = load.hourly_steam_profile(
        load.meal_heat_mj(ld, cyl), cfg["schedule"], ld["safety_factor"], ld["pot_efficiency"]
    )
    mid = index + pd.Timedelta(minutes=30) if timestamp == "start" else index
    # PVGIS stamps label the centre of the hour, so the local clock hour starts 30 min earlier.
    local_hour = (mid.tz_convert(site.tz) - pd.Timedelta(minutes=30)).hour
    return np.asarray(profile)[np.asarray(local_hour)]


def demand_series(index: pd.DatetimeIndex, site: Site, cfg: dict[str, Any], timestamp="centre") -> pd.Series:
    """Same as :func:`demand_array` but as a named Series on ``index``."""
    return pd.Series(demand_array(index, site, cfg, timestamp), index=index, name="demand_mj")


def _dispatch(collected: np.ndarray, demand: np.ndarray, store: dict[str, float]) -> dict[str, np.ndarray]:
    """Sequential hourly dispatch: direct use first, then store, then (outside) LPG."""
    n = len(collected)
    cap = store["capacity_mj"]
    eta_c, eta_d, loss = (
        store["charge_efficiency"],
        store["discharge_efficiency"],
        store["standing_loss_per_hour"],
    )
    level = cap * store["initial_fraction"]

    direct = np.zeros(n)
    stored_in = np.zeros(n)  # gross heat sent to the store (before charging loss)
    curtailed = np.zeros(n)
    from_store = np.zeros(n)  # heat delivered to the load from the store
    levels = np.zeros(n)

    for h in range(n):
        d = min(collected[h], demand[h])
        direct[h] = d
        surplus = collected[h] - d
        need = demand[h] - d

        if cap > 0 and surplus > 0:
            room = (cap - level) / eta_c  # gross heat that fits
            put = min(surplus, room)
            stored_in[h] = put
            level += put * eta_c
            curtailed[h] = surplus - put
        else:
            curtailed[h] = surplus

        if cap > 0 and need > 0 and level > 0:
            out = min(need, level * eta_d)  # delivered heat
            from_store[h] = out
            level -= out / eta_d

        level *= 1.0 - loss if cap > 0 else 1.0
        levels[h] = level
    return {
        "direct": direct,
        "stored_in": stored_in,
        "curtailed": curtailed,
        "from_store": from_store,
        "store_level": levels,
    }


def annual_from_arrays(
    per_dish_mj: np.ndarray,
    demand_mj: np.ndarray,
    cfg: dict[str, Any],
    n_dishes: int,
    store: dict[str, float],
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Dispatch a year from prepared arrays and return (hourly flows, annual totals).

    This is the engine behind :func:`simulate`; the uncertainty analysis calls it directly with
    precomputed arrays so that thousands of runs do not repeat the solar geometry.
    """
    if n_dishes < 0:
        raise ValueError("number of dishes cannot be negative")
    if store["capacity_mj"] < 0:
        raise ValueError("storage capacity cannot be negative")
    collected = per_dish_mj * n_dishes
    flows = _dispatch(collected, demand_mj, store)
    solar_to_load = flows["direct"] + flows["from_store"]
    lpg = demand_mj - solar_to_load
    flows["collected"], flows["demand"], flows["lpg"] = collected, demand_mj, lpg

    fu, bk = cfg["fuel"], cfg["backup"]
    cyl_mj = fuel.cylinder_energy_mj(fu["cylinder_mass_kg"], fu["calorific_value_mj_kg"])
    cylinders = float(solar_to_load.sum() / cyl_mj / bk["stove_efficiency"])
    co2_cyl = fuel.co2_per_cylinder_kg(
        fu["cylinder_mass_kg"], fu["carbon_mass_per_propane_mass"], fu["co2_per_carbon_mass"]
    )
    annual = {
        "demand_mj": float(demand_mj.sum()),
        "collected_mj": float(collected.sum()),
        "solar_to_load_mj": float(solar_to_load.sum()),
        "lpg_backup_mj": float(lpg.sum()),
        "curtailed_mj": float(flows["curtailed"].sum()),
        "solar_fraction": float(solar_to_load.sum() / demand_mj.sum()),
        "useful_collector_mwh": float(collected.sum() / 3600.0),
        "cylinders_displaced": cylinders,
        "co2_avoided_t": cylinders * co2_cyl / 1000.0,
    }
    return flows, annual


def simulate(
    weather: pd.DataFrame,
    site: Site,
    cfg: dict[str, Any],
    n_dishes: int,
    storage_mj: float | None = None,
    timestamp: str = "centre",
) -> Result:
    """Run one year. ``storage_mj`` overrides the config's capacity (0 means no store).

    Returns the hourly table and annual totals: solar fraction (share of the steam demand met by
    solar, directly or through the store), LPG backup heat, cylinders displaced (the final report convention:
    displaced steam heat over the cylinder energy and the 0.6 stove efficiency) and CO2 avoided.
    """
    store = dict(cfg["storage"])
    if storage_mj is not None:
        store["capacity_mj"] = float(storage_mj)

    per_dish = collector_heat_mj(weather, site, cfg, timestamp).to_numpy()
    demand = demand_array(weather.index, site, cfg, timestamp)
    flows, annual = annual_from_arrays(per_dish, demand, cfg, n_dishes, store)
    hourly = pd.DataFrame(
        {
            "collected_mj": flows["collected"],
            "demand_mj": flows["demand"],
            "direct_mj": flows["direct"],
            "stored_in_mj": flows["stored_in"],
            "from_store_mj": flows["from_store"],
            "curtailed_mj": flows["curtailed"],
            "lpg_backup_mj": flows["lpg"],
            "store_level_mj": flows["store_level"],
        },
        index=weather.index,
    )
    return Result(hourly=hourly, annual=annual)


def daily_energy(result: Result, site: Site) -> pd.DataFrame:
    """Collected and demanded heat per local day, handy for 'how many days meet the load'."""
    local = result.hourly.copy()
    local.index = local.index.tz_convert(site.tz)
    return local[["collected_mj", "demand_mj"]].groupby(local.index.date).sum()
