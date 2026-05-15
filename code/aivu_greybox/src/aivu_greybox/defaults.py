"""Pinned numerical defaults per `aivu_greybox` §11.2 canonical table.

Every numerical default from §§4-7 closing notes is reproduced here with its
origin section and v0.2 derivation status. Updates land in the origin
section's closing notes; this module follows by reference.

The module deliberately uses plain module-level constants rather than a
configuration object: §11 is "the canonical table", not "the configuration
schema". A configuration object that overrides defaults is a separate
concern that earns its place when the pilot demonstrates per-home overrides
are needed.

§11.2 amendment 2026-05-15: canonical parameter set updated from six to
seven. See spec/aivu_greybox_v0_1_section_11_amendment_2026_05_15.md for
the rationale. R_eff split into (R_opaque, U_fenestration); cfm50 replaced
by (C_stack, C_wind) operational-infiltration coefficients; F_slab moved
to HomeStaticContext as known-from-construction.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4 — Fan-Heat Consistency Check
# ---------------------------------------------------------------------------

# Minimum Fan-Heat window duration. The window must be at least this long
# for the time-averaged residual to settle within sensor noise.
# v0.2 derivation pending.
FH_TAU_FH_MIN: float = 30.0 * 60.0  # 30 minutes in seconds

# Settling window after fan turn-on before residual computation begins.
# Allows duct interior to reach thermal quasi-equilibrium with the air stream.
# v0.2 derivation pending.
FH_TAU_WARMUP_S: float = 15.0 * 60.0  # 15 minutes in seconds

# Pass threshold on the relative Fan-Heat residual R_FH / (η̂_distribution · ⟨P_fan⟩).
# v0.2 derivation: RSS propagation across Sensirion SHT35 stack, per-terminal
# Venturi calibration, Eaton-breaker electrical accuracy, with √12 spatial-
# averaging benefit on independent noise terms. The 1-σ floor is ~3.6%; the
# threshold sits one quarter-sigma above. Tightening below 4% would put the
# check below its noise floor.
FH_EPS_FH: float = 0.04  # 4% relative

# Lower and upper bounds on physically plausible identified η̂_distribution.
# Outside-range identification triggers Fan-Heat fail.
# v0.2 derivation pending.
FH_ETA_MIN: float = 0.85
FH_ETA_MAX: float = 0.96

# Maximum allowed return-side humidity-ratio drift over the Fan-Heat window.
# Larger drift implies an uncontrolled moisture source.
# v0.2 derivation pending.
FH_DELTA_W_MAX: float = 0.0002  # kg/kg

# Maximum allowed spatial standard deviation of terminal enthalpies during
# a Fan-Heat window. Larger spread implies non-uniform delivery.
# v0.2 derivation pending.
FH_SIGMA_SPATIAL_MAX_KJ_PER_KG: float = 0.5  # kJ/kg

# ---------------------------------------------------------------------------
# §5 — Day-1-2 passive batch fit
# ---------------------------------------------------------------------------

# Fan-mixing schedule per §5.3. 10 min/hr at clock-aligned hours.
# v0.1 settled.
FAN_ON_DURATION_S: float = 10.0 * 60.0  # 10 minutes
FAN_CYCLE_DURATION_S: float = 60.0 * 60.0  # 1 hour

# Per fan-on interval, first 60 s are observed for attic channel only;
# excluded from main channel. v0.1 settled.
WARMUP_EXCLUSION_S: float = 60.0

# Standard deviation on the spatial-averaged attic observation during the
# warmup window. v0.1 conservative; pilot validation will tighten.
# §5 v3.3 documents the reasoning: single-probe floor 0.1 °C, full-
# independent-√12 floor 0.029 °C, partial-correlation midpoint 0.05 °C.
SIGMA_T_ATTIC_C: float = 0.05

# Standard deviation on the main-channel return-plenum temperature observation.
# Sensirion SHT35 single-probe accuracy. v0.1 settled.
SIGMA_T_MAIN_C: float = 0.10

# Mode-agreement failure threshold for §5.7 convergence diagnostics.
# If the four prior-perturbed Laplace restarts return modes that disagree
# by more than 5% of the prior σ on any parameter, convergence fails.
LAPLACE_MODE_AGREEMENT_FRACTION: float = 0.05

# Number of independent L-BFGS-B starts from prior-perturbed initial values.
LAPLACE_NUM_RESTARTS: int = 4

# ---------------------------------------------------------------------------
# §6 — Day-4-5 active-perturbation batch fit
# ---------------------------------------------------------------------------

# Phase durations for the four-phase Days 4-5 protocol.
PHASE_A_DURATION_S: float = 18.0 * 3600.0  # 18 hours cooling drive
PHASE_B_DURATION_S: float = 6.0 * 3600.0  # 6 hours decay
PHASE_C_DURATION_S: float = 18.0 * 3600.0  # 18 hours reverse drive
PHASE_D_DURATION_S: float = 6.0 * 3600.0  # 6 hours closing observation

# Phase A asymptote rate threshold (indoor °C/hr).
PHASE_A_ASYMPTOTE_RATE_C_PER_HR: float = 0.1

# Phase D held-out validation tolerance (relative).
PHASE_D_RESIDUAL_TOLERANCE: float = 0.05

# Protocol-adherence tolerance on phase-transition timestamps.
PHASE_TRANSITION_TOLERANCE_S: float = 15.0 * 60.0  # ±15 minutes

# Wider uncertainty bound on attic-channel observations during Phase C's
# 50/10 schedule, where 10-minute fan-off intervals are too short for ducts
# to fully equilibrate with attic air.
SIGMA_T_ATTIC_DEGRADED_C: float = 0.10

# ---------------------------------------------------------------------------
# §7 — Recursive-mode Phase 2 solver
# ---------------------------------------------------------------------------

# Heartbeat cadence. Per §3.2.
HEARTBEAT_HZ: float = 1.0
HEARTBEAT_PERIOD_S: float = 1.0 / HEARTBEAT_HZ

# Per-heartbeat wall-clock budget (§7 INV-REC7-2 / §3.2 ceiling).
HEARTBEAT_BUDGET_MS: float = 100.0

# End-of-day async-budget (§7 INV-REC7-2).
END_OF_DAY_BUDGET_S: float = 60.0

# Significance-event drift threshold for §7.3.2 (2σ from §6 Day-5 value).
# v0.2 derivation pending.
SIGNIFICANCE_EVENT_SIGMA_THRESHOLD: float = 2.0

# First Law residual threshold for the §7.5.4 flag (fraction of daily
# total energy throughput). v0.2 derivation pending.
FIRST_LAW_RESIDUAL_THRESHOLD_FRACTION: float = 0.05

# ---------------------------------------------------------------------------
# §8 — Identifiability collapse detection
# ---------------------------------------------------------------------------

# Per-parameter prior-only test: flag fires when σ_posterior / σ_prior > 0.95.
# v0.1 pinned per INV-ID8-2; pilot data may tighten in v0.2.
ID8_RHO_FLAG_THRESHOLD: float = 0.95

# Tightness breakpoint between "loose" and "degraded" states.
# A parameter whose σ_post/μ_post exceeds 2× the §5.5/§6.4 expected value
# emits "degraded".
ID8_DEGRADED_MULTIPLIER: float = 2.0

# Hessian condition-number threshold for joint-identifiability flag (INV-ID8-3).
ID8_HESSIAN_KAPPA_THRESHOLD: float = 1.0e6

# Eigenvalue ridge threshold relative to λ_max (INV-ID8-3).
ID8_RIDGE_EIGENVALUE_FRACTION: float = 1.0e-4

# ---------------------------------------------------------------------------
# Seven-parameter canonical set, in canonical order
# ---------------------------------------------------------------------------
# Per §11.2 amendment 2026-05-15. Replaces the v0.1 six-parameter set.
#
# Physical roles:
#   R_opaque                 — dimensionless multiplier on opaque-envelope U·A
#                              (walls, ceiling, opaque doors).
#   U_fenestration           — dimensionless multiplier on fenestration U·A
#                              (windows, sliding glass doors).
#   C_house                  — whole-house sensible thermal capacitance, J/K.
#   C_stack                  — stack-driven operational-infiltration coefficient.
#                              Replaces v0.1 cfm50.
#   C_wind                   — wind-driven operational-infiltration coefficient.
#                              Replaces v0.1 cfm50.
#   C_w                      — whole-house latent moisture capacitance.
#   ceiling_coupling_factor  — dimensionless multiplier on total attic-to-
#                              conditioned-space coupling (captures bypass
#                              paths: recessed cans, hatches, top-plate gaps,
#                              duct radiation, can-light air mixing).

CANONICAL_PARAMETER_NAMES: tuple[str, ...] = (
    "R_opaque",
    "U_fenestration",
    "C_house",
    "C_stack",
    "C_wind",
    "C_w",
    "ceiling_coupling_factor",
)
NUM_CANONICAL_PARAMETERS: int = len(CANONICAL_PARAMETER_NAMES)

# ---------------------------------------------------------------------------
# §8 expected-tightness table — promoted to defaults per §11.2 amendment
# ---------------------------------------------------------------------------
# Per-parameter σ_post / μ_post that the §8 identifiability report classifies
# as "within" (≤ value), "loose" (≤ 2×), or "degraded" (> 2×). v0.1
# provisional; pilot data will tighten in v0.2.
#
# C_wind carries the loosest expected tightness, reflecting Phoenix's
# low-and-relatively-uniform wind regime. Climate-zone-conditional tables
# are v0.2 work.

EXPECTED_TIGHTNESS_SIGMA_OVER_MU: dict[str, float] = {
    "R_opaque": 0.05,
    "U_fenestration": 0.07,
    "C_house": 0.05,
    "C_stack": 0.20,
    "C_wind": 0.40,
    "C_w": 0.25,
    "ceiling_coupling_factor": 0.15,
}
