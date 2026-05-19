# AIVU Critical-Path Dependency Map

**Version:** 0.8 — drafted 2026-05-19 end of session. Supersedes v0.7 (2026-05-17 end of session) which captured T7 staged-fit shipping and the empirical validation of the v0.4 architectural reformulation. v0.8 captures two sessions of HVAC-track work: 2026-05-18 bootstrapped the HVAC commissioning track end-to-end (F5 v1 forward physics + H2 first-cut inverse-identification + §6 envelope test re-instrumented against measured HVAC), and 2026-05-19 shipped the Day 3-4 commissioning protocol spec and revised Working Preferences in response to two procedural failures. The v0.4 architectural insights stand. The reformulation continues to validate against real physics across all stages now reached.

**Purpose:** Honest dependency graph of every artifact needed to deliver the AIVU measurement architecture at production-defensible quality at one Phoenix pilot home. Single source of truth for "what's done, what isn't, what depends on what."

**Discipline this enforces:** No artifact gets called "done" until its honest state, its dependencies, and its retirement-of-stubs are named here. This document must be updated whenever a commit changes the state of any artifact named below. Update happens in the same session as the commit, not later.

---

## What this version captures: the two-day arc

### 2026-05-18: HVAC commissioning track bootstrapped, with two architectural-sequencing errors caught mid-session

The day opened with an attempt to validate §6 envelope active commissioning against `RealForwardChain` (`test_g8_active_staged_closed_loop.py`). The test produced an uninterpretable 2.1σ C_house bias because the synthesizer drove §6 with hard-coded HVAC values fabricating data the protocol architecture says must come from upstream HVAC characterization. Sequencing error #1 caught: §6 should not be tested against fabricated HVAC; it needed Day4Posterior produced by H2 against measured HVAC.

Drafting H1 v0.2 forward immediately surfaced sequencing error #2: H1 v0.2 referenced "Phase 2 Layer 2 forward physics" as if it existed in code. F4-F7 had been SPECCED on 2026-04-23 but no code had ever been written. H2 cannot fit against forward physics that doesn't exist.

The corrected sequence executed in the afternoon:
- **1a. F5 v1 pilot-scope** (`aivu_physics_phase2` v0.1.0, in `aivu` repo at `~/aivu/code/phase2/`): bi-quadratic forward physics, AHRI anchor enforced exactly, 29 tests passing.
- **1b. H2 first-cut** (`aivu_hvac_greybox` v0.1.0, in `aivu-greybox` repo): joint Laplace fit over D17_pilot + D20_pilot 10 free coefficients. Pass A closed-loop recovery against F5 passes; 95% CI covers truth on all 10 free coefficients; Hessian well-conditioned; AHRI anchor holds exactly through the fit. 10 tests passing.
- **2. Step 2 — §6 envelope test against measured HVAC** (`test_g8_active_staged_with_measured_hvac.py`): identical to morning's fabricated-HVAC test except Phase A cooling capacity is queried per-time-step from the Day4Posterior. **2 of 3 passed.** Stage 4 C_w PASSED; posterior-movement PASSED; Stage 3 C_house FAILED coverage with same posterior MAP as the fabricated-HVAC run (4.893e+06 vs truth 4.5e+06, 3.92σ off). The diagnostic `diag_day4_posterior_gap.py` confirmed Day4Posterior MAP tracks truth to within 0.05% across Phase A operating envelope, exonerating H2 as the source. The remaining bias is software-internal between simulator and §6 fit, ~0.1°F/hr indoor temperature impact (not field-relevant), tracked as mechanical debug homework.

Mid-session, two hardware vendor commitments landed:
- **M&M Manufacturing (Berkshire Hathaway operating company)** committed to manufacture and calibrate all Venturi airflow devices in-house at no cost on an 8-week timeline.
- **Device Solutions NC** committed to the HPM and Venturi interface boxes on the same timeline; NDA in progress.

First pilot hardware expected mid-July 2026. Two of the four open Hardware Spec §9 architectural items (HPM form factor, pod-to-ASC protocol) likely close as Device Solutions completes their design. ASC power source and I²C addressing remain open pending vendor design responses.

Nine architectural decisions logged for future-session continuity (full list in `AIVU_Current_State.md` 2026-05-18); the load-bearing ones:
- HVAC measurement is register-side (composite equipment × distribution_efficiency), not equipment-side.
- Pilot scope reduces H1 from 6 fitted parameters to 2 (D17_pilot, D20_pilot only).
- Phase 2 pilot scope reduces F4/F5/F6/F7 substantially; F4 deferred, F6 absorbed into H1 v0.2 register-side measurement, F7 light.
- Day-numbering correction: **7-Day Cx protocol** (Day 0 install + Days 1-2 passive envelope → Day2Posterior + Days 3-4 HVAC → Day4Posterior + Days 5-6 active envelope → Day6Posterior).
- Outside cryptographic review for G9 signing deferred to 50-home field trial; T5 §12.x signed-record schema remains on critical path.

### 2026-05-19: Day 3-4 protocol spec shipped, two procedural failures named and addressed

Session opened by surfacing the Mode 1 / Mode 2 / Mode 3 trade-off from Current State 2026-05-18 as an open decision. `conversation_search` recovered the resolution reached in chat after Current State was drafted: Day 3-4 produces a **primary measurement** of installed-system delivered Q(T_odb, T_wbe) and EER(T_odb, T_wbe) with quantified uncertainty; the bi-quadratic is a recording format, not a model to validate; the Mode trade-off dissolves under this framing because there is no defensibility-of-model concern. Mode 3 (setpoint manipulation across the natural Phoenix diurnal climb) follows.

`AIVU_HVAC_Commissioning_Protocol_Day34_v0_1.md` drafted in one pass against this resolution, ~240 lines. Defines the routine `aivu_hvac_greybox.sweep_orchestrator` will implement: 5 T_odb crossing levels × 3 cooling-load setpoint conditions per crossing = 15 sweep points target per day; best-effort acquisition with quantified uncertainty per acquired point; T_wbe falls out of the setpoint condition rather than being commanded directly. Scope decision: humid operating conditions never occur in Phoenix; AHRI's lab characterization at high T_wbe is trusted; no artificial humidification. A humid-climate protocol variant would revisit. Pre-conditions section clarifies that the contractor installs, HERS may rate operating parameters pro forma, **AIVU commissions** delivered capacity and EER — the institutional position the document sits on top of.

Two procedural failures named and addressed:

1. **2026-05-17 → 2026-05-18: spec-vs-code conflation.** The §6 test against fabricated HVAC consumed "Phase 2 Layer 2 forward physics" that had never been written. Spec-to-code latency in this project is frequently weeks; Claude treated "this was specified" as evidence "this is implemented." Addressed by adding to Working Preferences: verify upstream inputs exist as validated, tested code in the repo before reasoning forward.

2. **2026-05-18 → 2026-05-19: cold-start-vs-chat conflation.** Current State documented the Mode trade-off as "paused" because it was drafted while Claude perceived session-close on time-zone-misled pacing intuition, before the live chat resolution actually completed. Today's session opened against the stale documentation and started relitigating. Addressed by two Working Preferences additions: (a) session-close is gated on JDS's explicit signal, not Claude's pacing intuition, with Current State drafted last after all substantive discussion concluded; (b) any open question or paused decision in Current State gets `conversation_search`'d before being surfaced for ruling.

`AIVU_Working_Preferences.md` revised today, 170 → 176 lines, cold-start-canonical copy updated in `~/Desktop/Claude cold start Uploads/`.

---

## Prior context — v0.4 architectural insights, still standing

Summarized for self-containment; full content in v0.4 (greybox commit `c87e884`).

**Insight 1: Sequential identification by frequency band within Cx.** Joint fit could not identify seven parameters from §5 passive observation (Hessian condition number 2.9 × 10^14). Structural fix: four stages, frequency-bands separated, posterior-as-prior propagation. Validated 2026-05-17 against real Phase 1 + aivu_dynamic at 24h and 48h Phoenix-July windows. Stage 3 + Stage 4 now also validated against measured HVAC (2-of-3 in Step 2 2026-05-18), with a remaining software-internal bias on C_house tracked as homework.

**Insight 2: Temporal identification across Cx and continuous operation.** Per-parameter primary identification horizons. Some parameters reach production tightness within Cx; others require operational telemetry. The HPM tags regime-clean observation windows, accumulates per-regime statistics, feeds them to the BDT periodically for posterior refinement.

---

## Goal

**Deliver 7-Day dual-track commissioning at one Phoenix pilot home**, producing two independently signed records that together constitute the Digital Birth Certificate:

1. **Envelope half.** End-of-Day-6 `Day6Posterior` record with `AttestationMoment.ENVELOPE_HALF_FINAL`. Five parameters at `confidence_state = "production-threshold-at-Cx"` (R_opaque, U_fenestration, ceiling_coupling_factor at Stage 1; C_house at Stage 3; C_w at Stage 4); two parameters at `confidence_state = "preliminary-refining-at-Cx"` (C_stack, C_wind at Stage 2). Signed by the real `aivu_integrity` chain.

2. **HVAC half.** End-of-Day-4 record with `AttestationMoment.HVAC_HALF`. **Pilot scope: two parameters** (D17_pilot delivered capacity, D20_pilot EER), 10 free coefficients total fit jointly via Laplace + 2 AHRI anchors. Signed by `aivu_integrity` (pilot-floor stub during 1-home pilot; outside cryptographic review deferred to 50-home field trial).

---

## The 7-Day protocol

| Day | Activity | Track | Signed output |
|---|---|---|---|
| 0 | Hardware install, sensor placement, Mixing Length Verification, connectivity handshake | — | (none) |
| 1-2 | Envelope passive observation under fan-mixed conditions | envelope | `Day2Posterior` |
| 3-4 | HVAC operating-point sweep (Day 3 establishes; Day 4 validates) | HVAC | `Day4Posterior` / `HVAC_HALF` |
| 5-6 | Envelope active perturbation using calibrated HVAC as known excitation | envelope | `Day6Posterior` / `ENVELOPE_HALF_FINAL` |

---

## Conventions

**State** of an artifact:
- `SHIPPED` — code written, tested, committed; tests pass at production thresholds
- `SHIPPED_WITH_GAPS` — usable for some purposes; named gaps disqualify it for others
- `DRAFT_SHIPPED` — first-cut spec or skeleton committed; not yet Authoritative
- `SPECCED` — spec locked and complete; code does not yet exist
- `SPECCED_PARTIAL` — spec exists but has known holes
- `NOT_SPECCED` — no formal spec; design intent only
- `NOT_STARTED` — neither spec nor code begun

**Bridging** of a dependency: `REAL` / `STUB` / `SYNTHETIC` as in v0.6.

---

## Code artifacts — forward physics (`aivu-physics` repo)

### F1-F3.
Unchanged from v0.7. SHIPPED.

### F4 — Phase 2 Layer 1 (operational thermostat control)
- State: `SPECCED` (2026-04-23); **DEFERRED** for pilot per 2026-05-18 architectural decision
- Operational thermostat control logic is post-Cx scope; not pilot-blocking
- Recovers in v0.3 field-trial spec scope

### F5 — Phase 2 Layer 2 (equipment output bi-quadratics)
- State: **`SHIPPED` v0.1.0** (commit `d2f0795` on `aivu` repo, 2026-05-18)
- Pilot subset: three bi-quadratics (D17 capacity, D19 SHR, D20 EER) + composition rules + single-stage and two-stage dispatch + forward chain wrapping
- AHRI anchors satisfied exactly. 29 tests pass in 0.02s.
- New directory: `~/aivu/code/phase2/aivu_physics_phase2/`
- v0.2 scope (deferred): 8760-hour orchestration, cycling/PLF, fan-heat boundary, D18 cabinet derating, refrigerant-line pickup, variable-speed modulation

### F6 — Phase 2 Layer 3 (duct delivery)
- State: **ABSORBED into H1 v0.2** for pilot per 2026-05-18 architectural decision
- HVAC measurement is register-side (composite equipment × distribution_efficiency), end-to-end as one unit. No separate Phase 2 Layer 3 code for v1 pilot.
- Recovers as standalone module in v0.3 field-trial scope when per-register diagnostics surface as first-class deliverable

### F7 — Phase 2 cross-layer invariants
- State: `SPECCED`; light pilot-scope implementation (specifics in 2026-05-18 architectural decisions)

### F8.
Unchanged from v0.7.

### F9 — Phase 1 operational-infiltration amendment
- State: `NOT_STARTED`; remains demoted per v0.4; not pilot-blocking

### F10 — Pre-commissioning validation gate
- State: `NOT_STARTED`; T8 in T-series. Depends on staged-fit + signed-record construction

---

## Code artifacts — envelope inverse identification (`aivu-greybox` repo)

Unchanged from v0.7 except as noted below.

### G2. `aivu_greybox` §5 (passive Laplace fit)
- State: `SHIPPED_WITH_GAPS` (unchanged)
- Joint-fit `passive_fit.py` retained as reference; `staged_fit.py` is the production path

### G3. `aivu_greybox` §6 (active perturbation Laplace fit)
- State: `SHIPPED_WITH_GAPS` (unchanged)
- Joint-fit `active_fit.py` retained as reference; `staged_fit.py` carries Stages 3, 4

### G8-staged. §5 staged closed-loop test against real chain
- State: `SHIPPED` (commit `8448b7a` 2026-05-17)
- 3/3 passing at 24h and 48h Phoenix-July against real Phase 1 + aivu_dynamic
- Empirical validation of v0.4 architectural reformulation

### G7-G10 unchanged in state from v0.7. See v0.7 for details.

---

## Code artifacts — HVAC inverse identification (`aivu_hvac_greybox`)

### H1. Package spec
- State: **`DRAFT_SHIPPED` v0.2** (commit `d57ba2a` on `aivu-greybox` repo, 2026-05-18)
- Pilot scope: D17_pilot delivered capacity + D20_pilot EER, 10 free coefficients joint Laplace
- v0.1 preserved as v0.3 field-trial seed (D17-D22 full scope, six parameters)

### H2. Code (first-cut)
- State: **`SHIPPED` v0.1.0** (commit `d57ba2a` on `aivu-greybox` repo, 2026-05-18)
- Joint Laplace fit over 10 free coefficients. Pass A closed-loop recovery against F5: optimizer converges, Hessian well-conditioned, 95% CI covers truth, AHRI anchor holds exactly. 10 tests passing.
- Day4Posterior with `evaluate_q_delivered` / `evaluate_eer` §6-consumption interface.
- **Four modules deferred to v1 completion:** `sweep_orchestrator.py`, `cross_validation.py`, `quality_gates.py`, `forward_chain.py` as separate module
- Day4Posterior MAP-vs-truth gap confirmed <0.5% across Phase A envelope by `diag_day4_posterior_gap.py`

### H2-protocol. Day 3-4 HVAC Commissioning Protocol spec
- State: **`DRAFT_SHIPPED` v0.1** (drafted 2026-05-19, not yet committed)
- Specifies the routine `sweep_orchestrator.py` will implement: 5 T_odb crossings × 3 cooling-load setpoint conditions per crossing; setpoint manipulation only (no compressor-stage commands per AIVU Stance); best-effort with quantified uncertainty per acquired point
- Trust-AHRI-on-humidity scope decision for Phoenix; humid-climate variant deferred to v0.2 of this protocol

### H3. Closed-loop test against real Phase 2
- State: `NOT_STARTED`; depends on H2 v1 completion (four deferred modules) and Phase 2 v1 code

---

## Code artifacts — signed records and orchestrator

### G9-G10. Unchanged from v0.7.

---

## Architectural workstreams (T-series)

### T1-T6. Unchanged in state from v0.7.

### T7. Staged-fit code
- State: `SHIPPED` (commit `8448b7a`, 2026-05-17)
- Signed-record construction (Day2Posterior, Day6Posterior from staged outputs) pending T5 §12.x schema

### T8. F10 pre-commissioning validation gate
- State: `NOT_STARTED`; depends on T7 (satisfied) and signed-record construction
- Effort: <1 session once Day6Posterior construction lands

### T9. §6 staged closed-loop test against real chain
- State: `NOT_STARTED`; depends on T7 (satisfied)
- **Effort: <1 session.** Highest-leverage envelope-track item. Mirrors G8-staged but uses `synthesize_day45_window` real-chain analog with the four-phase HVAC excitation
- Pass criteria: Stage 3 95% CI coverage on C_house, Stage 4 95% CI coverage on C_w, both against real Phase 1 + aivu_dynamic

### T10 (NEW). Critical Path Map maintenance
- State: this document, drafted 2026-05-19 end of session
- Surfaces as workstream because v0.7 → v0.8 reshuffled enough state that the previous "next session's first half-hour" assumption no longer holds; v0.8 is the new anchor

---

## Hardware track

Substantially closed since v0.7:

- **M&M Manufacturing Venturi commitment** received 2026-05-18: in-house manufacturing and calibration of all Venturi airflow devices, no cost, 8-week timeline. Berkshire Hathaway operating company; Carrier-affiliated through flexible-duct heritage. Institutional credibility weight when pilot data is presented to institutional reviewers.
- **Device Solutions NC commitment** received 2026-05-18: HPM and Venturi interface boxes on the specs sent, 8-week timeline. NDA in progress. Two of four open Hardware Spec §9 architectural items (HPM form factor, pod-to-ASC protocol) likely close as Device Solutions completes their internal design. ASC power source and I²C addressing remain open pending vendor design responses.
- **First pilot hardware expected mid-July 2026.**

The hardware-vendor risk that loomed over the v0.4 → v0.7 arc is substantially contained. Pilot timeline now hinges on software side: protocol spec lock, sweep_orchestrator implementation, H2 v1 completion, T9 §6 staged validation, signed-record construction, integrity layer, HPM firmware.

---

## Remaining, in execution order under "ASAP to productive 7-Day Cx"

**Pilot-blocking software sequence — UPDATED in v0.8:**

1. **C_house bias mechanical debug** (homework queued for next session opening). `eta_distribution=1.0` rerun first; structural mismatch hypotheses in Current State 2026-05-18 if (1) doesn't move it.
2. **T9 §6 staged closed-loop against real chain.** v0.7 carried; still highest-leverage envelope-side. <1 session.
3. **H2 v1 completion: four deferred modules.**
   - `sweep_orchestrator.py` — Day 3-4 state machine implementing the Day 3-4 protocol spec
   - `cross_validation.py` — Day 3 vs Day 4 mode-agreement check per H1 v0.2 §4.2
   - `quality_gates.py` — production-threshold identifiability machinery, parallel to greybox §8
   - `forward_chain.py` as separate module (F5 currently imported directly)
   - Effort: ~2-3 sessions combined
4. **H2 Pass B real-chain integration** (against full Phase 2 v1 code, not synthetic F5). Depends on F4/F7 pilot-scope completion.
5. **H2 Pass E real-chain at Cx duration** (analog of envelope G8-staged). Depends on Pass B.
6. **Signed-record construction in staged_fit.py and aivu_hvac_greybox** (Day2Posterior, Day4Posterior, Day6Posterior from staged outputs). Depends on T5 §12.x schema decisions.
7. **T8 F10 pre-commissioning validation gate.** Depends on signed-record construction.
8. **T2 v0.3 / T3 v0.2 amendment text reconciliation.** Pure text-against-shipped-code bookkeeping; <1 session combined.

**In parallel:**

- F4/F7 pilot-scope completion (Phase 2 v1 envelope code, reduced scope per 2026-05-18). ~3-4 sessions remaining (down from v0.7's ~8 because of pilot-scope reductions).
- G3a Phases 2-5 day-numbering reconciliation. ~2.5 sessions.
- T1 v0.2, T4 §11.x, T5 §12.x, T6 MRAC fold-in (project-coherence work).
- Architectural Distillation v0.2 — earned by today's protocol spec landing and the AIVU-commissions framing now explicit. ~0.5 session.

**After convergence:**

G9 `aivu_integrity` pilot-floor (cryptographic review deferred to 50-home; pilot-floor stub sufficient for one-home pilot), G10 `aivu_hpm` scoping/spec/code, hardware/sensors/pilot home → 7-Day Cx execution.

---

## Critical-path summary in one sentence

**C_house bias homework first; T9 + H2 v1 completion (four deferred modules) + signed-record construction + T8 gate complete the inverse-identification track (~5 sessions total); F4/F7 pilot-scope completion in parallel (~3-4 sessions); H2 Pass B/E run after Phase 2 v1 lands; then convergence on G9 `aivu_integrity` pilot-floor + G10 `aivu_hpm` scoping/spec/code + hardware delivery (mid-July 2026) → run 7-Day Cx at one Phoenix pilot home → operational telemetry refines weakly-identified parameters and HVAC coefficients over months/years.**

The structural cure for the compound fracture (envelope and HVAC each specified assuming the other works) is end-to-end measurable in code: §5 staged-fit validated against real physics (2026-05-17), §6 stages validated against measured HVAC (2026-05-18, with one software-internal bias tracked as homework), H2 fits against F5 forward physics with 95% CI coverage on 10 free coefficients (2026-05-18), Day 3-4 commissioning protocol specifies the data-acquisition routine (2026-05-19). What remains is plumbing.

---

## Off-path items

Unchanged from v0.7.

---

## Open questions for next session

1. **C_house bias mechanical debug** — first task of next session. Sequence in Current State 2026-05-18 "homework" section: `eta_distribution=1.0` rerun, then Q_total-vs-Q_sensible handling check, then Stage 3 likelihood behavior at high excitation amplitude. (If the rerun executed mid-session 2026-05-19, the finding folds into this entry rather than reopening it.)
2. **T9 §6 staged closed-loop against real chain.** v0.7 priority carried; <1 session.
3. **Architectural Distillation v0.2.** Earned by today's work; ~0.5 session.
4. **HPM-in-circuit-box hardware status** — carried from v0.7. Device Solutions commitment 2026-05-18 likely resolves but JDS to confirm.
5. **G10 `aivu_hpm` scoping conversation.** Without `aivu_hpm` there is no pilot. Architecture-level questions to settle before §1 spec text: shape of the bounded MRAC inner loop, where the phase state machine lives across the 7-Day protocol, sub-100ms determinism as v0.1 target or v0.2 target, standalone-mode behavior priorities.
6. **Day 3-4 protocol spec lock criterion.** v0.1 ships today as DRAFT_SHIPPED. v0.2 spec-lock per the spec's closing note requires pilot Day 3-4 execution producing a Day4Posterior that H2 consumes successfully and that the §6 envelope active commissioning (Days 5-6) consumes successfully. Until then, v0.1 is the working document and sweep_orchestrator code is drafted against it.

---

*End of v0.8. Drafted 2026-05-19 end of session. Captures two sessions of HVAC-track work (2026-05-18 commissioning bootstrap + 2026-05-19 protocol spec) plus two procedural failures addressed in Working Preferences. v0.4's architectural insights stand. The reformulation continues to validate against real physics across all stages reached so far. Next session opens against this document; if anything below was relitigated mid-session and resolved differently, this file is stale and v0.9 reconciles before reasoning forward.*
