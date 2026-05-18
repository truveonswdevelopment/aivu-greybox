"""Day4Posterior signed record — HVAC half of the Digital Birth Certificate.

Per H1 v0.2 §4.3 (output) and §5 (§6 consumption interface):

The record carries the joint posterior over D17_pilot and D20_pilot, plus
the AHRI-rated nominal values that pair with each bi-quadratic. It exposes
the methods §6's envelope active commissioning consumes on Days 5-6 to
evaluate delivered HVAC capacity and EER at arbitrary operating points
within the sweep's operating-point envelope.

[Ref: AIVU HVAC Greybox Spec v0.2 (2026-05-18) §4.3, §5;
      AIVU greybox §12 signed-record schema (parallel structure).]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from aivu_physics_phase2.equipment_output import BiQuadraticCoefficients

from .bi_quadratic_fit import N_FREE_COEFFICIENTS, bracket_jacobian_at


# Indices in the 10-element free-coefficient vector / 10×10 covariance:
D17_BLOCK_SLICE: Final[slice] = slice(0, 5)
D20_BLOCK_SLICE: Final[slice] = slice(5, 10)


@dataclass(frozen=True)
class Day4Posterior:
    """End-of-Day-4 signed record for the HVAC half of the DBC.

    Carries the joint posterior over the 10 free coefficients (5 D17_pilot + 5
    D20_pilot, with each family's `a` determined by the AHRI anchor at every
    point of access via the BiQuadraticCoefficients dataclass).

    For §6 consumption: `evaluate_q_delivered(T_odb, T_wbe)` returns the
    posterior-predictive (mean, σ) of delivered cooling capacity in BTU/hr at
    the queried operating point. Same structure for `evaluate_eer`. These are
    the methods §6's active synthesizer replaces today's hard-coded HVAC
    values with on Days 5-6.

    Per H1 v0.2 §8 (and the deferred-G9-review decision 2026-05-18), v0.1
    construction does not include cryptographic signing — the record is the
    output dataclass; signing wraps it at the storage boundary via
    `aivu_integrity` once that ships.
    """

    d17_pilot: BiQuadraticCoefficients
    d20_pilot: BiQuadraticCoefficients
    posterior_covariance: np.ndarray  # shape (10, 10) over free coefficients
    q_nominal_pilot_btuh: float
    eer_nominal_pilot_btuh_per_w: float
    vintage_iso: str  # ISO 8601 timestamp of record creation

    def __post_init__(self):
        if self.posterior_covariance.shape != (N_FREE_COEFFICIENTS, N_FREE_COEFFICIENTS):
            raise ValueError(
                f"posterior_covariance must be ({N_FREE_COEFFICIENTS},"
                f"{N_FREE_COEFFICIENTS}); got {self.posterior_covariance.shape}"
            )
        if self.q_nominal_pilot_btuh <= 0:
            raise ValueError(
                f"q_nominal_pilot_btuh must be positive; got {self.q_nominal_pilot_btuh}"
            )
        if self.eer_nominal_pilot_btuh_per_w <= 0:
            raise ValueError(
                f"eer_nominal_pilot_btuh_per_w must be positive; "
                f"got {self.eer_nominal_pilot_btuh_per_w}"
            )

    def evaluate_q_delivered(
        self, t_odb_f: float, t_wbe_f: float
    ) -> tuple[float, float]:
        """Return (mean_BTU_per_hr, sigma_BTU_per_hr) for delivered capacity.

        Uses the fitted D17_pilot bi-quadratic for the mean and propagates the
        posterior covariance over the 5 D17_pilot free coefficients through
        the bracket's Jacobian to get σ. AHRI-anchor enforcement is reflected
        in the Jacobian (∂a/∂{b,c,d,e,f} terms baked in via
        `bracket_jacobian_at`).
        """
        mean_bracket = self.d17_pilot.evaluate(t_odb_f, t_wbe_f)
        j = bracket_jacobian_at(t_odb_f, t_wbe_f)
        cov_d17 = self.posterior_covariance[D17_BLOCK_SLICE, D17_BLOCK_SLICE]
        var_bracket = float(j @ cov_d17 @ j)
        sigma_bracket = max(0.0, var_bracket) ** 0.5
        return (
            self.q_nominal_pilot_btuh * mean_bracket,
            self.q_nominal_pilot_btuh * sigma_bracket,
        )

    def evaluate_eer(
        self, t_odb_f: float, t_wbe_f: float
    ) -> tuple[float, float]:
        """Return (mean_BTU_per_hr_per_W, sigma) for delivered EER."""
        mean_bracket = self.d20_pilot.evaluate(t_odb_f, t_wbe_f)
        j = bracket_jacobian_at(t_odb_f, t_wbe_f)
        cov_d20 = self.posterior_covariance[D20_BLOCK_SLICE, D20_BLOCK_SLICE]
        var_bracket = float(j @ cov_d20 @ j)
        sigma_bracket = max(0.0, var_bracket) ** 0.5
        return (
            self.eer_nominal_pilot_btuh_per_w * mean_bracket,
            self.eer_nominal_pilot_btuh_per_w * sigma_bracket,
        )
