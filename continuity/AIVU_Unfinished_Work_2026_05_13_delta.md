# AIVU Unfinished Work — delta from 2026-05-13 session

This file captures items that moved into or out of the unfinished-work queue during the 2026-05-13 session. To be merged into the canonical Unfinished Work doc at next maintenance pass.

---

## Items closed this session

| Item | Closed how |
|---|---|
| §§7-12 v0.1 spec drafting (A4-A9) | Spec text shipped May 12; reviewed and accepted this session |
| B1 — §4 + §5 + §6 code implementation | Production code + 69 tests passing against real Phoenix EPW |
| EPW test-fixture decision | Real Phoenix AMY 2024 file integrated, replacing synthetic diurnal sine |
| Forward-chain abstraction | `ForwardChain` Protocol defined; `StubForwardChain` ships; real-chain integration is a one-import swap |
| §12 signing-chain stub | `_signing_stub/` module shipped with INV-SIGN12-5 swap-target discipline |
| §8 logic | Embedded in `build_identifiability_report` (`passive_fit.py`); standalone module pending but mechanical |

---

## Items added to unfinished work

| Item | Origin | Priority |
|---|---|---|
| B2 — Closed-loop tests against real `aivu_corpus` | Needed once real chain available | High once unblocked |
| B3 — Real-chain integration (swap stub → real `aivu_physics + aivu_dynamic`) | Trivial one-import change | Gated on those packages |
| §8 standalone module extraction | Refactor opportunity | Low; logic already correct in place |
| Production thresholds vs test thresholds — written guidance | The `mode_agreement_fraction` and tightness gates differ between production and stub-physics tests; this discipline should be a §9 cross-cutting invariant addition in v0.2 | Low; current code is correct, doc gap |
| BASF spray-foam decomposition (v0.2 candidate) | Discussed this session; gated on BASF being a near-term Clearinghouse partner | Conditional |

---

## Items still open from prior sessions (status unchanged)

- D2 (SoC + Linux stack with Device Solutions) — JDS conversation
- G3 (OS doc v9.6 drafting) — JDS lane
- G4 (Architecture doc v3.0.1 fresh-eyes read) — JDS lane
- Insight 8 revisit re: EcoBee correction — deferred
- B4 (latent-side RealCycle fix in `aivu_dynamic`) — owner TBD
- B5 (ERV heat-recovery effectiveness in `aivu_dynamic`) — owner TBD

---

## Working-style note added to Working Preferences (informal, to merge at next maintenance pass)

JDS reframing from this session: "Your decision was fine; you got the work done; now we can have another go at it." Useful operating principle: Claude can ship "working but not optimal" without treating the next-iteration improvement as evidence of an initial mistake. The first cut establishes the structural correctness; refinement comes after, when the right next-step is visible. This is more productive than gold-plating up front.

Anti-pattern this discourages: Claude proactively warning about all known limitations before the first working cut exists, which delays the moment when JDS can actually see the system and direct the next iteration.

Pattern this encourages: ship the working version; surface limitations honestly in the result summary; let JDS direct what to improve next.
