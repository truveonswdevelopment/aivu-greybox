# aivu_hvac_greybox

HVAC inverse-identification for the AIVU pilot. Sister package to `aivu_greybox` (envelope inverse-identification).

## Scope

**v0.1.0 (first cut — Pass A closes here):**
- `bi_quadratic_fit.py` — joint Laplace fit over the 10 free coefficients of D17_pilot (delivered capacity) and D20_pilot (EER), with AHRI 95°F/67°F anchor enforced.
- `records.py` — `Day4Posterior` with §6-consumption interface (`evaluate_q_delivered`, `evaluate_eer`).
- Pass A closed-loop recovery test against F5 (aivu_physics_phase2).

**Deferred to subsequent passes:**
- `sweep_orchestrator.py` (Day 3-4 state machine; drives HPM via Ecobee pass-through)
- `cross_validation.py` (Day 3 vs Day 4 mode-agreement check per H1 v0.2 §4.2)
- `quality_gates.py` (production-threshold identifiability machinery)
- `forward_chain.py` as a separate module (currently F5 is imported directly)
- Pass B real-chain integration (against full Phase 2 v1 code)
- Pass E real-chain at Cx duration (analog of envelope greybox G8-staged test)
- Cryptographic signing via `aivu_integrity` (deferred per session decision 2026-05-18)

## Spec

`AIVU_HVAC_Greybox_Spec_v0_2.md` (drafted 2026-05-18; in cold-start/Temp folder pending session-close commit).

## Install

```bash
cd ~/aivu-greybox/code/aivu_hvac_greybox
pip install -e .
```

Note: requires `aivu_physics_phase2` to be installed first (also editable from `~/aivu/code/phase2/aivu_physics_phase2`).

## Test

```bash
pytest tests/ -v
```
