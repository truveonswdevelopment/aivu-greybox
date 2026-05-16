# AIVU Critical-Path Dependency Map

**Version:** 0.4 — drafted 2026-05-16 (afternoon), reconciling state after the 2026-05-16 48h closed-loop diagnostic dive on the §5 fit. v0.4 surfaces two architectural insights that emerged from reading the diagnostic output, both with consequences that reshape the project's measurement architecture and ripple through §5, §6, §11.x, §12, and the MRAC framing. v0.3 of this morning is correct on the procedural-fix story; v0.4 supersedes it on the measurement-architecture story.

**Purpose:** Honest dependency graph of every artifact needed to deliver the AIVU measurement architecture at production-defensible quality at one Phoenix pilot home. Single source of truth for "what's done, what isn't, what depends on what."

**Discipline this enforces:** No artifact gets called "done" until its honest state, its dependencies, and its retirement-of-stubs are named here. This document must be updated whenever a commit changes the state of any artifact named below. Update happens in the same session as the commit, not later.

---

## What changed from v0.3 (drafted 2026-05-16 morning)

The 2026-05-16 afternoon 48h diagnostic dive on the §5 passive fit produced an unexpected finding. Working through that finding with JDS generated two architectural insights that change the project structurally.

### The diagnostic finding (the data)

A diagnostic script (`tests/g8a_diagnostic.py`, not committed) re-ran the 48h fit and dumped the full Laplace structure that the test methods had ignored:

- Hessian condition number: **2.9 × 10^14**. Eight orders of magnitude beyond "severely degenerate" by any standard threshold.
- Four ridge vectors flagged by the §8 identifiability machinery, each one a **single-parameter eigenvector** with loading 1.0 on one parameter and zero on the others: C_house (eigenvalue 1.6 × 10^-8), C_wind (eigenvalue 6.2), C_stack (eigenvalue 25), C_w (eigenvalue 86).
- The four restarts converged tightly on R_opaque (0.00 σ_prior disagreement) but disagreed on C_stack (0.93 σ_prior), C_wind (0.65 σ_prior), and ceiling_coupling_factor (0.57 σ_prior). Production-default `mode_agreement_fraction = 0.05` would have rejected this fit.
- Per-parameter posterior-from-θ_true distances in posterior-σ units: C_w at 272 σ_posterior away from truth; C_house at 49 σ; R_opaque at 8.2 σ; U_fenestration at 6.5 σ; ceiling_coupling_factor at 5.9 σ. The reported posterior σ values for these parameters are Laplace-approximation artifacts of inverting an ill-conditioned Hessian, not genuine information.

The §11.2 amendment's seven-parameter set was correct in *what* AIVU wants to characterize. It did not specify the procedural separation by which §5 actually identifies them. v0.4 surfaces that the joint-fit framing under uniform residual weighting cannot identify the seven parameters from 48h of passive telemetry, no matter how long the window is extended.

The 4-of-7 result at 12h that v0.3 celebrated as "first measurement signal achieved" was Laplace-approximation artifact on parameters the §5 protocol does not constrain. v0.4 retires that framing honestly.

### Architectural insight 1 — Sequential identification by frequency band, within Cx

The seven parameters have characteristic frequency-content signatures. R_opaque, U_fenestration are roughly frequency-flat conductances identifiable at low frequencies (DC + diurnal). ceiling_coupling_factor is observable at the diurnal harmonic where sol-air drives the attic. C_house's thermal-mass time constant produces phase lag at the diurnal frequency. C_stack and C_wind respond to wind variability (synoptic, hours-to-day) and stack-effect ΔT. C_w lives at higher frequencies than C_house. The current joint fit weights all 1-Hz samples uniformly, allowing quasi-steady-state data to drown out the transients that actually constrain weakly-identified parameters.

The structural fix is sequential identification stage by stage, each stage targeting parameters whose signatures live in distinct frequency bands or physically homogeneous regimes:

- **§5 Stage 1 (diurnal-thermal band, night-weighted residuals):** R_opaque, U_fenestration, ceiling_coupling_factor. Conductive parameters identified when solar is off so attic-main coupling is purely conductive.
- **§5 Stage 2 (synoptic-wind band):** C_stack, C_wind. Identified against wind-variability residuals after Stage 1 parameters are pinned. The "wind doesn't follow a diurnal cycle" insight applies here — wind effects can be separated structurally rather than confounded with thermal effects.
- **§6 Stage 3 (active thermal night transients):** C_house. Driven by HVAC compressor-on cooling at night to produce large ΔT excursions; Phase B decay is a near-pure thermal-time-constant identification with solar absent and Stage 1 conductances pinned.
- **§6 Stage 4 (active moisture night transients):** C_w. Compressor-on dehumidification at night drives moisture out at known rate; W_main response reveals C_w with all thermal parameters pinned.

Posterior propagates between stages as informative prior (per the §11.2 posterior-as-prior chain discipline). Each parameter is identified in its cleanest regime.

§6's targeted role gets sharper: §6 is not "more excitation generically" but **targeted excitation against specific parameters (C_house, C_w) that §5 cannot reach, in physically homogeneous regimes (night, with §5 parameters pinned).**

### Architectural insight 2 — Temporal identification across Cx and continuous operation

A 7-day commissioning window has fixed information content per parameter, regardless of cleverness in the fit. Some parameters (R_opaque, U_fenestration) reach production tightness inside the window. Others (C_house, C_w even with §6 active perturbation) may reach preliminary tightness only; their production-grade values come from operational telemetry that accumulates over months and years. The HPM, running continuously after Cx, has the unique capability to **opportunistically capture regime-clean windows of the same regime classifications the Cx fit used**, accumulating posterior refinement on parameters that 7 days alone cannot pin.

Concretely: a parameter whose §5 Stage 2 fit produces a 25% posterior tightness at end-of-Cx because Phoenix-July weather only had three clean wind events of the right magnitude during the 7 days will, after 6 months of operational telemetry tagged for the same regime, have hundreds of clean events to average. The posterior tightens by √N — at 100 events, the noise-limited uncertainty drops by an order of magnitude. The same physics-based regime decomposition machinery runs on both timescales; the difference is the accumulation horizon.

Consequences ripple through the architecture:

- **Per-parameter epistemic horizons.** Each parameter in the seven-parameter set has a *primary identification horizon* (Cx for R_opaque, U_fenestration; Cx + 6mo operational for C_house, C_w; Cx + 12mo for some secondaries). The §11.x amendment that follows §11.2 specifies these per-parameter horizons. The §5.5 expected-tightness table becomes multi-column, indexed by parameter and horizon.

- **Signed-record schema evolves.** §12's signed-record format gains per-parameter epistemic status with vintage and confidence horizon. A Digital Birth Certificate carries not just (mean, covariance) per parameter but also (horizon, vintage, confidence-state). A consumer of the record understands which parameters are pinned-at-Cx vs. refining-over-time. This is the §12.x amendment.

- **HPM gains opportunistic-measurement role.** Today's MRAC framing has the HPM running the continuous-adaptation real-time control loop. v0.4 adds: the HPM also tags regime-clean observation windows, accumulates per-regime statistics, and feeds them to the BDT periodically for posterior refinement. Same MRAC principle, second time horizon. The MRAC doc gets an addendum capturing this dimension.

- **Clearinghouse data products differentiate by record vintage.** A 5-year-old AIVU-instrumented home has tighter posteriors than a 7-day-old one. Insurance underwriting that consumes the records understands the difference. (Out of scope for greybox; flagged for the OS doc and System Architecture.)

- **Asymmetry with HERS deepens further.** HERS is structurally a snapshot. AIVU is structurally cumulative. Not a feature comparison; a category difference.

### Work this surfaces as new top-of-stack

A new architectural document, **AIVU Temporal Identification Architecture**, lands BEFORE §5.3 and §6.3 spec amendments because it determines what those amendments are amending. Its scope:

1. The regime classification (diurnal-thermal night, synoptic-wind, active-thermal-transient, active-moisture-transient).
2. The per-parameter temporal profile (primary horizon, secondary refinement horizon).
3. The data-flow architecture (HPM tags windows by regime, accumulates per-regime statistics, feeds BDT for posterior updates).
4. The signed-record schema implications (per-parameter epistemic status with vintage).
5. The §11.x and §12.x amendments this enables.

Multi-session work, starts with v0.1 skeleton tomorrow.

---

## Prior context — what changed in v0.3 (2026-05-16 morning)

v0.3 retired the staleness in v0.2 that had become invisible during the 2026-05-15 working day (G7, G8, §11.2 amendment all landed without v0.2 being updated). The session-start verification protocol that would have caught the staleness landed as part of the procedural-fix commit.

The headline from v0.3 stands as historical fact but its framing retires under v0.4's insight 2 below:

The headline: G7 shipped, G8 shipped with a named gap, the §11.2 amendment is now Authoritative with seven canonical parameters, and Phase 1 of the day-numbering reconciliation workstream landed today's commit.

**§11.2 amendment locked Authoritative (commits 87b8775 → 64102b6 → dd31fa3 → 3708dc2, all 2026-05-15).** The six-parameter canonical set is retired. The seven-parameter set is `{R_opaque, U_fenestration, C_house, C_stack, C_wind, C_w, ceiling_coupling_factor}`. `R_eff` split into `R_opaque` + `U_fenestration`; `cfm50` replaced by `(C_stack, C_wind)`; `F_slab` moved out of the fit into `HomeStaticContext`. `Prior6D` renamed to `Prior7D` throughout. Greybox test count: 69 → 77 after Pass B fixture updates.

**G7 shipped (commit 814127e, 2026-05-15).** Real-chain adapter `real_chain.py` wraps `aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2 behind greybox's `ForwardChain` Protocol. 8 smoke tests pass. The "highest leverage unfinished work" framing retires.

**G8 shipped with a named gap (commit aff8f83, 2026-05-15).** §5 closed-loop test against the real chain via G7 recovered 4 of 7 parameters under a 12-hour passive observation window. The recovered parameters: C_house, C_stack, C_wind, C_w. The unrecovered: R_opaque and ceiling_coupling_factor traded off along an under-determined ridge; one additional parameter showed overconfident σ. This is the **first measurement signal in the project** — a partial one, with the failure modes matching what the §11.2 amendment predicted under 12h passive observation. Greybox total: 77 → 79 tests.

**Phase 1 day-numbering reconciliation landed (commit 3351b95, 2026-05-16).** Specs §§5-12 reconciled to the 7-Day protocol: Days 5-6 active perturbation, Day-4 HVAC map prerequisite, `Day6Posterior` references in spec text. INV-FIT12-* and INV-FIT45-* names retained as opaque historical identifiers with an etymology footnote in §9. The §11.2 amendment file was untouched (orthogonal to day-numbering). §10 Configuration 1 broadened to cover both V752-class and Nolan 8560-class floor plans against the possibility of two pilot homes.

**Two new workstreams surface from the G8 result and the §11.2 amendment's interim path.** Ridge resolution (attack R_opaque × ceiling_coupling_factor at 48h passive, then §6 active, then reparametrize if needed) and Phase 1 operational-infiltration amendment (retire the interim cfm50 translation in G7 by exposing an operational-infiltration entry point in `aivu_physics/infiltration.py`).

**Status corrections.** Greybox §§1-12 v0.1 all closed (not just §§4-8). All eight Phase 2 spec increments locked, not three. `aivu_integrity` is `SPECCED_PARTIAL` at the architecture layer (System Arch §6 + greybox §12 interface), not `NOT_SPECCED`. Greybox test count is 79, not the 43 the skeleton inferred. Greybox §6's Phase 2 dependency is Layer 2 + Layer 3, not Layer 1.

**Architectural finding — dual greybox tracks.** The skeleton's goal statement defaulted the deliverable to the envelope half of the Digital Birth Certificate alone. The HVAC half — explicitly named in System Arch §3.3 and greybox §6 v3 as required, and arguably the more structurally novel half because HVAC has *no* commissioning today — was not surfaced as a discrete artifact and had no code package owning it. Inverse identification of HVAC parameters from operating-point sweep telemetry is structurally parallel to envelope inverse identification: same Bayesian machinery, same Laplace fit pattern, same signing call surface, same identifiability/quality-gate discipline, different parameters. A sister package `aivu_hvac_greybox` now owns this work. The package family becomes: forward physics (`aivu_physics`, `aivu_dynamic`) and inverse identification (`aivu_greybox`, `aivu_hvac_greybox`).

**Protocol-structure correction — 7-Day not 5-Day.** The current commissioning protocol described across all documents (System Arch, Architectural Distillation, OS doc, greybox §§1-12, Phoenix Pilot Roadmap) was a 5-Day window. JDS clarified in the 2026-05-14 session that the actual protocol is 7 days: Day 0 for install and setup, Days 1-2 for envelope passive observation, Days 3-4 for HVAC two-pass commissioning (sweep + repeat for validation), Days 5-6 for envelope active perturbation. The vocabulary shift is being executed as the Day-Numbering Reconciliation Workstream — Phase 1 (greybox §§5-12 specs) landed today; Phases 2-4 (records dataclass rename, active_fit field rename, continuity touch-ups) and the broader doc-level updates (Architectural Distillation, System Arch v3.0.1, OS doc) remain.

**Two more artifacts surfaced in v0.2 are now resolved.** `aivu_hpm` — the real-time controller and orchestrator that runs both greybox packages on the actual HPM — remains scoped but not specified. The real-chain adapter shipped on 2026-05-15 as commit 814127e.

**Structural finding on the critical path.** The path forks. Envelope's §5 (passive) leg of greybox runs against the real chain today via G7+G8. Envelope's §6 (active) leg waits on Phase 2 v1 code AND on `aivu_hvac_greybox`'s Day-4 signed HVAC record. Earliest "stuff works" signal is **achieved** (partial, with the ridge gap named); next milestone is ridge resolution and/or the Phase 1 amendment.

**Hardware section retired.** Hardware status tracked in `AIVU_Phoenix_Pilot_Roadmap.md` workstreams C/D/E, not duplicated here.

---

## Goal

**Deliver 7-Day dual-track commissioning at one Phoenix pilot home**, producing two independently signed records that together constitute the Digital Birth Certificate:

1. **Envelope half.** End-of-Day-6 `Day6Posterior` record with `AttestationMoment.ENVELOPE_HALF_FINAL`, signed by the real `aivu_integrity` chain. (The Day-2 `ENVELOPE_HALF_INITIAL` record exists as an intermediate; Day-6 supersedes it as the home's commissioned envelope baseline.)

2. **HVAC half.** End-of-Day-4 record with `AttestationMoment.HVAC_HALF`, signed by the real `aivu_integrity` chain.

Both records authenticate dual-track physics characterization, with §8 identifiability flags surfaced and held-out residuals surviving scrutiny by an outside reviewer. A Clearinghouse customer (BASF, Marmon, or comparable) can buy either or both.

---

## The 7-Day protocol

| Day | Activity | Track | Signed output |
|---|---|---|---|
| 0 | Hardware install, sensor placement, Mixing Length Verification, connectivity handshake, sanity checks | — | (none) |
| 1-2 | Envelope passive observation under fan-mixed conditions (10 min/hr mixing schedule) | envelope | `Day2Posterior` / `ENVELOPE_HALF_INITIAL` |
| 3-4 | HVAC operating-point sweep, repeated on Day 4 for validation against Day 3 | HVAC | Day-4 record / `HVAC_HALF` |
| 5-6 | Envelope active perturbation using the calibrated HVAC as known excitation source | envelope | `Day6Posterior` / `ENVELOPE_HALF_FINAL` |

**Track separation is operational.** Envelope is characterized without assuming HVAC performance. HVAC is characterized without assuming envelope performance. Day 5-6 envelope's active fit consumes the Day-4-signed HVAC record as a hard prerequisite — by Day 5, HVAC is no longer an uncalibrated unknown; it is a signed, measured instrument. Envelope's active perturbation rides on top of that calibration. Each track stays honest about what it depends on.

---

## Conventions

**State** of an artifact:
- `SHIPPED` — code written, tested, committed; tests pass at production thresholds
- `SHIPPED_WITH_GAPS` — usable for some purposes; named gaps disqualify it for others
- `SPECCED` — spec is locked and complete; code does not yet exist
- `SPECCED_PARTIAL` — spec exists but has known holes
- `NOT_SPECCED` — no formal spec; design intent only

**Bridging** of a dependency:
- `REAL` — depended-on artifact is `SHIPPED` and wired in
- `STUB` — Protocol-conforming stand-in is in place; named retirement gate exists
- `SYNTHETIC` — test fixture or analytic stand-in for development convenience

**Carrying party** = who has the ball. JDS owns the outcome of every artifact; the carrying party is who is currently moving it forward.

---

## Code artifacts — forward physics (`aivu-physics` repo)

### F1. `aivu_physics` Phase 1 (envelope physics)
- State: `SHIPPED` (v4.0, locked 2026-04-18)
- Location: `~/aivu/code/phase1/aivu_physics/`
- Tests: 372 V-series invariants
- Floor plans supported: Nolan 8560, V752. Phoenix candidate pool is one or two homes similar to these per JDS 2026-05-14; floor-plan support is adequate.

### F2. `aivu_dynamic` (dynamic envelope simulator)
- State: `SHIPPED_WITH_GAPS` (v0.2, locked 2026-04-26)
- Location: `~/aivu/code/aivu_dynamic/`
- Tests: 87 D-series invariants
- Known gaps documented in `PROJECT_STATE.md`: B4 (RealCycle latent-side, Houston-required), B5 (ERV heat-recovery, V752 calibration). Both confirmed off-path for first pilot per Phoenix-only decision.

### F3. `aivu_corpus` (cohort orchestrator)
- State: `SHIPPED` (v0.2.0)
- Location: `~/aivu/code/aivu_corpus/`
- Tests: 45 invariants
- Pilot manifest committed at `aivu_corpus/pilot/pilot_manifest.parquet`.

### F4. Phase 2 Layer 1 (capacity demand) v1 code
- State: `SPECCED` (Increment 2 v0.2 locked 2026-04-23)
- Code: NOT STARTED
- Extraction document: `~/aivu/extraction/AIVU_Phase2_Layer1_Extraction_v0_1.md` drafted
- Carrying party: Claude
- Effort estimate: ~2 sessions

### F5. Phase 2 Layer 2 (equipment output) v1 code
- State: `SPECCED` (Increment 3 v0.1 locked 2026-04-23)
- Code: NOT STARTED
- Extraction document: not yet drafted
- Carrying party: Claude
- Effort estimate: ~3 sessions
- Critical-path role: produces the equipment-output physics consumed by both `aivu_hvac_greybox` (as the forward model for HVAC parameter ID) and `aivu_greybox` §6 (as the calibrated excitation source for envelope active perturbation).

### F6. Phase 2 Layer 3 (duct delivery) v1 code
- State: `SPECCED` (Increment 4 v0.1 locked 2026-04-23)
- Code: NOT STARTED
- Extraction document: not yet drafted
- Carrying party: Claude
- Effort estimate: ~2 sessions

### F7. Phase 2 v1 cross-layer invariants and integration
- State: covered by Increment 6 (Validation Invariants) locked spec
- Code: NOT STARTED
- Carrying party: Claude
- Effort estimate: ~1 session
- **Total Phase 2 v1 envelope (F4 + F5 + F6 + F7): ~8 sessions end-to-end**, contingent on no spec defects surfacing during implementation. Anchored against `aivu_dynamic` (four sessions for 87 invariants) and `aivu_corpus` (one session, narrower scope).

### F8. Phase 2 Per-Room (Increment 5)
- State: `SPECCED` (v0.2 locked 2026-04-23) — deferred from v1 code per Session 13 decision
- Critical-path role: OFF-PATH. Reserved for v2.

### F9. Phase 1 operational-infiltration amendment — NEW ARTIFACT 2026-05-15
- State: `NOT_STARTED` (flagged in §11.2 amendment as the retirement gate for G7's interim cfm50 translation)
- Carrying party: Claude
- Purpose: expose an operational-infiltration entry point in `~/aivu/code/phase1/aivu_physics/infiltration.py` (v4.0 → v4.1) that takes `(C_stack, C_wind, T_in, T_out, V_wind)` and returns infiltration heat flow + air mass flow directly, bypassing the cfm50 → Sherman-Grimsrud round-trip. Existing cfm50-based path remains for backward compatibility.
- Effect when shipped: G7's adapter retires its derived-cfm50 translation path; `(C_stack, C_wind)` flow directly into `infiltration.py`'s new entry point; greybox §5/§6 fits' posterior on `(C_stack, C_wind)` becomes directly meaningful at every operating point in the §6 active-perturbation window, not just the §5 mean. No greybox spec change required; only the adapter changes.
- Critical-path role: not blocking G8 (which already ran against the interim path). Becomes load-bearing when the ridge-resolution workstream (G8a) tries 48h or §6 active perturbation — at high-ΔT or high-wind moments, the interim path's bias would confuse the ridge diagnosis.
- Effort estimate: ~1 session for Phase 1 amendment; <0.5 session for the corresponding G7 adapter retirement of the derived-cfm50 path.

---

## Code artifacts — envelope inverse identification (`aivu-greybox` repo)

### G1. `aivu_greybox` §4 (Fan-Heat Consistency Check)
- State: `SHIPPED` (2026-05-13)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/fan_heat.py`
- Tests: 17 passing
- Dependencies: signing stub (Bridging: `STUB`; retires at G9)

### G2. `aivu_greybox` §5 (Days 1-2 passive Laplace fit)
- State: `SPEC_AMENDMENT_REQUIRED` (per v0.4 architectural insights, 2026-05-16 afternoon)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/passive_fit.py`
- Tests: 13 + 2 (G8) passing against `StubForwardChain` and `RealForwardChain`; the 2 G8 tests are now understood as baseline-against-which-new-version-is-validated, NOT as evidence of measurement signal
- Canonical parameter set: `{R_opaque, U_fenestration, C_house, C_stack, C_wind, C_w, ceiling_coupling_factor}` per §11.2 amendment Authoritative 2026-05-15 (unchanged)
- **What's wrong:** the current single-pass joint fit cannot identify the seven parameters from §5 passive telemetry, regardless of window length. The 2026-05-16 48h diagnostic showed condition number 2.9 × 10^14 and four single-parameter ridge vectors. The fix is structural — sequential identification by frequency band per the v0.4 sequential-identification insight, not a tuning adjustment.
- Dependencies:
  - **AIVU Temporal Identification Architecture document** (new top-of-stack, see Track 4 below). Specifies the regime classification and stage structure that §5.3 amendment will implement.
  - §5.3 spec amendment (frequency-domain likelihood, stage-by-stage identification per §5 Stage 1 and §5 Stage 2 of the v0.4 four-stage map).
  - Code rewrite of `passive_fit.py` to implement the staged structure with posterior-as-prior propagation between stages.
- Retirement gate: §5.3 amendment locks; staged-fit code passes closed-loop test against `aivu_corpus` synthetic trajectories at production-default `mode_agreement_fraction = 0.05` AND §8 `joint_identifiability_flag = False`.

### G3. `aivu_greybox` §6 (Days 5-6 active perturbation Laplace fit)
- State: `SPEC_AMENDMENT_REQUIRED` (per v0.4 architectural insights)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/active_fit.py`
- Tests: 13 passing (count from v0.2; now understood as baseline-against-which-staged-implementation-is-validated)
- Canonical parameter set: seven parameters per §11.2 amendment
- **Targeted role per v0.4:** §6 is no longer "more excitation generically." §6 targets C_house (Stage 3) and C_w (Stage 4) — parameters §5 structurally cannot identify — using HVAC-driven excursions in physically homogeneous regimes (night-only, with §5 parameters pinned via informative priors from §5 posterior). Day-vs-night separation suppresses solar confounding. Phase B's compressor-off decay at night is near-pure thermal-time-constant identification for C_house. Phase D's compressor-on dehumidification at night identifies C_w.
- Dependencies:
  - **AIVU Temporal Identification Architecture document** (specifies Stage 3 and Stage 4 design)
  - §6.3 spec amendment (the staged structure, day/night gating, posterior-from-§5 as prior)
  - Phase 2 Layers 2 and 3 (F5, F6) — forward chain has to support active-phase HVAC operation for the §6 fit to run against real chain
  - `aivu_hvac_greybox`'s Day-4 signed HVAC record
  - Code rewrite of `active_fit.py` for staged structure
- Retirement gate: §6.3 amendment locks; staged-fit code passes closed-loop test against `aivu_corpus` synthetic trajectories for C_house and C_w (the targets of §6) at production thresholds AND §8 joint check passes
- Pending code-side day-numbering work: `Day5Posterior` → `Day6Posterior` dataclass rename in `records.py`; `day3_map_record_hash` → `day4_map_record_hash` field rename in `active_fit.py`. Tracked as Phases 2-3 of the Day-Numbering Reconciliation Workstream. Day-numbering and §6.3 amendment can land in either order; tightly coupled enough that doing them in one combined commit may be cleaner.

### G3a. Day-Numbering Reconciliation Workstream
- State: **Phase 1 SHIPPED (2026-05-16, commit 3351b95); Phases 2-4 NOT_STARTED.**
- Phase 1 (spec rewrite, §§5-12): DONE. Spec text "Days 4-5" → "Days 5-6"; INV-FIT45-2 "Day-3 map" → "Day-4 map"; `Day5Posterior` references → `Day6Posterior` in spec text; INV-FIT12-* and INV-FIT45-* names retained as opaque historical identifiers with §9 etymology footnote; §10 Configuration 1 broadened to cover both V752 and Nolan 8560 floor-plan classes.
- Phase 2 (records dataclass rename in `records.py`): NOT_STARTED. Mechanical rename of `Day5Posterior` → `Day6Posterior` and cascading through `active_fit.py` imports + test fixtures.
- Phase 3 (`active_fit.py` field rename): NOT_STARTED. `day3_map_record_hash` → `day4_map_record_hash`; protocol-string identifier `§6_day5_active_compounded` → `§6_day6_active_compounded`.
- Phase 4 (continuity touch-ups): NOT_STARTED. Phoenix Pilot Roadmap, session logs (one-line notes), this dependency map's TODOs.
- Carrying party: Claude
- Effort estimate (remaining): Phases 2-3 together ~1 session; Phase 4 ~0.5 session.
- See `~/aivu-greybox/continuity/DAY_NUMBERING_RECONCILIATION_WORKSTREAM.md` for the four-phase scope document.

### G4. Other shipped greybox modules
- `psychrometrics.py` — 23 tests passing (ASHRAE reference values)
- `defaults.py` — §11.2 canonical numerical defaults; seven-parameter set per amendment Authoritative 2026-05-15 (commit 3708dc2)
- `records.py` — dataclasses for signed records (requires G3a Phase 2: `Day5Posterior` → `Day6Posterior` rename)
- `epw_loader.py` — Phoenix AMY 2024 EPW, 1-Hz interpolated slices
- `forward_chain.py` — `ForwardChain` Protocol contract + `StubForwardChain` analytic stand-in (stub now seven-parameter per Pass A)
- `passive_fit_types.py` — `Prior7D` (renamed from `Prior6D` per §11.2 amendment), telemetry window dataclass, ACCA prior
- `real_chain.py` — G7 adapter wrapping `aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2 (shipped 2026-05-15, commit 814127e; 8 smoke tests pass)

**Greybox total: 79 tests passing against real Phoenix EPW 2024** (69 pre-§11.2; 77 post-Pass-B; 79 post-G8).

### G5. `aivu_greybox` §7 (recursive solver)
- State: `SPECCED` (v1.1, locked 2026-05-13)
- Code: deferred to post-pilot per Roadmap A4
- Critical-path role: OFF-PATH for first pilot

### G6. `aivu_greybox` §8 (identifiability collapse detection)
- State: `SHIPPED_WITH_GAPS` — logic embedded in `build_identifiability_report` within `passive_fit.py`; standalone module extraction pending
- Critical-path role: required for pilot. Pending refactor is mechanical and does not change correctness.

### G7. Real-chain adapter — SHIPPED 2026-05-15
- State: `SHIPPED` (commit 814127e, 2026-05-15)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/real_chain.py`
- Tests: 8 smoke tests pass
- Purpose: thin wrapper that satisfies greybox's `ForwardChain` Protocol by wrapping `aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2. Sufficient for §5 today; Phase 2 wired in once F4-F7 ship (required for §6 production-threshold test).
- Known limitation: interim cfm50 translation in the `(C_stack, C_wind)` parameter path. The adapter converts the operational-infiltration coefficients into a derived-equivalent cfm50 at the §5 fit's mean operating conditions and feeds Phase 1 through its existing cfm50 path. Bias at high-ΔT or high-wind moments is named in the §11.2 amendment with a retirement gate. Retires when the Phase 1 operational-infiltration amendment ships (F9 below).
- Critical-path role: **achieved.** This was the highest-leverage unfinished work as of v0.2; landing it on 2026-05-15 unblocked G8 and made the §5 leg measurable for the first time.

### G8. §5 closed-loop test against the real chain — 12h v0.1 + 48h diagnostic, both retired in v0.4
- State: `RETIRED` as a measurement signal; **baseline-against-which-staged-implementation-is-validated** going forward
- 12h test (commit aff8f83, 2026-05-15): the 4-of-7 reading is Laplace-approximation artifact, not measurement signal. C_stack, C_wind, C_w, and C_house "covered" only because their reported posterior σ blew up wide enough to span θ_true by uncertainty. The fit was not constraining those parameters; it was reporting illusory width from inv(ill-conditioned Hessian).
- 48h experiment (2026-05-16): condition number 2.9 × 10^14; joint identifiability flag fired; four single-parameter ridge vectors at near-zero eigenvalues; restart-to-restart disagreement of 0.93 σ_prior on C_stack against the production-default threshold of 0.05. Under production discipline this fit would have raised `LaplaceFitFailed`.
- Test code remains in `tests/test_g8_closed_loop.py` and the diagnostic script in `tests/g8a_diagnostic.py` (uncommitted, lives only in JDS's local clone). When the §5.3 amendment lands and the staged-fit code is written, the closed-loop machinery will be re-targeted to validate per-stage recovery rather than seven-parameter joint recovery.
- v0.3's "first measurement signal achieved" framing retires honestly. v0.4's framing: greybox machinery runs end-to-end against real Phase 1 physics (architectural seam validated), but the inverse-identification structure under joint fit cannot extract production-defensible posteriors. The staged structure is the fix.

### G8a. Ridge resolution workstream — RETIRED in v0.4
- v0.3 surfaced this as the next experiment under the assumption the ridge was R_opaque × ceiling_coupling_factor coupled-parameter degeneracy. The 48h diagnostic showed the ridges are four single-parameter near-zero eigenvalues, NOT a coupled-parameter ridge. v0.4 retires the ridge-resolution workstream; the structural fix is sequential identification (the new Temporal Identification Architecture workstream), not resolving a coupled ridge.

---

## Code artifacts — HVAC inverse identification (new package `aivu_hvac_greybox`)

### H1. `aivu_hvac_greybox` package spec — NEW ARTIFACT
- State: `NOT_SPECCED`
- Carrying party: Claude (spec drafting); JDS interrogation as drafts surface
- Purpose: Bayesian inverse identification of HVAC equipment parameters from Days 3-4 operating-point-sweep telemetry, with Day 4 results validating Day 3. Produces the signed Day-4 record with `AttestationMoment.HVAC_HALF` — the HVAC half of the Digital Birth Certificate.
- Architectural mirror of `aivu_greybox`: same Laplace machinery, same quality-gate pattern, same signing call surface, different parameters.
- HVAC parameter set: bi-quadratic coefficients D17/D19/D20 plus cabinet UA D18 per Phase 2 Increment 8. Exact canonical-set definition pending read of Increment 8.
- Spec sections will likely mirror greybox: scope/non-goals, package family position, deployment target, the canonical parameter set, the inverse problem, two-pass protocol (Day 3 establishes, Day 4 validates), invariants, test plan, signing interface.
- Effort estimate: ~4 sessions, given the inverse-identification patterns established by greybox §§1-12 transfer largely intact.

### H2. `aivu_hvac_greybox` v1 code — NEW ARTIFACT
- State: `NOT_STARTED` (gated on H1)
- Carrying party: Claude
- Dependencies:
  - Phase 2 Layers 2 and 3 (F5, F6) as the forward chain
  - The real-chain adapter (G7), extended to expose Phase 2 forward physics via the same Protocol pattern greybox uses
  - `aivu_integrity` for signing (G9)
- Produces: Day-4 signed record schema and emission with `AttestationMoment.HVAC_HALF`. Schema needs to be settled in H1's spec phase so envelope §6's INV-FIT45 invariants (post-G3a amendment) can reference the right fields.
- Effort estimate: ~4 sessions for greybox-§§4-6-equivalent code, given inverse-ID patterns from greybox transfer to HVAC parameters with structural rather than algorithmic changes.

### H3. `aivu_hvac_greybox` closed-loop test against real Phase 2 — NEW ARTIFACT
- State: `NOT_STARTED`
- Carrying party: Claude
- Effort estimate: <1 session once H2 ships and F5/F6 are available
- Purpose: closed-loop recovery of known HVAC parameters from synthetic Days 3-4 sweeps generated by Phase 2 Layers 2/3. Same discipline as greybox B2 closed-loop tests against `aivu_corpus`.

---

## Code artifacts — signing chain and orchestrator

### G9. `aivu_integrity` — pilot-floor cryptographic package
- State: `SPECCED_PARTIAL` — System Arch §6 covers architecture (MMR, two-tier signing, 2-of-3 threshold attestation, OSS verification library); greybox §12 covers the call-site interface. Internal package spec not started.
- Code: NOT STARTED
- Carrying party: Claude for spec drafting and pilot-floor code. Cryptographic correctness review by an outside cryptographer needed before pilot data ships.
- Pilot-floor scope per greybox §12: per-packet HPM signing + local append-only signed log only. MMR commitment primitive and 2-of-3 threshold attestation spec'd in v0.1 but implementation in post-pilot work.
- Critical-path role: pilot data must be signed by real cryptographic chain before it can be sold via Clearinghouse. The `_signing_stub` retires when this ships. INV-SIGN12-5 names the swap-target.
- Both greybox packages (envelope and HVAC) depend on this for their signed records.

### G10. `aivu_hpm` — real-time controller and orchestrator on the HPM
- State: `NOT_SPECCED`
- Code: NOT STARTED
- Carrying party: Claude for spec drafting and non-hardware code. Hardware-integration code path TBD pending 2026-05-15 HPM-in-circuit-box outcome (Roadmap workstreams C/D).
- Required next move: scoping conversation with JDS before any §1 spec text is drafted. Architecture-level questions to settle: shape of the bounded MRAC inner loop; phase state machine location across the 7-Day protocol; sub-100ms determinism as v0.1 target vs v0.2 target; standalone-mode behavior priorities.
- Critical-path role: **without this, there is no pilot.** Greybox and `aivu_hvac_greybox` are library code — they compute posteriors when something hands them telemetry windows. `aivu_hpm` is what does the handing: telemetry ingestion (Eaton power, Venturi airflow, return T/RH), phase state machine across the 7-day protocol, invocation of both greybox packages at the right times, BDT uplink, certainty-equivalent controller-parameter ingestion, standalone-mode operation, failure-mode response.
- `aivu_hpm` also physically orchestrates the HVAC operating-point sweeps on Days 3-4 (via the EcoBee thermostat's programmable API as a command pass-through, per the architectural correction in greybox §6 v3).
- Effort estimate: not yet possible — pending scoping conversation.

---

## Off-path items (named explicitly so they stop being implicit)

Real work, but NOT on the path to first pilot. Surfaced to prevent quiet capacity absorption.

| Item | Why off-path |
|---|---|
| `aivu_dynamic` B4 (RealCycle latent-side, Houston) | Phoenix-only first pilot |
| `aivu_dynamic` B5 (ERV heat-recovery in `infiltration.py`) | V752 calibrated empirically during pilot |
| `aivu_greybox` §7 recursive solver code | Deferred per Roadmap A4 |
| `aivu_greybox` §8 standalone module extraction | Refactor of existing correct logic |
| Phase 2 Per-Room analysis (Increment 5 / Part 2a) | v2 scope |
| `aivu_pinn` (Born Educated PINN training pipeline) | Cohort-scale, post-pilot |
| `aivu_integrity` post-pilot surfaces (MMR, 2-of-3 threshold, OSS verification library) | Explicitly post-pilot per greybox §12 |
| Vocabulary update across all AIVU docs (5-Day → 7-Day) | Documentation workstream, not code |

---

## The critical path — five parallel tracks, one convergence

**Track 1 — envelope §5 path, architectural reformulation required (v0.4):**

```
F1, F2, F3 [SHIPPED]
    │
    ▼
G7  Real-chain adapter         [SHIPPED 2026-05-15, commit 814127e]
    │
    ▼
G8  §5 real-chain test         [SHIPPED 2026-05-15, commit aff8f83]
    │                              Joint-fit cannot identify 7 params from §5 passive
    │                              under uniform-residual weighting at any window length.
    │                              4-of-7 at 12h was Laplace-approx artifact.
    ▼
[NEW TOP-OF-STACK]
T1  Temporal Identification Architecture document
T2  §5.3 spec amendment (sequential identification by frequency band)
T7  passive_fit.py rewrite for staged structure
T8  F10 per-home pre-commissioning validation gate
    │
    ▼
Ready for §5 production-threshold retirement under staged structure
```

**Track 1b — Phase 1 operational-infiltration amendment, demoted in v0.4:**

```
F9  Phase 1 v4.0 → v4.1 (operational-infiltration entry point)
    │                              Demoted: not the dominant problem in v0.4.
    │                              Cleanliness item, sits below T1-T8.
    ▼
G7 adapter cleanup: derived-cfm50 path removed
```

**Track 2 — HVAC commissioning path (new, courtesy of this session):**

```
F4-F7  Phase 2 v1 code  (~8 sessions; Layers 2/3 are the inputs aivu_hvac_greybox needs)
    │
    │  (H1 spec drafting can run in parallel with the F4-F7 work)
    ▼
H1  aivu_hvac_greybox spec  (~4 sessions)
    │
    ▼
H2  aivu_hvac_greybox code  (~4 sessions; needs F5, F6, G7)
    │
    ▼
H3  HVAC closed-loop test against real Phase 2  (<1 session)
    │
    ▼
Ready to produce Day-4 signed HVAC record
```

**Track 3 — envelope §6 path, reframed in v0.4 as targeted excitation:**

```
T1 + T3 (§6.3 amendment) + F5, F6 + H2 (Day-4 record) + T7 (active_fit.py rewrite)
    │
    ▼
G3  §6 real-chain test for Stages 3 and 4 (C_house, C_w) at production thresholds
    │   §5 parameters pinned as informative priors; night-only HVAC excursions
    ▼
Ready to produce Day-6 signed envelope record (with epistemic status per parameter)
```

**Track 4 — signing path, runs in parallel:**

```
System Arch §6 + greybox §12 [SPECCED_PARTIAL]
    │
    ▼
G9  aivu_integrity pilot-floor
    + outside cryptographic review
```

**Track 5 — orchestrator path, runs in parallel (with hardware sub-path conditional):**

```
JDS scoping conversation
    │
    ▼
G10  aivu_hpm spec drafting
    │
    ├──→ non-hardware code (state machine across 7-day protocol,
    │    BDT uplink, both-greybox orchestration, standalone-mode)
    │
    └──→ hardware-integration code  ← TBD pending 2026-05-15 outcome
```

**Convergence:**

```
G3 (envelope §6 ready) + Day-4 HVAC record ready + G9 + G10 + Hardware/sensors/pilot home
    │
    ▼
Run 7-Day commissioning
    │
    ▼
Signed Day-4 record (HVAC_HALF) + signed Day-6 record (ENVELOPE_HALF_FINAL)
    │
    ▼
Digital Birth Certificate complete, both halves saleable through Clearinghouse
```

---

## New top-of-stack workstreams (v0.4 — Sequential and Temporal Identification)

The architectural workstreams that the 2026-05-16 afternoon diagnostic surfaced. These sit ahead of all five tracks in priority because the existing tracks depend on them: until the identification structure is settled, no §5/§6 specs or code below them can be written productively.

### T1. AIVU Temporal Identification Architecture document — TOP PRIORITY
- State: `NOT_STARTED` (skeleton drafting begins 2026-05-17)
- Location: `~/aivu-greybox/AIVU_Temporal_Identification_Architecture_v0_1.md` (repo root, peer with `AIVU_MRAC_Architecture_v0_1.md`)
- Scope: regime classification (diurnal-thermal night, synoptic-wind, active-thermal-transient, active-moisture-transient); per-parameter primary identification horizon and secondary refinement horizon; data-flow architecture (HPM tags windows by regime, accumulates per-regime statistics, periodically feeds BDT for posterior refinement); signed-record schema implications; the §11.x and §12.x amendments this enables.
- Why this is top-of-stack: §5.3 amendment, §6.3 amendment, §11.x amendment, §12.x amendment, F10 validation gate, and HPM scoping all depend on this document existing. It articulates what they are amending.
- Effort estimate: multi-session at architectural level (no code). Skeleton in 1 session; first review-ready draft within 3-4 sessions.

### T2. §5.3 spec amendment (sequential identification by frequency band)
- State: `NOT_STARTED`; depends on T1
- Scope: §5's likelihood structure shifts from uniform-residual-sum across 1-Hz samples to sequential stage-by-stage identification. Stage 1: R_opaque, U_fenestration, ceiling_coupling_factor against diurnal-thermal-band night-weighted residuals. Stage 2: C_stack, C_wind against synoptic-wind-band residuals with Stage 1 parameters pinned via posterior-as-prior. §5.5 expected-tightness table becomes per-stage rather than per-parameter.
- Effort estimate: 1-2 sessions.

### T3. §6.3 spec amendment (targeted-excitation staged identification)
- State: `NOT_STARTED`; depends on T1 and T2
- Scope: §6 targets C_house (Stage 3) and C_w (Stage 4) under night-only HVAC excursions with §5 parameters pinned. The four-phase protocol (A, B, C, D) maps to the staged structure with day/night gating. §6.4 expected-tightness reformulates per-stage.
- Effort estimate: 1-2 sessions.

### T4. §11.x amendment — per-parameter horizon assignment
- State: `NOT_STARTED`; depends on T1
- Scope: extends the §11.2 seven-parameter canonical set with per-parameter (primary identification horizon, secondary refinement horizon) metadata. The §5.5/§6.4 expected-tightness tables become multi-column indexed by horizon. Provisional priors update with horizon-aware framing.
- Effort estimate: <1 session once T1 lands.

### T5. §12.x amendment — signed-record schema with per-parameter epistemic status
- State: `NOT_STARTED`; depends on T1
- Scope: §12's signed-record format gains per-parameter epistemic status (mean, covariance, horizon, vintage, confidence-state). A consumer of the Digital Birth Certificate understands which parameters are pinned-at-Cx vs. refining-over-time. Schema evolution path specified so v0.1 records remain readable post-amendment.
- Effort estimate: 1 session.

### T6. MRAC doc addendum — temporal-identification dimension
- State: `NOT_STARTED`; depends on T1
- Scope: the MRAC doc gains a section explicitly capturing that the HPM's continuous-adaptation principle operates at two timescales — the real-time control loop (already in MRAC doc) AND the cumulative measurement loop (per Insight 2). One mechanism, two roles depending on parameter's epistemic status: drift-tracking for well-identified parameters; initial identification for weakly-identified parameters with multi-month/multi-year horizons.
- Effort estimate: <1 session once T1 lands.

### T7. Code rewrites in `passive_fit.py` and `active_fit.py`
- State: `NOT_STARTED`; depends on T2 and T3
- Scope: implement staged identification with posterior-as-prior propagation between stages. Existing single-pass code becomes baseline-against-which-staged-implementation-is-validated.
- Effort estimate: 2-3 sessions across both modules.

### T8. F10 pre-commissioning validation gate
- State: `NOT_STARTED`; depends on T7
- Scope: the per-home gate that 2026-05-16 afternoon's discussion surfaced. Before any real home gets a signed §5/§6 posterior, the pipeline runs the staged closed-loop test against `aivu_corpus` synthetic trajectories for that home's envelope class with production-strict thresholds (`mode_agreement_fraction = 0.05`, §8 `joint_identifiability_flag = False`). Halts and surfaces "this home's parameter regime is not in the validated envelope; engineering review required" on failure.
- Effort estimate: <1 session once T7 lands; mostly wrapping existing test machinery in a decision gate.

---

**Completed since v0.2:**
- ~~G7 — real-chain adapter ships.~~ DONE 2026-05-15 (commit 814127e).
- ~~G8 — §5 closed-loop test against real chain passes.~~ DONE 2026-05-15 with named gap (commit aff8f83): 4 of 7 parameters recovered at 12h passive; ridge resolution tracked as G8a.
- ~~§11.2 amendment locks Authoritative.~~ DONE 2026-05-15 (commits 87b8775 → 64102b6 → dd31fa3 → 3708dc2): seven-parameter canonical set landed in code with 77 tests passing.
- ~~G3a Phase 1 (greybox §§5-12 spec reconciliation).~~ DONE 2026-05-16 (commit 3351b95).

**Remaining, in execution order:**

1. **G8a (a) — 48h passive observation against the real chain.** Cheapest experiment to attack the ridge. Reuses the G8 machinery, longer window. Effort: <1 session.
2. **F9 — Phase 1 operational-infiltration amendment.** Retires G7's interim cfm50 translation. Can run in parallel with G8a (a). Effort: ~1 session.
3. **G3a Phases 2-3 — `Day5Posterior` → `Day6Posterior` records rename + `active_fit.py` field rename.** Mechanical code follow-up to today's spec reconciliation. Effort: ~1 session combined.
4. **F4-F7 — Phase 2 v1 code ships.** Layers 1, 2, 3 plus cross-layer invariants. Largest unfinished body of work. Effort: ~8 sessions.
5. **H1 — `aivu_hvac_greybox` spec drafted.** Can run in parallel with F4-F7. Effort: ~4 sessions.
6. **H2 — `aivu_hvac_greybox` code ships.** Needs F5, F6, G7 (G7 done). Effort: ~4 sessions.
7. **H3 — HVAC closed-loop test against real Phase 2 passes.** Effort: <1 session.
8. **G8a (b) — §6 active perturbation as ridge-resolution path.** Only after F5/F6 and §6 machinery against real chain. May be subsumed by G3 directly.
9. **G3 — envelope §6 closed-loop test against real chain at production thresholds, 7-of-7 coverage.** Effort: <1 session, given G7, F5, F6, H2, G3a Phase 2-3 all in place.
10. **G3a Phase 4 — continuity touch-ups.** Phoenix Pilot Roadmap, session logs, Critical Path Map TODOs. Effort: ~0.5 session.
11. **G9 — `aivu_integrity` pilot-floor ships.** Replaces `_signing_stub` at all call sites in both greybox packages. Outside cryptographic review completed.
12. **G10 — `aivu_hpm` ships, at the level required to run a pilot.** Scoping conversation first.
13. **Hardware, sensors, and pilot home reach pilot-ready state.** Tracked in `AIVU_Phoenix_Pilot_Roadmap.md` workstreams C/D/E.
14. **Run 7-Day commissioning.**

Gates 1-3 can proceed in parallel — none blocks the others. Gates 5-7 (HVAC track) can proceed in parallel with the F4-F7 envelope-side track. Gates 9 (G3) and 11-12 (G9, G10) wait on their respective upstream dependencies but each runs independently once unblocked.

---

## Critical-path summary in one sentence

**Architectural reformulation first (T1 Temporal Identification Architecture → T2/T3 §5.3/§6.3 amendments → T4/T5 §11.x/§12.x amendments → T6 MRAC addendum → T7 staged-fit code → T8 F10 validation gate); in parallel: Phase 2 v1 code + `aivu_hvac_greybox` spec/code; then convergence at envelope §6 staged-fit production-threshold test; then `aivu_integrity` pilot-floor + `aivu_hpm` + hardware + pilot home → run 7-Day Cx with per-parameter epistemic status records → continuous operational telemetry refines weakly-identified parameters over months/years → Clearinghouse data products differentiate by vintage.**

What v0.3 framed as "first measurement signal achieved" was Laplace-approximation artifact on parameters the §5 protocol does not constrain. The honest framing in v0.4: greybox machinery runs end-to-end against real Phase 1 physics, but the inverse-identification structure under joint fit cannot extract production-defensible posteriors. The staged structure (within Cx) and continuous-operational refinement (across years) are the structural fix. This adds time to the path-to-pilot but produces measurement that is defensible against a Tier-1 due-diligence reviewer.

---

## Open questions for next session

1. **AIVU Temporal Identification Architecture skeleton (T1, top priority).** First task of next session. Skeleton draft articulating: the regime classification, the per-parameter horizon profile, the data-flow architecture. Doesn't need to be complete; needs to be specific enough that T2-T6 amendments can begin to be drafted against it.

2. **§5.3 amendment first cut (T2).** Once T1 skeleton lands, the §5.3 amendment can be drafted in parallel. First cut: which parameters in which stage, which residual weighting per stage, how posteriors propagate stage-to-stage.

3. **Mathematical framework choice for the staged likelihood.** Options surfaced 2026-05-16 afternoon: (a) regime-stratified time-domain residual sum with regime-specific weights; (b) frequency-domain (FFT/Welch) likelihood with band-specific weights; (c) hybrid. Decision belongs in T1/T2; first cut likely (a) for implementability with (b) as v0.2 evolution.

4. **HPM-in-circuit-box hardware status — STATUS STILL UNKNOWN as of v0.4.** Carried forward from v0.3. JDS to confirm.

5. **§11.x amendment scope (T4).** Once T1 articulates the per-parameter horizon assignment, the §11.x amendment formalizes it in the canonical-parameter-set document. <1 session once T1 lands.

6. **§12.x amendment scope (T5).** Signed-record schema evolution for per-parameter epistemic status with vintage. Schema-evolution path so v0.1 records remain readable.

7. **Architectural Distillation update.** Still pending from v0.3. Now even more important because the Distillation is what new Claude sessions read at cold-start, and the v0.4 architectural insights will shape every future session's framing. ~0.5 session.

8. **Whether to commit `test_recovery_at_48h_passive` and `g8a_diagnostic.py` to the repo.** Currently uncommitted in JDS's local clone. Argument for committing: future replication of today's diagnostic. Argument against: the staged-fit code will supersede this test machinery within a few sessions, and committing it now creates dead-weight test code. Recommendation: commit only `g8a_diagnostic.py` as a one-time-experiment record, with a docstring noting it superseded by staged-fit machinery once T7 lands.

9. **Day-Numbering Reconciliation Phases 2-4.** Mechanical work; can land alongside T7's code rewrite or as a standalone commit before. Either order works.

---

*End of v0.4. Drafted 2026-05-16 afternoon after the diagnostic dive on the 48h closed-loop test. Captures two architectural insights (sequential identification by frequency band within Cx; temporal identification across Cx and continuous operation) that reshape the project's measurement architecture. Replaces v0.3 of 2026-05-16 morning on the measurement-architecture story; v0.3's procedural-fix story (cold-start canonical, session-start verification protocol, end-of-session checklist) is unchanged in v0.4.*
