"""Techno-economic evaluation of a design, and how uncertain it is.

``Evaluator`` turns one set of input values (a dictionary with the names in
``configs/uncertainty.yaml``) and one design (number of dishes, store size) into solar fraction,
cylinders displaced, capital cost, NPV, levelised cost of heat, payback and IRR. On top of it:

* :func:`monte_carlo` draws the inputs from their distributions and reports percentiles;
* :func:`sobol_indices` ranks which inputs drive the NPV (variance-based sensitivity, SALib);
* :func:`sizing_sweep` and :func:`pareto_front` explore the design space at fixed inputs.

Weather years are precomputed once (beam on the aperture, ambient temperature, cleaned DNI), so a
single evaluation costs one dispatch loop of 8760 steps.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample

from . import economics, fuel
from .config import CONFIG_DIR
from .irradiance import tracker_beam
from .simulate import annual_from_arrays, collector_heat_from_arrays, demand_array
from .weather import Site, clean_dni

__all__ = [
    "Evaluator",
    "load_distributions",
    "modes",
    "monte_carlo",
    "pareto_front",
    "sample_inputs",
    "sizing_sweep",
    "sobol_indices",
]


def load_distributions(path: str | Path | None = None) -> dict[str, Any]:
    """Read ``configs/uncertainty.yaml``."""
    path = Path(path) if path is not None else CONFIG_DIR / "uncertainty.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def modes(dists: dict[str, Any]) -> dict[str, float]:
    """The base-case value of every uncertain input."""
    return {k: v["mode"] for k, v in dists["parameters"].items()}


def _inverse_cdf(spec: dict[str, Any], u: np.ndarray) -> np.ndarray:
    """Map uniform [0, 1) samples to a distribution described in the YAML file."""
    kind, lo = spec["dist"], spec["low"]
    hi = spec["high"]
    if kind == "uniform":
        return lo + (hi - lo) * u
    if kind == "integer_uniform":
        return np.minimum(np.floor(lo + (hi - lo + 1) * u), hi)
    if kind == "triangular":
        mode = spec["mode"]
        c = (mode - lo) / (hi - lo) if hi > lo else 0.5
        return np.where(
            u < c,
            lo + np.sqrt(u * (hi - lo) * (mode - lo)),
            hi - np.sqrt((1.0 - u) * (hi - lo) * (hi - mode)),
        )
    raise ValueError(f"unknown distribution {kind!r}")


def sample_inputs(dists: dict[str, Any], u: np.ndarray) -> pd.DataFrame:
    """Turn an (n, k) array of uniform samples into input values, columns in YAML order."""
    names = list(dists["parameters"])
    return pd.DataFrame({k: _inverse_cdf(dists["parameters"][k], u[:, i]) for i, k in enumerate(names)})


class Evaluator:
    """Evaluate designs for given input values over a set of weather years.

    ``years`` maps a label (a year number, or ``"TMY"``) to a weather table with columns ``dni`` (raw
    or cleaned; it is cleaned here), ``temp_air`` and a UTC index with centre-of-hour stamps.
    """

    def __init__(
        self, years: dict[Any, pd.DataFrame], site: Site, cfg: dict[str, Any], dists: dict[str, Any]
    ):
        self.site, self.cfg, self.dists = site, cfg, dists
        self.fixed = dists["economics_fixed"]
        self._wx: dict[Any, dict[str, np.ndarray]] = {}
        self._demand_cache: dict[tuple[Any, int], np.ndarray] = {}
        self._index = {}
        for label, df in years.items():
            df = df.copy()
            df["dni"] = clean_dni(df, site, "centre")
            self._index[label] = df.index
            self._wx[label] = {
                "dni": df["dni"].to_numpy(),
                "temp": df["temp_air"].to_numpy(),
                "beam": tracker_beam(df, site, cfg["collector"]["tracker"], "centre").to_numpy(),
            }

    # ------------------------------------------------------------------ internals
    def _cfg_for(self, p: dict[str, float]) -> dict[str, Any]:
        cfg = copy.copy(self.cfg)
        sched = {k: list(v) for k, v in self.cfg["schedule"].items()}
        shift = int(p["dinner_shift_h"])
        sched["dinner"] = [h + shift for h in sched["dinner"]]
        cfg["schedule"] = sched
        return cfg

    def _demand(self, label: Any, shift: int, cfg: dict[str, Any]) -> np.ndarray:
        key = (label, shift)
        if key not in self._demand_cache:
            self._demand_cache[key] = demand_array(self._index[label], self.site, cfg, "centre")
        return self._demand_cache[key]

    def _label(self, year: float) -> Any:
        """Weather table for ``year``; with a single table (e.g. the typical year) it is always used."""
        if len(self._wx) == 1:
            return next(iter(self._wx))
        if int(year) not in self._wx:
            raise ValueError(f"no weather data for year {int(year)}; available: {sorted(self._wx)}")
        return int(year)

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, p: dict[str, float], n_dishes: int, storage_mj: float) -> dict[str, float]:
        """One design under one set of inputs."""
        label = self._label(p["weather_year"])
        w = self._wx[label]
        cfg = self._cfg_for(p)
        rho = self.cfg["collector"]["reflectivity"] * p["optical_multiplier"]
        per_dish = collector_heat_from_arrays(w["beam"], w["dni"], w["temp"], cfg, reflectivity=rho)
        demand = self._demand(label, int(p["dinner_shift_h"]), cfg)
        store = {
            **self.cfg["storage"],
            "capacity_mj": float(storage_mj),
            "charge_efficiency": p["storage_efficiency"],
            "discharge_efficiency": p["storage_efficiency"],
            "standing_loss_per_hour": p["standing_loss_per_hour"],
        }
        _, ann = annual_from_arrays(per_dish, demand, cfg, n_dishes, store)

        # Annual figures are per 365 days (every weather year has 8760 hours).
        fx = self.fixed
        capex = (
            n_dishes * fx["dish_area_m2"] * p["dish_cost_per_m2_inr"] * (1.0 + p["retrofit_fraction"])
            + storage_mj * p["storage_cost_per_mj_inr"]
        )
        om, salvage = fx["om_fraction"] * capex, fx["salvage_fraction"] * capex
        n, r, g = fx["life_years"], p["discount_rate"], p["lpg_escalation"]
        saving_y1 = ann["cylinders_displaced"] * p["lpg_price_inr"]
        pv_saving = saving_y1 * economics.escalating_annuity_factor(r, n, g)
        pv_om = om * economics.annuity_factor(r, n)
        pv_salv = economics.present_value_lump(salvage, r, n)
        npv = pv_saving + pv_salv - pv_om - capex
        out = {
            **ann,
            "capex_inr": capex,
            "npv_inr": npv,
            "benefit_cost": (pv_saving + pv_salv) / (capex + pv_om) if capex > 0 else float("nan"),
            "simple_payback_years": capex / saving_y1 if saving_y1 > 0 else float("inf"),
            "lcoh_inr_per_mj": economics.lcoh_inr_per_mj(capex, om, salvage, r, n, ann["solar_to_load_mj"]),
        }
        fu = self.cfg["fuel"]
        cyl_mj = fuel.cylinder_energy_mj(fu["cylinder_mass_kg"], fu["calorific_value_mj_kg"])
        out["lpg_inr_per_mj"] = p["lpg_price_inr"] / (cyl_mj * self.cfg["backup"]["stove_efficiency"])
        return out

    def irr(self, p: dict[str, float], n_dishes: int, storage_mj: float) -> float:
        """IRR of the design (rate at which the NPV above is zero); nan if it has none."""
        res = self.evaluate(p, n_dishes, storage_mj)
        fx = self.fixed
        saving_y1 = res["cylinders_displaced"] * p["lpg_price_inr"]
        om = fx["om_fraction"] * res["capex_inr"]
        flows = [-res["capex_inr"]] + [
            saving_y1 * (1.0 + p["lpg_escalation"]) ** (t - 1)
            - om
            + (fx["salvage_fraction"] * res["capex_inr"] if t == fx["life_years"] else 0.0)
            for t in range(1, fx["life_years"] + 1)
        ]
        try:
            return economics.irr_of_flows(flows)
        except ValueError:
            return float("nan")


# ---------------------------------------------------------------------- analyses
def monte_carlo(
    ev: Evaluator, n_dishes: int, storage_mj: float, n: int = 1000, seed: int = 0
) -> pd.DataFrame:
    """Draw ``n`` input sets (reproducibly from ``seed``) and evaluate the design on each."""
    rng = np.random.default_rng(seed)
    draws = sample_inputs(ev.dists, rng.random((n, len(ev.dists["parameters"]))))
    rows = [ev.evaluate(row.to_dict(), n_dishes, storage_mj) for _, row in draws.iterrows()]
    return pd.concat([draws, pd.DataFrame(rows)], axis=1)


def sobol_indices(
    ev: Evaluator, n_dishes: int, storage_mj: float, output: str = "npv_inr", n_base: int = 64, seed: int = 0
) -> pd.DataFrame:
    """First-order and total Sobol indices of ``output`` with respect to every uncertain input.

    Uses Saltelli sampling from SALib (``n_base * (2k + 2)`` model runs for ``k`` inputs). The
    integer inputs are treated as continuous in [0, 1) and mapped back through their distribution.
    """
    names = list(ev.dists["parameters"])
    problem = {"num_vars": len(names), "names": names, "bounds": [[0.0, 1.0]] * len(names)}
    u = sobol_sample.sample(problem, n_base, calc_second_order=False, scramble=True, seed=seed)
    inputs = sample_inputs(ev.dists, np.clip(u, 0.0, 1.0 - 1e-12))
    y = np.array([ev.evaluate(row.to_dict(), n_dishes, storage_mj)[output] for _, row in inputs.iterrows()])
    res = sobol_analyze.analyze(problem, y, calc_second_order=False, print_to_console=False, seed=seed)
    return pd.DataFrame(
        {"S1": res["S1"], "S1_conf": res["S1_conf"], "ST": res["ST"], "ST_conf": res["ST_conf"]}, index=names
    )


def sizing_sweep(
    ev: Evaluator, p: dict[str, float], dishes: list[int], storages: list[float]
) -> pd.DataFrame:
    """Every (dishes, storage) pair evaluated at the same input values ``p``."""
    rows = []
    for n in dishes:
        for s in storages:
            r = ev.evaluate(p, n, s)
            rows.append({"n_dishes": n, "storage_mj": s, **r})
    return pd.DataFrame(rows)


def pareto_front(
    df: pd.DataFrame, maximise: str = "solar_fraction", minimise: str = "lcoh_inr_per_mj"
) -> pd.DataFrame:
    """Designs not beaten on both objectives at once (higher ``maximise``, lower ``minimise``)."""
    d = (
        df.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=[maximise, minimise])
        .sort_values([minimise, maximise], ascending=[True, False])
    )
    best, keep = -np.inf, []
    for idx, row in d.iterrows():
        if row[maximise] > best + 1e-12:
            keep.append(idx)
            best = row[maximise]
    return d.loc[keep].sort_values(maximise)
