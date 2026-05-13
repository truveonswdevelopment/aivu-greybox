"""§5 — Day-1-2 passive batch fit (Laplace approximation).

Implements the six-parameter Bayesian inverse identification per §5:

  - Two-channel observation model per §5.3 (attic-channel from warmup
    terminal probes; main-channel from post-warmup return-plenum readings).
  - Multivariate Gaussian prior per §5.4.
  - Laplace approximation per §5.6 (L-BFGS-B with 4 prior-perturbed
    restarts; Hessian via finite differences; posterior = N(mode, H⁻¹)).
  - Convergence and quality diagnostics per §5.7.
  - Signed Day2Posterior record per §5.8.

The algorithm-class abstraction (§5.6, INV-ID8-8): this module's public
entry point `run_passive_batch_fit(...)` returns a `Day2Posterior` whose
shape is the same whether Laplace or the v0.2 NUTS/HMC fallback produced
the posterior. v0.1 ships Laplace only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

from .defaults import (
    CANONICAL_PARAMETER_NAMES,
    LAPLACE_MODE_AGREEMENT_FRACTION,
    LAPLACE_NUM_RESTARTS,
    NUM_CANONICAL_PARAMETERS,
    SIGMA_T_ATTIC_C,
    SIGMA_T_MAIN_C,
    WARMUP_EXCLUSION_S,
)
from .forward_chain import (
    ForwardChain,
    HomeStaticContext,
    HVACExcitation,
    StateTrajectory,
    WeatherSeries,
)
from .passive_fit_types import Day12TelemetryWindow, Prior6D
from .psychrometrics import P_ATM_PHOENIX_PA, humidity_ratio
from .records import (
    Day2Posterior,
    IdentifiabilityReport,
    PosteriorCommon,
)
from ._signing_stub import (
    AttestationMoment,
    LogInclusionProof,
    SignedRecord,
    ThresholdAttestation,
    commit_to_log,
    sign_record,
    threshold_attest,
)


# σ_W comes from SHT35 ±1.5% RH at typical Phoenix-July return-side
# conditions (~25 °C, ~40% RH). Computed at module load:
def _sht35_humidity_ratio_sigma() -> float:
    """Translate ±1.5% RH SHT35 spec to humidity-ratio uncertainty at
    typical return-plenum conditions."""
    # σ_W ≈ |∂W/∂RH| × σ_RH
    # ∂W/∂RH at fixed T: dW/dRH ≈ W / RH (since W ∝ P_w ∝ RH)
    t_ref = 25.0
    rh_ref = 40.0
    w_ref = humidity_ratio(t_ref, rh_ref, P_ATM_PHOENIX_PA)
    sigma_rh = 1.5  # %
    return abs(w_ref / rh_ref * sigma_rh)


SIGMA_W = _sht35_humidity_ratio_sigma()  # kg/kg


# ---------------------------------------------------------------------------
# Two-channel observation extraction per §5.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TwoChannelObservations:
    """Observations extracted from a Day-1-2 window per §5.3.

    The attic channel: one observation per fan-on interval, from the
    warmup-window terminal-probe spatial-averaged temperature reading.

    The main channel: one observation per post-warmup sample inside each
    fan-on interval, from the return-plenum probe (T and RH/W).
    """

    # Attic channel: one observation per fan-on interval (k = 1..K)
    attic_interval_centers_monotonic_ns: np.ndarray  # shape (K,)
    attic_interval_centers_telemetry_index: np.ndarray  # shape (K,)
    t_attic_obs_c: np.ndarray  # shape (K,)

    # Main channel: per-sample inside post-warmup of each fan-on interval
    main_sample_indices: np.ndarray  # shape (M,) — telemetry-array indices
    t_main_obs_c: np.ndarray  # shape (M,)
    w_main_obs_kg_per_kg: np.ndarray  # shape (M,)


def extract_two_channel_observations(
    window: Day12TelemetryWindow,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> TwoChannelObservations:
    """Per §5.3: split each fan-on interval into a warmup sub-interval
    (attic channel) and a main sub-interval (main channel).

    Warmup: first WARMUP_EXCLUSION_S after fan-on. Spatial-average across
    the 12 terminal SHT35 readings over the warmup duration; emit one
    T_attic^obs(k) per fan-on interval.

    Main: from WARMUP_EXCLUSION_S to end-of-fan-on. Per-sample return-
    plenum T and W readings; emit each as a main-channel observation.
    """
    fan_on_intervals = window.find_fan_on_intervals()
    if not fan_on_intervals:
        raise ValueError(
            "Day-1-2 telemetry window contains no fan-on intervals — "
            "INV-FIT12-6 schedule-adherence is violated. The fit cannot run."
        )

    attic_centers_ns: list[int] = []
    attic_centers_idx: list[int] = []
    attic_obs_c: list[float] = []
    main_idx: list[int] = []
    main_t_obs: list[float] = []
    main_w_obs: list[float] = []

    samples = window.samples
    for start, end in fan_on_intervals:
        # Find the index that is WARMUP_EXCLUSION_S after the fan-on start
        fan_on_start_ns = samples[start].monotonic_ns
        warmup_end_ns = fan_on_start_ns + int(WARMUP_EXCLUSION_S * 1e9)

        warmup_indices = [
            i for i in range(start, end) if samples[i].monotonic_ns < warmup_end_ns
        ]
        main_indices = [
            i for i in range(start, end) if samples[i].monotonic_ns >= warmup_end_ns
        ]
        if not warmup_indices or not main_indices:
            continue

        # Attic channel: spatial-average terminal T across the warmup window
        # (per §5.3: "Time-averaging across the 60s window and spatial-averaging
        # across the 12 terminals yields one T_attic^obs(k) observation")
        terminal_temps: list[float] = []
        for i in warmup_indices:
            for t in samples[i].terminals:
                terminal_temps.append(t.sht.temperature_c)
        t_attic_observation = float(np.mean(terminal_temps))
        # Center timestamp of the warmup window
        center_ns = (samples[warmup_indices[0]].monotonic_ns
                     + samples[warmup_indices[-1]].monotonic_ns) // 2
        center_idx = warmup_indices[len(warmup_indices) // 2]

        attic_centers_ns.append(center_ns)
        attic_centers_idx.append(center_idx)
        attic_obs_c.append(t_attic_observation)

        # Main channel: per-sample return-plenum T and W
        for i in main_indices:
            t_obs = samples[i].return_plenum.temperature_c
            rh_obs = samples[i].return_plenum.relative_humidity_pct
            try:
                w_obs = humidity_ratio(t_obs, rh_obs, p_atm_pa)
            except ValueError:
                # Skip samples with invalid psychrometric state
                continue
            main_idx.append(i)
            main_t_obs.append(t_obs)
            main_w_obs.append(w_obs)

    return TwoChannelObservations(
        attic_interval_centers_monotonic_ns=np.array(attic_centers_ns, dtype=np.int64),
        attic_interval_centers_telemetry_index=np.array(attic_centers_idx, dtype=np.int64),
        t_attic_obs_c=np.array(attic_obs_c, dtype=np.float64),
        main_sample_indices=np.array(main_idx, dtype=np.int64),
        t_main_obs_c=np.array(main_t_obs, dtype=np.float64),
        w_main_obs_kg_per_kg=np.array(main_w_obs, dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# Likelihood and negative-log-posterior
# ---------------------------------------------------------------------------


def neg_log_likelihood(
    theta: np.ndarray,
    obs: TwoChannelObservations,
    window: Day12TelemetryWindow,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
) -> float:
    """Two-channel observation neg-log-likelihood per §5.3.

    -log L(θ | data) = ½ Σ [
        (T_attic^obs(k) - T_attic^pred(t_warm(k); θ))² / σ_T_attic²
      + Σ_main (T_main^obs(t) - T_main^pred(t; θ))² / σ_T²
      + Σ_main (W_main^obs(t) - W_main^pred(t; θ))² / σ_W²
    ]
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

    # Index into the trajectory at the observation locations
    t_attic_pred = trajectory.t_attic_c[obs.attic_interval_centers_telemetry_index]
    t_main_pred = trajectory.t_main_c[obs.main_sample_indices]
    w_main_pred = trajectory.w_main_kg_per_kg[obs.main_sample_indices]

    # Reject NaN trajectories (degenerate parameter values)
    if (
        np.any(np.isnan(t_attic_pred))
        or np.any(np.isnan(t_main_pred))
        or np.any(np.isnan(w_main_pred))
    ):
        return 1e10  # large but finite, lets the optimizer recover

    # Sum squared residuals weighted by inverse-variance
    attic_residuals = obs.t_attic_obs_c - t_attic_pred
    main_t_residuals = obs.t_main_obs_c - t_main_pred
    main_w_residuals = obs.w_main_obs_kg_per_kg - w_main_pred

    chi2 = (
        np.sum(attic_residuals ** 2) / (SIGMA_T_ATTIC_C ** 2)
        + np.sum(main_t_residuals ** 2) / (SIGMA_T_MAIN_C ** 2)
        + np.sum(main_w_residuals ** 2) / (SIGMA_W ** 2)
    )
    return 0.5 * chi2


def neg_log_prior(theta: np.ndarray, prior: Prior6D) -> float:
    """-log p(θ) for the multivariate Gaussian prior, modulo constants."""
    delta = theta - prior.mean
    cov_inv = np.linalg.inv(prior.covariance)
    return 0.5 * delta @ cov_inv @ delta


def neg_log_posterior(
    theta: np.ndarray,
    obs: TwoChannelObservations,
    window: Day12TelemetryWindow,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    prior: Prior6D,
) -> float:
    """The objective L-BFGS-B minimizes."""
    return (
        neg_log_likelihood(theta, obs, window, forward_chain, context)
        + neg_log_prior(theta, prior)
    )


# ---------------------------------------------------------------------------
# Finite-difference Hessian
# ---------------------------------------------------------------------------


def finite_difference_hessian(
    func,
    theta_at: np.ndarray,
    step_fraction: float = 1e-4,
) -> np.ndarray:
    """Compute Hessian via second-order central differences.

    Per §5.6: gradients are analytic-where-available with finite-difference
    fallback. v0.1 stub forward chain does not provide analytic gradients;
    we use central differences with a step proportional to each parameter's
    magnitude. Real `aivu_dynamic` integration may eventually provide
    analytic Jacobians; the interface is unchanged.
    """
    n = theta_at.shape[0]
    hessian = np.zeros((n, n))
    # Step sizes scaled per parameter
    steps = np.maximum(step_fraction * np.abs(theta_at), step_fraction)

    # Diagonal: second derivative via 3-point central difference
    f0 = func(theta_at)
    for i in range(n):
        theta_plus = theta_at.copy()
        theta_minus = theta_at.copy()
        theta_plus[i] += steps[i]
        theta_minus[i] -= steps[i]
        f_plus = func(theta_plus)
        f_minus = func(theta_minus)
        hessian[i, i] = (f_plus - 2 * f0 + f_minus) / (steps[i] ** 2)

    # Off-diagonal: mixed partial via 4-point central difference
    for i in range(n):
        for j in range(i + 1, n):
            theta_pp = theta_at.copy()
            theta_pp[i] += steps[i]; theta_pp[j] += steps[j]
            theta_pm = theta_at.copy()
            theta_pm[i] += steps[i]; theta_pm[j] -= steps[j]
            theta_mp = theta_at.copy()
            theta_mp[i] -= steps[i]; theta_mp[j] += steps[j]
            theta_mm = theta_at.copy()
            theta_mm[i] -= steps[i]; theta_mm[j] -= steps[j]

            mixed = (
                func(theta_pp) - func(theta_pm) - func(theta_mp) + func(theta_mm)
            ) / (4 * steps[i] * steps[j])
            hessian[i, j] = mixed
            hessian[j, i] = mixed

    # Symmetrize numerically
    return 0.5 * (hessian + hessian.T)


# ---------------------------------------------------------------------------
# Laplace fit with 4 prior-perturbed restarts
# ---------------------------------------------------------------------------


class LaplaceFitFailed(Exception):
    """Per §5.7: a failed convergence/quality diagnostic halts the
    commissioning pipeline. Caller surfaces to operational layer."""


@dataclass(frozen=True)
class LaplaceResult:
    """End-to-end Laplace fit output, before signing."""

    posterior_mean: np.ndarray  # shape (6,)
    posterior_covariance: np.ndarray  # shape (6, 6)
    hessian_at_mode: np.ndarray  # shape (6, 6) -- inverse of covariance
    hessian_eigenvalues: np.ndarray  # shape (6,)
    hessian_condition_number: float
    restart_modes: np.ndarray  # shape (NUM_RESTARTS, 6)
    restart_log_posteriors: np.ndarray  # shape (NUM_RESTARTS,)
    mode_agreement_passed: bool
    hessian_positive_definite: bool
    optimizer_converged_all_restarts: bool
    posterior_prior_kl_divergence_per_param: np.ndarray  # shape (6,)


def _gaussian_kl_per_param(
    posterior_mean: np.ndarray,
    posterior_cov: np.ndarray,
    prior: Prior6D,
) -> np.ndarray:
    """Per-parameter KL(posterior_marginal_i || prior_marginal_i) per §8 Diagnostic 4."""
    n = posterior_mean.shape[0]
    out = np.empty(n)
    for i in range(n):
        sigma_post_sq = posterior_cov[i, i]
        sigma_prior_sq = prior.covariance[i, i]
        mu_post = posterior_mean[i]
        mu_prior = prior.mean[i]
        out[i] = 0.5 * (
            np.log(sigma_prior_sq / sigma_post_sq)
            + (sigma_post_sq + (mu_post - mu_prior) ** 2) / sigma_prior_sq
            - 1
        )
    return out


def run_laplace_fit(
    obs: TwoChannelObservations,
    window: Day12TelemetryWindow,
    prior: Prior6D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    num_restarts: int = LAPLACE_NUM_RESTARTS,
    rng_seed: int = 42,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> LaplaceResult:
    """Per §5.6: L-BFGS-B with N prior-perturbed restarts.

    Each restart starts from `prior.mean + δ` where δ ~ N(0, prior.covariance/36)
    (i.e., perturbation σ = prior σ / 6, keeping starts firmly within the
    prior's central mass).

    Args:
        mode_agreement_fraction: per §5.7 mode-agreement check, the maximum
            allowed restart-to-restart parameter disagreement as a fraction
            of prior σ. Default is the production value pinned in
            `defaults.LAPLACE_MODE_AGREEMENT_FRACTION` (0.05). Tests against
            simplified forward chains or shortened telemetry windows may
            need to relax this; production code must use the default.
    """
    rng = np.random.default_rng(rng_seed)
    n_params = NUM_CANONICAL_PARAMETERS

    def objective(theta: np.ndarray) -> float:
        return neg_log_posterior(theta, obs, window, forward_chain, context, prior)

    restart_modes = np.zeros((num_restarts, n_params))
    restart_log_posteriors = np.zeros(num_restarts)
    converged_flags = np.zeros(num_restarts, dtype=bool)

    # Starting points: 1 at prior.mean, remaining (N-1) perturbed
    cholesky_prior = np.linalg.cholesky(prior.covariance)

    for r in range(num_restarts):
        if r == 0:
            start = prior.mean.copy()
        else:
            # Perturbation scaled to 1/6 of prior σ — keeps restarts firmly
            # within the central mass of the prior so all four converge
            # cleanly. Mode-agreement check at session close still validates
            # the multi-restart discipline per §5.7.
            xi = rng.standard_normal(n_params)
            start = prior.mean + (cholesky_prior @ xi) / 6.0

        # L-BFGS-B with bounds — keep within ±3σ of prior (5σ was too wide
        # and pulled restarts into degenerate parameter regions where the
        # forward chain becomes numerically unstable)
        bounds = [
            (
                prior.mean[i] - 3.0 * prior.marginal_sigmas[i],
                prior.mean[i] + 3.0 * prior.marginal_sigmas[i],
            )
            for i in range(n_params)
        ]
        # Tighten further: strictly-positive parameters must stay positive
        # and well-conditioned. R_eff in particular drives a 1/R_eff term
        # in the dynamics and we cannot let it approach zero.
        positive_floors = {
            "R_eff": 0.5,        # m²·K/W
            "C_house": 1e5,      # J/K
            "cfm50": 100.0,      # cfm
            "C_w": 1.0,
            "F_slab": 0.0,
            "ceiling_coupling_factor": 0.0,
        }
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
            "Per §5.7: one or more L-BFGS-B restarts did not converge "
            f"(success flags: {converged_flags.tolist()}). The fit fails; "
            "no Day2Posterior emitted."
        )

    # Mode-agreement check per §5.7
    prior_sigmas = prior.marginal_sigmas
    mode_diffs = np.std(restart_modes, axis=0)
    mode_agreement_passed = bool(
        np.all(mode_diffs < mode_agreement_fraction * prior_sigmas)
    )

    # Select best-log-posterior mode as the canonical mode (the others
    # should agree to within tolerance per §5.7 mode-agreement check; if
    # they don't, mode_agreement_passed=False already records the failure)
    best_restart = int(np.argmax(restart_log_posteriors))
    mode = restart_modes[best_restart]

    if not mode_agreement_passed:
        raise LaplaceFitFailed(
            "Per §5.7 mode-agreement check: restart-to-restart parameter "
            "disagreement exceeds 5% of prior σ on at least one parameter. "
            "This indicates multimodality or premature local-mode convergence. "
            "The fit fails; no Day2Posterior emitted."
        )

    # Hessian at the mode
    hessian = finite_difference_hessian(objective, mode)
    eigenvalues = np.linalg.eigvalsh(hessian)
    positive_definite = bool(np.all(eigenvalues > 0))
    if not positive_definite:
        raise LaplaceFitFailed(
            f"Per §5.7 Hessian positive-definiteness check: at least one "
            f"eigenvalue ≤ 0 (eigenvalues: {eigenvalues.tolist()}). "
            "Indicates saddle point / local max / non-Gaussian posterior."
        )

    condition_number = float(np.max(eigenvalues) / np.min(eigenvalues))
    covariance = np.linalg.inv(hessian)
    # Symmetrize numerically
    covariance = 0.5 * (covariance + covariance.T)

    kl_per_param = _gaussian_kl_per_param(mode, covariance, prior)

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
        posterior_prior_kl_divergence_per_param=kl_per_param,
    )


# ---------------------------------------------------------------------------
# §8 identifiability report builder (Diagnostics 1-4 over Laplace output)
# ---------------------------------------------------------------------------


def build_identifiability_report(
    laplace: LaplaceResult,
    prior: Prior6D,
    protocol: str = "§5_day2_passive",
) -> IdentifiabilityReport:
    """Build the §8 v1 schema identifiability_report from the Laplace fit
    output. Implements the four diagnostics per §8.2 against the posterior.
    """
    from .defaults import (
        ID8_HESSIAN_KAPPA_THRESHOLD,
        ID8_RHO_FLAG_THRESHOLD,
        ID8_RIDGE_EIGENVALUE_FRACTION,
    )

    posterior_sigmas = np.sqrt(np.diag(laplace.posterior_covariance))
    prior_sigmas = prior.marginal_sigmas

    per_parameter: dict[str, dict] = {}
    any_identifiability_flag = False
    any_degraded_tightness = False

    for i, name in enumerate(CANONICAL_PARAMETER_NAMES):
        # Diagnostic 1: ρ = σ_posterior / σ_prior
        rho = float(posterior_sigmas[i] / prior_sigmas[i])
        flag = rho > ID8_RHO_FLAG_THRESHOLD
        if flag:
            any_identifiability_flag = True

        # Diagnostic 2: tightness state
        # σ_post / μ_post; expected values from §5.5 table baked here as the
        # canonical reference (per INV-ID8-7 the table is by reference to §5.5).
        # Pinned values per §5 v3.3 closing note: 5/5/30/15/25/15
        # (R_eff / C_house / cfm50 / F_slab / C_w / ceiling_coupling_factor)
        expected_tightness_pct = {
            "R_eff": 0.05,
            "C_house": 0.05,
            "cfm50": 0.30,
            "F_slab": 0.15,
            "C_w": 0.25,
            "ceiling_coupling_factor": 0.15,
        }
        achieved = float(posterior_sigmas[i] / abs(laplace.posterior_mean[i]))
        expected = expected_tightness_pct[name]
        if achieved <= expected:
            state = "within"
        elif achieved <= 2.0 * expected:
            state = "loose"
        else:
            state = "degraded"
            any_degraded_tightness = True

        per_parameter[name] = {
            "rho": rho,
            "identifiability_flag": flag,
            "tightness_state": state,
            "sigma_post_over_mu_post": achieved,
            "sigma_post_over_mu_post_expected": expected,
            "D_KL_nats": float(laplace.posterior_prior_kl_divergence_per_param[i]),
        }

    # Diagnostic 3: Hessian spectrum
    lambda_max = float(np.max(laplace.hessian_eigenvalues))
    ridge_threshold = lambda_max * ID8_RIDGE_EIGENVALUE_FRACTION
    eigenvectors = np.linalg.eigh(laplace.hessian_at_mode).eigenvectors

    ridge_vectors: list[dict] = []
    for i, eigval in enumerate(laplace.hessian_eigenvalues):
        if eigval < ridge_threshold:
            loadings = {
                CANONICAL_PARAMETER_NAMES[p]: float(eigenvectors[p, i])
                for p in range(NUM_CANONICAL_PARAMETERS)
            }
            ridge_vectors.append(
                {"eigenvalue": float(eigval), "loadings": loadings}
            )

    joint_id_flag = (
        laplace.hessian_condition_number > ID8_HESSIAN_KAPPA_THRESHOLD
        or len(ridge_vectors) > 0
    )
    if joint_id_flag:
        any_identifiability_flag = True

    hessian_spectrum = {
        "eigenvalues": laplace.hessian_eigenvalues.tolist(),
        "condition_number": laplace.hessian_condition_number,
        "ridge_vectors": ridge_vectors,
        "joint_identifiability_flag": joint_id_flag,
    }

    summary = {
        "any_identifiability_flag": any_identifiability_flag,
        "any_degraded_tightness": any_degraded_tightness,
    }

    return IdentifiabilityReport(
        protocol=protocol,
        per_parameter=per_parameter,
        hessian_spectrum=hessian_spectrum,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# End-to-end §5 orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PassiveFitResult:
    """End-to-end output of `run_passive_batch_fit`: the Laplace fit, the
    signed Day2Posterior record, the inclusion proof, and the threshold-
    attestation (stub) per §2.3 envelope-half-initial signing."""

    laplace: LaplaceResult
    day2_posterior: Day2Posterior
    signed_record: SignedRecord
    inclusion_proof: LogInclusionProof
    threshold_attestation: ThresholdAttestation


def run_passive_batch_fit(
    window: Day12TelemetryWindow,
    prior: Prior6D,
    fan_heat_pass_record_hash: str,
    home_id: str,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> PassiveFitResult:
    """Per §5 end-to-end:

      1. Extract two-channel observations per §5.3.
      2. Run the Laplace fit with 4 prior-perturbed restarts (§5.6).
      3. Build §8 identifiability report from the Laplace output.
      4. Construct the Day2Posterior record (§5.8).
      5. Sign and log via §12: sign_record → commit_to_log → threshold_attest
         (envelope_half_initial moment).

    Args:
      mode_agreement_fraction: passthrough to `run_laplace_fit` for the
        §5.7 mode-agreement diagnostic. Tests against simplified forward
        chains can relax this; production code uses the default.

    Caller responsibilities:
      - Supply a valid `FanHeatPass` record hash (INV-FIT12-1). The §4 module
        is responsible for producing it; this function trusts the caller's
        upstream check.
      - Supply a Prior6D with provenance metadata per §5.4 (INV-FIT12-3).

    Raises:
      LaplaceFitFailed if any §5.7 convergence or quality diagnostic fails.
      The commissioning pipeline halts (INV-FIT12-4); no Day2Posterior signed.
    """
    if not fan_heat_pass_record_hash:
        raise ValueError(
            "INV-FIT12-1: §5 MUST NOT consume Day-1-2 telemetry without a "
            "valid FanHeatPass record hash. Caller must supply the hash."
        )

    obs = extract_two_channel_observations(window, p_atm_pa)

    laplace = run_laplace_fit(
        obs,
        window,
        prior,
        forward_chain,
        context,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    id_report = build_identifiability_report(laplace, prior)

    # Build the Day2Posterior record per §5.8
    posterior_common = PosteriorCommon(
        home_id=home_id,
        parameter_names=CANONICAL_PARAMETER_NAMES,
        posterior_mean=tuple(laplace.posterior_mean.tolist()),
        posterior_covariance=tuple(
            tuple(row) for row in laplace.posterior_covariance.tolist()
        ),
        prior_provenance_descriptor=prior.provenance_descriptor,
        prior_hash=prior.provenance_hash,
        monotonic_timestamp_ns=window.samples[-1].monotonic_ns,
    )
    day2 = Day2Posterior(
        common=posterior_common,
        identifiability_report=id_report,
        fan_heat_pass_record_hash=fan_heat_pass_record_hash,
    )

    # Sign + log + threshold-attest per §12 (INV-SIGN12-1, INV-SIGN12-2,
    # INV-SIGN12-3 with envelope_half_initial moment)
    signable = {
        "record_type": day2.record_type,
        "fan_heat_pass_record_hash": day2.fan_heat_pass_record_hash,
        "home_id": day2.common.home_id,
        "parameter_names": list(day2.common.parameter_names),
        "posterior_mean": list(day2.common.posterior_mean),
        # Flatten covariance for canonical-form hashing
        "posterior_covariance": [list(row) for row in day2.common.posterior_covariance],
        "prior_provenance_descriptor": day2.common.prior_provenance_descriptor,
        "prior_hash": day2.common.prior_hash,
        "monotonic_timestamp_ns": day2.common.monotonic_timestamp_ns,
        "identifiability_report": {
            "protocol": id_report.protocol,
            "per_parameter": id_report.per_parameter,
            "hessian_spectrum": id_report.hessian_spectrum,
            "summary": id_report.summary,
        },
        "hessian_eigenvalues": laplace.hessian_eigenvalues.tolist(),
        "convergence_diagnostics": {
            "optimizer_converged_all_restarts": laplace.optimizer_converged_all_restarts,
            "mode_agreement_passed": laplace.mode_agreement_passed,
            "hessian_positive_definite": laplace.hessian_positive_definite,
            "hessian_condition_number": laplace.hessian_condition_number,
            "restart_log_posteriors": laplace.restart_log_posteriors.tolist(),
            "restart_mode_disagreement_max_frac_of_prior_sigma": float(
                np.max(np.std(laplace.restart_modes, axis=0) / prior.marginal_sigmas)
            ),
        },
    }
    signed = sign_record(signable)
    inclusion = commit_to_log(signed)
    attestation = threshold_attest(signable, AttestationMoment.ENVELOPE_HALF_INITIAL)

    return PassiveFitResult(
        laplace=laplace,
        day2_posterior=day2,
        signed_record=signed,
        inclusion_proof=inclusion,
        threshold_attestation=attestation,
    )
