"""Psychrometric utilities per `aivu_greybox` §11.3.

Implements the four closed-form relations consumed by §4 (Fan-Heat residual)
and §5 (two-channel observation likelihood):

    1. Moist-air specific enthalpy h(T, W)  [ASHRAE Fundamentals Ch. 1]
    2. Saturation vapor pressure P_ws(T)   [Hyland-Wexler 1983, liquid regime]
    3. Partial pressure from RH            [P_w = (RH/100) * P_ws]
    4. Humidity ratio from partial pressures [W = 0.62198 * P_w / (P_atm - P_w)]

Coordinate conventions per §11.3.1:
    - Temperature: °C internal (NOT °F; conversion happens only at the
      report-emission boundary per §1.3 unit conventions)
    - Humidity ratio W: kg water vapor per kg dry air
    - Atmospheric pressure: Pa; default Phoenix elevation 335 m → 97.3 kPa
    - Enthalpy: kJ/kg dry air

Ice-regime psychrometrics (T < 0 °C) are explicitly out of scope for v0.1
per §11.5; Phoenix-July does not exercise that regime.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Atmospheric pressure
# ---------------------------------------------------------------------------

# Phoenix elevation: 335 m. P_atm computed via barometric formula at standard
# atmosphere: P = P_0 * (1 - L*h/T_0)^(g*M/(R*L)), giving ~97,310 Pa.
# Per §11.3.1, v0.1 treats P_atm as a per-home constant; weather-station
# barometric pull is v0.2.
P_ATM_PHOENIX_PA: float = 97_310.0

# Default for non-Phoenix sites: sea-level standard atmosphere.
P_ATM_SEA_LEVEL_PA: float = 101_325.0

# ---------------------------------------------------------------------------
# Hyland-Wexler 1983 coefficients for liquid water saturation (240-533 K)
# Per ASHRAE Fundamentals 2009 Ch. 1, Eq. 6
# ---------------------------------------------------------------------------

_HW_C1: float = -5_800.2206
_HW_C2: float = 1.3914993
_HW_C3: float = -0.048_640_239
_HW_C4: float = 4.176_476_8e-5
_HW_C5: float = -1.445_209_3e-8
_HW_C6: float = 6.545_967_3  # coefficient on ln(T)


def saturation_vapor_pressure_pa(temperature_c: float) -> float:
    """Saturation vapor pressure over liquid water, Hyland-Wexler 1983.

    Valid range: -33 °C to +260 °C (240-533 K). Outside this range the
    coefficients are extrapolated and the result is unreliable.

    Args:
        temperature_c: Dry-bulb temperature in °C.

    Returns:
        Saturation vapor pressure in Pa.

    Raises:
        ValueError: if temperature_c < -33 (ice regime, out of scope per §11.5)
            or temperature_c > 100 (above the residential range we expect).
    """
    if temperature_c < -33.0:
        raise ValueError(
            f"Temperature {temperature_c} °C below liquid-regime range "
            "(< -33 °C). Ice-regime psychrometrics are out of scope for v0.1 "
            "per §11.5; cohort expansion into northern climates triggers a "
            "v0.2 §11 extension."
        )
    if temperature_c > 100.0:
        raise ValueError(
            f"Temperature {temperature_c} °C above residential range. "
            "Hyland-Wexler is valid to 260 °C but a residential telemetry "
            "stream exceeding 100 °C indicates a sensor fault, not a "
            "computational request."
        )

    t_k = temperature_c + 273.15
    ln_p = (
        _HW_C1 / t_k
        + _HW_C2
        + _HW_C3 * t_k
        + _HW_C4 * t_k * t_k
        + _HW_C5 * t_k * t_k * t_k
        + _HW_C6 * math.log(t_k)
    )
    return math.exp(ln_p)


def partial_vapor_pressure_pa(temperature_c: float, rh_pct: float) -> float:
    """Partial vapor pressure from relative humidity.

    Args:
        temperature_c: Dry-bulb temperature in °C.
        rh_pct: Relative humidity in percent (0-100).

    Returns:
        Partial vapor pressure in Pa.
    """
    if not 0.0 <= rh_pct <= 100.0:
        raise ValueError(
            f"RH {rh_pct}% outside [0, 100]. SHT35 readings above 100% indicate "
            "saturation conditions per §4.2 measurement-validity-near-saturation "
            "discussion; the caller should reject such readings before invoking "
            "psychrometric utilities, not pass them through."
        )
    return (rh_pct / 100.0) * saturation_vapor_pressure_pa(temperature_c)


def humidity_ratio(
    temperature_c: float, rh_pct: float, p_atm_pa: float = P_ATM_PHOENIX_PA
) -> float:
    """Humidity ratio W = 0.62198 * P_w / (P_atm - P_w).

    The constant 0.62198 is the molecular-weight ratio of water vapor to
    dry air per ASHRAE Fundamentals.

    Args:
        temperature_c: Dry-bulb temperature in °C.
        rh_pct: Relative humidity in percent (0-100).
        p_atm_pa: Atmospheric pressure in Pa. Default is the Phoenix per-home
            constant per §11.3.1.

    Returns:
        Humidity ratio in kg water vapor per kg dry air.
    """
    p_w = partial_vapor_pressure_pa(temperature_c, rh_pct)
    if p_w >= p_atm_pa:
        raise ValueError(
            f"Partial vapor pressure {p_w} Pa ≥ atmospheric pressure "
            f"{p_atm_pa} Pa: supersaturation regime, out of scope."
        )
    return 0.62198 * p_w / (p_atm_pa - p_w)


def moist_air_enthalpy_kj_per_kg(
    temperature_c: float, humidity_ratio_kg_per_kg: float
) -> float:
    """Moist-air specific enthalpy per ASHRAE Fundamentals Ch. 1.

        h(T, W) = 1.006 * T + W * (2501 + 1.86 * T)   [kJ/kg dry air]

    Reference state: 0 °C dry air and 0 °C saturated liquid water.

    Args:
        temperature_c: Dry-bulb temperature in °C.
        humidity_ratio_kg_per_kg: Humidity ratio (kg water / kg dry air).

    Returns:
        Specific enthalpy in kJ per kg dry air.
    """
    return 1.006 * temperature_c + humidity_ratio_kg_per_kg * (
        2501.0 + 1.86 * temperature_c
    )


# ---------------------------------------------------------------------------
# Convenience: SHT35-output → enthalpy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PsychrometricState:
    """A single (T, RH) measurement reduced to the derived moist-air state."""

    temperature_c: float
    relative_humidity_pct: float
    humidity_ratio_kg_per_kg: float
    enthalpy_kj_per_kg: float
    p_atm_pa: float


def state_from_sht_reading(
    temperature_c: float,
    rh_pct: float,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> PsychrometricState:
    """Reduce a single SHT35 (T, RH) reading to the derived moist-air state.

    Single entry point for §4's per-terminal enthalpy computation: each of the
    13 SHT35 pods (12 supply terminal + 1 return plenum, per Hardware Spec
    v1.1) emits (T, RH) at 1 Hz; this function produces the W and h derived
    quantities §4.5 consumes.
    """
    w = humidity_ratio(temperature_c, rh_pct, p_atm_pa)
    h = moist_air_enthalpy_kj_per_kg(temperature_c, w)
    return PsychrometricState(
        temperature_c=temperature_c,
        relative_humidity_pct=rh_pct,
        humidity_ratio_kg_per_kg=w,
        enthalpy_kj_per_kg=h,
        p_atm_pa=p_atm_pa,
    )


def fahrenheit_to_celsius(temp_f: float) -> float:
    """Boundary-only unit conversion per §11.3.1 ('SI internal')."""
    return (temp_f - 32.0) * 5.0 / 9.0


def celsius_to_fahrenheit(temp_c: float) -> float:
    """Boundary-only unit conversion per §11.3.1 ('SI internal')."""
    return temp_c * 9.0 / 5.0 + 32.0
