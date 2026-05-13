# `aivu_greybox` v0.1 — Section 9: Invariants consolidation

**Status:** v1.1 draft, 2026-05-13 (revision: §12 invariants folded in upon §12 v1 closure same day). Anchored against §§1-12 (§§1-3 v0.1.1, §4 v3, §5 v3.3, §6 v3, §8 v1, §10 v1, §11 v1, §12 v1 closed; §7 pending). §9 enumerates the full canonical invariant set referenced from §1.4 deliverables and §10 test plan. It introduces no new invariants of its own; updates to an invariant happen in its origin section, and §9 follows by reference.

---

## 9.1 Position of §9 in the greybox spec

§§4, 5, 6, 7, and 8 each name local invariants — protocol pre-conditions, signing requirements, propagation rules, and other normative constraints — at the end of the section that defines them. §9 collects them into one canonical enumeration so that downstream consumers do not have to chase five sections to know what `aivu_greybox` is required to guarantee.

§9 reproduces each invariant verbatim from its origin section. It does not summarize, paraphrase, or compress. The text of an invariant is the text in its origin section; §9 is the index, not an editorial pass. If a discrepancy arises between §9 and an origin section, the origin section wins by construction; §9 is updated to match.

Two views are emitted:

- **§9.2 — Origin-section enumeration.** The canonical list, grouped by the section that authors each invariant. This is the view §10 test plan iterates over.
- **§9.3 — Cross-cutting access patterns.** Invariants grouped by theme (signing chain, protocol adherence, prior provenance, identifiability, command authority, observation completeness). This is the view a reader uses to answer "what does greybox guarantee about signing?" without reading five sections.

---

## 9.2 Origin-section enumeration

### From §4 — Fan-Heat Consistency Check (INV-FH-1 through INV-FH-4)

**INV-FH-1 — No batch fit on Fan-Heat-Fail.** If the most recent Fan-Heat record for a home is a `FanHeatFail`, or if no `FanHeatPass` record exists, §5's passive-fit procedure and §6's active-perturbation-fit procedure MUST refuse to consume telemetry from this home's commissioning window. Implementations MUST raise an error if called in this state.

**INV-FH-2 — The window must be a fan-only window with spatial uniformity.** The damper-closed, compressor-off, heat-strip-off, moisture-stability, and spatial-uniformity constraints in §4.4 are not optional. A window violating any of them is not a Fan-Heat window; computing identification on such a window and emitting either a Pass or Fail record on the basis of that computation is a protocol violation that voids the resulting record. Implementations MUST reject non-conforming windows rather than compute on them.

**INV-FH-3 — Records are complete and externally verifiable.** Every `FanHeatPass` and `FanHeatFail` record MUST contain the full set of fields in §4.5, committed via the `aivu_integrity` API. An external verifier holding the HPM's public key, the relevant 1 Hz telemetry packets (served on demand per §2.5), and the MMR inclusion proofs MUST be able to re-derive `η̂_distribution` and `R_FH` and re-check both pass conditions independently. No part of the check may rely on intermediate state outside the record.

**INV-FH-4 — `η_distribution` identified by Fan-Heat is the Day-1 prior for §6, not the final value.** The identified `η̂_distribution` and its uncertainty established at Day-1 MUST be consumed by §6 as the prior for active-perturbation joint refinement, not treated as a fixed parameter for the remainder of the 5-Day window. Treating Fan-Heat's identification as final would discard the joint-identification structure that makes envelope and equipment parameters independently observable under §6 excitation. The successive refinement Day-1 → Day-1-2 (passive) → Day-4-5 (active) is the architectural sequence; each stage tightens the prior for the next.

### From §5 — Day-1-2 passive batch fit (INV-FIT12-1 through INV-FIT12-8)

**INV-FIT12-1 — `FanHeatPass` prerequisite.** §5 MUST NOT consume Day-1-2 telemetry without a valid `FanHeatPass` record on the home's signed log (per §4 INV-FH-1). If no such record exists, §5 raises an error and refuses to run.

**INV-FIT12-2 — Operational-mode adherence.** The Day-1-2 window MUST satisfy: compressor off, heat strip off, OA dampers closed, fan operating on the programmed mixing schedule. Any sample showing nonzero compressor, heat-strip, or auxiliary-heat activity; any sample with `δ_OAD ≠ 0`; or any fan-on/fan-off transition departing from the programmed schedule by more than ±10 seconds disqualifies the window. The fit either re-collects a clean 48-hour window or raises an error if no clean window is available within the commissioning timeline.

**INV-FIT12-3 — Prior provenance is signed metadata.** The end-of-Day-2 posterior record MUST include the prior provenance descriptor and prior hash. Posteriors signed without provenance metadata are invalid; implementations MUST refuse to emit them.

**INV-FIT12-4 — Convergence diagnostics gate the signing.** No `Day2Posterior` record is emitted (and therefore no Digital Birth Certificate envelope-half-initial signing occurs) if convergence diagnostics fail per §5.7. Implementations MUST halt the pipeline rather than sign a non-converged posterior.

**INV-FIT12-5 — Identifiability flags are preserved, not suppressed.** Per-parameter identifiability flags from §8 are part of the signed record. A loose-posterior parameter (effectively prior-only) MUST be signed with its identifiability flag set; downstream consumers (especially §6) MUST consume the flag and treat the parameter accordingly.

**INV-FIT12-6 — Fan-mixing schedule adherence as window validity.** The programmed mixing schedule is part of the window definition, not protocol decoration. Schedule timestamps MUST be signed into the Day-1-2 window metadata, and an external verifier MUST be able to confirm from the telemetry that fan-on/fan-off transitions occurred at the scheduled times within tolerance.

**INV-FIT12-7 — Warmup-window observations preserved as separate data products.** The 60-second fan-on warmup window per interval contains attic-temperature observations that are excluded from the main-channel likelihood but are themselves load-bearing data for the `ceiling_coupling_factor` identification. Implementations MUST preserve `T_attic^obs(k)` for all 48 intervals as a first-class output channel, not discard the warmup readings as transient noise.

**INV-FIT12-8 — Two-channel likelihood structure.** The §5 likelihood MUST be evaluated on both the attic-observation channel (warmup-window terminal probes) and the main-observation channel (post-warmup return-plenum probe), per §5.3. A §5 implementation that consumes only the main channel and discards the attic channel is non-compliant; the two-state envelope model in Phase 1 v4.0 / `aivu_dynamic` v0.2 requires both for identifiability.

### From §6 — Day-4-5 active-perturbation batch fit (INV-FIT45-1 through INV-FIT45-7)

**INV-FIT45-1 — `Day2Posterior` prerequisite.** §6 MUST NOT run without a valid `Day2Posterior` record from §5 as the prior.

**INV-FIT45-2 — Day-3 map prerequisite.** §6 MUST NOT run without a valid Day-3-signed (Capacity, EER) operating-point map. The HVAC excitation `u_meas` for Phase A is computed from that map; without it, `u_meas` is not defined.

**INV-FIT45-3 — HPM-authored command authority via thermostat API pass-through.** §6's protocol requires that the HPM can issue specific compressor and fan capacity commands (such as "compressor stage 2 ON, fan high") that the thermostat transmits to the equipment as a command pass-through, without the thermostat exercising its own setpoint-tracking control loop during the 48-hour Days 4-5 window. For the Phoenix pilot this is provided by the EcoBee thermostat's programmable API. If a deployment uses a thermostat that does not expose a programmable command-pass-through API (e.g., a building where the thermostat is the only HVAC controller available with no programmable interface, or a commercial building with a proprietary BAS controller), §6 v0.1 cannot run; a v0.2 fallback protocol using setpoint-trajectory-driven excitation would need to be specified.

**INV-FIT45-4 — Excitation protocol adherence.** The HPM commands actually issued during Days 4-5 MUST match the programmed phase schedule within tolerance (default ±15 min on phase transitions; compressor and fan commands themselves are deterministic from the protocol). Deviations are recorded into the signed record; large deviations (e.g., hardware fault) are noted as caveats on the posterior's interpretation.

**INV-FIT45-5 — Prior provenance chain preserved.** The §6 posterior record MUST reference the §5 posterior's prior-provenance descriptor (per §5.4) and the §5 posterior's own hash. An external verifier examining a `Day5Posterior` MUST be able to trace the full prior-provenance chain.

**INV-FIT45-6 — Convergence diagnostics gate the signing.** Same as INV-FIT12-4 for §5. No `Day5Posterior` record is emitted (and therefore no Digital Birth Certificate envelope-half-final signing occurs) if convergence or quality diagnostics fail per §6.6.

**INV-FIT45-7 — `η_distribution` held at Day-1 value.** §6 v0.1 MUST NOT attempt to jointly identify `η_distribution` along with the six canonical envelope parameters. The value used is the §4-identified Day-1 value, propagated through the fit as a known input. Joint identification is a v0.2 question; attempting it in v0.1 risks an `R_eff × η_distribution` degeneracy that the Phase A excitation alone cannot resolve.

### From §7 — Recursive-mode Phase 2 solver and First Law residual (pending)

§7 has not yet been drafted. When §7 lands, its invariants enter §9.2 here under a new identifier prefix (anticipated: `INV-REC7-N` for recursive-mode invariants, parallel to `INV-FIT12-N` and `INV-FIT45-N` for the two batch fits). §9 is updated by re-running the enumeration; this placeholder marks the slot so §9 does not silently omit §7's content when §7 closes.

### From §8 — Identifiability collapse detection and posterior tightness (INV-ID8-1 through INV-ID8-8)

**INV-ID8-1 — All four diagnostics MUST run on every greybox posterior.** §5 batch-mode, §6 batch-mode, and §7 recursive-mode are all in scope. A greybox implementation that emits a posterior without an accompanying identifiability report is non-compliant.

**INV-ID8-2 — Per-parameter flags fire at ρ > 0.95.** The threshold is pinned at 0.95 for v0.1. Implementations MUST NOT silently apply a different threshold; changes to the threshold MUST be documented in the §8 revision header and applied uniformly to all six parameters.

**INV-ID8-3 — Joint-identifiability flag fires when condition number κ > 10⁶ OR when any eigenvalue λ_i < 10⁻⁴ × λ_max.** Both conditions are emitted to the report regardless; the flag is the OR of the two.

**INV-ID8-4 — §8 does NOT gate signing.** A flagged posterior MUST be signed; suppression of flagged posteriors is non-compliant.

**INV-ID8-5 — §8 does NOT modify the posterior.** §8 reads, summarizes, and flags; it does not rescale, re-center, or re-fit. The posterior emitted by §5 or §6 is the posterior that gets signed.

**INV-ID8-6 — Flags propagate forward.** §6 MUST consume the §5 report's per-parameter flags and route protocol decisions accordingly per §6.4. §7 MUST consume the §6 report's per-parameter flags as input to recursive-mode operation. Downstream consumers (Clearinghouse, Digital Birth Certificate) MUST receive the flags as part of the signed record.

**INV-ID8-7 — The expected-tightness table is the §5.5 / §6.4 table.** §8 does not maintain its own expected-tightness expectations. Updates to the expected-tightness values happen in §5.5 or §6.4 and propagate to §8 by reference; §8 implementations MUST read the current §5.5 / §6.4 values rather than caching a snapshot.

**INV-ID8-8 — Laplace assumption surfaced explicitly.** Under the v0.1 Laplace approximation, Diagnostic 4's D_KL is computed in closed form. Under the v0.2 NUTS/HMC fallback per §5.6, D_KL is computed numerically from the marginal samples. The interface contract (D_KL emitted per parameter) is invariant across the algorithm-class substitution; implementations MUST NOT assume the closed-form path.

### From §12 — Signing chain (INV-SIGN12-1 through INV-SIGN12-7)

**INV-SIGN12-1 — Every record `aivu_greybox` emits MUST be signed before it leaves the package boundary.** No record is emitted unsigned. The records covered are: telemetry packets (continuous), Fan-Heat Pass/Fail records (§4), Day-2 posterior records (§5), Day-5 posterior records (§6), and the §8 identifiability reports co-signed with their parent posterior. Implementations that emit any of these records without invoking `sign_record` are non-compliant.

**INV-SIGN12-2 — Every signed record MUST be appended to the local signed log before being consumed by a downstream call site.** `sign_record` and `commit_to_log` are paired; signing without appending leaves the record unverifiable to any later consumer. The sequence is `sign_record` → `commit_to_log`, not reversed and not separated.

**INV-SIGN12-3 — Birth Certificate half-signing moments MUST invoke `threshold_attest` with the correct `AttestationMoment` identifier.** Three moments exist: Day-3 HVAC half, Day-2 envelope-initial, Day-5 envelope-final. Each is identified by its enum value; the value is part of the threshold-attestation payload. Wrong-moment attestation (signing the Day-2 posterior with the `envelope_half_final` moment label) is non-compliant.

**INV-SIGN12-4 — The stub-attestation flag MUST be honest.** v0.1 pilot ships with `threshold_attest` returning stub-attestation. The returned `ThresholdAttestation` payload MUST carry the "stub-attestation, post-pilot replacement required" flag visible to any consumer parsing the record. A v0.1 implementation that emits a stub-attestation without the flag is non-compliant. The flag does NOT block use of the artifact during the pilot; it ensures that any consumer downstream can distinguish stub from live attestation.

**INV-SIGN12-5 — The signing interface is invariant across the v0.1 → post-pilot transition.** `aivu_greybox` code that calls `sign_record`, `commit_to_log`, or `threshold_attest` MUST NOT need modification when `aivu_integrity`'s post-pilot implementation lands. The function signatures pin this. Implementation swaps happen inside `aivu_integrity`; greybox code is unaware.

**INV-SIGN12-6 — Inclusion proofs MUST be retrievable post-hoc.** Any signed record committed to the local log MUST remain retrievable (by content-addressed hash) for the deployed lifetime of the HPM. Storage-management policy (rotation, archival, post-pilot anchoring) lives in `aivu_integrity`; the retrieval contract from `aivu_greybox`'s perspective is "indefinitely available."

**INV-SIGN12-7 — Monotonic timestamps MUST be strictly increasing within a single HPM's log.** Two records with the same monotonic timestamp (or with non-increasing timestamps) constitute a log corruption. The HPM's monotonic clock guarantees strict ordering; the invariant makes this part of the API contract so `aivu_integrity` can rely on it for replay-protection without separate clock-validation logic in `aivu_greybox`.

---

## 9.3 Cross-cutting access patterns

The same 34 invariants, re-indexed by what they constrain rather than by where they originate. An invariant appears under every theme it constrains; the total citation count exceeds 34 because most invariants touch more than one theme. This view is for human navigation, not enumeration — §10 test plan iterates §9.2, not §9.3.

### Signing-chain integrity

Invariants that constrain what gets signed, by whom, and with what completeness.

- INV-FH-3 (records complete and externally verifiable)
- INV-FIT12-3 (prior provenance is signed metadata)
- INV-FIT12-4 (convergence diagnostics gate the signing)
- INV-FIT12-5 (identifiability flags preserved, not suppressed)
- INV-FIT12-6 (fan-mixing schedule signed into window metadata)
- INV-FIT45-5 (prior-provenance chain preserved across §5 → §6)
- INV-FIT45-6 (convergence diagnostics gate the signing)
- INV-ID8-4 (§8 does NOT gate signing — flagged posteriors are still signed)
- INV-SIGN12-1 (every record signed before leaving package boundary)
- INV-SIGN12-2 (sign-then-log: signing paired with append-to-log)
- INV-SIGN12-3 (Birth Certificate half-signing moments use correct AttestationMoment)
- INV-SIGN12-4 (stub-attestation flag honesty)
- INV-SIGN12-6 (inclusion proofs retrievable post-hoc)
- INV-SIGN12-7 (monotonic timestamps strictly increasing)

### Protocol-adherence and window-validity

Invariants that determine whether a telemetry window is admissible for fitting.

- INV-FH-1 (no batch fit on Fan-Heat-Fail)
- INV-FH-2 (Fan-Heat window must satisfy operational constraints)
- INV-FIT12-1 (§5 prerequisite: valid FanHeatPass)
- INV-FIT12-2 (§5 operational-mode adherence)
- INV-FIT12-6 (fan-mixing schedule is part of window definition)
- INV-FIT45-1 (§6 prerequisite: valid Day2Posterior)
- INV-FIT45-2 (§6 prerequisite: valid Day-3 operating-point map)
- INV-FIT45-4 (§6 excitation protocol adherence within tolerance)

### Prior provenance and successive refinement

Invariants that constrain how priors flow from one fit to the next.

- INV-FH-4 (`η_distribution` from Fan-Heat is the Day-1 prior, not the final value)
- INV-FIT12-3 (prior provenance is signed metadata at end of §5)
- INV-FIT45-1 (§6 inherits §5 posterior as prior)
- INV-FIT45-5 (prior-provenance chain preserved across §5 → §6)
- INV-FIT45-7 (`η_distribution` held at Day-1 value in §6; joint refinement is v0.2)

### Identifiability semantics

Invariants that govern how identifiability is detected, flagged, and propagated.

- INV-FIT12-5 (identifiability flags preserved and propagated)
- INV-ID8-1 (all four §8 diagnostics MUST run on every posterior)
- INV-ID8-2 (per-parameter prior-only flag at ρ > 0.95)
- INV-ID8-3 (joint-identifiability flag on Hessian condition number or ridge)
- INV-ID8-4 (flagged posteriors are still signed)
- INV-ID8-5 (§8 does not modify the posterior)
- INV-ID8-6 (flags propagate §5 → §6 → §7 → Clearinghouse)
- INV-ID8-7 (expected-tightness table read from §5.5 / §6.4 by reference)
- INV-ID8-8 (Laplace vs. NUTS/HMC: interface invariant, implementation differs)

### Command authority and observation completeness

Invariants that constrain what the HPM can do to equipment and what it must observe.

- INV-FIT45-3 (HPM-authored command authority via thermostat API pass-through)
- INV-FIT12-7 (warmup-window attic observations preserved as first-class data)
- INV-FIT12-8 (two-channel likelihood: attic + main channels both required)

### Interface invariance across version transitions

Invariants that pin function signatures and contracts so v0.1 implementations can be swapped without caller-side code changes.

- INV-ID8-8 (Laplace vs. NUTS/HMC: interface invariant, implementation differs)
- INV-SIGN12-5 (signing interface invariant across v0.1 → post-pilot transition)

---

## 9.4 Update discipline

§9 has three rules:

1. **§9 follows its origin sections; it does not lead them.** When an invariant in §4-§8 is edited, the §9 entry is updated to match in the same revision. A discrepancy between §9 and an origin section is always resolved in favor of the origin section.

2. **No new invariants in §9.** §9 introduces no invariants of its own. If a new invariant is needed, it lives in the section it constrains. §9 is enumeration; §10 is test plan; the rest of greybox is normative content.

3. **Identifier retirement.** When an invariant is retired (made obsolete by a later version), its identifier retires with it. INV-FIT45-3 v0.2 might rephrase the EcoBee dependency for setpoint-trajectory-driven excitation; if so, it remains INV-FIT45-3 with a v0.2 reading. Recycling identifiers across structurally different invariants would break cross-document references and is non-compliant.

---

## 9.5 Out of scope

The following are explicitly out of §9 v0.1:

- **Invariants over the greybox package boundary** — i.e., invariants on `aivu_physics`, `aivu_dynamic`, `aivu_integrity`, or HPM hardware. Those live in their own specs.
- **Test cases that verify each invariant.** Those live in §10.
- **Cross-package invariants** (e.g., "the greybox posterior's `R_eff` must be consistent with the `aivu_physics` Phase 1 v4.0 forward-chain `R_eff`"). Such invariants belong to the package whose top-level integrity property they support, not to greybox in isolation.

---

*End of §9 v1.1 draft. 34 invariants enumerated from §§4, 5, 6, 8, 12. §7 placeholder pending. Cross-cutting view groups by theme: signing-chain integrity (14 citations), protocol-adherence (8), prior provenance (5), identifiability semantics (9), command authority and observation completeness (3), interface invariance across version transitions (2).*
