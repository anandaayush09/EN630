"""Techno-economics as done in the final report (pages 14 and 15): payback, NPV, benefit-cost ratio, IRR.

Money is in rupees. The conventions below are the report's: end-of-year cash flows, a constant
annual fuel saving and O&M, salvage received at the end of the dish life.
"""

from __future__ import annotations

__all__ = [
    "annuity_factor",
    "benefit_cost_ratio",
    "escalating_annuity_factor",
    "irr",
    "irr_of_flows",
    "lcoh_inr_per_mj",
    "npv_at_rate",
    "npv_of_flows",
    "npv_project",
    "present_value_lump",
    "roi_percent",
    "simple_payback_years",
]


def annuity_factor(rate: float, years: int) -> float:
    """Present value of 1 rupee a year for ``years`` years at discount ``rate``."""
    return years if rate == 0 else (1.0 - (1.0 + rate) ** -years) / rate


def present_value_lump(amount: float, rate: float, years: int) -> float:
    """Present value of a single payment at the end of ``years``."""
    return amount / (1.0 + rate) ** years


def simple_payback_years(capital: float, annual_saving: float) -> float:
    """Capital over annual saving (the final report 'SPP'); ignores O&M and discounting by design."""
    return capital / annual_saving


def roi_percent(payback_years: float) -> float:
    """The final report 'ROI' = (1 / simple payback) x 100."""
    return 100.0 / payback_years


def npv_project(
    capital: float, annual_saving: float, om: float, salvage: float, rate: float, years: int
) -> dict[str, float]:
    """NPV of the project and its parts: saving + salvage - O&M - capital."""
    af = annuity_factor(rate, years)
    pv_saving = annual_saving * af
    pv_om = om * af
    pv_salvage = present_value_lump(salvage, rate, years)
    return {
        "pv_saving": pv_saving,
        "pv_om": pv_om,
        "pv_salvage": pv_salvage,
        "npv": pv_saving + pv_salvage - pv_om - capital,
    }


def benefit_cost_ratio(parts: dict[str, float], capital: float) -> float:
    """The final report definition: (PV saving + PV salvage) / (capital + PV O&M)."""
    return (parts["pv_saving"] + parts["pv_salvage"]) / (capital + parts["pv_om"])


def npv_at_rate(capital: float, net_annual: float, salvage: float, rate: float, years: int) -> float:
    """NPV of -capital, then ``net_annual`` each year, with salvage added in the last year."""
    total = -capital
    for t in range(1, years + 1):
        total += (net_annual + (salvage if t == years else 0.0)) / (1.0 + rate) ** t
    return total


def irr(capital: float, net_annual: float, salvage: float, years: int, tol: float = 1e-10) -> float:
    """Internal rate of return by bisection: the rate at which the NPV is zero.

    Bisection is used instead of a library solver because the cash flows have one sign change
    (outflow then inflows), so the NPV falls monotonically with the rate and a root is unique.
    """
    if net_annual <= 0 and salvage <= 0:
        raise ValueError("no positive cash flow: the project has no IRR")
    lo, hi = -0.99, 10.0  # a negative IRR is legitimate for a project that does not pay back
    if npv_at_rate(capital, net_annual, salvage, lo, years) < 0:
        raise ValueError("NPV is negative even at a -99 % rate: no IRR in range")
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if npv_at_rate(capital, net_annual, salvage, mid, years) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def escalating_annuity_factor(rate: float, years: int, growth: float) -> float:
    """Present value of a payment of 1 in year one that grows by ``growth`` a year afterwards.

    ``sum_{t=1..N} (1 + g)^(t-1) / (1 + r)^t``. With ``growth = 0`` it equals :func:`annuity_factor`.
    Used for fuel savings when the LPG price is assumed to rise.
    """
    q = (1.0 + growth) / (1.0 + rate)
    if abs(q - 1.0) < 1e-12:
        return years / (1.0 + rate)
    return (1.0 - q**years) / ((1.0 + rate) - (1.0 + growth))


def npv_of_flows(flows: list[float], rate: float) -> float:
    """NPV of a list of end-of-year cash flows, index 0 being today."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(flows))


def irr_of_flows(flows: list[float], tol: float = 1e-10) -> float:
    """IRR of general cash flows by bisection on (-99 %, 1000 %); raises if there is no sign change."""
    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv_of_flows(flows, lo), npv_of_flows(flows, hi)
    if f_lo * f_hi > 0:
        raise ValueError("cash flows have no IRR in the search range")
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if (npv_of_flows(flows, mid) > 0) == (f_lo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def lcoh_inr_per_mj(
    capital: float, annual_om: float, salvage: float, rate: float, years: int, annual_heat_mj: float
) -> float:
    """Levelised cost of heat: discounted costs over discounted heat, rupees per MJ.

    ``(capital + PV(O&M) - PV(salvage)) / (annuity factor x annual heat)``. Comparable with the
    cost of the same heat from LPG, ``price / (cylinder MJ x stove efficiency)``.
    """
    if annual_heat_mj <= 0:
        return float("inf")
    af = annuity_factor(rate, years)
    return (capital + annual_om * af - present_value_lump(salvage, rate, years)) / (af * annual_heat_mj)
