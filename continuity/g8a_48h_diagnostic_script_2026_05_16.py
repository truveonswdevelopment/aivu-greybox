"""G8a diagnostic dive — full diagnostic dump from a 48h passive fit.

Re-runs the same fit as `test_recovery_at_48h_passive` but captures and
prints the full diagnostic structure that the test ignored:

  - Per-restart final modes (4 restarts × 7 parameters)
  - Per-restart final log-posteriors
  - Restart-to-restart mode disagreement (in units of prior σ)
  - Hessian eigenvalues and condition number
  - Identifiability report's ridge vectors (eigenvector loadings on
    small-eigenvalue directions — these directly name which parameter
    combinations are degenerate)
  - Per-parameter posterior vs prior vs θ_true comparison

Output: structured stdout + JSON dump to /tmp/g8a_diagnostics.json

Run with:
  cd ~/aivu-greybox/code/aivu_greybox
  ~/aivu-greybox/.venv/bin/python tests/g8a_diagnostic.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# Add the tests/ directory to the path so we can import the helpers from
# test_g8_closed_loop.py without duplicating them.
sys.path.insert(0, str(Path(__file__).parent))

from test_g8_closed_loop import (  # noqa: E402
    THETA_TRUE_PERTURBED,
    _make_phoenix_site,
    _make_sim_config,
    _make_v752_context,
    _synthesize_day12_window_real_chain,
)

from aivu_greybox._signing_stub import _reset_log_for_testing  # noqa: E402
from aivu_greybox.defaults import CANONICAL_PARAMETER_NAMES  # noqa: E402
from aivu_greybox.passive_fit import run_passive_batch_fit  # noqa: E402
from aivu_greybox.passive_fit_types import make_acca_manual_j_fallback_prior  # noqa: E402
from aivu_greybox.real_chain import RealForwardChain  # noqa: E402


def main():
    _reset_log_for_testing()

    print("=" * 78)
    print("G8a diagnostic dive — 48h passive fit, full diagnostic structure")
    print("=" * 78)

    # ---- Build the same scene as the test ----
    site = _make_phoenix_site()
    sim_config = _make_sim_config()
    context = _make_v752_context()
    real_chain = RealForwardChain(site=site, sim_config=sim_config)

    print("\n[1/3] Synthesizing 48h telemetry at theta_true ...")
    window = _synthesize_day12_window_real_chain(
        theta_true=THETA_TRUE_PERTURBED,
        real_chain=real_chain,
        context=context,
        duration_hours=48.0,
        seed=2026,
    )

    prior = make_acca_manual_j_fallback_prior()

    print("[2/3] Running passive batch fit ...")
    result = run_passive_batch_fit(
        window=window,
        prior=prior,
        fan_heat_pass_record_hash="g8a_diagnostic_hash",
        home_id="V752_g8a_diagnostic",
        forward_chain=real_chain,
        context=context,
        mode_agreement_fraction=5.0,  # same as the test, for apples-to-apples
    )
    print("[3/3] Extracting diagnostics ...\n")

    laplace = result.laplace
    id_report = result.day2_posterior.identifiability_report

    prior_sigmas = np.asarray(prior.marginal_sigmas)
    prior_mean = np.asarray(prior.mean)
    posterior_mean = np.asarray(laplace.posterior_mean)
    posterior_cov = np.asarray(laplace.posterior_covariance)
    posterior_sigmas = np.sqrt(np.diag(posterior_cov))

    # =======================================================================
    # Section A: per-restart convergence — degeneracy vs local-optima diagnosis
    # =======================================================================
    print("-" * 78)
    print("A. PER-RESTART CONVERGENCE")
    print("-" * 78)
    print("If all 4 restarts converged to the same mode -> single-attractor")
    print("(likely degeneracy: the likelihood has one minimum and it's wrong).")
    print("If restarts diverged -> multi-attractor (local-optima issue).\n")

    restart_modes = np.asarray(laplace.restart_modes)
    restart_lps = np.asarray(laplace.restart_log_posteriors)

    print(f"  {'param':<28} " + " ".join(f"restart_{r}" for r in range(restart_modes.shape[0])))
    for i, name in enumerate(CANONICAL_PARAMETER_NAMES):
        vals = " ".join(f"{restart_modes[r, i]:>10.4g}" for r in range(restart_modes.shape[0]))
        print(f"  {name:<28} {vals}")
    print(f"\n  log_posteriors:                " + " ".join(f"{lp:>10.4g}" for lp in restart_lps))
    print(f"  optimizer_converged_all:       {laplace.optimizer_converged_all_restarts}")
    print(f"  mode_agreement_passed:         {laplace.mode_agreement_passed}  "
          f"(but mode_agreement_fraction was 5.0 = essentially disabled)")

    # Restart-to-restart disagreement in units of prior sigma
    disagreement = np.std(restart_modes, axis=0) / prior_sigmas
    print(f"\n  Restart-to-restart disagreement (in units of prior sigma):")
    for i, name in enumerate(CANONICAL_PARAMETER_NAMES):
        marker = ""
        if disagreement[i] > 0.5:
            marker = "  <-- LARGE: restarts found different modes here"
        elif disagreement[i] > 0.05:
            marker = "  <-- moderate"
        print(f"    {name:<28} {disagreement[i]:>8.4f} * sigma_prior{marker}")
    print(f"\n  max disagreement: {disagreement.max():.4f} sigma_prior on "
          f"{CANONICAL_PARAMETER_NAMES[int(np.argmax(disagreement))]}")
    print("  Production default mode_agreement_fraction = 0.05 (5% of prior sigma).")
    print("  If max disagreement >> 0.05, production discipline would have rejected this fit.")

    # =======================================================================
    # Section B: Hessian spectrum — degeneracy fingerprint
    # =======================================================================
    print("\n" + "-" * 78)
    print("B. HESSIAN EIGENSTRUCTURE")
    print("-" * 78)
    print("Hessian = inverse posterior covariance. Small eigenvalues correspond")
    print("to directions in parameter space where data does NOT constrain theta.")
    print("Large condition number = posterior is on a near-degenerate ridge.\n")

    eigvals = np.asarray(laplace.hessian_eigenvalues)
    cond = float(laplace.hessian_condition_number)
    print(f"  Eigenvalues (ascending): {sorted(eigvals.tolist())}")
    print(f"  Condition number kappa = {cond:.4g}")
    if cond > 1e6:
        print(f"  ** kappa > 1e6: posterior is severely degenerate **")
    elif cond > 1e4:
        print(f"  ** kappa > 1e4: posterior has substantial degeneracy **")
    elif cond > 1e2:
        print(f"  kappa moderate")
    else:
        print(f"  kappa low: posterior is well-conditioned, fit is genuinely confident")
    print(f"  Hessian positive-definite: {laplace.hessian_positive_definite}")

    # =======================================================================
    # Section C: ridge vectors — WHICH parameter combinations are degenerate
    # =======================================================================
    print("\n" + "-" * 78)
    print("C. RIDGE VECTORS — degenerate parameter combinations")
    print("-" * 78)
    print("Each ridge vector is an eigenvector of the Hessian with a small")
    print("eigenvalue. Its loadings tell us WHICH parameter combinations the")
    print("data fails to constrain. Loading magnitudes near 1 indicate the")
    print("parameter is heavily involved in the degenerate combination.\n")

    ridge_vectors = id_report.hessian_spectrum.get("ridge_vectors", [])
    joint_flag = id_report.hessian_spectrum.get("joint_identifiability_flag", False)

    print(f"  joint_identifiability_flag: {joint_flag}")
    print(f"  Number of ridge vectors flagged: {len(ridge_vectors)}")
    if not ridge_vectors:
        print("  No ridge vectors flagged — the production identifiability check")
        print("  did not classify any direction as degenerate. (May still be near-degenerate")
        print("  if condition number is large — see Section B.)")
    for k, rv in enumerate(ridge_vectors):
        print(f"\n  Ridge vector {k+1}: eigenvalue = {rv['eigenvalue']:.4g}")
        # Sort loadings by absolute value
        loadings = rv["loadings"]
        sorted_loads = sorted(loadings.items(), key=lambda kv: abs(kv[1]), reverse=True)
        for name, w in sorted_loads:
            bar = "*" * max(0, int(abs(w) * 30))
            print(f"    {name:<28} {w:>+8.4f}  {bar}")

    # =======================================================================
    # Section D: per-parameter — prior, posterior, theta_true, where did it go?
    # =======================================================================
    print("\n" + "-" * 78)
    print("D. PER-PARAMETER: posterior vs prior vs theta_true")
    print("-" * 78)
    print("Distances are in units of prior sigma. Negative means below prior mean.\n")

    print(f"  {'param':<28} {'prior_mean':>12} {'theta_true':>12} {'posterior':>12} "
          f"{'tt-from-pm':>12} {'pst-from-pm':>12} {'pst-from-tt':>14}")
    print("  " + "-" * 110)
    for i, name in enumerate(CANONICAL_PARAMETER_NAMES):
        pm = prior_mean[i]
        ps = prior_sigmas[i]
        tt = THETA_TRUE_PERTURBED[i]
        ps_post = posterior_mean[i]
        tt_from_pm = (tt - pm) / ps
        post_from_pm = (ps_post - pm) / ps
        post_from_tt = (ps_post - tt) / np.sqrt(posterior_cov[i, i])
        print(f"  {name:<28} {pm:>12.4g} {tt:>12.4g} {ps_post:>12.4g} "
              f"{tt_from_pm:>+11.3f}σp {post_from_pm:>+11.3f}σp {post_from_tt:>+13.3f}σpost")

    print("\n  Reading: if posterior is far from theta_true in units of POSTERIOR sigma,")
    print("  the fit is confidently wrong (rather than appropriately uncertain).")

    # =======================================================================
    # Save the full structure to JSON for later analysis
    # =======================================================================
    diagnostic = {
        "window_duration_hours": 48.0,
        "theta_true": THETA_TRUE_PERTURBED.tolist(),
        "parameter_names": list(CANONICAL_PARAMETER_NAMES),
        "prior_mean": prior_mean.tolist(),
        "prior_marginal_sigmas": prior_sigmas.tolist(),
        "posterior_mean": posterior_mean.tolist(),
        "posterior_covariance": posterior_cov.tolist(),
        "posterior_sigmas": posterior_sigmas.tolist(),
        "restart_modes": restart_modes.tolist(),
        "restart_log_posteriors": restart_lps.tolist(),
        "restart_disagreement_over_prior_sigma": disagreement.tolist(),
        "hessian_eigenvalues": eigvals.tolist(),
        "hessian_condition_number": cond,
        "hessian_positive_definite": laplace.hessian_positive_definite,
        "mode_agreement_passed_relaxed": laplace.mode_agreement_passed,
        "identifiability_report_per_parameter": id_report.per_parameter,
        "identifiability_report_hessian_spectrum": id_report.hessian_spectrum,
        "identifiability_report_summary": id_report.summary,
    }
    out_path = Path("/tmp/g8a_diagnostics.json")
    with open(out_path, "w") as f:
        json.dump(diagnostic, f, indent=2)
    print(f"\n  Full diagnostic structure written to: {out_path}")
    print("=" * 78)


if __name__ == "__main__":
    main()
