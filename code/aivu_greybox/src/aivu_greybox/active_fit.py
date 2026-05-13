"""§6 — Days 4-5 active-perturbation batch fit.

Builds on §5's machinery. Differences:

  - Prior is §5's end-of-Day-2 posterior (not a cold prior).
  - HVAC excitation is the controlled four-phase protocol (Phase A 18h
    continuous cooling drive, Phase B 6h decay, Phase C 18h reverse drive,
    Phase D 6h closing observation).
  - Likelihood is phase-aware: different σ_T_attic for Phase C samples
    (degraded due to 50/10 fan schedule per §6.3), attic channel
    unavailable during Phase A (continuous fan).
  - Additional §6.6 diagnostics: Phase D held-out residual, Phase A
    asymptote check.
  - `η_distribution` is held at the §4 Day-1 value per INV-FIT45-7.
  - Output is `Day5Posterior` signed via threshold_attest with
    AttestationMoment.ENVELOPE_HALF_FINAL per §12.

The Laplace solver, finite-difference Hessian, and §8 identifiability-
report builder are all reused from `passive_fit`. §6 only adds the
phase-aware likelihood and the §6.6 phase-D diagnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

from .defaults import (
    CANONICAL_PARAMETER_NAMES,
    LAPLACE_MODE_AGREEMENT_FRACTION,
    LAPLACE_NUM_RESTARTS,
    NUM_CANONICAL_PARAMETERS,
    PHASE_A_ASYMPTOTE_RATE_C_PER_HR,
    PHASE_A_DURATION_S,
    PHASE_B_DURATION_S,
    PHASE_C_DURATION_S,
    PHASE_D_DURATION_S,
    PHASE_D_RESIDUAL_TOLERANCE,
    SIGMA_T_ATTIC_C,
    SIGMA_T_ATTIC_DEGRADED_C,
    SIGMA_T_MAIN_C,
    WARMUP_EXCLUSION_S,
)
from .fan_heat import FanHeatSample, SHTReading, TerminalSample
from .forward_chain import (
    ForwardChain,
    HomeStaticContext,
    HVACExcitation,
    StateTrajectory,
    WeatherSeries,
)
from .passive_fit import (
    LaplaceFitFailed,
    LaplaceResult,
    SIGMA_W,
    build_identifiability_report,
    finite_difference_hessian,
)
from .passive_fit_types import Prior6D
from .psychrometrics import P_ATM_PHOENIX_PA, humidity_ratio
from .records import Day5Posterior, IdentifiabilityReport, PosteriorCommon
from ._signing_stub import (
    AttestationMoment,
    LogInclusionProof,
    SignedRecord,
    ThresholdAttestation,
    commit_to_log,
    sign_record,
    threshold_attest,
)


# ---------------------------------------------------------------------------
# Phase enumeration
# ---------------------------------------------------------------------------


class ActivePhase(Enum):
    """The four phases of the Days 4-5 protocol per §6.2."""

    PHASE_A_COOLING_DRIVE = "phase_a"
    PHASE_B_DECAY = "phase_b"
    PHASE_C_REVERSE_DRIVE = "phase_c"
    PHASE_D_CLOSING = "phase_d"


# Boundaries (seconds since window start), per §6.2 default durations
_PHASE_BOUNDARIES_S: tuple[float, float, float, float] = (
    PHASE_A_DURATION_S,  # end of A
    PHASE_A_DURATION_S + PHASE_B_DURATION_S,  # end of B
    PHASE_A_DURATION_S + PHASE_B_DURATION_S + PHASE_C_DURATION_S,  # end of C
    PHASE_A_DURATION_S + PHASE_B_DURATION_S + PHASE_C_DURATION_S + PHASE_D_DURATION_S,  # end of D
)


def _phase_at(
    seconds_since_start: float,
    boundaries: tuple[float, float, float, float] = _PHASE_BOUNDARIES_S,
) -> ActivePhase:
    """Classify a sample by its time-since-window-start into one of the four phases.

    `boundaries` is (end_of_A, end_of_B, end_of_C, end_of_D) in seconds.
    Default is the spec values; tests may pass shortened boundaries.
    """
    if seconds_since_start < boundaries[0]:
        return ActivePhase.PHASE_A_COOLING_DRIVE
    elif seconds_since_start < boundaries[1]:
        return ActivePhase.PHASE_B_DECAY
    elif seconds_since_start < boundaries[2]:
        return ActivePhase.PHASE_C_REVERSE_DRIVE
    else:
        return ActivePhase.PHASE_D_CLOSING


# ---------------------------------------------------------------------------
# Day-4-5 telemetry window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Day45TelemetryWindow:
    """A 48-hour active-perturbation window for §6.

    Like Day12TelemetryWindow but the HVAC excitation has phase structure
    rather than uniform 10-min/hr fan mixing.
    """

    samples: tuple[FanHeatSample, ...]
    # The HVAC excitation derived from compressor and fan commands actually
    # issued to the equipment during each phase (per the Day-3 map plus
    # η_distribution from §4)
    hvac_excitation_monotonic_ns: np.ndarray
    q_sens_w: np.ndarray  # signed: negative during Phase A cooling drive
    m_lat_kg_per_s: np.ndarray  # signed: negative during Phase A dehumidification
    # Weather (same shape as Day12TelemetryWindow)
    weather_monotonic_ns: np.ndarray
    t_outdoor_c: np.ndarray
    rh_outdoor_pct: np.ndarray
    solar_global_w_per_m2: np.ndarray
    wind_speed_m_per_s: np.ndarray
    # Per-sample phase classification (computed at construction time so the
    # likelihood can index by phase quickly)
    phase_index: np.ndarray  # shape (N,), values 0..3 mapping to ActivePhase

    def __post_init__(self):
        n = len(self.samples)
        for name, arr in [
            ("hvac_excitation_monotonic_ns", self.hvac_excitation_monotonic_ns),
            ("q_sens_w", self.q_sens_w),
            ("m_lat_kg_per_s", self.m_lat_kg_per_s),
            ("weather_monotonic_ns", self.weather_monotonic_ns),
            ("t_outdoor_c", self.t_outdoor_c),
            ("rh_outdoor_pct", self.rh_outdoor_pct),
            ("solar_global_w_per_m2", self.solar_global_w_per_m2),
            ("wind_speed_m_per_s", self.wind_speed_m_per_s),
            ("phase_index", self.phase_index),
        ]:
            if arr.shape != (n,):
                raise ValueError(f"{name} length {arr.shape[0]} != samples {n}")

    @property
    def duration_s(self) -> float:
        return (self.samples[-1].monotonic_ns - self.samples[0].monotonic_ns) / 1e9

    def indices_for_phase(self, phase: ActivePhase) -> np.ndarray:
        """Return the telemetry-array indices that belong to a given phase."""
        target = list(ActivePhase).index(phase)
        return np.where(self.phase_index == target)[0]


def classify_samples_by_phase(
    samples: Sequence[FanHeatSample],
    phase_durations_s: tuple[float, float, float, float] | None = None,
) -> np.ndarray:
    """Compute the per-sample phase index given the protocol's boundary times.

    Args:
        samples: 1-Hz telemetry samples.
        phase_durations_s: (A, B, C, D) durations in seconds. Default is the
            spec values (18h, 6h, 18h, 6h). Tests may pass shortened durations.

    Returns: shape (N,) integer array.
    """
    if phase_durations_s is None:
        boundaries = _PHASE_BOUNDARIES_S
    else:
        boundaries = (
            phase_durations_s[0],
            phase_durations_s[0] + phase_durations_s[1],
            phase_durations_s[0] + phase_durations_s[1] + phase_durations_s[2],
            phase_durations_s[0] + phase_durations_s[1] + phase_durations_s[2] + phase_durations_s[3],
        )
    start_ns = samples[0].monotonic_ns
    indices = np.empty(len(samples), dtype=np.int64)
    for i, s in enumerate(samples):
        seconds = (s.monotonic_ns - start_ns) / 1e9
        phase = _phase_at(seconds, boundaries)
        indices[i] = list(ActivePhase).index(phase)
    return indices


# ---------------------------------------------------------------------------
# Phase-aware observation extraction (analog of §5 two-channel, adapted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseAwareObservations:
    """Observations extracted from a Day-4-5 window per §6.3 phase-aware
    likelihood structure."""

    # Phase A: continuous main-channel observations (no attic channel)
    phase_a_main_indices: np.ndarray
    phase_a_t_main_obs: np.ndarray
    phase_a_w_main_obs: np.ndarray

    # Phase B: full two-channel (matching §5's pattern)
    phase_b_attic_centers_idx: np.ndarray
    phase_b_t_attic_obs: np.ndarray
    phase_b_main_indices: np.ndarray
    phase_b_t_main_obs: np.ndarray
    phase_b_w_main_obs: np.ndarray

    # Phase C: two-channel but attic σ doubled (σ_T_attic_degraded)
    phase_c_attic_centers_idx: np.ndarray
    phase_c_t_attic_obs: np.ndarray
    phase_c_main_indices: np.ndarray
    phase_c_t_main_obs: np.ndarray
    phase_c_w_main_obs: np.ndarray

    # Phase D: full two-channel (matching Phase B)
    phase_d_attic_centers_idx: np.ndarray
    phase_d_t_attic_obs: np.ndarray
    phase_d_main_indices: np.ndarray
    phase_d_t_main_obs: np.ndarray
    phase_d_w_main_obs: np.ndarray


def extract_phase_aware_observations(
    window: Day45TelemetryWindow,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> PhaseAwareObservations:
    """Per §6.3: extract observations into the four phase-classified buckets,
    applying the channel-availability rules:

      - Phase A: continuous fan, no attic channel. Main-channel observations
        are taken at every sample.
      - Phase B: 1-fan-on-per-hour mixing. Standard §5 two-channel split
        (warmup → attic; post-warmup → main).
      - Phase C: 50/10 schedule. Attic channel degraded. Same split logic
        as Phase B but with σ_T_attic_degraded.
      - Phase D: same as Phase B.
    """
    samples = window.samples

    # Phase A: every sample is a valid main-channel observation
    phase_a_idx = window.indices_for_phase(ActivePhase.PHASE_A_COOLING_DRIVE)
    phase_a_t_obs = np.array(
        [samples[i].return_plenum.temperature_c for i in phase_a_idx]
    )
    phase_a_w_obs = []
    valid_phase_a_idx = []
    for i in phase_a_idx:
        t = samples[i].return_plenum.temperature_c
        rh = samples[i].return_plenum.relative_humidity_pct
        try:
            w = humidity_ratio(t, rh, p_atm_pa)
            phase_a_w_obs.append(w)
            valid_phase_a_idx.append(i)
        except ValueError:
            continue
    phase_a_main_indices = np.array(valid_phase_a_idx, dtype=np.int64)
    phase_a_t_main_obs = np.array(
        [samples[i].return_plenum.temperature_c for i in valid_phase_a_idx]
    )
    phase_a_w_main_obs = np.array(phase_a_w_obs)

    # Phases B, C, D: shared fan-on-interval extraction logic
    def extract_intervals(phase: ActivePhase) -> tuple[np.ndarray, ...]:
        """Return (attic_centers_idx, t_attic_obs, main_indices, t_main_obs, w_main_obs)."""
        phase_idx = window.indices_for_phase(phase)
        if phase_idx.size == 0:
            return (
                np.empty(0, dtype=np.int64),
                np.empty(0),
                np.empty(0, dtype=np.int64),
                np.empty(0),
                np.empty(0),
            )

        # Find fan-on intervals within the phase
        # Look at the per-sample fan_on flag in this phase's slice
        phase_start_idx = int(phase_idx[0])
        phase_end_idx_excl = int(phase_idx[-1]) + 1

        fan_on_intervals: list[tuple[int, int]] = []
        in_fan_on = False
        start = 0
        for i in range(phase_start_idx, phase_end_idx_excl):
            if samples[i].fan_on and not in_fan_on:
                start = i
                in_fan_on = True
            elif not samples[i].fan_on and in_fan_on:
                fan_on_intervals.append((start, i))
                in_fan_on = False
        if in_fan_on:
            fan_on_intervals.append((start, phase_end_idx_excl))

        attic_centers: list[int] = []
        attic_obs: list[float] = []
        main_idx: list[int] = []
        main_t: list[float] = []
        main_w: list[float] = []

        for fstart, fend in fan_on_intervals:
            fan_on_start_ns = samples[fstart].monotonic_ns
            warmup_end_ns = fan_on_start_ns + int(WARMUP_EXCLUSION_S * 1e9)
            warmup = [i for i in range(fstart, fend) if samples[i].monotonic_ns < warmup_end_ns]
            main = [i for i in range(fstart, fend) if samples[i].monotonic_ns >= warmup_end_ns]
            if not warmup or not main:
                continue
            # Attic observation: spatial-average across 12 terminals during warmup
            terminal_temps = [t.sht.temperature_c for i in warmup for t in samples[i].terminals]
            t_attic_obs_val = float(np.mean(terminal_temps))
            center_idx = warmup[len(warmup) // 2]
            attic_centers.append(center_idx)
            attic_obs.append(t_attic_obs_val)
            for i in main:
                t = samples[i].return_plenum.temperature_c
                rh = samples[i].return_plenum.relative_humidity_pct
                try:
                    w = humidity_ratio(t, rh, p_atm_pa)
                except ValueError:
                    continue
                main_idx.append(i)
                main_t.append(t)
                main_w.append(w)

        return (
            np.array(attic_centers, dtype=np.int64),
            np.array(attic_obs),
            np.array(main_idx, dtype=np.int64),
            np.array(main_t),
            np.array(main_w),
        )

    pb_atc_idx, pb_atc, pb_mi, pb_mt, pb_mw = extract_intervals(ActivePhase.PHASE_B_DECAY)
    pc_atc_idx, pc_atc, pc_mi, pc_mt, pc_mw = extract_intervals(ActivePhase.PHASE_C_REVERSE_DRIVE)
    pd_atc_idx, pd_atc, pd_mi, pd_mt, pd_mw = extract_intervals(ActivePhase.PHASE_D_CLOSING)

    return PhaseAwareObservations(
        phase_a_main_indices=phase_a_main_indices,
        phase_a_t_main_obs=phase_a_t_main_obs,
        phase_a_w_main_obs=phase_a_w_main_obs,
        phase_b_attic_centers_idx=pb_atc_idx,
        phase_b_t_attic_obs=pb_atc,
        phase_b_main_indices=pb_mi,
        phase_b_t_main_obs=pb_mt,
        phase_b_w_main_obs=pb_mw,
        phase_c_attic_centers_idx=pc_atc_idx,
        phase_c_t_attic_obs=pc_atc,
        phase_c_main_indices=pc_mi,
        phase_c_t_main_obs=pc_mt,
        phase_c_w_main_obs=pc_mw,
        phase_d_attic_centers_idx=pd_atc_idx,
        phase_d_t_attic_obs=pd_atc,
        phase_d_main_indices=pd_mi,
        phase_d_t_main_obs=pd_mt,
        phase_d_w_main_obs=pd_mw,
    )


# ---------------------------------------------------------------------------
# Phase-aware likelihood
# ---------------------------------------------------------------------------


def neg_log_likelihood_active(
    theta: np.ndarray,
    obs: PhaseAwareObservations,
    window: Day45TelemetryWindow,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    use_phase_d: bool = False,
) -> float:
    """Phase-aware -log L(θ | data) per §6.3.

    By default, Phase D is excluded so that the posterior derived from
    Phases A+B+C can be used to compute the §6.6 held-out residual. Set
    `use_phase_d=True` to include all four phases in the fit (used only
    when explicitly desired; the canonical §6 spec holds Phase D out).
    """
    hvac = HVACExcitation(
        monotonic_ns=window.hvac_excitation_monotonic_ns,
        q_sens_w=window.q_sens_w,
        m_lat_kg_per_s=window.m_lat_kg_per_s,
    )
    weather = WeatherSeries(
        monotonic_ns=window.weather_monotonic_ns,
        t_outdoor_c=window.t_outdoor_c,
        rh_outdoor_pct=window.rh_outdoor_pct,
        solar_global_w_per_m2=window.solar_global_w_per_m2,
        wind_speed_m_per_s=window.wind_speed_m_per_s,
    )

    trajectory = forward_chain.run(theta, hvac, weather, context)

    if (
        np.any(np.isnan(trajectory.t_main_c))
        or np.any(np.isnan(trajectory.w_main_kg_per_kg))
        or np.any(np.isnan(trajectory.t_attic_c))
    ):
        return 1e10

    chi2 = 0.0

    # Phase A: continuous main-channel
    if obs.phase_a_main_indices.size:
        t_pred = trajectory.t_main_c[obs.phase_a_main_indices]
        w_pred = trajectory.w_main_kg_per_kg[obs.phase_a_main_indices]
        chi2 += np.sum((obs.phase_a_t_main_obs - t_pred) ** 2) / (SIGMA_T_MAIN_C ** 2)
        chi2 += np.sum((obs.phase_a_w_main_obs - w_pred) ** 2) / (SIGMA_W ** 2)

    # Phase B: full two-channel
    if obs.phase_b_attic_centers_idx.size:
        t_attic_pred = trajectory.t_attic_c[obs.phase_b_attic_centers_idx]
        chi2 += np.sum((obs.phase_b_t_attic_obs - t_attic_pred) ** 2) / (SIGMA_T_ATTIC_C ** 2)
    if obs.phase_b_main_indices.size:
        t_pred = trajectory.t_main_c[obs.phase_b_main_indices]
        w_pred = trajectory.w_main_kg_per_kg[obs.phase_b_main_indices]
        chi2 += np.sum((obs.phase_b_t_main_obs - t_pred) ** 2) / (SIGMA_T_MAIN_C ** 2)
        chi2 += np.sum((obs.phase_b_w_main_obs - w_pred) ** 2) / (SIGMA_W ** 2)

    # Phase C: two-channel with degraded attic σ
    if obs.phase_c_attic_centers_idx.size:
        t_attic_pred = trajectory.t_attic_c[obs.phase_c_attic_centers_idx]
        chi2 += np.sum((obs.phase_c_t_attic_obs - t_attic_pred) ** 2) / (
            SIGMA_T_ATTIC_DEGRADED_C ** 2
        )
    if obs.phase_c_main_indices.size:
        t_pred = trajectory.t_main_c[obs.phase_c_main_indices]
        w_pred = trajectory.w_main_kg_per_kg[obs.phase_c_main_indices]
        chi2 += np.sum((obs.phase_c_t_main_obs - t_pred) ** 2) / (SIGMA_T_MAIN_C ** 2)
        chi2 += np.sum((obs.phase_c_w_main_obs - w_pred) ** 2) / (SIGMA_W ** 2)

    # Phase D: held out by default per §6.6 architectural purpose
    if use_phase_d:
        if obs.phase_d_attic_centers_idx.size:
            t_attic_pred = trajectory.t_attic_c[obs.phase_d_attic_centers_idx]
            chi2 += np.sum((obs.phase_d_t_attic_obs - t_attic_pred) ** 2) / (
                SIGMA_T_ATTIC_C ** 2
            )
        if obs.phase_d_main_indices.size:
            t_pred = trajectory.t_main_c[obs.phase_d_main_indices]
            w_pred = trajectory.w_main_kg_per_kg[obs.phase_d_main_indices]
            chi2 += np.sum((obs.phase_d_t_main_obs - t_pred) ** 2) / (SIGMA_T_MAIN_C ** 2)
            chi2 += np.sum((obs.phase_d_w_main_obs - w_pred) ** 2) / (SIGMA_W ** 2)

    return 0.5 * chi2


def neg_log_prior(theta: np.ndarray, prior: Prior6D) -> float:
    """Same as §5; reproduced here for clarity rather than cross-imported."""
    delta = theta - prior.mean
    cov_inv = np.linalg.inv(prior.covariance)
    return 0.5 * delta @ cov_inv @ delta


def neg_log_posterior_active(
    theta: np.ndarray,
    obs: PhaseAwareObservations,
    window: Day45TelemetryWindow,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    prior: Prior6D,
    use_phase_d: bool = False,
) -> float:
    return (
        neg_log_likelihood_active(theta, obs, window, forward_chain, context, use_phase_d)
        + neg_log_prior(theta, prior)
    )


# ---------------------------------------------------------------------------
# §6.6 Phase D held-out residual
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseDResidualReport:
    """The §6.6 architectural-purpose validation against held-out Phase D data.

    The trajectory predicted by the posterior derived from Phases A+B+C is
    compared against observed Phase D telemetry. A residual exceeding the
    spec threshold (5% relative on time-averaged indoor T or W) flags the
    posterior for review.
    """

    t_main_time_avg_residual_relative: float
    w_main_time_avg_residual_relative: float
    flagged: bool
    threshold_used: float
    num_phase_d_samples: int


def compute_phase_d_residual(
    posterior_mean: np.ndarray,
    obs: PhaseAwareObservations,
    window: Day45TelemetryWindow,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    threshold: float = PHASE_D_RESIDUAL_TOLERANCE,
) -> PhaseDResidualReport:
    """Per §6.6: predict from the posterior, compare against held-out Phase D."""
    if obs.phase_d_main_indices.size == 0:
        return PhaseDResidualReport(
            t_main_time_avg_residual_relative=float("nan"),
            w_main_time_avg_residual_relative=float("nan"),
            flagged=False,
            threshold_used=threshold,
            num_phase_d_samples=0,
        )

    hvac = HVACExcitation(
        monotonic_ns=window.hvac_excitation_monotonic_ns,
        q_sens_w=window.q_sens_w,
        m_lat_kg_per_s=window.m_lat_kg_per_s,
    )
    weather = WeatherSeries(
        monotonic_ns=window.weather_monotonic_ns,
        t_outdoor_c=window.t_outdoor_c,
        rh_outdoor_pct=window.rh_outdoor_pct,
        solar_global_w_per_m2=window.solar_global_w_per_m2,
        wind_speed_m_per_s=window.wind_speed_m_per_s,
    )
    trajectory = forward_chain.run(posterior_mean, hvac, weather, context)

    t_pred = trajectory.t_main_c[obs.phase_d_main_indices]
    w_pred = trajectory.w_main_kg_per_kg[obs.phase_d_main_indices]

    t_obs_avg = float(np.mean(obs.phase_d_t_main_obs))
    t_pred_avg = float(np.mean(t_pred))
    w_obs_avg = float(np.mean(obs.phase_d_w_main_obs))
    w_pred_avg = float(np.mean(w_pred))

    if abs(t_obs_avg) < 1e-6:
        t_residual_rel = float("nan")
    else:
        t_residual_rel = abs(t_pred_avg - t_obs_avg) / abs(t_obs_avg)
    if abs(w_obs_avg) < 1e-9:
        w_residual_rel = float("nan")
    else:
        w_residual_rel = abs(w_pred_avg - w_obs_avg) / abs(w_obs_avg)

    flagged = (t_residual_rel > threshold) or (w_residual_rel > threshold)

    return PhaseDResidualReport(
        t_main_time_avg_residual_relative=t_residual_rel,
        w_main_time_avg_residual_relative=w_residual_rel,
        flagged=flagged,
        threshold_used=threshold,
        num_phase_d_samples=int(obs.phase_d_main_indices.size),
    )


# ---------------------------------------------------------------------------
# §6 Laplace fit — analog of §5's but with phase-aware likelihood
# ---------------------------------------------------------------------------


def run_active_laplace_fit(
    obs: PhaseAwareObservations,
    window: Day45TelemetryWindow,
    prior: Prior6D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    num_restarts: int = LAPLACE_NUM_RESTARTS,
    rng_seed: int = 42,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> LaplaceResult:
    """Laplace fit using the phase-aware likelihood, holding out Phase D.

    Structurally identical to `passive_fit.run_laplace_fit` but with the
    §6.3 likelihood and Phase D excluded from the fit by default. The
    prior is the §5 end-of-Day-2 posterior per §6.3.
    """
    rng = np.random.default_rng(rng_seed)
    n_params = NUM_CANONICAL_PARAMETERS

    def objective(theta: np.ndarray) -> float:
        return neg_log_posterior_active(
            theta, obs, window, forward_chain, context, prior, use_phase_d=False
        )

    restart_modes = np.zeros((num_restarts, n_params))
    restart_log_posteriors = np.zeros(num_restarts)
    converged_flags = np.zeros(num_restarts, dtype=bool)

    cholesky_prior = np.linalg.cholesky(prior.covariance)
    positive_floors = {
        "R_eff": 0.5,
        "C_house": 1e5,
        "cfm50": 100.0,
        "C_w": 1.0,
        "F_slab": 0.0,
        "ceiling_coupling_factor": 0.0,
    }

    for r in range(num_restarts):
        if r == 0:
            start = prior.mean.copy()
        else:
            xi = rng.standard_normal(n_params)
            start = prior.mean + (cholesky_prior @ xi) / 6.0

        bounds = [
            (
                prior.mean[i] - 3.0 * prior.marginal_sigmas[i],
                prior.mean[i] + 3.0 * prior.marginal_sigmas[i],
            )
            for i in range(n_params)
        ]
        for i, name in enumerate(CANONICAL_PARAMETER_NAMES):
            lower = max(positive_floors.get(name, 0.0), bounds[i][0])
            bounds[i] = (lower, bounds[i][1])

        result = minimize(
            objective,
            x0=start,
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": 1e-9, "gtol": 1e-7, "maxiter": 200},
        )
        restart_modes[r] = result.x
        restart_log_posteriors[r] = -result.fun
        converged_flags[r] = bool(result.success)

    optimizer_converged_all_restarts = bool(np.all(converged_flags))
    if not optimizer_converged_all_restarts:
        raise LaplaceFitFailed(
            "Per §6.6 (cross-reference to §5.7): one or more L-BFGS-B "
            f"restarts did not converge (success flags: {converged_flags.tolist()}). "
            "Per INV-FIT45-6, no Day5Posterior emitted."
        )

    prior_sigmas = prior.marginal_sigmas
    mode_diffs = np.std(restart_modes, axis=0)
    mode_agreement_passed = bool(
        np.all(mode_diffs < mode_agreement_fraction * prior_sigmas)
    )
    if not mode_agreement_passed:
        raise LaplaceFitFailed(
            "Per §6.6 mode-agreement check: restart-to-restart parameter "
            f"disagreement exceeds {mode_agreement_fraction:.2g} × prior σ "
            "on at least one parameter. Per INV-FIT45-6, no Day5Posterior emitted."
        )

    best_restart = int(np.argmax(restart_log_posteriors))
    mode = restart_modes[best_restart]

    hessian = finite_difference_hessian(objective, mode)
    eigenvalues = np.linalg.eigvalsh(hessian)
    positive_definite = bool(np.all(eigenvalues > 0))
    if not positive_definite:
        raise LaplaceFitFailed(
            f"Per §6.6 Hessian positive-definiteness check: at least one "
            f"eigenvalue ≤ 0 (eigenvalues: {eigenvalues.tolist()}). "
            "Per INV-FIT45-6, no Day5Posterior emitted."
        )

    condition_number = float(np.max(eigenvalues) / np.min(eigenvalues))
    covariance = np.linalg.inv(hessian)
    covariance = 0.5 * (covariance + covariance.T)

    # KL divergence per parameter (against the §5 posterior used as §6 prior)
    n = mode.shape[0]
    kl = np.empty(n)
    for i in range(n):
        sigma_post_sq = covariance[i, i]
        sigma_prior_sq = prior.covariance[i, i]
        mu_post = mode[i]
        mu_prior = prior.mean[i]
        kl[i] = 0.5 * (
            np.log(sigma_prior_sq / sigma_post_sq)
            + (sigma_post_sq + (mu_post - mu_prior) ** 2) / sigma_prior_sq
            - 1
        )

    return LaplaceResult(
        posterior_mean=mode,
        posterior_covariance=covariance,
        hessian_at_mode=hessian,
        hessian_eigenvalues=eigenvalues,
        hessian_condition_number=condition_number,
        restart_modes=restart_modes,
        restart_log_posteriors=restart_log_posteriors,
        mode_agreement_passed=mode_agreement_passed,
        hessian_positive_definite=positive_definite,
        optimizer_converged_all_restarts=optimizer_converged_all_restarts,
        posterior_prior_kl_divergence_per_param=kl,
    )


# ---------------------------------------------------------------------------
# End-to-end §6 orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveFitResult:
    """End-to-end output of `run_active_batch_fit`."""

    laplace: LaplaceResult
    phase_d_residual: PhaseDResidualReport
    day5_posterior: Day5Posterior
    signed_record: SignedRecord
    inclusion_proof: LogInclusionProof
    threshold_attestation: ThresholdAttestation


def run_active_batch_fit(
    window: Day45TelemetryWindow,
    day2_posterior_as_prior: Prior6D,
    day2_posterior_record_hash: str,
    day3_map_record_hash: str,
    home_id: str,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> ActiveFitResult:
    """Per §6 end-to-end:

      1. Verify prerequisites: §5 Day2Posterior + Day-3 (Capacity, EER)
         map records both exist (INV-FIT45-1, INV-FIT45-2).
      2. Extract phase-aware observations per §6.3.
      3. Run the Laplace fit on Phases A+B+C with §5 posterior as prior
         (§6.5, INV-FIT45-7 — η_distribution held at §4 Day-1 value).
      4. Compute Phase D held-out residual per §6.6.
      5. Build §8 identifiability report from the Laplace output.
      6. Construct the Day5Posterior record (§6.7).
      7. Sign and log via §12 with AttestationMoment.ENVELOPE_HALF_FINAL
         per INV-SIGN12-3 — this is the *envelope half, final signing*
         that supersedes the §5 envelope-half-initial.

    Raises:
      LaplaceFitFailed if any §6.6 convergence or quality diagnostic
      fails (INV-FIT45-6).
      ValueError if INV-FIT45-1 or INV-FIT45-2 prerequisites are missing.
    """
    if not day2_posterior_record_hash:
        raise ValueError(
            "INV-FIT45-1: §6 MUST NOT run without a valid Day2Posterior "
            "record from §5 as the prior. Caller must supply the hash."
        )
    if not day3_map_record_hash:
        raise ValueError(
            "INV-FIT45-2: §6 MUST NOT run without a valid Day-3-signed "
            "(Capacity, EER) operating-point map. Caller must supply the hash."
        )

    obs = extract_phase_aware_observations(window, p_atm_pa)

    laplace = run_active_laplace_fit(
        obs,
        window,
        day2_posterior_as_prior,
        forward_chain,
        context,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    phase_d_residual = compute_phase_d_residual(
        laplace.posterior_mean, obs, window, forward_chain, context
    )

    id_report = build_identifiability_report(
        laplace, day2_posterior_as_prior, protocol="§6_day5_active_compounded"
    )

    posterior_common = PosteriorCommon(
        home_id=home_id,
        parameter_names=CANONICAL_PARAMETER_NAMES,
        posterior_mean=tuple(laplace.posterior_mean.tolist()),
        posterior_covariance=tuple(
            tuple(row) for row in laplace.posterior_covariance.tolist()
        ),
        prior_provenance_descriptor=day2_posterior_as_prior.provenance_descriptor,
        prior_hash=day2_posterior_as_prior.provenance_hash,
        monotonic_timestamp_ns=window.samples[-1].monotonic_ns,
    )

    excitation_record = {
        "phase_a_duration_s": PHASE_A_DURATION_S,
        "phase_b_duration_s": PHASE_B_DURATION_S,
        "phase_c_duration_s": PHASE_C_DURATION_S,
        "phase_d_duration_s": PHASE_D_DURATION_S,
        "phase_d_held_out": True,
        "sigma_T_attic_degraded_used_for_phase_c": SIGMA_T_ATTIC_DEGRADED_C,
        "eta_distribution_held_at_day1_value": True,  # INV-FIT45-7
    }

    day5 = Day5Posterior(
        common=posterior_common,
        identifiability_report=id_report,
        day2_posterior_hash=day2_posterior_record_hash,
        day3_map_hash=day3_map_record_hash,
        excitation_protocol_record=excitation_record,
    )

    signable = {
        "record_type": day5.record_type,
        "day2_posterior_hash": day5.day2_posterior_hash,
        "day3_map_hash": day5.day3_map_hash,
        "home_id": day5.common.home_id,
        "parameter_names": list(day5.common.parameter_names),
        "posterior_mean": list(day5.common.posterior_mean),
        "posterior_covariance": [list(row) for row in day5.common.posterior_covariance],
        "prior_provenance_descriptor": day5.common.prior_provenance_descriptor,
        "prior_hash": day5.common.prior_hash,
        "monotonic_timestamp_ns": day5.common.monotonic_timestamp_ns,
        "excitation_protocol_record": excitation_record,
        "identifiability_report": {
            "protocol": id_report.protocol,
            "per_parameter": id_report.per_parameter,
            "hessian_spectrum": id_report.hessian_spectrum,
            "summary": id_report.summary,
        },
        "convergence_diagnostics": {
            "optimizer_converged_all_restarts": laplace.optimizer_converged_all_restarts,
            "mode_agreement_passed": laplace.mode_agreement_passed,
            "hessian_positive_definite": laplace.hessian_positive_definite,
            "hessian_condition_number": laplace.hessian_condition_number,
            "restart_log_posteriors": laplace.restart_log_posteriors.tolist(),
        },
        "phase_d_residual": {
            "t_main_time_avg_residual_relative": phase_d_residual.t_main_time_avg_residual_relative,
            "w_main_time_avg_residual_relative": phase_d_residual.w_main_time_avg_residual_relative,
            "flagged": phase_d_residual.flagged,
            "threshold_used": phase_d_residual.threshold_used,
            "num_phase_d_samples": phase_d_residual.num_phase_d_samples,
        },
    }

    signed = sign_record(signable)
    inclusion = commit_to_log(signed)
    # INV-SIGN12-3: AttestationMoment.ENVELOPE_HALF_FINAL — supersedes
    # the §5 envelope-half-initial signing per §2.3
    attestation = threshold_attest(signable, AttestationMoment.ENVELOPE_HALF_FINAL)

    return ActiveFitResult(
        laplace=laplace,
        phase_d_residual=phase_d_residual,
        day5_posterior=day5,
        signed_record=signed,
        inclusion_proof=inclusion,
        threshold_attestation=attestation,
    )
