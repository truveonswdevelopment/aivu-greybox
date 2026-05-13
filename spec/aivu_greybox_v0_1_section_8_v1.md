# `aivu_greybox` v0.1 — Section 8: Identifiability collapse detection and posterior tightness

**Status:** v1 draft, 2026-05-13. Anchored against §§1-7 (with §§1-3 v0.1.1, §4 v3, §5 v3.3, §6 v3 closed; §7 pending). The six-parameter canonical set is `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}` per §§1-3 v0.1.1. Inherits: the Laplace posterior shape from §5.6 (mean = Hessian-mode, covariance = inverse Hessian at the mode); the per-parameter prior from §5.4; the expected per-parameter posterior-tightness tables from §5.5 (passive) and §6.4 (active-compounded). §8 produces signed metadata that travels with every greybox posterior — it does not produce a separate signed artifact.

---

## 8.1 Position of §8 in the greybox pipeline

§§5 and §6 each end by emitting a multivariate posterior over the six canonical parameters. §8 is the diagnostic layer that runs **after** the posterior is computed and **before** the signed record is emitted. The signed record consists of the posterior (mean + covariance) plus §8's diagnostic outputs as load-bearing metadata. §5 INV-FIT12-5 and §6's matching invariant both require that §8's outputs be part of the signed record, not a side report.

§8 runs in two modes that share the same primitives:

- **Batch mode** — invoked at end-of-Day-2 (after §5) and end-of-Day-5 (after §6). Operates on the just-computed posterior against the prior that fed the fit. This is the mode that produces the signed metadata on the §5 and §6 posteriors.
- **Recursive mode** — invoked at heartbeat cadence by §7 during Phase 2 ongoing-Cx. Operates on the current Kalman-class posterior against the previous posterior (treated as the recursive-mode prior). §7 specifies the cadence; §8 specifies the diagnostic logic, which is the same regardless of mode.

§8 does not modify the posterior. It does not re-run the fit. It does not gate signing — the posterior is signed regardless of what §8 finds. What §8 controls is whether downstream consumers see a clean posterior or a posterior flagged on one or more parameters.

---

## 8.2 The four diagnostics

§8 produces four diagnostic outputs per fit. All four are emitted for every posterior; none is optional. The first two operate per-parameter; the second two operate on the joint posterior.

### Diagnostic 1 — Per-parameter identifiability flag (prior-only test)

For each of the six canonical parameters, compute the ratio of marginal posterior standard deviation to prior standard deviation:

> ρ_i = σ_posterior,i / σ_prior,i

The posterior marginal σ_posterior,i is the square root of the i-th diagonal element of the posterior covariance matrix. The prior marginal σ_prior,i comes from the §5.4 prior interface.

The flag fires when **ρ_i > 0.95**. A parameter whose marginal posterior is 95% or more of its marginal prior width has been moved essentially not at all by the fit — the data carries no information about it, and the posterior is effectively prior-only on that parameter.

The 0.95 threshold is conservative: a properly identified parameter under Phoenix-July §5 conditions should hit ρ ≲ 0.30 on the well-identified parameters and ρ ≲ 0.50 on the loosely-identified ones (computed from the §5.5 expected-tightness table relative to typical prior widths). A 0.95 reading means something has gone structurally wrong, not that the data was weak — weak data produces ρ in the 0.5-0.8 range without firing the flag.

The threshold is pinned at 0.95 for v0.1. Pilot data will determine whether a tighter threshold (e.g., 0.85) is warranted to catch borderline cases earlier. Bookkeeping decision; if the threshold moves, it moves uniformly across all six parameters and the change is documented in the §8 revision header.

### Diagnostic 2 — Per-parameter posterior-tightness assessment against §5.5 / §6.4 expectations

For each parameter, compare the achieved relative posterior tightness `σ_posterior,i / μ_posterior,i` against the §5.5 or §6.4 expected range for that parameter under the protocol that produced this posterior.

The expected tightness table from §5.5 (end-of-Day-2, passive forcing, Phoenix-July) is:

| Parameter | Expected `σ_post / μ_post` |
| --- | --- |
| `R_eff` | ≲ 5% |
| `C_house` | ≲ 5% |
| `ceiling_coupling_factor` | ≲ 15% |
| `F_slab` | ≲ 15% |
| `C_w` | ≲ 25% |
| `cfm50` | ≲ 30% |

The §6.4 table for end-of-Day-5 (compounded passive + active) is tighter across the board:

| Parameter | Expected `σ_post / μ_post` |
| --- | --- |
| `R_eff` | ≲ 1% |
| `C_house` | ≲ 1.5% |
| `ceiling_coupling_factor` | ≲ 4% |
| `F_slab` | ≲ 5% |
| `C_w` | ≲ 8% |
| `cfm50` | ≲ 8% |

For each parameter, §8 emits one of three states:

- `within` — achieved tightness within the expected range (≤ table value).
- `loose` — achieved tightness exceeds the expected range by ≤ 2×. The posterior is usable but wider than predicted; the gap is logged for cohort-level analysis.
- `degraded` — achieved tightness exceeds the expected range by > 2×. The posterior is signed but flagged; downstream consumers must treat the parameter as substantially less constrained than the protocol nominally delivers.

The 2× breakpoint between `loose` and `degraded` is the v0.1 default. As with Diagnostic 1's threshold, pilot data determines whether the breakpoint is right. If a parameter consistently lands `loose` across pilot homes, the §5.5 / §6.4 expectation table needs updating, not the breakpoint.

Diagnostic 2 does not duplicate Diagnostic 1. Diagnostic 1 detects structural failure (the data said nothing); Diagnostic 2 detects performance gap (the data said less than the protocol predicted). A parameter can be `within` on Diagnostic 1 (well-moved from prior) and `degraded` on Diagnostic 2 (moved less than expected). Both signals are independently informative.

### Diagnostic 3 — Hessian eigenvalue spectrum (ridge detection on the joint posterior)

The per-parameter diagnostics above are blind to joint identifiability failure. Two parameters can each be well-identified marginally while being jointly under-determined along a ridge in the posterior — moving along the ridge changes both parameters together but does not change the likelihood. The §5.5 discussion of `R_eff` × `ceiling_coupling_factor` joint identifiability anticipates exactly this concern.

§8 emits the full eigenvalue spectrum of the Hessian at the mode. From the spectrum, two derived quantities:

- **Condition number** κ = λ_max / λ_min. A condition number above ~10⁶ indicates the posterior has a near-degenerate direction — a ridge along which the likelihood is effectively flat. Reported as a scalar.
- **Ridge-vector list.** Each eigenvector with eigenvalue λ_i < 10⁻⁴ × λ_max is emitted along with its eigenvalue and its parameter-loading profile (which canonical parameters contribute to the ridge direction, with what sign). A ridge-vector that loads heavily on two parameters is the signature of joint identifiability failure between those parameters.

The two thresholds (κ > 10⁶, λ_i < 10⁻⁴ × λ_max) are coupled: a posterior with κ ≤ 10⁶ has no λ_i below 10⁻⁴ × λ_max by construction, so the ridge-vector list is empty exactly when the condition number is below threshold. Both are emitted regardless — downstream consumers may want the spectrum even when no ridge fires.

When the ridge-vector list is non-empty, §8 raises a **joint-identifiability flag** naming the parameters that load on each ridge. The §5 protocol cannot resolve such a ridge from passive data alone; the standard remediation is §6 active perturbation, which by construction provides excitation in directions the passive fit cannot. If a §6 posterior still emits a joint-identifiability flag, the ridge is structural and the parameters in question cannot be resolved by the v0.1 protocols at this site; the signed record carries the flag and downstream consumers route accordingly.

### Diagnostic 4 — Per-parameter posterior-prior KL divergence

The third per-parameter diagnostic, complementary to Diagnostic 1. For each parameter, compute the KL divergence between the marginal posterior and the marginal prior:

> D_KL,i = KL(posterior_marginal_i ‖ prior_marginal_i)

For Gaussian marginals (the Laplace approximation guarantees this), the closed form is:

> D_KL,i = ½ × [log(σ_prior,i² / σ_posterior,i²) + (σ_posterior,i² + (μ_posterior,i − μ_prior,i)²) / σ_prior,i² − 1]

Diagnostic 1's ratio test catches "the posterior is the prior in disguise" but is blind to a posterior that has the same width as the prior but has *moved* in mean — that is information, and Diagnostic 1 misses it. D_KL captures both: a posterior identical to the prior gives D_KL = 0; any deviation in mean or variance increases D_KL.

D_KL is emitted as a numeric value per parameter. It is not gated against a threshold in v0.1 — the value is logged in the signed record for cohort-level analysis. Pilot data will determine whether a threshold (e.g., D_KL < 0.01 nats fires a complementary flag to Diagnostic 1) earns its place in v0.2.

The Laplace assumption matters here. If the v0.2 NUTS/HMC fallback (§5.6 commitment) is invoked, the posterior marginals are no longer guaranteed Gaussian, and D_KL is computed numerically from the marginal samples rather than from the closed form. The interface contract is the same; the implementation differs.

---

## 8.3 What §8 emits

§8's output is a structured diagnostic record that travels as signed metadata with the posterior. The schema in v0.1:

```
identifiability_report:
  protocol: "§5_day2_passive" | "§6_day5_active_compounded" | "§7_recursive_mode"
  per_parameter:
    R_eff:
      rho:                       float            # Diagnostic 1
      identifiability_flag:      bool             # Diagnostic 1
      tightness_state:           "within"|"loose"|"degraded"  # Diagnostic 2
      sigma_post_over_mu_post:   float            # Diagnostic 2
      sigma_post_over_mu_post_expected: float     # from §5.5 or §6.4 table
      D_KL_nats:                 float            # Diagnostic 4
    C_house: ...
    cfm50: ...
    F_slab: ...
    C_w: ...
    ceiling_coupling_factor: ...
  hessian_spectrum:                               # Diagnostic 3
    eigenvalues:                 [float, ...]
    condition_number:            float
    ridge_vectors:               [{eigenvalue, loadings: {param: float}}, ...]
    joint_identifiability_flag:  bool
  summary:
    any_identifiability_flag:    bool             # OR of per-param flags + joint flag
    any_degraded_tightness:      bool             # any parameter at "degraded"
```

The report is consumed by:

- **§5 → §6**: §6 reads per-parameter identifiability flags from the end-of-Day-2 report and routes Phase A/B/C/D excitation accordingly (a parameter flagged at end-of-Day-2 is one §6 should aim to identify).
- **§7 ongoing-Cx**: per-parameter flags propagate forward as the recursive-mode prior interface. A parameter flagged at end-of-Day-5 enters ongoing-Cx as a parameter the recursive solver should monitor for drift but should not over-weight.
- **§12 signing chain**: the report is part of the signed Day-2 and Day-5 records that become the envelope and HVAC halves of the Digital Birth Certificate.
- **Clearinghouse**: per-home reports aggregate into a cohort-level distribution of identifiability outcomes. Homes that consistently flag the same parameter point to a protocol gap; homes that flag idiosyncratically point to site-specific noise.

---

## 8.4 What §8 does not do

§8 does not gate signing. The posterior is signed with or without flags. The architectural reason: an unflagged signed posterior is a positive claim about parameter identification; a flagged signed posterior is a positive claim about which parameters were not identified. Both are load-bearing records. Suppressing flagged posteriors would erase the negative-result information that the cohort-level dataset depends on.

§8 does not re-run the fit. If a flag fires, the recourse is §6 (after §5) or the next ongoing-Cx window (after §7), not a re-fit on the same data. Re-fitting under different starting conditions and surfacing whichever run produces no flags would be a quiet form of result-shopping.

§8 does not adjust the prior. A loose posterior on `cfm50` at end-of-Day-2 does not cause §6 to widen its prior on `cfm50`. §6 inherits the §5 posterior as-is, flag and all.

§8 does not contain physics. It operates on the abstract posterior shape and on the prior. The parameter names are the only physics-aware element; everything else (Hessian eigenvalues, KL divergence, ratios) is generic posterior diagnostics.

§8 does not specify the prior. The prior interface is §5.4. §8 reads the prior; it does not author it.

---

## 8.5 Invariants

**INV-ID8-1 — All four diagnostics MUST run on every greybox posterior.** §5 batch-mode, §6 batch-mode, and §7 recursive-mode are all in scope. A greybox implementation that emits a posterior without an accompanying identifiability report is non-compliant.

**INV-ID8-2 — Per-parameter flags fire at ρ > 0.95.** The threshold is pinned at 0.95 for v0.1. Implementations MUST NOT silently apply a different threshold; changes to the threshold MUST be documented in the §8 revision header and applied uniformly to all six parameters.

**INV-ID8-3 — Joint-identifiability flag fires when condition number κ > 10⁶ OR when any eigenvalue λ_i < 10⁻⁴ × λ_max.** Both conditions are emitted to the report regardless; the flag is the OR of the two.

**INV-ID8-4 — §8 does NOT gate signing.** A flagged posterior MUST be signed; suppression of flagged posteriors is non-compliant.

**INV-ID8-5 — §8 does NOT modify the posterior.** §8 reads, summarizes, and flags; it does not rescale, re-center, or re-fit. The posterior emitted by §5 or §6 is the posterior that gets signed.

**INV-ID8-6 — Flags propagate forward.** §6 MUST consume the §5 report's per-parameter flags and route protocol decisions accordingly per §6.4. §7 MUST consume the §6 report's per-parameter flags as input to recursive-mode operation. Downstream consumers (Clearinghouse, Digital Birth Certificate) MUST receive the flags as part of the signed record.

**INV-ID8-7 — The expected-tightness table is the §5.5 / §6.4 table.** §8 does not maintain its own expected-tightness expectations. Updates to the expected-tightness values happen in §5.5 or §6.4 and propagate to §8 by reference; §8 implementations MUST read the current §5.5 / §6.4 values rather than caching a snapshot.

**INV-ID8-8 — Laplace assumption surfaced explicitly.** Under the v0.1 Laplace approximation, Diagnostic 4's D_KL is computed in closed form. Under the v0.2 NUTS/HMC fallback per §5.6, D_KL is computed numerically from the marginal samples. The interface contract (D_KL emitted per parameter) is invariant across the algorithm-class substitution; implementations MUST NOT assume the closed-form path.

---

## 8.6 Out of scope

The following are explicitly out of §8 v0.1:

- **Posterior-predictive checks.** Running the forward model with samples drawn from the posterior and comparing to held-out data is a different diagnostic class. §6 Phase D does a structurally similar check internal to §6's own fit (the Phase D residual). A general posterior-predictive framework is v0.2 work.

- **Cohort-level identifiability analysis.** When N homes have produced N reports, the cross-home distribution of identifiability outcomes is itself a diagnostic — a parameter that flags `degraded` in 80% of homes points to a protocol problem, not a per-home problem. This analysis lives in the Clearinghouse, not in greybox.

- **Cross-validation between §5 and §6.** A §5 posterior on `R_eff` and a §6 posterior on `R_eff` ought to be statistically consistent; if they disagree at the > 3σ level, something is wrong with one of them. Spec for the §5-vs-§6 consistency check belongs to the version of greybox that introduces cross-fit validation, which is v0.2 at the earliest.

- **Confidence-interval communication to non-technical consumers.** A homeowner-facing version of the identifiability report — translating ρ values and KL divergences into "your home's envelope was well-characterized" / "your home's airtightness measurement is uncertain" — is a Clearinghouse product concern, not a greybox spec concern.

- **Adaptive protocol selection.** Using §8 outputs at end-of-Day-2 to *change* the §6 protocol (e.g., extend Phase A from 18h to 24h because `R_eff` is flagged) is interesting and probably right for v0.2. It is explicitly not in v0.1: the §6 protocol is fixed regardless of §5's report. The §5 report changes how §6's *output* is interpreted, not how the protocol is run.

---

*End of §8 v1 draft. Configuration parameters pinned: ρ flag threshold 0.95; tightness breakpoints "within" / "loose" (≤2× expected) / "degraded" (>2× expected); Hessian condition-number threshold 10⁶; ridge-vector eigenvalue threshold 10⁻⁴ × λ_max. Six-parameter canonical set unchanged: `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}`. Diagnostic 4 (D_KL) emitted as a value, not gated against a threshold in v0.1. §9 (invariants consolidation) opens next.*
