# `aivu_greybox` v0.1 — Section 10: Test plan

**Status:** v1.1 draft, 2026-05-13 (revision: §12 invariants registered in §10.5 coverage matrix upon §12 v1 closure same day). Anchored against §§1-12 (with §7 pending). §10 specifies the test plan that validates `aivu_greybox` v0.1 against its §9 invariants, its §3.2 performance ceilings, and its §3.3 cross-platform reproducibility commitment. The pilot-blocking subset is named explicitly; the remainder constitutes v0.2 work that does not gate the Phoenix pilot.

---

## 10.1 Position of §10 in the greybox spec

§10 is the verification layer. Three distinct test classes operate on `aivu_greybox` v0.1:

- **Closed-loop posterior recovery against `aivu_corpus` synthetic trajectories** (§10.2). Known parameters in via the forward chain, posterior out via greybox, recovery checked against the known parameters. This is the load-bearing functional test.
- **Performance-ceiling verification** (§10.3). The three ceilings in §3.2 — Day-1-2 batch ≤ 24h wall-clock, Day-4-5 batch ≤ 24h wall-clock, Phase 2 per-cycle ≤ 100 ms — verified on representative HPM hardware.
- **Cross-platform numerical reproducibility** (§10.4). The §3.3 architectural commitment to bit-identical posteriors across macOS development and embedded Linux deployment, tested at two gates: the v0.1 architectural gate (bit-identity, per §3.3) and the relaxed pilot-test gate (10⁻⁵ relative, per roadmap B3 softening).

Every invariant in §9 maps to at least one test in §10.2, §10.3, or §10.4. The mapping is enumerated in §10.5 as the invariant-coverage matrix.

§10 does not specify field tests on the pilot home. Those are pilot operations (Workstream F in the roadmap), governed by the 5-Day commissioning protocol's operational document. §10's scope is the package, not its deployment.

---

## 10.2 Closed-loop posterior recovery

### 10.2.1 Methodology

Closed-loop recovery is the package-family symmetry property §1.4 makes load-bearing: every parameter `aivu_greybox` identifies is a parameter `aivu_dynamic` consumes, and every observable `aivu_greybox` conditions on is an output the forward chain produces. The test:

1. **Choose a parameter vector** θ_true from the test corpus.
2. **Run the forward chain** (`aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2) with θ_true and a specified excitation schedule, producing a synthetic 1 Hz telemetry trajectory.
3. **Run greybox** on that telemetry, producing a posterior over θ.
4. **Check recovery** against θ_true: per-parameter posterior tightness and 95% credible-interval coverage.

The forward chain is the same code path that the live pilot uses to *predict* what the home will do; the greybox inverse path is the same code path that the live pilot uses to *identify* what the home is doing. Running them against each other is the strongest in-package consistency check available before pilot data exists.

### 10.2.2 Pass criteria

For each parameter in each test configuration, two checks apply:

- **Tightness check.** Achieved relative posterior standard deviation σ_post / μ_post ≤ the §5.5 (passive) or §6.4 (active-compounded) expected value for that parameter. A configuration that achieves tightness within expectation passes; a configuration that achieves tightness > 2× expectation fails per §8 Diagnostic 2's `degraded` breakpoint.
- **Coverage check.** The posterior's 95% credible interval covers θ_true for that parameter. Coverage failure on more than 5% of corpus rows indicates the posterior is over-confident — a more serious failure than tightness underperformance, because it means signed records report tighter constraints than the data actually supports.

A test configuration passes when **both** checks pass on all six parameters across all configured corpus rows. Tightness failure on a single parameter is investigated; coverage failure on more than the 5% threshold is a v0.1 release blocker.

### 10.2.3 Test configurations

Three configurations are specified, mapping to the three batch-fit modes:

**Configuration 1 — §5 Day-1-2 passive batch fit.** The pilot-blocking case. Excitation schedule: programmed 10 min/hr fan mixing, compressor off, heat strip off, OA dampers closed. Forward-chain conditions: Phoenix-July (climate file from `aivu_corpus`), V752 or V752-class envelope geometry, foam-attic configuration. Telemetry window: 48 hours. Expected posterior tightness per the §5.5 table (5% / 5% / 30% / 15% / 25% / 15% on `R_eff` / `C_house` / `cfm50` / `F_slab` / `C_w` / `ceiling_coupling_factor`).

**Configuration 2 — §6 Days-4-5 active-perturbation batch fit.** The pilot-blocking case for the second commissioning fit. Excitation schedule: the four-phase protocol from §6.2 (Phase A 18h continuous-fan continuous-compressor at full capacity; Phase B 6h decay; Phase C 18h reverse drive fan-only; Phase D 6h closing). Inherits §5 posterior as prior. Expected posterior tightness per the §6.4 table (1% / 1.5% / 8% / 5% / 8% / 4%).

**Configuration 3 — §7 recursive-mode Phase 2 solver.** Pending §7 spec; placeholder included for completeness. The recursive-mode test consumes a long telemetry trajectory (months, not days) and verifies that the per-cycle posterior update stays calibrated as parameters drift. Configuration 3 lands when §7 lands.

### 10.2.4 Corpus rows

Per §1.4 deliverables, two corpus configurations are tested:

- **17-row demonstration corpus.** The compact corpus established by `aivu_corpus` v0.2 §3 for demonstrating recovery across the canonical parameter ranges. Spans the central region of the six-parameter space at Phoenix-July climate. Pass on the 17-row demonstration corpus is the **pilot-test gate** for §10.2.
- **20-row full-corpus recipe.** The extended corpus exercising the tails of the parametric space — climate × envelope × HVAC combinations at the edges. Pass on the 20-row corpus is the v0.2 release target; v0.1 does not block on full-corpus pass, but each row's recovery result is logged for cohort-level analysis as the pilot scales.

The B2 roadmap softening narrows the v0.1 closed-loop validation to the 17-row demonstration corpus plus the Phoenix-July foam-attic slice of the 20-row recipe. Full 20-row pass returns as v0.2 work when the deployed cohort expands.

---

## 10.3 Performance-ceiling verification

### 10.3.1 The three ceilings

§3.2 pins three wall-clock ceilings. Each is verified by a distinct test:

- **Day-1-2 batch fit ≤ 24 hours.** Measured on representative HPM hardware (the SoC selected via D2, in progress with Device Solutions) running Configuration 1 telemetry. Expected actual time is well below 24 hours; the ceiling exists to constrain implementation choices.
- **Day-4-5 batch fit ≤ 24 hours.** Same hardware, Configuration 2 telemetry, inheriting the Configuration 1 posterior as prior.
- **Phase 2 per-cycle update ≤ 100 ms.** Per-cycle recursive update on representative HPM hardware. Verified per §3.2's commitment that 100 ms gives 10× headroom against 1 Hz telemetry cadence and leaves room for `aivu_integrity`'s per-packet signing and MMR append. Verification lands when §7 lands (recursive-mode is §7's scope).

### 10.3.2 Pass criteria

For each ceiling: 95th-percentile wall-clock across at least 100 independent runs (different corpus rows, same hardware) must be at or below the §3.2 ceiling. 95th-percentile rather than median because the ceiling is what a pilot-deployed HPM must guarantee, not what it averages.

If the 95th-percentile result is comfortably below the ceiling (≤ 50% of ceiling), the ceiling is documented as "comfortable" and stays at §3.2's value. If the result is tight (50-100% of ceiling), the ceiling is documented as "tight" and the v0.2 spec considers raising it. If the result exceeds the ceiling, v0.1 has a release blocker.

### 10.3.3 Hardware dependency

§10.3 cannot run until D2 (SoC + Linux stack selection, in active conversation with Device Solutions per the May 12 roadmap entry) settles. The reference HPM hardware is the deliverable D2 produces. The closed-loop recovery in §10.2 runs on whatever development hardware is available; only the performance-ceiling tests in §10.3 strictly require the production SoC.

---

## 10.4 Cross-platform numerical reproducibility

### 10.4.1 The two gates

§3.3 commits `aivu_greybox` to bit-identical posteriors across macOS development and embedded Linux deployment. The architectural reason is the §6 Delta 7 integrity property: a posterior committed via threshold attestation on one platform must be reproducible on the other for external verification to be meaningful.

§10.4 runs the cross-platform check at **two gates**, both reported:

- **Architectural gate (bit-identity).** The §3.3 commitment. Run identical Configuration 1 telemetry through identical greybox versions on macOS and on the D2-selected Linux target; serialize the posterior objects; check bit-identity of the serialized representations.
- **Pilot-test gate (10⁻⁵ relative).** The roadmap B3 softening for v0.1. The same posterior comparison, with the pass criterion relaxed to `‖θ_macOS − θ_Linux‖ / ‖θ_macOS‖ ≤ 10⁻⁵` on the posterior mean vector and corresponding tolerance on the diagonal of the covariance matrix. The 10⁻⁵ floor is five orders of magnitude below the measurement noise floor.

### 10.4.2 What ships, what is logged

The pilot ships when the **10⁻⁵ gate passes**. The bit-identity result is reported alongside but does not gate v0.1 release. Two cases:

- **Both gates pass.** §3.3's architectural commitment is satisfied; bit-identity hardening for v0.2 is unnecessary. Document and move on.
- **10⁻⁵ gate passes, bit-identity gate fails.** Pilot ships. The bit-identity gap is logged as a v0.2 hardening item; root-causing the bit-identity loss (typically a BLAS-version mismatch, ODE-integrator step-control nondeterminism, or compiler-flag drift) becomes pre-Clearinghouse work since external-verifier reproducibility requires bit-identity.
- **10⁻⁵ gate fails.** v0.1 has a release blocker. Investigate before pilot.

The two-gate structure is the explicit consequence of relaxing the §3.3 architectural commitment for the pilot only; v0.2 hardens back to bit-identity when the Clearinghouse's external-verifier role becomes live.

### 10.4.3 Test mechanics

The reproducibility test produces a side-by-side posterior comparison artifact:

```
reproducibility_report:
  greybox_version:      str
  numpy_version:        str
  scipy_version:        str
  blas_implementation:  str
  ode_integrator:       str
  test_input_corpus_row: str
  posterior_macos:
    mean:               [float, ...]    # 6-vector
    covariance:         [[float, ...], ...]  # 6x6
  posterior_linux_d2:
    mean:               [float, ...]
    covariance:         [[float, ...], ...]
  bit_identity_gate:
    passed:             bool
    serialized_hash_match: bool
  relative_agreement_gate:
    mean_relative_error:     float
    cov_diagonal_relative_error: [float, ...]
    passed:             bool       # all elements ≤ 1e-5
```

The report is itself signed via `aivu_integrity` and becomes part of the v0.1 release artifact.

---

## 10.5 Invariant coverage matrix

Every invariant in §9.2 maps to at least one test class. The matrix below is the canonical mapping; missing entries indicate a v0.1 spec gap rather than an acceptable omission.

| Invariant | Origin | Covered by |
| --- | --- | --- |
| INV-FH-1 (no batch fit on Fan-Heat-Fail) | §4 | §10.2.3 (negative test: synthetic FanHeatFail prerequisite, expect refusal) |
| INV-FH-2 (Fan-Heat window must be valid) | §4 | §10.2.3 (negative test: malformed Fan-Heat window, expect rejection) |
| INV-FH-3 (records complete and externally verifiable) | §4 | §10.2.3 (signed-record verification: external re-derivation of `η̂_distribution` and `R_FH` from telemetry) |
| INV-FH-4 (`η_distribution` is Day-1 prior, not final) | §4 | §10.2.3 (Configuration 2 propagation test: §4-identified value enters §6 as prior, not as fixed value) |
| INV-FIT12-1 (`FanHeatPass` prerequisite for §5) | §5 | §10.2.3 (negative test) |
| INV-FIT12-2 (§5 operational-mode adherence) | §5 | §10.2.3 (negative test: telemetry with compressor-on samples, expect window rejection) |
| INV-FIT12-3 (prior provenance signed metadata at end of §5) | §5 | §10.2.3 (signed-record verification) |
| INV-FIT12-4 (convergence diagnostics gate signing) | §5 | §10.2.3 (negative test: non-converged fit, expect no `Day2Posterior` emission) |
| INV-FIT12-5 (identifiability flags preserved) | §5 | §10.2.3 (signed-record verification: flag presence in `Day2Posterior`) |
| INV-FIT12-6 (fan-mixing schedule signed into window metadata) | §5 | §10.2.3 (signed-record verification: schedule timestamps recoverable from record) |
| INV-FIT12-7 (warmup observations preserved) | §5 | §10.2.3 (signed-record verification: `T_attic^obs(k)` series in `Day2Posterior` artifact) |
| INV-FIT12-8 (two-channel likelihood structure) | §5 | §10.2.2 (recovery test: `ceiling_coupling_factor` recovery depends on two-channel evaluation per §5.5) |
| INV-FIT45-1 (§6 prerequisite: `Day2Posterior`) | §6 | §10.2.3 (negative test) |
| INV-FIT45-2 (§6 prerequisite: Day-3 map) | §6 | §10.2.3 (negative test) |
| INV-FIT45-3 (HPM command authority via thermostat API pass-through) | §6 | §10.2.3 (negative test: simulated thermostat-only deployment, expect §6 refusal) |
| INV-FIT45-4 (excitation protocol adherence within tolerance) | §6 | §10.2.3 (positive and negative tests: within-tolerance and outside-tolerance excitation) |
| INV-FIT45-5 (prior-provenance chain preserved §5 → §6) | §6 | §10.2.3 (signed-record verification: §5 posterior hash in `Day5Posterior` record) |
| INV-FIT45-6 (convergence diagnostics gate signing) | §6 | §10.2.3 (negative test) |
| INV-FIT45-7 (`η_distribution` held at Day-1 value) | §6 | §10.2.3 (positive test: confirm §6 does not modify `η_distribution`) |
| INV-ID8-1 (all four diagnostics on every posterior) | §8 | §10.2.3 (signed-record verification: identifiability report present) |
| INV-ID8-2 (ρ > 0.95 fires per-parameter flag) | §8 | §10.2.2 (synthetic prior-only test: parameter with no informative data, expect ρ ≈ 1 and flag) |
| INV-ID8-3 (joint-identifiability flag on κ > 10⁶ or λ ridge) | §8 | §10.2.2 (synthetic ridge test: parameter pair under known degeneracy, expect joint flag) |
| INV-ID8-4 (§8 does NOT gate signing) | §8 | §10.2.3 (positive test: flagged posterior is signed and emitted) |
| INV-ID8-5 (§8 does NOT modify the posterior) | §8 | §10.2.3 (positive test: byte-equal posterior pre- and post-§8) |
| INV-ID8-6 (flags propagate forward) | §8 | §10.2.3 (Configuration 2 verification: §5 flags present in §6 input) |
| INV-ID8-7 (expected-tightness table by reference) | §8 | §10.2.3 (positive test: modify §5.5 table, observe §8 picks up new values without code change) |
| INV-ID8-8 (Laplace vs. NUTS/HMC interface invariant) | §8 | v0.2 test, when NUTS/HMC fallback lands |
| INV-SIGN12-1 (every record signed before emission) | §12 | §10.2.3 (signed-record verification: every emitted record carries a signature) |
| INV-SIGN12-2 (sign-then-log paired sequence) | §12 | §10.2.3 (negative test: emit signed record without log append, expect rejection downstream) |
| INV-SIGN12-3 (correct AttestationMoment per Birth Certificate half) | §12 | §10.2.3 (positive test: Day-2 carries `envelope_half_initial`; Day-5 carries `envelope_half_final`; Day-3 map carries `hvac_half`) |
| INV-SIGN12-4 (stub-attestation flag honesty) | §12 | §10.2.3 (positive test: v0.1 stub-attestation payload carries the post-pilot-replacement-required flag) |
| INV-SIGN12-5 (signing interface invariance v0.1 → post-pilot) | §12 | v0.2+ test, when live threshold attestation lands; v0.1 verifies the contract is stable (function signatures unchanged) |
| INV-SIGN12-6 (inclusion proofs retrievable post-hoc) | §12 | §10.2.3 (positive test: retrieve a record by content-addressed hash from a previously-written log; verify inclusion proof) |
| INV-SIGN12-7 (monotonic timestamps strictly increasing) | §12 | §10.2.3 (negative test: attempt to write a record with non-increasing timestamp, expect rejection) |

§7 invariants are not represented in the matrix because §7 has not yet been drafted; §10.5 is updated when §7 lands.

The matrix is the artifact §9.4's update discipline cross-references. A new invariant in §4-§8 must land in §10.5 in the same revision; an invariant in §10.5 without a corresponding row in §9.2 is a spec inconsistency.

---

## 10.6 Out of scope

The following are explicitly out of §10 v0.1:

- **Cohort-level analysis across pilot homes.** When N pilot homes have produced N posteriors, cross-home consistency analysis is a Clearinghouse concern, not a greybox test.
- **Field tests on the pilot home itself.** Workstream F (operational protocol) and the 5-Day commissioning protocol document own the field-test methodology. §10 validates the package against synthetic trajectories before deployment; pilot data validates the deployment.
- **Production monitoring.** Runtime alerting, drift detection in the field, and the Clearinghouse-level integrity audit are operational concerns, not §10 concerns.
- **Performance regression tracking across greybox versions.** A continuous benchmark suite tracking how §3.2 performance evolves over greybox versions is a v0.2 concern; v0.1 verifies the ceilings once.
- **Full 20-row corpus pass.** v0.1 narrows to the 17-row demonstration corpus plus the Phoenix-July foam-attic slice of the 20-row recipe per roadmap B2. Full 20-row pass is v0.2 work.
- **Adversarial / fuzz testing of the signed-record format.** Robustness of `aivu_integrity`'s signature verification against malformed inputs belongs in `aivu_integrity`'s own test suite, not in greybox's.

---

*End of §10 v1.1 draft. Three test classes pinned: closed-loop posterior recovery against `aivu_corpus` (17-row demonstration corpus + Phoenix-July slice of 20-row recipe, two gates per parameter — tightness against §5.5/§6.4 expectations and 95% credible-interval coverage on θ_true); performance-ceiling verification (§3.2 ceilings, 95th-percentile across ≥100 runs, on D2-selected HPM hardware); cross-platform reproducibility (bit-identity architectural gate plus 10⁻⁵ relative pilot-test gate, both reported, pilot ships on the relaxed gate). Invariant-coverage matrix maps 32 of 34 §9 invariants to specific v0.1 tests; INV-ID8-8 (NUTS/HMC interface) and INV-SIGN12-5 (live threshold attestation contract stability) are v0.2+ tests. §11 (common utilities) opens next.*
