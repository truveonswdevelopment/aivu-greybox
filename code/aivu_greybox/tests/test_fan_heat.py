"""Tests for `aivu_greybox.fan_heat` — the §4 Fan-Heat Consistency Check.

The test strategy: construct synthetic 1-Hz telemetry windows with KNOWN
underlying η_distribution, run them through `run_fan_heat_check`, and verify:

  1. The identified η̂ matches the synthetic ground truth within the
     expected uncertainty (closed-loop §4 recovery test).
  2. The pass/fail adjudication is correct for the synthetic conditions.
  3. INV-FH-2 rejection fires on intentionally non-conforming windows.
  4. Signed records are produced per §12 with the stub-attestation flag set.

Phoenix-July ambient is the reference test environment.
"""

from __future__ import annotations

import math
import random
import pytest

from aivu_greybox._signing_stub import _reset_log_for_testing
from aivu_greybox.defaults import (
    FH_DELTA_W_MAX,
    FH_ETA_MAX,
    FH_ETA_MIN,
    FH_SIGMA_SPATIAL_MAX_KJ_PER_KG,
    FH_TAU_FH_MIN,
    FH_TAU_WARMUP_S,
)
from aivu_greybox.fan_heat import (
    FanHeatSample,
    FanHeatWindowInvalid,
    SHTReading,
    TerminalSample,
    run_fan_heat_check,
)
from aivu_greybox.psychrometrics import (
    P_ATM_PHOENIX_PA,
    humidity_ratio,
    moist_air_enthalpy_kj_per_kg,
)
from aivu_greybox.records import FanHeatFail, FanHeatFailureMode, FanHeatPass


# ---------------------------------------------------------------------------
# Synthetic-telemetry generators
# ---------------------------------------------------------------------------


def _make_terminal(
    terminal_index: int,
    return_temp_c: float,
    return_rh_pct: float,
    eta_truth: float,
    p_fan_w: float,
    total_mass_flow_kg_per_s: float,
    noise_seed: int,
) -> TerminalSample:
    """Build one terminal sample where the enthalpy rise is set by the
    target η_distribution.

    The synthetic model: under perfect-conservation fan-only operation,
    the fan delivers η * P_fan watts as enthalpy rise distributed uniformly
    across the 12 terminals. Each terminal sees:

        Δh = (η * P_fan) / (m_dot * 12)   [if we assume equal flow]

    So h_terminal = h_return + Δh, and we back out (T_terminal, RH_terminal)
    such that the enthalpy matches. Approximation: we keep RH ≈ return RH
    (mostly-sensible heating under fan operation) and adjust T to match h.

    Sensirion SHT35 noise: ±0.1 °C, ±1.5% RH. Add gaussian noise within those
    bands (seeded per-terminal for reproducibility in tests).
    """
    rng = random.Random(noise_seed + terminal_index)

    # Mass flow per terminal: distribute total_mass_flow uniformly across 12
    m_dot_terminal = total_mass_flow_kg_per_s / 12.0

    # Each terminal sees η*P_fan / 12 of the delivered enthalpy rise
    # The total per-second enthalpy delivered (kJ/s) is:
    delivered_kw = eta_truth * (p_fan_w / 1000.0)
    delivered_per_terminal_kw = delivered_kw / 12.0
    # Δh per terminal in kJ/kg = (kJ/s) / (kg/s)
    delta_h = delivered_per_terminal_kw / m_dot_terminal if m_dot_terminal > 0 else 0.0

    # Return state
    w_return = humidity_ratio(return_temp_c, return_rh_pct, P_ATM_PHOENIX_PA)
    h_return = moist_air_enthalpy_kj_per_kg(return_temp_c, w_return)

    # Target terminal enthalpy
    h_terminal_target = h_return + delta_h

    # Back out terminal T assuming RH stays at return RH (sensible fan-heat)
    # h = 1.006*T + W*(2501 + 1.86*T)
    # Solving for T given h and the same W (approximation):
    # h = (1.006 + W*1.86)*T + W*2501
    # T = (h - W*2501) / (1.006 + W*1.86)
    t_terminal = (h_terminal_target - w_return * 2501.0) / (1.006 + w_return * 1.86)

    # Add SHT35 noise: in real telemetry, time-averaging over 30+ minutes
    # reduces the per-sample noise floor substantially. The Sensirion SHT35
    # spec is ±0.1 °C and ±1.5% RH at 1σ for a single reading, but the
    # Fan-Heat protocol time-averages over ~1800 samples; what's left after
    # averaging is dominated by systematic calibration scatter (per-probe
    # offsets that don't average out), at the 0.01-0.02 °C and 0.1-0.2% RH
    # level. The synthetic fixture models that residual scatter directly,
    # not the per-sample noise floor.
    t_noisy = t_terminal + rng.gauss(0.0, 0.01)
    # Convert humidity back from W → RH at the noisy temperature
    # RH = P_w / P_ws * 100
    from aivu_greybox.psychrometrics import saturation_vapor_pressure_pa

    p_w = w_return * P_ATM_PHOENIX_PA / (0.62198 + w_return)
    rh_at_terminal = (p_w / saturation_vapor_pressure_pa(t_noisy)) * 100.0
    rh_at_terminal = max(0.1, min(99.9, rh_at_terminal + rng.gauss(0.0, 0.1)))

    return TerminalSample(
        terminal_index=terminal_index,
        sht=SHTReading(temperature_c=t_noisy, relative_humidity_pct=rh_at_terminal),
        mass_flow_kg_per_s=m_dot_terminal,
    )


def make_fan_heat_window(
    duration_s: float,
    eta_truth: float,
    *,
    return_temp_c: float = 26.0,
    return_rh_pct: float = 35.0,
    fan_power_w: float = 400.0,
    total_mass_flow_kg_per_s: float = 0.6,  # ~1300 CFM at standard density
    operational_overrides: dict | None = None,
    return_humidity_drift_kg_per_kg: float = 0.0,
    spatial_imbalance_kj_per_kg: float = 0.0,
    seed: int = 42,
) -> list[FanHeatSample]:
    """Generate a synthetic 1-Hz Fan-Heat telemetry window with known truth.

    Args:
        duration_s: Total window duration in seconds.
        eta_truth: The true η_distribution embedded in the synthetic enthalpy rise.
        return_temp_c, return_rh_pct: Return-plenum state, held constant unless
            return_humidity_drift_kg_per_kg > 0.
        fan_power_w: Constant fan power throughout the window.
        total_mass_flow_kg_per_s: Sum across the 12 terminals.
        operational_overrides: dict of {sample_index: dict-of-attrs-to-override}
            for testing INV-FH-2 violations (e.g. a sample with compressor_on=True).
        return_humidity_drift_kg_per_kg: If > 0, return-side W drifts linearly
            over the window by this amount (for INV-FH-2 moisture-stability tests).
        spatial_imbalance_kj_per_kg: If > 0, terminal index 0 reads ΔH higher than
            the other 11 by this amount (for INV-FH-2 spatial-uniformity tests).
        seed: RNG seed for SHT noise.

    Returns:
        List of FanHeatSample objects at 1 Hz.
    """
    operational_overrides = operational_overrides or {}
    samples: list[FanHeatSample] = []
    n_samples = int(duration_s)

    for i in range(n_samples):
        # Linear humidity drift across the window (only used for INV-FH-2 tests)
        progress = i / max(n_samples - 1, 1)
        if return_humidity_drift_kg_per_kg != 0.0:
            w_target = (
                humidity_ratio(return_temp_c, return_rh_pct, P_ATM_PHOENIX_PA)
                + return_humidity_drift_kg_per_kg * progress
            )
            # Compute the RH corresponding to (return_temp_c, w_target)
            from aivu_greybox.psychrometrics import saturation_vapor_pressure_pa

            p_w_target = w_target * P_ATM_PHOENIX_PA / (0.62198 + w_target)
            rh_i = (p_w_target / saturation_vapor_pressure_pa(return_temp_c)) * 100.0
            rh_i = max(0.1, min(99.9, rh_i))
        else:
            rh_i = return_rh_pct

        return_sht = SHTReading(
            temperature_c=return_temp_c, relative_humidity_pct=rh_i
        )

        # Build 12 terminals
        terminals = []
        for term_idx in range(12):
            t_sample = _make_terminal(
                terminal_index=term_idx,
                return_temp_c=return_temp_c,
                return_rh_pct=rh_i,
                eta_truth=eta_truth,
                p_fan_w=fan_power_w,
                total_mass_flow_kg_per_s=total_mass_flow_kg_per_s,
                noise_seed=seed + i,
            )
            # Spatial imbalance: bump terminal 0
            if term_idx == 0 and spatial_imbalance_kj_per_kg != 0.0:
                # Add an offset to the temperature to produce the enthalpy bump.
                w_t = humidity_ratio(
                    t_sample.sht.temperature_c,
                    t_sample.sht.relative_humidity_pct,
                    P_ATM_PHOENIX_PA,
                )
                delta_t = spatial_imbalance_kj_per_kg / (1.006 + w_t * 1.86)
                new_t = t_sample.sht.temperature_c + delta_t
                t_sample = TerminalSample(
                    terminal_index=term_idx,
                    sht=SHTReading(
                        temperature_c=new_t,
                        relative_humidity_pct=t_sample.sht.relative_humidity_pct,
                    ),
                    mass_flow_kg_per_s=t_sample.mass_flow_kg_per_s,
                )
            terminals.append(t_sample)

        # Build the sample
        sample_attrs = {
            "monotonic_ns": int(i * 1e9),
            "wall_clock_iso": f"2026-07-15T12:{i // 60:02d}:{i % 60:02d}+00:00",
            "terminals": tuple(terminals),
            "return_plenum": return_sht,
            "fan_power_w": fan_power_w,
            "compressor_on": False,
            "heat_strip_on": False,
            "aux_heat_on": False,
            "oad_position": 0.0,
            "fan_on": True,
        }
        # Apply any operational overrides
        if i in operational_overrides:
            sample_attrs.update(operational_overrides[i])

        samples.append(FanHeatSample(**sample_attrs))

    return samples


# ---------------------------------------------------------------------------
# Recovery tests: η̂ should match η_truth
# ---------------------------------------------------------------------------


class TestFanHeatRecovery:
    """Closed-loop §4 recovery: known η in, η̂ out, check the match."""

    def setup_method(self):
        _reset_log_for_testing()

    @pytest.mark.parametrize("eta_truth", [0.88, 0.90, 0.92, 0.94])
    def test_eta_recovery_at_various_truths(self, eta_truth):
        # Build a clean Phoenix-July fan-heat window with this η truth
        duration = FH_TAU_FH_MIN + 5 * 60  # comfortable margin
        samples = make_fan_heat_window(duration_s=duration, eta_truth=eta_truth)
        result = run_fan_heat_check(samples, home_id="V752_pilot")

        # Recovery should be within a couple percent at the synthetic noise levels
        assert result.is_pass
        assert isinstance(result.record, FanHeatPass)
        assert result.record.common.eta_distribution_hat == pytest.approx(
            eta_truth, rel=2e-2
        )

    def test_pass_record_carries_eps_fh_used(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        # Per INV-FH-3, the tolerances actually used are part of the record
        assert result.record.common.eps_fh_used > 0
        assert result.record.common.eta_min_used == FH_ETA_MIN
        assert result.record.common.eta_max_used == FH_ETA_MAX


# ---------------------------------------------------------------------------
# Pass/fail adjudication
# ---------------------------------------------------------------------------


class TestPassFailAdjudication:
    def setup_method(self):
        _reset_log_for_testing()

    def test_passes_in_range(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        assert result.is_pass
        assert isinstance(result.record, FanHeatPass)
        assert result.failure_mode is None

    def test_fails_eta_below_range(self):
        # η = 0.70 is well below FH_ETA_MIN (0.85)
        # The synthetic generator delivers this in clean physics; the residual
        # check ε_FH may still pass since the model is consistent — only the
        # range check trips.
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.70)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        assert not result.is_pass
        assert isinstance(result.record, FanHeatFail)
        # Either pure-range or BOTH (if residual also fails); in either case
        # the η-out-of-range condition is part of the diagnosis
        assert result.failure_mode in (
            FanHeatFailureMode.ETA_OUT_OF_RANGE,
            FanHeatFailureMode.BOTH,
        )

    def test_fails_eta_above_range(self):
        # η = 0.99 is above FH_ETA_MAX (0.96)
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.99)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        assert not result.is_pass
        assert result.failure_mode in (
            FanHeatFailureMode.ETA_OUT_OF_RANGE,
            FanHeatFailureMode.BOTH,
        )


# ---------------------------------------------------------------------------
# INV-FH-2 enforcement
# ---------------------------------------------------------------------------


class TestINV_FH_2_Enforcement:
    """Per §4 spec: implementations MUST reject non-conforming windows
    rather than compute on them."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_rejects_window_too_short(self):
        # Window shorter than FH_TAU_FH_MIN
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN - 60, eta_truth=0.90)
        with pytest.raises(FanHeatWindowInvalid) as exc_info:
            run_fan_heat_check(samples, home_id="V752_pilot")
        assert "duration" in str(exc_info.value).lower()

    def test_rejects_window_with_compressor_on(self):
        # Inject a single compressor-on sample mid-window
        samples = make_fan_heat_window(
            duration_s=FH_TAU_FH_MIN + 60,
            eta_truth=0.90,
            operational_overrides={500: {"compressor_on": True}},
        )
        with pytest.raises(FanHeatWindowInvalid) as exc_info:
            run_fan_heat_check(samples, home_id="V752_pilot")
        assert "operational-mode" in str(exc_info.value).lower()

    def test_rejects_window_with_heat_strip_on(self):
        samples = make_fan_heat_window(
            duration_s=FH_TAU_FH_MIN + 60,
            eta_truth=0.90,
            operational_overrides={100: {"heat_strip_on": True}},
        )
        with pytest.raises(FanHeatWindowInvalid):
            run_fan_heat_check(samples, home_id="V752_pilot")

    def test_rejects_window_with_open_oad(self):
        samples = make_fan_heat_window(
            duration_s=FH_TAU_FH_MIN + 60,
            eta_truth=0.90,
            operational_overrides={200: {"oad_position": 0.5}},
        )
        with pytest.raises(FanHeatWindowInvalid):
            run_fan_heat_check(samples, home_id="V752_pilot")

    def test_rejects_moisture_drift(self):
        # Drift larger than FH_DELTA_W_MAX
        samples = make_fan_heat_window(
            duration_s=FH_TAU_FH_MIN + 60,
            eta_truth=0.90,
            return_humidity_drift_kg_per_kg=FH_DELTA_W_MAX * 5,  # well above
        )
        with pytest.raises(FanHeatWindowInvalid) as exc_info:
            run_fan_heat_check(samples, home_id="V752_pilot")
        assert "moisture" in str(exc_info.value).lower() or "W drift" in str(exc_info.value)

    def test_rejects_spatial_imbalance(self):
        # One terminal reads enthalpy substantially higher than the others
        samples = make_fan_heat_window(
            duration_s=FH_TAU_FH_MIN + 60,
            eta_truth=0.90,
            spatial_imbalance_kj_per_kg=FH_SIGMA_SPATIAL_MAX_KJ_PER_KG * 5,
        )
        with pytest.raises(FanHeatWindowInvalid) as exc_info:
            run_fan_heat_check(samples, home_id="V752_pilot")
        assert "spatial" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# §12 signing-chain integration
# ---------------------------------------------------------------------------


class TestSigningIntegration:
    """Per §12 INV-SIGN12-1 and INV-SIGN12-2: every record signed and
    appended to the log in the sign_record → commit_to_log sequence."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_pass_produces_signed_record_with_stub_flag(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")

        # The signed record carries the stub flag (INV-SIGN12-4 analog —
        # sign_record itself flags as stub in v0.1)
        assert result.signed.is_stub_signature is True

    def test_pass_produces_inclusion_proof(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")

        # Inclusion proof is non-empty and references the record's hash
        assert result.inclusion_proof.record_hash == result.signed.record_hash
        assert result.inclusion_proof.log_head_hash_at_append != "GENESIS"

    def test_post_hoc_retrieval(self):
        """INV-SIGN12-6 — signed records retrievable by content-addressed hash."""
        from aivu_greybox._signing_stub.integrity_api import _retrieve_by_hash_for_testing

        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")

        retrieved = _retrieve_by_hash_for_testing(result.signed.record_hash)
        assert retrieved is not None
        assert retrieved.record_hash == result.signed.record_hash

    def test_fail_records_also_signed_and_logged(self):
        """Per INV-FH-3 + §4 fail-mode: FanHeatFail records are signed and
        logged regardless of which condition failed."""
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.70)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        assert not result.is_pass
        assert result.signed.is_stub_signature is True
        assert result.inclusion_proof.record_hash == result.signed.record_hash

    def test_monotonic_timestamps_strictly_increasing(self):
        """INV-SIGN12-7."""
        from aivu_greybox._signing_stub.integrity_api import _log

        for i in range(3):
            samples = make_fan_heat_window(
                duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90, seed=i * 100
            )
            run_fan_heat_check(samples, home_id=f"V752_pilot_run{i}")

        # The log now has 3 entries with strictly-increasing monotonic timestamps
        timestamps = [e.monotonic_timestamp.nanoseconds for e in _log.entries]
        for a, b in zip(timestamps, timestamps[1:]):
            assert b > a, "Monotonic timestamps must be strictly increasing"


# ---------------------------------------------------------------------------
# INV-FH-3 record completeness
# ---------------------------------------------------------------------------


class TestRecordCompleteness:
    """INV-FH-3: an external verifier MUST be able to re-derive η̂_distribution
    and R_FH from the signed record + the underlying telemetry packets.
    Test: the record has every field the spec §4.5 requires."""

    def setup_method(self):
        _reset_log_for_testing()

    def test_pass_record_has_all_required_fields(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.90)
        result = run_fan_heat_check(samples, home_id="V752_pilot")

        signable = result.record.to_signable()
        required_fields = {
            "record_type",
            "home_id",
            "window_start_monotonic_ns",
            "window_end_monotonic_ns",
            "window_start_wallclock_iso",
            "window_end_wallclock_iso",
            "eta_distribution_hat",
            "eta_distribution_sigma",
            "r_fh",
            "r_fh_relative",
            "eps_fh_used",
            "eta_min_used",
            "eta_max_used",
            "fan_power_avg_w",
            "return_humidity_drift_kg_per_kg",
            "spatial_enthalpy_stddev_kj_per_kg",
            "samples_consumed",
        }
        assert required_fields.issubset(signable.keys()), (
            f"Missing fields: {required_fields - signable.keys()}"
        )

    def test_fail_record_carries_failure_mode(self):
        samples = make_fan_heat_window(duration_s=FH_TAU_FH_MIN + 60, eta_truth=0.70)
        result = run_fan_heat_check(samples, home_id="V752_pilot")
        signable = result.record.to_signable()
        assert signable["record_type"] == "FanHeatFail"
        assert "failure_mode" in signable
