"""Joint Laplace fit for D17_pilot and D20_pilot bi-quadratics.

Implements H1 v0.2 §3.1 (D17_pilot delivered-capacity) and §3.2 (D20_pilot EER)
as a single joint fit over 10 free coefficients (5 per family, with each
family's `a` determined by the AHRI 95°F / 67°F anchor).

The fit consumes observed sweep telemetry — pairs of (Q_total_delivered,
P_electrical) at known (T_odb, T_wbe) operating points — and the
nameplate-derived Q_nominal_pilot and EER_nominal_pilot. It produces:
- MAP estimates of D17_pilot and D20_pilot coefficient sets
- 10×10 joint posterior covariance via Laplace approximation
- Hessian condition number for identifiability diagnostics

Sensible/latent decomposition is NOT fitted here per H1 v0.2 §3.4 — that
information lives in the per-pod (T, RH) telemetry audit log and is read by
§6 at runtime.

[Ref: AIVU HVAC Greybox Spec v0.2 (2026-05-18) §3;
      AIVU Phase 2 Physics Specification Increment 3 v0.1 §3.1, §8.1;
      AIVU greybox §8 identifiability machinery (parallel structure).]
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize

from aivu_physics_phase2.equipment_output import (
    AHRI_T_ODB_F,
    AHRI_T_WBE_F,
    BiQuadraticCoefficients,
)


# Free coefficient ordering: (b17, c17, d17, e17, f17, b20, c20, d20, e20, f20).
# Each family's `a` is computed from the AHRI anchor.
N_FREE_PER_FAMILY: int = 5
N_FREE_COEFFICIENTS: int = 10


# ---------------------------------------------------------------------------
# Anchor enforcement
# ---------------------------------------------------------------------------


def anchor_a(b: float, c: float, d: float, e: float, f: float) -> float:
    """Compute the `a` coefficient so bracket = 1.0 at AHRI rating conditions.

    bracket = a + b·T_odb + c·T_odb² + d·T_wbe + e·T_wbe² + f·T_odb·T_wbe
    Setting bracket(95, 67) = 1.0 and solving for `a`.
    """
    return 1.0 - (
        AHRI_T_ODB_F * b
        + AHRI_T_ODB_F**2 * c
        + AHRI_T_WBE_F * d
        + AHRI_T_WBE_F**2 * e
        + AHRI_T_ODB_F * AHRI_T_WBE_F * f
    )


def coefficients_from_free(
    free: np.ndarray,
) -> tuple[BiQuadraticCoefficients, BiQuadraticCoefficients]:
    """Unpack 10-element free vector into (D17, D20) BiQuadraticCoefficients.

    Each family's `a` is computed from anchor; the bracket equals 1.0 at AHRI
    rating conditions by construction.
    """
    if free.shape != (N_FREE_COEFFICIENTS,):
        raise ValueError(
            f"Free coefficient vector must have shape ({N_FREE_COEFFICIENTS},), got {free.shape}"
        )
    b17, c17, d17_, e17, f17, b20, c20, d20_, e20, f20 = free
    a17 = anchor_a(b17, c17, d17_, e17, f17)
    a20 = anchor_a(b20, c20, d20_, e20, f20)
    return (
        BiQuadraticCoefficients(a=a17, b=b17, c=c17, d=d17_, e=e17, f=f17),
        BiQuadraticCoefficients(a=a20, b=b20, c=c20, d=d20_, e=e20, f=f20),
    )


def free_from_coefficients(
    d17: BiQuadraticCoefficients, d20: BiQuadraticCoefficients
) -> np.ndarray:
    """Pack (D17, D20) BiQuadraticCoefficients into 10-element free vector.

    The `a` coefficients are dropped (determined by anchor).
    """
    return np.array(
        [d17.b, d17.c, d17.d, d17.e, d17.f, d20.b, d20.c, d20.d, d20.e, d20.f]
    )


def bracket_jacobian_at(t_odb_f: float, t_wbe_f: float) -> np.ndarray:
    """Jacobian of bracket(T_odb, T_wbe) w.r.t. (b, c, d, e, f), with anchor enforced.

    Since a = 1.0 - (95·b + 9025·c + 67·d + 4489·e + 6365·f), we have
        ∂a/∂b = -95, ∂a/∂c = -9025, ∂a/∂d = -67, ∂a/∂e = -4489, ∂a/∂f = -6365

    And bracket = a + b·T_odb + c·T_odb² + d·T_wbe + e·T_wbe² + f·T_odb·T_wbe.

    So ∂bracket/∂b = T_odb + ∂a/∂b = T_odb - 95, etc.

    Returns: array of shape (5,) for one family.
    """
    return np.array(
        [
            t_odb_f - AHRI_T_ODB_F,
            t_odb_f**2 - AHRI_T_ODB_F**2,
            t_wbe_f - AHRI_T_WBE_F,
            t_wbe_f**2 - AHRI_T_WBE_F**2,
            t_odb_f * t_wbe_f - AHRI_T_ODB_F * AHRI_T_WBE_F,
        ]
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepPoint:
    """One steady-state observation from the Day 3-4 sweep.

    q_total_delivered_btuh: integrated register-side delivered capacity per H1
    v0.2 §3.1 (Σ pods of enthalpy difference × airflow).

    p_electrical_w: HVAC equipment electrical power from Eaton smart-circuit
    breaker, averaged over the steady-state dwell.
    """

    t_odb_f: float
    t_wbe_f: float
    q_total_delivered_btuh: float
    p_electrical_w: float


@dataclass(frozen=True)
class Prior:
    """Gaussian prior over the 10 free coefficients."""

    mean: np.ndarray  # shape (10,)
    covariance: np.ndarray  # shape (10, 10)

    def __post_init__(self):
        if self.mean.shape != (N_FREE_COEFFICIENTS,):
            raise ValueError(f"Prior mean must have shape ({N_FREE_COEFFICIENTS},)")
        if self.covariance.shape != (N_FREE_COEFFICIENTS, N_FREE_COEFFICIENTS):
            raise ValueError(
                f"Prior covariance must have shape "
                f"({N_FREE_COEFFICIENTS}, {N_FREE_COEFFICIENTS})"
            )


@dataclass(frozen=True)
class LaplaceResult:
    """Output of the joint Laplace fit."""

    map_free_coefficients: np.ndarray  # shape (10,)
    posterior_covariance: np.ndarray  # shape (10, 10)
    d17_pilot: BiQuadraticCoefficients
    d20_pilot: BiQuadraticCoefficients
    hessian_condition_number: float
    optimizer_converged: bool


# ---------------------------------------------------------------------------
# Objective: negative log posterior
# ---------------------------------------------------------------------------


def neg_log_likelihood(
    free: np.ndarray,
    sweep_points: list[SweepPoint],
    q_nominal_pilot_btuh: float,
    eer_nominal_pilot_btuh_per_w: float,
    sigma_q_relative: float,
    sigma_p_relative: float,
) -> float:
    """Gaussian NLL of observed (Q, P) under the model.

    Model:
      Q_model = Q_nominal_pilot × bracket_D17(T_odb, T_wbe)
      EER_model = EER_nominal_pilot × bracket_D20(T_odb, T_wbe)
      P_model = Q_model / EER_model

    Noise is relative-Gaussian (σ = noise_fraction × predicted value) on each
    observation. Penalizes non-physical brackets (≤0) with a large value
    rather than NaN so the optimizer steers away.
    """
    d17, d20 = coefficients_from_free(free)
    nll = 0.0
    for pt in sweep_points:
        bracket_17 = d17.evaluate(pt.t_odb_f, pt.t_wbe_f)
        bracket_20 = d20.evaluate(pt.t_odb_f, pt.t_wbe_f)
        # Physical-region guard: capacity and EER must be positive.
        if bracket_17 <= 0 or bracket_20 <= 0:
            return 1e10
        q_model = q_nominal_pilot_btuh * bracket_17
        eer_model = eer_nominal_pilot_btuh_per_w * bracket_20
        p_model = q_model / eer_model
        sigma_q = sigma_q_relative * q_model
        sigma_p = sigma_p_relative * p_model
        nll += 0.5 * ((pt.q_total_delivered_btuh - q_model) / sigma_q) ** 2
        nll += 0.5 * ((pt.p_electrical_w - p_model) / sigma_p) ** 2
    return nll


def neg_log_prior(free: np.ndarray, prior: Prior) -> float:
    """Gaussian NLL of free coefficients under the prior."""
    diff = free - prior.mean
    return 0.5 * float(diff @ np.linalg.solve(prior.covariance, diff))


# ---------------------------------------------------------------------------
# Joint Laplace fit
# ---------------------------------------------------------------------------


def _numerical_hessian(objective, x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """Central-difference numerical Hessian at x."""
    n = len(x)
    H = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            xpp = x.copy()
            xpp[i] += eps
            xpp[j] += eps
            xmm = x.copy()
            xmm[i] -= eps
            xmm[j] -= eps
            xpm = x.copy()
            xpm[i] += eps
            xpm[j] -= eps
            xmp = x.copy()
            xmp[i] -= eps
            xmp[j] += eps
            H[i, j] = (
                objective(xpp) + objective(xmm) - objective(xpm) - objective(xmp)
            ) / (4 * eps * eps)
            H[j, i] = H[i, j]
    return H


def run_joint_laplace_fit(
    sweep_points: list[SweepPoint],
    q_nominal_pilot_btuh: float,
    eer_nominal_pilot_btuh_per_w: float,
    prior: Prior,
    sigma_q_relative: float = 0.02,
    sigma_p_relative: float = 0.02,
    num_restarts: int = 4,
    rng_seed: int = 42,
) -> LaplaceResult:
    """Run the joint D17_pilot + D20_pilot Laplace fit.

    Strategy: minimize the negative log posterior via L-BFGS-B from multiple
    restart points (prior mean + perturbations). Pick the best minimum.
    Compute numerical Hessian at the MAP for the Laplace posterior covariance.

    Args:
        sweep_points: Day 3-4 sweep observations. Need ≥ 6 points minimum for
            10-parameter fit; ≥ 15 (5×3) recommended per H1 v0.2 §3.1.
        q_nominal_pilot_btuh: Q_total_delivered at AHRI rating conditions.
            Either measured directly or estimated as nameplate × assumed_efficiency.
        eer_nominal_pilot_btuh_per_w: EER at AHRI rating conditions.
        prior: Gaussian prior over 10 free coefficients.
        sigma_q_relative: Relative measurement noise σ on Q_total_delivered.
        sigma_p_relative: Relative measurement noise σ on P_electrical.
        num_restarts: Number of optimizer restarts from perturbed initial points.
        rng_seed: RNG seed for perturbation reproducibility.

    Returns:
        LaplaceResult with MAP estimates, posterior covariance, and
        identifiability diagnostics.
    """
    if len(sweep_points) < N_FREE_COEFFICIENTS:
        raise ValueError(
            f"Need at least {N_FREE_COEFFICIENTS} sweep points to fit "
            f"{N_FREE_COEFFICIENTS} free coefficients; got {len(sweep_points)}."
        )
    rng = np.random.default_rng(rng_seed)

    def objective(x: np.ndarray) -> float:
        return neg_log_likelihood(
            x,
            sweep_points,
            q_nominal_pilot_btuh,
            eer_nominal_pilot_btuh_per_w,
            sigma_q_relative,
            sigma_p_relative,
        ) + neg_log_prior(x, prior)

    best_result = None
    best_objective_value = float("inf")
    any_converged = False

    prior_sigmas = np.sqrt(np.diag(prior.covariance))

    for r in range(num_restarts):
        if r == 0:
            x0 = prior.mean.copy()
        else:
            # Perturb by 0.3 prior σ — large enough to break symmetry, small
            # enough to stay in a physical-region neighborhood.
            x0 = prior.mean + 0.3 * prior_sigmas * rng.standard_normal(
                N_FREE_COEFFICIENTS
            )
        result = optimize.minimize(
            objective,
            x0,
            method="L-BFGS-B",
            options={"maxiter": 500, "ftol": 1e-10, "gtol": 1e-8},
        )
        any_converged = any_converged or result.success
        if result.fun < best_objective_value:
            best_objective_value = result.fun
            best_result = result

    map_free = best_result.x

    # Posterior covariance via Laplace: H^{-1} where H is the Hessian of NLP at MAP.
    hessian = _numerical_hessian(objective, map_free)
    try:
        posterior_cov = np.linalg.inv(hessian)
    except np.linalg.LinAlgError:
        posterior_cov = np.linalg.pinv(hessian)

    eigvals = np.linalg.eigvalsh(hessian)
    # Condition number on the Hessian (not the covariance): big = ill-conditioned.
    min_eigval = float(np.min(eigvals))
    max_eigval = float(np.max(eigvals))
    if min_eigval <= 0:
        cond_number = float("inf")
    else:
        cond_number = max_eigval / min_eigval

    d17, d20 = coefficients_from_free(map_free)

    return LaplaceResult(
        map_free_coefficients=map_free,
        posterior_covariance=posterior_cov,
        d17_pilot=d17,
        d20_pilot=d20,
        hessian_condition_number=cond_number,
        optimizer_converged=any_converged,
    )
