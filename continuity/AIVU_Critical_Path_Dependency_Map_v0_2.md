# AIVU Critical-Path Dependency Map

**Version:** 0.2 — drafted 2026-05-14 at session close. Walked through with JDS in this session; this draft incorporates the corrections, additions, and architectural finding from that walk-through. Replaces the v0.1 skeleton of 2026-05-13. To be reviewed once more in a subsequent session and then declared authoritative.

**Purpose:** Honest dependency graph of every artifact needed to deliver dual-track commissioning at one Phoenix pilot home. Single source of truth for "what's done, what isn't, what depends on what."

**Discipline this enforces:** No artifact gets called "done" until its honest state, its dependencies, and its retirement-of-stubs are named here.

---

## What changed from v0.1 (the 2026-05-13 skeleton)

Five status errors corrected, three unstarted code artifacts surfaced, one architectural finding about the dual-track nature of commissioning, and one protocol-structure correction from 5-Day to 7-Day.

**Status corrections.** Greybox §§1-12 v0.1 all closed (not just §§4-8). All eight Phase 2 spec increments locked, not three. `aivu_integrity` is `SPECCED_PARTIAL` at the architecture layer (System Arch §6 + greybox §12 interface), not `NOT_SPECCED`. Greybox test count is 69, not the 43 the skeleton inferred. Greybox §6's Phase 2 dependency is Layer 2 + Layer 3, not Layer 1.

**Architectural finding — dual greybox tracks.** The skeleton's goal statement defaulted the deliverable to the envelope half of the Digital Birth Certificate alone. The HVAC half — explicitly named in System Arch §3.3 and greybox §6 v3 as required, and arguably the more structurally novel half because HVAC has *no* commissioning today — was not surfaced as a discrete artifact and had no code package owning it. Inverse identification of HVAC parameters from operating-point sweep telemetry is structurally parallel to envelope inverse identification: same Bayesian machinery, same Laplace fit pattern, same signing call surface, same identifiability/quality-gate discipline, different parameters. A sister package `aivu_hvac_greybox` now owns this work. The package family becomes: forward physics (`aivu_physics`, `aivu_dynamic`) and inverse identification (`aivu_greybox`, `aivu_hvac_greybox`).

**Protocol-structure correction — 7-Day not 5-Day.** The current commissioning protocol described across all documents (System Arch, Architectural Distillation, OS doc, greybox §§1-12, Phoenix Pilot Roadmap) is a 5-Day window. JDS clarified in this session that the actual protocol is 7 days: Day 0 for install and setup, Days 1-2 for envelope passive observation, Days 3-4 for HVAC two-pass commissioning (sweep + repeat for validation), Days 5-6 for envelope active perturbation. This is a vocabulary shift across all AIVU documents; it is flagged here and tracked as a separate documentation update workstream. The dependency map uses 7-Day terminology throughout.

**Two more artifacts surfaced.** `aivu_hpm` — the real-time controller and orchestrator that runs both greybox packages on the actual HPM — was named in the System Arch doc as "scoped but not yet specified" and absent from the skeleton entirely. The real-chain adapter — the small piece of code that wraps `aivu_physics` + `aivu_dynamic` to satisfy greybox's `ForwardChain` Protocol — was buried inside a gate description rather than named as a discrete artifact. Both are now on the critical path.

**Structural finding on the critical path.** The path forks. Envelope's §5 (passive) leg of greybox needs only the real-chain adapter and Phase 1 + dynamic physics. Envelope's §6 (active) leg waits on Phase 2 v1 code AND on `aivu_hvac_greybox`'s Day-4 signed HVAC record. This means once the adapter ships, §5 can run against the real chain *months before* Phase 2 lands — earliest possible "stuff works" signal.

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

---

## Code artifacts — envelope inverse identification (`aivu-greybox` repo)

### G1. `aivu_greybox` §4 (Fan-Heat Consistency Check)
- State: `SHIPPED` (2026-05-13)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/fan_heat.py`
- Tests: 17 passing
- Dependencies: signing stub (Bridging: `STUB`; retires at G9)

### G2. `aivu_greybox` §5 (Days 1-2 passive Laplace fit)
- State: `SHIPPED_WITH_GAPS` (2026-05-13)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/passive_fit.py`
- Tests: 13 passing against `StubForwardChain`
- Dependencies:
  - Forward chain (Bridging: `STUB` via `StubForwardChain`; retires when G7 ships)
  - Signing chain (Bridging: `STUB`; retires at G9)
- Retirement gate: real-chain adapter (G7) ships AND closed-loop test passes at production thresholds (currently kwarg-relaxed against stub)

### G3. `aivu_greybox` §6 (Days 5-6 active perturbation Laplace fit)
- State: `SHIPPED_WITH_GAPS` (2026-05-13)
- Location: `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/active_fit.py`
- Tests: 13 passing against `StubForwardChain`
- Dependencies:
  - Forward chain INCLUDING Phase 2 Layers 2 and 3 (Bridging: `STUB` via `StubForwardChain`; retires when G7 + F5 + F6 ship)
  - Day-4 signed HVAC record from H2 (Bridging: currently absent; retires when `aivu_hvac_greybox` ships)
  - Signing chain (Bridging: `STUB`; retires at G9)
- Retirement gate: real-chain adapter ships AND Phase 2 Layers 2-3 ship AND `aivu_hvac_greybox` Day-4 record available AND closed-loop test passes at production thresholds with full 6-of-6 per-parameter coverage
- This is the artifact most exposed to upstream gaps. Until F5, F6, and H2 ship, §6 has never seen production-quality forward physics or a real HVAC record underneath it.

### G3a. Greybox §6 spec amendment — DAY-LABEL CORRECTION
- State: `NOT_STARTED` documentation work
- Current spec text describes "Days 4-5" active perturbation; corrected protocol is Days 5-6
- INV-FIT45-1 / INV-FIT45-2 reword from "Day-3 map prerequisite" to "Day-4 HVAC record prerequisite"
- Records dataclass rename from `Day5Posterior` to `Day6Posterior` (code change, mechanical)
- AttestationMoment-emission day labels updated
- Carrying party: Claude
- Effort estimate: <1 session

### G4. Other shipped greybox modules
- `psychrometrics.py` — 23 tests passing (ASHRAE reference values)
- `defaults.py` — §11.2 canonical numerical defaults
- `records.py` — dataclasses for signed records (requires G3a-related renames)
- `epw_loader.py` — Phoenix AMY 2024 EPW, 1-Hz interpolated slices
- `forward_chain.py` — `ForwardChain` Protocol contract + `StubForwardChain` analytic stand-in
- `passive_fit_types.py` — Prior6D, telemetry window dataclass, ACCA prior

**Greybox total: 69 tests passing against real Phoenix EPW 2024.**

### G5. `aivu_greybox` §7 (recursive solver)
- State: `SPECCED` (v1.1, locked 2026-05-13)
- Code: deferred to post-pilot per Roadmap A4
- Critical-path role: OFF-PATH for first pilot

### G6. `aivu_greybox` §8 (identifiability collapse detection)
- State: `SHIPPED_WITH_GAPS` — logic embedded in `build_identifiability_report` within `passive_fit.py`; standalone module extraction pending
- Critical-path role: required for pilot. Pending refactor is mechanical and does not change correctness.

### G7. Real-chain adapter — NEW ARTIFACT, NEXT TO SHIP
- State: `NOT_SPECCED` (specification implied by the existing `ForwardChain` Protocol)
- Location: to be created in `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/`
- Carrying party: Claude
- Effort estimate: ~1 session
- Purpose: thin wrapper that satisfies greybox's `ForwardChain` Protocol by wrapping `aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2. Initially Phase 1 + dynamic only (sufficient for §5); Phase 2 wired in once F4-F7 ship (required for §6).
- Critical-path role: **highest leverage unfinished work in the project right now.** Unblocks the envelope §5 leg entirely. Surfaces real-chain integration issues before Phase 2 and `aivu_hvac_greybox` are layered on.

### G8. §5 closed-loop test against the real chain — EARLY-SIGNAL MILESTONE
- State: `NOT_STARTED`
- Carrying party: Claude
- Effort estimate: <1 session
- Purpose: run greybox §5's closed-loop test with the real-chain adapter (G7) in place. §5 does NOT need Phase 2 — it characterizes the envelope under fan-mixed conditions, no HVAC excitation.
- Critical-path role: **earliest "stuff works" signal in the project.** Validates real-chain integration in isolation before §6, Phase 2, and `aivu_hvac_greybox` are layered on.

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

**Track 1 — envelope §5 path, earliest signal:**

```
F1, F2, F3 [SHIPPED]
    │
    ▼
G7  Real-chain adapter         ← NEXT TO SHIP (~1 session)
    │
    ▼
G8  §5 real-chain test         ← EARLY "stuff works" signal (<1 session)
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
G7 + F5, F6 + H2 (Day-4 record available) + G3a (§6 spec amendment)
    │
    ▼
G3  §6 real-chain test at production thresholds, 6-of-6 coverage
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

1. **G7 — real-chain adapter ships.** Unblocks envelope §5 leg. Highest leverage code work. Carrying party: Claude. Effort: ~1 session.
2. **G8 — §5 closed-loop test against real chain passes.** Earliest "stuff works" signal. Effort: <1 session.
3. **F4-F7 — Phase 2 v1 code ships.** Largest unfinished body of work. Effort: ~8 sessions.
4. **H1 — `aivu_hvac_greybox` spec drafted.** Can run in parallel with F4-F7. Effort: ~4 sessions.
5. **H2 — `aivu_hvac_greybox` code ships.** Needs F5, F6, G7. Effort: ~4 sessions.
6. **H3 — HVAC closed-loop test against real Phase 2 passes.** Effort: <1 session.
7. **G3a — Greybox §6 spec amendment (day-label correction).** Effort: <1 session. Can run any time, ideally before G3 production-threshold test.
8. **G3 — envelope §6 closed-loop test against real chain at production thresholds, 6-of-6 coverage.** Effort: <1 session, given G7, F5, F6, H2, G3a all in place.
9. **G9 — `aivu_integrity` pilot-floor ships.** Replaces `_signing_stub` at all call sites in both greybox packages. Outside cryptographic review completed.
10. **G10 — `aivu_hpm` ships, at the level required to run a pilot.** Scoping conversation first.
11. **Hardware, sensors, and pilot home reach pilot-ready state.** Tracked in `AIVU_Phoenix_Pilot_Roadmap.md` workstreams C/D/E.
12. **Run 7-Day commissioning.**

Gates 3, 4-6, 9, and 10 can proceed in parallel. Gate 2 is fast enough to insert between 1 and 3. Gate 7 is independent documentation work.

---

## Critical-path summary in one sentence

**Real-chain adapter → (early-signal §5 test in parallel with) Phase 2 v1 code + `aivu_hvac_greybox` spec/code/test → envelope §6 production-threshold test → `aivu_integrity` pilot-floor → `aivu_hpm` → hardware + pilot home → run 7-Day commissioning → both halves of Digital Birth Certificate signed.**

The fork at the real-chain adapter is the structurally important fact: earliest "stuff works" signal is reachable in ~2 sessions after the adapter ships, without waiting for Phase 2 v1 code, `aivu_hvac_greybox`, or anything downstream.

---

## Open questions for next session

1. **Phase 2 Increment 8 read.** Before drafting `aivu_hvac_greybox` H1 spec, read Increment 8 to extract the canonical HVAC parameter set (D17/D19/D20 bi-quadratic + D18 cabinet UA, plus anything else) and any pre-existing forward-side invariants the inverse package will inherit. Mechanical work — likely <1 session of reading.

2. **`aivu_hpm` scoping conversation.** Pre-spec walk-through with JDS to settle: shape of the bounded MRAC inner loop in code; where the phase state machine lives across the 7-day protocol; sub-100ms determinism as v0.1 target vs v0.2 target; standalone-mode behavior priorities. Once these are settled, §1 spec drafting begins.

3. **2026-05-15 HPM-in-circuit-box outcome.** What hardware actually arrived. Whether hardware-in-the-loop testing is feasible from Claude's environment or requires a partner working against the physical device.

4. **`aivu_integrity` outside cryptographic review.** Who reviews the pilot-floor crypto before pilot data ships.

5. **Vocabulary update workstream across AIVU docs.** 5-Day → 7-Day terminology in System Arch v3.0.1, OS doc v9.5, Architectural Distillation, greybox §§1-12 (G3a is the §6 piece of this), Phoenix Pilot Roadmap, partner-facing materials. Carrying-party assignment per document.

---

*End of v0.2. Walked through with JDS in the 2026-05-14 session and incorporates the corrections, additions, dual-greybox-track architectural finding, and 7-Day protocol correction from that walk-through. Not yet declared authoritative — one more review pass at next session, then graduates into cold-start uploads.*
