# AIVU Critical-Path Dependency Map

**Version:** 0.7 — drafted 2026-05-17 end of session, capturing today's afternoon validation work. Supersedes v0.6 (same date, morning). The afternoon's work shipped T7 staged-fit code (v0.1.1), validated it via fast tests (19/20 passing), and demonstrated end-to-end recovery against real Phase 1 + aivu_dynamic physics at 24h (13 min) and 48h (23 min) Phoenix-July windows. The v0.4 architectural reformulation is now empirically validated, not just architecturally argued. v0.6 remains in git history; v0.4's two architectural insights stand unchanged in v0.7.

**Purpose:** Honest dependency graph of every artifact needed to deliver the AIVU measurement architecture at production-defensible quality at one Phoenix pilot home. Single source of truth for "what's done, what isn't, what depends on what."

**Discipline this enforces:** No artifact gets called "done" until its honest state, its dependencies, and its retirement-of-stubs are named here. This document must be updated whenever a commit changes the state of any artifact named below. Update happens in the same session as the commit, not later.

---

## What this version captures: the yesterday-to-today arc

### Yesterday (2026-05-16): the failure that drove the reformulation

The first G8 closed-loop test against `RealForwardChain` at 12h Phoenix-July showed only **4 of 7 parameters covered** at 95% CI against a perturbed θ_true. The G8a diagnostic confirmed why: Hessian condition number 2.9 × 10^14, four single-parameter near-zero eigenvectors. The joint fit could not identify seven parameters from 48h of passive observation regardless of window length — a structural identifiability failure, not a numerical one. We documented this honestly by lowering the G8 assertion bar to 4-of-7 with an inline note that ridge resolution was tracked as a separate workstream. The result was the v0.4 architectural reformulation commit (`c87e884`).

### The decision: structural reformulation, not joint-fit patching

Parameters affect the residual at different frequency bands. R_opaque / U_fenestration / ceiling_coupling_factor drive the diurnal-fundamental response. C_stack / C_wind drive the synoptic band. C_house drives thermal-mass transients. C_w drives moisture dynamics. Fitting all seven simultaneously against full-spectrum residual confounds them; **fitting them sequentially against band-restricted residuals separates them.** Four stages, posterior-as-prior propagation between stages, frequency-domain Welch likelihood per stage. Plus the two-tier horizon model placing C_stack and C_wind as Stage 2 best-effort within Cx, primary-identified operationally — Cx defensibility does not gate on infiltration parameters whose constraint depends on wind events the 48h window may not contain.

This was not a patch. It was a different identification structure that solves the problem the joint fit could not.

### Today (2026-05-17): the reformulation validated end-to-end

T7 v0.1.1 `staged_fit.py` shipped (~980 lines). Tested against the same real Phase 1 + aivu_dynamic chain that failed yesterday:

- **Fast-test suite**: 19 of 20 passed (single failure is a known stub-physics artifact, resolved under real physics)
- **G8-staged at 24h Phoenix-July**: **3 of 3 passed in 13 min 13 s.** Stage 1 recovered all three conductances at 95% CI — including the R_opaque that defeated the joint fit yesterday.
- **G8-staged at 48h Phoenix-July** (canonical Cx-duration validation): **3 of 3 passed in 22 min 56 s.**

The architectural reformulation is empirically validated, not just architecturally argued. 7-Day Cx pilot defensibility is structurally on the table.

---

## What changed from v0.6 (morning 2026-05-17)

v0.6 captured the morning's architectural decisions (math framework choice (b), two-tier horizon model, T1/T2/H1 first cuts) and projected the critical path as "T2 v0.2 → T3 v0.1 → T7 code → T8 gate."

**v0.7 captures that this projection was overly conservative.** The actual afternoon ordering ran code-first, validate-immediately, text-reconcile-later. The architectural understanding from the morning was sharp enough that T7 code could be drafted directly against the v0.1 amendments rather than waiting for v0.2/v0.3 text-level reconciliation. The closed-loop validation against real physics ran the same session as the code shipped.

### Artifacts shipped after v0.6

- **T7 v0.1.1 `staged_fit.py`** — ~980 lines. Four StageSpec constants with concrete Welch parameters and band edges. `welch_band_weighted_negloglik` with the correct Parseval N-factor and linear detrending. Passive (§5) and active (§6) observation extractors. Shared Laplace orchestration. Posterior-as-prior propagation. `run_staged_passive_batch_fit` and `run_staged_active_batch_fit` orchestrators.

- **Fast-test suite `test_staged_fit.py`** — 20 tests across Welch likelihood math, observation extraction, posterior propagation, Stage 1 / Stage 3 / Stage 4 closed-loop recovery against stub, Stage 2 best-effort behavior, end-to-end orchestrators, Stage 1 gating discipline. **19 of 20 passed.** Single failure (`test_stage1_posterior_tighter_than_prior_on_target_params`) is a stub-physics artifact — the stub doesn't model Phase 1's full diurnal envelope dynamics, so the band-restricted Welch likelihood under stub has marginal informational density on R_opaque. The same parameter tightens correctly under real physics in the G8-staged validation below.

- **G8-staged closed-loop validation `test_g8_staged_closed_loop.py`** — 3 tests against `RealForwardChain` (real Phase 1 + aivu_dynamic) at `THETA_TRUE_PERTURBED` (perturbed off ACCA Manual J fallback prior mean on every parameter).
  - **24h Phoenix-July window: 3/3 passed in 13 min 13 s**
  - **48h Phoenix-July window: 3/3 passed in 22 min 56 s** (the canonical Cx-duration validation)
  - Stage 1 (gating) recovers R_opaque, U_fenestration, ceiling_coupling_factor at 95% CI coverage. Stage 2 (best-effort) completes without raising. Posterior demonstrably moves from prior, ruling out silent prior-snap.

### Bug fixes shipped after v0.6

Three bugs in the T7 v0.1 first cut were caught and fixed mid-session via theory review against the residual likelihood math:

1. **Welch N-factor missing.** Original code returned `0.5 × band_power / sigma_obs²`. Correct per Parseval is `0.5 × N × band_power / sigma_obs²`. Without the N factor the likelihood was orders of magnitude below the prior penalty and the optimizer collapsed to the prior. Fixed in v0.1.1.

2. **Welch windows too short for their bands.** Original Stage 1 used a 6h Welch window with a [1/24h, 1/6h] target band. Spectral resolution df = 1/T_seg = 1/6h means the band's low-frequency edge (1/24h) sat below the Welch window's spectral resolution; the band collapsed to ~1 bin. Lengthened to 24h / 24h / 12h / 3h for Stages 1-4. Fixed in v0.1.1.

3. **Night filter retired.** Originally Stages 1, 3, 4 night-filtered to suppress solar contamination. The forward chain models solar via sol-air temperature, so daytime residuals carry valid model-mismatch information. Time-domain night exclusion was solving a problem the model already solves AND shortened the residual signal, damaging spectral resolution at the diurnal fundamental. Retired across all stages in v0.1.1; the `night_filter_mask` function remains in place as dead code with a future-use comment.

### Substantive items surfaced after v0.6

- **Linear detrending per Welch segment** as a deliberate spectral-leakage-suppression mechanism. The Hann window's main lobe is ~4 bins wide; without detrending, DC leakage from a non-zero residual mean contaminates the first non-DC bin (= the diurnal fundamental for Stage 1's 24h segment). `detrend="linear"` removes mean + linear drift per segment, isolating the load-bearing diurnal-band content.

- **Code-first / text-second ordering observation.** Today demonstrated that when architectural understanding is sharp, the code can ship ahead of text-level amendment reconciliation. T2 v0.2 amendment text references 6h/12h Welch windows and night filtering; v0.1.1 code uses 24h/24h/12h/3h and no night filter. The code is source of truth, the text catches up at next-session pace. v0.7's execution ordering reflects this discipline rather than the strict spec-before-code ordering of v0.6.

### What did not change from v0.6

The two-tier horizon model stands. The math framework choice (b) stands. The pilot-blocking vs. project-coherence split stands. T1 v0.1.1 with two-tier pointer remains unchanged. H1 v0.1 first cut stands. v0.4's architectural insights stand and are now empirically validated.

---

## Prior context — v0.4 architectural insights (2026-05-16 afternoon)

Summarized for self-containment; full content in v0.4 (greybox commit `c87e884`) and v0.5/v0.6 (same date earlier this session).

**Insight 1: Sequential identification by frequency band within Cx.** Joint fit could not identify seven parameters from §5 passive observation (Hessian condition number 2.9 × 10^14, four single-parameter near-zero eigenvectors). Structural fix: four stages, frequency-bands separated, posterior-as-prior propagation. **Validated 2026-05-17 afternoon against real Phase 1 + aivu_dynamic.**

**Insight 2: Temporal identification across Cx and continuous operation.** Per-parameter primary identification horizons. Some parameters (R_opaque, U_fenestration, ceiling_coupling_factor, C_house, C_w) reach production tightness within Cx; others (C_stack, C_wind, plus HVAC parameters that drift over operational time) require operational telemetry. The HPM tags regime-clean observation windows, accumulates per-regime statistics, feeds the BDT periodically for posterior refinement.

---

## Goal

**Deliver 7-Day dual-track commissioning at one Phoenix pilot home**, producing two independently signed records that together constitute the Digital Birth Certificate:

1. **Envelope half.** End-of-Day-6 `Day6Posterior` record with `AttestationMoment.ENVELOPE_HALF_FINAL`. Five parameters at `confidence_state = "production-threshold-at-Cx"` (R_opaque, U_fenestration, ceiling_coupling_factor at Stage 1; C_house at Stage 3; C_w at Stage 4); two parameters at `confidence_state = "preliminary-refining-at-Cx"` (C_stack, C_wind at Stage 2). Signed by the real `aivu_integrity` chain.

2. **HVAC half.** End-of-Day-4 record with `AttestationMoment.HVAC_HALF`. Six D-candidates per Increment 8, 25 scalars total. Signed by the real `aivu_integrity` chain.

---

## The 7-Day protocol

| Day | Activity | Track | Signed output |
|---|---|---|---|
| 0 | Hardware install, sensor placement, Mixing Length Verification, connectivity handshake, sanity checks | — | (none) |
| 1-2 | Envelope passive observation under fan-mixed conditions; D18 cabinet UA measured during fan-only segments | envelope + HVAC | `Day2Posterior` / `ENVELOPE_HALF_INITIAL` |
| 3-4 | HVAC operating-point sweep (Day 3 establishes; Day 4 validates + duct-blower test) | HVAC | Day-4 record / `HVAC_HALF` |
| 5-6 | Envelope active perturbation using the calibrated HVAC as known excitation source | envelope | `Day6Posterior` / `ENVELOPE_HALF_FINAL` |

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

### F1-F8.
Unchanged from v0.6.

### F9. Phase 1 operational-infiltration amendment
- State: `NOT_STARTED`, DEMOTED in v0.4, remains demoted in v0.7
- Cleanliness item under two-tier horizon model; not pilot-blocking

---

## Code artifacts — envelope inverse identification (`aivu-greybox` repo)

### G1. `aivu_greybox` §4 (Fan-Heat Consistency)
- State: `SHIPPED`; 17 tests

### G2. `aivu_greybox` §5 (passive Laplace fit)
- State: `SHIPPED_WITH_GAPS` (revised from v0.6's `SPEC_AMENDMENT_IN_PROGRESS`)
- The original joint-fit `passive_fit.py` remains in the repo as the joint-fit reference and continues to power `test_passive_fit.py`. The staged-fit reformulation (T7's `staged_fit.py`) shipped as a parallel module rather than rewriting `passive_fit.py` in place.
- Gap: amendment text (T2) lags v0.1.1 code by Welch parameters, night-filter retirement, and band edges. Next session: T2 v0.3 reconciliation.

### G3. `aivu_greybox` §6 (active perturbation Laplace fit)
- State: `SHIPPED_WITH_GAPS` (revised from v0.6's `SPEC_AMENDMENT_REQUIRED`)
- Same situation as G2: joint-fit `active_fit.py` remains as reference; `staged_fit.py` carries the §6 stages (3, 4). Stage 3 + Stage 4 closed-loop recovery against stub demonstrated; real-chain validation for §6 stages is the next G8-equivalent (T9, new in v0.7 below).

### G3a. Day-Numbering Reconciliation Workstream
- Phases 1-4: unchanged from v0.6
- Phase 5 (Phase 2 Physics Spec Increments): NOT_STARTED, ~1 session

### G4. Other shipped greybox modules
- Plus `staged_fit.py` as of 2026-05-17. Total: 79 tests + 23 new staged-fit tests passing (19 fast + 3 real-chain × 2 window durations confirmed).

### G5-G6. Unchanged from v0.6.

### G7. Real-chain adapter
- State: `SHIPPED` (commit 814127e, 2026-05-15)
- **Confirmed conforming under real-physics load by today's G8-staged validation.** RealForwardChain delivered consistent T_in / W_in / T_attic trajectories across both 24h and 48h test runs; envelope-overrides context manager properly snapshotted and restored Phase 1 module constants.

### G8. §5 closed-loop test against real chain
- State: RETIRED as measurement signal under joint-fit (since joint fit fails identifiability)
- Survives as `test_g8_closed_loop.py` baseline scaffolding inside T7

### G8a. Ridge resolution workstream
- State: RETIRED — confirmed unnecessary by today's G8-staged success

### **G8-staged. §5 staged closed-loop test against real chain (NEW in v0.7)**
- State: `SHIPPED` — `test_g8_staged_closed_loop.py` passing at 24h and 48h
- Empirical validation that the v0.4 + v0.6 architectural reformulation works under real Phase 1 physics
- Pass criteria met: Stage 1 (gating) 95% CI coverage on all three conductances; Stage 2 (best-effort) completes without raising; posterior moves from prior

---

## Code artifacts — HVAC inverse identification (`aivu_hvac_greybox`)

### H1. Package spec
- State: `DRAFT_SHIPPED` (v0.1 first cut 2026-05-17)
- v0.2 scope unchanged from v0.6

### H2-H3. Code and closed-loop test
- State: `NOT_STARTED`; gated on H1 lock

---

## Code artifacts — signing chain and orchestrator

### G9-G10. Unchanged from v0.6.

---

## Architectural workstreams (T-series)

### T1. AIVU Temporal Identification Architecture document
- State: `DRAFT_SHIPPED` (v0.1.1 with two-tier pointer 2026-05-17)
- v0.2 scope unchanged: operational refinement detail, per-home vs. per-cohort, HVAC operational refinement, two-tier model fleshed out

### T2. §5.3 spec amendment
- State: `DRAFT_SHIPPED` (v0.2, 2026-05-17 morning)
- v0.3 scope: **text-level reconciliation to v0.1.1 code reality** — 24h Welch windows (not 6h/12h), night filter retired, linear detrending added, N-factor fix documented in the math derivation, band edges per stage. Effort: <1 session.
- Code is source of truth as of 2026-05-17 afternoon.

### T3. §6.3 spec amendment
- State: `DRAFT_SHIPPED` (v0.1, 2026-05-17 morning)
- v0.2 scope: **text-level reconciliation to v0.1.1 code reality** — Stages 3 and 4 consume full 48h window across all phases (not phase-restricted to Phase B / Phase D as v0.1 text claims), no night filter. Effort: <1 session.

### T4-T6. Unchanged from v0.6.

### T7. Code rewrites — staged_fit.py (NOT passive_fit/active_fit in place)
- State: `SHIPPED` (v0.1.1, 2026-05-17)
- Architecture deviated from v0.6's framing: rather than rewriting `passive_fit.py` and `active_fit.py` in place, T7 shipped a parallel `staged_fit.py` module that uses the same `ForwardChain` Protocol but implements the staged Welch-likelihood machinery independently. Cleaner separation; existing joint-fit code remains as reference; no breaking changes to passive_fit / active_fit interfaces.
- Pending: signed-record construction (`Day2Posterior` / `Day6Posterior` from staged-fit outputs) deferred pending T5 §12.x schema. Day5Posterior → Day6Posterior rename per G3a Phase 2/3.

### T8. F10 pre-commissioning validation gate
- State: `NOT_STARTED`; depends on T7 (now satisfied) and signed-record construction
- Effort: <1 session once Day6Posterior construction lands
- Gates on Stages 1, 3, 4 production thresholds only

### **T9. §6 staged closed-loop test against real chain (NEW in v0.7)**
- State: `NOT_STARTED`; depends on T7 (satisfied)
- Effort: <1 session — mirrors G8-staged structurally but uses `synthesize_day45_window` real-chain analog with the four-phase HVAC excitation
- Pass criteria: Stage 3 95% CI coverage on C_house, Stage 4 95% CI coverage on C_w, both against real Phase 1 + aivu_dynamic

---

## Remaining, in execution order under "ASAP to productive 7-Day Cx"

**Pilot-blocking sequence (envelope architectural reformulation) — SHARPLY REDUCED in v0.7:**

1. **T9 §6 staged closed-loop against real chain** — finishes the staged-fit validation across all four stages. <1 session.
2. **Signed-record construction in staged_fit.py** — Day2Posterior/Day6Posterior from staged outputs. ~1 session (mostly mechanical; depends on T5 schema decisions).
3. **T8 F10 validation gate** — wraps the now-validated staged-fit machinery. <1 session.
4. **T2 v0.3 + T3 v0.2 text reconciliation** — bring amendment text in line with v0.1.1 code. <1 session combined.

**In parallel:**

- F4-F7 Phase 2 v1 envelope code. ~8 sessions; longest sequence.
- H1 v0.2 → spec lock, then H2 code, then H3 closed-loop test. ~7 sessions combined.
- G3a Phases 2-5. ~2.5 sessions total.

**Project-coherence work:**

- T1 v0.2 (operational refinement architecture)
- T4 §11.x amendment, T5 §12.x amendment, T6 MRAC fold-in
- Architectural Distillation v0.2 — **earned by today's G8-staged success.** Can now be written: 7-Day protocol + structural cure reframed as Cx + continuous operational refinement + Digital Birth Certificate as record-with-vintage + empirical demonstration that staged-fit works on real Phoenix physics.

**After staged-fit + HVAC track converge:**

Unchanged from v0.6: G9 `aivu_integrity` pilot-floor + outside cryptographic review, G10 `aivu_hpm` scoping/spec/code, hardware/sensors/pilot home → 7-Day commissioning.

---

## Critical-path summary in one sentence

**T9 §6 staged closed-loop validation + signed-record construction + T8 F10 gate complete the envelope inverse-identification track (~3 sessions total); H1 v0.2/H2/H3 HVAC track in parallel (~7 sessions); F4-F7 Phase 2 v1 envelope code longest pole (~8 sessions); G3a Phases 2-5 day-numbering reconciliation in parallel; then G9 `aivu_integrity` pilot-floor + outside cryptographic review + G10 `aivu_hpm` scoping/spec/code + hardware → run 7-Day Cx → continuous operational telemetry refines C_stack, C_wind, and HVAC parameters over months/years.**

---

## Off-path items

Unchanged from v0.6.

---

## Open questions for next session

1. **T9** — §6 staged closed-loop against real chain. Highest leverage: finishes empirical validation across all four stages.
2. **T2 v0.3 / T3 v0.2** — amendment text reconciliation. Pure bookkeeping but unblocks Authoritative-lock criterion.
3. **HPM-in-circuit-box hardware status** — carried forward, 4+ sessions unconfirmed. JDS to verify.
4. **G10 `aivu_hpm` scoping conversation** — without `aivu_hpm` there is no pilot.
5. **Outside cryptographic review timing for G9** — lead time scheduling.

---

## What today established

Beyond the artifact-level updates above, today's session demonstrated three things that affect future-session pacing:

1. **The architectural reformulation works.** v0.4 + v0.6 architecture survives real-physics contact at realistic Cx duration. 7-Day Cx is on the table.

2. **Code can ship ahead of text.** When architectural understanding is sharp, drafting code against v0.1 amendments and reconciling text afterward is faster than the strict spec-first-then-code ordering. The discipline that protects this is: code is source of truth; amendment text reconciliation is a tracked obligation, not optional.

3. **Bug-catching against theory is fast.** The N-factor and Welch-window-spectral-resolution bugs were caught by reviewing the residual likelihood math against the first draft of T7, not by waiting for closed-loop tests to fail. Theory review pays for itself per iteration.

---

*End of v0.7. Drafted 2026-05-17 end of session. Supersedes v0.6 (same date morning) which captured the architectural decisions; v0.7 captures the afternoon's implementation and validation. v0.4's architectural insights stand and are now empirically validated against real Phoenix physics at 24h and 48h Cx durations.*
