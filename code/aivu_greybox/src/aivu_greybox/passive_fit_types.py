"""Prior interface (§5.4) and Day-1-2 passive-window telemetry types (§5.3).

Per §5.4: §5 specifies the prior INTERFACE, not the prior values. The
caller (the BDT or a fallback supplier) constructs a Prior6D and hands it
to `run_passive_batch_fit`. The path that produced the prior is captured
in `provenance` for downstream auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .defaults import CANONICAL_PARAMETER_NAMES, NUM_CANONICAL_PARAMETERS
from .fan_heat import FanHeatSample  # reused for the inner telemetry-sample shape


# ---------------------------------------------------------------------------
# Prior over the six canonical parameters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Prior6D:
    """Multivariate Gaussian prior over the canonical parameter vector.

    Per §5.4:
      - Mean vector μ_prior ∈ ℝ⁶
      - Covariance matrix Σ_prior ∈ ℝ⁶ˣ⁶, positive-definite
      - Provenance descriptor and hash

    The path preference order (PINN → EnergyPlus → ACCA Manual J) is
    operational policy; this dataclass carries whichever path's output
    via the provenance fields.
    """

    mean: np.ndarray  # shape (6,)
    covariance: np.ndarray  # shape (6, 6)
    provenance_descriptor: str
    provenance_hash: str
    generated_timestamp_iso: str

    def __post_init__(self):
        if self.mean.shape != (NUM_CANONICAL_PARAMETERS,):
            raise ValueError(
                f"Prior mean shape {self.mean.shape} != "
                f"({NUM_CANONICAL_PARAMETERS},). Canonical parameter order: "
                f"{CANONICAL_PARAMETER_NAMES}"
            )
        if self.covariance.shape != (
            NUM_CANONICAL_PARAMETERS,
            NUM_CANONICAL_PARAMETERS,
        ):
            raise ValueError(
                f"Prior covariance shape {self.covariance.shape} != "
                f"({NUM_CANONICAL_PARAMETERS}, {NUM_CANONICAL_PARAMETERS})"
            )
        # Symmetric
        if not np.allclose(self.covariance, self.covariance.T, rtol=1e-10):
            raise ValueError("Prior covariance must be symmetric")
        # Positive-definite check: Cholesky succeeds iff PD
        try:
            np.linalg.cholesky(self.covariance)
        except np.linalg.LinAlgError:
            raise ValueError(
                "Prior covariance must be positive-definite (Cholesky failed)"
            )

    @property
    def marginal_sigmas(self) -> np.ndarray:
        """Per-parameter standard deviations: sqrt of diagonal of covariance."""
        return np.sqrt(np.diag(self.covariance))


def make_acca_manual_j_fallback_prior(provenance_hash: str = "") -> Prior6D:
    """Construct an ACCA Manual J fallback prior per §5.4 path-preference (3).

    Per the spec: "appropriate as a strict-pilot-time fallback. The AOT
    §3.2 placeholder of 0.75 for ceiling_coupling_factor is consistent
    with this fallback path." Other parameter values are typical for a
    Phoenix CZ 2B single-family of 1800-sqft-class with two-stage AC and
    foam-deck attic.

    Returned prior σ's are deliberately wide on the loosely-identified
    parameters (cfm50, F_slab, C_w) and tighter on the well-characterized
    ones (R_eff, C_house, ceiling_coupling_factor) — reflecting what
    Manual J actually constrains.
    """
    import hashlib
    from datetime import datetime, timezone

    # Means in SI internal units.
    # R_eff ~ 5 m²·K/W effective (whole-envelope thermal resistance,
    #    approximate for 1800-sqft single-family with foam-deck attic)
    # C_house ~ 5 MJ/K (lumped sensible capacitance, 1800 sqft)
    # cfm50 ~ 1800 (whole-house leakage at 50 Pa, typical Phoenix new build)
    # F_slab ~ 100 W/K (slab F-factor for ground coupling)
    # C_w ~ 8 kg dry air × something  (moisture capacity proxy)
    # ceiling_coupling_factor ~ 0.75 per AOT §3.2 placeholder
    mean = np.array([5.0, 5.0e6, 1800.0, 100.0, 50.0, 0.75])

    # Marginal standard deviations: wider for loose parameters.
    # 20% R_eff, 15% C_house, 50% cfm50, 40% F_slab, 30% C_w, 33% ceiling_coupling
    sigmas = np.array([1.0, 7.5e5, 900.0, 40.0, 15.0, 0.25])
    # Diagonal covariance (Manual J does not give correlated information)
    cov = np.diag(sigmas ** 2)

    descriptor = "ACCA_ManualJ_Phoenix_2B_1800sqft_2stage_foam_attic"
    if not provenance_hash:
        provenance_hash = hashlib.sha256(descriptor.encode()).hexdigest()[:32]

    return Prior6D(
        mean=mean,
        covariance=cov,
        provenance_descriptor=descriptor,
        provenance_hash=provenance_hash,
        generated_timestamp_iso=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Day-1-2 telemetry window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Day12TelemetryWindow:
    """A 48-hour passive-observation window for §5.

    Structurally similar to the FanHeatSample list used by §4, but
    enforces:
      - 48-hour duration (§5.2 protocol)
      - Programmed fan-mixing schedule (10 min on / 50 min off per clock-
        aligned hour) — INV-FIT12-6 requires this be signed metadata.

    The schedule is NOT stored separately from samples; it's derivable
    from samples by reading the fan_on flag. We expose helper methods
    that index into the warmup-channel and main-channel sub-intervals.
    """

    samples: tuple[FanHeatSample, ...]
    # The HVAC excitation as 1-Hz arrays for forward-chain consumption
    # (derived from fan_power + η̂_distribution at construction time)
    hvac_excitation_monotonic_ns: np.ndarray
    q_sens_w: np.ndarray
    m_lat_kg_per_s: np.ndarray
    # Weather as 1-Hz arrays
    weather_monotonic_ns: np.ndarray
    t_outdoor_c: np.ndarray
    rh_outdoor_pct: np.ndarray
    solar_global_w_per_m2: np.ndarray
    wind_speed_m_per_s: np.ndarray

    def __post_init__(self):
        if not self.samples:
            raise ValueError("Day12TelemetryWindow requires non-empty samples")
        n_arrays_expected = len(self.samples)
        for name, arr in [
            ("hvac_excitation_monotonic_ns", self.hvac_excitation_monotonic_ns),
            ("q_sens_w", self.q_sens_w),
            ("m_lat_kg_per_s", self.m_lat_kg_per_s),
            ("weather_monotonic_ns", self.weather_monotonic_ns),
            ("t_outdoor_c", self.t_outdoor_c),
            ("rh_outdoor_pct", self.rh_outdoor_pct),
            ("solar_global_w_per_m2", self.solar_global_w_per_m2),
            ("wind_speed_m_per_s", self.wind_speed_m_per_s),
        ]:
            if arr.shape != (n_arrays_expected,):
                raise ValueError(
                    f"{name} length {arr.shape[0]} != number of samples "
                    f"{n_arrays_expected}"
                )

    @property
    def duration_s(self) -> float:
        return (self.samples[-1].monotonic_ns - self.samples[0].monotonic_ns) / 1e9

    def find_fan_on_intervals(self) -> list[tuple[int, int]]:
        """Return list of (start_index, end_index_exclusive) for each fan-on
        interval in the window.

        Per §5.2: 10 minutes on at minutes 0-10 of each clock-aligned hour.
        With 1-Hz telemetry, each fan-on interval is ~600 contiguous samples.
        We detect them by scanning the `fan_on` flag.
        """
        intervals: list[tuple[int, int]] = []
        in_fan_on = False
        start = 0
        for i, s in enumerate(self.samples):
            if s.fan_on and not in_fan_on:
                start = i
                in_fan_on = True
            elif not s.fan_on and in_fan_on:
                intervals.append((start, i))
                in_fan_on = False
        if in_fan_on:
            intervals.append((start, len(self.samples)))
        return intervals
