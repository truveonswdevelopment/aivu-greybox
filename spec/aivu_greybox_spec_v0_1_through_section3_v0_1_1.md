# AIVU Inverse-Identification Physics Specification

**Package:** `aivu_greybox`
**Version:** 0.1.1 (small revision to §§1.2 and 2.5 — 2026-05-12)
**Original draft:** April 27, 2026
**Maintainer:** Jan-Dieter Spalink
**AI Partner:** Claude (Opus 4.7, Anthropic)

**Revision 2026-05-12 (v0.1 → v0.1.1) — §§1.2 and 2.5 only.** Canonical parameter set extended from five to six by adding `ceiling_coupling_factor` (the dimensionless thermal-coupling parameter between the conditioned attic and the main conditioned space, conducted through the ceiling sheetrock and insulation assembly). Parameter previously discussed in §§4-6 drafts under the misleading name `foam_coupling_factor` (the spray foam at the roof deck is the envelope boundary, not the coupling element); renamed 2026-05-12. `κ_buffer` in v0.1 §§1.2 and 2.5 is the same physical quantity as `C_w` in `aivu_dynamic` v0.2 (the lumped moisture-side thermal capacity, paired with `C_house` on the sensible side); the naming question is settled in favor of `C_w` to match `aivu_dynamic` v0.2 convention. The six-parameter set committed by this revision is `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}`. This revision exercises the §1.2 caveat *"Additional parameters may be committed at code-implementation time if the data-flow analysis surfaces them"* — the data-flow analysis through the §§4-6 drafts surfaced the sixth parameter. No other content of §§1-3 changed.

**Relationship to prior specs.** Builds on `aivu_physics` Phase 1 v4.0 (locked April 18, 2026) for envelope physics, `aivu_physics` Phase 2 v0.1 (locked April 23, 2026) for HVAC physics, and `aivu_dynamic` v0.2 (locked April 26, 2026) for time-domain envelope dynamics. All invariants from those specs remain in force; this package does not re-derive or re-validate any of them. Phase 2 Increment 1 §2.3 explicitly defers grey-box identification to a future separate package; this is that package, formally renamed `aivu_greybox` per Delta 1 of the AOT v2.5 → v2.6 Editorial Addendum (April 27, 2026).

**Authoritative architecture.** AIVU System Architecture of Truth v2.5 (April 9, 2026), with two extensions issued April 27, 2026: the Editorial Addendum (six deltas) and Extension I, Delta 7 — The Integrity Model. Where the addenda conflict with v2.5 prose, the addenda govern. The aivu_greybox specification honors all seven deltas and the additional clarifications captured in the session-13B handoff (R as design-intent specification distinct from plant identity; modification-request architecture as the only HPM→BDT learning-loop flow; raw telemetry HPM-resident under normal operations with on-demand serving via MMR inclusion proofs; layered adjudication with HPM-local first-pass and Clearinghouse on-demand higher-fidelity).

---

## 1. Purpose, Scope, Non-Goals

### 1.1 Purpose

`aivu_greybox` performs Bayesian inverse identification of physically meaningful envelope parameters from operational 1 Hz telemetry. The forward physics chain that produces predicted indoor trajectories from {weather, equipment, parameters} is locked across `aivu_physics` Phase 1, `aivu_physics` Phase 2, and `aivu_dynamic`. This package inverts that chain: given measured trajectories and the corresponding HVAC excitation, it produces a posterior distribution over the parameters that, fed back into the forward chain, would have generated the measurements.

The posterior is the package's output. What downstream consumers do with it — sign it as the envelope half of the Digital Birth Certificate, uplink it to the BDT inside an HPM-authored modification request, anchor a drift event to Bitcoin via OpenTimestamps — is the concern of `aivu_hpm`, the BDT, and `aivu_integrity` respectively. `aivu_greybox` produces the inferential object; the system architecture handles its institutional consumption.

Two solver modes share a common physics core. The batch mode runs at end-of-Day-2 and end-of-Day-5 of the 5-Day Pre-Occupancy commissioning window described in AOT v2.5 §3.2 and §3.4, with wall-clock budget measured in hours, producing the high-fidelity posterior that anchors the Digital Birth Certificate's envelope half. The recursive mode runs at heartbeat cadence throughout Phase 2 post-occupancy operation, with per-cycle budget measured in tens to hundreds of milliseconds, tracking the slowly-varying parameter posterior against the end-of-Day-5 baseline as the home ages, the equipment drifts, and structural events accumulate.

### 1.2 Scope

- **Bayesian inverse identification of envelope parameters** from 1 Hz telemetry against the locked forward chain. The canonical parameter set (§4) consists of `R_eff`, `C_house`, `cfm50`, `F_slab`, `C_w`, and `ceiling_coupling_factor` (six parameters; see header revision note for the v0.1 → v0.1.1 extension from five), with priors drawn from the cohort PINN's projection at the home's gbXML coordinates. The §1.2 caveat *"Additional parameters may be committed at code-implementation time if the data-flow analysis surfaces them"* is the door through which the sixth parameter (`ceiling_coupling_factor`) was committed.
- **Two solver modes**, sharing physics structure: batch Bayesian for commissioning posteriors and recursive Kalman-family for Phase 2 continuous identification.
- **Self-tests and quality gates** that establish whether the posterior produced is trustworthy: the Fan-Heat Consistency Check (Delta 4 of the Editorial Addendum, elevated to first-class self-test), First Law residual verification, identifiability collapse detection, and posterior tightness criteria gating the Day 3 anchor.
- **Output contracts** with the three downstream consumers: the Digital Birth Certificate signing process (envelope half), `aivu_hpm`'s modification-request authoring (recursive posterior plus drift signals as one input), and the Clearinghouse audit pipeline (pass/fail flags and residual logs via `aivu_integrity` commitment).
- **Test plan** anchored on closed-loop validation against `aivu_corpus` synthetic trajectories: known parameters in via the forward chain, posterior out via this package, recovery checked against the known parameters within confidence intervals.

### 1.3 Non-Goals

The following are explicitly out of scope for `aivu_greybox`. Each is named in its appropriate home so the boundary is operational rather than merely proscriptive.

- **Forward physics.** The forward model is locked across `aivu_physics` Phase 1 (envelope, quasi-steady), `aivu_physics` Phase 2 (HVAC capacity demand, equipment output, duct delivery), and `aivu_dynamic` (time-domain envelope state evolution). This package consumes that forward model as a black-box oracle. It does not redefine, re-derive, or re-implement any of it.
- **Modification-request authoring.** The decision to send a modification request to the BDT — to propose that R no longer adequately represents the plant — is made by `aivu_hpm` using `aivu_greybox`'s posterior (and other inputs, including MRAC adaptation-state proximity to bounds and accumulated aberration filings) as evidence. `aivu_greybox` produces the posterior and a drift signal indicating posterior shift relative to the end-of-Day-5 baseline; `aivu_hpm` decides whether that warrants an upward proposal.
- **HVAC operating-point map.** The Day 3 commissioning produces a measured (Capacity, EER) map as a function of outdoor dry-bulb, return-air conditions, airflow, and compressor stage, per AOT v2.5 §3.3. That map is `aivu_physics` Phase 2 territory (Layer 2 calibration via the D17 / D19 / D20 bi-quadratic coefficients and D18 cabinet UA per Phase 2 Increment 8 §§2–4). `aivu_greybox` consumes the calibrated map as a known input to Days 4–5 active envelope characterization but does not produce or refine it.
- **Reference Model R.** R is the IndoorClimateObjective object plus the cohort-PINN-derived inputs supporting it, authored by the BDT and downloaded to the HPM. It encodes the home's design intent — comfort bands, IAQ thresholds, economic guardrails, the desired closed-loop response. `aivu_greybox` does not author, modify, or hold R. It produces plant-identity parameters; the comparison of plant identity against R-supporting assumptions, and the resulting modification-request authoring, lives in `aivu_hpm`.
- **Cryptographic infrastructure.** MMR commitment of posteriors at production, per-packet signing, 2-of-3 threshold attestation at Birth Certificate signing moments, OpenTimestamps anchoring of drift events — all live in `aivu_integrity`. `aivu_greybox` calls into `aivu_integrity`'s API to commit posteriors and obtain inclusion proofs; it does not implement any cryptographic primitive.
- **PINN training.** The cohort PINN that supplies the prior for batch fits and that is refined by uplinked posteriors lives in the BDT. PINN architecture, loss design, training pipeline are downstream of this package's outputs and not in scope.
- **Real-time control.** The bounded classical MRAC inner loop on the HPM consumes certainty-equivalent controller parameters distilled from the BDT's PINN per AOT v2.5 §1.2. `aivu_greybox` does not consume those parameters and does not interact with the inner loop's adaptation state.

### 1.4 Deliverables

- This specification document.
- A `src/aivu_greybox/` Python package implementing the two solver modes against the locked forward chain. Composes with `aivu_physics`, `aivu_dynamic`, and `aivu_integrity` as imported dependencies; does not modify any of them.
- A test suite covering invariants G1–G5 (§9), validated against analytic solutions where possible and against `aivu_corpus` closed-loop recovery elsewhere.
- A pilot validation report demonstrating posterior recovery against the `aivu_corpus` 17-row demonstration corpus and the 20-row full-corpus recipe, with confidence intervals reported per parameter per configuration.

## 2. Position in the Package Family

### 2.1 Forward chain and inverse position

The AIVU envelope-and-HVAC physics is implemented as a forward chain across three locked specifications:

- `aivu_physics` Phase 1 v4.0 specifies envelope physics quasi-steady: the per-hour envelope-driven thermal load given weather, geometry, envelope variant, orientation, setpoint, and occupancy. The conditioned space is treated as held at setpoint.

- `aivu_physics` Phase 2 v0.1 specifies HVAC physics in three layers: capacity demand from the indoor climate objective (Layer 1), equipment-outlet capacity from the equipment specification at the AHU outlet (Layer 2), and delivered capacity to the conditioned space after duct conduction and leakage (Layer 3).

- `aivu_dynamic` v0.2 specifies time-domain envelope dynamics: lumped sensible capacitance `C_house` and moisture capacity `C_w`, the two-state vector `x = (T_in, W_in)`, and the state equations 6.1 and 6.2 that evolve indoor state under specified HVAC excitation. This is what releases the Phase 1 quasi-steady "held at setpoint" assumption when the controller cannot or does not maintain setpoint.

The three together constitute the forward physics: given parameters and a specified HVAC excitation profile, the chain produces a trajectory of `(T_in, W_in)` indoor state, the corresponding 11-term envelope load decomposition, equipment electrical draw, supply and return enthalpies, and mass flow through the coil — all sampled at 1 Hz or finer.

`aivu_greybox` inverts this chain. Given measured 1 Hz telemetry of the same observables (Eaton breaker power per circuit, supply-tail Venturi mass flow, supply T/RH, return T/RH, weather, indoor T/RH) over a window of 48 hours (commissioning batch) or one heartbeat interval (Phase 2 recursive), and given the corresponding HVAC excitation, the package produces a posterior distribution over the canonical envelope parameters that, fed back into the forward chain, would have generated the measurements.

The forward chain is a deterministic map from {parameters, excitation, weather} to {trajectory, observables}. The inverse problem is the Bayesian update of a prior over parameters using the observed trajectory as evidence. The prior comes from the cohort PINN at the home's gbXML coordinates, projected to the parameter space `aivu_greybox` operates in. The posterior is the prior updated by the data through the forward chain's likelihood.

This is forward/inverse symmetry in the strict sense. Every parameter `aivu_greybox` identifies is a parameter `aivu_dynamic` consumes. Every observable `aivu_greybox` conditions on is an output the forward chain produces. The closed-loop validation (§10) consists of running the forward chain with known parameters via `aivu_corpus`, feeding the resulting trajectories back through `aivu_greybox`, and checking that the recovered posterior covers the original parameters within confidence intervals.

### 2.2 Consumed dependencies

`aivu_greybox` consumes the following at runtime:

- **`aivu_physics`** for the envelope load decomposition and HVAC physics evaluated at given parameter values and given indoor state. Specifically the modified `loads.compute_loads(hour, cfg, occupancy_flag, T_in_F=T_in, W_in=W_in)` API per `aivu_dynamic` §10, which evaluates Phase 1's load math at dynamic indoor state rather than at a held setpoint. The Phase 2 Layer 2 / Layer 3 physics is consumed via the calibrated equipment-specification and delivery-system-specification objects established at Day 3 commissioning.

- **`aivu_dynamic`** for the time-domain forward simulator. The integrator (RK4 or Euler per `aivu_dynamic` §7), the state equations, the excitation provider abstraction. `aivu_greybox`'s likelihood evaluation calls `aivu_dynamic.dynamic.run(...)` with candidate parameter values and the actual measured HVAC excitation, computes the model trajectory, and compares against the measured trajectory.

- **`aivu_integrity`** for cryptographic commitment of posteriors. At posterior production, the package calls into `aivu_integrity` to sign the posterior under the HPM's per-packet key, append it to the local MMR alongside (and in temporal correspondence with) the telemetry segment from which it was derived, and obtain the MMR inclusion proof. The proof becomes part of the posterior's output object (§9). At Birth Certificate signing moments, `aivu_greybox` invokes `aivu_integrity`'s 2-of-3 threshold attestation protocol; the protocol and key management are `aivu_integrity`'s responsibility, not this package's.

### 2.3 Downstream consumers

Three downstream consumers receive `aivu_greybox` outputs:

- **The Digital Birth Certificate signing process** consumes the end-of-Day-2 batch posterior (envelope half, initial signing) and the end-of-Day-5 batch posterior (envelope half, final signing). Each is signed via the 2-of-3 threshold attestation among HPM, BDT, and Clearinghouse per Delta 7 §7.2, anchored per-event to Bitcoin via OpenTimestamps per Delta 7 §7.3, and stored as the immutable record of the home's commissioned envelope identity.

- **`aivu_hpm`'s modification-request authoring** consumes the Phase 2 recursive posterior continuously. When the recursive posterior's distance from the end-of-Day-5 baseline (measured per §7.4) exceeds a threshold, `aivu_greybox` raises a drift signal alongside the current posterior. `aivu_hpm` combines this signal with other inputs — MRAC adaptation state proximity to bounds, accumulated aberration filings, occupant-preference inputs — and decides whether to author a modification request to the BDT. `aivu_greybox` does not author the request; it provides the plant-identity evidence that informs `aivu_hpm`'s decision.

- **The Clearinghouse audit pipeline** consumes the self-test outputs from §8: pass/fail flags from the Fan-Heat Consistency Check, First Law residual logs, identifiability collapse flags, posterior tightness measurements. These flow upward through the layered adjudication architecture (HPM-local first-pass adjudication runs continuously; the Clearinghouse pulls underlying data on demand for higher-fidelity adjudication when a claim, regulatory inquiry, statistical quarantine event, or other institutional trigger warrants it).

### 2.4 Sibling packages

Two packages share scope adjacency with `aivu_greybox` without a runtime dependency:

- **`aivu_corpus`** v0.2 is the closed-loop validation tool. It generates synthetic trajectories from the forward chain across deliberately specified parameter and excitation sweeps. `aivu_greybox`'s test plan (§10) consists primarily of running posterior recovery against `aivu_corpus` output. The package family relationship: `aivu_corpus` runs the forward chain; `aivu_greybox` runs the inverse; `aivu_corpus`'s outputs are `aivu_greybox`'s test inputs.

- **`aivu_pinn`** is a future package in the AIVU family, training the Born Educated PINN on the forward chain's parameter coverage and on uplinked posteriors from deployed homes. `aivu_greybox`'s posteriors arrive at the BDT inside HPM-authored modification requests (per the architecture clarified in this session); the BDT then decides whether and how to incorporate them into PINN refinement. `aivu_greybox` is one input source to `aivu_pinn`'s training, not a co-developer.

### 2.5 The Big Digital Twin and the cohort PINN

The cohort PINN is the BDT-resident learned plant model `P̂` per AOT v2.5. For `aivu_greybox`'s purposes, the PINN serves a single role: it is the source of the informative prior that the batch and recursive solvers consume.

At Phase 0 (Off-Site Birth), the cohort PINN is initialized by the EnergyPlus 8,760-hour synthetic load profile against the home's gbXML model and TMY3 weather. The BDT distills certainty-equivalent controller parameters from the initialized PINN — these are signed by the Clearinghouse and pushed to the HPM as part of the Born-Educated R loaded onto firmware before the home is occupied. The PINN itself remains in the BDT.

`aivu_greybox` does not consume the PINN directly. What it consumes is a parameter-space prior derived from the PINN at the home's gbXML coordinates. The derivation maps the PINN's high-dimensional learned representation into a distribution over the canonical parameter set `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}`. The derivation mechanism is `aivu_pinn`'s responsibility (or, in v0.1 absent `aivu_pinn`, a parameter-space prior is constructed directly from the cohort statistics across pilot homes and the home's gbXML-derived design intent — or, absent a gbXML, from ACCA Manual J-derived defaults for the home's climate zone and size class, per §5.4). Whichever path supplies the prior, `aivu_greybox` consumes it as a Gaussian (or appropriately structured) distribution with means, covariance, and provenance metadata.

Two paths through which `aivu_greybox` outputs flow back to the BDT — both via `aivu_hpm`-authored modification requests, never as a direct telemetry stream:

- A modification request triggered by Phase 2 drift detection carries the current recursive posterior (as `aivu_greybox`'s evidence for the proposed R modification) along with the corresponding telemetry-segment commitment via MMR inclusion proof. The BDT decides whether the proposed modification warrants a revised R (and possibly a corresponding cohort PINN refinement).

- A modification request triggered by a commissioning event (end-of-Day-2 or end-of-Day-5 posterior signing) carries the batch posterior. Birth Certificate signing invokes 2-of-3 threshold attestation per Delta 7; the BDT participates in the attestation, holding the threshold-attested posterior in its own audit-replicated record.

In neither path does the HPM stream raw 1 Hz telemetry to the BDT. The replication channel under Delta 7 §7.4, as clarified in this session, holds raw telemetry at the HPM under normal operations; the BDT receives modification requests and MMR roots, with raw telemetry served on demand via verification requests and authenticated through MMR inclusion proofs.

## 3. Deployment Target and Compute Budget

### 3.1 Deployment target

`aivu_greybox` runs on the Home Performance Manager (HPM) edge node. Per Delta 1 of the Editorial Addendum, this residency is a structural commitment: cloud-resident grey-box identification at fleet scale beyond approximately one thousand homes becomes a 1 Hz cloud firehose with linear ingest cost. HPM-resident identification scales cleanly to arbitrary fleet size because each home performs its own fit locally and uplinks only the resulting derived objects.

The HPM hardware capability specification per Delta 2 of the Editorial Addendum is capability-based, not ISA-locked. ARM Cortex-A class hardware satisfies the spec; so do x86 industrial single-board computers and emerging RISC-V industrial parts. `aivu_greybox` makes no assumption about the underlying ISA. The capability requirements relevant to this package are inherited verbatim from Delta 2:

- Multi-core SoC capable of running Linux (preferably PREEMPT_RT) with hardware floating-point and SIMD.
- ≥ 2 GB RAM (4–8 GB preferred).
- ≥ 32 GB industrial-grade flash (64–128 GB preferred for buffering audit logs across multi-day ISP outages).
- Sub-100 ms determinism for the real-time path.
- Hardware root of trust and cryptographic accelerator sufficient for the per-packet signing and threshold attestation load.

`aivu_greybox` does not impose additional hardware requirements beyond Delta 2. The package's compute load is bounded by the budgets of §3.2 and is sized to the capability spec with margin.

### 3.2 Compute budgets

Three compute budgets bound `aivu_greybox`'s wall-clock envelope:

- **Day 1–2 batch fit**: ≤ 24 hours wall-clock, executed during the Day 1–2 passive observation phase of commissioning (AOT v2.5 §3.2). The fit consumes 48 hours of accumulated 1 Hz telemetry. The 24-hour ceiling is architectural — bounded by the next phase of commissioning (Day 3 HVAC operating-point map construction, which depends on the Day 1–2 envelope posterior as a known prior). Actual fit time on representative hardware is expected in minutes, not hours, for the canonical parameter set.

- **Day 4–5 batch fit**: ≤ 24 hours wall-clock, executed during the Day 4–5 active envelope characterization phase (AOT v2.5 §3.4). The fit consumes 48 hours of Days 4–5 active-perturbation telemetry, with the Day 1–2 posterior as the Bayesian prior. The same 24-hour ceiling applies; the same expected actual time applies.

- **Phase 2 per-cycle update**: ≤ 100 ms wall-clock, executed each heartbeat in the Phase 2 recursive solver mode. This gives 10× headroom against 1 Hz telemetry cadence and leaves room for the per-packet Ed25519 signing and MMR append that `aivu_integrity` requires per cycle. The 100 ms ceiling is verified against representative HPM hardware in §10's test plan; if hardware verification shows the ceiling tight, it relaxes to a higher value in v0.2; if comfortable, it stays.

These are ceilings, not targets. The package is designed to operate well below them; the ceilings exist to constrain implementation choices (algorithm class, integrator step size, parameter dimensionality) so that hardware capability is not silently exceeded as the spec evolves.

### 3.3 Cross-platform numerical reproducibility

`aivu_greybox` posteriors must be bit-identical across the development platform (macOS) and the deployment platform (embedded Linux on HPM hardware). Otherwise the integrity story under Delta 7 develops a hole: a posterior committed via threshold attestation on one platform must be reproducible on the other for verification to be meaningful.

The v0.1 reproducibility policy is bit-identity via pinned numerical stack. Specifically:

- NumPy at a specific minor version, with build-determinism flags enabled.
- SciPy at a specific minor version.
- BLAS implementation pinned (OpenBLAS at a specific build), single-threaded for deterministic ordering of floating-point operations.
- ODE integrator inherited from `aivu_dynamic` v0.2 §7, where deterministic step control is already locked.

Specific version pins are configuration parameters of the deployed package, not spec content; they update without spec revision through the normal package version bump. A bounded-drift policy with explicit First Law tolerance is a v0.2 question if the v0.1 pinned-stack discipline proves operationally restrictive.

The reproducibility check is a §10 test: run the canonical posterior recovery on macOS development and on representative HPM hardware (or a Linux container exercising the deployment numerical stack), confirm bit-identity of the resulting posterior object.

### 3.4 Initialization and dependencies

`aivu_greybox` initialization on the HPM presupposes that two events have already occurred:

- **Born-Educated R has been loaded onto the HPM firmware**, including the parameter-space prior derived from the cohort PINN at this home's gbXML coordinates. This happens at the end of Phase 0 per AOT v2.5 §2.1 / §2.2, before the HPM ships to site.

- **The DKG ceremony has run** as part of Phase 0 / installation per Delta 7 §7.2, establishing threshold key shares distributed among the HPM, BDT, and Clearinghouse. `aivu_integrity`'s threshold attestation API is operative when `aivu_greybox` first commits a posterior.

The hardware install at Day 0 of commissioning (sensor placement, Mixing Length Verification, connectivity handshake per AOT v2.5 §3.1) completes before the Day 1–2 batch fit begins. `aivu_greybox` does not run during Day 0; it runs in the three phases identified in §3.2.

### 3.5 Over-the-air update of identifier code

OTA updates to `aivu_greybox` over the operational lifetime of the HPM (decades) are a host-platform concern handled by `aivu_hpm`, not specified in this package. `aivu_greybox` participates in OTA as one of several packages updated through whatever signed-firmware mechanism `aivu_hpm` provides (alongside `aivu_dynamic`, `aivu_integrity`, the bounded MRAC inner loop, and other HPM-resident code). The dependency is acknowledged here so that `aivu_hpm`'s eventual specification scopes OTA appropriately; `aivu_greybox` v0.1 does not specify the mechanism.

*End of §2 and §3, v0.1 draft. Awaiting Jan-Dieter review before §4 begins.*
