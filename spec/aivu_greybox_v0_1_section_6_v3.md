# aivu_greybox v0.1 — §6: Days 5-6 Active-Perturbation Batch Fit

**Status:** Third-pass draft, v3.1 (day-numbering reconciliation pass per Reconciliation Workstream Phase 1, 2026-05-16: §6's active-perturbation window updated from Days 4-5 to Days 5-6, reflecting the 7-Day commissioning protocol with HVAC commissioning expanded to Days 3-4 two-pass; Day-3 (Capacity, EER) map references updated to Day-4 to reflect that the signed HVAC record now lands at end-of-Day-4 after Day-4's validation repeat of Day-3's sweep; `Day5Posterior` → `Day6Posterior`. INV-FIT45-* names retained as opaque historical identifiers — see §9 etymology footnote. Substantive protocol content unchanged: four-phase 48-hour structure with phase durations 18h / 6h / 18h / 6h, HPM-authored commands via EcoBee API pass-through, fan-only-plus-solar reverse drive, `η_distribution` held at §4 Day-1 value, Phase D held-out validation). Prior v3 (2026-05-12) supersedes v2 of 2026-05-11. **Material correction from v2: HPM-to-HVAC control architecture clarified.** v2 read as if the HPM issues commands directly to compressor and fan, bypassing the thermostat. Actual architecture: HPM issues commands through the EcoBee thermostat's programmable API, which transmits them to the equipment as a command pass-through without exercising EcoBee's own control logic. The protocol math is unchanged (the HPM still commands specific operating points and observes the equipment's response); the architectural framing is corrected throughout. INV-FIT45-3 reworded accordingly. Other v2 content (protocol restructured around full-capacity continuous compressor operation, hold durations 18h driven / 6h decay, aspirational-not-strict steady-state framing, fan-only-plus-solar reverse drive, `η_distribution` held at Day-1 value, Phase D as held-out validation) carried forward unchanged.

Anchored against §§1-5 (including §5 v3.4 closed earlier today). Inherits: §4-identified `η_distribution`, Day-4 (Capacity, EER) operating-point map calibrated by `aivu_physics` Phase 2 Layer 2/3, end-of-Day-2 posterior from §5 as the Bayesian prior, per-parameter identifiability flags from §5.

The Days 5-6 fit produces the **end-of-Day-6 posterior** — the final envelope baseline that anchors the *envelope half, final signing* of the Digital Birth Certificate per §2.3.

---

## 6.1 Position in the commissioning sequence

§6 specifies the Days 5-6 active-perturbation batch fit. It is the second and final batch fit of the 7-Day commissioning window. Where §5 identified the envelope from passive observation, §6 refines that posterior under HPM-commanded HVAC excitation (issued through the EcoBee thermostat's programmable API as a command pass-through, not via EcoBee's own control logic), exploiting the now-calibrated equipment as the active measurement source.

Three architectural distinctions from §5 govern §6's structure:

**The HVAC system is now calibrated.** Days 3-4 produced the (Capacity, EER) operating-point map per `aivu_physics` Phase 2 Layer 2/3 — Day 3 establishes the sweep, Day 4 repeats it for validation against Day 3 — signed at end-of-Day-4 as the HVAC half of the Digital Birth Certificate. §6 consumes this map as a known input — every HPM-commanded HVAC operating point during Days 5-6 has known thermodynamic effect on the conditioned space.

**The system is driven, not held.** §6 issues compressor and fan capacity commands to the HVAC via the HPM, transmitted through the EcoBee thermostat's programmable API as a command pass-through (the EcoBee transmits HPM-authored commands to the equipment without exercising its own thermostat control loop). The protocol drives the system to extreme operating points and observes the full driven trajectory rather than waiting for steady state. **Strict steady state is not achievable in a 48-hour window** for a residential envelope where main-space thermal time constant is ~60 hours (typical R_eff × C_house) and slab thermal time constant is 24-72 hours. The fit identifies parameters from the trajectory itself: the slow approach toward thermal balance, the fast decay components, and the differential rates between main-space and attic states. Strict steady state would simplify the energy-balance algebra; the Laplace fit against the locked forward chain does not require it.

**The prior is informative.** §5's end-of-Day-2 posterior is far tighter than a cold-start prior on the well-identified parameters (`R_eff`, `C_house`, `foam_coupling_factor`) and modestly tighter on the loosely-identified ones (`F_slab`, `C_w`, `cfm50`). §6 inherits this and produces a posterior that combines passive (Days 1-2) and active (Days 5-6) information, not a fresh active-only fit. Per-parameter identifiability flags from §5 propagate forward as input to the §6 fit.

## 6.2 The Days 5-6 protocol

The protocol is four phases across 48 hours, each driven by HPM-authored commands to the compressor and fan (issued through the EcoBee API as a command pass-through), with the equipment operated at known states from the Day-4 (Capacity, EER) operating-point map.

**Pre-condition.** Per INV-FIT45-1 and INV-FIT45-2, §6 requires a valid `Day2Posterior` record and a valid Day-4-signed operating-point map. The Days 5-6 window begins at the start of Day 5 (midnight local time, Phoenix).

### 6.2.1 Phase A — Cooling drive (18 hours)

**Window:** Day 5, 00:00 - 18:00 local time.

**HPM commands:** Compressor at full capacity continuously; fan at nominal speed continuously (no mixing schedule — the fan runs without interruption throughout the phase, supporting continuous compressor operation).

**Trajectory.** Indoor temperature falls from whatever Day-4-end value through the equipment's reachable range. Phoenix-July typical: indoor reaches 16-22°C depending on the envelope's actual `R_eff` and the equipment's full-capacity output at the prevailing outdoor and return-air conditions. Indoor humidity ratio falls toward the coil's effective dewpoint output under continuous dehumidification. The slab thermal mass dominates the slow component of the indoor-temperature trajectory; by hour 14-18, indoor temperature is approaching a quasi-asymptote with the slab still slowly cooling toward its own ground-coupled equilibrium.

**Architectural purpose:**
- **`R_eff`** — high-SNR identification from the sustained ~18-24°C indoor-outdoor differential. The trajectory toward thermal balance pins `R_eff` to the precision of the Day-4 map calibration and the §4 fan-heat calibration.
- **`C_w`** — continuous dehumidification produces a clean latent-side balance. With no occupants, no appliances, and OA dampers closed, the only moisture sources are infiltration (driven by `cfm50` and outdoor humidity) and slow desorption from construction materials. The latent capacity from the Day-4 map combined with the measured indoor `W` trajectory identifies `C_w`.
- **`cfm50`** — the cooling drive's continuous OA-dampers-closed operation creates a regime where infiltration is the *only* outdoor-air path. The latent-side balance plus the conduction-vs-infiltration split in the sensible balance separate `cfm50` from `R_eff` cleanly.

**Continuous-fan observation regime.** During Phase A the fan runs continuously, so the §5 fan-on-warmup attic-observation window is not periodically available. Terminal probes during Phase A read supply-side delivered air (related to return-plenum reading by the §4-identified `η_distribution`); the return-plenum probe reads volume-averaged main-conditioned-space air. Attic temperature is not directly observed during Phase A but is propagated by the forward chain from §5's Day-2 posterior on `foam_coupling_factor`. Phase B's decay produces fresh direct attic observations.

### 6.2.2 Phase B — Cooling decay (6 hours)

**Window:** Day 5, 18:00 - 24:00 local time.

**HPM commands:** Compressor off; fan on §5 mixing schedule (10 min on at minutes 0-10 of each hour, 50 min off).

**Trajectory.** Indoor temperature relaxes upward exponentially toward outdoor temperature. Main-space relaxation time constant is `τ_main = R_eff · C_house`; attic relaxation time constant is set by `R_envelope_roof · C_attic`. The two states are coupled by `foam_coupling_factor`. The 6-hour decay window captures the fast envelope component of the relaxation; the slow slab component continues to evolve and will not equilibrate.

**Architectural purpose:**
- **`C_house`** — recovered from the main-space decay time constant. With `R_eff` pinned by Phase A, dividing `τ_main` by `R_eff` yields `C_house` directly.
- **`foam_coupling_factor`** — the differential relaxation rates of `T_main` and `T_attic` (the latter observed via §5's two-channel mechanism during the 6 mixing-fan-on intervals across this phase) directly express the coupling parameter. The two-channel measurement is critical here; without the attic-warmup observation, the parameter would be loosely identified by indirect inference from main-space behavior alone.

### 6.2.3 Phase C — Reverse drive (18 hours)

**Window:** Day 6, 00:00 - 18:00 local time.

**HPM commands:** Compressor off; fan at extended duty cycle (50 minutes on at minutes 0-50 of each hour, 10 min off) at nominal speed.

**Trajectory.** With no compressor cooling, the building responds to overnight outdoor cooling (early hours) followed by solar-driven heating (after sunrise). Fan-only operation produces ~600W of continuous sensible injection during fan-on intervals (`η̂_distribution × P_fan` from §4) — a known and substantial heat source supplementing the natural solar gain. Indoor temperature drifts up through the morning and afternoon, with no occupant or appliance loads (per Phoenix-pilot pre-occupancy conditions, no fridge, no standby loads, no fixtures running). By mid-afternoon, indoor temperature approaches 30-35°C depending on the envelope's response to natural plus fan-induced heating.

**Architectural purpose:**
- **`F_slab`** — the slow upward drift over 18 hours specifically exposes slab thermal mass. The slab, having spent Phase A absorbing some of the cooling drive's enthalpy (the slab acts as a sink during cooling), now releases that stored energy slowly back to the conditioned space during the reverse drive. This produces a slow-component thermal trajectory that is distinguishable from the fast main-space response. With main-space parameters pinned by Phases A and B, the residual slow component identifies `F_slab`.
- **`cfm50` refinement** — the reverse drive produces a different infiltration regime than the cooling drive (no compressor-induced depressurization; pure stack-and-wind driven). The infiltration-vs-conduction split during this phase, combined with the Phase A result, separates the wind-dependent component from the stack-dependent component within the lumped `cfm50` parameter.
- **`C_w` refinement** — overnight and morning typically have higher outdoor humidity ratios than afternoon; the infiltration pulls in this higher-humidity air, producing an upward indoor-W trajectory that the moisture-side dynamics constrain against the (already partially identified) `C_w`.

**Why no compressor in Phase C.** A symmetric heating phase using heat-strip resistance would be operationally simple but architecturally noisy: heat-strip electrical input is large (~10 kW for a typical residential heat strip), and the resulting indoor-outdoor differential of opposite sign would mainly retest `R_eff` rather than pin `F_slab` and refine `cfm50`. The fan-only-plus-solar reverse drive uses the structurally distinct excitation mechanism (slow heating from below via slab release plus solar gain from above via roof) to identify the parameters Phase A cannot.

### 6.2.4 Phase D — Final closing observation (6 hours)

**Window:** Day 6, 18:00 - 24:00 local time.

**HPM commands:** Compressor off; fan on §5 mixing schedule (10 min on / 50 min off).

**Trajectory.** Following Phase C's reverse drive, the building has reached its highest indoor temperature near mid-to-late afternoon. As outdoor temperature falls into evening, the building begins to cool naturally. The 6-hour window provides a final observation of envelope behavior under conditions distinct from any prior phase — moderate indoor-outdoor differential, no driven excitation, mixing-fan observation regime active.

**Architectural purpose:** Closing fit-quality validation. Phase D's trajectory is *predicted* by the forward chain given the posterior derived from Phases A+B+C; the residual between prediction and observation during Phase D is a diagnostic on the posterior's calibration. A large Phase D residual indicates the parameter set identified from A+B+C does not generalize to the regime D occupies — a possible signal of identifiability collapse, prior misspecification, or model-structure inadequacy. Phase D is therefore the §6 internal validation against held-out data, internal to the same fit.

### 6.2.5 Excitation summary

| Phase | Window | HPM compressor | HPM fan | Identifies primarily |
|---|---|---|---|---|
| A: Cooling drive | Day 5, 00:00-18:00 (18h) | Full capacity | Continuous nominal | `R_eff`, `C_w`, `cfm50` |
| B: Cooling decay | Day 5, 18:00-24:00 (6h) | Off | Mixing 10/50 | `C_house`, `foam_coupling_factor` |
| C: Reverse drive | Day 6, 00:00-18:00 (18h) | Off | Extended 50/10 | `F_slab`, refines `cfm50` and `C_w` |
| D: Final close | Day 6, 18:00-24:00 (6h) | Off | Mixing 10/50 | Validation against held-out data |

Total: 48 hours, fitting within the 24-hour-wall-clock-fit ceiling per §3.2. The Laplace optimization consumes the entire 48-hour trajectory as one observation set; phases are not fit separately, only operated separately.

## 6.3 The fit problem

§6 performs Bayesian inverse identification of the six canonical envelope parameters from 48 hours of 1 Hz Days 5-6 telemetry, with the §5 end-of-Day-2 posterior as the prior, the Day-4-calibrated equipment as the known excitation source, and the same two-channel observation model as §5 — with the channel availability varying across phases per §6.2.

**The state vector and forward model.** Same two-state envelope as §5: `aivu_dynamic.dynamic.run(θ, u_meas, w_meas)` propagating `(T_main, W_main, T_attic, W_attic)`. The canonical parameter vector unchanged: `θ = (R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor)`.

**The HVAC excitation `u_meas`.** Computed at each 1 Hz sample. During Phase A:

```
Q̇_HVAC,sensible(t)  =  Capacity_sensible(T_out(t), T_return(t), W_return(t), m_air(t))  · 1.0
Q̇_HVAC,latent(t)    =  Capacity_latent(T_out(t), T_return(t), W_return(t), m_air(t))    · 1.0
Q̇_fan(t)            =  η̂_distribution · P_fan(t)
```

(Compressor at full capacity = cooling_fraction 1.0; both sensible and latent capacities at the operating point from the Day-4 map; fan continuous.)

During Phases B and D:

```
Q̇_HVAC,sensible(t)  =  0  (compressor off)
Q̇_HVAC,latent(t)    =  0  (compressor off)
Q̇_fan(t)            =  η̂_distribution · P_fan(t) · 𝟙_{fan_on}(t)  (mixing schedule)
```

During Phase C:

```
Q̇_HVAC,sensible(t)  =  0  (compressor off)
Q̇_HVAC,latent(t)    =  0  (compressor off)
Q̇_fan(t)            =  η̂_distribution · P_fan(t) · 𝟙_{fan_on}(t)  (extended-duty mixing)
```

(Phase C fan-heat injection averaged across the duty cycle: 50 min/hr × 500 W × 0.92 ≈ 380 Wh/hr, roughly 5× the Phase B/D injection rate. This is part of the controlled excitation budget for Phase C, not a parasitic loss.)

**Channel availability across phases.** The two observation channels are not uniformly available:

- **Phase A (continuous fan)**: Return-plenum reads volume-averaged `T_main`, `W_main` continuously. Terminal probes read supply-side delivered air continuously, related to return via §4 `η_distribution`. Attic-channel observations (terminal-probe warmup readings) are **not available** during Phase A — the fan never cycles off long enough for ducts to thermally equilibrate with the attic.

- **Phase B (mixing schedule)**: Six fan-on intervals (one per hour for 6 hours). Two-channel observation as in §5: warmup-window terminal probes read attic, post-warmup return-plenum reads main.

- **Phase C (extended duty 50/10)**: Eighteen fan-on intervals (one per hour for 18 hours), each 50 minutes long. The 10-minute fan-off intervals are too short for ducts to fully thermally equilibrate with attic (typical attic thermal mass relaxation back to equilibrium with surrounding air is ~5-15 minutes). Attic-channel observations during Phase C are therefore **degraded** — the first 60 seconds of fan-on read air that has only partially equilibrated. The observations are retained with a wider uncertainty bound (`σ_T_attic` doubled to 0.10°C for Phase C samples).

- **Phase D (mixing schedule)**: Same as Phase B. Six fan-on intervals, full two-channel observation.

The §6 likelihood handles the per-phase channel availability by summing only over actually-available observation intervals, with phase-appropriate σ values.

**The likelihood.** Structurally extended from §5 to handle phase-dependent observation channels:

```
log L(θ | data)  =  −½ [
    Σ_{t ∈ Phase A continuous} (T_main^obs(t) − T_main^pred(t; θ))² / σ_T²
                              + (W_main^obs(t) − W_main^pred(t; θ))² / σ_W²
  + Σ_{k ∈ Phase B intervals} (T_attic^obs(k) − T_attic^pred(t_warm(k); θ))² / σ_T_attic²
                            + Σ_{t ∈ k_main}  (T_main^obs(t) − T_main^pred(t; θ))² / σ_T²
                                            + (W_main^obs(t) − W_main^pred(t; θ))² / σ_W²
  + Σ_{k ∈ Phase C intervals} (T_attic^obs(k) − T_attic^pred(t_warm(k); θ))² / σ_T_attic_degraded²
                            + Σ_{t ∈ k_main}  (T_main^obs(t) − T_main^pred(t; θ))² / σ_T²
                                            + (W_main^obs(t) − W_main^pred(t; θ))² / σ_W²
  + Σ_{k ∈ Phase D intervals} (same as Phase B)
]
```

where `σ_T = 0.1°C`, `σ_T_attic = 0.05°C` (per §5 v3.2 calibration), `σ_T_attic_degraded = 0.10°C` (Phase C wider bound), `σ_W` from SHT35 ±1.5% RH translated to humidity-ratio space.

**The prior.** §5's end-of-Day-2 posterior:

```
p(θ)_6  =  N(θ | μ_5_posterior, Σ_5_posterior)
```

Per-parameter identifiability flags from §5 propagate forward.

**The posterior.** Standard Bayesian update against the active-perturbation likelihood, computed by Laplace approximation per §5.6.

## 6.4 Identifiability under the §6 protocol

The protocol is structured against specific identifiability gains. Expected posterior tightness at end-of-Day-6, compounding §5 prior with §6 data:

| Parameter | §5 (passive) | §6 (active, this protocol) | Primary phase |
|---|---|---|---|
| `R_eff` | 5% | **≲ 1%** | Phase A sustained drive |
| `C_house` | 5% | **≲ 1.5%** | Phase B decay |
| `cfm50` | 30% | **≲ 8%** | Phases A + C combined |
| `F_slab` | 15% | **≲ 5%** | Phase C reverse drive |
| `C_w` | 25% | **≲ 8%** | Phases A + C latent balance |
| `foam_coupling_factor` | 15% | **≲ 4%** | Phase B differential decay |

Substantial tightening across all six parameters. The largest absolute improvements are on `cfm50` (30% → 8%, ~4× tightening) and `F_slab` (15% → 5%, 3× tightening) — the two parameters that passive observation cannot resolve.

**On joint identifiability of `R_eff` and `η_distribution`.** Phase A's continuous-fan continuous-compressor operation involves both a known coil capacity (Day-4 map) and a known fan-heat injection (§4 `η_distribution`). If §6 attempts to jointly identify `η_distribution` along with `R_eff`, the two parameters trade off against each other along an under-determined ridge — both affect the relationship between equipment electrical input and indoor temperature. **§6 v0.1 holds `η̂_distribution` at the §4-identified Day-1 value** and lets §7 ongoing-Cx track its drift over months. Joint identification within §6 is deferred to v0.2 if a structurally distinct excitation can be designed that breaks the degeneracy (e.g., a Phase C-style fan-only-no-compressor regime is necessary to identify `η_distribution` independent of compressor output, but adding it to the §6 fit with only ~5 hours of distinct data would not provide decisive SNR).

**Identifiability collapse detection (§8) runs after §6 fit completes.** Any parameter that remains effectively prior-only after §6 indicates a structural identifiability gap. The resulting posterior is signed with the identifiability-collapse flag preserved, and downstream consumers see exactly which parameters are committed at high confidence and which are not.

**The Phase D residual diagnostic** (§6.2.4) provides additional confidence: if Phase D observations match Phase-A+B+C-derived predictions to within their measurement uncertainty, the posterior generalizes correctly. A large Phase D residual is a structural warning that the parameter set has been overfit to the driven phases.

## 6.5 Solver mode

§6 runs in **batch mode**, Laplace approximation per §5.6. Computational budget: 24-hour wall-clock ceiling per §3.2, expected actual time in minutes on representative HPM hardware.

**One operational difference from §5.** The §6 likelihood involves evaluating the Day-4 (Capacity, EER) operating-point map at each Phase A sample (~65k samples across 18 hours). Bi-quadratic interpolation per `aivu_physics` Phase 2 Increment 8 is a fast operation; total map-evaluation cost across all phases is bounded and well within the wall-clock ceiling.

## 6.6 Convergence and quality diagnostics

Identical to §5.7 (optimizer convergence per restart, mode-agreement across restarts, Hessian positive-definiteness, Hessian eigenvalue spectrum, posterior-prior divergence per parameter).

Two §6-specific diagnostics added:

- **Phase D held-out residual.** The Phase D trajectory is predicted by the forward chain using the posterior derived from Phases A+B+C, and the prediction is compared against observation. A residual exceeding `5% relative` on time-averaged indoor temperature or humidity flags the posterior for review. Emitted as a diagnostic; does not halt the fit but is signed into the record.

- **Phase A asymptote check.** During the final 2-3 hours of Phase A, indoor temperature should be approaching a quasi-asymptote (rate of change below 0.1°C/hour). If the trajectory is still changing at a higher rate, Phase A duration was insufficient for the slow components to manifest. Emitted as a diagnostic. Future protocol-iteration question; does not halt the v0.1 fit.

## 6.7 Output: the end-of-Day-6 signed posterior record

On successful fit completion, §6 emits a `Day6Posterior` record. Structure identical to §5's `Day2Posterior` (§5.8), with these additions:

- **Reference to the `Day2Posterior` record** (by content-addressed hash) — explicit chain through the prior.
- **Reference to the Day-4 (Capacity, EER) operating-point map signing record** (by content-addressed hash) — explicit chain through the HVAC calibration.
- **Excitation protocol record** — the actual HPM compressor and fan commands executed during Days 5-6, including timestamps of phase transitions and any deviations from the programmed protocol (e.g., if a hardware fault forced an early compressor shutoff in Phase A). Signed into the record.
- **Phase D held-out residual** per §6.6.
- **Phase A asymptote diagnostic** per §6.6.

Per §1.3's cryptographic-infrastructure non-goal, signing and commitment is performed by calling into `aivu_integrity`'s API. The record is signed with the HPM per-packet signing key, committed via MMR, appended to the local signed log. Per §2.3, the Digital Birth Certificate signing process consumes this record as the *envelope half, final signing* and invokes `aivu_integrity`'s 2-of-3 threshold attestation protocol at that signing moment. This supersedes the Day-2 initial signing as the home's commissioned envelope baseline.

## 6.8 Invariants

The §6 batch fit has seven invariants any implementation must satisfy.

**INV-FIT45-1 — `Day2Posterior` prerequisite.** §6 MUST NOT run without a valid `Day2Posterior` record from §5 as the prior.

**INV-FIT45-2 — Day-4 map prerequisite.** §6 MUST NOT run without a valid Day-4-signed (Capacity, EER) operating-point map. The HVAC excitation `u_meas` for Phase A is computed from that map; without it, `u_meas` is not defined.

**INV-FIT45-3 — HPM-authored command authority via thermostat API pass-through.** §6's protocol requires that the HPM can issue specific compressor and fan capacity commands (such as "compressor stage 2 ON, fan high") that the thermostat transmits to the equipment as a command pass-through, without the thermostat exercising its own setpoint-tracking control loop during the 48-hour Days 5-6 window. For the Phoenix pilot this is provided by the EcoBee thermostat's programmable API. If a deployment uses a thermostat that does not expose a programmable command-pass-through API (e.g., a building where the thermostat is the only HVAC controller available with no programmable interface, or a commercial building with a proprietary BAS controller), §6 v0.1 cannot run; a v0.2 fallback protocol using setpoint-trajectory-driven excitation would need to be specified.

**INV-FIT45-4 — Excitation protocol adherence.** The HPM commands actually issued during Days 5-6 MUST match the programmed phase schedule within tolerance (default ±15 min on phase transitions; compressor and fan commands themselves are deterministic from the protocol). Deviations are recorded into the signed record; large deviations (e.g., hardware fault) are noted as caveats on the posterior's interpretation.

**INV-FIT45-5 — Prior provenance chain preserved.** The §6 posterior record MUST reference the §5 posterior's prior-provenance descriptor (per §5.4) and the §5 posterior's own hash. An external verifier examining a `Day6Posterior` MUST be able to trace the full prior-provenance chain.

**INV-FIT45-6 — Convergence diagnostics gate the signing.** Same as INV-FIT12-4 for §5. No `Day6Posterior` record is emitted (and therefore no Digital Birth Certificate envelope-half-final signing occurs) if convergence or quality diagnostics fail per §6.6.

**INV-FIT45-7 — `η_distribution` held at Day-1 value.** §6 v0.1 MUST NOT attempt to jointly identify `η_distribution` along with the six canonical envelope parameters. The value used is the §4-identified Day-1 value, propagated through the fit as a known input. Joint identification is a v0.2 question; attempting it in v0.1 risks an `R_eff × η_distribution` degeneracy that the Phase A excitation alone cannot resolve.

## 6.9 What this section does not specify

- **The Day-4 (Capacity, EER) operating-point map construction.** `aivu_physics` Phase 2 Layer 2/3 territory.
- **The operational protocol for the technician** during Days 5-6 — what to monitor, what to escalate, how to respond to hardware faults during the 48-hour window. Operational protocol document territory.
- **The recursive-mode solver** for Phase 2 ongoing-Cx operation. Specified in §7-§8.
- **Joint refinement of `η_distribution`.** §6 v0.1 holds at Day-1 value; joint identification deferred to v0.2 per INV-FIT45-7.
- **Protocol parameters as configuration.** Phase durations (18h / 6h / 18h / 6h), compressor command (full capacity), fan duty cycles (continuous / 10-50 / 50-10 / 10-50), and tolerances (±15 min phase transitions, ±5% Phase D residual, 0.1°C/hr Phase A asymptote rate) are configuration defaults pinned for the Phoenix-pilot configuration. Other climate zones or builder configurations may want different values; the §6 spec's structure is preserved across configurations, only the numerical defaults change.
- **Heat-strip-based reverse excitation.** Replaced in v2 by fan-only-plus-solar reverse drive (Phase C). Heat-strip excitation would be operationally simple but architecturally noisy per §6.2.3.

---

*End of §6 third-pass draft v3.1. Configuration defaults: four-phase protocol (Phase A cooling drive 18h at full capacity continuous fan; Phase B cooling decay 6h with mixing fan; Phase C reverse drive 18h fan-only extended duty no compressor; Phase D final closing observation 6h mixing fan); Phase A asymptote check rate threshold 0.1°C/hr; Phase D residual tolerance 5% relative; protocol-adherence ±15 min on transitions; `σ_T_attic_degraded = 0.10°C` for Phase C samples. HPM-authored commands transmitted to equipment via EcoBee API as command pass-through (architectural correction 2026-05-12). Day-numbering reconciled to 7-Day protocol (Days 5-6 active perturbation, Day-4 HVAC map prerequisite, `Day6Posterior` output) per Reconciliation Workstream Phase 1, 2026-05-16. Six-parameter canonical set unchanged: `{R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor}`. Expected end-of-Day-6 posterior tightness ranges per parameter (1% / 1.5% / 8% / 5% / 8% / 4%) — substantial tightening from §5 (5% / 5% / 30% / 15% / 25% / 15%). `η_distribution` held at §4 Day-1 value per INV-FIT45-7; joint refinement deferred to v0.2. §7 (recursive-mode Phase 2 solver) opens next.*
