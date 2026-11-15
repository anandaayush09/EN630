"""Command-line entry point: ``en630 fetch-data | reproduce | simulate | sweep``.

Why argparse and not a third-party CLI library: four small commands do not justify a new
dependency. Outputs are printed and, where useful, written under ``outputs/`` (ignored by git).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .config import load_config
from .reproduce import reproduce_final_report
from .simulate import simulate
from .uncertainty import Evaluator, load_distributions, modes, pareto_front, sizing_sweep
from .weather import (
    IIT_BOMBAY,
    clean_dni,
    fetch_pvgis_multiyear,
    fetch_pvgis_tmy,
    read_tmy_csv,
)

DATA = Path(__file__).resolve().parents[2] / "data"
OUT = Path("outputs")


def _tmy() -> pd.DataFrame:
    df = read_tmy_csv(DATA / "pvgis_tmy_iitb.csv")
    df["dni"] = clean_dni(df, IIT_BOMBAY, "centre")
    return df


def cmd_fetch(args: argparse.Namespace) -> int:
    """Download the typical year and the 2005-2023 hourly series from PVGIS into data/."""
    fetch_pvgis_tmy(IIT_BOMBAY, DATA / "pvgis_tmy_iitb.csv")
    print(f"wrote {DATA / 'pvgis_tmy_iitb.csv'}")
    if not args.tmy_only:
        fetch_pvgis_multiyear(IIT_BOMBAY, 2005, 2023, DATA / "pvgis_dni_2005_2023_iitb.csv.gz")
        print(f"wrote {DATA / 'pvgis_dni_2005_2023_iitb.csv.gz'}")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Rebuild the final report numbers from their stated inputs and print the comparison."""
    table = reproduce_final_report()
    OUT.mkdir(exist_ok=True)
    table.to_csv(OUT / "final_report_reproduction.csv", index=False)
    n_ok = int((table.verdict == "reproduces").sum())
    print(table[["group", "quantity", "reported", "recomputed", "verdict"]].to_string(index=False))
    print(
        f"\n{n_ok} of {len(table)} figures reproduce; {int((table.expect == 'gap').sum())} documented gaps."
    )
    print(f"wrote {OUT / 'final_report_reproduction.csv'}")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Simulate one typical year for a design and print the annual results."""
    res = simulate(_tmy(), IIT_BOMBAY, load_config(), args.dishes, args.storage)
    a = res.annual
    print(f"{args.dishes} dishes, {args.storage:.0f} MJ store, typical year at IIT Bombay")
    print(f"  solar share of steam demand : {a['solar_fraction']:.1%}")
    print(f"  useful collector heat       : {a['useful_collector_mwh']:.0f} MWh")
    print(f"  LPG cylinders displaced     : {a['cylinders_displaced']:.0f} per year")
    print(f"  CO2 avoided                 : {a['co2_avoided_t']:.1f} t per year")
    if args.hourly:
        OUT.mkdir(exist_ok=True)
        res.hourly.to_csv(OUT / "hourly.csv")
        print(f"wrote {OUT / 'hourly.csv'}")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    """Sweep dishes and store size at the base inputs and print the best designs."""
    cfg, dists = load_config(), load_distributions()
    ev = Evaluator({"TMY": _tmy()[["dni", "temp_air"]]}, IIT_BOMBAY, cfg, dists)
    dishes = list(range(args.min_dishes, args.max_dishes + 1, args.step))
    storages = [0, 250, 500, 750, 1000, 1500, 2000, 3000, 4000]
    sw = sizing_sweep(ev, modes(dists), dishes, storages)
    OUT.mkdir(exist_ok=True)
    sw.to_csv(OUT / "sweep.csv", index=False)
    best = sw.loc[sw.npv_inr.idxmax()]
    print(
        f"best NPV: {int(best.n_dishes)} dishes, {best.storage_mj:.0f} MJ store -> "
        f"NPV {best.npv_inr / 1e5:.1f} lakh INR, solar share {best.solar_fraction:.0%}, "
        f"{best.lcoh_inr_per_mj:.2f} INR/MJ (LPG {best.lpg_inr_per_mj:.2f})"
    )
    front = pareto_front(sw)
    print(f"{len(front)} designs on the cost/solar-share Pareto front; wrote {OUT / 'sweep.csv'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="en630", description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch-data", help="download PVGIS weather data (network needed)")
    p.add_argument("--tmy-only", action="store_true", help="skip the 19-year series")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("reproduce", help="rebuild the final report results from their stated inputs")
    p.set_defaults(func=cmd_reproduce)

    p = sub.add_parser("simulate", help="hourly simulation of one design over the typical year")
    p.add_argument("--dishes", type=int, default=14)
    p.add_argument("--storage", type=float, default=0.0, help="store capacity in MJ")
    p.add_argument("--hourly", action="store_true", help="also write the hourly table")
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("sweep", help="sizing sweep over dishes and storage")
    p.add_argument("--min-dishes", type=int, default=4)
    p.add_argument("--max-dishes", type=int, default=40)
    p.add_argument("--step", type=int, default=2)
    p.set_defaults(func=cmd_sweep)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
