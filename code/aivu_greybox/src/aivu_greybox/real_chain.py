"""§G7 — Real-chain adapter: greybox ForwardChain Protocol → Phase 1 + dynamic.

This module is gate G7 of the AIVU critical path. It replaces
`StubForwardChain` with the real forward physics: `aivu_physics` Phase 1
v4.0 (envelope/infiltration/attic primitives) composed by `aivu_dynamic`
v0.2 (integrator + capacitance + HVAC excitation) behind greybox's
`ForwardChain` Protocol. Once G7 lands, greybox's §5 passive fit and
§6 active fit run against real physics — gate G8 (closed-loop §5 test
against this adapter) is the earliest "stuff works" signal in the
project.


Architectural contract
----------------------

Greybox owns a seven-parameter canonical inverse identification per the
2026-05-15 §11.2 amendment:

    θ = (R_opaque, U_fenestration, C_house, C_stack, C_wind, C_w,
         ceiling_coupling_factor)

This adapter routes each parameter to its Phase 1 / aivu_dynamic home:

  C_house, C_w
      Pass through `run_dynamic`'s `c_eff_per_ft2_override` and
      `kappa_buffer_override` kwargs (D17-dyn / D18-dyn). SI→imperial
      conversion at the boundary.

  R_opaque
      Multiplier on opaque envelope U·A. Patched into Phase 1's
      `envelope.py` module constants for the duration of the call:
      `R_WALL_WHOLE`, `U_DOOR`, and `VARIANT_PROPERTIES[variant].R_ceiling`.

  U_fenestration
      Multiplier on fenestration U·A. Patched into `envelope.U_WINDOW`,
      `envelope.U_SGD`, and each entry of
      `geometry.nolan_8560.WINDOW_TYPES`.

  C_stack, C_wind
      Sherman-Grimsrud stack and wind coefficients. Patched into
      `infiltration.C_S_STACK` and `infiltration.C_W_WIND`. This is the
      "operational-infiltration" path that displaces HERS-convention
      cfm50; the §11.2 amendment names this explicitly.

  ceiling_coupling_factor
      Multiplier on the conductance between attic air and conditioned
      space, capturing as-built bypass paths (recessed cans, hatches,
      top-plate gaps, duct radiation through drywall) that nameplate
      U·A doesn't see. Applied as an additional multiplier on
      `VARIANT_PROPERTIES[variant].R_ceiling` (composed with R_opaque
      on the ceiling element).

F_slab is sourced from `HomeStaticContext` (known from gbXML + Manual J
climate-zone F-factor; not fitted) and patched into `envelope.F_SLAB`
the same way the seven θ values are.


Monkey-patching strategy
------------------------

The Phase 1 module constants are global state. Patching them is not
thread-safe and not parallel-safe. Greybox's Laplace fit is sequential
(one forward-chain call at a time per restart, one restart at a time),
so for this application it's acceptable. The context manager
`_envelope_overrides` snapshots originals on entry and restores them on
exit, including in the exception path, so a failed forward-chain call
does not leave Phase 1 in a perturbed state.

A cleaner alternative would be to add multiplier kwargs to Phase 1's
`compute_loads` (similar to how D17 added `T_in_F` and `W_in`). That's
a Phase 1 spec amendment with broader implications and is out of scope
for G7. The monkey-patch path is intentionally chosen as the minimal
adapter-side change.


Attic model — G7 v0.1 (steady-state)
------------------------------------

Phase 1's `attic.attic_temperature` is a steady-state weighted mean of
four driving temperatures (sol-air through roof, indoor through ceiling,
garage through knee walls, outdoor through ventilation). `compute_loads`
calls this inside its zone-ceiling computation; the steady-state result
flows through naturally as part of the integrator's substep evaluation.

With `ceiling_coupling_factor` applied as a multiplier on the ceiling
conductance, Phase 1's steady-state attic equation correctly responds:
the attic settles closer to T_in (more coupling pulls attic toward
conditioned space) AND the heat flow Q_ceiling = (f · U_ceil) · A · ΔT
sees both the multiplier and the new attic temperature. Physically
consistent.

What this v0.1 path does NOT capture: real attic thermal mass (C_attic).
The lag of T_attic behind T_sol-air — typically 30–90 min in Phoenix
foam-deck attics — is the signature that gives `ceiling_coupling_factor`
its identifiability under §6 active perturbation. Without it, the attic
channel responds instantaneously to driving conditions and the parameter
is harder to recover. The Phase 1 dynamic-attic amendment (separate
workstream) addresses this. For G7 v0.1 and G8 closed-loop validation,
the steady-state attic is sufficient: the parameter still affects the
envelope load and T_in trajectory.


T_attic output for greybox's attic-channel observation
------------------------------------------------------

`DynamicResult` from `run_dynamic` exposes `T_in` and `W_in` substep
trajectories but NOT `T_attic` (Phase 1 computes T_attic internally
inside `compute_loads` and discards it). Greybox's two-channel §5 fit
needs T_attic on the same time axis as T_in.

The adapter re-derives T_attic from Phase 1 primitives at each substep
using the same closed-form math `compute_loads` did. This is cheap
(four conductances, one weighted mean) and uses only public Phase 1
APIs. Same answer Phase 1 produced internally, just exposed.


HVAC excitation sign convention
-------------------------------

Greybox uses SI (W) with positive `q_sens_w` = HVAC adds heat to the
conditioned space (e.g., fan heat during §5 passive observation).
`aivu_dynamic` uses imperial (BTU/hr) with positive `Q_HVAC` = HVAC
removes heat (the cooling-convention default). The adapter wraps the
greybox excitation in a `Custom` HVACScheduleProvider that performs
the unit-and-sign conversion at the boundary:

    Q_HVAC[BTU/hr] = -q_sens_w[W] × 3.412


Weather
-------

Greybox supplies its own 1-Hz `WeatherSeries` (temperature, RH, solar,
wind aligned to the telemetry monotonic timestamps). `aivu_dynamic`
loads EPW from disk via `aivu_physics.weather.read_epw` (the site's
TMY3 file). The adapter lets aivu_dynamic load its EPW and treats
greybox's `WeatherSeries` as telemetry-axis metadata only — used to
align the output trajectory to observation timestamps.

This keeps the forward chain physically coherent: Phase 1's solar
geometry, sol-air temperatures, and outdoor conditions all derive from
the same EPW row, with no risk of `weather` and `solar_geometry`
disagreeing about what hour it is.


Performance
-----------

§5's L-BFGS-B fit calls the forward chain ~50–200 times per restart
× 4 restarts = up to ~800 calls per Laplace fit. Each call integrates
a 48-hour window at aivu_dynamic's default 60 substeps/hour (~2,880
substeps). Each substep evaluates `compute_loads`. Total ~2.3M
compute_loads calls per Laplace fit at the upper end. This is the
dominant cost; the adapter itself adds only the constant overhead of
context-manager setup/teardown per forward-chain call.

G7 v0.1 does not micro-optimize. If G8 reveals the wall time is too
high for practical iteration, the next move is shorter test windows
(8–12 hours instead of 48) for unit tests, with the real 48-hour
validation reserved for explicit validation runs.


[Ref: aivu_greybox §11.2 amendment 2026-05-15;
      aivu_greybox §5 v0.1; aivu_greybox §6 v0.1;
      aivu_physics Phase 1 v4.0; aivu_dynamic v0.2;
      aivu_greybox forward_chain.py ForwardChain Protocol;
      AIVU Architectural Distillation; v0.2 Critical Path Dependency Map.]
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

# Phase 1 / dynamic imports. These require both `aivu_physics` and
# `aivu_dynamic` installed in the same Python environment as greybox.
# Tests that exercise the real chain use `pytest.importorskip` to skip
# gracefully when the dependencies are absent.
from aivu_physics import attic as A
from aivu_physics import envelope as E
from aivu_physics import infiltration as INF
from aivu_physics import loads as L
from aivu_physics.geometry import nolan_8560 as N
from aivu_physics.geometry.site import Site

from aivu_dynamic.dynamic import run_dynamic
from aivu_dynamic.excitation import Custom, HVACScheduleProvider
from aivu_dynamic.integrator import IntegratorSpec
from aivu_dynamic.state import DynamicState

from .defaults import CANONICAL_PARAMETER_NAMES, NUM_CANONICAL_PARAMETERS
from .forward_chain import (
    ForwardChain,
    HomeStaticContext,
    HVACExcitation,
    StateTrajectory,
    WeatherSeries,
)


# ---------------------------------------------------------------------------
# Unit conversions at the SI/imperial boundary
# ---------------------------------------------------------------------------

# Watts → BTU/hr (positive sense unchanged; sign flip applied separately
# at the HVAC boundary per the package convention difference).
_W_TO_BTUH: float = 3.412141633

# J/K → BTU/°F (greybox C_house → aivu_dynamic c_eff_per_ft2 conversion).
# 1 BTU = 1055.056 J; 1 °F = (5/9) K; so 1 BTU/°F = 1055.056 × 9/5 = 1899.10 J/K,
# and 1 J/K = 1/1899.10 = 5.26527e-4 BTU/°F.
_J_PER_K_TO_BTU_PER_F: float = 1.0 / 1899.10081

# kg water / s → lb water / hr (greybox m_lat → aivu_dynamic M_HVAC):
# 1 kg/s × 3600 s/hr × 2.20462 lb/kg = 7936.64 lb/hr.
_KG_PER_S_TO_LB_PER_HR: float = 3600.0 * 2.20462

# ft²/m² (greybox carries floor_area_m2; Phase 1 carries floor_area_ft²).
_FT2_PER_M2: float = 10.7639104


def _c_to_f(t_c: float) -> float:
    """°C → °F."""
    return t_c * 9.0 / 5.0 + 32.0


def _f_to_c(t_f: float) -> float:
    """°F → °C."""
    return (t_f - 32.0) * 5.0 / 9.0


# ---------------------------------------------------------------------------
# Envelope-constant context manager — applies θ to Phase 1's globals
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _envelope_overrides(
    *,
    r_opaque: float,
    u_fenestration: float,
    f_ceiling: float,
    c_stack: float,
    c_wind: float,
    f_slab: float,
    variant: E.EnvelopeVariant,
):
    """Temporarily patch Phase 1's envelope and infiltration constants.

    Snapshots originals on entry and restores them on exit, even if the
    wrapped code raises. Not thread-safe by construction (the constants
    are module-level globals); use only in greybox's sequential Laplace
    fit context.

    The multipliers are applied as:
      - Opaque elements (walls, doors, ceiling, knee walls):
            new_U = r_opaque × nameplate_U
        Implemented by dividing the corresponding R values by r_opaque
        (since U = 1/R), or by multiplying U values directly where the
        constant is a U.
      - Ceiling specifically gets an additional `f_ceiling` multiplier
        on top of `r_opaque`:
            new_U_ceiling = r_opaque × f_ceiling × nameplate_U_ceiling
      - Fenestration (windows, SGD):
            new_U = u_fenestration × nameplate_U
        Applied to envelope.U_WINDOW, envelope.U_SGD, and every entry
        of geometry.nolan_8560.WINDOW_TYPES.
      - Infiltration: C_S_STACK and C_W_WIND replaced with greybox's
        calibrated (c_stack, c_wind).
      - F_slab: replaced with the home's known-from-construction value
        from HomeStaticContext.
    """
    # Snapshot
    original_R_wall = E.R_WALL_WHOLE
    original_U_door = E.U_DOOR
    original_U_window = E.U_WINDOW
    original_U_sgd = E.U_SGD
    original_F_slab = E.F_SLAB
    original_U_knee = A.U_KNEE_WALL
    original_C_s_stack = INF.C_S_STACK
    original_C_w_wind = INF.C_W_WIND
    original_variant_props = E.VARIANT_PROPERTIES[variant]
    original_window_types = dict(N.WINDOW_TYPES)  # shallow copy of dict

    try:
        # Apply opaque-envelope R_opaque multiplier
        # new_U = r_opaque × U_nominal ⇔ new_R = R_nominal / r_opaque
        E.R_WALL_WHOLE = original_R_wall / r_opaque
        E.U_DOOR = original_U_door * r_opaque
        A.U_KNEE_WALL = original_U_knee * r_opaque

        # Ceiling: composed multiplier r_opaque × f_ceiling
        # new_R_ceiling = R_nominal / (r_opaque × f_ceiling)
        # Guard against optimizer probes at composed factor near zero.
        composed_ceiling_factor = max(r_opaque * f_ceiling, 1.0e-3)
        new_R_ceiling = original_variant_props.R_ceiling / composed_ceiling_factor
        E.VARIANT_PROPERTIES[variant] = replace(
            original_variant_props,
            R_ceiling=new_R_ceiling,
        )

        # Fenestration U_fenestration multiplier
        E.U_WINDOW = original_U_window * u_fenestration
        E.U_SGD = original_U_sgd * u_fenestration
        # Patch each WindowType entry. Each entry is a frozen dataclass
        # with a .U field; rebuild with the multiplier applied.
        for code, wt in original_window_types.items():
            N.WINDOW_TYPES[code] = replace(wt, U=wt.U * u_fenestration)

        # Slab F-factor (from context, not fitted)
        E.F_SLAB = f_slab

        # Sherman-Grimsrud coefficients
        INF.C_S_STACK = c_stack
        INF.C_W_WIND = c_wind

        yield
    finally:
        # Restore everything
        E.R_WALL_WHOLE = original_R_wall
        E.U_DOOR = original_U_door
        E.U_WINDOW = original_U_window
        E.U_SGD = original_U_sgd
        E.F_SLAB = original_F_slab
        A.U_KNEE_WALL = original_U_knee
        INF.C_S_STACK = original_C_s_stack
        INF.C_W_WIND = original_C_w_wind
        E.VARIANT_PROPERTIES[variant] = original_variant_props
        # Restore window-types dict in place (keeps any references valid)
        N.WINDOW_TYPES.clear()
        N.WINDOW_TYPES.update(original_window_types)


# ---------------------------------------------------------------------------
# HVAC excitation: greybox SI → aivu_dynamic imperial, via Custom provider
# ---------------------------------------------------------------------------


def _make_hvac_provider(
    hvac: HVACExcitation,
    t0_ns: int,
) -> HVACScheduleProvider:
    """Wrap a greybox HVACExcitation as an aivu_dynamic HVACScheduleProvider.

    Sign and unit:
      - greybox `q_sens_w` is W, positive = HVAC adds heat to conditioned
        space.
      - dynamic `Q_HVAC` is BTU/hr, positive = HVAC removes heat.
      - Conversion: Q_HVAC[BTU/hr] = -q_sens_w[W] × 3.412
      - Latent: m_lat is kg water/s with the same sign convention as
        q_sens_w (greybox positive = HVAC adds moisture). Dynamic's
        M_HVAC is lb water/hr with positive = HVAC removes moisture.
        Conversion includes the same sign flip plus kg/s → lb/hr.

    Time lookup uses nearest-neighbor on the greybox 1-Hz grid. With
    aivu_dynamic's default 60 substeps/hour (1-minute Δt), nearest-
    neighbor is within sensor noise; we don't interpolate.
    """
    # Pre-compute time offsets in hours from t0 for substep lookup.
    t_hours_grid = (hvac.monotonic_ns - t0_ns) / 1.0e9 / 3600.0
    q_btuh = -hvac.q_sens_w * _W_TO_BTUH
    m_lb_per_hr = -hvac.m_lat_kg_per_s * _KG_PER_S_TO_LB_PER_HR

    def _lookup_idx(t_hours: float) -> int:
        idx = int(np.searchsorted(t_hours_grid, t_hours))
        if idx < 0:
            return 0
        if idx >= len(q_btuh):
            return len(q_btuh) - 1
        return idx

    def q_func(t_hours, x, cfg, hour, wfile, occupancy_flag, rec):
        return float(q_btuh[_lookup_idx(t_hours)])

    def m_func(t_hours, x, cfg, hour, wfile, occupancy_flag, rec):
        return float(m_lb_per_hr[_lookup_idx(t_hours)])

    return Custom(Q_func=q_func, M_func=m_func)


# ---------------------------------------------------------------------------
# T_attic recomputation — uses Phase 1 primitives at substep cadence
# ---------------------------------------------------------------------------


def _compute_t_attic_trajectory(
    dyn_result,
    site: Site,
    cfg: L.SimConfig,
    epw_path,
) -> np.ndarray:
    """Reconstruct T_attic substep-by-substep using Phase 1 primitives.

    DynamicResult carries `T_in` per substep but not `T_attic`. We
    re-derive T_attic at each substep using the same closed-form math
    Phase 1's `compute_loads` did internally — same EPW row, same
    variant U values, same garage buffer, same area-weighted sol-air.
    Because we're inside the `_envelope_overrides` context, the patched
    ceiling R value is what `attic_temperature` sees, so f_ceiling and
    r_opaque are reflected.

    Returns: shape (n_substeps,) array of T_attic in °C (greybox SI).
    """
    # Lazy import to avoid circular issues; weather module is heavy.
    from aivu_physics import weather as W
    from aivu_dynamic.dynamic import _build_hour_context

    wfile = W.read_epw(epw_path, site)

    t_hours = np.array(dyn_result.t_hours, dtype=np.float64)
    t_in_f = np.array(dyn_result.T_in, dtype=np.float64)
    n = t_hours.shape[0]
    t_attic_f = np.empty(n, dtype=np.float64)

    # Per-hour cache of (T_sol_air_roof_F, m_dot_attic) so we don't redo
    # solar geometry on every substep.
    hour_cache: dict[int, tuple[float, float, float]] = {}

    props = E.VARIANT_PROPERTIES[cfg.variant]

    for k in range(n):
        # Map t_hours to integer EPW-hour index. Substeps live inside
        # an hour, so int() truncation gives the hour boundary.
        hour_idx = min(int(t_hours[k]), len(wfile) - 1)

        if hour_idx not in hour_cache:
            wrow = wfile[hour_idx]
            hour_ctx = _build_hour_context(wrow, site)
            # Sol-air roof: area-weight across facets.
            T_sa_roof = _area_weighted_sol_air_roof(hour_ctx, cfg)
            # Vented mass flow (zero for foam variant).
            if cfg.variant == E.EnvelopeVariant.UNVENTED_FOAM:
                m_dot = 0.0
            else:
                m_dot = A.vented_attic_mass_flow(
                    A.vented_attic_ach(hour_ctx.V_wind_mph)
                )
            hour_cache[hour_idx] = (T_sa_roof, m_dot, hour_ctx.T_out_F)

        T_sa_roof, m_dot, T_out_F = hour_cache[hour_idx]
        # Substep-specific: T_in changes per substep, and T_garage
        # depends on T_in.
        t_in_now_f = t_in_f[k]
        T_garage = A.garage_buffer_temperature(t_in_now_f, T_out_F)

        t_attic_f[k] = A.attic_temperature(
            U_roof=props.U_roof_deck,
            A_roof=N.A_ROOF_CONDITIONED_FT2,
            T_sol_air_roof_F=T_sa_roof,
            U_ceil=props.U_ceiling,  # already patched by context manager
            A_ceil=N.A_CEILING_CONDITIONED_FT2,
            T_in_F=t_in_now_f,
            U_knee=A.U_KNEE_WALL,    # already patched
            A_knee=N.A_KNEE_WALL_FT2,
            T_garage_F=T_garage,
            m_dot_attic=m_dot,
            T_out_F=T_out_F,
        )

    # °F → °C for greybox SI output
    return (t_attic_f - 32.0) * 5.0 / 9.0


def _area_weighted_sol_air_roof(hour: L.HourContext, cfg: L.SimConfig) -> float:
    """Area-weighted sol-air across conditioned-roof facets.

    Mirrors what `loads._roof_area_weighted_sol_air` computes internally
    inside `compute_loads`. Phase 1's helper is module-private; we use
    the same public primitives it calls.
    """
    from aivu_physics import solar_geometry as SG
    from aivu_physics import surface_irradiance as SI

    h_o = SI.outdoor_film_coefficient(hour.V_wind_mph)
    pairs: list[tuple[float, float]] = []
    for facet in N.ROOF_FACETS:
        applied_az = (
            facet.canonical_azimuth_deg + cfg.orientation_offset_deg
        ) % 360.0
        tilt_deg = facet.tilt_rad * 180.0 / 3.141592653589793
        cos_theta = SG.cos_incidence_angle(
            hour.altitude_deg,
            hour.solar_azimuth_deg,
            surface_tilt_deg=tilt_deg,
            surface_azimuth_deg=applied_az,
        )
        I_surface = SI.total_surface_irradiance(
            DNI=hour.DNI,
            DHI=hour.DHI,
            altitude_deg=hour.altitude_deg,
            cos_theta=max(0.0, cos_theta),
            surface_tilt_deg=tilt_deg,
        )
        T_sa = SI.sol_air_temperature(
            T_out_F=hour.T_out_F,
            I_surface=I_surface,
            h_o=h_o,
            alpha=SI.ALPHA_ROOF,
            lw_correction_F=SI.LW_CORRECTION_HORIZONTAL_F,
        )
        # Use area-fraction (facet.area_ft2 / total_roof_area) to match
        # attic.area_weighted_sol_air's normalization expectation.
        pairs.append((T_sa, facet.area_ft2))
    # Normalize area fractions
    total_area = sum(a for _, a in pairs)
    normalized = [(T, a / total_area) for T, a in pairs]
    return A.area_weighted_sol_air(normalized)


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealForwardChain:
    """Real-chain adapter implementing greybox's `ForwardChain` Protocol.

    Construction:
        site:        Phase 1 Site (lat/lon, EPW filename, T_ground_F).
        sim_config:  Phase 1 SimConfig (envelope variant, orientation,
                     setpoint).
        integrator:  aivu_dynamic IntegratorSpec. Defaults to Euler at
                     60 substeps/hour. Tests may use larger substep
                     counts or switch to RK4 for tighter accuracy.
        epw_path:    Optional override path to the EPW file. When None
                     (default), aivu_dynamic resolves the path from
                     `site.epw_filename` in its package data directory.

    Per-home configuration that varies (initial state, attic capacitance,
    F_slab) is carried in the greybox-facing `HomeStaticContext` and
    passed at `run()` time.

    For closed-loop tests (gate G8), construct one RealForwardChain per
    pilot home configuration. For production use under `aivu_hpm`, the
    adapter is instantiated once at HPM init and reused across the §5
    and §6 fits.
    """

    site: Site
    sim_config: L.SimConfig
    integrator: IntegratorSpec = field(default_factory=IntegratorSpec)
    epw_path: Any = None  # Optional path override

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
        r_opaque, u_fenestration, c_house_si, c_stack, c_wind, c_w, f_ceiling = theta

        # F_slab from context (known from gbXML + climate-zone F-factor)
        f_slab = context.f_slab_btuh_per_ft_f

        # C_house: greybox J/K → aivu_dynamic BTU/(°F·ft²)
        floor_area_ft2 = context.floor_area_m2 * _FT2_PER_M2
        c_house_btu_per_f = c_house_si * _J_PER_K_TO_BTU_PER_F
        c_eff_per_ft2 = c_house_btu_per_f / floor_area_ft2

        # C_w pass-through (units convention not yet tight; see §11.2
        # amendment notes on provisional unit alignment)
        kappa_buffer = c_w

        # Initial state: greybox °C → aivu_dynamic °F
        initial_state = DynamicState(
            T_in_F=_c_to_f(context.initial_t_main_c),
            W_in=context.initial_w_main_kg_per_kg,
        )

        # HVAC excitation
        t0_ns = int(hvac.monotonic_ns[0])
        excitation = _make_hvac_provider(hvac, t0_ns)

        # Duration: round greybox window to whole hours (aivu_dynamic's
        # cadence). For a 48-hour fit window with 1-Hz telemetry, this
        # is exact.
        duration_s = float(hvac.monotonic_ns[-1] - hvac.monotonic_ns[0]) / 1.0e9
        duration_hours = max(1, int(round(duration_s / 3600.0)))

        # Resolve EPW path (used for both the dynamic run and the
        # T_attic reconstruction afterward).
        if self.epw_path is None:
            from pathlib import Path as _P
            from aivu_physics import sim as _SIM
            pkg_root = _P(_SIM.__file__).resolve().parents[2]
            epw_path = pkg_root / "data" / "weather" / self.site.epw_filename
        else:
            epw_path = self.epw_path

        with _envelope_overrides(
            r_opaque=r_opaque,
            u_fenestration=u_fenestration,
            f_ceiling=f_ceiling,
            c_stack=c_stack,
            c_wind=c_wind,
            f_slab=f_slab,
            variant=self.sim_config.variant,
        ):
            dyn_result = run_dynamic(
                site=self.site,
                cfg=self.sim_config,
                occupancy="unoccupied",  # §5 protocol: pre-occupancy
                excitation=excitation,
                initial_state=initial_state,
                integrator=self.integrator,
                duration_hours=duration_hours,
                epw_path=epw_path,
                c_eff_per_ft2_override=c_eff_per_ft2,
                kappa_buffer_override=kappa_buffer,
            )

            # T_attic reconstruction — done inside the override context
            # so the patched ceiling U feeds the attic equation.
            t_attic_c_substeps = _compute_t_attic_trajectory(
                dyn_result, self.site, self.sim_config, epw_path
            )

        # Project substep trajectories onto greybox's observation grid.
        t_substeps_hours = np.array(dyn_result.t_hours, dtype=np.float64)
        t_substeps_ns = t0_ns + (t_substeps_hours * 3600.0 * 1.0e9).astype(np.int64)
        t_main_c_substeps = np.array(
            [_f_to_c(t) for t in dyn_result.T_in], dtype=np.float64
        )
        w_main_substeps = np.array(dyn_result.W_in, dtype=np.float64)

        obs_ns_f64 = hvac.monotonic_ns.astype(np.float64)
        sub_ns_f64 = t_substeps_ns.astype(np.float64)

        t_main_c_at_obs = np.interp(obs_ns_f64, sub_ns_f64, t_main_c_substeps)
        w_main_at_obs = np.interp(obs_ns_f64, sub_ns_f64, w_main_substeps)
        t_attic_c_at_obs = np.interp(obs_ns_f64, sub_ns_f64, t_attic_c_substeps)

        return StateTrajectory(
            monotonic_ns=hvac.monotonic_ns,
            t_main_c=t_main_c_at_obs,
            w_main_kg_per_kg=w_main_at_obs,
            t_attic_c=t_attic_c_at_obs,
        )
