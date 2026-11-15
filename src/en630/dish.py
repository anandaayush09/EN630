"""Scheffler-dish optics and receiver model, written the way the final report states it.

This module reproduces the final report calculation (pages 8 to 12) as pure functions of their
inputs. It deliberately keeps the report's simplifications (one design DNI, one design
hour, a fixed receiver temperature) so that the report's numbers can be rebuilt first.
The hourly model in ``simulate.py`` and the tracker models in ``irradiance.py`` do not
share these simplifications.
"""

from __future__ import annotations

import math

__all__ = [
    "absorbed_power_w",
    "concentration_ratio",
    "cos_incidence",
    "declination_deg",
    "dishes_required",
    "equation_of_time_min",
    "heat_per_dish_j",
    "hour_angle_deg",
    "optical_efficiency",
    "receiver_efficiency",
    "receiver_heat_loss_w",
    "sky_temperature_k",
]


def declination_deg(day_of_year: int) -> float:
    """Solar declination, Cooper's formula (final report equation 2): 23.45 sin(360 (284+n)/365)."""
    return 23.45 * math.sin(math.radians(360.0 * (284 + day_of_year) / 365.0))


def equation_of_time_min(day_of_year: int) -> float:
    """Equation of time in minutes, Spencer-type series (final report equations 3 and 4)."""
    b = math.radians(360.0 * (day_of_year - 1) / 365.0)
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(b)
        - 0.032077 * math.sin(b)
        - 0.014615 * math.cos(2 * b)
        - 0.04089 * math.sin(2 * b)
    )


def hour_angle_deg(
    day_of_year: int, clock_time_h: float, longitude_deg: float, standard_longitude_deg: float
) -> float:
    """Hour angle (final report equations 5 and 6) for a clock time at a site east of the standard meridian.

    Local apparent time = clock time - (standard longitude - longitude)/15 + E/60; the hour
    angle is 15 degrees per hour from solar noon.
    """
    lat_h = (
        clock_time_h
        - (standard_longitude_deg - longitude_deg) / 15.0
        + equation_of_time_min(day_of_year) / 60.0
    )
    return (lat_h - 12.0) * 15.0


def cos_incidence(
    tilt_deg: float, azimuth_deg: float, declination: float, hour_angle: float, latitude_deg: float
) -> float:
    """Cosine of the angle of incidence on a tilted surface (final report equation 7)."""
    beta, gamma, delta, omega, phi = (
        math.radians(x) for x in (tilt_deg, azimuth_deg, declination, hour_angle, latitude_deg)
    )
    return (
        math.sin(beta)
        * math.cos(gamma)
        * (math.cos(delta) * math.cos(omega) * math.sin(phi) - math.sin(delta) * math.cos(phi))
        + math.sin(beta) * math.sin(gamma) * math.cos(delta) * math.sin(omega)
        + math.cos(beta)
        * (math.cos(delta) * math.cos(omega) * math.cos(phi) + math.sin(delta) * math.sin(phi))
    )


def concentration_ratio(reflector_area_m2: float, receiver_area_m2: float) -> float:
    """Geometric concentration ratio: reflector aperture over receiver aperture."""
    return reflector_area_m2 / receiver_area_m2


def optical_efficiency(cos_theta: float, reflectivity: float, absorptivity: float) -> float:
    """Optical efficiency = cos(theta) x mirror reflectivity x receiver absorptivity (final report p.10)."""
    return cos_theta * reflectivity * absorptivity


def sky_temperature_k(ambient_k: float, coefficient: float = 0.0553, offset_k: float = 10.0) -> float:
    """Effective sky temperature as the final report uses it: ``coefficient * Ta**1.5 + offset``.

    The report prints the coefficient as 0.00553 and calls the formula Swinbank's. Only 0.0553
    gives its printed 298 K (the textbook Swinbank relation is 0.0552 Ta**1.5 with no offset),
    so 0.0553 is the default and the difference is documented rather than silently fixed.
    """
    return coefficient * ambient_k**1.5 + offset_k


def receiver_heat_loss_w(
    receiver_area_m2: float,
    convection_coeff_w_m2k: float,
    receiver_k: float,
    ambient_k: float,
    sky_k: float,
    emissivity: float,
    stefan_boltzmann: float = 5.67e-8,
) -> float:
    """Receiver loss = convection + radiation to the sky (final report p.10), in watts."""
    convection = convection_coeff_w_m2k * receiver_area_m2 * (receiver_k - ambient_k)
    radiation = stefan_boltzmann * emissivity * receiver_area_m2 * (receiver_k**4 - sky_k**4)
    return convection + radiation


def absorbed_power_w(dni_w_m2: float, reflector_area_m2: float, optical_eff: float) -> float:
    """Power reaching the receiver: DNI x reflector area x optical efficiency."""
    return dni_w_m2 * reflector_area_m2 * optical_eff


def receiver_efficiency(absorbed_w: float, loss_w: float) -> float:
    """Share of the absorbed power that is not lost again at the receiver."""
    return (absorbed_w - loss_w) / absorbed_w


def heat_per_dish_j(
    dni_w_m2: float,
    reflector_area_m2: float,
    seconds_per_hour: float,
    design_hours: float,
    receiver_eff: float,
    optical_eff: float,
) -> float:
    """Heat delivered by one dish per day for ``design_hours`` of design-DNI operation (final report p.12)."""
    return dni_w_m2 * reflector_area_m2 * seconds_per_hour * design_hours * receiver_eff * optical_eff


def dishes_required(heat_needed_j: float, heat_per_dish: float) -> float:
    """Unrounded number of dishes; the report rounds to the nearest integer."""
    return heat_needed_j / heat_per_dish
