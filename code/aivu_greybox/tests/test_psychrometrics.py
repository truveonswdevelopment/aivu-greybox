"""Tests for `aivu_greybox.psychrometrics` against ASHRAE Fundamentals
reference values.

Reference values are drawn from ASHRAE Handbook of Fundamentals 2009 Ch. 1
and standard psychrometric calculators (verified against multiple
independent implementations). Tolerances are tight where the closed-form
relations are exact and looser where they involve the Hyland-Wexler series
truncation.
"""

from __future__ import annotations

import math
import pytest

from aivu_greybox.psychrometrics import (
    P_ATM_PHOENIX_PA,
    P_ATM_SEA_LEVEL_PA,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    humidity_ratio,
    moist_air_enthalpy_kj_per_kg,
    partial_vapor_pressure_pa,
    saturation_vapor_pressure_pa,
    state_from_sht_reading,
)


# ---------------------------------------------------------------------------
# Saturation vapor pressure — Hyland-Wexler 1983
# ---------------------------------------------------------------------------


class TestSaturationVaporPressure:
    def test_at_0_celsius(self):
        # 0 °C: P_ws ≈ 611.2 Pa (ASHRAE Handbook reference)
        assert saturation_vapor_pressure_pa(0.0) == pytest.approx(611.2, rel=1e-3)

    def test_at_25_celsius(self):
        # 25 °C: P_ws ≈ 3169 Pa
        assert saturation_vapor_pressure_pa(25.0) == pytest.approx(3169.0, rel=1e-3)

    def test_at_40_celsius(self):
        # 40 °C: P_ws ≈ 7384 Pa
        assert saturation_vapor_pressure_pa(40.0) == pytest.approx(7384.0, rel=1e-3)

    def test_monotonic_increasing(self):
        temps = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
        pws = [saturation_vapor_pressure_pa(t) for t in temps]
        for a, b in zip(pws, pws[1:]):
            assert b > a, "P_ws must be monotonically increasing with T"

    def test_rejects_ice_regime(self):
        with pytest.raises(ValueError, match="Ice-regime"):
            saturation_vapor_pressure_pa(-40.0)

    def test_rejects_unphysical_high(self):
        with pytest.raises(ValueError, match="residential range"):
            saturation_vapor_pressure_pa(150.0)


# ---------------------------------------------------------------------------
# Partial vapor pressure
# ---------------------------------------------------------------------------


class TestPartialVaporPressure:
    def test_at_saturation(self):
        # RH = 100% → P_w = P_ws
        t = 25.0
        assert partial_vapor_pressure_pa(t, 100.0) == saturation_vapor_pressure_pa(t)

    def test_at_zero_rh(self):
        assert partial_vapor_pressure_pa(25.0, 0.0) == 0.0

    def test_at_50_rh(self):
        # RH = 50% → P_w = 0.5 * P_ws
        t = 25.0
        assert partial_vapor_pressure_pa(t, 50.0) == pytest.approx(
            0.5 * saturation_vapor_pressure_pa(t), rel=1e-12
        )

    def test_rejects_out_of_range_rh(self):
        with pytest.raises(ValueError):
            partial_vapor_pressure_pa(25.0, -1.0)
        with pytest.raises(ValueError):
            partial_vapor_pressure_pa(25.0, 110.0)


# ---------------------------------------------------------------------------
# Humidity ratio
# ---------------------------------------------------------------------------


class TestHumidityRatio:
    def test_at_zero_rh(self):
        # Bone dry → W = 0
        assert humidity_ratio(25.0, 0.0) == 0.0

    def test_at_25c_50rh_sea_level(self):
        # 25 °C, 50% RH, sea level → W ≈ 0.00988 kg/kg
        # (ASHRAE psychrometric chart reference)
        w = humidity_ratio(25.0, 50.0, P_ATM_SEA_LEVEL_PA)
        assert w == pytest.approx(0.00988, rel=5e-3)

    def test_at_25c_50rh_phoenix(self):
        # Phoenix is lower pressure → W is slightly higher at same T/RH
        w_phoenix = humidity_ratio(25.0, 50.0, P_ATM_PHOENIX_PA)
        w_sea = humidity_ratio(25.0, 50.0, P_ATM_SEA_LEVEL_PA)
        assert w_phoenix > w_sea
        # The ratio should match (P_atm - P_w)_phoenix / (P_atm - P_w)_sea closely
        pw = partial_vapor_pressure_pa(25.0, 50.0)
        expected_ratio = (P_ATM_SEA_LEVEL_PA - pw) / (P_ATM_PHOENIX_PA - pw)
        assert w_phoenix / w_sea == pytest.approx(expected_ratio, rel=1e-10)

    def test_phoenix_july_typical(self):
        # Phoenix July afternoon: 40 °C, 15% RH
        # Expected W ≈ 0.0073 kg/kg (drier than 25C/50RH despite higher T,
        # because the low RH dominates)
        w = humidity_ratio(40.0, 15.0, P_ATM_PHOENIX_PA)
        assert 0.006 < w < 0.009

    def test_supersaturation_rejected(self):
        # Force P_w > P_atm by using an absurdly low P_atm
        with pytest.raises(ValueError, match="supersaturation"):
            humidity_ratio(50.0, 100.0, p_atm_pa=1000.0)


# ---------------------------------------------------------------------------
# Moist-air enthalpy — ASHRAE Fundamentals Ch. 1
# ---------------------------------------------------------------------------


class TestMoistAirEnthalpy:
    def test_dry_air_at_zero(self):
        # h(0 °C, W=0) = 0 by ASHRAE reference state
        assert moist_air_enthalpy_kj_per_kg(0.0, 0.0) == 0.0

    def test_dry_air_at_25c(self):
        # h(25 °C, W=0) = 1.006 * 25 = 25.15 kJ/kg
        assert moist_air_enthalpy_kj_per_kg(25.0, 0.0) == pytest.approx(25.15, rel=1e-12)

    def test_25c_with_humidity(self):
        # h(25, 0.01) = 1.006*25 + 0.01*(2501 + 1.86*25)
        # = 25.15 + 0.01*2547.5 = 25.15 + 25.475 = 50.625 kJ/kg
        h = moist_air_enthalpy_kj_per_kg(25.0, 0.01)
        assert h == pytest.approx(50.625, rel=1e-12)

    def test_phoenix_july_supply_air(self):
        # Typical Phoenix July supply air after cooling: 13 °C, W ≈ 0.0085
        # Computed: 1.006*13 + 0.0085*(2501 + 1.86*13) = 13.078 + 21.464 = 34.54 kJ/kg
        h = moist_air_enthalpy_kj_per_kg(13.0, 0.0085)
        assert h == pytest.approx(34.54, rel=1e-3)


# ---------------------------------------------------------------------------
# PsychrometricState convenience
# ---------------------------------------------------------------------------


class TestStateFromSHTReading:
    def test_consistency(self):
        # state_from_sht_reading should produce values consistent with the
        # individual functions
        t, rh = 24.0, 45.0
        state = state_from_sht_reading(t, rh)
        w_direct = humidity_ratio(t, rh)
        h_direct = moist_air_enthalpy_kj_per_kg(t, w_direct)
        assert state.humidity_ratio_kg_per_kg == pytest.approx(w_direct, rel=1e-12)
        assert state.enthalpy_kj_per_kg == pytest.approx(h_direct, rel=1e-12)
        assert state.temperature_c == t
        assert state.relative_humidity_pct == rh
        assert state.p_atm_pa == P_ATM_PHOENIX_PA


# ---------------------------------------------------------------------------
# Boundary unit conversions
# ---------------------------------------------------------------------------


class TestUnitConversions:
    def test_roundtrip_celsius_fahrenheit(self):
        for t in [-10.0, 0.0, 13.0, 25.0, 32.5, 100.0]:
            assert celsius_to_fahrenheit(fahrenheit_to_celsius(t * 1.0)) == pytest.approx(
                t, rel=1e-12
            )

    def test_known_conversions(self):
        assert fahrenheit_to_celsius(32.0) == 0.0
        assert fahrenheit_to_celsius(212.0) == 100.0
        assert celsius_to_fahrenheit(0.0) == 32.0
        assert celsius_to_fahrenheit(100.0) == 212.0
