"""Record dataclasses for `aivu_greybox` v0.1.

Each record type corresponds to a signed artifact in the spec:

  - FanHeatPass / FanHeatFail  ← §4.5
  - Day2Posterior              ← §5.8
  - Day5Posterior              ← §6.7
  - HeartbeatPosterior          ← §7.7
  - DailyPosterior              ← §7.7
  - SignificanceEvent           ← §7.7

v0.1 implements FanHeatPass / FanHeatFail in full. The other dataclasses
are scaffolded with the fields the spec requires; implementations land
in subsequent B-workstream items.

All record dataclasses are frozen, type-annotated, and convert to plain
dicts via the `to_signable()` method for the §12 sign_record call. The
to_signable form is what gets hashed and signed; the dataclass form is
what greybox code constructs and consumes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class FanHeatFailureMode(Enum):
    """The two failure modes per §4 closing notes."""

    RESIDUAL_EXCEEDS_EPS_FH = "residual_exceeds_eps_fh"
    ETA_OUT_OF_RANGE = "eta_out_of_range"
    BOTH = "both"


@dataclass(frozen=True)
class FanHeatRecordCommon:
    """Fields common to FanHeatPass and FanHeatFail per §4.5."""

    # Window identification
    home_id: str
    window_start_monotonic_ns: int
    window_end_monotonic_ns: int
    window_start_wallclock_iso: str  # ISO 8601 wall-clock at window start
    window_end_wallclock_iso: str

    # Identified value and its uncertainty (Day-1 prior for §6 per INV-FH-4)
    eta_distribution_hat: float
    eta_distribution_sigma: float

    # The residual itself
    r_fh: float  # raw residual in kJ/kg (the numerator of the relative test)
    r_fh_relative: float  # R_FH / (η̂_distribution * ⟨P_fan⟩), dimensionless

    # The tolerances actually used
    eps_fh_used: float
    eta_min_used: float
    eta_max_used: float

    # Window-validity summary (every INV-FH-2 constraint must have been
    # checked and either satisfied or rejected — these fields are the
    # signed record of that check)
    fan_power_avg_w: float
    return_humidity_drift_kg_per_kg: float
    spatial_enthalpy_stddev_kj_per_kg: float
    samples_consumed: int


@dataclass(frozen=True)
class FanHeatPass:
    """Signed §4 record on Fan-Heat-Pass. INV-FH-3: records are complete
    and externally verifiable. Every field needed for an external verifier
    to re-derive η̂_distribution and r_fh from raw telemetry is present.
    """

    common: FanHeatRecordCommon
    record_type: str = "FanHeatPass"

    def to_signable(self) -> dict[str, Any]:
        return {"record_type": self.record_type, **asdict(self.common)}


@dataclass(frozen=True)
class FanHeatFail:
    """Signed §4 record on Fan-Heat-Fail. Per §4 closing notes: the signed
    residual and identified η̂_distribution are preserved on fail, with the
    failure-mode flag distinguishing which condition tripped.
    """

    common: FanHeatRecordCommon
    failure_mode: FanHeatFailureMode
    record_type: str = "FanHeatFail"

    def to_signable(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "failure_mode": self.failure_mode.value,
            **asdict(self.common),
        }


# ---------------------------------------------------------------------------
# Scaffolds for §§5, 6, 7 records — fields per spec, implementation in later B items
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PosteriorCommon:
    """Fields common to Day2Posterior, Day5Posterior, HeartbeatPosterior,
    DailyPosterior. Captures the multivariate Gaussian posterior plus the
    metadata §§5.8 / §6.7 / §7.7 require."""

    home_id: str
    parameter_names: tuple[str, ...]
    posterior_mean: tuple[float, ...]
    posterior_covariance: tuple[tuple[float, ...], ...]
    prior_provenance_descriptor: str
    prior_hash: str
    monotonic_timestamp_ns: int


@dataclass(frozen=True)
class IdentifiabilityReport:
    """§8 v1 schema. Co-signed with parent posterior per §8 INV-ID8-1; not
    separately signed. Scaffolded here; computation lands in B-workstream
    items implementing §8."""

    protocol: str  # "§5_day2_passive" | "§6_day5_active_compounded" | "§7_recursive_mode"
    per_parameter: dict[str, dict[str, Any]] = field(default_factory=dict)
    hessian_spectrum: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Day2Posterior:
    """§5.8 signed posterior record. Scaffolded; B1 §5 implementation pending."""

    common: PosteriorCommon
    identifiability_report: IdentifiabilityReport
    fan_heat_pass_record_hash: str  # INV-FIT12-1 prerequisite linkage
    record_type: str = "Day2Posterior"


@dataclass(frozen=True)
class Day5Posterior:
    """§6.7 signed posterior record. Scaffolded; B1 §6 implementation pending."""

    common: PosteriorCommon
    identifiability_report: IdentifiabilityReport
    day2_posterior_hash: str  # INV-FIT45-1 prerequisite linkage
    day3_map_hash: str  # INV-FIT45-2 prerequisite linkage
    excitation_protocol_record: dict[str, Any] = field(default_factory=dict)
    record_type: str = "Day5Posterior"


# ---------------------------------------------------------------------------
# §7 records — recursive mode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeartbeatPosterior:
    """§7.7 per-heartbeat (1 Hz) record. Compact: parameter mean μ_t, diagonal
    of Σ_t, full Σ_t deferred to DailyPosterior to bound storage."""

    common: PosteriorCommon  # NOTE: common.posterior_covariance contains diagonal only at heartbeat cadence
    observation_channels_available: tuple[str, ...]  # which channels updated this heartbeat
    most_recent_daily_posterior_hash: str
    record_type: str = "HeartbeatPosterior"


@dataclass(frozen=True)
class FirstLawResidualRecord:
    """§7.5 First Law residual self-test output, daily."""

    date_iso: str  # YYYY-MM-DD local
    epsilon_fl_joules: float  # signed residual
    epsilon_fl_relative: float  # residual / total daily energy throughput
    per_term_audit: dict[str, float]  # which term contributed which fraction
    threshold_flag: bool  # True if exceeds FIRST_LAW_RESIDUAL_THRESHOLD_FRACTION
    interval_baseline_state_recovery: dict[str, float]  # T_main, T_attic, W_main delta over interval


@dataclass(frozen=True)
class DailyPosterior:
    """§7.7 daily summary record."""

    common: PosteriorCommon
    date_iso: str
    start_of_day_mean: tuple[float, ...]
    end_of_day_mean: tuple[float, ...]
    start_of_day_covariance: tuple[tuple[float, ...], ...]
    end_of_day_covariance: tuple[tuple[float, ...], ...]
    identifiability_report: IdentifiabilityReport
    first_law_residual: FirstLawResidualRecord
    heartbeat_hash_range: tuple[str, str]  # (first_hash, last_hash) of contributing heartbeats
    record_type: str = "DailyPosterior"


@dataclass(frozen=True)
class SignificanceEvent:
    """§7.7 event-driven significance record. Threshold-attested per
    §7.3.3 and INV-REC7-5."""

    common: PosteriorCommon
    triggered_at_monotonic_ns: int
    triggered_parameter: str
    drift_sigma: float  # how many σ from §6 Day-5 baseline
    baseline_day5_posterior_hash: str
    contributing_daily_hashes: tuple[str, ...]  # leading up to the event
    first_law_residual_summary: dict[str, float]
    record_type: str = "SignificanceEvent"
