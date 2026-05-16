# aivu_greybox v0.1 — §5: Days 1-2 Passive-Observation Batch Fit

**Status:** Third-pass draft, 2026-05-11/12, v3.4 (day-numbering reconciliation pass per Reconciliation Workstream Phase 1, 2026-05-16: Day-3 references updated to Days 3-4 for the HVAC commissioning activity, with the signed map output landing at end-of-Day-4; Days 4-5 active perturbation updated to Days 5-6; clarification that Day 1 is the first measurement day, NOT the Day-0 install day; substantive content unchanged. Prior v3.3 correction from v3.2: §5.6 NUTS/HMC fallback explicitly committed as v0.2 architectural answer to non-Gaussian-posterior risk, per JDS direction 2026-05-12). Prior v3.2 changes: parameter name `κ_buffer` → `C_w` to match April 27 spec naming; algorithm class NUTS → Laplace approximation per April 27 §6.2 spec lock for v0.1; §5.7 convergence diagnostics rewritten for Laplace; §5.8 output record updated for Laplace structure. Prior v3.1 changes: softened `σ_T_attic` from 0.029°C to 0.05°C pending pilot validation of inter-probe calibration scatter; corrected `foam_coupling_factor` empirical anchor to ~2.5°F at 3pm-July from prior simulation. Anchored against §§1-4 (including §4 v3 closed earlier today) and against Phase 1 v4.0 §10 (two-state attic-main envelope model with foam coupling) and `aivu_dynamic` v0.2 (forward-chain state vector and inverse-fit parameter set). Supersedes v3.2.

Material changes from v2:
- Canonical parameter set extended from five to **six**, adding `foam_coupling_factor` to reflect the two-state attic-main envelope architecture committed in Phase 1 v4.0 §10. `aivu_dynamic` v0.2 line 35 already lists this parameter; greybox §1.2's five-parameter naming was incomplete for the Phoenix-foam-attic configuration.
- Operational definition: AHU fan on programmed mixing schedule (10 min/hr) during Days 1-2, was "HVAC fully off."
- Observation model: **two channels**. Return-plenum SHT35 reads `T_main` during fan-on post-warmup intervals; terminal SHT35s read `T_attic` during the first 60s of each fan-on interval (duct-equilibrated air). Both feed the §5 likelihood.
- Path preference order in §5.4 carried forward from v2 fix (EnergyPlus ahead of ACCA).

---

## 5.1 Position in the commissioning sequence

§5 specifies the Day-1-2 passive-observation batch fit. The fit runs at end-of-Day-2 once 48 hours of telemetry have accumulated, against the canonical parameter set `{R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor}`, using the locked forward chain (`aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2) as the likelihood and a structured Bayesian prior supplied externally.

The fit produces the **end-of-Day-2 posterior**. Per §2.3 this posterior is the *envelope half, initial signing* of the Digital Birth Certificate; it is also the Bayesian prior consumed by §6's active-perturbation joint refinement on Days 5-6.

**Day-numbering convention.** Day 1 is the first measurement day after the home is instrumented and the system is brought online. The Day-0 install day (sensor placement, Mixing Length Verification, connectivity handshake) precedes Day 1 and is out of scope for §5. The 7-Day commissioning window is Day-0 install plus Days 1-6 measurement protocol.

Days 3-4 sit between Days 1-2 and Days 5-6 and run the HVAC operating-point sweep that calibrates the (Capacity, EER) map. Day 3 establishes the sweep; Day 4 repeats it for validation against Day 3, with the signed map landing at end-of-Day-4 as the HVAC half of the Digital Birth Certificate. §5 does not produce or consume that map. The Days 3-4 sweep can proceed concurrently with or after the §5 batch fit completes; the only ordering constraint is that §6 requires both the §5 posterior and the calibrated Day-4 map before it runs.

## 5.2 Operational definition

During Days 1-2:

- **Compressor off, heat strip off, OA dampers closed.** No equipment activity that would inject load-bearing inputs of unknown magnitude (the (Capacity, EER) map is not constructed until Days 3-4).
- **AHU fan operates on a programmed mixing schedule:** 10 minutes on at minutes 0-10 of each clock-aligned hour, 50 minutes off, fan at the nominal speed used by §4 Fan-Heat. 48 fan-on intervals over the 48-hour window.
- **All other state passive:** building experiences weather forcing, no occupants (commissioning is pre-occupancy), no commanded perturbation.

**The fan schedule is the §5 measurement protocol, not a workaround.** The architectural reason for fan operation is structural: the §4 Fan-Heat-validated sensor stack includes a return-plenum SHT35 located behind the return air filter and far enough from the fan that radiation effects from fan motor or coil surfaces are negligible. During fan operation, the return-plenum probe reads air that has just been pulled through the conditioned volume and mixed by the filter, naturally integrating the volume-averaged main-conditioned-space temperature and humidity ratio. The 12 terminal SHT35s read supply-side delivered air, related to the return-plenum reading by the §4-identified `η_distribution`. Together, the return + terminal stack measures indoor state during every fan-on interval at a precision set by the §4 calibration of the delivery instrument.

Outside fan-on intervals, the AHU is quiescent. Air sits in the ductwork and equilibrates with the conditioned attic; conditioned-space air stratifies under natural buoyancy and solar forcing. §5.3 below restricts the main-space likelihood to fan-on intervals after a 60s warmup accordingly — and turns the warmup itself into a second observation channel.

**Why this fan schedule is correct:**

- 10 minutes per fan-on interval is comfortably longer than the duct-flush warmup (~60s for the supply ductwork) and the filter thermal-equilibrium time (under 30s), leaving 8+ minutes of valid main-space measurement per interval.
- 48 fan-on intervals across the 48-hour window provide far more than adequate temporal sampling of the diurnal envelope-forcing cycle for envelope-parameter identification — 24 indoor-state observations per diurnal cycle.
- Fan-heat injection at 10 min/hr × ~500W × `η̂_distribution` ≈ 80 Wh/hr ≈ 1.9 kWh/day, which is ~2% of typical Phoenix-July daily envelope load. The injection is known a priori (from §4) and enters the forward chain through `u_meas`; it does not introduce identification ambiguity. Indoor temperature rise from fan heat alone, over a 48-hour HVAC-off-but-fan-cycling window, is roughly 0.3-0.5°C — small relative to the diurnal swing of 10-15°C the fit is identifying against.
- Filter restriction is negligible at install time (clean filter); long-term filter loading is a Phase 2 ongoing-Cx concern (§7) where the same instrument stack tracks the slow drift of `η_distribution` over months.

## 5.3 The fit problem

§5 performs Bayesian inverse identification of the six canonical envelope parameters from 48 hours of 1 Hz telemetry against the locked forward chain, with two observation channels exploiting the structure of the fan-on intervals.

**The state vector and forward model.** Per Phase 1 v4.0 §10 and `aivu_dynamic` v0.2, the conditioned envelope is a two-state thermal system: main conditioned space (`T_main`, with moisture state `W_main`) and conditioned attic (`T_attic`, with `W_attic` typically tracking via vapor diffusion through ceiling assemblies). Phase 1 v4.0 §10 specifies the foam-at-deck attic-air equation:

```
T_attic_ss = (U_roof·A_roof·T_sol_air + U_ceiling·A_ceiling·T_main) / (U_roof·A_roof + U_ceiling·A_ceiling)
```

with the dynamic version in `aivu_dynamic` v0.2 carrying attic thermal mass and a coupling parameter `foam_coupling_factor` that governs the effective `U_ceiling × A_ceiling` product for the spray-foam-deck geometry. The 0.75 default in AOT §3.2 is a placeholder prior; §5 identifies the home-specific value.

Let `θ = (R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor)` be the canonical parameter vector. The forward chain, accessed via `aivu_dynamic.dynamic.run(θ, u_meas, w_meas)`, produces a predicted state trajectory `(T_main^pred(t), W_main^pred(t), T_attic^pred(t))` over the 48-hour window given:

- `θ` — candidate parameter vector (six elements);
- `u_meas` — measured HVAC excitation: during fan-on intervals, `u_meas` is the sensible-heat injection `Q̇_sens(t) = η̂_distribution · P_fan(t)` with `η̂_distribution` from the §4 Day-1 identification and `P_fan(t)` from the Eaton breaker; during fan-off intervals, `u_meas ≡ 0`. Latent injection is zero throughout. The fan-heat injection enters the main-conditioned-space state, not the attic state — air recirculation under fan-only conditions does not couple AHU electrical input to the attic state directly;
- `w_meas` — measured weather (outdoor T/RH, solar irradiance, wind) at 1 Hz from the site weather station.

**The two observation channels.**

Each fan-on interval `k` (10 minutes long, starting at the top of each hour) contains two structurally distinct sub-intervals:

- **Warmup sub-interval `k_warm = [0, 60s]` after fan-on.** Air sitting in the supply ductwork during the preceding 50-minute fan-off interval has equilibrated thermally with the conditioned attic. When the fan kicks on, this attic-equilibrated air is pushed through the 12 terminal SHT35 probes before being replaced by freshly mixed conditioned-space air. The 12 terminal probes therefore read the **attic-air state** during this sub-interval. Time-averaging across the 60s window and spatial-averaging across the 12 terminals yields one `T_attic^obs(k)` observation per fan-on interval, with `√12 ≈ 3.46` spatial-averaging benefit on independent noise. The return-plenum probe during `k_warm` reads air pulled from the conditioned space (no equivalent long duct equilibration), so it provides a main-conditioned-space observation that complements the attic reading.

- **Main-fan sub-interval `k_main = [60s, 600s]` after fan-on.** Supply ductwork has been swept clean of attic-equilibrated air; terminal and return probes both read freshly mixed conditioned-space air. The return-plenum SHT35 reads the volume-averaged `T_main` and `W_main`; the terminal SHT35s read supply-side delivered state, which under fan-only excitation is `(T_main + Q̇_sens · ⟨residence time⟩ / mC)` per the §4-identified `η_distribution`. The return-plenum reading is canonical for the main-state likelihood contribution; terminal readings during `k_main` are a redundant corroboration channel.

**The likelihood.** Sum of contributions across the two observation channels, over the 48-hour window:

```
log L(θ | data)  =  −½ Σ_{k=1}^{48} [
    (T_attic^obs(k) − T_attic^pred(t_warm(k); θ))² / σ_T_attic²
  + Σ_{t ∈ k_main} (T_main^obs(t) − T_main^pred(t; θ))² / σ_T²
  + Σ_{t ∈ k_main} (W_main^obs(t) − W_main^pred(t; θ))² / σ_W²
]
```

where:
- `σ_T_attic = 0.05°C` for the spatial-averaged attic observation. This treats the SHT35 factory calibration offsets across the 12 terminal probes as partially correlated (same manufacturing lot, same calibration batch), so the effective spatial averaging is less than the full √N benefit a fully-independent set would deliver. The conservative default of 0.05°C is roughly halfway between the single-probe noise floor (0.1°C) and the full-√12 floor (0.029°C). Pilot data will eventually constrain the actual scatter; if probe-to-probe agreement turns out tighter than 0.05°C, the value can be revised downward in v0.2;
- `σ_T = 0.1°C` for the return-plenum main observation (SHT35 spec);
- `σ_W` is the SHT35 ±1.5% RH spec translated to humidity-ratio space at typical conditions.

The forward chain predicts continuously over the 48-hour window; the likelihood evaluates only on the structured observation intervals. State propagation through fan-off intervals is the bridge that makes the next fan-on observation depend on parameters even though no likelihood is evaluated during the bridge.

**The prior.** §5 consumes a structured Bayesian prior on `θ`:

```
p(θ)  =  N(θ | μ_prior, Σ_prior)
```

The prior is multivariate Gaussian over the six-element parameter vector. The `foam_coupling_factor` prior has the AOT §3.2 placeholder value 0.75 as `μ_prior[6]` with appropriate width; values for the other five come from the path-supplied source per §5.4.

**The posterior.** Standard Bayesian inversion:

```
p(θ | data)  ∝  p(data | θ) · p(θ)
```

Computed by Laplace approximation (§5.6) using the locked forward chain as the likelihood evaluator. Convergence and quality diagnostics in §5.7.

## 5.4 Prior interface and provenance

The Day-1-2 fit is the first batch fit in greybox's commissioning sequence; its prior determines the regularization of the posterior on parameters that turn out to be loosely identified (§5.5).

§5 specifies the prior interface, not the prior values:

**Prior structure:**

- Multivariate Gaussian over the canonical parameter vector `θ = (R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor)`;
- Mean vector `μ_prior` ∈ ℝ⁶;
- Covariance matrix `Σ_prior` ∈ ℝ⁶ˣ⁶, positive-definite;
- Provenance metadata: a free-text descriptor naming the source path (e.g., "PINN_v0.1_cohort_2026_Q3", "EnergyPlus_8760h_BeazerPhoenix_TMY3", "ACCA_ManualJ_Phoenix_2B_1800sqft_2stage_foam_attic"), the timestamp of generation, and a hash of the source artifact when one exists.

**Provenance is signed metadata on the posterior.** The end-of-Day-2 signed posterior record (see §5.8) MUST include the prior provenance descriptor as a load-bearing field. Loose-parameter posteriors are prior-sensitive; external verifiers interpreting the posterior on (e.g.) `F_slab` need to know whether the supporting prior came from a trained PINN, an EnergyPlus simulation, or a Manual J table, because the inferential weight of the posterior on that parameter depends on which.

**Path preference order, for reference (not legislated by this spec):**

1. **Trained PINN**, when `aivu_pinn` v0.1 is available — projected at the home's gbXML coordinates, returning a six-parameter-space distribution including `foam_coupling_factor`. The architectural commitment from AOT; the only path that produces priors that improve with cohort growth.
2. **EnergyPlus 8,760-hour simulation** on the home's gbXML against the relevant TMY3 weather. Produces a physics-grounded, time-domain prior structurally compatible with the locked forward chain — extract parameter values by running `aivu_physics + aivu_dynamic` against the EnergyPlus trajectory and identifying the parameters that reproduce it. EnergyPlus's native handling of foam-at-deck unvented attic geometry yields a defensible prior on `foam_coupling_factor` specifically. No cohort learning, but the prior is grounded in DOE-2-derived heat-balance physics.
3. **ACCA Manual J-derived default values**, when neither of the above is available. Steady-state assumption set; appropriate as a strict-pilot-time fallback. The AOT §3.2 placeholder of 0.75 for `foam_coupling_factor` is consistent with this fallback path.

Whichever path supplied the prior, §5 consumes it through the same interface and emits the same posterior structure. The provenance descriptor makes the choice auditable downstream.

## 5.5 Identifiability under the §5 protocol

Under the §5.2 operational conditions (compressor off, fan on 10 min/hr mixing schedule, two-channel observations with attic readings during 60s warmup and main readings during 60s-600s post-warmup), the six canonical parameters are not equally observable from 48 hours of data. §5 produces the joint posterior over all six and reports per-parameter identifiability assessments alongside the posterior.

**Expected identifiability profile under Phoenix-July passive forcing with two-channel measurement:**

- **`R_eff` (envelope thermal resistance) — well-identified.** Dominant parameter governing the diurnal swing magnitude in `T_main`. 15-20°C diurnal envelope forcing across two cycles with 24 high-precision return-plenum observations per cycle directly constrains `R_eff`. Expected posterior tightness: σ_posterior / μ_prior ≲ 5%.

- **`C_house` (lumped main-space sensible capacitance) — well-identified.** Governs phase lag between outdoor temperature peak and main-space temperature peak. Both phase and attenuation observable from the return-plenum trajectory across two diurnal cycles. Expected posterior tightness: σ_posterior / μ_prior ≲ 5%.

- **`foam_coupling_factor` — well-identified, possibly the largest beneficiary of the two-channel observation model.** The instantaneous differential between `T_attic^obs(k)` (from terminal-probe warmup readings) and `T_main^obs(k)` (from main-fan return-plenum readings) at each of 48 fan-on intervals directly constrains the attic-to-main coupling. The simulation anchor for the Phoenix-foam-attic configuration is a 3pm-July attic-to-main differential of ~2.5°F (~1.4°C) — produced by prior modeling, more reliable than incidental occupant reports. The differential is largest at midday solar peak and approaches zero near pre-dawn, so the parameter's discriminating signal concentrates in a 4-6 hour daytime window each diurnal cycle. With two diurnal cycles in the 48-hour observation window, the fit sees ~8-12 high-SNR observation intervals on this parameter; the remaining intervals contribute lower-weight constraints. Expected posterior tightness: σ_posterior / μ_prior ≲ 15% (softened from a previous 10% prediction pending pilot validation; the differential magnitude is modest enough that the posterior tightness is sensitive to the actual day-to-day weather variability during the 48-hour window). Tightened further by §6 when active perturbation introduces controlled main-space cooling that swings the attic-main differential through a wider range.

- **`F_slab` (slab coupling) — moderately identified.** Depends on whether enough thermal drift reaches the slab over 48 hours to distinguish slab-coupled response from envelope-only response. Phoenix-July high-diurnal-forcing conditions usually achieve this. Expected posterior tightness: σ_posterior / μ_prior ≲ 15%; tightened by §6.

- **`C_w` (moisture capacity, lumped) — moderately to loosely identified.** The moisture-side analog of `C_house` — paired with the sensible state in the two-state-per-side `aivu_dynamic` formulation. Depends on magnitude of indoor RH excursion across the 48 hours. Phoenix-July dry conditions produce modest indoor RH variation under passive operation; partially constrained but the posterior is wider than the sensible-side parameters. Expected posterior tightness: σ_posterior / μ_prior ≲ 25%; tightened materially by §6 under active perturbation.

- **`cfm50` (envelope airtightness) — loosely identified, trickiest of the six.** Passive infiltration is wind-dependent through the n-factor relation. Phoenix-July typical wind speeds (5-10 mph average) provide some infiltration signal but the n-factor introduces a multiplicative uncertainty that the passive fit cannot resolve. Expected posterior tightness: σ_posterior / μ_prior ≲ 30%; tightened substantially by §6 when controlled HVAC operation introduces depressurization signatures.

**On joint identifiability of `R_eff` and `foam_coupling_factor`.** A two-state model raises the question of whether the envelope-resistance path (outdoor to attic to main) and the attic-coupling path can be independently identified, or whether they trade off against each other along an under-determined ridge. Under Phoenix-July conditions the answer is "mostly yes, independently identifiable" — the *phase* of `T_attic` relative to outdoor solar forcing (driven by attic thermal mass + R_envelope_roof) is structurally distinct from the *phase* of `T_main` relative to `T_attic` (driven by main thermal mass + foam coupling). The two phase relationships separate the parameters. §8 identifiability collapse detection runs after the fit to confirm this empirically; if a ridge exists in the posterior, §8 raises the flag and §6 active perturbation provides the discriminating excitation.

**On envelope-resistance decomposition into roof and wall paths.** Phase 1 v4.0 §10 carries `R_envelope_roof` and `R_envelope_walls` as architecturally distinct paths. `R_eff` in greybox §1.2 is the lumped equivalent. Whether §5 identifies the lumped `R_eff` or decomposes it depends on the SNR available. Default for v0.1: **§5 identifies the lumped `R_eff` from the two-channel data**; decomposition into roof and wall paths is a v0.2 question if §6 active perturbation provides discriminating SNR (e.g., night-time cooling operation with no solar forcing discriminates wall-dominated cooling load from roof-dominated). For the Phoenix pilot, lumped `R_eff` is sufficient.

**Identifiability collapse detection (§8) MUST run after the §5 fit and before the posterior is signed.** If any parameter posterior is structurally unconstrained (effectively returning the prior unchanged with σ_posterior / σ_prior > 0.95), §8 raises an identifiability-collapse flag for that parameter. The end-of-Day-2 posterior is signed regardless, but the flag becomes load-bearing metadata: §6 receives notice that the parameter requires active perturbation to identify, and downstream consumers see which parameters at end-of-Day-2 are effectively prior-only.

## 5.6 Solver mode

§5 runs in **batch mode** (§1.1). The end-of-Day-2 fit consumes 48 hours of telemetry in a single Bayesian update; not a recursive filter, no state maintenance across cycles. The recursive solver mode of §1.1 operates in Phase 2 post-occupancy and is specified separately (§7-§8).

**Algorithm class.** Laplace approximation as the v0.1 default. The forward chain from `aivu_physics` Phase 1 v4.0 and `aivu_dynamic` v0.2 is smooth and deterministic in the parameters; with an informative prior and 48 hours of 1 Hz data the negative-log-posterior is well-approximated as quadratic near its mode for the canonical parameter set. Laplace approximation finds the posterior mode by numerical optimization, computes the Hessian at the mode, and reports the posterior as a multivariate Gaussian with mean equal to the mode and covariance equal to the inverse Hessian. Output: means, full covariance matrix, and the identifiability diagnostics derived from the Hessian's spectrum (§8). The algorithm-class abstraction in the implementation API allows v0.2 or later versions to substitute variational inference or Hamiltonian Monte Carlo for posteriors that turn out to be non-Gaussian; the interface contract `(prior, telemetry_window, hvac_excitation) → (posterior, diagnostics)` is preserved across substitutions.

**v0.2 commitment: NUTS/HMC fallback.** The v0.1 Laplace approximation carries a known failure mode: if the actual posterior is non-Gaussian (for example, bimodal because the `R_eff × η_distribution` ridge is not fully broken by the available data), Laplace converges to one mode and reports a unimodal Gaussian approximation. The §5.7 diagnostics (mode-agreement across restarts, Hessian positive-definiteness) catch most such cases, but a posterior that is non-Gaussian without producing inter-restart disagreement remains a residual risk. **v0.2 commits to NUTS/HMC as the algorithm-class fallback** for any home or operating regime where v0.1 pilot data shows non-Gaussian posterior structure. The algorithm-class abstraction above is what makes this substitution mechanical rather than structural; the interface contract is preserved. Pilot data is what determines whether the fallback is needed for a given home configuration.

**Optimizer configuration.** L-BFGS-B with analytic-where-available + finite-difference fallback for gradients of the forward chain. Convergence tolerance on log-posterior gradient norm. Multiple restarts from prior-perturbed starting points (4 restarts default) to verify the mode is global rather than local. Configurable; pinned at these defaults for the Phoenix-pilot configuration.

**Computational budget.** Per §3.2, the end-of-Day-2 fit has 24-hour wall-clock ceiling and expected actual time in minutes on representative HPM hardware. Laplace with `aivu_dynamic` likelihood evaluation requires ~50-200 forward-chain calls per restart × 4 restarts = ~200-800 total forward-chain evaluations against the 48-hour window. Far below the 24-hour ceiling. The §10 test plan validates this on the HPM target.

## 5.7 Convergence and quality diagnostics

The §5 fit emits convergence and quality diagnostics alongside the posterior. First-class outputs, not optional logging:

- **Optimizer convergence per restart.** The L-BFGS-B optimizer reports convergence status (gradient norm below tolerance, function-value plateau, iteration limit hit, or numerical failure). The fit FAILS if any restart returns a non-converged status. All restart log-posteriors are emitted.
- **Mode-agreement across restarts.** All 4 restarts should converge to the same mode (within numerical tolerance). Restart-to-restart parameter disagreement above `5%` of prior σ on any parameter indicates multimodality or premature local-mode convergence; the fit FAILS in this case. Restart-to-restart agreement is itself a signed diagnostic on the posterior record.
- **Hessian positive-definiteness at the mode.** The Hessian must be positive-definite for the Laplace approximation to be valid (the negative-log-posterior must be locally convex at the mode). Implementations MUST check this and FAIL if any eigenvalue of the Hessian is ≤ 0. A non-positive-definite Hessian typically indicates either (a) the optimizer found a saddle point or local max rather than the true mode, or (b) the posterior is genuinely non-Gaussian and Laplace is the wrong algorithm class for this problem instance.
- **Hessian eigenvalue spectrum.** The full eigenvalue spectrum of the Hessian (or equivalently the singular values of the posterior covariance) is emitted as part of the diagnostics. §8 uses this for identifiability collapse detection per §5.5: a parameter direction with very small Hessian eigenvalue corresponds to a posterior direction that is effectively prior-only.
- **Posterior-prior divergence per parameter** (KL or symmetric KL, implementation choice). Used by §8 for the identifiability-collapse check described in §5.5.

A FAIL on any of the convergence or quality diagnostics halts the commissioning pipeline; the technician escalation path is operational protocol and not legislated here.

## 5.8 Output: the end-of-Day-2 signed posterior record

On successful fit completion, §5 emits a `Day2Posterior` record containing:

- Window start and end timestamps (48-hour Day-1-2 observation window);
- **Programmed fan-mixing schedule** for the window (start time of each fan-on interval, nominal fan speed, total fan-on duty cycle);
- Telemetry hash references for the underlying 1 Hz packets (return-plenum SHT35, 12 terminal SHT35s, 12 terminal Venturis, Eaton breaker, outdoor weather);
- **Per-interval attic temperature observations** (`T_attic^obs(k)` for k = 1..48), derived from the warmup-window terminal probe readings, with their associated uncertainty estimates;
- **Posterior**: mode vector (mean) and full 6×6 covariance matrix from the Laplace approximation, plus per-parameter percentiles derived from the Gaussian. Hessian eigenvalue spectrum at the mode included for downstream diagnostic use;
- Per-parameter identifiability flags from §8;
- Convergence and quality diagnostics per §5.7 (optimizer convergence status, mode-agreement across restarts, Hessian positive-definiteness, Hessian eigenvalue spectrum, posterior-prior divergence);
- **Prior provenance descriptor and prior hash** (per §5.4);
- Forward-chain version identifiers (`aivu_physics` Phase 1 v4.0, `aivu_dynamic` v0.2);
- `aivu_greybox` package version;
- Reference to the valid `FanHeatPass` record from §4 (by content-addressed hash) and the identified `η̂_distribution` it produced;
- `aivu_integrity` inclusion proof for the record itself.

Per §1.3's cryptographic-infrastructure non-goal, signing and commitment is performed by calling into `aivu_integrity`'s API. The record is signed with the HPM per-packet signing key, committed via MMR, appended to the local signed log. Per §2.3, the Digital Birth Certificate signing process consumes this record as the *envelope half, initial signing* and invokes `aivu_integrity`'s 2-of-3 threshold attestation protocol at that signing moment.

## 5.9 Invariants

The §5 batch fit has eight invariants any implementation must satisfy. Part of the §9 invariant set referenced in §1.4.

**INV-FIT12-1 — `FanHeatPass` prerequisite.** §5 MUST NOT consume Day-1-2 telemetry without a valid `FanHeatPass` record on the home's signed log (per §4 INV-FH-1). If no such record exists, §5 raises an error and refuses to run.

**INV-FIT12-2 — Operational-mode adherence.** The Day-1-2 window MUST satisfy: compressor off, heat strip off, OA dampers closed, fan operating on the programmed mixing schedule. Any sample showing nonzero compressor, heat-strip, or auxiliary-heat activity; any sample with `δ_OAD ≠ 0`; or any fan-on/fan-off transition departing from the programmed schedule by more than ±10 seconds disqualifies the window. The fit either re-collects a clean 48-hour window or raises an error if no clean window is available within the commissioning timeline.

**INV-FIT12-3 — Prior provenance is signed metadata.** The end-of-Day-2 posterior record MUST include the prior provenance descriptor and prior hash. Posteriors signed without provenance metadata are invalid; implementations MUST refuse to emit them.

**INV-FIT12-4 — Convergence diagnostics gate the signing.** No `Day2Posterior` record is emitted (and therefore no Digital Birth Certificate envelope-half-initial signing occurs) if convergence diagnostics fail per §5.7. Implementations MUST halt the pipeline rather than sign a non-converged posterior.

**INV-FIT12-5 — Identifiability flags are preserved, not suppressed.** Per-parameter identifiability flags from §8 are part of the signed record. A loose-posterior parameter (effectively prior-only) MUST be signed with its identifiability flag set; downstream consumers (especially §6) MUST consume the flag and treat the parameter accordingly.

**INV-FIT12-6 — Fan-mixing schedule adherence as window validity.** The programmed mixing schedule is part of the window definition, not protocol decoration. Schedule timestamps MUST be signed into the Day-1-2 window metadata, and an external verifier MUST be able to confirm from the telemetry that fan-on/fan-off transitions occurred at the scheduled times within tolerance.

**INV-FIT12-7 — Warmup-window observations preserved as separate data products.** The 60-second fan-on warmup window per interval contains attic-temperature observations that are excluded from the main-channel likelihood but are themselves load-bearing data for the `foam_coupling_factor` identification. Implementations MUST preserve `T_attic^obs(k)` for all 48 intervals as a first-class output channel, not discard the warmup readings as transient noise.

**INV-FIT12-8 — Two-channel likelihood structure.** The §5 likelihood MUST be evaluated on both the attic-observation channel (warmup-window terminal probes) and the main-observation channel (post-warmup return-plenum probe), per §5.3. A §5 implementation that consumes only the main channel and discards the attic channel is non-compliant; the two-state envelope model in Phase 1 v4.0 / `aivu_dynamic` v0.2 requires both for identifiability.

## 5.10 What this section does not specify

- **The Day-4 (Capacity, EER) operating-point map**, which lives in `aivu_physics` Phase 2 Layer 2/3, constructed by the HPM-side protocol runner from the Days 3-4 sweep telemetry against the Fan-Heat-validated terminal stack.
- **The §6 active-perturbation joint refinement** that consumes the end-of-Day-2 posterior as a prior and tightens the loosely-identified parameters under controlled HVAC excitation.
- **The specific values of the ACCA-derived / EnergyPlus / PINN-derived prior** — those live in the prior-construction artifact pointed to by the provenance descriptor, not in this spec.
- **The recursive-mode solver** for Phase 2 ongoing-Cx operation, specified in §7-§8.
- **Envelope-resistance decomposition** into `R_envelope_roof` and `R_envelope_walls` paths. Phase 1 v4.0 §10 has the structural distinction; §5 v0.1 identifies the lumped `R_eff` and defers decomposition to v0.2 if §6 active perturbation provides discriminating SNR.
- **Additional latent-side states** (e.g., separate attic moisture buffering) — `aivu_dynamic` v0.2 handles `W_main` and `W_attic` per its forward-chain specification; §5 consumes whatever the forward chain provides.

---

*End of §5 third-pass draft v3.3. Configuration parameters pinned: 10 min/hr fan mixing schedule at clock-aligned hours; 60s warmup exclusion (turned into the second observation channel); Laplace approximation with L-BFGS-B optimizer, 4 prior-perturbed restarts; mode-agreement failure threshold (5% of prior σ); Hessian positive-definiteness check at the mode. v0.2 commits NUTS/HMC as fallback for non-Gaussian posteriors (added 2026-05-12). Six-parameter canonical set `{R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor}`. Expected posterior tightness ranges per parameter (5% / 5% / 15% / 15% / 25% / 30%) for Phoenix-July passive forcing with two-channel observation, anchored against ~2.5°F (3pm-July) simulation prediction for attic-main differential. σ_T_attic = 0.05°C (conservative pending pilot validation of inter-probe calibration scatter). §6 (active-perturbation fit) opens next.*
