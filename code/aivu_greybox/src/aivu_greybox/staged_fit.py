"""§5/§6 staged identification by frequency band — T7 implementation of
the §5.3 amendment v0.2 (T2) and §6.3 amendment v0.1 (T3).

This module replaces the joint-fit framing of `passive_fit.py` and
`active_fit.py` with sequential staged identification per the v0.4
architectural reformulation. Four stages:

  - Stage 1 (§5, diurnal-thermal night): R_opaque, U_fenestration,
    ceiling_coupling_factor. Production thresholds gating.
  - Stage 2 (§5, synoptic-wind, best-effort): C_stack, C_wind. Posterior
    width reported but not gating, per the two-tier horizon model.
  - Stage 3 (§6, active thermal night): C_house. Production thresholds
    gating.
  - Stage 4 (§6, active moisture night): C_w. Production thresholds gating.

Posterior propagates between stages as informative prior per the §11.2
posterior-as-prior chain discipline.

The math framework is (b) frequency-domain Welch likelihood per T2 v0.2.
Stage-specific Welch parameters and band edges per the amendment.

This module is the first cut; v0.2 work is reconciliation to §5/§6's
current text at word level, and Welch-parameter tuning against
aivu_corpus synthetic trajectories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from scipy.optimize import minimize
from scipy.signal import welch

from .defaults import (
    CANONICAL_PARAMETER_NAMES,
    EXPECTED_TIGHTNESS_SIGMA_OVER_MU,
    LAPLACE_MODE_AGREEMENT_FRACTION,
    LAPLACE_NUM_RESTARTS,
    NUM_CANONICAL_PARAMETERS,
    SIGMA_T_ATTIC_C,
    SIGMA_T_MAIN_C,
)
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
from .passive_fit_types import Day12TelemetryWindow, Prior7D
from .psychrometrics import P_ATM_PHOENIX_PA, humidity_ratio


# ---------------------------------------------------------------------------
# Stage definitions — parameter targets and Welch / band specifications
# ---------------------------------------------------------------------------


# Canonical-order indices of each parameter, for stage-target masks
_PARAM_INDEX = {name: i for i, name in enumerate(CANONICAL_PARAMETER_NAMES)}


@dataclass(frozen=True)
class StageSpec:
    """Static specification of one stage's identification target and likelihood
    geometry. Per T2 v0.2 / T3 v0.1.
    """

    name: str  # e.g. "stage1_diurnal_thermal"
    protocol_string: str  # for IdentifiabilityReport
    target_parameter_names: tuple[str, ...]
    welch_window_seconds: float
    welch_overlap_fraction: float
    band_low_period_seconds: float   # band low edge expressed as period (1/f_high)
    band_high_period_seconds: float  # band high edge expressed as period (1/f_low)
    apply_night_filter: bool
    gating: bool  # True if failure raises LaplaceFitFailed; False if best-effort
    expected_excitation_window_seconds: float  # for diagnostic / Welch segment count


# Stage 1 — diurnal-thermal night, conductances. Per T2 v0.2.
STAGE_1 = StageSpec(
    name="stage1_diurnal_thermal",
    protocol_string="§5_stage1_diurnal_thermal",
    target_parameter_names=("R_opaque", "U_fenestration", "ceiling_coupling_factor"),
    welch_window_seconds=6.0 * 3600.0,
    welch_overlap_fraction=0.5,
    band_low_period_seconds=6.0 * 3600.0,   # 1/6h upper frequency edge
    band_high_period_seconds=24.0 * 3600.0,  # 1/24h lower frequency edge
    apply_night_filter=True,
    gating=True,
    expected_excitation_window_seconds=21.0 * 3600.0,  # ~21h usable night data in Days 1-2
)


# Stage 2 — synoptic-wind, infiltration. Best-effort per two-tier horizon model.
STAGE_2 = StageSpec(
    name="stage2_synoptic_wind",
    protocol_string="§5_stage2_synoptic_wind",
    target_parameter_names=("C_stack", "C_wind"),
    welch_window_seconds=12.0 * 3600.0,
    welch_overlap_fraction=0.5,
    band_low_period_seconds=3.0 * 3600.0,    # 1/3h upper frequency edge
    band_high_period_seconds=24.0 * 3600.0,  # 1/24h lower frequency edge
    apply_night_filter=False,
    gating=False,
    expected_excitation_window_seconds=48.0 * 3600.0,
)


# Stage 3 — active thermal night transients, C_house. Production gating.
STAGE_3 = StageSpec(
    name="stage3_active_thermal",
    protocol_string="§6_stage3_active_thermal",
    target_parameter_names=("C_house",),
    welch_window_seconds=3.0 * 3600.0,
    welch_overlap_fraction=0.5,
    band_low_period_seconds=30.0 * 60.0,    # 1/30min upper frequency edge
    band_high_period_seconds=12.0 * 3600.0,  # 1/12h lower frequency edge
    apply_night_filter=True,
    gating=True,
    expected_excitation_window_seconds=21.0 * 3600.0,
)


# Stage 4 — active moisture night transients, C_w. Production gating.
STAGE_4 = StageSpec(
    name="stage4_active_moisture",
    protocol_string="§6_stage4_active_moisture",
    target_parameter_names=("C_w",),
    welch_window_seconds=1.0 * 3600.0,
    welch_overlap_fraction=0.5,
    band_low_period_seconds=15.0 * 60.0,    # 1/15min upper frequency edge
    band_high_period_seconds=3.0 * 3600.0,   # 1/3h lower frequency edge
    apply_night_filter=True,
    gating=True,
    expected_excitation_window_seconds=21.0 * 3600.0,
)


# Solar-irradiance threshold for the night filter, W/m². Per T2 v0.2.
NIGHT_FILTER_SOLAR_THRESHOLD_W_M2 = 50.0


# ---------------------------------------------------------------------------
# Night-filter helpers
# ---------------------------------------------------------------------------


def night_filter_mask(weather: WeatherSeries) -> np.ndarray:
    """Return a boolean mask over the 1-Hz telemetry indicating night samples.

    Per T2 v0.2: retain samples where solar_global < threshold. The
    sunset-to-sunrise clock-time component is implicitly captured by the
    solar-irradiance threshold; for the v0.1 first cut, we don't add a
    separate clock-time check (it would double-count what the threshold
    already enforces).
    """
    return weather.solar_global_w_per_m2 < NIGHT_FILTER_SOLAR_THRESHOLD_W_M2


# ---------------------------------------------------------------------------
# Welch-based band-weighted likelihood
# ---------------------------------------------------------------------------


def welch_band_weighted_negloglik(
    residual: np.ndarray,
    dt_seconds: float,
    window_seconds: float,
    overlap_fraction: float,
    band_low_period_seconds: float,
    band_high_period_seconds: float,
    sigma_obs: float,
) -> float:
    """Compute the band-weighted -log L over a Welch PSD of the residual.

    Per T2 v0.2 §5.3 amendment: the staged-fit likelihood is computed on
    the Welch PSD of the residual between observed and model-predicted
    telemetry, restricted to the stage's frequency band.

    For a Gaussian residual model with known σ_obs, the negative log
    likelihood is (1/(2σ_obs²)) × (band-summed power × df), which is
    proportional to the variance contribution from the band. This treats
    the in-band power as the "signal" the fit tries to minimize.

    Args:
        residual: time-domain residual array, shape (N,)
        dt_seconds: sample period (seconds between consecutive samples)
        window_seconds: Welch segment length in seconds
        overlap_fraction: 0.0 to <1.0
        band_low_period_seconds: residual band low-period edge (= 1/f_high)
        band_high_period_seconds: residual band high-period edge (= 1/f_low)
        sigma_obs: per-sample observation σ (same units as residual)

    Returns:
        -log L contribution from this band-weighted Welch likelihood.

    Notes:
        Returns 1e10 (large but finite) if the residual is too short for the
        requested Welch segment, allowing the optimizer to recover from a
        degenerate parameter region rather than crashing.
    """
    n_samples = residual.size
    nperseg = int(round(window_seconds / dt_seconds))

    # Need at least one full Welch segment
    if nperseg < 8 or n_samples < nperseg:
        return 1e10

    noverlap = int(round(nperseg * overlap_fraction))
    fs = 1.0 / dt_seconds

    # NaN guard
    if np.any(np.isnan(residual)):
        return 1e10

    freqs, psd = welch(
        residual,
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        scaling="density",
    )

    # Convert period edges to frequency edges (Hz)
    f_low = 1.0 / band_high_period_seconds  # low frequency
    f_high = 1.0 / band_low_period_seconds   # high frequency

    # Select frequencies in the band (inclusive of edges, excluding DC)
    in_band = (freqs >= f_low) & (freqs <= f_high) & (freqs > 0)
    if not np.any(in_band):
        return 1e10

    # Frequency-domain spacing
    df = freqs[1] - freqs[0] if freqs.size > 1 else 1.0

    # Band-summed power = ∫ PSD df over the band ≈ Σ PSD × df.
    # This is variance contribution from the band.
    band_power = float(np.sum(psd[in_band]) * df)

    # Gaussian negative-log-likelihood for known σ_obs:
    # -log L ∝ band_power / (2 σ_obs²)
    return 0.5 * band_power / (sigma_obs ** 2)


# ---------------------------------------------------------------------------
# Stage-specific residual extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageObservations:
    """Per-stage observed telemetry as 1-Hz arrays. The fit computes
    residuals at each candidate θ by calling the forward chain and
    subtracting predicted from observed at the same indices."""

    t_main_observed_c: np.ndarray
    w_main_observed_kg_per_kg: np.ndarray
    t_attic_observed_c: np.ndarray  # shape (N,) or empty if not used
    observation_mask: np.ndarray  # bool, which 1-Hz indices contribute to the fit


def extract_stage_observations_passive(
    window: Day12TelemetryWindow,
    stage: StageSpec,
    weather: WeatherSeries,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> StageObservations:
    """Extract per-sample observed telemetry across the full window, plus
    the stage's observation mask (which samples contribute to the residual).

    For passive §5 stages, the observed quantities come from the
    Day12TelemetryWindow's return_plenum readings (T_main, W_main) and the
    terminal-probe spatial averages during fan-on warmup (T_attic).
    """
    samples = window.samples
    n = len(samples)

    t_main = np.empty(n)
    w_main = np.empty(n)
    t_attic = np.full(n, np.nan)  # only populated at terminal-probe samples

    for i, s in enumerate(samples):
        t_main[i] = s.return_plenum.temperature_c
        try:
            w_main[i] = humidity_ratio(
                s.return_plenum.temperature_c,
                s.return_plenum.relative_humidity_pct,
                p_atm_pa,
            )
        except ValueError:
            w_main[i] = np.nan
        # Terminal-probe spatial average available when fan_on
        if s.fan_on and s.terminals:
            t_attic[i] = float(np.mean([t.sht.temperature_c for t in s.terminals]))

    # Build the observation mask: night filter if applicable, plus exclude NaN
    if stage.apply_night_filter:
        mask = night_filter_mask(weather)
    else:
        mask = np.ones(n, dtype=bool)
    # Exclude samples with NaN main observations (psychrometric failures)
    mask = mask & ~np.isnan(t_main) & ~np.isnan(w_main)

    return StageObservations(
        t_main_observed_c=t_main,
        w_main_observed_kg_per_kg=w_main,
        t_attic_observed_c=t_attic,
        observation_mask=mask,
    )


# ---------------------------------------------------------------------------
# Stage-specific objective
# ---------------------------------------------------------------------------


def stage_neg_log_likelihood(
    theta: np.ndarray,
    stage: StageSpec,
    obs: StageObservations,
    hvac: HVACExcitation,
    weather: WeatherSeries,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    dt_seconds: float,
) -> float:
    """Compute -log L(θ | data) for one stage via the band-weighted Welch
    likelihood applied to T_main residuals (and W_main residuals for Stage 4).
    """
    trajectory = forward_chain.run(theta, hvac, weather, context)

    if (
        np.any(np.isnan(trajectory.t_main_c))
        or np.any(np.isnan(trajectory.w_main_kg_per_kg))
    ):
        return 1e10

    # T_main residual, restricted to the stage's observation mask
    t_main_residual = obs.t_main_observed_c - trajectory.t_main_c
    t_main_residual_masked = t_main_residual[obs.observation_mask]

    nll = welch_band_weighted_negloglik(
        residual=t_main_residual_masked,
        dt_seconds=dt_seconds,
        window_seconds=stage.welch_window_seconds,
        overlap_fraction=stage.welch_overlap_fraction,
        band_low_period_seconds=stage.band_low_period_seconds,
        band_high_period_seconds=stage.band_high_period_seconds,
        sigma_obs=SIGMA_T_MAIN_C,
    )

    # Stage 4 (moisture) also uses W_main residual
    if "C_w" in stage.target_parameter_names:
        w_main_residual = obs.w_main_observed_kg_per_kg - trajectory.w_main_kg_per_kg
        w_main_residual_masked = w_main_residual[obs.observation_mask]
        nll += welch_band_weighted_negloglik(
            residual=w_main_residual_masked,
            dt_seconds=dt_seconds,
            window_seconds=stage.welch_window_seconds,
            overlap_fraction=stage.welch_overlap_fraction,
            band_low_period_seconds=stage.band_low_period_seconds,
            band_high_period_seconds=stage.band_high_period_seconds,
            sigma_obs=SIGMA_W,
        )

    return nll


def stage_neg_log_prior(theta: np.ndarray, prior: Prior7D) -> float:
    """Multivariate Gaussian -log prior. Identical to passive_fit's."""
    delta = theta - prior.mean
    cov_inv = np.linalg.inv(prior.covariance)
    return 0.5 * delta @ cov_inv @ delta


# ---------------------------------------------------------------------------
# Shared Laplace orchestration (factored from passive_fit.run_laplace_fit)
# ---------------------------------------------------------------------------


def _laplace_with_objective(
    objective: Callable[[np.ndarray], float],
    prior: Prior7D,
    num_restarts: int,
    rng_seed: int,
    mode_agreement_fraction: float,
    raise_on_failure: bool,
    failure_context_label: str,
) -> LaplaceResult:
    """Run L-BFGS-B with N prior-perturbed restarts, then build the Laplace
    approximation. Factored from `passive_fit.run_laplace_fit` so the staged
    code can reuse it across all four stages.

    If `raise_on_failure=False`, convergence/quality failures are recorded
    in the returned LaplaceResult (the *_passed/*_pd flags) but do not
    raise. This is how Stage 2 (best-effort) gets its non-gating behavior.
    """
    rng = np.random.default_rng(rng_seed)
    n_params = NUM_CANONICAL_PARAMETERS

    restart_modes = np.zeros((num_restarts, n_params))
    restart_log_posteriors = np.zeros(num_restarts)
    converged_flags = np.zeros(num_restarts, dtype=bool)

    cholesky_prior = np.linalg.cholesky(prior.covariance)
    positive_floors = {
        "R_opaque": 0.1,
        "U_fenestration": 0.1,
        "C_house": 1e5,
        "C_stack": 0.0,
        "C_wind": 0.0,
        "C_w": 1000.0,  # kg; C_w cannot fall below the bare conditioned-air
                        # mass (~857 kg). The floor sits just above it so the
                        # real_chain C_w→kappa_buffer conversion stays positive.
        "ceiling_coupling_factor": 0.0,
    }

    # Optimizer coordinate normalization (2026-05-21 fix).
    # The seven canonical parameters span ~7 orders of magnitude (R_opaque ~1
    # to C_house ~5e6). L-BFGS-B applies one step length and one inverse-
    # Hessian scaling across all coordinates at once, so a large-magnitude
    # parameter is effectively frozen: its gradient is correct but unusable at
    # a step size shared with order-1 parameters, and the optimizer returns
    # success having never moved it. This silently biased C_house recovery
    # (recovered 4.893e6 vs truth 4.5e6, bit-identical across runs) until the
    # 2026-05-21 diagnosis. The fix runs L-BFGS-B in normalized coordinates
    # u = theta / scale, with scale = prior marginal sigma (strictly positive;
    # makes the prior curvature isotropic), and unscales at the boundary.
    scale = prior.marginal_sigmas.copy()
    scale = np.where(scale > 0.0, scale, 1.0)  # defensive; marginal sigmas are > 0

    def objective_normalized(u: np.ndarray) -> float:
        return objective(u * scale)

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

        # Run L-BFGS-B in normalized coordinates; unscale the result.
        start_u = start / scale
        bounds_u = [
            (lo / scale[i], hi / scale[i]) for i, (lo, hi) in enumerate(bounds)
        ]
        result = minimize(
            objective_normalized,
            x0=start_u,
            method="L-BFGS-B",
            bounds=bounds_u,
            options={"ftol": 1e-9, "gtol": 1e-7, "maxiter": 200},
        )
        restart_modes[r] = result.x * scale
        restart_log_posteriors[r] = -result.fun
        converged_flags[r] = bool(result.success)

    optimizer_converged_all_restarts = bool(np.all(converged_flags))
    if not optimizer_converged_all_restarts and raise_on_failure:
        raise LaplaceFitFailed(
            f"[{failure_context_label}] one or more L-BFGS-B restarts did not "
            f"converge (success flags: {converged_flags.tolist()})."
        )

    prior_sigmas = prior.marginal_sigmas
    mode_diffs = np.std(restart_modes, axis=0)
    mode_agreement_passed = bool(
        np.all(mode_diffs < mode_agreement_fraction * prior_sigmas)
    )
    if not mode_agreement_passed and raise_on_failure:
        raise LaplaceFitFailed(
            f"[{failure_context_label}] mode-agreement check failed: "
            f"restart-to-restart parameter disagreement exceeds "
            f"{mode_agreement_fraction:.2g} × prior σ on at least one parameter."
        )

    best_restart = int(np.argmax(restart_log_posteriors))
    mode = restart_modes[best_restart]

    # NOTE (2026-05-21): the optimizer above runs in normalized coordinates to
    # fix the conditioning bug that froze C_house. The Hessian below is still
    # raw-coordinate finite-differenced; whether it needs the same treatment is
    # settled by the post-fix active (§6) rerun — if the mode is now correct
    # but the recovered sigma is not, normalize this step the same way. See the
    # 2026-05-21 session log.
    hessian = finite_difference_hessian(objective, mode)
    eigenvalues = np.linalg.eigvalsh(hessian)
    positive_definite = bool(np.all(eigenvalues > 0))
    if not positive_definite and raise_on_failure:
        raise LaplaceFitFailed(
            f"[{failure_context_label}] Hessian not positive-definite at mode "
            f"(eigenvalues: {eigenvalues.tolist()})."
        )

    if positive_definite:
        condition_number = float(np.max(eigenvalues) / np.min(eigenvalues))
        covariance = np.linalg.inv(hessian)
        covariance = 0.5 * (covariance + covariance.T)
    else:
        # Best-effort path: report the singular Hessian honestly, use a
        # regularized pseudo-inverse for covariance so downstream code doesn't
        # crash on the singular matrix.
        condition_number = float("inf")
        eigvals_for_inv = np.where(eigenvalues > 0, eigenvalues, 1e-12)
        # Reconstruct via spectral decomposition, regularized
        eigvecs = np.linalg.eigh(hessian).eigenvectors
        covariance = eigvecs @ np.diag(1.0 / eigvals_for_inv) @ eigvecs.T
        covariance = 0.5 * (covariance + covariance.T)

    # KL per parameter
    n = mode.shape[0]
    kl = np.empty(n)
    for i in range(n):
        sigma_post_sq = max(covariance[i, i], 1e-30)
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
# Posterior-as-prior propagation between stages
# ---------------------------------------------------------------------------


def propagate_posterior_as_prior(
    base_prior: Prior7D,
    previous_laplace: LaplaceResult,
    previous_target_param_names: tuple[str, ...],
) -> Prior7D:
    """Construct the next stage's prior by replacing the previous stage's
    target-parameter marginals with the posterior's marginals.

    Per T2 v0.2 § Stage 2 posterior-as-prior propagation:
        Stage N+1's prior = Gaussian with mean = (Stage N posterior mean
        on target params, base prior mean elsewhere) and covariance =
        block-diagonal with Stage N posterior covariance on target params
        and base prior covariance elsewhere.

    The block-diagonal structure is conservative: it ignores cross-block
    correlation between the just-identified parameters and the rest. In
    practice the just-identified parameters' posterior is much tighter
    than the prior on the others, so the cross-block correlation is small.
    Analytical marginalization is the v0.2 alternative.
    """
    new_mean = base_prior.mean.copy()
    new_cov = np.array(base_prior.covariance, copy=True)

    target_indices = [_PARAM_INDEX[name] for name in previous_target_param_names]

    # Replace target-param means with the posterior means
    for idx in target_indices:
        new_mean[idx] = previous_laplace.posterior_mean[idx]

    # Replace the target-param block of the covariance with the posterior block
    for i in target_indices:
        for j in target_indices:
            new_cov[i, j] = previous_laplace.posterior_covariance[i, j]
        # Zero out off-block correlations (conservative)
        for j in range(NUM_CANONICAL_PARAMETERS):
            if j not in target_indices:
                new_cov[i, j] = 0.0
                new_cov[j, i] = 0.0

    # Symmetrize numerically
    new_cov = 0.5 * (new_cov + new_cov.T)

    # Ensure positive definiteness — small jitter on the diagonal if Cholesky fails
    try:
        np.linalg.cholesky(new_cov)
    except np.linalg.LinAlgError:
        jitter = 1e-12 * np.eye(NUM_CANONICAL_PARAMETERS)
        new_cov = new_cov + jitter

    return Prior7D(
        mean=new_mean,
        covariance=new_cov,
        provenance_descriptor=(
            f"{base_prior.provenance_descriptor}"
            f"|propagated_from_stage_targets={previous_target_param_names}"
        ),
        provenance_hash=base_prior.provenance_hash + "_propagated",
        generated_timestamp_iso=base_prior.generated_timestamp_iso,
    )


# ---------------------------------------------------------------------------
# Per-stage public entry points
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageResult:
    """Output of one stage's fit: Laplace approximation + identifiability
    report. The staged orchestrator collects these from each stage and
    composes the signed record."""

    stage: StageSpec
    laplace: LaplaceResult
    identifiability_report: object  # IdentifiabilityReport from passive_fit


def run_stage_passive(
    stage: StageSpec,
    window: Day12TelemetryWindow,
    prior: Prior7D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    dt_seconds: float = 1.0,
    num_restarts: int = LAPLACE_NUM_RESTARTS,
    rng_seed: int = 42,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> StageResult:
    """Run one §5 stage (Stage 1 or Stage 2) end-to-end.

    For Stage 1 (gating), failures raise LaplaceFitFailed.
    For Stage 2 (best-effort), failures are recorded in the LaplaceResult
    flags but do not raise.
    """
    weather = WeatherSeries(
        monotonic_ns=window.weather_monotonic_ns,
        t_outdoor_c=window.t_outdoor_c,
        rh_outdoor_pct=window.rh_outdoor_pct,
        solar_global_w_per_m2=window.solar_global_w_per_m2,
        wind_speed_m_per_s=window.wind_speed_m_per_s,
    )
    hvac = HVACExcitation(
        monotonic_ns=window.hvac_excitation_monotonic_ns,
        q_sens_w=window.q_sens_w,
        m_lat_kg_per_s=window.m_lat_kg_per_s,
    )

    obs = extract_stage_observations_passive(window, stage, weather)

    def objective(theta: np.ndarray) -> float:
        return (
            stage_neg_log_likelihood(
                theta, stage, obs, hvac, weather, forward_chain, context, dt_seconds
            )
            + stage_neg_log_prior(theta, prior)
        )

    laplace = _laplace_with_objective(
        objective=objective,
        prior=prior,
        num_restarts=num_restarts,
        rng_seed=rng_seed,
        mode_agreement_fraction=mode_agreement_fraction,
        raise_on_failure=stage.gating,
        failure_context_label=stage.name,
    )

    id_report = build_identifiability_report(
        laplace, prior, protocol=stage.protocol_string
    )

    return StageResult(stage=stage, laplace=laplace, identifiability_report=id_report)


# ---------------------------------------------------------------------------
# Staged passive (§5) orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagedPassiveFitResult:
    """End-to-end output of `run_staged_passive_batch_fit`.

    Collects the per-stage results. Signed Day2Posterior construction is
    deferred to a separate step in v0.1 (avoids tangling the per-stage
    machinery with the schema-evolution work that T5 §12.x amendment owns).
    """

    stage1: StageResult
    stage2: StageResult
    final_posterior_mean: np.ndarray
    final_posterior_covariance: np.ndarray


def run_staged_passive_batch_fit(
    window: Day12TelemetryWindow,
    base_prior: Prior7D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    dt_seconds: float = 1.0,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> StagedPassiveFitResult:
    """Per §5.3 amendment v0.2: run Stage 1 (gating, conductances) followed
    by Stage 2 (best-effort, infiltration) with Stage 1's posterior
    propagated as informative prior into Stage 2.

    Raises:
        LaplaceFitFailed if Stage 1 fails any production threshold.
        Stage 2 failures are recorded but do not raise.
    """
    # Stage 1 — gating
    stage1_result = run_stage_passive(
        STAGE_1,
        window,
        base_prior,
        forward_chain,
        context,
        dt_seconds=dt_seconds,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    # Propagate Stage 1 posterior as informative prior for Stage 2
    stage2_prior = propagate_posterior_as_prior(
        base_prior, stage1_result.laplace, STAGE_1.target_parameter_names
    )

    # Stage 2 — best-effort
    stage2_result = run_stage_passive(
        STAGE_2,
        window,
        stage2_prior,
        forward_chain,
        context,
        dt_seconds=dt_seconds,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    # Compose final posterior: Stage 1 conductances + Stage 2 infiltration +
    # base prior for the §6 parameters (C_house, C_w) — §6 hasn't run yet.
    final_mean = base_prior.mean.copy()
    final_cov = np.array(base_prior.covariance, copy=True)
    for name in STAGE_1.target_parameter_names:
        idx = _PARAM_INDEX[name]
        final_mean[idx] = stage1_result.laplace.posterior_mean[idx]
    for name in STAGE_2.target_parameter_names:
        idx = _PARAM_INDEX[name]
        final_mean[idx] = stage2_result.laplace.posterior_mean[idx]
    # Compose block-diagonal covariance
    s1_indices = [_PARAM_INDEX[n] for n in STAGE_1.target_parameter_names]
    s2_indices = [_PARAM_INDEX[n] for n in STAGE_2.target_parameter_names]
    target_indices = s1_indices + s2_indices
    for i in target_indices:
        for j in range(NUM_CANONICAL_PARAMETERS):
            if j in s1_indices and i in s1_indices:
                final_cov[i, j] = stage1_result.laplace.posterior_covariance[i, j]
            elif j in s2_indices and i in s2_indices:
                final_cov[i, j] = stage2_result.laplace.posterior_covariance[i, j]
            elif i != j:
                # Zero cross-block correlations for now
                final_cov[i, j] = 0.0
    final_cov = 0.5 * (final_cov + final_cov.T)

    return StagedPassiveFitResult(
        stage1=stage1_result,
        stage2=stage2_result,
        final_posterior_mean=final_mean,
        final_posterior_covariance=final_cov,
    )


# ---------------------------------------------------------------------------
# §6 active staged fit (Stages 3 and 4)
# ---------------------------------------------------------------------------
#
# Architectural call for v0.1: both Stage 3 (C_house) and Stage 4 (C_w)
# consume night-filtered samples across all four phases (A/B/C/D), not
# phase-restricted samples. Reasoning:
#   (1) Single A/B/C/D cycle in 48h gives 6h of Phase B (decay) and 6h of
#       Phase D (closing) — too short for meaningful Welch averaging at
#       Stage 3's 3h window length.
#   (2) The Welch band weighting handles the regime decomposition: Stage 3's
#       1/30min-to-1/12h band captures thermal-mass response across both
#       compressor-on (Phase A/C) and compressor-off (Phase B/D) dynamics.
#   (3) The forward chain captures the HVAC excitation directly via q_sens_w
#       and m_lat_kg_per_s; the residual after subtracting the model
#       prediction carries the parameter information regardless of phase.
#   (4) Different residual channels distinguish the stages: Stage 3 against
#       T_main residual, Stage 4 against W_main residual.
#
# This deviates from T3 v0.1's phase-restricted framing. The text-level
# reconciliation is a T3 v0.2 item; the architectural decision here is
# captured for that reconciliation.

# We import the active-window dataclass from active_fit to avoid duplication.
from .active_fit import Day45TelemetryWindow, classify_samples_by_phase


def extract_stage_observations_active(
    window: Day45TelemetryWindow,
    stage: StageSpec,
    weather: WeatherSeries,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> StageObservations:
    """Extract per-sample observed telemetry across the full §6 active window,
    plus the stage's observation mask.

    For active §6 stages, the structure mirrors the passive extractor but
    operates on a Day45TelemetryWindow. Night-filter mask applies per the
    stage spec.
    """
    samples = window.samples
    n = len(samples)

    t_main = np.empty(n)
    w_main = np.empty(n)
    t_attic = np.full(n, np.nan)

    for i, s in enumerate(samples):
        t_main[i] = s.return_plenum.temperature_c
        try:
            w_main[i] = humidity_ratio(
                s.return_plenum.temperature_c,
                s.return_plenum.relative_humidity_pct,
                p_atm_pa,
            )
        except ValueError:
            w_main[i] = np.nan
        # Attic from terminal probes when fan is on (Phase B/C/D have
        # fan-on intervals; Phase A is continuous fan)
        if s.fan_on and s.terminals:
            t_attic[i] = float(np.mean([t.sht.temperature_c for t in s.terminals]))

    if stage.apply_night_filter:
        mask = night_filter_mask(weather)
    else:
        mask = np.ones(n, dtype=bool)
    mask = mask & ~np.isnan(t_main) & ~np.isnan(w_main)

    return StageObservations(
        t_main_observed_c=t_main,
        w_main_observed_kg_per_kg=w_main,
        t_attic_observed_c=t_attic,
        observation_mask=mask,
    )


def run_stage_active(
    stage: StageSpec,
    window: Day45TelemetryWindow,
    prior: Prior7D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    dt_seconds: float = 1.0,
    num_restarts: int = LAPLACE_NUM_RESTARTS,
    rng_seed: int = 42,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> StageResult:
    """Run one §6 stage (Stage 3 or Stage 4) end-to-end.

    Both §6 stages are gating (production thresholds). Failures raise
    LaplaceFitFailed unless stage.gating is False (currently not the case
    for Stage 3 or Stage 4, but the mechanism is uniform).
    """
    weather = WeatherSeries(
        monotonic_ns=window.weather_monotonic_ns,
        t_outdoor_c=window.t_outdoor_c,
        rh_outdoor_pct=window.rh_outdoor_pct,
        solar_global_w_per_m2=window.solar_global_w_per_m2,
        wind_speed_m_per_s=window.wind_speed_m_per_s,
    )
    hvac = HVACExcitation(
        monotonic_ns=window.hvac_excitation_monotonic_ns,
        q_sens_w=window.q_sens_w,
        m_lat_kg_per_s=window.m_lat_kg_per_s,
    )

    obs = extract_stage_observations_active(window, stage, weather)

    def objective(theta: np.ndarray) -> float:
        return (
            stage_neg_log_likelihood(
                theta, stage, obs, hvac, weather, forward_chain, context, dt_seconds
            )
            + stage_neg_log_prior(theta, prior)
        )

    laplace = _laplace_with_objective(
        objective=objective,
        prior=prior,
        num_restarts=num_restarts,
        rng_seed=rng_seed,
        mode_agreement_fraction=mode_agreement_fraction,
        raise_on_failure=stage.gating,
        failure_context_label=stage.name,
    )

    id_report = build_identifiability_report(
        laplace, prior, protocol=stage.protocol_string
    )

    return StageResult(stage=stage, laplace=laplace, identifiability_report=id_report)


# ---------------------------------------------------------------------------
# Staged active (§6) orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagedActiveFitResult:
    """End-to-end output of `run_staged_active_batch_fit`.

    Collects per-stage results from Stage 3 (C_house) and Stage 4 (C_w),
    composed with the §5 staged posterior to produce the final 7-parameter
    posterior. Signed Day6Posterior construction is deferred to a separate
    helper in v0.1 pending T5 §12.x amendment.
    """

    stage3: StageResult
    stage4: StageResult
    final_posterior_mean: np.ndarray
    final_posterior_covariance: np.ndarray


def run_staged_active_batch_fit(
    window: Day45TelemetryWindow,
    passive_fit_result: StagedPassiveFitResult,
    base_prior: Prior7D,
    forward_chain: ForwardChain,
    context: HomeStaticContext,
    dt_seconds: float = 1.0,
    mode_agreement_fraction: float = LAPLACE_MODE_AGREEMENT_FRACTION,
) -> StagedActiveFitResult:
    """Per §6.3 amendment v0.1: run Stage 3 (C_house, gating) followed by
    Stage 4 (C_w, gating) with the §5 staged posterior propagated as
    informative prior into Stage 3, and Stage 3's posterior further
    propagated into Stage 4.

    Args:
        window: Day-5-6 active-perturbation window with phase structure.
        passive_fit_result: output of `run_staged_passive_batch_fit` —
            its final_posterior_mean and final_posterior_covariance carry
            the §5 stages' results that Stage 3 takes as informative prior
            on the §5 parameters.
        base_prior: the original ACCA Manual J fallback prior or PINN-
            derived prior. Used as the starting structure for prior
            propagation; the §5 staged posterior overrides its target
            parameter blocks.

    Raises:
        LaplaceFitFailed if Stage 3 or Stage 4 fails any production threshold.
    """
    # Build the Stage 3 prior: §5 staged posterior on (R_opaque, U_fenestration,
    # ceiling_coupling_factor, C_stack, C_wind), base prior on the rest.
    stage3_prior_mean = passive_fit_result.final_posterior_mean.copy()
    stage3_prior_cov = np.array(passive_fit_result.final_posterior_covariance, copy=True)
    # Ensure positive definiteness — small jitter on the diagonal if Cholesky fails
    try:
        np.linalg.cholesky(stage3_prior_cov)
    except np.linalg.LinAlgError:
        stage3_prior_cov = stage3_prior_cov + 1e-10 * np.eye(NUM_CANONICAL_PARAMETERS)
    stage3_prior = Prior7D(
        mean=stage3_prior_mean,
        covariance=stage3_prior_cov,
        provenance_descriptor=(
            f"{base_prior.provenance_descriptor}"
            f"|propagated_from_passive_stages_1_2"
        ),
        provenance_hash=base_prior.provenance_hash + "_passive_propagated",
        generated_timestamp_iso=base_prior.generated_timestamp_iso,
    )

    # Stage 3 — gating, C_house
    stage3_result = run_stage_active(
        STAGE_3,
        window,
        stage3_prior,
        forward_chain,
        context,
        dt_seconds=dt_seconds,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    # Propagate Stage 3 posterior as informative prior for Stage 4
    stage4_prior = propagate_posterior_as_prior(
        stage3_prior, stage3_result.laplace, STAGE_3.target_parameter_names
    )

    # Stage 4 — gating, C_w
    stage4_result = run_stage_active(
        STAGE_4,
        window,
        stage4_prior,
        forward_chain,
        context,
        dt_seconds=dt_seconds,
        mode_agreement_fraction=mode_agreement_fraction,
    )

    # Compose final posterior: §5 staged posterior + Stage 3 C_house + Stage 4 C_w
    final_mean = passive_fit_result.final_posterior_mean.copy()
    final_cov = np.array(passive_fit_result.final_posterior_covariance, copy=True)
    for name in STAGE_3.target_parameter_names:
        idx = _PARAM_INDEX[name]
        final_mean[idx] = stage3_result.laplace.posterior_mean[idx]
    for name in STAGE_4.target_parameter_names:
        idx = _PARAM_INDEX[name]
        final_mean[idx] = stage4_result.laplace.posterior_mean[idx]
    # Compose block-diagonal covariance: each stage's target block from its posterior
    s3_indices = [_PARAM_INDEX[n] for n in STAGE_3.target_parameter_names]
    s4_indices = [_PARAM_INDEX[n] for n in STAGE_4.target_parameter_names]
    active_target_indices = s3_indices + s4_indices
    for i in active_target_indices:
        for j in range(NUM_CANONICAL_PARAMETERS):
            if j in s3_indices and i in s3_indices:
                final_cov[i, j] = stage3_result.laplace.posterior_covariance[i, j]
            elif j in s4_indices and i in s4_indices:
                final_cov[i, j] = stage4_result.laplace.posterior_covariance[i, j]
            elif i != j:
                final_cov[i, j] = 0.0
    final_cov = 0.5 * (final_cov + final_cov.T)

    return StagedActiveFitResult(
        stage3=stage3_result,
        stage4=stage4_result,
        final_posterior_mean=final_mean,
        final_posterior_covariance=final_cov,
    )
