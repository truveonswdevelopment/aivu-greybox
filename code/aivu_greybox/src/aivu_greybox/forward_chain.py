"""Forward-chain interface — what aivu_greybox needs from aivu_physics
+ aivu_dynamic.

This module defines a Protocol that the real `aivu_physics` Phase 1 v4.0 +
`aivu_dynamic` v0.2 packages must satisfy. The signatures match the specs:

  - aivu_dynamic.dynamic.run(theta, u_meas, w_meas) → trajectory per
    `aivu_dynamic` v0.2 §6 (state equations) and §7 (integration).
  - Theta = (R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor)
    per `aivu_greybox` §§1-3 v0.1.1 canonical six-parameter set.

Per `aivu_greybox` v0.1 §5.3, the forward chain is consumed at evaluation
time as `(T_main^pred(t), W_main^pred(t), T_attic^pred(t))` over the
48-hour window for each candidate θ. The greybox code does not own the
forward chain; it owns the interface and calls into the chain.

In v0.1 the live implementations of `aivu_physics` Phase 1 v4.0 and
`aivu_dynamic` v0.2 are not yet shipped to this package. The
`StubForwardChain` here provides a numerically-credible analytic stand-in
for testing the greybox machinery against synthetic trajectories while
the real packages stabilize; production use replaces it with a thin
adapter that wraps the real packages' APIs.
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
    schedule. They are home-specific but not part of the six-parameter
    canonical fit set.

    In production, this comes from the home's gbXML or the AOT-supplied
    SimConfig. In v0.1 stub, it carries the minimum the analytic stand-in
    needs.
    """

    home_id: str
    floor_area_m2: float  # ~167 m² (~1800 ft²) for V752-class
    ceiling_area_m2: float
    slab_area_m2: float
    window_area_m2: float
    initial_t_main_c: float  # T_main at window start
    initial_w_main_kg_per_kg: float
    initial_t_attic_c: float


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

    A class satisfying this protocol provides one method: given the six-
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
            theta: Six-element parameter vector in canonical order
                (R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor).
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

    NOT physically rigorous in detail. The stub implements:

      - First-order lumped-capacitance envelope dynamics:
            C_house · dT_main/dt = (T_outdoor - T_main)/R_eff
                                   - F_slab · (T_main - T_slab)
                                   + cfm50_to_infiltration_load(cfm50, ...)
                                   + Q_sens(t)
                                   - ceiling_coupling · (T_main - T_attic)
      - Two-state attic-main coupling:
            C_attic · dT_attic/dt = (T_sol_air - T_attic) · U_roof·A_roof
                                    - ceiling_coupling · (T_attic - T_main)
      - First-order moisture state with C_w:
            C_w · dW_main/dt = (W_outdoor - W_main) · infiltration_proxy

    This is enough physical structure to:
      - Have all six parameters appear in the dynamics so closed-loop
        recovery is a meaningful test of the inverse machinery;
      - Be smooth and well-conditioned for L-BFGS-B optimization;
      - Be fast enough that running the greybox test suite is feasible.

    What it is NOT: a substitute for `aivu_physics` Phase 1 v4.0. The real
    forward chain handles all of Phase 1's envelope load decomposition
    (opaque-wall conduction, fenestration, infiltration with stack/wind
    components, slab F-factor coupling to ground, internal gains,
    psychrometric latent loads) properly. Closed-loop recovery against
    the stub validates the greybox MACHINERY; closed-loop recovery
    against `aivu_corpus` synthetic trajectories generated by the real
    forward chain is what §10 prescribes for spec validation.
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
        r_eff, c_house, cfm50, f_slab, c_w, ceiling_coupling = theta

        n_samples = hvac.monotonic_ns.shape[0]

        if r_eff <= 0 or c_house <= 0 or c_w <= 0 or ceiling_coupling < 0:
            # Return a degenerate trajectory; the likelihood will be very
            # negative but we don't crash the optimizer
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
                t_sol_air = t_out + weather.solar_global_w_per_m2[last_integrated_i] / h_o_w_per_m2_k

                q_attic_from_roof = u_roof_area * (t_sol_air - t_a)
                q_attic_to_main = ceiling_coupling * (t_a - t_m)
                dt_attic = (q_attic_from_roof - q_attic_to_main) / c_attic
                t_a_new = t_a + dt * dt_attic

                q_envelope = (t_out - t_m) / r_eff
                q_slab = -f_slab * (t_m - slab_temp_c)
                q_infiltration = cfm50 * 0.0001 * (t_out - t_m)
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
                dw_main = (w_out - w_m) * cfm50 * 0.00005 / c_w
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
