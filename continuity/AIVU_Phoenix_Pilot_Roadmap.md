# AIVU Phoenix Pilot Roadmap

**Current as of:** 2026-05-13 session close
**Maintained by:** Claude, updated each session

This is the working roadmap for the Phoenix pilot. Each workstream item carries a status flag and the session it closed in (if applicable). Closed items are retained for traceability, not for re-litigation.

---

## Workstream A — Spec drafting (CLOSED)

All items closed in the 2026-05-12 session.

- A1 — §§1-3 v0.1.1 — CLOSED 2026-05-12
- A2 — §5 v3.3 — CLOSED 2026-05-12
- A3 — §6 v3 — CLOSED 2026-05-12
- A4 — §7 v1 (Phase 2 recursive solver + First Law residual) — CLOSED 2026-05-13. Code implementation deferred to post-pilot unless homeowner agrees to ongoing-Cx at closing.
- A5 — §8 v1 (identifiability collapse detection) — CLOSED 2026-05-13
- A6 — §9 v1.1 (invariants consolidation) — CLOSED 2026-05-13
- A7 — §10 v1.1 (test plan) — CLOSED 2026-05-13
- A8 — §11 v1 (common utilities) — CLOSED 2026-05-13
- A9 — §12 v1 (signing chain) — CLOSED 2026-05-13

---

## Workstream B — `aivu_greybox` package code

### B1 — §4 + §5 + §6 implementation — CLOSED 2026-05-13

Production package shipped at `src/aivu_greybox/`:
- §4 Fan-Heat Consistency Check (`fan_heat.py`) — full end-to-end including INV-FH-2 window validation, η̂_distribution identification, pass/fail adjudication, signed FanHeatPass / FanHeatFail records via §12 stub.
- §5 Day-1-2 passive batch fit (`passive_fit.py`) — two-channel observation extraction, Laplace fit with 4 prior-perturbed restarts, finite-difference Hessian, §8 identifiability report builder, signed Day2Posterior with `ENVELOPE_HALF_INITIAL` attestation.
- §6 Day-4-5 active perturbation fit (`active_fit.py`) — phase-aware likelihood, Phase D held-out residual per §6.6, signed Day5Posterior with `ENVELOPE_HALF_FINAL` attestation.
- §11 utilities (`psychrometrics.py`, `defaults.py`) — Hyland-Wexler saturation, ASHRAE enthalpy, all §11.2 numerical defaults.
- §12 stub (`_signing_stub/`) — three function signatures matching the spec; INV-SIGN12-5 swap-target for `aivu_integrity` post-pilot.
- Forward-chain Protocol (`forward_chain.py`) — contract for `aivu_physics` + `aivu_dynamic` integration plus `StubForwardChain` analytic stand-in.
- EPW loader (`epw_loader.py`) — Phoenix AMY 2024 weather, 1-Hz interpolated slices.

Test suite at `tests/`: 69 tests passing against real Phoenix-July 2024 EPW weather. Coverage: psychrometric correctness, INV-FH-2 enforcement, closed-loop recovery (§5: full 6-param 95% CI; §6: 5-of-6 against stub physics), §12 signing chain end-to-end including correct AttestationMoment per phase.

### B2 — §10 closed-loop tests against real `aivu_corpus` — PENDING

Requires:
- `aivu_corpus` synthetic trajectory generation populated against real `aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2 (not the stub).
- Live integration of greybox forward-chain Protocol with the real packages (one-import swap).

When this lands, the strict per-parameter recovery test (currently relaxed to 5-of-6 against stub) becomes the production gate.

### B3 — Real-chain integration — PENDING

Replace `forward_chain.StubForwardChain` import sites with real `aivu_physics + aivu_dynamic` wrapper. Trivial swap; gated on those packages being shipped to this repository.

### B4 — Latent-side RealCycle fix in `aivu_dynamic` — PENDING

Out of greybox scope but in the larger code workstream. JDS lane or Claude lane TBD.

### B5 — ERV heat-recovery effectiveness — PENDING

`aivu_dynamic` extension. Out of greybox scope.

### B6 — §7 recursive-mode code — DEFERRED to post-pilot per A4

---

## Workstream C — HPM hardware

Per May 12 status. Half-blocked on D2 (SoC + Linux stack with Device Solutions).

---

## Workstream D — SoC / Linux integration

- D2 (SoC + Linux stack with Device Solutions) — JDS conversation, pending.

---

## Workstream E — Sensor stack

Per May 12 status. Hardware Spec v1.1 closed.

---

## Workstream F — BDT, Clearinghouse infrastructure

Per May 12 status.

---

## Workstream G — Documentation & investor materials

- G1, G2 — closed per May 12.
- G3 — OS doc v9.6 drafting — JDS lane.
- G4 — Architecture doc v3.0.1 fresh-eyes read — JDS lane.

---

## Insights queue

- Insight 8 (EcoBee correction) — revisit deferred.

---

## Next session entry points

1. B2 — closed-loop tests against real `aivu_corpus`. Requires `aivu_corpus` + real chain.
2. B3 — real-chain integration. Trivial once packages available.
3. §8 standalone module extraction — mechanical refactor of `build_identifiability_report`.
4. End-of-session bundle protocol confirmed (May 13).
