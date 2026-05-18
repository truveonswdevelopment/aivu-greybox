"""§G8-active-staged — Closed-loop §6 staged active fit against the real forward chain.

This is the §6 counterpart to `test_g8_staged_closed_loop.py`. Where the §5
G8-staged test (2026-05-17) validated Stages 1 + 2 recover R_opaque,
U_fenestration, and ceiling_coupling_factor against real Phase 1 +
aivu_dynamic physics at Cx duration (48h, 3-of-3), this test validates the
§6 active half: Stages 3 + 4 recover C_house and C_w against the same real
chain over the four-phase Day-4/5 active commissioning window.

Test pattern (per §10.2 closed-loop, staged structure per T3 v0.1):
  1. Choose a perturbed θ_true off the ACCA Manual J fallback prior mean.
  2. Synthesize a 48-hour Day-1/2 passive window from RealForwardChain at
     θ_true and run §5 staged passive fit to get the passive posterior.
  3. Synthesize a Day-4/5 active window (four-phase HVAC excitation) from
     RealForwardChain at θ_true.
  4. Run run_staged_active_batch_fit(...) with the §5 passive posterior
     as the active fit's prior on §5 parameters.
  5. Verify:
       - Stage 3 (gating): 95% CI on C_house covers θ_true.
       - Stage 4 (gating): 95% CI on C_w covers θ_true.
       - Posterior moves measurably from prior on at least one §6 parameter.

Both §6 stages are gating per T3 v0.1; failures raise rather than degrade
to best-effort. This is the §6 analogue of the §5 Stage 1 gating discipline.

Wall time: estimated 30-50 minutes per test. Each test re-runs the §5
passive fit before running §6. The §10.2 validation pattern intentionally
accepts the wall time as the cost of real-chain correctness.

[Ref: §6.3 amendment T3 v0.1 (2026-05-17);
      T7 staged_fit.py v0.1.1 (2026-05-17);
      G8-staged §5 validation 2026-05-17 (24h, 48h, 3/3);
      AIVU Temporal Identification Architecture v0.1;
      AIVU Critical Path Dependency Map v0.7.]
"""

from __future__ import annotations

import pytest

# Same dependency-import discipline as test_g8_staged_closed_loop.py.
aivu_physics = pytest.importorskip(
    "aivu_physics",
    reason="G8-active-staged closed-loop test requires aivu_physics to be installed",
)
aivu_dynamic = pytest.importorskip(
    "aivu_dynamic",
    reason="G8-active-staged closed-loop test requires aivu_dynamic to be installed",
)

import numpy as np

from aivu_greybox._signing_stub import _reset_log_for_testing
from aivu_greybox.active_fit import Day45TelemetryWindow, classify_samples_by_phase
from aivu_greybox.defaults import (
    CANONICAL_PARAMETER_NAMES,
    PHASE_A_DURATION_S,
    PHASE_B_DURATION_S,
    PHASE_C_DURATION_S,
    PHASE_D_DURATION_S,
)
from aivu_greybox.fan_heat import FanHeatSample, SHTReading, TerminalSample
from aivu_greybox.forward_chain import HVACExcitation, HomeStaticContext, WeatherSeries
from aivu_greybox.passive_fit_types import make_acca_manual_j_fallback_prior
from aivu_greybox.psychrometrics import (
    P_ATM_PHOENIX_PA,
    saturation_vapor_pressure_pa,
)
from aivu_greybox.real_chain import RealForwardChain
from aivu_greybox.staged_fit import (
    STAGE_3,
    STAGE_4,
    run_staged_active_batch_fit,
    run_staged_passive_batch_fit,
)

# Reuse the §5 real-chain synthesizer and Phoenix fixtures from G8 v0.1.
from test_g8_closed_loop import (
    THETA_TRUE_PERTURBED,
    _make_phoenix_site,
    _make_sim_config,
    _make_v752_context,
    _synthesize_day12_window_real_chain,
)


# ---------------------------------------------------------------------------
# Real-chain Day-4/5 synthesizer
# ---------------------------------------------------------------------------


def _synthesize_day45_window_real_chain(
    theta_true: np.ndarray,
    real_chain: RealForwardChain,
    context: HomeStaticContext,
    phase_durations_s: tuple[float, float, float, float] | None = None,
    eta_distribution: float = 0.90,
    fan_power_w: float = 400.0,
    cooling_capacity_w: float = 5000.0,
    moisture_removal_kg_per_s: float = 1.0e-4,
    total_mass_flow_kg_per_s: float = 0.6,
    obs_noise_t_attic_c: float = 0.02,
    obs_noise_t_main_c: float = 0.02,
    obs_noise_w_frac: float = 0.005,
    seed: int = 1234,
) -> Day45TelemetryWindow:
    """Day-4/5 active commissioning window driven by RealForwardChain.

    Structurally parallels `synthesize_day45_window` in test_active_fit.py
    but substitutes RealForwardChain for StubForwardChain. Same four-phase
    HVAC excitation, same Phoenix-July weather (real AMY 2024 EPW), same
    observation noise model. The forward chain is the only substitution.

    Returns a Day45TelemetryWindow at the full §6 spec duration
    (PHASE_A + PHASE_B + PHASE_C + PHASE_D, ~48h total under default
    spec values).
    """
    rng = np.random.default_rng(seed)

    if phase_durations_s is None:
        phase_durations_s = (
            PHASE_A_DURATION_S, PHASE_B_DURATION_S,
            PHASE_C_DURATION_S, PHASE_D_DURATION_S,
        )
    pa_dur, pb_dur, pc_dur, pd_dur = phase_durations_s
    total_dur = pa_dur + pb_dur + pc_dur + pd_dur
    n_samples = int(total_dur)

    # Phoenix-July from the real AMY 2024 EPW. The real-chain test assumes
    # the EPW file is present; absence is a setup error, not a fallback case.
    from aivu_greybox.epw_loader import phoenix_july_slice
    duration_h = max(1.0, n_samples / 3600.0)
    sl = phoenix_july_slice(start_day=15, start_hour=1, duration_hours=duration_h)
    t_outdoor = sl.t_outdoor_c[:n_samples].copy()
    rh_outdoor = sl.rh_outdoor_pct[:n_samples].copy()
    solar = sl.solar_global_w_per_m2[:n_samples].copy()
    wind = sl.wind_speed_m_per_s[:n_samples].copy()

    monotonic_ns = np.arange(n_samples, dtype=np.int64) * int(1e9)
    seconds_since_start = np.arange(n_samples, dtype=np.float64)

    phase_a_end = pa_dur
    phase_b_end = pa_dur + pb_dur
    phase_c_end = pa_dur + pb_dur + pc_dur

    # Fan schedule: Phase A continuous, B 10/50, C 50/10, D 10/50.
    fan_on = np.zeros(n_samples, dtype=bool)
    for i in range(n_samples):
        s = seconds_since_start[i]
        if s < phase_a_end:
            fan_on[i] = True
        elif s < phase_b_end:
            within_b = s - phase_a_end
            fan_on[i] = (within_b % 3600) < 600
        elif s < phase_c_end:
            within_c = s - phase_b_end
            fan_on[i] = (within_c % 3600) < 3000
        else:
            within_d = s - phase_c_end
            fan_on[i] = (within_d % 3600) < 600

    # HVAC excitation: Phase A compressor + fan; Phases B/C/D fan-only when on.
    q_sens_w = np.zeros(n_samples)
    m_lat = np.zeros(n_samples)
    for i in range(n_samples):
        s = seconds_since_start[i]
        if s < phase_a_end:
            q_sens_w[i] = -cooling_capacity_w + eta_distribution * fan_power_w
            m_lat[i] = -moisture_removal_kg_per_s
        elif fan_on[i]:
            q_sens_w[i] = eta_distribution * fan_power_w
            m_lat[i] = 0.0
        else:
            q_sens_w[i] = 0.0
            m_lat[i] = 0.0

    hvac = HVACExcitation(
        monotonic_ns=monotonic_ns, q_sens_w=q_sens_w, m_lat_kg_per_s=m_lat
    )
    weather = WeatherSeries(
        monotonic_ns=monotonic_ns,
        t_outdoor_c=t_outdoor,
        rh_outdoor_pct=rh_outdoor,
        solar_global_w_per_m2=solar,
        wind_speed_m_per_s=wind,
    )

    # Run REAL forward chain at θ_true to get the ground-truth trajectory.
    truth = real_chain.run(theta_true, hvac, weather, context)

    # Build per-sample telemetry from truth + noise. Pattern mirrors stub:
    # terminal warmup detection, supply-side vs attic-side targeting.
    samples: list[FanHeatSample] = []
    for i in range(n_samples):
        t_main_noisy = truth.t_main_c[i] + rng.normal(0, obs_noise_t_main_c)
        w_main_noisy = max(
            1e-5,
            truth.w_main_kg_per_kg[i] * (1.0 + rng.normal(0, obs_noise_w_frac)),
        )
        p_w_main = w_main_noisy * P_ATM_PHOENIX_PA / (0.62198 + w_main_noisy)
        rh_main = (p_w_main / saturation_vapor_pressure_pa(t_main_noisy)) * 100.0
        rh_main = float(np.clip(rh_main, 0.5, 99.5))

        s = seconds_since_start[i]
        in_warmup = False
        if fan_on[i]:
            t_in_fan_on = 0
            for j in range(i, -1, -1):
                if not fan_on[j]:
                    t_in_fan_on = i - j - 1
                    break
                if j == 0:
                    t_in_fan_on = i + 1
                    break
            in_warmup = t_in_fan_on < 60

        if in_warmup or not fan_on[i]:
            terminal_t_target = truth.t_attic_c[i]
        else:
            terminal_t_target = truth.t_main_c[i] + 0.3
            if s < phase_a_end:
                # Phase A supply is cold (cooling), not warmed.
                terminal_t_target = truth.t_main_c[i] - 8.0

        terminals = []
        for tidx in range(12):
            t_noisy = terminal_t_target + rng.normal(0, obs_noise_t_attic_c)
            p_w_term = w_main_noisy * P_ATM_PHOENIX_PA / (0.62198 + w_main_noisy)
            try:
                rh_term = (p_w_term / saturation_vapor_pressure_pa(t_noisy)) * 100.0
            except (ValueError, OverflowError):
                rh_term = 50.0
            rh_term = float(np.clip(rh_term, 0.5, 99.5))
            terminals.append(
                TerminalSample(
                    terminal_index=tidx,
                    sht=SHTReading(
                        temperature_c=t_noisy,
                        relative_humidity_pct=rh_term,
                    ),
                    mass_flow_kg_per_s=total_mass_flow_kg_per_s / 12 if fan_on[i] else 0.0,
                )
            )

        compressor_on = s < phase_a_end
        samples.append(
            FanHeatSample(
                monotonic_ns=int(monotonic_ns[i]),
                wall_clock_iso=f"2026-07-17T00:00:{i:010d}+00:00",
                terminals=tuple(terminals),
                return_plenum=SHTReading(
                    temperature_c=t_main_noisy,
                    relative_humidity_pct=rh_main,
                ),
                fan_power_w=fan_power_w if fan_on[i] else 0.0,
                compressor_on=compressor_on,
                heat_strip_on=False,
                aux_heat_on=False,
                oad_position=0.0,
                fan_on=bool(fan_on[i]),
            )
        )

    phase_index = classify_samples_by_phase(samples, phase_durations_s=phase_durations_s)
    return Day45TelemetryWindow(
        samples=tuple(samples),
        hvac_excitation_monotonic_ns=monotonic_ns,
        q_sens_w=q_sens_w,
        m_lat_kg_per_s=m_lat,
        weather_monotonic_ns=monotonic_ns,
        t_outdoor_c=t_outdoor,
        rh_outdoor_pct=rh_outdoor,
        solar_global_w_per_m2=solar,
        wind_speed_m_per_s=wind,
        phase_index=phase_index,
    )


# ---------------------------------------------------------------------------
# Closed-loop recovery — §6 staged active milestone
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestRealChainActiveStagedClosedLoopRecovery:
    """§6 staged-fit equivalent of the §5 G8-staged validation: Stages 3 + 4
    recover C_house and C_w against real Phase 1 + aivu_dynamic physics.

    Each test re-runs the full §5 + §6 pipeline via the `_run_full_pipeline`
    helper, paying the full cost per test. This mirrors the §5 G8-staged
    pattern where each test method independently runs the staged passive fit.
    """

    def setup_method(self):
        _reset_log_for_testing()

    def _run_full_pipeline(self, seed: int = 2026):
        """Build the real chain, run §5 to convergence, then run §6.

        Shared helper. Returns (active_result, base_prior) for assertion use.
        """
        site = _make_phoenix_site()
        sim_config = _make_sim_config()
        context = _make_v752_context()
        real_chain = RealForwardChain(site=site, sim_config=sim_config)
        base_prior = make_acca_manual_j_fallback_prior()

        # §5 passive: 48h Phoenix-July window — matches the G8-staged
        # validation that passed 3/3 at 48h.
        passive_window = _synthesize_day12_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            duration_hours=48.0,
            seed=seed,
        )
        passive_result = run_staged_passive_batch_fit(
            window=passive_window,
            base_prior=base_prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        # §6 active: full four-phase spec duration under default
        # PHASE_*_DURATION_S values from defaults.
        active_window = _synthesize_day45_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            seed=seed,
        )
        active_result = run_staged_active_batch_fit(
            window=active_window,
            passive_fit_result=passive_result,
            base_prior=base_prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        return active_result, base_prior

    def test_stage3_recovers_c_house_under_real_chain(self):
        """Stage 3 must hit 95% CI coverage on C_house against the real
        forward chain. Stage 3 is gating per T3 v0.1 — failure raises."""
        result, _ = self._run_full_pipeline(seed=2026)

        posterior_mean = result.final_posterior_mean
        posterior_cov = result.final_posterior_covariance
        posterior_sigmas = np.sqrt(np.diag(posterior_cov))

        per_param_log = []
        for name in STAGE_3.target_parameter_names:
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
                f"Stage 3 (gating) failed coverage on {name}.\n  "
                + "\n  ".join(per_param_log)
            )

    def test_stage4_recovers_c_w_under_real_chain(self):
        """Stage 4 must hit 95% CI coverage on C_w against the real
        forward chain. Stage 4 is gating per T3 v0.1 — failure raises."""
        result, _ = self._run_full_pipeline(seed=11)

        posterior_mean = result.final_posterior_mean
        posterior_cov = result.final_posterior_covariance
        posterior_sigmas = np.sqrt(np.diag(posterior_cov))

        per_param_log = []
        for name in STAGE_4.target_parameter_names:
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
                f"Stage 4 (gating) failed coverage on {name}.\n  "
                + "\n  ".join(per_param_log)
            )

    def test_posterior_moves_from_prior_on_active_parameters(self):
        """Sanity check: at least one §6 parameter posterior moves measurably
        from prior. Rules out collapse to the §5 posterior or to the ACCA
        fallback prior."""
        result, base_prior = self._run_full_pipeline(seed=2026)

        posterior_mean = result.final_posterior_mean
        prior_mean = base_prior.mean
        prior_sigmas = base_prior.marginal_sigmas

        active_param_names = list(STAGE_3.target_parameter_names) + list(
            STAGE_4.target_parameter_names
        )
        active_indices = [
            list(CANONICAL_PARAMETER_NAMES).index(name)
            for name in active_param_names
        ]
        movements_in_sigmas = np.abs(
            posterior_mean[active_indices] - prior_mean[active_indices]
        ) / prior_sigmas[active_indices]
        max_movement = float(np.max(movements_in_sigmas))

        per_param_log = {
            active_param_names[k]: float(movements_in_sigmas[k])
            for k in range(len(active_indices))
        }
        assert max_movement >= 0.3, (
            f"§6 posterior mean did not move measurably from prior mean: "
            f"max movement = {max_movement:.2f}σ across {active_param_names}. "
            f"Per-parameter (in σ): {per_param_log}"
        )
