# `aivu_greybox` v0.1 — Section 7: Recursive-mode Phase 2 solver and First Law residual

**Status:** v1.2 (day-numbering reconciliation pass per Reconciliation Workstream Phase 1, 2026-05-16: Days-4-5 references updated to Days-5-6; §6 Day-5 posterior references updated to §6 Day-6 posterior; `Day5Posterior` → `Day6Posterior`; Day-3 (Capacity, EER) map references updated to Day-4; 5-Day commissioning window references updated to 7-Day; INV-REC7-* names unaffected. Substantive content unchanged). Prior v1 draft 2026-05-13. Anchored against §§1-6 and §§8-12 (with §7 the last v0.1 section to land). §7 specifies the heartbeat-cadence recursive solver that operates after the 7-Day commissioning window closes, and the First Law residual self-test that runs alongside it. Per A4: §7 spec is pilot-blocking; §7 code is pilot-blocking only if the homeowner agrees to ongoing measurement at home closing. §7 spec is settled regardless of that decision.

---

## 7.1 Position of §7 in the greybox pipeline

§§4-6 are batch-mode fits over fixed telemetry windows: Fan-Heat (§4) over the Day-1 fan-only window, passive batch (§5) over the Day-1-2 48-hour window, active-perturbation batch (§6) over the Days-5-6 48-hour window. Each emits a single posterior, signs it, and exits. The 7-Day commissioning window closes with the §6 Day-6 envelope-half-final signing.

§7 is what runs afterward. From the moment the homeowner moves in until the HPM is decommissioned years later, §7 operates continuously: consumes 1 Hz telemetry at heartbeat cadence, maintains a recursive posterior over the six canonical parameters, tracks parameter drift, runs the First Law residual self-test against ground truth, and signs the resulting records into the same log §§4-6 wrote into during commissioning.

§7 is the *only* greybox mode that operates during occupancy. The home's behavior is now driven by occupant activity, weather variation, equipment cycling, and seasonal drift — none of which §§5-6 contend with. §7 is structured to handle these conditions while preserving the integrity properties §§4-6 established at commissioning.

Two sub-systems share the §7 namespace:

- **§7.2-7.4** — the recursive solver itself: state, update equation, prior interface, signed-output cadence.
- **§7.5-7.6** — the First Law residual self-test: a per-cycle energy-balance check that is structurally independent of the recursive solver's parameter estimates and serves as a continuous validation channel against ground truth.

The two are designed to fail in distinguishable ways. Solver drift (recursive posterior moves over time) tells you the home is changing. First Law residual drift (energy-balance gap grows) tells you the model or the measurements are wrong. Confusing the two would be catastrophic; §7 separates them by construction.

---

## 7.2 Recursive solver — state and update

### 7.2.1 State vector

The recursive posterior maintains the same six-parameter canonical set as §§5-6: `{R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}`. The state is a multivariate Gaussian over these six parameters, characterized by the parameter mean vector μ_t and the parameter covariance matrix Σ_t.

The state is **not** the home's thermal state (T_main, T_attic, W_main, etc.). The home's thermal state evolves on the seconds-to-minutes timescale and is reconstructed at each heartbeat from telemetry; §7's state is the slower-evolving belief about the home's *parameters*, which drift on weeks-to-months timescales.

### 7.2.2 Initialization

At commissioning-window close, §7 initializes from the §6 Day-6 posterior:

> (μ_0, Σ_0) = (μ_Day6, Σ_Day6)

with the per-parameter identifiability flags from §6 propagated forward as initial-condition metadata. A parameter flagged at end-of-Day-6 as `degraded` or as carrying an identifiability collapse enters §7 with the same flag; §7 does not re-baseline.

If §6 did not run (the commissioning window was aborted or §6 emitted no signed posterior), §7 does not initialize. The home remains in "commissioning incomplete" state until a valid §6 posterior exists.

### 7.2.3 Update equation

At each heartbeat, §7 receives a 1-second telemetry window (one sample per channel from all 13 SHT pods, 12 Venturi flows, Eaton breaker electrical, OA damper, weather station). The update step is:

1. **Predict.** Propagate the current parameter posterior (μ_{t-1}, Σ_{t-1}) through a process model that allows parameters to drift slowly. The process model is `μ_pred = μ_{t-1}`, `Σ_pred = Σ_{t-1} + Q·Δt`, where `Q` is the process noise covariance — a small diagonal matrix expressing the prior belief that parameters drift on weeks-to-months timescales, not seconds-to-minutes. Per-parameter `Q` diagonal values are pinned in §11 with v0.2 derivation status.

2. **Reconstruct thermal state.** From the 1-second telemetry window, compute the current observable thermal state: T_main from the return-plenum probe, T_attic from terminal probes during any fan-on period (fan-off heartbeats skip the attic-channel update), W_main from the return-plenum humidity, and HVAC operating state from the Eaton breaker and Day-4 (Capacity, EER) operating-point map.

3. **Innovate.** Evaluate the forward chain (`aivu_physics` Phase 1 v4.0 + `aivu_dynamic` v0.2) at (μ_pred, observed thermal state, observed HVAC state) for the previous heartbeat, producing a prediction of what the thermal state should be at this heartbeat. The innovation is the difference between predicted and observed thermal state.

4. **Update.** The Kalman-class update step uses the innovation, the observation noise covariance (per-channel SHT and Venturi noise plus §11 values), and the linearized forward-chain sensitivity (Jacobian computed numerically at μ_pred) to produce (μ_t, Σ_t).

The structure is intentionally familiar. §7 v0.1 uses the **Extended Kalman Filter (EKF) formulation** with the forward chain providing the nonlinear measurement function and numerical Jacobians computed at each step. The choice trades sophistication for predictability: EKF behavior under §3.2's 100 ms per-cycle ceiling is well-characterized, and the failure modes (linearization error in high-curvature regimes) are exactly what the First Law residual self-test is designed to detect.

The algorithm-class abstraction from §5.6 applies here too: if pilot data shows the EKF linearization producing systematic bias in high-curvature regimes, the v0.2 fallback is an Unscented Kalman Filter (UKF) or particle filter, with the interface contract `(prior, telemetry_heartbeat) → (posterior, diagnostics)` preserved across substitutions.

### 7.2.4 Fan-off-aware observation model

Phoenix-July post-commissioning operation has the HVAC cycling — fan-on and fan-off intervals alternating throughout each day. The two-channel observation model from §5.3 applies adaptively:

- **Fan-on heartbeat**: both channels valid. Main-channel observation is the return-plenum probe; attic-channel observation is the terminal-probe warmup reading (first 60 s of fan-on per §5.3).
- **Fan-off heartbeat**: main channel observation is valid only if the return-plenum probe has spatial-representativeness (typically yes during occupancy when natural convection mixes the conditioned space — this is a softer requirement than §5's programmed fan-mixing during commissioning); attic channel is unavailable (no terminal warmup signal without recent fan-on).

§7 propagates the heartbeat-type metadata so the update step weights observations appropriately. Stale-channel skipping (don't innovate against a channel that isn't observable this heartbeat) is the v0.1 strategy; weighted-blending of recent observations across heartbeats is v0.2 if pilot data shows it earning its place.

---

## 7.3 Prior provenance and signed-output cadence

### 7.3.1 Prior provenance

§7's prior at heartbeat t is the posterior at heartbeat t-1, which traces back through the recursive chain to the §6 Day-6 posterior, which traces back to §5 Day-2 (the §6 prior), which traces back to §5.4's prior path. The full prior-provenance chain is preserved per INV-FIT12-3 and INV-FIT45-5, propagated through §7 as a per-heartbeat reference in the signed record's metadata.

For storage efficiency, §7 records reference the most recent commissioning-signing record (§6 Day-6) by content-addressed hash rather than reproducing the full chain. An external verifier reconstructs the chain by walking back through the log.

### 7.3.2 Signed-output cadence

Three signing cadences operate concurrently:

- **Per-heartbeat (1 Hz)**: every telemetry packet plus the posterior estimate at that heartbeat are signed via `sign_record` + `commit_to_log` per §12. This is continuous; per-cycle budget includes signing within the §3.2 100 ms ceiling.

- **Per-update-batch (configurable; default daily)**: at end of each calendar day, an aggregated posterior summary record is signed. The summary captures the day's posterior trajectory (start-of-day μ and Σ, end-of-day μ and Σ, intra-day excursions), the day's §8 identifiability report (run once per day at end-of-day rather than per-heartbeat), and the day's aggregate First Law residual statistics. Daily summaries are what downstream consumers (Clearinghouse, insurer, warrantor) typically read; per-heartbeat records exist for forensic re-derivation.

- **Per-significance-event (event-driven)**: when a parameter's posterior crosses a configurable drift threshold (default: posterior mean has moved by more than 2σ from the §6 Day-6 value), a significance-event record is signed *and* invokes `threshold_attest` per §12 — analogous to the commissioning Birth Certificate signings, but for the post-commissioning event ("home's effective R-value has drifted significantly from commissioned baseline"). The drift-threshold value is pinned in §11 with v0.2 derivation status.

### 7.3.3 Threshold-attest moments in §7

The post-commissioning significance events are the only §7 invocations of `threshold_attest`. Per-heartbeat and per-day signing use `sign_record` + `commit_to_log` only. The architectural reason: threshold attestation is reserved for moments where the Clearinghouse and downstream institutional consumers need a load-bearing cohort-significance commitment. Per-heartbeat data is voluminous and locally-verifiable; daily summaries are the typical read surface; significance events are the cohort-level alerts.

In v0.1 with stub-attestation per §12 INV-SIGN12-4, significance-event records carry the stub-attestation flag. Post-pilot `aivu_integrity` swap-in activates live 2-of-3 threshold attestation without §7 code changes per INV-SIGN12-5.

---

## 7.4 §8 invocation cadence

§8 INV-ID8-1 requires all four diagnostics on every greybox posterior. §7 satisfies this with a tiered cadence:

- **Diagnostic 1 (per-parameter prior-only ρ-test)**: evaluated at end-of-day on the daily-summary posterior. The relevant baseline is the §6 Day-6 σ values (the "prior" for the recursive chain), not the per-heartbeat σ that effectively drift downward as data accumulates. A parameter that flags `ρ > 0.95` against the §6 baseline indicates the recursive solver has lost identifiability on that parameter — a structural concern.
- **Diagnostic 2 (per-parameter posterior-tightness state)**: evaluated at end-of-day. The expected tightness baseline for recursive mode is not §5.5 / §6.4 (those are batch-mode tables). v0.1 conservatively uses the §6.4 table as the baseline; a parameter whose §7 daily-summary tightness exceeds 2× the §6.4 expected value emits `degraded` per §8.2. Pilot data will determine whether recursive mode warrants its own expected-tightness table per parameter in v0.2.
- **Diagnostic 3 (Hessian eigenvalue spectrum)**: §7 doesn't compute a Hessian directly; the recursive Σ matrix is the analog. The condition number κ of Σ and the ridge-vector analysis run on Σ at end-of-day, with the same INV-ID8-3 thresholds.
- **Diagnostic 4 (per-parameter posterior-prior KL divergence)**: evaluated at end-of-day against the §6 Day-6 prior — i.e., the cumulative information gained since commissioning. D_KL grows monotonically over time as the recursive solver consumes more data, which is informative on its own merit (slow growth in D_KL on a parameter = home behavior consistent with commissioning; sudden growth = potential drift or fault).

The cadence choice (daily, not per-heartbeat) is the architectural answer to the §8 cost-vs-utility tradeoff in recursive mode. Per-heartbeat §8 would consume budget that §3.2's 100 ms ceiling cannot accommodate; end-of-day §8 is sufficient for the diagnostic purpose (catching multi-hour-to-multi-day drift patterns, not heartbeat-level noise).

---

## 7.5 First Law residual self-test

### 7.5.1 Purpose

The recursive solver in §7.2 is, by construction, an estimate of the home's parameters under a forward-chain model. If the forward chain is structurally wrong — wrong physics, wrong sensor calibration, wrong assumption about HVAC behavior, broken sensor — the solver will produce parameter estimates that minimize the prediction-observation residual *within* the assumed model class, while masking the model's actual disagreement with physical reality.

The First Law residual self-test runs a check the recursive solver structurally cannot run on itself: a closed energy-balance audit against the conservation laws that hold regardless of what model is fit to the data.

### 7.5.2 The energy-balance equation

Over any time interval [t_0, t_1] during which the home's thermal state has returned to (approximately) its initial value, the first law of thermodynamics requires:

> ∫ (Q_HVAC + Q_solar + Q_internal − Q_envelope − Q_infiltration − Q_distribution) dt  ≈  ΔU_home

with all terms in W (sensible) or kg/s (latent), integrated over the interval. The right-hand side ΔU_home is the change in stored internal energy, computed from the home's thermal state at t_0 vs. t_1.

When the integration interval is chosen so that the home returns to near-baseline state (same T_main, T_attic, W_main as t_0 within tolerance), ΔU_home ≈ 0 and the sum of inflows and outflows over the interval must close on itself. Departures from closure are the First Law residual.

### 7.5.3 What gets measured vs. what gets computed

The terms on the left-hand side split into two categories:

- **Directly measured**: Q_HVAC from the Day-4 calibrated (Capacity, EER) operating-point map evaluated at observed operating conditions; Q_solar from the weather station's pyranometer (where instrumented; otherwise from solar position and clear-sky model with cloud correction); Q_internal from occupancy detection plus typical-residential internal-gain tables.

- **Computed via the forward chain at current μ_t**: Q_envelope, Q_infiltration, Q_distribution. These depend on the recursive solver's current parameter estimate.

The residual ε_FL = (measured terms − computed terms − ΔU_home) is what gets signed at each evaluation. ε_FL captures every gap between the model's predicted energy balance and the conservation-law requirement.

### 7.5.4 Evaluation cadence

First Law residual is evaluated at end-of-day. The daily interval is chosen so that diurnal thermal cycling brings the home back to near-baseline state at the same hour each day (typically pre-dawn, when thermal state has equilibrated overnight). Window-bracketing — selecting a daily interval where ΔU_home is minimized — is the v0.1 default; v0.2 may compute First Law over longer intervals (weekly, monthly) for parameter-drift detection on different timescales.

The signed record at end-of-day includes:

- ε_FL value (residual, in W·hr/day or J/day);
- ε_FL relative magnitude (residual / total energy throughput);
- per-term audit (which measured term contributed which fraction of the throughput);
- a flag if ε_FL exceeds a configurable threshold (default: 5% of daily total energy throughput, pinned in §11 with v0.2 derivation status).

### 7.5.5 Interpreting ε_FL

A small ε_FL is necessary but not sufficient for model correctness — coincidental cancellation of errors is possible. A large or persistently-growing ε_FL is strong evidence that something is wrong. Five candidate causes, in rough order of likelihood:

1. **Sensor drift or fault.** SHT calibration drift over years, Venturi clogging, breaker-CT degradation. Detected by single-channel patterns (one channel's contribution to ε_FL grows while others remain stable).
2. **Parameter drift outside the recursive solver's tracking ability.** Solar gain has changed (tree growth shading, replaced window, exterior shading installation); envelope has materially changed (failed insulation, undocumented renovation). The recursive solver may still produce internally-consistent parameter estimates while the underlying home no longer matches the commissioned baseline.
3. **HVAC equipment degradation beyond what the Day-4 operating-point map captures.** Refrigerant loss, compressor wear, fan-motor decline. Detected by HVAC-related terms (Q_HVAC) contributing disproportionately to the residual.
4. **Operating-mode departures from §6 commissioning conditions.** Phoenix-July post-commissioning behavior includes regimes §6's Days-5-6 active perturbation did not cover; the recursive solver may extrapolate from a regime that doesn't quite match.
5. **Model structural inadequacy.** The forward chain's assumptions about envelope dynamics, infiltration, or HVAC behavior may be wrong in ways that didn't surface during commissioning. This is the same misspecification risk the §10 closed-loop testing structurally cannot detect; First Law residual is one of the architectural defenses against it.

The First Law residual record is signed regardless of which cause is operative; downstream consumers (warrantor, Clearinghouse, homeowner-facing service) consume the record and route diagnostic action accordingly. §7 does not adjudicate the cause; it surfaces the gap.

---

## 7.6 First Law residual is structurally independent of the recursive solver

This is the architectural property that makes the First Law residual diagnostic load-bearing rather than ceremonial.

The recursive solver's job is to fit parameters such that the forward-chain prediction matches the observation. If the solver succeeds at that job perfectly, the prediction-observation residual on the *observation channels it uses* (T_main, T_attic, W_main) is small. This says nothing about whether the energy balance closes.

The First Law residual runs the audit on a *different* quantity: total energy in over a closed interval vs. total energy stored. The solver cannot make this residual small by adjusting parameters, because the energy-in terms (Q_HVAC measured from the Day-4 calibration, Q_solar measured by pyranometer, Q_internal from occupancy detection) are observation quantities the solver doesn't fit — they are inputs to the forward chain, not outputs of it. The residual is therefore structurally insensitive to parameter optimization within the forward-chain model class.

What can collapse the First Law residual to zero is: the model class itself being correct. What the First Law residual cannot detect, by construction, is: errors in the directly-measured terms that happen to coincidentally cancel against errors in the computed terms over a given interval. Two structural defenses against that coincidence-cancellation case:

- **Multi-interval consistency.** A residual that's small on Tuesday but large on Wednesday flags the Tuesday cancellation as coincidence rather than as model correctness. Daily-cadence evaluation across hundreds of days gives this naturally.
- **Per-term audit in the signed record.** ε_FL's decomposition into per-term contributions makes the cancellation visible if it ever occurs.

This is the architectural reason §7 is the only greybox section that emits both a parameter-fit residual (from the recursive solver) *and* a conservation-law residual (from the First Law self-test). The two are independently informative; together they are stronger than either alone.

---

## 7.7 Output: per-heartbeat, daily, and significance-event records

§7 emits three record types:

**`HeartbeatPosterior(t)`** — per-heartbeat (1 Hz). Compact: parameter mean μ_t, diagonal of Σ_t (full Σ_t recorded daily, not per-heartbeat, to bound storage), heartbeat timestamp, observation-channel availability flags, reference to most recent `DailyPosterior` for prior-provenance walk. Signed via `sign_record` + `commit_to_log`.

**`DailyPosterior(date)`** — per calendar day. Comprehensive: start-of-day and end-of-day (μ, Σ), intra-day excursion summary, daily §8 identifiability report, daily First Law residual record (ε_FL, decomposition, threshold flag), references to all `HeartbeatPosterior` records contributing to this day (by content-addressed hash range), provenance walk to `Day6Posterior`. Signed.

**`SignificanceEvent(t)`** — event-driven. Emitted when a parameter's posterior crosses the configurable drift threshold (default 2σ from §6 Day-6 value). Comprehensive: the trigger condition (which parameter, by how much, against which baseline), pointer to the time-series of `DailyPosterior` records leading up to the event, summary of First Law residual behavior leading up to the event, identifiability flags. Signed *and* threshold-attested per §12.

---

## 7.8 Invariants

**INV-REC7-1 — §7 MUST NOT initialize without a valid §6 Day-6 posterior.** If commissioning did not produce a valid signed `Day6Posterior`, §7 does not start. The home remains in "commissioning incomplete" state until a valid §6 posterior exists. This is the architectural analog of INV-FIT12-1 / INV-FIT45-1 for the recursive mode.

**INV-REC7-2 — Per-heartbeat update wall-clock MUST stay within §3.2's 100 ms ceiling.** Recursive update step plus per-heartbeat signing (per §12) plus heartbeat-cadence diagnostic computations together must complete within 100 ms. End-of-day computations (§8 invocation, First Law residual, daily summary signing) run asynchronously and are not subject to the heartbeat ceiling; they get a separate ≤ 60 second budget per evaluation.

**INV-REC7-3 — Identifiability flags from §6 propagate into §7 initialization.** A parameter flagged at end-of-Day-6 enters §7 with the same flag set. §7 does not re-baseline a flagged parameter; the flag is preserved until §7's own §8 invocation either clears it (parameter becomes identifiable as recursive data accumulates) or escalates it (parameter that was flagged stays flagged or degrades).

**INV-REC7-4 — First Law residual MUST be computed and signed at end-of-day, regardless of recursive-solver success.** A failed or non-converged recursive update does not exempt the day from First Law residual evaluation. If the recursive solver failed to update on a particular day, the day's `DailyPosterior` carries that failure flag, but the First Law residual is still computed against the previous day's μ_t and signed. The architectural reason: First Law residual is the conservation-law audit independent of the solver; suppressing it on solver failure would erase the one structurally-independent diagnostic.

**INV-REC7-5 — Significance-event records MUST invoke `threshold_attest`, not `sign_record` alone.** Significance events are cohort-significance commitments analogous to commissioning Birth Certificate signings, and require the same attestation surface. Per-heartbeat and daily-summary records use `sign_record` only; significance events escalate. In v0.1 with stub-attestation per §12 INV-SIGN12-4, the significance-event record carries the stub flag; post-pilot swap-in activates live attestation without §7 code change per INV-SIGN12-5.

**INV-REC7-6 — Recursive solver MUST NOT modify the §6 Day-6 posterior.** The §6 Day-6 record is the immutable commissioning baseline. §7 produces new records that *reference* the Day-6 baseline; it does not rewrite or supersede it. The recursive chain proceeds forward from Day-6; the commissioning record stays where it is.

**INV-REC7-7 — Stale-channel skipping is per-heartbeat, not session-level.** A fan-off heartbeat skips the attic channel for that heartbeat only; it does not disable the attic channel for subsequent fan-on heartbeats. The skip-logic operates on the current 1-second telemetry window's observable channels.

**INV-REC7-8 — Algorithm-class abstraction is preserved.** §7 v0.1 uses EKF; v0.2 may substitute UKF, particle filter, or other non-Gaussian recursive method. The interface contract `(prior, telemetry_heartbeat) → (posterior, diagnostics)` MUST be preserved across substitutions, identical to the §5.6 algorithm-class abstraction commitment for batch fits.

---

## 7.9 Out of scope

The following are explicitly out of §7 v0.1:

- **Forward-chain re-training during recursive operation.** §7 fits parameters within an assumed forward-chain model. If pilot data shows the model class itself is wrong, that's grounds for an `aivu_dynamic` revision, not a §7 capability. Auto-detection of structural model error beyond what the First Law residual surfaces is v0.2+ work.

- **Cross-home pattern matching.** When a parameter drifts at a particular home, comparing against similar drift patterns across other Clearinghouse-monitored homes is potentially diagnostic. That comparison is Clearinghouse work, not §7's. §7 surfaces the drift; the Clearinghouse routes the cross-home analysis.

- **Adaptive commissioning re-runs.** If §7 diagnostic flags indicate the commissioning baseline is materially obsolete (major renovation, equipment replacement), the right response is to re-commission, which means running a new §§4-6 cycle. §7 does not initiate this; the operational layer does. §7's role is to make the obsolescence visible via the daily and event records.

- **Per-heartbeat full Σ_t recording.** §7 records the diagonal of Σ_t per heartbeat (parameter-by-parameter uncertainty) but the full covariance only at end-of-day. Storage budget at 1 Hz × 365 days × 6×6 floats × deployed-lifetime years is the constraint; v0.2 may revisit if storage becomes cheaper or if cross-parameter covariance at heartbeat cadence proves diagnostic. v0.1 holds the line at diagonal-only per heartbeat.

- **Multi-zone recursive solver.** v0.1 §7 operates on the two-state attic-main envelope model. Per-room (Scenario R) recursive operation is a v0.2 question and aligns with Phase 2 Part 2a's per-room analysis deferral noted in Unfinished Work Category 2.

- **Compute-time tracking of recursive performance across the deployed lifetime.** Whether per-heartbeat update time grows as Σ_t evolves over months is a v0.2 monitoring concern; v0.1 verifies the §3.2 ceiling once and does not run continuous benchmarks.

---

*End of §7 v1 draft. Recursive solver: EKF formulation, six-parameter state, per-heartbeat update at 1 Hz under §3.2's 100 ms ceiling, end-of-day §8 invocation. First Law residual self-test: structurally independent of recursive-solver fit, end-of-day cadence, energy-balance audit with per-term decomposition. Three record types: `HeartbeatPosterior` (1 Hz, signed), `DailyPosterior` (1/day, signed, includes §8 report and First Law residual), `SignificanceEvent` (event-driven, signed AND threshold-attested). Eight invariants (INV-REC7-1 through INV-REC7-8). v0.1 closes; §7's pilot-blocking scope on code resolves at home closing per A4. With §7 closed, `aivu_greybox` v0.1 spec body is complete.*
