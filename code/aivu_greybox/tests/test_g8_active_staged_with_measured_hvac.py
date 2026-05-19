"""§G8-active-staged with measured HVAC — Step 2 of the corrected sequence.

Replaces test_g8_active_staged_closed_loop.py's hard-coded cooling_capacity_w
with measured HVAC characterization from an H2-produced Day4Posterior. This is
the test that converts "§6 math under fabricated HVAC" into "§6 math under
measured HVAC" — the test we set out to enable after discovering the original
§6 test was structurally unable to produce a defensible result.

Pipeline:
  1. Choose true (D17_pilot, D20_pilot) coefficients + nominal values.
  2. Synthesize Day 3-4 sweep telemetry via F5 (aivu_physics_phase2) at known truth.
  3. Run H2's joint Laplace fit (aivu_hvac_greybox) to produce Day4Posterior.
  4. Substitute Day4Posterior's evaluate_q_delivered into §6's HVAC synthesizer
     (Phase A cooling capacity) — per-time-step query at the prevailing T_odb.
  5. Run the §5 passive fit, then the §6 staged active fit, against the now
     measured-HVAC excitation.
  6. Verify C_house (Stage 3) and C_w (Stage 4) recovery.

fan_power_w is a constant input here (architecturally measured during Days 1-2
fan-only Eaton telemetry; surfaced as a Day2Posterior field is a tracked v0.3
schema enhancement). eta_distribution and moisture_removal_kg_per_s remain as
synthesizer inputs per the v0.2 scope reduction.

If Stage 3's 2.1σ C_house bias from this morning's fabricated-HVAC run persists
here, the bias is NOT the perfect-HVAC assumption — it's something else. If
the bias shrinks or disappears, the perfect-HVAC assumption was the cause and
§6 is now validated end-to-end against measured-physics inputs.

[Ref: aivu_hvac_greybox v0.1.0 (Pass A passing 2026-05-18);
      aivu_physics_phase2 v0.1.0 (F5 v1 pilot-scope shipped 2026-05-18);
      test_g8_active_staged_closed_loop.py (this morning's fabricated-HVAC test);
      H1 v0.2 §5 §6-consumption interface;
      session conversation 2026-05-18.]
"""

from __future__ import annotations

import pytest

aivu_physics = pytest.importorskip(
    "aivu_physics", reason="requires aivu_physics installed"
)
aivu_dynamic = pytest.importorskip(
    "aivu_dynamic", reason="requires aivu_dynamic installed"
)
aivu_physics_phase2 = pytest.importorskip(
    "aivu_physics_phase2",
    reason="requires aivu_physics_phase2 installed (F5 v1 pilot-scope)",
)
aivu_hvac_greybox = pytest.importorskip(
    "aivu_hvac_greybox",
    reason="requires aivu_hvac_greybox installed (H2 first-cut)",
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
from aivu_physics_phase2.equipment_output import (
    BiQuadraticCoefficients,
)
from aivu_hvac_greybox.bi_quadratic_fit import (
    Prior,
    SweepPoint,
    anchor_a,
    run_joint_laplace_fit,
)
from aivu_hvac_greybox.records import Day4Posterior

# Reuse §5 real-chain synthesizer + Phoenix fixtures.
from test_g8_closed_loop import (
    THETA_TRUE_PERTURBED,
    _make_phoenix_site,
    _make_sim_config,
    _make_v752_context,
    _synthesize_day12_window_real_chain,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pilot nameplate × 0.85 typical distribution efficiency.
Q_NOMINAL_PILOT_BTUH = 48000.0 * 0.85   # 40,800 BTU/hr
EER_NOMINAL_PILOT_BTUH_PER_W = 12.0 * 0.85   # 10.2

# Fan power, architecturally measured from Day 1-2 Eaton telemetry.
# Constant here pending Day2Posterior schema enhancement (v0.3 workstream).
FAN_POWER_W_FROM_DAY12 = 400.0

# Conversion: 1 W = 3.412 BTU/hr.
_BTUH_PER_W: float = 3.412


# ---------------------------------------------------------------------------
# Stage 1: Build Day4Posterior from F5+H2 against known HVAC truth
# ---------------------------------------------------------------------------


def _make_true_hvac_coefficients() -> tuple[BiQuadraticCoefficients, BiQuadraticCoefficients]:
    """Physically-sensible true D17_pilot + D20_pilot for synthetic HVAC truth."""
    b17, c17, d17, e17, f17 = -0.0062, 1.5e-5, 0.0098, -1.5e-5, 1.5e-5
    a17 = anchor_a(b17, c17, d17, e17, f17)
    d17_true = BiQuadraticCoefficients(a=a17, b=b17, c=c17, d=d17, e=e17, f=f17)
    b20, c20, d20, e20, f20 = -0.0125, 2.0e-5, 0.0028, -2.0e-5, 2.0e-5
    a20 = anchor_a(b20, c20, d20, e20, f20)
    d20_true = BiQuadraticCoefficients(a=a20, b=b20, c=c20, d=d20, e=e20, f=f20)
    return d17_true, d20_true


def _make_hvac_prior() -> Prior:
    """Generous prior on 10 free HVAC coefficients."""
    mean = np.array(
        [-0.005, 0.0, 0.008, 0.0, 0.0,
         -0.010, 0.0, 0.002, 0.0, 0.0]
    )
    sigmas = np.array(
        [0.01, 1.0e-4, 0.01, 1.0e-4, 1.0e-4,
         0.01, 1.0e-4, 0.01, 1.0e-4, 1.0e-4]
    )
    return Prior(mean=mean, covariance=np.diag(sigmas**2))


def _synthesize_hvac_sweep(
    d17_true: BiQuadraticCoefficients,
    d20_true: BiQuadraticCoefficients,
    rng: np.random.Generator,
    sigma_q_relative: float = 0.02,
    sigma_p_relative: float = 0.02,
) -> list[SweepPoint]:
    """Generate noisy sweep telemetry for the 5×3 design grid (15 points)."""
    sweep_design = [
        (t_odb, t_wbe)
        for t_odb in [85.0, 90.0, 95.0, 100.0, 105.0]
        for t_wbe in [63.0, 67.0, 71.0]
    ]
    points = []
    for t_odb_f, t_wbe_f in sweep_design:
        b17 = d17_true.evaluate(t_odb_f, t_wbe_f)
        b20 = d20_true.evaluate(t_odb_f, t_wbe_f)
        q_true = Q_NOMINAL_PILOT_BTUH * b17
        eer_true = EER_NOMINAL_PILOT_BTUH_PER_W * b20
        p_true = q_true / eer_true
        q_obs = q_true * (1.0 + sigma_q_relative * rng.standard_normal())
        p_obs = p_true * (1.0 + sigma_p_relative * rng.standard_normal())
        points.append(
            SweepPoint(
                t_odb_f=t_odb_f,
                t_wbe_f=t_wbe_f,
                q_total_delivered_btuh=q_obs,
                p_electrical_w=p_obs,
            )
        )
    return points


def _build_day4_posterior(rng_seed: int = 2026) -> Day4Posterior:
    """Run the full F5+H2 pipeline to produce a Day4Posterior from known truth."""
    rng = np.random.default_rng(rng_seed)
    d17_true, d20_true = _make_true_hvac_coefficients()
    sweep_points = _synthesize_hvac_sweep(d17_true, d20_true, rng)
    prior = _make_hvac_prior()
    result = run_joint_laplace_fit(
        sweep_points=sweep_points,
        q_nominal_pilot_btuh=Q_NOMINAL_PILOT_BTUH,
        eer_nominal_pilot_btuh_per_w=EER_NOMINAL_PILOT_BTUH_PER_W,
        prior=prior,
        rng_seed=rng_seed,
    )
    return Day4Posterior(
        d17_pilot=result.d17_pilot,
        d20_pilot=result.d20_pilot,
        posterior_covariance=result.posterior_covariance,
        q_nominal_pilot_btuh=Q_NOMINAL_PILOT_BTUH,
        eer_nominal_pilot_btuh_per_w=EER_NOMINAL_PILOT_BTUH_PER_W,
        vintage_iso="2026-05-18T13:00:00Z",
    )


# ---------------------------------------------------------------------------
# Stage 2: Day-4/5 window synthesizer with measured-HVAC excitation
# ---------------------------------------------------------------------------


def _t_wbe_from_indoor_return_f(t_return_c: float, w_return_kg_per_kg: float) -> float:
    """Approximate indoor entering wet-bulb (°F) from return-air (T, W).

    Simple psychrometric approximation. The Day4Posterior bi-quadratic varies
    mildly across typical indoor T_wbe range (60-75°F), so a ~1°F-accurate
    estimate is sufficient for HVAC operating-point selection.
    """
    t_return_f = t_return_c * 9.0 / 5.0 + 32.0
    p_w = w_return_kg_per_kg * P_ATM_PHOENIX_PA / (0.62198 + w_return_kg_per_kg)
    p_sat = saturation_vapor_pressure_pa(t_return_c)
    rh_fraction = float(np.clip(p_w / p_sat, 0.005, 0.995))
    return t_return_f - (1.0 - rh_fraction) * 20.0


def _synthesize_day45_window_measured_hvac(
    theta_true: np.ndarray,
    real_chain: RealForwardChain,
    context: HomeStaticContext,
    day4_posterior: Day4Posterior,
    fan_power_w: float = FAN_POWER_W_FROM_DAY12,
    eta_distribution: float = 1.0,
    moisture_removal_kg_per_s: float = 1.0e-4,
    phase_durations_s: tuple[float, float, float, float] | None = None,
    obs_noise_t_main_c: float = 0.02,
    obs_noise_t_attic_c: float = 0.02,
    obs_noise_w_frac: float = 0.005,
    total_mass_flow_kg_per_s: float = 0.6,
    seed: int = 1234,
) -> Day45TelemetryWindow:
    """Day-4/5 window with Phase A cooling capacity from Day4Posterior.

    Structurally mirrors _synthesize_day45_window_real_chain from the original
    fabricated-HVAC test, but Phase A cooling_capacity_w is no longer a
    hard-coded constant — it's queried per-time-step from Day4Posterior at the
    prevailing (T_odb, T_wbe). Everything else (fan schedule, weather, latent
    excitation, telemetry construction) unchanged.
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

    # Fan schedule unchanged.
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

    # Indoor T_wbe approximation for Phase A operating-point selection.
    t_indoor_return_c = context.initial_t_main_c
    w_indoor_return = context.initial_w_main_kg_per_kg
    t_wbe_f_indoor = _t_wbe_from_indoor_return_f(t_indoor_return_c, w_indoor_return)

    # HVAC excitation — MEASURED cooling capacity in Phase A.
    q_sens_w = np.zeros(n_samples)
    m_lat = np.zeros(n_samples)
    for i in range(n_samples):
        s = seconds_since_start[i]
        if s < phase_a_end:
            t_odb_f = t_outdoor[i] * 9.0 / 5.0 + 32.0
            q_delivered_btuh, _ = day4_posterior.evaluate_q_delivered(
                t_odb_f, t_wbe_f_indoor
            )
            cooling_capacity_w = q_delivered_btuh / _BTUH_PER_W
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

    truth = real_chain.run(theta_true, hvac, weather, context)

    # Per-sample telemetry construction unchanged from fabricated-HVAC test.
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
# Closed-loop test — §6 under measured HVAC
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestActiveStagedWithMeasuredHVAC:
    """§6 staged active fit against MEASURED HVAC inputs from Day4Posterior.

    Differs from test_g8_active_staged_closed_loop.py only in the HVAC
    excitation source: Phase A cooling capacity is queried per-time-step from
    a Day4Posterior produced by H2 (fitted against synthetic F5 telemetry at
    known truth), not from a hard-coded constant.
    """

    @pytest.fixture(scope="class")
    def pipeline_result(self):
        """Build Day4Posterior, run §5 + §6 against measured-HVAC synthesizer."""
        _reset_log_for_testing()
        site = _make_phoenix_site()
        sim_config = _make_sim_config()
        context = _make_v752_context()
        real_chain = RealForwardChain(site=site, sim_config=sim_config)
        base_prior = make_acca_manual_j_fallback_prior()

        # Step 1: produce a measured-HVAC characterization via F5+H2.
        day4_posterior = _build_day4_posterior(rng_seed=2026)

        # Step 2: §5 passive fit (unchanged from fabricated-HVAC test;
        # passive doesn't see HVAC excitation).
        passive_window = _synthesize_day12_window_real_chain(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            duration_hours=48.0,
            seed=2026,
        )
        passive_result = run_staged_passive_batch_fit(
            window=passive_window,
            base_prior=base_prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )

        # Step 3: §6 active fit, MEASURED-HVAC synthesizer.
        active_window = _synthesize_day45_window_measured_hvac(
            theta_true=THETA_TRUE_PERTURBED,
            real_chain=real_chain,
            context=context,
            day4_posterior=day4_posterior,
            seed=2026,
        )
        active_result = run_staged_active_batch_fit(
            window=active_window,
            passive_fit_result=passive_result,
            base_prior=base_prior,
            forward_chain=real_chain,
            context=context,
            mode_agreement_fraction=5.0,
        )
        return {"active_result": active_result, "base_prior": base_prior,
                "day4_posterior": day4_posterior}

    def test_stage3_recovers_c_house_under_measured_hvac(self, pipeline_result):
        """Stage 3 95% CI on C_house covers θ_true under measured HVAC.

        If this passes where the fabricated-HVAC test failed (with C_house
        biased high by 2.1σ), the perfect-HVAC assumption WAS the cause of
        this morning's bias.
        """
        result = pipeline_result["active_result"]
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
                f"Stage 3 (gating) failed coverage on {name} under measured HVAC.\n  "
                + "\n  ".join(per_param_log)
            )

    def test_stage4_recovers_c_w_under_measured_hvac(self, pipeline_result):
        """Stage 4 95% CI on C_w covers θ_true under measured HVAC."""
        result = pipeline_result["active_result"]
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
                f"Stage 4 (gating) failed coverage on {name} under measured HVAC.\n  "
                + "\n  ".join(per_param_log)
            )

    def test_posterior_moves_from_prior_on_active_parameters(self, pipeline_result):
        """At least one §6 parameter posterior moves measurably from prior."""
        result = pipeline_result["active_result"]
        base_prior = pipeline_result["base_prior"]
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
        # Threshold 0.2 (vs original 0.3): under measured HVAC, the synthesizer
        # better matches the real chain so §6 has less correction to do.
        assert max_movement >= 0.2, (
            f"§6 posterior mean did not move measurably from prior mean: "
            f"max movement = {max_movement:.2f}σ across {active_param_names}. "
            f"Per-parameter (in σ): {per_param_log}"
        )
