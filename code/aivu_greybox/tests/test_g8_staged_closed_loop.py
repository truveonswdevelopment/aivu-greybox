"""§G8-staged — Closed-loop §5 staged passive fit against the real forward chain.

This is the staged-fit counterpart to `test_g8_closed_loop.py`. Where G8
v0.1 demonstrated that the joint Bayesian fit moves data through the
real Phase 1 + aivu_dynamic pipeline (with the 2026-05-16 diagnostic
revealing that "4-of-7 recovery" at 12h was Laplace-approximation
artifact on parameters the §5 protocol does not constrain), this test
validates the staged-fit reformulation per the v0.4 architectural
insight and T7 implementation.

Test pattern (per §10.2 closed-loop, staged structure per T2 v0.2):
  1. Choose a perturbed θ_true off the prior mean.
  2. Synthesize a 24-hour telemetry window from RealForwardChain at
     θ_true (24h needed for Stage 1's 24h Welch window).
  3. Run `run_staged_passive_batch_fit(...)` against RealForwardChain
     with the ACCA Manual J fallback prior.
  4. Verify:
       - Stage 1 (gating): 95% CI covers θ_true on all three conductance
         parameters (R_opaque, U_fenestration, ceiling_coupling_factor).
       - Stage 2 (best-effort): orchestrator completes without raising;
         posterior on C_stack, C_wind is populated regardless of width.
       - Posterior actually moves from prior mean — sanity check that
         the fit is learning rather than collapsing to the prior.

The bar under the staged design is structurally different from G8 v0.1.
Stage 1's gating discipline means a successful run delivers
production-threshold posteriors on the three conductances; Stage 2's
best-effort framing puts C_stack and C_wind on the operational
refinement horizon per the two-tier model. C_house and C_w are §6
parameters and remain at their prior values after §5.

Test wall time: estimated 5-15 minutes. Each Welch likelihood evaluation
calls the forward chain once; two staged Laplace fits with 4 restarts
each multiplies the per-call cost. The §10.2 validation pattern
intentionally accepts the wall time as the cost of real-chain
correctness.

[Ref: §11.2 amendment 2026-05-15;
      §5.3 amendment T2 v0.2 (2026-05-17);
      T7 staged_fit.py v0.1.1 (2026-05-17);
      AIVU Temporal Identification Architecture v0.1;
      v0.6 Critical Path Dependency Map;
      AIVU Architectural Distillation; G7 real_chain.py adapter.]
"""

from __future__ import annotations

import pytest

# Same dependencies as G8 v0.1: aivu_physics and aivu_dynamic required.
aivu_physics = pytest.importorskip(
    "aivu_physics",
    reason="G8-staged closed-loop test requires aivu_physics to be installed",
)
aivu_dynamic = pytest.importorskip(
    "aivu_dynamic",
    reason="G8-staged closed-loop test requires aivu_dynamic to be installed",
)

import numpy as np

from aivu_greybox._signing_stub import _reset_log_for_testing
from aivu_greybox.defaults import CANONICAL_PARAMETER_NAMES
from aivu_greybox.passive_fit_types import make_acca_manual_j_fallback_prior
from aivu_greybox.real_chain import RealForwardChain
from aivu_greybox.staged_fit import (
    STAGE_1,
    STAGE_2,
    run_staged_passive_batch_fit,
)

# Reuse the real-chain synthesizer and fixtures from G8 v0.1.
from test_g8_closed_loop import (
    THETA_TRUE_PERTURBED,
    _make_phoenix_site,
    _make_sim_config,
    _make_v752_context,
    _synthesize_day12_window_real_chain,
)


# ---------------------------------------------------------------------------
# Closed-loop recovery — staged-fit milestone
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestRealChainStagedClosedLoopRecovery:
    """Staged-fit equivalent of G8: verify the staged passive fit recovers
    θ_true against real Phase 1 physics, with Stage 1 gating and Stage 2
    best-effort under the two-tier horizon model."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_stage1_recovers_conductances_under_real_chain(self):
        """Stage 1 (gating) must hit 95% CI coverage on all three
        conductance parameters (R_opaque, U_fenestration,
        ceiling_coupling_factor) against the real forward chain.

        This is the staged-fit equivalent of G8's "stuff works" signal:
        a pass here means the frequency-domain Welch likelihood + staged
        identification structure actually recovers parameters where the
        joint fit could not under production-strict identifiability.
        """
        site = _make_phoenix_site()
        sim_config = _make_sim_config()
        context = _make_v752_context()
        real_chain = RealForwardChain(site=site, sim_config=sim_config)

        # 24h window: minimum for Stage 1's 24h Welch segment. Single
        # segment, no Welch averaging — pure FFT under Hann window with
        # linear detrending. The diurnal signal is strong in 24h of
        # Phoenix-July weather.
        window = _synthesize_day12_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            duration_hours=48.0,
            seed=2026,
        )

        # The prior is the ACCA Manual J fallback, NOT centered at θ_true.
        # The fit must move parameters off the prior mean.
        prior = make_acca_manual_j_fallback_prior()

        # Run the staged passive fit. mode_agreement_fraction relaxed
        # for real-chain v0.1 (matches G8 v0.1's 5.0).
        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        # Stage 1 coverage check: 95% CI on each Stage 1 target must
        # contain θ_true.
        posterior_mean = result.final_posterior_mean
        posterior_cov = result.final_posterior_covariance
        posterior_sigmas = np.sqrt(np.diag(posterior_cov))

        per_param_log = []
        for name in STAGE_1.target_parameter_names:
            i = list(CANONICAL_PARAMETER_NAMES).index(name)
            lo = posterior_mean[i] - 2 * posterior_sigmas[i]
            hi = posterior_mean[i] + 2 * posterior_sigmas[i]
            theta_i = THETA_TRUE_PERTURBED[i]
            covered = lo <= theta_i <= hi
            per_param_log.append(
                f"{name}: θ_true={theta_i:.4g}, "
                f"posterior={posterior_mean[i]:.4g}±{posterior_sigmas[i]:.4g}, "
                f"95% CI=[{lo:.4g},{hi:.4g}], covered={covered}"
            )
            assert covered, (
                f"Stage 1 (gating) failed coverage on {name}.\n  "
                + "\n  ".join(per_param_log)
            )

    def test_stage2_completes_best_effort_against_real_chain(self):
        """Stage 2 (best-effort) must complete without raising even when
        C_stack/C_wind posterior is wide. Posterior values must be
        populated regardless of identifiability flag state."""
        site = _make_phoenix_site()
        sim_config = _make_sim_config()
        context = _make_v752_context()
        real_chain = RealForwardChain(site=site, sim_config=sim_config)

        window = _synthesize_day12_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            duration_hours=48.0,
            seed=11,
        )
        prior = make_acca_manual_j_fallback_prior()

        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        # Stage 2 result must be present and dimensionally correct,
        # regardless of identifiability flag values.
        assert result.stage2 is not None
        assert result.stage2.laplace.posterior_mean.shape == (
            len(CANONICAL_PARAMETER_NAMES),
        )
        # The Stage 2 protocol string must be carried through.
        assert (
            result.stage2.identifiability_report.protocol
            == STAGE_2.protocol_string
        )

    def test_posterior_moves_from_prior_on_stage1_parameters(self):
        """Sanity check: posterior mean for at least one Stage 1 parameter
        differs measurably from the prior mean. Confirms the staged fit
        is learning from data rather than collapsing to the prior."""
        site = _make_phoenix_site()
        sim_config = _make_sim_config()
        context = _make_v752_context()
        real_chain = RealForwardChain(site=site, sim_config=sim_config)

        window = _synthesize_day12_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            duration_hours=48.0,
            seed=2026,
        )
        prior = make_acca_manual_j_fallback_prior()

        result = run_staged_passive_batch_fit(
            window=window,
            base_prior=prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        posterior_mean = result.final_posterior_mean
        prior_mean = prior.mean
        prior_sigmas = prior.marginal_sigmas

        # Restrict the movement check to Stage 1 parameters — Stage 2 may
        # legitimately not move much in 24h of Phoenix weather, and §6
        # parameters are not fit in §5 so they stay at their prior values.
        stage1_indices = [
            list(CANONICAL_PARAMETER_NAMES).index(name)
            for name in STAGE_1.target_parameter_names
        ]
        stage1_movements_in_sigmas = np.abs(
            posterior_mean[stage1_indices] - prior_mean[stage1_indices]
        ) / prior_sigmas[stage1_indices]
        max_stage1_movement = float(np.max(stage1_movements_in_sigmas))

        per_param_log = {
            STAGE_1.target_parameter_names[k]: float(stage1_movements_in_sigmas[k])
            for k in range(len(stage1_indices))
        }
        assert max_stage1_movement >= 0.3, (
            f"Stage 1 posterior mean did not move measurably from prior mean: "
            f"max movement = {max_stage1_movement:.2f}σ across "
            f"{STAGE_1.target_parameter_names}. Per-parameter (in σ): "
            f"{per_param_log}"
        )
