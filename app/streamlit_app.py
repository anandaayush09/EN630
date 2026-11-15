"""What-if explorer for the dish field: change the design and the inputs, see the result at once.

Run with:  uv run --group app streamlit run app/streamlit_app.py

Everything shown comes from the same functions as the notebooks (``en630.uncertainty.Evaluator``
and ``en630.simulate``); the app adds no model of its own.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from en630.config import load_config
from en630.plotting import INK, SERIES, SURFACE, apply_theme
from en630.simulate import simulate
from en630.uncertainty import Evaluator, load_distributions, modes
from en630.weather import IIT_BOMBAY, clean_dni, read_multiyear_csv, read_tmy_csv, to_local

warnings.filterwarnings("ignore")
DATA = Path(__file__).resolve().parents[1] / "data"
LAKH = 1e5

st.set_page_config(page_title="Scheffler dish cooking: what-if", layout="wide")
apply_theme()


@st.cache_resource(show_spinner="Loading weather data...")
def load_everything():
    cfg, dists = load_config(), load_distributions()
    tmy = read_tmy_csv(DATA / "pvgis_tmy_iitb.csv")
    my = read_multiyear_csv(DATA / "pvgis_dni_2005_2023_iitb.csv.gz")
    years = {"Typical year": tmy[["dni", "temp_air"]], **{y: g for y, g in my.groupby(my.index.year)}}
    return cfg, dists, years


cfg, dists, years = load_everything()
base = modes(dists)

st.title("Solar steam for hostel cooking: what-if explorer")
st.caption(
    "IIT Bombay, PVGIS weather, 14 dishes is the final report design. Store cost is a placeholder estimate; "
    "meal hours and store efficiencies are assumptions (see docs/report.md)."
)

with st.sidebar:
    st.header("Design")
    n_dishes = st.slider("Number of dishes", 0, 40, 14)
    storage = st.slider("Steam store (MJ)", 0, 4000, 1000, step=250)
    st.header("Weather")
    choice = st.selectbox("Weather year", list(years), index=0)
    st.header("Costs and prices")
    price = st.slider("LPG price per cylinder (INR)", 800, 2200, int(base["lpg_price_inr"]), step=25)
    esc = st.slider("LPG price rise per year (%)", 0.0, 10.0, 0.0, step=0.5) / 100
    dish_cost = st.slider("Dish cost per m² (INR)", 15000, 35000, int(base["dish_cost_per_m2_inr"]), step=500)
    retro = st.slider("Kitchen retrofit (share of dish cost)", 0.0, 0.4, base["retrofit_fraction"], step=0.05)
    store_cost = st.slider(
        "Store cost per MJ (INR, placeholder)", 200, 3000, int(base["storage_cost_per_mj_inr"]), step=100
    )
    disc = st.slider("Discount rate (%)", 5.0, 15.0, base["discount_rate"] * 100, step=0.5) / 100


@st.cache_resource(show_spinner="Preparing the model...")
def make_evaluator(label):
    return Evaluator({label: years[label]}, IIT_BOMBAY, cfg, dists)


ev = make_evaluator(choice)
p = {
    **base,
    "lpg_price_inr": float(price),
    "lpg_escalation": esc,
    "dish_cost_per_m2_inr": float(dish_cost),
    "retrofit_fraction": retro,
    "storage_cost_per_mj_inr": float(store_cost),
    "discount_rate": disc,
}
r = ev.evaluate(p, n_dishes, float(storage))
irr = ev.irr(p, n_dishes, float(storage)) if n_dishes else float("nan")

c = st.columns(5)
c[0].metric("Solar share of steam demand", f"{r['solar_fraction']:.0%}")
c[1].metric("LPG cylinders displaced / year", f"{r['cylinders_displaced']:,.0f}")
c[2].metric("CO₂ avoided / year", f"{r['co2_avoided_t']:.1f} t")
c[3].metric("Capital cost", f"{r['capex_inr'] / LAKH:.1f} lakh")
c[4].metric("NPV (15 years)", f"{r['npv_inr'] / LAKH:.1f} lakh")
c = st.columns(5)
c[0].metric(
    "Simple payback", f"{r['simple_payback_years']:.1f} yr" if r["simple_payback_years"] < 100 else "never"
)
c[1].metric("IRR", f"{irr:.1%}" if irr == irr else "n/a")
c[2].metric("Solar heat cost", f"{r['lcoh_inr_per_mj']:.2f} INR/MJ" if r["lcoh_inr_per_mj"] < 1e3 else "n/a")
c[3].metric("LPG heat cost", f"{r['lpg_inr_per_mj']:.2f} INR/MJ")
c[4].metric(
    "Benefit-cost ratio", f"{r['benefit_cost']:.2f}" if r["benefit_cost"] == r["benefit_cost"] else "n/a"
)

# ------------------------------------------------------------------ monthly picture
wx = years[choice].copy()
wx["dni"] = clean_dni(wx, IIT_BOMBAY, "centre")
res = simulate(
    wx, IIT_BOMBAY, {**cfg, "storage": {**cfg["storage"], "capacity_mj": float(storage)}}, n_dishes
)
h = (
    to_local(res.hourly, IIT_BOMBAY).groupby("month")[["direct_mj", "from_store_mj", "lpg_backup_mj"]].sum()
    / 3600.0
)

fig, ax = plt.subplots(figsize=(9, 3.6))
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
bottom = pd.Series(0.0, index=h.index)
for col, label, colour in (
    ("direct_mj", "solar, used directly", SERIES[0]),
    ("from_store_mj", "solar, via the store", SERIES[2]),
    ("lpg_backup_mj", "LPG backup", SERIES[1]),
):
    ax.bar(
        range(12),
        h[col].to_numpy(),
        bottom=bottom.to_numpy(),
        color=colour,
        label=label,
        width=0.72,
        edgecolor=SURFACE,
        linewidth=1.2,
    )
    bottom += h[col]
ax.set_xticks(range(12), months)
ax.set_ylabel("steam heat supplied (MWh per month)")
ax.grid(axis="x", visible=False)
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.1))
ax.set_title("Who supplies the steam, month by month", loc="left", color=INK["primary"])
st.pyplot(fig, clear_figure=True)

st.caption(
    "Model: hour-by-hour dispatch (solar, then store, then LPG) with an idealised single-axis tracker; "
    "accuracy limits and open points are listed in LIMITATIONS_AND_FUTURE_SCOPE.md."
)
