"""LPG energy content, equivalent cylinders and carbon dioxide (final report pages 5 and 13)."""

from __future__ import annotations

__all__ = ["co2_per_cylinder_kg", "cylinder_energy_mj", "cylinders_equivalent"]


def cylinder_energy_mj(mass_kg: float, calorific_value_mj_kg: float) -> float:
    """Heat content of one LPG cylinder."""
    return mass_kg * calorific_value_mj_kg


def cylinders_equivalent(heat_mj: float, cylinder_mj: float) -> float:
    """Number of cylinders whose heat equals ``heat_mj`` (before any stove efficiency)."""
    return heat_mj / cylinder_mj


def co2_per_cylinder_kg(
    mass_kg: float, carbon_mass_per_propane_mass: float, co2_per_carbon_mass: float
) -> float:
    """CO2 released by burning a cylinder of propane: carbon mass x 44/12 (complete combustion).

    Treating the cylinder as pure propane (C3H8) follows the report; commercial LPG also
    contains butane, so this slightly understates the true factor.
    """
    return mass_kg * carbon_mass_per_propane_mass * co2_per_carbon_mass
