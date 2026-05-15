"""Forward-chain interface — what aivu_greybox needs from aivu_physics
+ aivu_dynamic.

This module defines a Protocol that the real `aivu_physics` Phase 1 v4.0 +
`aivu_dynamic` v0.2 packages must satisfy. The signatures match the specs:

  - aivu_dynamic.dynamic.run(theta, u_meas, w_meas) → trajectory per
    `aivu_dynamic` v0.2 §6 (state equations) and §7 (integration).
  - Theta = (R_opaque, U_fenestration, C_house, C_stack, C_wind, C_w,
    ceiling_coupling_factor) per `aivu_greybox` §11.2 amendment 2026-05-15.

Per `aivu_greybox` v0.1 §5.3, the forward chain is consumed at evaluation
time as `(T_main^pred(t), W_main^pred(t), T_attic^pred(t))` over the
48-hour window for each candidate θ. The greybox code does not own the
forward chain; it owns the interface and calls into the chain.

In v0.1 the live implementations of `aivu_physics` Phase 1 v4.0 and
`aivu_dynamic` v0.2 are not yet shipped to this package. The
`StubForwardChain` here provides a numerically-credible analytic stand-in
for testing the greybox machinery against synthetic trajectories while
the real packages stabilize; production use replaces it with a thin
adapter that wraps the real packages' APIs (G7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .defaults import CANONICAL_PARAMETER_NAMES, NUM_CANONICAL_PARAMETERS


@dataclass(frozen=True)
class WeatherSeries:
    """1-Hz outdoor weather time series spanning the fit window.

    Per `aivu_dynamic` v0.2 §8: weather enters the forward chain through
    the standard EPW-derived inputs. Time is monotonic, 1 Hz cadence.
    """

    monotonic_ns: np.ndarray  # shape (N,)
    t_outdoor_c: np.ndarray  # shape (N,), °C
    rh_outdoor_pct: np.ndarray  # shape (N,)
    solar_global_w_per_m2: np.ndarray  # shape (N,)
    wind_speed_m_per_s: np.ndarray  # shape (N,)

    def __post_init__(self):
        n = self.monotonic_ns.shape[0]
        for name in (
            "t_outdoor_c",
            "rh_outdoor_pct",
            "solar_global_w_per_m2",
            "wind_speed_m_per_s",
        ):
            arr = getattr(self, name)
            if arr.shape != (n,):
                raise ValueError(
                    f"WeatherSeries.{name} shape {arr.shape} != ({n},)"
                )


@dataclass(frozen=True)
class HVACExcitation:
    """Measured HVAC sensible and latent excitation, 1-Hz cadence.

    Per §5.3: during fan-on intervals `u_meas` is the sensible-heat
    injection Q̇_sens(t) = η̂_distribution · P_fan(t). During fan-off
    intervals `u_meas ≡ 0`. Latent injection is zero throughout §5.
    """

    monotonic_ns: np.ndarray  # shape (N,)
    q_sens_w: np.ndarray  # shape (N,), W (positive = heat added by HVAC)
    m_lat_kg_per_s: np.ndarray  # shape (N,)


@dataclass(frozen=True)
class HomeStaticContext:
    """Static per-home context that the forward chain needs but `aivu_greybox`
    does not fit.

    For Phase 1 v4.0 these are configuration items like geometry (window
    areas, ceiling area, slab area, orientation), HVAC nameplate, occupancy
    schedule. They are home-specific but not part of the canonical fit set.

    Per §11.2 amendment 2026-05-15, two additional fields are now
    known-from-construction rather than fitted:
      - `f_slab_btuh_per_ft_f`: slab F-factor, BTU/(hr·ft·°F), computed
        from gbXML perimeter + slab edge insulation R + Manual J climate-
        zone F-factor table. Replaces v0.1's `F_slab` fitted parameter.
      - `c_attic_j_per_k`: attic thermal capacitance, J/K. Computed from
        gbXML attic volume + framing + radiant barrier inventory.
        Required by the real-chain adapter's dynamic attic ODE; not
        applicable to `StubForwardChain` (the stub treats attic as a
        third state with its own internal capacitance constant).

    In production, both come from the home's gbXML or the AOT-supplied
    SimConfig. In v0.1 stub, they carry sensible Phoenix-V752 defaults
    so existing test fixtures continue to construct cleanly.
    """

    home_id: str
    floor_area_m2: float  # ~167 m² (~1800 ft²) for V752-class
    ceiling_area_m2: float
    slab_area_m2: float
    window_area_m2: float
    initial_t_main_c: float  # T_main at window start
    initial_w_main_kg_per_kg: float
    initial_t_attic_c: float
    # New in §11.2 amendment 2026-05-15:
    f_slab_btuh_per_ft_f: float = 0.73  # Manual J Phoenix CZ 2B default for
                                         # R-5 slab-edge insulation; per-home
                                         # gbXML supersedes in production.
    c_attic_j_per_k: float = 1.5e5      # Phoenix V752-class default:
                                         # ~7000 ft³ attic air + framing +
                                         # radiant barrier. Per-home gbXML
                                         # supersedes in production.


@dataclass(frozen=True)
class StateTrajectory:
    """The forward chain's output for a given (θ, u_meas, w_meas, context).

    Per §5.3 likelihood: greybox needs T_main^pred, W_main^pred, T_attic^pred
    at the times where observations exist. The forward chain returns the
    trajectory at the same 1-Hz cadence as the input telemetry so the
    likelihood can index by sample.
    """

    monotonic_ns: np.ndarray  # shape (N,), matches input weather/HVAC monotonic
    t_main_c: np.ndarray  # shape (N,)
    w_main_kg_per_kg: np.ndarray  # shape (N,)
    t_attic_c: np.ndarray  # shape (N,)


class ForwardChain(Protocol):
    """The contract aivu_greybox §5/§6 requires from aivu_physics + aivu_dynamic.

    A class satisfying this protocol provides one method: given the seven-
    parameter θ, measured HVAC excitation, measured weather, and the
    home's static context, return the predicted state trajectory.

    Per aivu_dynamic v0.2 §6/§7/§10, the integration uses Forward Euler at
    1-minute sub-steps (default) or RK4, with Phase 1's compute_loads
    evaluated at the dynamic indoor state via the T_in_F / W_in kwargs
    introduced in `aivu_dynamic` v0.2 §10.

    The greybox code calls this many times per fit (~50-200 per restart
    × 4 restarts = up to ~800 calls per Laplace fit). Performance matters;
    accuracy more.
    """

    def run(
        self,
        theta: np.ndarray,
        hvac: HVACExcitation,
        weather: WeatherSeries,
        context: HomeStaticContext,
    ) -> StateTrajectory:
        """Integrate the dynamic envelope forward in time.

        Args:
            theta: Seven-element parameter vector in canonical order
                (R_opaque, U_fenestration, C_house, C_stack, C_wind,
                C_w, ceiling_coupling_factor).
            hvac: Measured 1-Hz HVAC excitation.
            weather: Measured 1-Hz outdoor weather.
            context: Home-specific static configuration.

        Returns:
            StateTrajectory at the same 1-Hz cadence as `hvac` and `weather`.
        """
        ...


# ---------------------------------------------------------------------------
# v0.1 stub forward chain — analytic stand-in for testing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StubForwardChain:
    """Analytic stand-in for the real aivu_physics + aivu_dynamic.

    NOT physically rigorous in detail. The stub implements simplified
    dynamics where every one of the seven canonical parameters appears,
    so closed-loop recovery is a meaningful test of the inverse
    machinery:

      - Envelope conduction with R_opaque dominating the conductance
        and U_fenestration adding a secondary path. This is the stub's
        analog of the Phase 1 envelope decomposition.
      - Operational infiltration via (C_stack, C_wind) — stack-driven
        component scales with |T_out - T_in|, wind-driven with V_wind.
        This is the stub's analog of the Phase 1 amendment that
        replaces cfm50 with the operational decomposition.
      - First-order lumped sensible state with C_house.
      - First-order moisture state with C_w.
      - Two-state attic-main coupling with ceiling_coupling_factor on
        the attic↔main conductance, internal stub attic capacitance.
      - F_slab pulled from HomeStaticContext (no longer fitted per
        §11.2 amendment).

    This is enough physical structure to:
      - Have all seven parameters appear in the dynamics so closed-loop
        recovery is a meaningful test of the inverse machinery;
      - Be smooth and well-conditioned for L-BFGS-B optimization;
      - Be fast enough that running the greybox test suite is feasible.

    What it is NOT: a substitute for `aivu_physics` Phase 1 v4.0. The real
    forward chain handles all of Phase 1's envelope load decomposition
    (opaque-wall conduction with per-element U-values, fenestration with
    NFRC ratings, operational infiltration with the Phase 1 amendment's
    Sherman-Grimsrud decomposition, slab F-factor coupling to ground,
    internal gains, psychrometric latent loads) properly. Closed-loop
    recovery against the stub validates the greybox MACHINERY;
    closed-loop recovery against `aivu_corpus` synthetic trajectories
    generated by the real forward chain (G8) is what §10 prescribes
    for spec validation.

    Per §11.2 amendment 2026-05-15: stub retires when G7 ships and G8
    passes. Until then, this is the analytic stand-in the test suite
    runs against.
    """

    # Integration step size in seconds. aivu_dynamic v0.2 §7 default is 60s.
    # For the v0.1 stub, we sub-sample the input telemetry to keep the
    # forward chain fast enough for the optimizer's hundreds of calls.
    integration_step_s: float = 60.0

    def run(
        self,
        theta: np.ndarray,
        hvac: HVACExcitation,
        weather: WeatherSeries,
        context: HomeStaticContext,
    ) -> StateTrajectory:
        if theta.shape != (NUM_CANONICAL_PARAMETERS,):
            raise ValueError(
                f"theta shape {theta.shape} != ({NUM_CANONICAL_PARAMETERS},). "
                f"Canonical order: {CANONICAL_PARAMETER_NAMES}"
            )
        r_opaque, u_fenestration, c_house, c_stack, c_wind, c_w, ceiling_coupling = theta

        # F_slab is now known-from-construction (HomeStaticContext) per
        # §11.2 amendment 2026-05-15.
        f_slab = context.f_slab_btuh_per_ft_f

        n_samples = hvac.monotonic_ns.shape[0]

        # Degenerate-parameter guard: return NaN trajectory if any
        # strictly-positive parameter is non-positive. The likelihood will
        # be very negative but we don't crash the optimizer.
        if (
            r_opaque <= 0
            or u_fenestration <= 0
            or c_house <= 0
            or c_w <= 0
            or ceiling_coupling < 0
            or c_stack < 0
            or c_wind < 0
        ):
            nan = np.full(n_samples, np.nan)
            return StateTrajectory(
                monotonic_ns=hvac.monotonic_ns,
                t_main_c=nan,
                w_main_kg_per_kg=nan,
                t_attic_c=nan,
            )

        # Telemetry sample period (typically 1 second)
        dt_telemetry_s = (
            (hvac.monotonic_ns[-1] - hvac.monotonic_ns[0]) / 1e9 / max(n_samples - 1, 1)
        )
        # Step every `stride` telemetry samples; reuse previous integration state
        # in between. This is the v0.1 stub's performance optimization for the
        # optimizer hot loop; the real aivu_dynamic integrator handles
        # 1-minute substeps with proper midpoint values per its §7.
        stride = max(1, int(round(self.integration_step_s / dt_telemetry_s)))

        t_main = np.empty(n_samples)
        w_main = np.empty(n_samples)
        t_attic = np.empty(n_samples)

        t_main[0] = context.initial_t_main_c
        w_main[0] = context.initial_w_main_kg_per_kg
        t_attic[0] = context.initial_t_attic_c

        # Internal stub attic capacitance — stub uses a fraction of C_house
        # as the attic's own thermal mass. The real adapter's attic ODE will
        # use context.c_attic_j_per_k; the stub keeps its self-consistent
        # internal value so closed-loop recovery of `ceiling_coupling_factor`
        # remains meaningful.
        c_attic = c_house * 0.05
        u_roof_area = max(20.0, context.ceiling_area_m2 * 0.4)
        slab_temp_c = 22.0
        h_o_w_per_m2_k = 25.0

        # Pre-import for tight loop
        from .psychrometrics import humidity_ratio as _hr, P_ATM_PHOENIX_PA as _Patm

        # Maintain the integrated state at telemetry resolution by stepping
        # at stride boundaries and forward-filling between them.
        last_integrated_i = 0
        t_m = t_main[0]
        w_m = w_main[0]
        t_a = t_attic[0]

        for i in range(1, n_samples):
            if (i - last_integrated_i) >= stride:
                dt = (hvac.monotonic_ns[i] - hvac.monotonic_ns[last_integrated_i]) / 1e9
                t_out = weather.t_outdoor_c[last_integrated_i]
                v_wind = weather.wind_speed_m_per_s[last_integrated_i]
                t_sol_air = t_out + weather.solar_global_w_per_m2[last_integrated_i] / h_o_w_per_m2_k

                q_attic_from_roof = u_roof_area * (t_sol_air - t_a)
                q_attic_to_main = ceiling_coupling * (t_a - t_m)
                dt_attic = (q_attic_from_roof - q_attic_to_main) / c_attic
                t_a_new = t_a + dt * dt_attic

                # Envelope conduction: opaque path (1/R_opaque) + fenestration
                # path (U_fenestration * window_area). Both scale with
                # (t_out - t_m). Stub-only: real chain decomposes properly.
                ua_opaque = 1.0 / r_opaque
                ua_fenestration = u_fenestration * context.window_area_m2 * 0.05
                q_envelope = (ua_opaque + ua_fenestration) * (t_out - t_m)

                q_slab = -f_slab * (t_m - slab_temp_c)

                # Operational infiltration: stack + wind decomposition. Both
                # carry sign with (t_out - t_m). Stub uses linear forms; real
                # chain uses Sherman-Grimsrud with the 0.65 / 1.0 exponents.
                dT_outin = t_out - t_m
                sign_dT = 1.0 if dT_outin > 0 else (-1.0 if dT_outin < 0 else 0.0)
                q_inf_stack = c_stack * abs(dT_outin) * sign_dT
                q_inf_wind = c_wind * v_wind * sign_dT
                q_infiltration = q_inf_stack + q_inf_wind

                q_hvac = hvac.q_sens_w[last_integrated_i]
                q_ceiling_in = ceiling_coupling * (t_a - t_m)
                dt_main = (
                    q_envelope + q_slab + q_infiltration + q_hvac + q_ceiling_in
                ) / c_house
                t_m_new = t_m + dt * dt_main

                w_out = _hr(
                    weather.t_outdoor_c[last_integrated_i],
                    weather.rh_outdoor_pct[last_integrated_i],
                    _Patm,
                )
                # Moisture transport: use (C_stack + C_wind) as a proxy for
                # the air-mass-flow scale. Stub-only; the real chain derives
                # ṁ_air from the operational-infiltration model directly.
                ma_inf_proxy = c_stack + c_wind
                dw_main = (w_out - w_m) * ma_inf_proxy * 0.05 / c_w
                w_m_new = w_m + dt * dw_main

                t_a = t_a_new
                t_m = t_m_new
                w_m = w_m_new
                last_integrated_i = i

            t_main[i] = t_m
            w_main[i] = w_m
            t_attic[i] = t_a

        return StateTrajectory(
            monotonic_ns=hvac.monotonic_ns,
            t_main_c=t_main,
            w_main_kg_per_kg=w_main,
            t_attic_c=t_attic,
        )
