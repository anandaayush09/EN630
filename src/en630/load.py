"""Daily cooking heat demand of the hostel mess, as built up in the final report (pages 11 and 12, Table 4).

The report prices each food item separately, adds them (Table 4), applies a safety factor and
divides by the efficiency of the cooking pots to get the steam heat the solar field must supply.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "demand_table",
    "design_steam_heat_mj",
    "hourly_steam_profile",
    "meal_heat_mj",
    "milk_batch_mj",
    "rice_pot_mj",
    "sensible_heat_mj",
]


def sensible_heat_mj(mass_kg: float, cp_kj_kgk: float, delta_t_k: float) -> float:
    """Heat to warm a mass by ``delta_t_k``, in MJ."""
    return mass_kg * cp_kj_kgk * delta_t_k / 1000.0


def rice_pot_mj(rice: dict[str, Any], ambient_c: float) -> float:
    """Heat for one rice pot: warm the water and rice to the cooking temperature, plus the
    chemical (gelatinisation) energy of the rice, ``Mf Kf`` (final report p.11)."""
    d_t = rice["cook_temperature_c"] - ambient_c
    water = rice["water_kg"] * rice["cp_water_kj_kgk"] * d_t
    solid = rice["rice_kg"] * rice["cp_rice_kj_kgk"] * d_t
    reaction = rice["rice_kg"] * rice["reaction_kj_per_kg_rice"]
    return (water + solid + reaction) / 1000.0


def milk_batch_mj(milk: dict[str, Any], ambient_c: float) -> float:
    """Heat to bring one milk batch to its final temperature."""
    mass = milk["volume_l"] * milk["density_kg_l"]
    return sensible_heat_mj(mass, milk["cp_kj_kgk"], milk["final_temperature_c"] - ambient_c)


def demand_table(load: dict[str, Any], cylinder_mj: float, use_reported_pot: bool = True) -> dict[str, float]:
    """Table 4 of the final report as a flat dictionary, in MJ.

    ``use_reported_pot`` takes the printed 17.97 MJ per rice pot (which the report then
    multiplies by 7 and 5). The pot energy recomputed from the stated inputs is 17.95 MJ, 0.1 %
    lower, because the report does not state the specific heat of water it used.
    """
    ambient = load["ambient_c"]
    pot = load["rice_pot"]["reported_pot_mj"] if use_reported_pot else rice_pot_mj(load["rice_pot"], ambient)
    milk_batch = milk_batch_mj(load["milk"], ambient)

    hw = load["hot_water"]
    hot_water_day = sensible_heat_mj(hw["mass_kg"], hw["cp_kj_kgk"], hw["final_temperature_c"] - ambient)

    cd = load["curry_and_dal"]
    curry_total = cylinder_mj * cd["cylinders_per_day"] * cd["stove_efficiency"]

    rows = {
        "rice_lunch": pot * load["rice_pot"]["pots_lunch"],
        "rice_dinner": pot * load["rice_pot"]["pots_dinner"],
        "milk_morning_and_dinner": milk_batch * load["milk"]["batches"],
        "milk_snacks": load["milk"]["snack_milk_mj"],
        "hot_water_all_meals": hot_water_day,
        "curry_and_dal": curry_total,
    }
    rows["total"] = sum(rows.values())
    return rows


def design_steam_heat_mj(day_total_mj: float, safety_factor: float, pot_efficiency: float) -> float:
    """Steam heat to be generated: day total x safety factor / cooking-pot efficiency."""
    return day_total_mj * safety_factor / pot_efficiency


def meal_heat_mj(load: dict[str, Any], cylinder_mj: float) -> dict[str, float]:
    """Cooking heat of each meal in MJ, regrouping Table 4 by meal instead of by food.

    Morning: milk and hot water. Lunch: rice, curry and dal, hot water. Snacks: milk and hot water.
    Dinner: milk, rice, curry and dal, hot water. The four meals add up to the 939.86 MJ day total.
    """
    t = demand_table(load, cylinder_mj)
    milk_batch = t["milk_morning_and_dinner"] / load["milk"]["batches"]
    water = t["hot_water_all_meals"] / load["hot_water"]["meals"]
    curry = t["curry_and_dal"] / load["curry_and_dal"]["meals"]
    pot = load["rice_pot"]
    rice_pot = t["rice_lunch"] / pot["pots_lunch"]
    return {
        "morning": milk_batch + water,
        "lunch": rice_pot * pot["pots_lunch"] + curry + water,
        "snacks": t["milk_snacks"] + water,
        "dinner": milk_batch + rice_pot * pot["pots_dinner"] + curry + water,
    }


def hourly_steam_profile(
    meals_mj: dict[str, float],
    schedule: dict[str, list[int]],
    safety_factor: float,
    pot_efficiency: float,
) -> list[float]:
    """Steam heat drawn in each hour of the day (24 values, MJ), starting at midnight.

    Each meal's cooking heat is scaled to steam heat (safety factor over pot efficiency, as in
    the final report) and spread evenly over the hours listed for it in ``schedule``. The schedule is an
    assumption: the final report gives each meal's energy but not the hours it is cooked.
    """
    profile = [0.0] * 24
    for meal, heat in meals_mj.items():
        hours = schedule[meal]
        for h in hours:
            profile[h] += heat * safety_factor / pot_efficiency / len(hours)
    return profile
