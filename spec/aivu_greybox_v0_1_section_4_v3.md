# aivu_greybox v0.1 — §4: Fan-Heat Consistency Check

**Status:** Third-pass draft, 2026-05-11. Supersedes v2 of the same date. Material changes from v2: terminal-side probe geometry (replaces plenum-side); Option B framing — Fan-Heat *identifies* `η_distribution` rather than consuming it as a prior; Sensirion-specific sensor stack; tightened numerical defaults derived against the actual instrument propagation.

---

## 4.1 Position among the four self-tests

§1.2 names four self-tests and quality gates that establish whether posteriors produced by this package are trustworthy: the Fan-Heat Consistency Check, First Law residual verification, identifiability collapse detection, and posterior tightness criteria. Each gates something specific. Fan-Heat is the only one that runs *before* the forward-chain likelihood is exercised; the other three operate on or after the likelihood. The remaining three self-tests are specified in their own sections: First Law residual verification in §7, identifiability collapse detection in §8, posterior tightness in §8.

Delta 4 of the Editorial Addendum (April 27, 2026) elevated Fan-Heat from a recommended commissioning check to a required first-class self-test. The remainder of §4 specifies the math, the data interface, the pass/fail semantics, and the invariants any implementation must satisfy.

## 4.2 What Fan-Heat does

Fan-Heat performs two coupled functions:

**(i) Validates the end-to-end delivery instrument stack** — the per-terminal Sensirion T/RH probes, the per-terminal Sensirion SDP8xx Venturi flow stations at the supply registers, and the Eaton-breaker electrical measurement on the air handler — as a self-consistent measurement system, before that instrument is used to interrogate the envelope during the remainder of commissioning.

**(ii) Identifies `η_distribution`** — the calibration coefficient relating fan electrical input to delivered enthalpy at the terminals — as a per-home quantity, establishing the Day-1 prior that §6 active-perturbation refinement subsequently jointly identifies along with envelope and equipment parameters.

Both functions emerge from the same energy balance evaluated on the same Day-1 fan-only telemetry window. The check passes when (a) the post-identification residual falls below tolerance *and* (b) the identified `η_distribution` falls within physical bounds for the home's configuration.

### Why probes are at the terminals, not the plenum

The supply-side T/RH probes sit at the terminals — at the supply registers where conditioned air enters the occupied space — rather than at the supply plenum near the air handler. Three architectural reasons, in order of load-bearing weight:

**Measurement validity near saturation.** Air leaving an active cooling coil exits at or near 100% RH along the wet-bulb line; that is how a cooling coil operates. Capacitive RH sensors, including the Sensirion SHT35, are not calibrated to read accurately at saturation: water condenses onto the polymer sensing element, the reading saturates at or above 100% and exhibits multi-minute hysteresis as the element dries back; sensor self-heating biases the reading low in a way that depends on local airflow and cannot be calibrated out. A probe immediately downstream of the coil sits in this regime continuously during all cooling operation — which is the operating mode Days 3-5 specifically exercise. Probes at the plenum would return structurally invalid readings during the very protocol windows that depend on supply enthalpy as a load-bearing input. Probes at the terminals see the air after duct-conduction reheat raises sensible temperature by 1-2°C and pulls RH off the saturation line into the 85-90% range, well within the SHT35 calibrated envelope.

**Stratification from refrigerant distribution.** TXV-fed coil circuits produce non-uniform face temperature and humidity that persist for several diameters downstream. RH gradient across the coil face is sharper than the sensible gradient. A single plenum probe samples whichever stratum its sensing element happens to occupy. Flex-duct turbulence over the supply-duct run mixes the stratification out by the time air reaches the terminals.

**What the occupant actually receives.** The supply enthalpy that matters for indoor climate control, for envelope load reconciliation, and for the dual-track commissioning architecture is the enthalpy *delivered to the conditioned space*, not the enthalpy at the AHU output. The terminal placement measures the quantity that subsequently appears as the supply-side boundary condition in §5 and §6 fits.

### What `η_distribution` represents

`η_distribution` is the calibration coefficient of the end-to-end delivery instrument — the AHU plus distribution plus terminal probe stack, taken as a unified system. It is the fraction of fan electrical input that appears as enthalpy rise *at the terminals* relative to the return. Duct conduction to the conditioned attic is therefore not a parasitic loss to back out; it is *intrinsic* to the instrument's calibration. A home with longer or less-insulated supply ducts has a different `η_distribution` than a home with shorter or better-insulated ones, and Fan-Heat is what pins this value for each specific home.

The dual-track commissioning architecture treats the HVAC system as the calibrated measurement instrument that probes the envelope during Days 3-5. Fan-Heat establishes the Day-1 anchor on that instrument's calibration coefficient, which §6 refines under active excitation jointly with envelope and equipment parameters. The Day-3 (Capacity, EER) operating-point map is constructed against this same calibrated stack — meaning the map is automatically a *delivered-capacity* map (capacity reaching the conditioned space at the terminals), and `aivu_physics` Phase 2 Layer 3 (duct delivery) inherits the delivery instrument as Fan-Heat established it rather than requiring separate reconciliation.

## 4.3 The governing equation

Under Day-1 fan-only operation — outside-air dampers closed, no compressor, no heat strip, no auxiliary heat — the only thermal source in the air-handling system is fan motor heat dissipation. Energy balance on the delivery system between the return and the terminals:

```
Σ_{i=1}^{N_t} ṁ_air,i · (h_terminal,i − h_return)  =  η_distribution · P_fan_electrical
```

Where:

- `N_t` is the number of supply terminals (12 for the Beazer Phoenix pilot home);
- `ṁ_air,i` is air mass flow rate at terminal `i` [kg/s], measured by the Sensirion SDP8xx Venturi station at that terminal, calibrated to the duct diameter's expected CFM range;
- `h_terminal,i` is moist-air specific enthalpy at terminal `i` [kJ/kg dry air], computed from Sensirion SHT35 T and RH readings;
- `h_return` is moist-air specific enthalpy at the return, computed analogously;
- `P_fan_electrical` is electrical power input to the air-handler fan motor [kW], measured at the Eaton breaker;
- `η_distribution` is the per-home delivery calibration coefficient identified by this check.

Moist-air specific enthalpy uses the ASHRAE Fundamentals relation `h(T, W) = 1.006·T + W·(2501 + 1.86·T)` with `T` in °C and `W` the humidity ratio [kg water / kg dry air]. `W` is computed from measured `T` and `RH` via Hyland-Wexler 1983 saturation pressure, partial pressure from RH, humidity ratio from partial pressures. Psychrometric utilities are referenced from §11.

Under fan-only conditions with no active conditioning and a sufficiently long warmup, terminal enthalpies are approximately uniform across `i` (no spatial structure inherited from coil-side processes). The check therefore operates in a low-spatial-variation regime that maximizes the spatial-averaging benefit of the 12-terminal probe array. Spatial uniformity is itself one of the quality checks in §4.4.

Fan-Heat is **not** a forward-chain likelihood call. It does not invoke `aivu_dynamic.dynamic.run(...)`. It is a pure energy-balance identification on instantaneous telemetry, independent of envelope physics, equipment physics, and time-domain dynamics. This is why it runs *before* the batch fit consumes its first window of Day-1-2 data.

## 4.4 Inputs from Day-1 fan-only telemetry

Fan-Heat consumes a Day-1 fan-only telemetry window of length `τ_FH = 30 minutes`, sampled at 1 Hz, after a `τ_warmup = 15 minute` warmup window allowing cabinet thermal mass and short-duct surfaces to reach steady state. Both timings are configuration parameters pinned at the values shown for the Phoenix-pilot air-handler configuration. Channels are:

| Channel | Source | Symbol | Cardinality |
|---|---|---|---|
| Terminal `i` dry-bulb temperature | Sensirion SHT35, terminal `i` | `T_terminal,i(t)` | `N_t = 12` |
| Terminal `i` relative humidity | Sensirion SHT35, terminal `i` | `RH_terminal,i(t)` | `N_t = 12` |
| Terminal `i` air mass flow | Sensirion SDP8xx Venturi, terminal `i` | `ṁ_air,i(t)` | `N_t = 12` |
| Return dry-bulb temperature | Sensirion SHT35, return | `T_return(t)` | 1 |
| Return relative humidity | Sensirion SHT35, return | `RH_return(t)` | 1 |
| Air-handler fan electrical input | Eaton breaker current × voltage | `P_fan(t)` | 1 |
| Outside-air damper position | Damper feedback | `δ_OAD(t)` | 1 |

The window is rejected and re-collected if any of the following hold for the `τ_FH` window:

- `δ_OAD ≠ 0` at any sample (the window must be fan-only with respect to outdoor air);
- Any compressor, heat-strip, or auxiliary-heat electrical channel reads above its standby threshold;
- Any channel returns NaN, out-of-range, or stuck-value for more than 5 consecutive samples;
- Return-side humidity ratio drifts by more than `ΔW_max = 0.0002 kg/kg` over the window (no uncontrolled moisture source);
- Spatial standard deviation of `h_terminal,i` across the 12 terminals exceeds `σ_spatial_max = 0.5 kJ/kg dry air` (terminals not in agreement implies either a mixing problem, an active conditioning leakage, or a sensor problem — none acceptable for Fan-Heat).

The moisture-stability bound and the spatial-uniformity bound together license treating Fan-Heat as a low-variability identification problem. Fan-only operation does not change moisture in the airstream and produces a uniform delivered enthalpy across terminals; departures from either condition disqualify the window.

## 4.5 Identification and pass/fail semantics

Fan-Heat identifies `η_distribution` and a residual `R_FH` from the time-averaged energy balance. Let:

```
LHS_avg  =  ⟨ Σ_i ṁ_air,i(t) · [h_terminal,i(t) − h_return(t)] ⟩
RHS_unit =  ⟨ P_fan(t) ⟩
```

Where `⟨·⟩` denotes the `τ_FH`-window time average. Then `η_distribution` is identified as:

```
η̂_distribution  =  LHS_avg / RHS_unit
```

And the post-identification residual `R_FH` is computed as the time-resolved RMS departure from the identified balance:

```
R_FH  =  rms_t [ Σ_i ṁ_air,i(t) · (h_terminal,i(t) − h_return(t))  −  η̂_distribution · P_fan(t) ]
```

normalized by `η̂_distribution · ⟨P_fan⟩`. The residual measures how well the identified coefficient explains the *time-resolved* energy balance, not the time-averaged one (which is identically zero by construction of `η̂_distribution`).

The check **passes** if both of the following hold:

**(i) Residual tolerance:**

```
R_FH / (η̂_distribution · ⟨P_fan⟩)  ≤  ε_FH
```

with default `ε_FH = 4%`. This is derived in §11 from RSS propagation of independent uncertainties across the Sensirion sensor stack, the per-terminal Venturi calibration, and the Eaton-breaker electrical accuracy, accounting for the √12 spatial-averaging benefit on independent noise terms and the correlated nature of systematic contributions. The 1-σ floor is ~3.6%; the threshold sits one quarter-sigma above. Tightening below 4% would put the check below its noise floor and produce spurious failures under conditions where all sensors are within spec.

**(ii) Physical-bound check on identified `η_distribution`:**

```
η_min  ≤  η̂_distribution  ≤  η_max
```

with defaults `η_min = 0.85` and `η_max = 0.96` for the Phoenix-pilot delivery geometry (AHU in conditioned mechanical room, supply plenum reaching into spray-foam-insulated conditioned attic, flex-duct runs to 12 terminals). Identified values outside this band indicate the identification has converged on a physically implausible value, which under fan-only conditions with the moisture-stability and spatial-uniformity gates passing typically points to a calibration error in either the per-terminal Venturi array or the electrical measurement that the residual alone does not catch.

**On pass:** the package emits a `FanHeatPass` record containing:

- Window start and end timestamps;
- Per-channel telemetry hash references (so the underlying 1 Hz packets are addressable via inclusion proof);
- Computed `LHS_avg`, `⟨P_fan⟩`, identified `η̂_distribution`, residual `R_FH`, and the relative residual;
- Tolerances used: `ε_FH`, `η_min`, `η_max`;
- Pass flag;
- `aivu_integrity` inclusion proof for the record itself.

Per §1.3's cryptographic-infrastructure non-goal, signing and commitment of this record is performed by calling into `aivu_integrity`'s API: the record is signed with the HPM per-packet signing key, appended to the local append-only log, and committed via MMR with an inclusion proof returned to the caller. The identified `η̂_distribution` and its propagated uncertainty become the Day-1 prior for §6 active-perturbation joint refinement, where envelope parameters, equipment parameters, and `η_distribution` are co-identified under HVAC excitation.

Existence of a valid `FanHeatPass` record for the home is a prerequisite for §5's passive-fit procedure to consume Day-1-2 telemetry (see INV-FH-1 below).

**On fail:** the package emits a `FanHeatFail` record with the same fields plus a failure flag distinguishing the two failure modes (residual exceeds `ε_FH`; identified `η̂_distribution` outside `[η_min, η_max]`; both). The signed residual and identified `η̂_distribution` are preserved. **No batch fit runs.** The package halts the commissioning pipeline and surfaces the failure to the operational layer for technician action. The procedure by which a technician disambiguates the failure source and re-establishes a valid Fan-Heat window is operational protocol and lives in the field-deployable 5-Day commissioning protocol document, not in this package specification.

## 4.6 Invariants

The Fan-Heat Consistency Check has four invariants any implementation must satisfy. These are part of the §9 invariant set referenced in §1.4.

**INV-FH-1 — No batch fit on Fan-Heat-Fail.** If the most recent Fan-Heat record for a home is a `FanHeatFail`, or if no `FanHeatPass` record exists, §5's passive-fit procedure and §6's active-perturbation-fit procedure MUST refuse to consume telemetry from this home's commissioning window. Implementations MUST raise an error if called in this state. The check is meaningful only if its failure has consequences; this invariant is what makes it consequential.

**INV-FH-2 — The window must be a fan-only window with spatial uniformity.** The damper-closed, compressor-off, heat-strip-off, moisture-stability, and spatial-uniformity constraints in §4.4 are not optional. A window violating any of them is not a Fan-Heat window; computing identification on such a window and emitting either a Pass or Fail record on the basis of that computation is a protocol violation that voids the resulting record. Implementations MUST reject non-conforming windows rather than compute on them.

**INV-FH-3 — Records are complete and externally verifiable.** Every `FanHeatPass` and `FanHeatFail` record MUST contain the full set of fields in §4.5, committed via the `aivu_integrity` API. An external verifier holding the HPM's public key, the relevant 1 Hz telemetry packets (served on demand per §2.5), and the MMR inclusion proofs MUST be able to re-derive `η̂_distribution` and `R_FH` and re-check both pass conditions independently. No part of the check may rely on intermediate state outside the record.

**INV-FH-4 — `η_distribution` identified by Fan-Heat is the Day-1 prior for §6, not the final value.** The identified `η̂_distribution` and its uncertainty established at Day-1 MUST be consumed by §6 as the prior for active-perturbation joint refinement, *not* treated as a fixed parameter for the remainder of the 5-Day window. Treating Fan-Heat's identification as final would discard the joint-identification structure that makes envelope and equipment parameters independently observable under §6 excitation. The successive refinement Day-1 → Day-1-2 (passive) → Day-4-5 (active) is the architectural sequence; each stage tightens the prior for the next.

## 4.7 What this section does not specify

Three things are deliberately out of scope here, named so the boundary is operational rather than proscriptive:

- **The technician procedure on Fan-Heat-Fail.** Disambiguation tests, handheld reference-instrument cross-checks, and the failure-handling decision tree are field-deployable protocol and live in the operational 5-Day commissioning protocol document. This package's contract on fail is the signed record and the halt; the rest is operational.

- **The §5 passive-fit procedure** consuming Day-1-2 telemetry after Fan-Heat passes, to identify the §1.2-canonical envelope parameter subset `{R_eff, C_house, cfm50, F_slab, κ_buffer}` from the passive observation window.

- **The §6 active-perturbation procedure** consuming Day-4-5 telemetry, with the Day-1-2 posterior as the Bayesian prior on envelope parameters and the Day-1 Fan-Heat identification as the Bayesian prior on `η_distribution`. §6 jointly refines envelope, equipment, and delivery parameters under active HVAC excitation, producing the end-of-Day-5 posterior that anchors the envelope half of the Digital Birth Certificate. The Day-3 (Capacity, EER) operating-point map — constructed by `aivu_physics` Phase 2 Layer 2/3 against the same Fan-Heat-validated terminal stack — is the calibrated equipment side that §6 consumes.

---

*End of §4 third-pass draft. Six numerical defaults pinned (`τ_FH = 30 min`, `τ_warmup = 15 min`, `ε_FH = 4%`, `η_min = 0.85`, `η_max = 0.96`, `ΔW_max = 0.0002 kg/kg`, `σ_spatial_max = 0.5 kJ/kg`). Each is overwritable on JDS review without structural change. §5 (passive-fit procedure) opens next.*
