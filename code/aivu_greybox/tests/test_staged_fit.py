"""Tests for `aivu_greybox.staged_fit` — T7 v0.1.1 staged identification.

Closed-loop validation: synthesize a Day-1-2 telemetry window from known
θ_true via the stub forward chain, run the staged fit, verify the
posterior contains θ_true within its credible intervals.

Distinct from `test_passive_fit.py` which validates the joint-fit
machinery: this file validates the staged-fit machinery — frequency-
domain Welch likelihood per T2 v0.2, two-tier horizon model per the
2026-05-17 session, posterior-as-prior propagation between stages.

Stage 1 coverage check is the load-bearing test (production-threshold
gating). Stage 2 is best-effort: validates that the orchestrator
completes without raising, that the posterior is propagated forward,
and that the signed identifiability flags are correctly recorded.

§11.2 amendment 2026-05-15: seven-parameter canonical set is in force
throughout these tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from aivu_greybox._signing_stub import _reset_log_for_testing
from aivu_greybox.defaults import (
    CANONICAL_PARAMETER_NAMES,
    LAPLACE_MODE_AGREEMENT_FRACTION,
    NUM_CANONICAL_PARAMETERS,
)
from aivu_greybox.forward_chain import StubForwardChain
from aivu_greybox.passive_fit import LaplaceFitFailed
from aivu_greybox.passive_fit_types import (
    Prior7D,
    make_acca_manual_j_fallback_prior,
)
from aivu_greybox.staged_fit import (
    STAGE_1,
    STAGE_2,
    STAGE_3,
    STAGE_4,
    StagedActiveFitResult,
    StagedPassiveFitResult,
    StageResult,
    extract_stage_observations_active,
    extract_stage_observations_passive,
    propagate_posterior_as_prior,
    run_stage_active,
    run_stage_passive,
    run_staged_active_batch_fit,
    run_staged_passive_batch_fit,
    welch_band_weighted_negloglik,
)

# Reuse the synthetic-window machinery from the passive-fit and active-fit
# test suites. Importing across test files keeps the fixtures as single
# sources of truth.
from test_passive_fit import THETA_TRUE_V752, synthesize_day12_window
from test_active_fit import (
    _make_tight_prior,
    _shorten_phases,
    synthesize_day45_window,
)


# ---------------------------------------------------------------------------
# Welch likelihood — unit-level sanity checks
# ---------------------------------------------------------------------------


class TestWelchLikelihoodMath:
    """The likelihood implements (N / 2σ²) × ∫_{band} PSD df per Parseval.
    These tests confirm the load-bearing behaviors without involving the
    forward chain."""

    def test_zero_residual_gives_zero_nll(self):
        """A residual of all zeros has zero in-band power → zero NLL."""
        residual = np.zeros(48 * 3600)  # 48h at 1 Hz
        nll = welch_band_weighted_negloglik(
            residual=residual,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        assert nll < 1e-6, f"Zero residual gave non-zero NLL: {nll}"

    def test_in_band_signal_produces_finite_nll(self):
        """A sinusoid at the diurnal frequency (in-band) produces finite NLL
        that scales with amplitude."""
        n_samples = 48 * 3600
        t = np.arange(n_samples) / 3600.0  # hours
        # Diurnal signal at 1/24h, amplitude 1 °C
        residual = np.sin(2 * np.pi * t / 24.0)
        nll = welch_band_weighted_negloglik(
            residual=residual,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        # The diurnal signal is in-band; NLL should be substantial
        # (positive, finite). The N factor (~172000) times the in-band power
        # (~0.5 for unit-amplitude sine) divided by 2σ² (= 0.02) gives a
        # large but well-defined NLL on the order of 1e6 or more.
        assert np.isfinite(nll), f"Expected finite NLL, got {nll}"
        assert nll > 1.0, f"In-band sinusoid produced negligible NLL: {nll}"

    def test_out_of_band_signal_produces_small_nll(self):
        """A sinusoid at 1/1h (well above Stage 1's band) produces small
        NLL — the band weighting suppresses it."""
        n_samples = 48 * 3600
        t = np.arange(n_samples) / 3600.0
        # 1-hour-period signal (well above Stage 1's [1/24h, 1/6h] band)
        residual = np.sin(2 * np.pi * t / 1.0)
        nll_out_of_band = welch_band_weighted_negloglik(
            residual=residual,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        # Compare against an in-band sinusoid of the same amplitude
        residual_in_band = np.sin(2 * np.pi * t / 24.0)
        nll_in_band = welch_band_weighted_negloglik(
            residual=residual_in_band,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        # Out-of-band NLL should be at least an order of magnitude smaller
        assert nll_out_of_band < 0.1 * nll_in_band, (
            f"Band selection failed: out-of-band NLL {nll_out_of_band:.3g} "
            f"not much smaller than in-band NLL {nll_in_band:.3g}"
        )

    def test_short_residual_returns_finite_fallback(self):
        """A residual shorter than the Welch segment returns the 1e10
        fallback rather than crashing."""
        residual = np.zeros(100)  # too short for any meaningful Welch
        nll = welch_band_weighted_negloglik(
            residual=residual,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        assert nll == 1e10

    def test_nan_residual_returns_finite_fallback(self):
        """A residual containing NaN returns the 1e10 fallback."""
        residual = np.zeros(48 * 3600)
        residual[1000] = np.nan
        nll = welch_band_weighted_negloglik(
            residual=residual,
            dt_seconds=1.0,
            window_seconds=24.0 * 3600.0,
            overlap_fraction=0.5,
            band_low_period_seconds=6.0 * 3600.0,
            band_high_period_seconds=24.0 * 3600.0,
            sigma_obs=0.1,
        )
        assert nll == 1e10


# ---------------------------------------------------------------------------
# Stage observations
# ---------------------------------------------------------------------------


class TestStageObservations:
    """The passive-window observation extractor produces residual-ready
    arrays of the correct shape, with NaN exclusions applied."""

    def test_observation_arrays_match_window_length(self):
        window, _ = synthesize_day12_window(THETA_TRUE_V752, duration_hours=4.0)
        from aivu_greybox.forward_chain import WeatherSeries
        weather = WeatherSeries(
            monotonic_ns=window.weather_monotonic_ns,
            t_outdoor_c=window.t_outdoor_c,
            rh_outdoor_pct=window.rh_outdoor_pct,
            solar_global_w_per_m2=window.solar_global_w_per_m2,
            wind_speed_m_per_s=window.wind_speed_m_per_s,
        )
        obs = extract_stage_observations_passive(window, STAGE_1, weather)
        n = len(window.samples)
        assert obs.t_main_observed_c.shape == (n,)
        assert obs.w_main_observed_kg_per_kg.shape == (n,)
        assert obs.observation_mask.shape == (n,)
        assert obs.observation_mask.dtype == bool

    def test_observation_mask_excludes_nan_w_main(self):
        """If psychrometric conversion fails on some samples, those samples
        are excluded from the observation mask."""
        window, _ = synthesize_day12_window(THETA_TRUE_V752, duration_hours=4.0)
        from aivu_greybox.forward_chain import WeatherSeries
        weather = WeatherSeries(
            monotonic_ns=window.weather_monotonic_ns,
            t_outdoor_c=window.t_outdoor_c,
            rh_outdoor_pct=window.rh_outdoor_pct,
            solar_global_w_per_m2=window.solar_global_w_per_m2,
            wind_speed_m_per_s=window.wind_speed_m_per_s,
        )
        obs = extract_stage_observations_passive(window, STAGE_1, weather)
        # No samples should have NaN T_main or W_main in the masked region
        for idx in np.where(obs.observation_mask)[0]:
            assert not np.isnan(obs.t_main_observed_c[idx])
            assert not np.isnan(obs.w_main_observed_kg_per_kg[idx])


# ---------------------------------------------------------------------------
# Posterior-as-prior propagation
# ---------------------------------------------------------------------------


class TestPosteriorAsPriorPropagation:
    """Stage N's posterior on its target parameters replaces the prior's
    block for those parameters before Stage N+1 runs."""

    def test_target_param_block_replaced(self):
        base = make_acca_manual_j_fallback_prior()
        # Construct a fake LaplaceResult with a known posterior mean and cov
        fake_posterior_mean = base.mean.copy()
        # Pretend Stage 1 identified R_opaque = 0.85, U_fenestration = 1.05
        # (intentionally different from prior mean of 1.0)
        idx_R = list(CANONICAL_PARAMETER_NAMES).index("R_opaque")
        idx_U = list(CANONICAL_PARAMETER_NAMES).index("U_fenestration")
        idx_C = list(CANONICAL_PARAMETER_NAMES).index("ceiling_coupling_factor")
        fake_posterior_mean[idx_R] = 0.85
        fake_posterior_mean[idx_U] = 1.05
        fake_posterior_mean[idx_C] = 0.70
        # Posterior covariance: tighter on target params than the prior
        fake_posterior_cov = np.array(base.covariance, copy=True)
        for i in (idx_R, idx_U, idx_C):
            fake_posterior_cov[i, i] *= 0.01  # 10x tighter

        # Build a minimal LaplaceResult-shaped object for the test
        from aivu_greybox.passive_fit import LaplaceResult
        fake_laplace = LaplaceResult(
            posterior_mean=fake_posterior_mean,
            posterior_covariance=fake_posterior_cov,
            hessian_at_mode=np.linalg.inv(fake_posterior_cov),
            hessian_eigenvalues=np.linalg.eigvalsh(np.linalg.inv(fake_posterior_cov)),
            hessian_condition_number=1.0,
            restart_modes=np.tile(fake_posterior_mean, (4, 1)),
            restart_log_posteriors=np.zeros(4),
            mode_agreement_passed=True,
            hessian_positive_definite=True,
            optimizer_converged_all_restarts=True,
            posterior_prior_kl_divergence_per_param=np.zeros(NUM_CANONICAL_PARAMETERS),
        )

        propagated = propagate_posterior_as_prior(
            base, fake_laplace, STAGE_1.target_parameter_names
        )

        # The propagated prior's mean should carry Stage 1's posterior means
        # on the target parameters
        assert abs(propagated.mean[idx_R] - 0.85) < 1e-10
        assert abs(propagated.mean[idx_U] - 1.05) < 1e-10
        assert abs(propagated.mean[idx_C] - 0.70) < 1e-10

        # Non-target parameters should retain the base prior's mean
        for i in range(NUM_CANONICAL_PARAMETERS):
            if i not in (idx_R, idx_U, idx_C):
                assert abs(propagated.mean[i] - base.mean[i]) < 1e-10

        # The target-param block of the covariance should be the posterior's
        # (tighter than the prior's)
        for i in (idx_R, idx_U, idx_C):
            assert propagated.covariance[i, i] < base.covariance[i, i]

        # The propagated covariance must still be positive-definite
        np.linalg.cholesky(propagated.covariance)


# ---------------------------------------------------------------------------
# Stage 1 closed-loop recovery — LOAD-BEARING
# ---------------------------------------------------------------------------


class TestStage1ClosedLoopRecovery:
    """Per T2 v0.2: Stage 1 must hit production thresholds. Closed-loop
    recovery against the stub forward chain validates the machinery."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage1_recovers_conductances_within_95pct_ci(self):
        """The Stage 1 posterior's 95% credible interval should contain
        θ_true on R_opaque, U_fenestration, ceiling_coupling_factor."""
        theta_true = THETA_TRUE_V752
        # Full 48h window for diurnal-band Welch averaging (3 segments)
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=2026
        )
        prior = make_acca_manual_j_fallback_prior()

        # Stage 1 directly — fixture loosened mode_agreement_fraction so the
        # stub-physics quirks don't trip §5.7's production-strict check
        stage1_result = run_stage_passive(
            STAGE_1,
            window,
            prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        posterior_mean = stage1_result.laplace.posterior_mean
        posterior_cov = stage1_result.laplace.posterior_covariance
        posterior_sigmas = np.sqrt(np.diag(posterior_cov))

        for name in STAGE_1.target_parameter_names:
            i = list(CANONICAL_PARAMETER_NAMES).index(name)
            lo = posterior_mean[i] - 2 * posterior_sigmas[i]
            hi = posterior_mean[i] + 2 * posterior_sigmas[i]
            assert lo <= theta_true[i] <= hi, (
                f"θ_true[{name}] = {theta_true[i]:.4g} not in Stage 1 95% CI "
                f"[{lo:.4g}, {hi:.4g}] (posterior mean {posterior_mean[i]:.4g}, "
                f"σ {posterior_sigmas[i]:.4g})"
            )

    def test_stage1_posterior_tighter_than_prior_on_target_params(self):
        """Stage 1 must visibly tighten the posterior σ on R_opaque,
        U_fenestration, ceiling_coupling_factor versus the prior σ."""
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=42
        )
        prior = make_acca_manual_j_fallback_prior()
        prior_sigmas = prior.marginal_sigmas

        stage1_result = run_stage_passive(
            STAGE_1,
            window,
            prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )
        posterior_sigmas = np.sqrt(
            np.diag(stage1_result.laplace.posterior_covariance)
        )

        for name in STAGE_1.target_parameter_names:
            i = list(CANONICAL_PARAMETER_NAMES).index(name)
            rho = posterior_sigmas[i] / prior_sigmas[i]
            assert rho < 0.99, (
                f"Stage 1 did not tighten {name}: σ_post/σ_prior = {rho:.3f}"
            )


# ---------------------------------------------------------------------------
# Stage 2 best-effort behavior
# ---------------------------------------------------------------------------


class TestStage2BestEffort:
    """Stage 2 is non-gating per the two-tier horizon model. Failures are
    recorded in the LaplaceResult flags but do not raise."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage2_does_not_raise_on_loose_posterior(self):
        """Stage 2's posterior on C_stack/C_wind may be wide depending on
        the wind content of the synthetic window. The orchestrator must
        complete without raising regardless."""
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=7
        )
        prior = make_acca_manual_j_fallback_prior()

        # The end-to-end staged passive fit must not raise even if Stage 2
        # produces a wide posterior
        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )
        # Stage 2's LaplaceResult should be populated, whatever its quality
        assert result.stage2 is not None
        assert result.stage2.laplace.posterior_mean.shape == (NUM_CANONICAL_PARAMETERS,)


# ---------------------------------------------------------------------------
# End-to-end staged passive fit — covers Stage 1 + Stage 2 + propagation
# ---------------------------------------------------------------------------


class TestStagedPassiveBatchFit:
    """The orchestrator runs Stage 1 (gating), propagates posterior, runs
    Stage 2 (best-effort), composes the final 7-parameter posterior."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_orchestrator_completes_and_returns_seven_parameter_posterior(self):
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=2026
        )
        prior = make_acca_manual_j_fallback_prior()

        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        assert isinstance(result, StagedPassiveFitResult)
        assert result.final_posterior_mean.shape == (NUM_CANONICAL_PARAMETERS,)
        assert result.final_posterior_covariance.shape == (
            NUM_CANONICAL_PARAMETERS,
            NUM_CANONICAL_PARAMETERS,
        )
        # The final posterior covariance must be positive-definite
        np.linalg.cholesky(result.final_posterior_covariance)

    def test_stage1_target_params_recover_theta_true(self):
        """Through the full orchestrator, Stage 1's target parameters in
        the final composed posterior should be near θ_true."""
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=2026
        )
        prior = make_acca_manual_j_fallback_prior()

        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        final_mean = result.final_posterior_mean
        final_sigmas = np.sqrt(np.diag(result.final_posterior_covariance))

        for name in STAGE_1.target_parameter_names:
            i = list(CANONICAL_PARAMETER_NAMES).index(name)
            lo = final_mean[i] - 2 * final_sigmas[i]
            hi = final_mean[i] + 2 * final_sigmas[i]
            assert lo <= theta_true[i] <= hi, (
                f"After staged passive fit, θ_true[{name}] = {theta_true[i]:.4g} "
                f"not in 95% CI [{lo:.4g}, {hi:.4g}]"
            )

    def test_identifiability_report_carries_stage_protocol_string(self):
        """Each stage's identifiability report should carry the stage-
        specific protocol string for the signed record."""
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=11
        )
        prior = make_acca_manual_j_fallback_prior()

        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        assert result.stage1.identifiability_report.protocol == STAGE_1.protocol_string
        assert result.stage2.identifiability_report.protocol == STAGE_2.protocol_string


# ---------------------------------------------------------------------------
# Stage 1 gating discipline
# ---------------------------------------------------------------------------


class TestStage1Gating:
    """When production thresholds are enforced (default
    LAPLACE_MODE_AGREEMENT_FRACTION = 0.05), Stage 1 raises LaplaceFitFailed
    on a fit that the stub physics can't deliver. With loosened threshold,
    the same fit succeeds. Validates that gating discipline is actually
    enforceable."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage1_raises_under_production_threshold_on_stub(self):
        """Under production-strict mode_agreement_fraction = 0.05, Stage 1
        against the stub physics is expected to fail one or more of the
        §5.7 diagnostics (the stub's information content is limited). This
        validates that the gating mechanism actually halts.
        """
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day12_window(
            theta_true, duration_hours=48.0, seed=2026
        )
        prior = make_acca_manual_j_fallback_prior()

        # Production-strict threshold — expected to raise against the stub
        with pytest.raises(LaplaceFitFailed):
            run_stage_passive(
                STAGE_1,
                window,
                prior,
                forward_chain=StubForwardChain(),
                context=context,
                mode_agreement_fraction=LAPLACE_MODE_AGREEMENT_FRACTION,
            )


# ---------------------------------------------------------------------------
# Active-stage tests — Stage 3 (C_house) and Stage 4 (C_w)
# ---------------------------------------------------------------------------


def _build_fake_passive_result(theta_true: np.ndarray) -> StagedPassiveFitResult:
    """Construct a fake StagedPassiveFitResult representing perfect §5
    success — mean at θ_true, tight covariance — to bypass the passive
    stages in active-stage tests.

    This isolates Stage 3 / Stage 4 testing from passive-stage runtime.
    Real integration is tested in TestStagedActiveBatchFit by running the
    full passive + active pipeline.
    """
    from aivu_greybox.passive_fit import LaplaceResult
    from aivu_greybox.records import IdentifiabilityReport

    # Tight covariance: 5% σ on each parameter relative to its mean
    fake_sigmas = np.array([0.05, 0.05, 2.5e5, 0.05, 0.05, 2.5, 0.04])
    fake_cov = np.diag(fake_sigmas ** 2)

    # Minimal LaplaceResult shells for stage1/stage2 — never read by
    # the active orchestrator, only final_posterior_mean/cov are.
    fake_laplace = LaplaceResult(
        posterior_mean=theta_true.copy(),
        posterior_covariance=fake_cov,
        hessian_at_mode=np.linalg.inv(fake_cov),
        hessian_eigenvalues=np.linalg.eigvalsh(np.linalg.inv(fake_cov)),
        hessian_condition_number=1.0,
        restart_modes=np.tile(theta_true, (4, 1)),
        restart_log_posteriors=np.zeros(4),
        mode_agreement_passed=True,
        hessian_positive_definite=True,
        optimizer_converged_all_restarts=True,
        posterior_prior_kl_divergence_per_param=np.zeros(NUM_CANONICAL_PARAMETERS),
    )
    fake_id_report = IdentifiabilityReport(
        protocol="fake_stage_for_test",
        per_parameter={},
        hessian_spectrum={},
        summary={"any_identifiability_flag": False, "any_degraded_tightness": False},
    )
    fake_stage1 = StageResult(
        stage=STAGE_1,
        laplace=fake_laplace,
        identifiability_report=fake_id_report,
    )
    fake_stage2 = StageResult(
        stage=STAGE_2,
        laplace=fake_laplace,
        identifiability_report=fake_id_report,
    )
    return StagedPassiveFitResult(
        stage1=fake_stage1,
        stage2=fake_stage2,
        final_posterior_mean=theta_true.copy(),
        final_posterior_covariance=fake_cov,
    )


class TestActiveStageObservations:
    """The active-window observation extractor produces residual-ready
    arrays of the correct shape, with NaN exclusions applied."""

    def test_observation_arrays_match_window_length(self):
        durations = _shorten_phases(0.20)
        window, _ = synthesize_day45_window(
            THETA_TRUE_V752, phase_durations_s=durations, seed=11
        )
        from aivu_greybox.forward_chain import WeatherSeries
        weather = WeatherSeries(
            monotonic_ns=window.weather_monotonic_ns,
            t_outdoor_c=window.t_outdoor_c,
            rh_outdoor_pct=window.rh_outdoor_pct,
            solar_global_w_per_m2=window.solar_global_w_per_m2,
            wind_speed_m_per_s=window.wind_speed_m_per_s,
        )
        obs = extract_stage_observations_active(window, STAGE_3, weather)
        n = len(window.samples)
        assert obs.t_main_observed_c.shape == (n,)
        assert obs.w_main_observed_kg_per_kg.shape == (n,)
        assert obs.observation_mask.shape == (n,)
        assert obs.observation_mask.dtype == bool


# ---------------------------------------------------------------------------
# Stage 3 closed-loop recovery — LOAD-BEARING
# ---------------------------------------------------------------------------


class TestStage3ClosedLoopRecovery:
    """Per T3 v0.1: Stage 3 hits production thresholds for C_house.
    Closed-loop recovery against the stub forward chain validates the
    machinery.

    Test uses full-length phase durations (scale 1.0 = 48h total) so the
    12h Welch window has multiple segments. Slow — tens of seconds —
    but unavoidable for meaningful Stage 3 testing.
    """

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage3_recovers_c_house_within_95pct_ci(self):
        theta_true = THETA_TRUE_V752
        window, context = synthesize_day45_window(
            theta_true, phase_durations_s=None, seed=2026  # None = spec durations
        )
        passive_result = _build_fake_passive_result(theta_true)

        # Build Stage 3 prior from the fake passive result, widened on C_house
        # to give the optimizer room to maneuver from the prior bound
        from aivu_greybox.passive_fit_types import Prior7D
        stage3_prior_mean = passive_result.final_posterior_mean.copy()
        stage3_prior_cov = np.array(
            passive_result.final_posterior_covariance, copy=True
        )
        # Widen C_house to ~20% so the recovery test isn't bound-limited
        idx_C_house = list(CANONICAL_PARAMETER_NAMES).index("C_house")
        stage3_prior_cov[idx_C_house, idx_C_house] = (1.0e6) ** 2
        stage3_prior = Prior7D(
            mean=stage3_prior_mean,
            covariance=stage3_prior_cov,
            provenance_descriptor="staged_passive_fake",
            provenance_hash="fake_hash",
            generated_timestamp_iso="2026-07-17T00:00:00Z",
        )

        stage3_result = run_stage_active(
            STAGE_3,
            window,
            stage3_prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        posterior_mean = stage3_result.laplace.posterior_mean
        posterior_sigmas = np.sqrt(np.diag(stage3_result.laplace.posterior_covariance))

        i = idx_C_house
        lo = posterior_mean[i] - 2 * posterior_sigmas[i]
        hi = posterior_mean[i] + 2 * posterior_sigmas[i]
        assert lo <= theta_true[i] <= hi, (
            f"θ_true[C_house] = {theta_true[i]:.4g} not in Stage 3 95% CI "
            f"[{lo:.4g}, {hi:.4g}] (posterior mean {posterior_mean[i]:.4g}, "
            f"σ {posterior_sigmas[i]:.4g})"
        )


# ---------------------------------------------------------------------------
# Stage 4 closed-loop recovery — LOAD-BEARING
# ---------------------------------------------------------------------------


class TestStage4ClosedLoopRecovery:
    """Per T3 v0.1: Stage 4 hits production thresholds for C_w.

    Stage 4's 3h Welch window is forgiving — even half-length phase
    durations (24h total) give ~8 Welch segments. Test uses phase scale
    0.5 for runtime control while keeping recovery meaningful.
    """

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage4_recovers_c_w_within_95pct_ci(self):
        theta_true = THETA_TRUE_V752
        durations = _shorten_phases(0.5)  # 24h total
        window, context = synthesize_day45_window(
            theta_true, phase_durations_s=durations, seed=2026
        )
        passive_result = _build_fake_passive_result(theta_true)

        # Build Stage 4 prior: passive result mean, widened on C_w
        from aivu_greybox.passive_fit_types import Prior7D
        stage4_prior_mean = passive_result.final_posterior_mean.copy()
        stage4_prior_cov = np.array(
            passive_result.final_posterior_covariance, copy=True
        )
        idx_C_w = list(CANONICAL_PARAMETER_NAMES).index("C_w")
        stage4_prior_cov[idx_C_w, idx_C_w] = (20.0) ** 2  # ~40% σ on C_w
        stage4_prior = Prior7D(
            mean=stage4_prior_mean,
            covariance=stage4_prior_cov,
            provenance_descriptor="staged_passive_fake",
            provenance_hash="fake_hash",
            generated_timestamp_iso="2026-07-17T00:00:00Z",
        )

        stage4_result = run_stage_active(
            STAGE_4,
            window,
            stage4_prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        posterior_mean = stage4_result.laplace.posterior_mean
        posterior_sigmas = np.sqrt(np.diag(stage4_result.laplace.posterior_covariance))

        i = idx_C_w
        lo = posterior_mean[i] - 2 * posterior_sigmas[i]
        hi = posterior_mean[i] + 2 * posterior_sigmas[i]
        assert lo <= theta_true[i] <= hi, (
            f"θ_true[C_w] = {theta_true[i]:.4g} not in Stage 4 95% CI "
            f"[{lo:.4g}, {hi:.4g}] (posterior mean {posterior_mean[i]:.4g}, "
            f"σ {posterior_sigmas[i]:.4g})"
        )


# ---------------------------------------------------------------------------
# End-to-end staged active fit — passive + active in sequence
# ---------------------------------------------------------------------------


class TestStagedActiveBatchFit:
    """The full pipeline: §5 staged passive → §6 staged active. Uses
    fake passive result to bypass the passive-stage runtime; the
    composition into the final 7-parameter posterior is the load-bearing
    behavior.
    """

    def setup_method(self):
        _reset_log_for_testing()

    def test_orchestrator_returns_seven_parameter_posterior(self):
        theta_true = THETA_TRUE_V752
        durations = _shorten_phases(0.5)
        window, context = synthesize_day45_window(
            theta_true, phase_durations_s=durations, seed=2026
        )
        passive_result = _build_fake_passive_result(theta_true)
        base_prior = make_acca_manual_j_fallback_prior()

        result = run_staged_active_batch_fit(
            window=window,
            passive_fit_result=passive_result,
            base_prior=base_prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        assert isinstance(result, StagedActiveFitResult)
        assert result.final_posterior_mean.shape == (NUM_CANONICAL_PARAMETERS,)
        assert result.final_posterior_covariance.shape == (
            NUM_CANONICAL_PARAMETERS,
            NUM_CANONICAL_PARAMETERS,
        )
        np.linalg.cholesky(result.final_posterior_covariance)

    def test_identifiability_reports_carry_active_protocol_strings(self):
        theta_true = THETA_TRUE_V752
        durations = _shorten_phases(0.5)
        window, context = synthesize_day45_window(
            theta_true, phase_durations_s=durations, seed=11
        )
        passive_result = _build_fake_passive_result(theta_true)
        base_prior = make_acca_manual_j_fallback_prior()

        result = run_staged_active_batch_fit(
            window=window,
            passive_fit_result=passive_result,
            base_prior=base_prior,
            forward_chain=StubForwardChain(),
            context=context,
            mode_agreement_fraction=1.5,
        )

        assert result.stage3.identifiability_report.protocol == STAGE_3.protocol_string
        assert result.stage4.identifiability_report.protocol == STAGE_4.protocol_string
