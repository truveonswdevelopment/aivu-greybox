"""§4 — Fan-Heat Consistency Check.

Per §4.1, the Fan-Heat check runs on the Day-1 fan-only window. It
simultaneously:

  (i)  Verifies that the calibrated sensor stack (12 supply-terminal SHT35s,
       1 return-plenum SHT35, the per-terminal Marmon Venturis, the
       Eaton-breaker electrical measurement) is internally consistent under
       a known-physics regime (fan-only, no compressor, no heat strip);
  (ii) Identifies η_distribution — the calibration coefficient relating fan
       electrical input to delivered enthalpy at the terminals — as a per-
       home quantity. This becomes the Day-1 prior for §6 active-perturbation
       refinement per INV-FH-4.

The §4 check is steady-state. No envelope dynamics; no forward chain. The
HVAC is in a known idle configuration; the only thermodynamic event is the
fan motor's electrical input being converted into a small but measurable
enthalpy rise at the supply terminals.

Implementation reads telemetry (12 supply + 1 return SHT35 readings, fan
electrical, fan power) at 1 Hz across a τ_FH-minimum window, validates the
window per INV-FH-2, identifies η̂_distribution, and emits either a
FanHeatPass (signed and logged) or a FanHeatFail (signed and logged with
the failure-mode flag).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from .defaults import (
    FH_DELTA_W_MAX,
    FH_EPS_FH,
    FH_ETA_MAX,
    FH_ETA_MIN,
    FH_SIGMA_SPATIAL_MAX_KJ_PER_KG,
    FH_TAU_FH_MIN,
    FH_TAU_WARMUP_S,
)
from .psychrometrics import P_ATM_PHOENIX_PA, state_from_sht_reading
from .records import (
    FanHeatFail,
    FanHeatFailureMode,
    FanHeatPass,
    FanHeatRecordCommon,
)
from ._signing_stub import (
    LogInclusionProof,
    SignedRecord,
    commit_to_log,
    sign_record,
)

# ---------------------------------------------------------------------------
# Telemetry input types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SHTReading:
    """A single SHT35 reading at one sample timestamp."""

    temperature_c: float
    relative_humidity_pct: float


@dataclass(frozen=True)
class TerminalSample:
    """One 1-Hz sample of the per-terminal SHT35 plus its Venturi mass-flow."""

    terminal_index: int  # 0..11 for the 12 supply terminals
    sht: SHTReading
    mass_flow_kg_per_s: float


@dataclass(frozen=True)
class FanHeatSample:
    """One 1-Hz sample of the full Fan-Heat-relevant telemetry stack."""

    monotonic_ns: int
    wall_clock_iso: str

    terminals: tuple[TerminalSample, ...]  # length 12 per Hardware Spec v1.1
    return_plenum: SHTReading
    fan_power_w: float

    # Operational-mode flags (used to enforce INV-FH-2)
    compressor_on: bool
    heat_strip_on: bool
    aux_heat_on: bool
    oad_position: float  # delta_OAD: 0.0 = closed; INV-FH-2 requires this be 0
    fan_on: bool

    def is_fan_only_idle(self) -> bool:
        """All non-fan HVAC components are off; OAD is closed; fan is on.

        This is the operational-mode condition INV-FH-2 demands.
        """
        return (
            self.fan_on
            and not self.compressor_on
            and not self.heat_strip_on
            and not self.aux_heat_on
            and self.oad_position == 0.0
        )


# ---------------------------------------------------------------------------
# Window validity check — INV-FH-2
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowValidityReport:
    """Per-INV-FH-2 audit of a candidate Fan-Heat window."""

    duration_s: float
    duration_sufficient: bool  # ≥ FH_TAU_FH_MIN per defaults
    operational_mode_ok: bool  # every sample passes is_fan_only_idle()
    moisture_stability_ok: bool  # return W drift ≤ FH_DELTA_W_MAX
    spatial_uniformity_ok: bool  # σ(h_terminal) ≤ FH_SIGMA_SPATIAL_MAX
    return_humidity_drift: float
    spatial_enthalpy_stddev: float
    samples_consumed: int

    @property
    def is_valid(self) -> bool:
        return (
            self.duration_sufficient
            and self.operational_mode_ok
            and self.moisture_stability_ok
            and self.spatial_uniformity_ok
        )


def _validate_window(
    samples: Sequence[FanHeatSample],
    p_atm_pa: float,
) -> WindowValidityReport:
    """Apply INV-FH-2 to a candidate fan-only window.

    Skips the warmup span at the start of the window (per FH_TAU_WARMUP_S)
    when assessing moisture stability and spatial uniformity, but still
    requires the operational-mode condition to hold throughout — including
    during the warmup.
    """
    if not samples:
        return WindowValidityReport(
            duration_s=0.0,
            duration_sufficient=False,
            operational_mode_ok=False,
            moisture_stability_ok=False,
            spatial_uniformity_ok=False,
            return_humidity_drift=float("nan"),
            spatial_enthalpy_stddev=float("nan"),
            samples_consumed=0,
        )

    duration_s = (samples[-1].monotonic_ns - samples[0].monotonic_ns) / 1e9
    duration_sufficient = duration_s >= FH_TAU_FH_MIN

    # Operational mode must hold every sample, warmup included
    operational_mode_ok = all(s.is_fan_only_idle() for s in samples)

    # Skip warmup for moisture-stability and spatial-uniformity assessment
    warmup_end_ns = samples[0].monotonic_ns + int(FH_TAU_WARMUP_S * 1e9)
    post_warmup = [s for s in samples if s.monotonic_ns >= warmup_end_ns]

    if not post_warmup:
        return WindowValidityReport(
            duration_s=duration_s,
            duration_sufficient=duration_sufficient,
            operational_mode_ok=operational_mode_ok,
            moisture_stability_ok=False,
            spatial_uniformity_ok=False,
            return_humidity_drift=float("nan"),
            spatial_enthalpy_stddev=float("nan"),
            samples_consumed=0,
        )

    # Moisture stability: max return-W minus min return-W over post-warmup window
    return_w_series = [
        state_from_sht_reading(
            s.return_plenum.temperature_c,
            s.return_plenum.relative_humidity_pct,
            p_atm_pa,
        ).humidity_ratio_kg_per_kg
        for s in post_warmup
    ]
    return_w_drift = max(return_w_series) - min(return_w_series)
    moisture_stability_ok = return_w_drift <= FH_DELTA_W_MAX

    # Spatial uniformity: across the post-warmup window, compute the
    # time-averaged enthalpy at each of the 12 terminals, then check the
    # standard deviation across terminals against FH_SIGMA_SPATIAL_MAX.
    per_terminal_avg_h: list[float] = []
    num_terminals = len(post_warmup[0].terminals)
    for term_idx in range(num_terminals):
        terminal_enthalpies = [
            state_from_sht_reading(
                s.terminals[term_idx].sht.temperature_c,
                s.terminals[term_idx].sht.relative_humidity_pct,
                p_atm_pa,
            ).enthalpy_kj_per_kg
            for s in post_warmup
        ]
        per_terminal_avg_h.append(statistics.mean(terminal_enthalpies))
    spatial_stddev = (
        statistics.stdev(per_terminal_avg_h) if len(per_terminal_avg_h) > 1 else 0.0
    )
    spatial_uniformity_ok = spatial_stddev <= FH_SIGMA_SPATIAL_MAX_KJ_PER_KG

    return WindowValidityReport(
        duration_s=duration_s,
        duration_sufficient=duration_sufficient,
        operational_mode_ok=operational_mode_ok,
        moisture_stability_ok=moisture_stability_ok,
        spatial_uniformity_ok=spatial_uniformity_ok,
        return_humidity_drift=return_w_drift,
        spatial_enthalpy_stddev=spatial_stddev,
        samples_consumed=len(post_warmup),
    )


# ---------------------------------------------------------------------------
# η_distribution identification — the core §4 computation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentificationResult:
    """η_distribution identification output, before pass/fail adjudication."""

    eta_hat: float
    eta_sigma: float
    r_fh: float  # numerator of the relative residual test, kJ/kg
    r_fh_relative: float  # R_FH / (η̂ · ⟨P_fan⟩)
    avg_fan_power_w: float
    avg_total_mass_flow_kg_per_s: float


def _identify_eta_distribution(
    samples: Sequence[FanHeatSample],
    p_atm_pa: float,
) -> IdentificationResult:
    """Identify η̂_distribution from a validated fan-only window.

    Per §4.5: η_distribution is the fraction of fan electrical input that
    appears as enthalpy rise at the terminals relative to the return.

    For each sample i in the post-warmup window:

        ΔH_delivered(i) = sum over terminals t of
                          m_dot(t, i) * (h_terminal(t, i) - h_return(i))

    and over the window:

        η̂_distribution = ⟨ΔH_delivered⟩ / ⟨P_fan⟩

    with both numerator and denominator time-averaged. The residual R_FH
    is the difference between the per-sample ΔH_delivered and the time-
    averaged η̂_distribution · P_fan at that sample, time-averaged over
    the window.

    σ_eta is propagated from sample-to-sample variance of (ΔH_delivered/P_fan).
    """
    # Skip the warmup window per FH_TAU_WARMUP_S
    if not samples:
        raise ValueError("Cannot identify η on empty window")
    warmup_end_ns = samples[0].monotonic_ns + int(FH_TAU_WARMUP_S * 1e9)
    post_warmup = [s for s in samples if s.monotonic_ns >= warmup_end_ns]
    if not post_warmup:
        raise ValueError(
            "No post-warmup samples available; window too short to identify η"
        )

    # Per-sample ΔH and P_fan
    per_sample_dh: list[float] = []
    per_sample_pfan: list[float] = []
    per_sample_mass_flow_total: list[float] = []

    for s in post_warmup:
        return_state = state_from_sht_reading(
            s.return_plenum.temperature_c,
            s.return_plenum.relative_humidity_pct,
            p_atm_pa,
        )
        # Delivered enthalpy rise across the AHU+ducts+terminals stack:
        # sum over terminals of m_dot * (h_terminal - h_return)
        dh_sample_kj_per_s = 0.0  # kW (kJ per second)
        total_mass_flow = 0.0
        for t in s.terminals:
            term_state = state_from_sht_reading(
                t.sht.temperature_c, t.sht.relative_humidity_pct, p_atm_pa
            )
            dh_sample_kj_per_s += t.mass_flow_kg_per_s * (
                term_state.enthalpy_kj_per_kg - return_state.enthalpy_kj_per_kg
            )
            total_mass_flow += t.mass_flow_kg_per_s
        per_sample_dh.append(dh_sample_kj_per_s)
        per_sample_pfan.append(s.fan_power_w / 1000.0)  # W → kW
        per_sample_mass_flow_total.append(total_mass_flow)

    avg_dh_kw = statistics.mean(per_sample_dh)
    avg_pfan_kw = statistics.mean(per_sample_pfan)
    avg_mass_flow = statistics.mean(per_sample_mass_flow_total)

    if avg_pfan_kw <= 0.0:
        raise ValueError(
            f"Mean fan power {avg_pfan_kw} kW ≤ 0: invalid fan-only window "
            "(INV-FH-2 should have caught this; check fan_on flag in samples)"
        )

    eta_hat = avg_dh_kw / avg_pfan_kw

    # Per-sample residual: ΔH_i - η̂ * P_fan_i
    per_sample_residual = [
        per_sample_dh[i] - eta_hat * per_sample_pfan[i]
        for i in range(len(per_sample_dh))
    ]
    # R_FH: RMS of the per-sample residual, in kW
    r_fh_kw = math.sqrt(
        statistics.mean(r * r for r in per_sample_residual)
    )
    # Relative test per §4.5
    r_fh_relative = r_fh_kw / (eta_hat * avg_pfan_kw) if eta_hat * avg_pfan_kw != 0 else float("inf")

    # σ_eta: sample standard deviation of (ΔH/P_fan) divided by sqrt(N).
    per_sample_eta_estimates = [
        per_sample_dh[i] / per_sample_pfan[i]
        for i in range(len(per_sample_dh))
        if per_sample_pfan[i] > 0.0
    ]
    n = len(per_sample_eta_estimates)
    if n > 1:
        sample_std = statistics.stdev(per_sample_eta_estimates)
        eta_sigma = sample_std / math.sqrt(n)
    else:
        eta_sigma = float("nan")

    return IdentificationResult(
        eta_hat=eta_hat,
        eta_sigma=eta_sigma,
        r_fh=r_fh_kw,
        r_fh_relative=r_fh_relative,
        avg_fan_power_w=avg_pfan_kw * 1000.0,
        avg_total_mass_flow_kg_per_s=avg_mass_flow,
    )


# ---------------------------------------------------------------------------
# The pass/fail adjudication and end-to-end §4 pipeline
# ---------------------------------------------------------------------------


def _determine_failure_mode(
    eta_hat: float, r_fh_relative: float
) -> FanHeatFailureMode | None:
    """Return None if both pass conditions hold; else the failure mode flag."""
    residual_fails = r_fh_relative > FH_EPS_FH
    eta_out_of_range = not (FH_ETA_MIN <= eta_hat <= FH_ETA_MAX)

    if residual_fails and eta_out_of_range:
        return FanHeatFailureMode.BOTH
    if residual_fails:
        return FanHeatFailureMode.RESIDUAL_EXCEEDS_EPS_FH
    if eta_out_of_range:
        return FanHeatFailureMode.ETA_OUT_OF_RANGE
    return None


@dataclass(frozen=True)
class FanHeatResult:
    """End-to-end Fan-Heat output: the record (Pass or Fail), the
    SignedRecord wrapper, and the log inclusion proof.

    Returned to the caller so the operational layer can act on the result
    (proceed with §5 on Pass; halt the commissioning pipeline on Fail per
    §4 closing notes).
    """

    record: FanHeatPass | FanHeatFail
    signed: SignedRecord
    inclusion_proof: LogInclusionProof
    is_pass: bool
    failure_mode: FanHeatFailureMode | None  # None if pass


class FanHeatWindowInvalid(Exception):
    """Raised per INV-FH-2 when a candidate window is structurally invalid.

    Per §4 spec, implementations MUST reject non-conforming windows rather
    than compute on them. The caller is responsible for collecting a clean
    window before re-invoking; the operational protocol governs what that
    re-collection looks like.
    """

    def __init__(self, report: WindowValidityReport):
        self.report = report
        reasons = []
        if not report.duration_sufficient:
            reasons.append(
                f"duration {report.duration_s:.0f}s < τ_FH_min ({FH_TAU_FH_MIN:.0f}s)"
            )
        if not report.operational_mode_ok:
            reasons.append("operational-mode constraint violated (some sample not fan-only-idle)")
        if not report.moisture_stability_ok:
            reasons.append(
                f"return W drift {report.return_humidity_drift:.6f} > ΔW_max ({FH_DELTA_W_MAX})"
            )
        if not report.spatial_uniformity_ok:
            reasons.append(
                f"spatial enthalpy σ {report.spatial_enthalpy_stddev:.3f} kJ/kg "
                f"> σ_spatial_max ({FH_SIGMA_SPATIAL_MAX_KJ_PER_KG} kJ/kg)"
            )
        super().__init__("INV-FH-2 violated: " + "; ".join(reasons))


def run_fan_heat_check(
    samples: Sequence[FanHeatSample],
    home_id: str,
    p_atm_pa: float = P_ATM_PHOENIX_PA,
) -> FanHeatResult:
    """End-to-end §4 Fan-Heat Consistency Check.

    Workflow:
        1. Validate the window per INV-FH-2. Raise on failure (do NOT
           compute on a non-conforming window).
        2. Identify η̂_distribution and compute R_FH per §4.5.
        3. Adjudicate pass/fail against ε_FH and the [η_min, η_max] range.
        4. Build the FanHeatPass or FanHeatFail record per §4.5.
        5. Sign and log-append per §12 (sign_record → commit_to_log).
        6. Return all artifacts for the caller.

    Args:
        samples: Sequence of 1-Hz FanHeatSample objects covering at least
            FH_TAU_FH_MIN seconds. The first FH_TAU_WARMUP_S are treated as
            warmup and skipped for moisture-stability and spatial-uniformity
            assessment.
        home_id: Identifier for the home this Fan-Heat record belongs to.
        p_atm_pa: Atmospheric pressure at the home. Default Phoenix.

    Returns:
        FanHeatResult with the signed record and inclusion proof.

    Raises:
        FanHeatWindowInvalid: if the window fails any INV-FH-2 constraint.
    """
    # Step 1: window validity per INV-FH-2
    validity = _validate_window(samples, p_atm_pa)
    if not validity.is_valid:
        raise FanHeatWindowInvalid(validity)

    # Step 2: identify η̂
    ident = _identify_eta_distribution(samples, p_atm_pa)

    # Step 3: pass/fail adjudication
    failure_mode = _determine_failure_mode(ident.eta_hat, ident.r_fh_relative)
    is_pass = failure_mode is None

    # Step 4: build the §4.5 record
    common = FanHeatRecordCommon(
        home_id=home_id,
        window_start_monotonic_ns=samples[0].monotonic_ns,
        window_end_monotonic_ns=samples[-1].monotonic_ns,
        window_start_wallclock_iso=samples[0].wall_clock_iso,
        window_end_wallclock_iso=samples[-1].wall_clock_iso,
        eta_distribution_hat=ident.eta_hat,
        eta_distribution_sigma=ident.eta_sigma,
        r_fh=ident.r_fh,
        r_fh_relative=ident.r_fh_relative,
        eps_fh_used=FH_EPS_FH,
        eta_min_used=FH_ETA_MIN,
        eta_max_used=FH_ETA_MAX,
        fan_power_avg_w=ident.avg_fan_power_w,
        return_humidity_drift_kg_per_kg=validity.return_humidity_drift,
        spatial_enthalpy_stddev_kj_per_kg=validity.spatial_enthalpy_stddev,
        samples_consumed=validity.samples_consumed,
    )

    record: FanHeatPass | FanHeatFail
    if is_pass:
        record = FanHeatPass(common=common)
    else:
        assert failure_mode is not None
        record = FanHeatFail(common=common, failure_mode=failure_mode)

    # Step 5: sign and log per §12. sign_record → commit_to_log
    # (INV-SIGN12-1, INV-SIGN12-2 paired sequence).
    signable = record.to_signable()
    signed = sign_record(signable)
    proof = commit_to_log(signed)

    return FanHeatResult(
        record=record,
        signed=signed,
        inclusion_proof=proof,
        is_pass=is_pass,
        failure_mode=failure_mode,
    )


# ---------------------------------------------------------------------------
# Helper for callers: generating "now" wall-clock ISO strings
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Return current UTC time in ISO 8601 format. Convenience for callers
    constructing FanHeatSample objects in test or operational code."""
    return datetime.now(timezone.utc).isoformat()
