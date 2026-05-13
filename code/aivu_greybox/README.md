# aivu_greybox

Inverse identification of envelope and equipment parameters from commissioning-window telemetry.

This package implements the `aivu_greybox` v0.1 spec sections §§1-12. v0.1 status:

| Section | Status | Module |
|---|---|---|
| §4 Fan-Heat Consistency Check | **Implemented (B1 first cut)** | `fan_heat.py` |
| §5 Day-1-2 passive batch fit | Spec closed, code pending | `passive_fit.py` (planned) |
| §6 Day-4-5 active perturbation fit | Spec closed, code pending | `active_fit.py` (planned) |
| §7 Recursive-mode Phase 2 solver + First Law residual | Spec closed, code pending | `recursive.py` (planned) |
| §8 Identifiability collapse detection | Spec closed, code pending | `identifiability.py` (planned) |
| §9 Invariants consolidation | Spec only | — |
| §10 Test plan | Spec only | (drives the test suite) |
| §11 Common utilities | **Implemented** | `psychrometrics.py`, `defaults.py` |
| §12 Signing chain | **Stub implementation** | `_signing_stub/` (replaced post-pilot by `aivu_integrity`) |

## Install (development)

```bash
cd /path/to/aivu_greybox_code
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -v
```

## Architectural notes

- **SI internal, °F at the boundary only** per §11.3.1.
- **Six-parameter canonical set**: `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}` per §§1-3 v0.1.1.
- **Phoenix elevation P_atm**: 97,310 Pa as the per-home constant. v0.2 may pull live barometric pressure from the weather station.
- **Signing surface**: the package calls into `aivu_integrity` for record signing, log append, and threshold attestation. v0.1 uses an in-package stub (`_signing_stub/`) that matches the §12 function signatures so caller code does not change when the real `aivu_integrity` lands per INV-SIGN12-5.
- **Stub-attestation honesty (INV-SIGN12-4)**: all stub signatures carry the `is_stub_signature` / `post_pilot_replacement_required` flags; downstream consumers can distinguish stub from live attestation.

## What v0.1 §4 does

Fan-Heat Consistency Check (§4):

1. Reads a 30+ minute fan-only telemetry window (12 supply terminal SHT35s + 1 return plenum SHT35 + 12 per-terminal Venturi mass-flow + fan electrical).
2. Validates the window per INV-FH-2 (compressor off, heat strip off, OAD closed, moisture stability, spatial uniformity). Rejects non-conforming windows.
3. Identifies η̂_distribution from the time-averaged enthalpy rise vs. fan electrical input.
4. Adjudicates pass/fail against ε_FH (4% relative residual) and [η_min, η_max] = [0.85, 0.96].
5. Emits a signed FanHeatPass or FanHeatFail record per §4.5; logged via the stub `aivu_integrity` interface.

See `tests/test_fan_heat.py` for closed-loop recovery validation, INV-FH-2 rejection cases, and §12 signing-chain integration.
