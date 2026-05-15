# `aivu_greybox` §11.2 Spec Amendment — Canonical Parameter Set Revision

**Amendment ID:** GREYBOX-§11.2-AMEND-2026-05-15
**Drafted:** 2026-05-15 (session with JDS)
**Status:** Authoritative — landed in code 2026-05-15.

**Locked in code:** Pass A (commit `64102b6`) ported the seven-parameter canonical set into `defaults.py`, `forward_chain.py`, `passive_fit_types.py`, and `passive_fit.py`. Pass B (commit `dd31fa3`) updated `active_fit.py` and the test fixtures; all 69 tests pass against the new set. The Operational addendum was updated in the same Pass B commit to capture the canonical python/pytest invocation.
**Supersedes:** §11.2 canonical six-parameter set as encoded in
`defaults.CANONICAL_PARAMETER_NAMES` v0.1.

---

## Why this amendment exists

The original six-parameter canonical set was specified before the
`ceiling_coupling_factor` parameter's physical role and the real-chain
adapter's parameter-translation requirements had been worked through.
Two of the original six parameters do not survive contact with the
physics:

- `R_eff` as a single whole-envelope resistance conflates two
  physically independent degradation modes (opaque-envelope insulation
  vs. fenestration seal/frame). A single multiplier on aggregate U·A
  cannot represent a home with sagging batt insulation and intact
  windows differently from a home with failing window seals and intact
  walls. The §5 fit cannot identify what doesn't exist as a single
  scalar.

- `cfm50` carries forward the HERS blower-door measurement convention
  into AIVU's fit, which is exactly the convention AIVU was designed to
  displace. Blower-door tests pressurize the house to 50 Pa — a
  pressure differential the building never experiences in operation —
  and convert to operational infiltration via a √(ΔP/50) scaling that
  ignores stack and wind decomposition. AIVU's calibrated HVAC and
  supply-tail Venturi can observe infiltration directly under operating
  conditions; the fit should produce the operational infiltration
  model, not a cfm50 proxy.

A third parameter, `F_slab`, is physically determined at construction
and calculable from gbXML + Manual J + climate zone. Its thermal impact
under operating conditions varies (soil moisture, slab thermal mass
lag, effective ground temperature) but the variability is small and
better captured by Phase 2 drift monitoring against a
construction-document baseline than by per-home inverse identification.
It does not belong in greybox's canonical fit set; it belongs in
`HomeStaticContext` alongside `c_attic_j_per_k`.

This amendment makes those three corrections.

---

## The new canonical set

Seven parameters, in canonical order:

```
CANONICAL_PARAMETER_NAMES = (
    "R_opaque",
    "U_fenestration",
    "C_house",
    "C_stack",
    "C_wind",
    "C_w",
    "ceiling_coupling_factor",
)
```

### `R_opaque` (dimensionless multiplier)

**Physical meaning.** Multiplier on the opaque-envelope conductive
heat path: opaque walls (above-grade), ceiling plane (where applicable
per variant), opaque doors. Prior mean centered at 1.0; the as-built
deviation from variant nameplate is what the fit measures.

**Why dimensionless multiplier rather than absolute R-value.** The
variant's nameplate U-values represent the production builder's
specification. Greybox is measuring deviation from specification — the
question is "did this home get built to the spec it was sold under,"
not "what is the absolute R-value." A multiplier of 0.85 means "this
home's opaque envelope conducts heat 15% more readily than nameplate";
that statement is meaningful to the builder, the warranty insurer, and
the buyer. An absolute R-value is meaningful only in the context of
what it was supposed to be.

**Coupling to forward chain.** The adapter applies `R_opaque` as a
multiplier on the aggregate opaque-element U·A contribution to
`compute_loads`'s envelope sensible stream. Implementation details
belong in the adapter, not here.

**Identifiability character.** Well-conditioned in §5 passive Days 1-2
(long thermal time constants are mass-and-conduction dominated and the
opaque path is the bulk of the conduction). Tightens further in §6
active perturbation.

### `U_fenestration` (dimensionless multiplier)

**Physical meaning.** Multiplier on the conductive heat path through
fenestration (windows, sliding glass doors). Captures glazing seal
degradation, frame conduction deviation from NFRC nameplate, and
air infiltration around the rough opening. Prior mean centered at
1.0.

**Why separate from `R_opaque`.** Opaque-envelope degradation and
fenestration degradation are physically independent — different
materials, different failure modes, different timescales. A single
multiplier across both elements forces them to move together when they
do not.

**Coupling to forward chain.** The adapter applies `U_fenestration` as
a multiplier on the fenestration U·A contribution to `compute_loads`.
Window solar gain is unaffected (governed by SHGC, not U).

**Identifiability character.** Better identified in §6 active
perturbation than in §5 passive, because solar gain through windows is
a strong, well-characterized excitation channel disproportionately
loaded on fenestration. §5 may emit a "loose" or "degraded" tightness
state on this parameter on cloudy Days 1-2; that is expected and not a
failure mode.

### `C_house` (J/K, unchanged from v0.1)

Whole-house lumped sensible thermal capacitance. Unchanged from the
v0.1 six-parameter set. Forward-chain entry is `run_dynamic`'s
`c_eff_per_ft2_override` after SI→imperial conversion (J/K →
BTU/(°F·ft²), divided by floor area).

### `C_stack` and `C_wind` (operational-infiltration coefficients)

**Physical meaning.** Operational envelope infiltration is modeled as:

    Q_inf = C_stack · |T_in − T_out|^n  +  C_wind · V_wind^m

with exponents `n = 0.65` and `m = 1.0` fixed at the ASHRAE 152 /
Sherman-Grimsrud values. `C_stack` and `C_wind` are per-home fitted
coefficients in units that make the heat flow come out in W. The two
coefficients together replace the v0.1 `cfm50` parameter and
displace the HERS blower-door measurement convention.

**Forward-chain entry path — interim.** Phase 1's `infiltration.py`
v4.0 currently consumes cfm50 as input via the variant's nameplate
infiltration value, not (C_stack, C_wind). Until the Phase 1
operational-infiltration amendment ships (tracked as a separate
workstream, see "Phase 1 amendment dependency" below), the greybox fit
identifies `C_stack` and `C_wind` but the adapter feeds Phase 1 a
*derived equivalent cfm50* computed from the fitted coefficients at
the §5 fit's mean operating conditions. This is the interim. It is
honest at the operating point but incurs predictable bias on
days/hours far from that operating point.

**Retirement gate for the interim.** When the Phase 1
operational-infiltration amendment ships, the adapter switches to
passing `(C_stack, C_wind)` directly through to `infiltration.py`
and the derived-cfm50 path retires. The greybox §5 / §6 fits are
unchanged; only the adapter's parameter-translation path changes. The
swap site lives in the adapter and is named explicitly so the
retirement is mechanical.

**Identifiability character.** `C_stack` is well-identified at high
indoor-outdoor ΔT (winter or Phoenix summer at night). `C_wind` needs
wind variation across the fit window to be identified; Phoenix is
relatively low-wind, so `C_wind` is expected to be the loosest of the
two and the §8 identifiability report should be checked carefully.

### `C_w` (latent capacitance, unchanged from v0.1)

Whole-house lumped latent moisture capacitance. Unchanged from v0.1.
Forward-chain entry is `run_dynamic`'s `kappa_buffer_override`.

### `ceiling_coupling_factor` (dimensionless multiplier, unchanged from v0.1)

Multiplier on the total conductance between attic air and the
conditioned space, capturing as-built coupling paths nameplate drywall
U·A does not see (recessed cans, hatches, top-plate gaps, duct
radiation, can-light bypass). Settled in the 2026-05-15 session.

Forward-chain entry: the real-chain adapter integrates a dynamic
attic state with this multiplier applied to the ceiling-conduction
path; attic thermal capacitance enters as a known-from-construction
value in `HomeStaticContext` (`c_attic_j_per_k`), not fitted.

---

## What leaves the canonical set

### `R_eff`

Replaced by `R_opaque` and `U_fenestration` per the rationale above.
Code that referenced `R_eff` in v0.1 (records dataclass, prior,
forward-chain calls, identifiability report) is updated to reference
both successors.

### `cfm50`

Replaced by `(C_stack, C_wind)` per the rationale above. Interim
adapter behavior preserves a forward-chain cfm50 path; the canonical
parameter the greybox FIT identifies is the pair, not cfm50.

### `F_slab`

Moves to `HomeStaticContext` as a known-from-construction value,
alongside `c_attic_j_per_k`. Calculated from gbXML perimeter, slab
edge insulation R-value, and Manual J climate-zone F-factor table.
Thermal-impact verification under operating conditions becomes a Phase
2 drift-monitoring concern, not a Phase 1 commissioning fit concern.

---

## Affected modules and surface area

In `aivu_greybox`:

- `defaults.CANONICAL_PARAMETER_NAMES` — replace tuple with the new
  seven-element ordering.
- `defaults.NUM_CANONICAL_PARAMETERS` — recomputed.
- `defaults.ID8_*` thresholds — unchanged; the §8 diagnostics are
  parameter-agnostic.
- `defaults` per-parameter expected-tightness table (currently inline
  in `passive_fit.py::build_identifiability_report`) — replaced with
  the seven new entries. Initial values per the table below; pilot
  data will tighten in v0.2.
- `passive_fit_types.Prior6D` → rename to `Prior7D`. Mean shape
  changes from (6,) to (7,); covariance from (6,6) to (7,7). Provenance
  fields unchanged.
- `passive_fit_types.make_acca_manual_j_fallback_prior` — return a
  `Prior7D` with seven means and seven sigmas. Provisional values
  per the table below.
- `passive_fit.run_passive_batch_fit` — signature unchanged (it takes
  a Prior, telemetry window, forward chain, context); internal
  parameter handling automatically scales with `NUM_CANONICAL_PARAMETERS`.
- `passive_fit.run_laplace_fit` — `positive_floors` dict updated to
  reference the new parameter names. Bounds and optimizer config
  unchanged in structure.
- `passive_fit.build_identifiability_report` — the inline
  `expected_tightness_pct` dict expands to seven entries.
- `forward_chain.HomeStaticContext` — add `f_slab_btuh_per_ft_f` field
  (or SI-equivalent W/(m·K)) for the known-from-construction F-factor.
  No other schema change at the contract level.
- `records.PosteriorCommon.parameter_names` and `posterior_mean` /
  `posterior_covariance` tuple shapes follow `NUM_CANONICAL_PARAMETERS`.

In `aivu_physics` (tracked as a separate workstream — see "Phase 1
amendment dependency" below):

- `infiltration.py` v4.0 → v4.1: add an operational-infiltration entry
  point that takes `(C_stack, C_wind, T_in_F, T_out_F, V_wind_mph)`
  and returns infiltration heat flow + air mass flow directly,
  bypassing cfm50. Existing cfm50-based path remains for backward
  compatibility with code that hasn't migrated.

In tests:

- The 69 currently-passing greybox tests need parameter-count updates
  in their fixtures. The closed-loop discipline against
  `StubForwardChain` and against `aivu_corpus` synthetic trajectories
  is unchanged in structure; the fixtures supply seven-parameter θ
  vectors instead of six.

---

## Provisional prior values for the ACCA Manual J fallback

These are the starting estimates for the first pilot. Per §5.4
path-preference, BDT-derived priors will displace these as the cohort
grows. Phoenix CZ 2B single-family, 1800-sqft-class, two-stage AC,
foam-deck attic.

| Parameter                  | Prior mean                | Prior σ                | Provenance / notes                                                                 |
|----------------------------|---------------------------|------------------------|------------------------------------------------------------------------------------|
| `R_opaque`                 | 1.0                       | 0.15                   | Variant nameplate as starting point; ±15% covers expected build-quality range.     |
| `U_fenestration`           | 1.0                       | 0.10                   | NFRC ratings are more reliable than wall execution; tighter prior justified.       |
| `C_house`                  | 5.0 × 10⁶ J/K             | 7.5 × 10⁵              | Unchanged from v0.1.                                                               |
| `C_stack`                  | TBD (operational equiv.)  | wide                   | Set so that derived-cfm50 at design ΔT matches nameplate cfm50 ± 50%.              |
| `C_wind`                   | TBD (operational equiv.)  | wide                   | Set so that derived-cfm50 at design wind matches nameplate cfm50 ± 50%.            |
| `C_w`                      | 50                        | 15                     | Unchanged from v0.1.                                                               |
| `ceiling_coupling_factor`  | 0.75                      | 0.25                   | Unchanged from v0.1 (AOT §3.2 placeholder).                                        |

The two C_stack / C_wind values need a translation from "nameplate
cfm50 of ~1800 at Phoenix design conditions" into the operational
coefficient pair. That translation is mechanical (apply the
Sherman-Grimsrud formula at design T_in − T_out and design wind, solve
for the coefficients consistent with the nameplate cfm50 at 50 Pa).
The derivation belongs in §11.2's amendment companion document; values
get pinned once the math is walked through.

---

## Expected-tightness table (replaces the v0.1 inline dict)

Per-parameter posterior σ/μ that the §8 identifiability report
classifies as "within" (≤ value), "loose" (≤ 2×), or "degraded"
(> 2×). Provisional values; pilot data will tighten in v0.2.

| Parameter                  | Expected σ_post / μ_post |
|----------------------------|--------------------------|
| `R_opaque`                 | 0.05                     |
| `U_fenestration`           | 0.07                     |
| `C_house`                  | 0.05                     |
| `C_stack`                  | 0.20                     |
| `C_wind`                   | 0.35                     |
| `C_w`                      | 0.25                     |
| `ceiling_coupling_factor`  | 0.15                     |

`C_wind` carries the loosest expected tightness, reflecting Phoenix's
low-and-relatively-uniform wind regime. If a pilot site has more wind
variability, the table is climate-zone-conditional in v0.2.

---

## Phase 1 amendment dependency

The `(C_stack, C_wind)` parameters' clean forward-chain path requires
`aivu_physics/infiltration.py` to expose an operational-infiltration
entry point. Until that ships, the real-chain adapter translates
`(C_stack, C_wind)` into a derived-equivalent cfm50 at the §5 fit's
mean operating conditions and feeds Phase 1 through its existing
cfm50 path. This is the interim. It is honest at the fit's operating
point but biased far from it.

The Phase 1 amendment is tracked as a separate workstream in the
dependency map (sister to G7, not on G7's critical path). When it
ships:

1. The adapter's derived-cfm50 path retires.
2. `(C_stack, C_wind)` flow directly into `infiltration.py`'s new
   entry point.
3. The greybox §5 fit's posterior on `(C_stack, C_wind)` becomes
   directly meaningful at every operating point in the §6
   active-perturbation window, not just the §5 mean.
4. No greybox spec change is required; only the adapter changes.

The interim path's bias at high-ΔT or high-wind moments is the cost of
unblocking G7. It is named in the §11.2 spec rather than hidden in
adapter code so future Claude sessions can see exactly what
limitation they're inheriting and when it retires.

---

## What does not change

- §5 Bayesian Laplace machinery (algorithm class, restarts,
  convergence diagnostics, mode-agreement check, Hessian positive-
  definiteness check, finite-difference Hessian).
- §6 active-perturbation four-phase protocol (Phase A drive, Phase B
  decay, Phase C reverse drive, Phase D held-out validation).
- §7 recursive solver structure (still deferred to post-pilot per
  Roadmap A4).
- §8 identifiability collapse detection logic (Diagnostics 1-4 against
  posterior; the diagnostics are parameter-agnostic and scale with
  `NUM_CANONICAL_PARAMETERS`).
- §12 signing interface and call surface.
- The two-channel observation model (attic channel from warmup terminal
  probes; main channel from post-warmup return plenum) — the
  observation model is unchanged; what gets fitted against the
  observations is what this amendment changes.

---

## Sequencing relative to G7

1. **This amendment locks first.** §11.2 canonical set, prior values,
   expected-tightness table, the interim Phase-1 path with its named
   retirement gate.
2. **Phase 1 operational-infiltration amendment** flagged as a
   separate workstream. Not on G7's path.
3. **G7 adapter ships against the new seven-parameter set** with the
   interim cfm50 translation in place.
4. **Greybox §§4-8 tests** updated to the new parameter count.
5. **G8 — §5 closed-loop test against the real chain** at the new
   parameter set. Earliest "stuff works" signal in the project.

Steps 3, 4, and 5 are sequential. Step 2 runs in parallel and retires
the interim when ready.

---

*End of draft amendment. Awaiting JDS lock before §11.2 in `defaults.py` is rewritten and the prior, records, and identifiability-report code follow.*
