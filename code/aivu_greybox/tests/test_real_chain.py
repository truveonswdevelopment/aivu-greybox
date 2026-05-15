"""Smoke tests for `aivu_greybox.real_chain` — G7 adapter.

These tests verify the adapter module imports cleanly and basic
construction works. They do NOT run the integrator end-to-end; that's
G8's job and requires both `aivu_physics` and `aivu_dynamic` to be
installed in the test environment with a valid Phoenix EPW file
available.

Tests that require the real chain use `pytest.importorskip` to skip
gracefully when dependencies are absent. The greybox CI environment
will eventually install both packages; until then, these smoke tests
verify what they can verify without the dependencies, and the heavier
end-to-end test is gated on dependency availability.
"""

from __future__ import annotations

import pytest

# Skip the entire module if aivu_physics or aivu_dynamic are not available.
# This is the right behavior for greybox's current CI, which does not yet
# install the forward-chain dependencies.
aivu_physics = pytest.importorskip(
    "aivu_physics",
    reason="G7 adapter requires aivu_physics to be installed",
)
aivu_dynamic = pytest.importorskip(
    "aivu_dynamic",
    reason="G7 adapter requires aivu_dynamic to be installed",
)

# If we got here, both packages are available — run the smoke tests.

import numpy as np

from aivu_greybox.defaults import (
    CANONICAL_PARAMETER_NAMES,
    NUM_CANONICAL_PARAMETERS,
)
from aivu_greybox.forward_chain import (
    ForwardChain,
    HomeStaticContext,
    HVACExcitation,
    WeatherSeries,
)
from aivu_greybox.real_chain import (
    RealForwardChain,
    _envelope_overrides,
    _make_hvac_provider,
)


class TestAdapterConstruction:
    def test_real_forward_chain_can_be_constructed(self):
        """The adapter dataclass is instantiable with a Phase 1 Site and
        SimConfig. No simulation is run; this just verifies the type
        construction works."""
        from aivu_physics import envelope as E
        from aivu_physics import loads as L
        from aivu_physics.geometry.site import Site

        # A minimal Phoenix-like Site. The EPW file is referenced by name
        # only; this test doesn't read it.
        site = Site(
            name="phoenix_smoke",
            state="AZ",
            climate_zone="2B",
            latitude_deg=33.4,
            longitude_deg=-112.0,
            elevation_m=337.0,
            utc_offset_hours=-7.0,
            epw_filename="USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780_AMY_2024.epw",
            epw_station_name="Phoenix Sky Harbor Intl AP",
            T_ground_F=70.0,
            design_cooling_DB_F=109.0,
            design_cooling_MCWB_F=70.0,
        )
        cfg = L.SimConfig(
            variant=E.EnvelopeVariant.UNVENTED_FOAM,
            orientation_offset_deg=0.0,
            T_in_F=75.0,
            RH_in=0.50,
            T_ground_F=70.0,
        )
        adapter = RealForwardChain(site=site, sim_config=cfg)
        # Type checks
        assert hasattr(adapter, "run") and callable(adapter.run)
        assert adapter.site is site
        assert adapter.sim_config is cfg

    def test_adapter_rejects_wrong_theta_shape(self):
        """The adapter must enforce the seven-parameter contract at the
        boundary, matching how StubForwardChain enforces shape."""
        from aivu_physics import envelope as E
        from aivu_physics import loads as L
        from aivu_physics.geometry.site import Site

        site = Site(
            name="phoenix_smoke",
            state="AZ",
            climate_zone="2B",
            latitude_deg=33.4,
            longitude_deg=-112.0,
            elevation_m=337.0,
            utc_offset_hours=-7.0,
            epw_filename="USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780_AMY_2024.epw",
            epw_station_name="Phoenix Sky Harbor Intl AP",
            T_ground_F=70.0,
            design_cooling_DB_F=109.0,
            design_cooling_MCWB_F=70.0,
        )
        cfg = L.SimConfig(
            variant=E.EnvelopeVariant.UNVENTED_FOAM,
            T_in_F=75.0, RH_in=0.50, T_ground_F=70.0,
        )
        adapter = RealForwardChain(site=site, sim_config=cfg)

        # 6-element theta (the pre-amendment shape) should be rejected
        wrong_theta = np.array([1.0, 5.0e6, 1800.0, 100.0, 50.0, 0.75])
        # We don't even need a full HVAC/weather/context to trigger the
        # shape check — it's the first thing run() does.
        with pytest.raises(ValueError, match="theta shape"):
            adapter.run(
                theta=wrong_theta,
                hvac=None,        # type: ignore[arg-type]
                weather=None,     # type: ignore[arg-type]
                context=None,     # type: ignore[arg-type]
            )


class TestEnvelopeOverrides:
    """The context manager must patch the right constants and restore
    them on exit, including in the exception path."""

    def test_patches_and_restores_R_wall(self):
        from aivu_physics import envelope as E

        original = E.R_WALL_WHOLE
        with _envelope_overrides(
            r_opaque=1.5,
            u_fenestration=1.0,
            f_ceiling=1.0,
            c_stack=1.44e-4,
            c_wind=1.74e-4,
            f_slab=0.73,
            variant=E.EnvelopeVariant.UNVENTED_FOAM,
        ):
            assert E.R_WALL_WHOLE == pytest.approx(original / 1.5)
        assert E.R_WALL_WHOLE == original

    def test_restores_on_exception(self):
        """If the wrapped code raises, originals must still be restored.
        This protects against forward-chain failures leaving Phase 1 in
        a perturbed state across the rest of a Laplace fit."""
        from aivu_physics import envelope as E
        from aivu_physics import infiltration as INF

        original_R_wall = E.R_WALL_WHOLE
        original_C_s = INF.C_S_STACK

        with pytest.raises(RuntimeError, match="boom"):
            with _envelope_overrides(
                r_opaque=2.0,
                u_fenestration=1.0,
                f_ceiling=1.0,
                c_stack=5.0e-4,
                c_wind=1.74e-4,
                f_slab=0.73,
                variant=E.EnvelopeVariant.UNVENTED_FOAM,
            ):
                raise RuntimeError("boom")

        assert E.R_WALL_WHOLE == original_R_wall
        assert INF.C_S_STACK == original_C_s

    def test_patches_infiltration_coefficients(self):
        from aivu_physics import envelope as E
        from aivu_physics import infiltration as INF

        with _envelope_overrides(
            r_opaque=1.0,
            u_fenestration=1.0,
            f_ceiling=1.0,
            c_stack=2.0e-4,
            c_wind=3.0e-4,
            f_slab=0.73,
            variant=E.EnvelopeVariant.UNVENTED_FOAM,
        ):
            assert INF.C_S_STACK == 2.0e-4
            assert INF.C_W_WIND == 3.0e-4

    def test_ceiling_gets_composed_R_opaque_and_f_ceiling(self):
        """The ceiling element is multiplied by BOTH r_opaque and f_ceiling
        because the two effects are physically independent: r_opaque is
        nameplate envelope degradation, f_ceiling is bypass-path coupling."""
        from aivu_physics import envelope as E
        from dataclasses import replace

        variant = E.EnvelopeVariant.UNVENTED_FOAM
        original_R_ceil = E.VARIANT_PROPERTIES[variant].R_ceiling

        with _envelope_overrides(
            r_opaque=2.0,
            u_fenestration=1.0,
            f_ceiling=3.0,
            c_stack=1.44e-4,
            c_wind=1.74e-4,
            f_slab=0.73,
            variant=variant,
        ):
            new_R_ceil = E.VARIANT_PROPERTIES[variant].R_ceiling
            # R_new = R_original / (r_opaque × f_ceiling) = R_original / 6
            assert new_R_ceil == pytest.approx(original_R_ceil / 6.0)

        # Restored
        assert E.VARIANT_PROPERTIES[variant].R_ceiling == original_R_ceil


class TestHVACProviderUnits:
    """The HVAC provider must correctly translate greybox SI to dynamic
    imperial at the boundary, including the sign convention difference."""

    def test_w_positive_input_becomes_negative_btuh_output(self):
        """Greybox q_sens_w > 0 means HVAC adds heat. Dynamic Q_HVAC > 0
        means HVAC removes heat. So a positive greybox W should become
        a negative dynamic BTU/hr."""
        monotonic_ns = np.arange(100, dtype=np.int64) * int(1e9)
        q_sens_w = np.full(100, 400.0)  # +400 W = HVAC adding heat
        m_lat = np.zeros(100)

        hvac = HVACExcitation(
            monotonic_ns=monotonic_ns,
            q_sens_w=q_sens_w,
            m_lat_kg_per_s=m_lat,
        )
        provider = _make_hvac_provider(hvac, t0_ns=int(monotonic_ns[0]))

        # Call the underlying Q_func directly. The aivu_dynamic
        # HVACScheduleProvider.get_command signature has many args; we
        # only need t_hours for the lookup.
        result = provider.Q_func(0.005, None, None, None, None, 0, None)
        # +400 W × 3.412 BTU/(W·hr) = +1365 BTU/hr, then sign flip = -1365
        assert result == pytest.approx(-400.0 * 3.412141633)

    def test_zero_input_zero_output(self):
        monotonic_ns = np.arange(10, dtype=np.int64) * int(1e9)
        hvac = HVACExcitation(
            monotonic_ns=monotonic_ns,
            q_sens_w=np.zeros(10),
            m_lat_kg_per_s=np.zeros(10),
        )
        provider = _make_hvac_provider(hvac, t0_ns=int(monotonic_ns[0]))
        assert provider.Q_func(0.001, None, None, None, None, 0, None) == 0.0
        assert provider.M_func(0.001, None, None, None, None, 0, None) == 0.0
