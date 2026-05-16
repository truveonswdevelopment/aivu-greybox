# AIVU Critical-Path Dependency Map

**Version:** 0.3 — drafted 2026-05-16, reconciling state after the 2026-05-15 session's six commits (§11.2 amendment lock, Pass A, Pass B, amendment promoted to Authoritative, G7, G8) and the 2026-05-16 session's Phase 1 day-numbering reconciliation commit. v0.2 of 2026-05-14 was not updated at session close on 2026-05-15 — a real bookkeeping miss that produced an hour of wasted reasoning at the start of 2026-05-16 before being caught and corrected. v0.3 retires that staleness.

**Purpose:** Honest dependency graph of every artifact needed to deliver dual-track commissioning at one Phoenix pilot home. Single source of truth for "what's done, what isn't, what depends on what."

**Discipline this enforces:** No artifact gets called "done" until its honest state, its dependencies, and its retirement-of-stubs are named here. **Discipline added in v0.3:** this document must be updated whenever a commit changes the state of any artifact named below. Update happens in the same session as the commit, not later.

---

## What changed from v0.2 (the 2026-05-14 draft)

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
- State: `SHIPPED_WITH_GAPS` (2026-05-13; seven-parameter set landed 2026-05-15 Pass A/B)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/passive_fit.py`
- Tests: 13 passing against `StubForwardChain` (count from v0.2; total greybox count is now 79 post-G7/G8)
- Canonical parameter set: `{R_opaque, U_fenestration, C_house, C_stack, C_wind, C_w, ceiling_coupling_factor}` per §11.2 amendment Authoritative 2026-05-15
- Dependencies:
  - Forward chain: Bridging `STUB` via `StubForwardChain` for the test suite; `REAL` via G7 for G8 closed-loop test
  - Signing chain (Bridging: `STUB`; retires at G9)
- Retirement gate: closed-loop test passes at production thresholds for all seven parameters. G8 has produced a partial pass (4 of 7 parameters under 12h passive); remaining work tracked as the ridge-resolution workstream below.

### G3. `aivu_greybox` §6 (Days 5-6 active perturbation Laplace fit)
- State: `SHIPPED_WITH_GAPS` (2026-05-13; seven-parameter set landed 2026-05-15 Pass A/B; spec reconciled to Days 5-6 framing 2026-05-16)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/active_fit.py`
- Tests: 13 passing against `StubForwardChain` (count from v0.2)
- Canonical parameter set: seven parameters per §11.2 amendment
- Dependencies:
  - Forward chain INCLUDING Phase 2 Layers 2 and 3 (Bridging: `STUB` via `StubForwardChain`; partially retires when G7 + F5 + F6 ship — G7 done, F5/F6 pending)
  - Day-4 signed HVAC record from H2 (Bridging: currently absent; retires when `aivu_hvac_greybox` ships)
  - Signing chain (Bridging: `STUB`; retires at G9)
- Retirement gate: Phase 2 Layers 2-3 ship AND `aivu_hvac_greybox` Day-4 record available AND closed-loop test passes at production thresholds with full 7-of-7 per-parameter coverage
- Pending code-side day-numbering work: `Day5Posterior` → `Day6Posterior` dataclass rename in `records.py`; `day3_map_record_hash` → `day4_map_record_hash` field rename in `active_fit.py`. Tracked as Phases 2-3 of the Day-Numbering Reconciliation Workstream.
- This is the artifact most exposed to upstream gaps. Until F5, F6, and H2 ship, §6 has never seen production-quality forward physics or a real HVAC record underneath it.

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

### G8. §5 closed-loop test against the real chain — SHIPPED WITH NAMED GAP 2026-05-15
- State: `SHIPPED_WITH_GAPS` (commit aff8f83, 2026-05-15)
- Location: `~/aivu-greybox/code/aivu_greybox/tests/test_g8_closed_loop.py`
- Tests: 2 passing
- Result: 4 of 7 parameters recovered under 12h passive observation against `aivu_corpus` synthetic Phoenix-July trajectories. Recovered: `C_house`, `C_stack`, `C_wind`, `C_w`. Unrecovered: `R_opaque` and `ceiling_coupling_factor` traded off along an under-determined ridge; one parameter showed overconfident σ.
- Critical-path role: **first measurement signal in the project.** Greybox machinery, written entirely without reference to the real forward chain, recovers a meaningful subset of envelope parameters when driven by real physics through G7 — with the failure mode being exactly what the §11.2 amendment predicted under 12h passive observation. Validates the architectural seam between greybox and Phase 1 + dynamic.
- Gap: 3 of 7 parameters not recovered at 12h. See G8a below.

### G8a. Ridge resolution workstream — NEW ARTIFACT 2026-05-15
- State: `NOT_STARTED`
- Carrying party: Claude
- Purpose: resolve the R_opaque × ceiling_coupling_factor identifiability ridge that left G8 with 4-of-7 recovery instead of 7-of-7.
- Three angles, roughly in increasing cost:
  - **(a) 48h passive observation window.** G8 ran at 12h; the §5 spec window is 48h. Longer passive observation gives the foam-coupling-factor's diurnal signal more cycles to discriminate against R_opaque's solar-coupled response. Cheap to try; runs in <1 session against the existing G8 machinery.
  - **(b) §6 active perturbation.** Phase A's continuous-fan continuous-compressor drive introduces controlled main-space cooling that swings the attic-main differential through a wider range. The §6 spec predicts this resolves the ridge. Requires Phase 2 Layers 2-3 (F5, F6) shipped first.
  - **(c) Reparametrization.** Replace R_opaque × ceiling_coupling_factor with a less-correlated pair (e.g., total ceiling-plane conductance + an attic-isolation ratio). Architectural change; only attempt if (a) and (b) don't crack the ridge.
- Sequencing: (a) first as a cheap experiment. If (a) succeeds, the §11.2 amendment's expected-tightness table for `R_opaque` and `ceiling_coupling_factor` gets pinned by the result and v0.1 retirement is in reach. If (a) does not succeed, (b) becomes the path and waits on F5/F6.
- Effort estimate: (a) <1 session; (b) gated on F5/F6; (c) variable.

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

**Track 1 — envelope §5 path, first measurement signal achieved:**

```
F1, F2, F3 [SHIPPED]
    │
    ▼
G7  Real-chain adapter         [SHIPPED 2026-05-15, commit 814127e]
    │
    ▼
G8  §5 real-chain test         [SHIPPED 2026-05-15, commit aff8f83]
    │                              4 of 7 parameters recovered at 12h
    ▼
G8a Ridge resolution           ← NEXT (R_opaque × ceiling_coupling_factor ridge)
    │                              (a) 48h passive — cheap experiment, <1 session
    │                              (b) §6 active perturbation — gated on F5/F6
    │                              (c) reparametrization — last resort
    ▼
Ready for §5 production-threshold retirement (7-of-7 coverage)
```

**Track 1b — Phase 1 operational-infiltration amendment, parallel to Track 1's ridge work:**

```
F9  Phase 1 v4.0 → v4.1 (operational-infiltration entry point)
    │                              Retires G7's interim cfm50 translation
    ▼
G7 adapter cleanup: derived-cfm50 path removed
    │
    ▼
(C_stack, C_wind) flow directly to infiltration.py;
posterior on those parameters becomes meaningful at every operating point
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

**Track 3 — envelope §6 path (gated on Track 2 outputs):**

```
G7 [DONE] + F5, F6 + H2 (Day-4 record available) + G3a Phases 2-3 (records / active_fit code rename)
    │
    ▼
G3  §6 real-chain test at production thresholds, 7-of-7 coverage
    │
    ▼
Ready to produce Day-6 signed envelope record
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

## Gates in execution order

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

**G7+G8 achieved (first measurement signal landed) → ridge resolution at 48h + Phase 1 operational-infiltration amendment in parallel → Phase 2 v1 code + `aivu_hvac_greybox` spec/code/test → envelope §6 production-threshold test → `aivu_integrity` pilot-floor → `aivu_hpm` → hardware + pilot home → run 7-Day commissioning → both halves of Digital Birth Certificate signed.**

What v0.2 framed as "earliest stuff works signal" has been achieved. The next milestone shape is not "can the machinery measure anything" but "can the machinery measure *enough* to cross the 7-of-7-parameter production threshold." The ridge-resolution workstream is the immediate next experiment.

---

## Open questions for next session

1. **Ridge resolution: 48h passive first.** The cheapest experiment. Reuse G8's machinery against a 48h synthetic trajectory rather than 12h. If `R_opaque` and `ceiling_coupling_factor` resolve, the §11.2 amendment's expected-tightness predictions get pinned and the §5 leg moves toward production-threshold retirement. If the ridge persists, the path forks to §6 active perturbation (waits on F5/F6) or reparametrization.

2. **Phase 2 Increment 8 read.** Before drafting `aivu_hvac_greybox` H1 spec, read Increment 8 to extract the canonical HVAC parameter set (D17/D19/D20 bi-quadratic + D18 cabinet UA, plus anything else) and any pre-existing forward-side invariants the inverse package will inherit. Mechanical work — likely <1 session of reading.

3. **`aivu_hpm` scoping conversation.** Pre-spec walk-through with JDS to settle: shape of the bounded MRAC inner loop in code; where the phase state machine lives across the 7-day protocol; sub-100ms determinism as v0.1 target vs v0.2 target; standalone-mode behavior priorities. Once these are settled, §1 spec drafting begins.

4. **2026-05-15 HPM-in-circuit-box outcome — STATUS UNKNOWN AS OF v0.3.** v0.2 flagged this as an open question for the 2026-05-15 session. The 2026-05-15 work focused on §11.2 + G7 + G8 and did not surface a hardware status update. Whether hardware actually arrived, and whether hardware-in-the-loop testing is feasible from Claude's environment or requires a partner working against the physical device, is not yet captured in any committed artifact. JDS to confirm or update.

5. **`aivu_integrity` outside cryptographic review.** Who reviews the pilot-floor crypto before pilot data ships.

6. **Vocabulary update workstream across AIVU docs.** Greybox §§5-12 done 2026-05-16. Still pending: Architectural Distillation (cold-start upload, currently still describes 5-Day protocol), System Arch v3.0.1 (currently describes 5-Day in §3), OS doc v9.5, Phoenix Pilot Roadmap, partner-facing materials. Carrying-party assignment per document.

7. **Architectural Distillation update.** The Distillation in cold-start uploads still describes a 5-Day protocol and does not name the MRAC principle. Per Working Preferences, cold-start docs are operationally canonical — every new session that opens without further context forms an obsolete mental model. High-leverage hygiene; <0.5 session.

---

*End of v0.3. Reconciles state after the 2026-05-15 session (§11.2 lock, G7, G8) and the 2026-05-16 day-numbering Phase 1 commit. Replaces v0.2 of 2026-05-14, which had become materially stale during the 2026-05-15 work and was not updated at that session's close. v0.3 lands the discipline added in the header: this document must be updated whenever a commit changes the state of any artifact it names, in the same session as the commit.*
