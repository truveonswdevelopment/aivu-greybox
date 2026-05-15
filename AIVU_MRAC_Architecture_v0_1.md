# AIVU MRAC Architecture v0.1

**Status:** Authoritative as of 2026-05-15.
**Author:** Jan-Dieter Spalink, in conversation with Claude.
**Location:** Repository root — read this first.

---

## Why this document exists

Every spec section in AIVU (§1 through §12 today, more later) describes a particular component, protocol, or invariant. None of them, individually, name the principle that organizes the whole system. This document does.

The principle is **MRAC — Model Reference Adaptive Control.** It has been the implicit framing for the AIVU architecture from the beginning. Naming it explicitly here matters because every downstream architectural choice — what parameters we identify, how often we re-fit them, what records we sign, how we manage multi-version cohorts, how we handle the seven-day commissioning vs. years of subsequent operation — falls out of this principle once it is stated correctly.

If a future contributor (human or Claude) reads only one document about AIVU, this should be the one.

---

## The principle

In classical Model Reference Adaptive Control, three components compose:

1. **The plant.** The real physical system under measurement and control. For AIVU, the plant is the residential home: its envelope, its HVAC equipment, the occupants and their behavior, the weather acting on it from outside.

2. **The reference model.** A mathematical model of how the plant is expected to behave. For AIVU, the reference model is `aivu_physics` Phase 1's envelope physics plus `aivu_dynamic`'s integrator plus (eventually) `aivu_hvac_physics`'s equipment model — collectively, the seven-parameter (and eventually larger) physics model that produces predicted indoor state trajectories from weather, HVAC excitation, and the home's static configuration.

3. **The adaptive law.** A mechanism that compares the plant's measured behavior to the reference model's predictions and continuously updates the model's parameters to minimize the discrepancy. For AIVU, the adaptive law is the Bayesian inverse-identification machinery in `aivu_greybox`: the Laplace fit, the §8 identifiability report, the signed records, the §12 attestation chain.

The system as a whole is adaptive: parameters that begin as ACCA Manual J fallback priors converge toward the home's true as-built values as data accumulates, and they keep tracking as the home ages and changes.

**AIVU is not a one-shot characterization tool.** It is a continuously adapting model that maintains an up-to-date physics representation of every home in its corpus, for the operational lifetime of each home under each owner. The seven-day commissioning protocol is the bootstrap moment — the initial parameter identification under controlled excitation — but it is *only* the bootstrap. Everything after the seventh day is continuous adaptation under opportunistic excitation.

---

## The two operational regimes

AIVU operates in two distinct regimes that share the same machinery but apply it differently.

### Bootstrap regime (Day 0 install plus six days of measurement protocol)

Active, structured, controlled excitation. The household has temporarily moved out. **Day 0** is installation: AIVU equipment is installed, sensors are calibrated, the home is prepared for measurement. **Days 1 through 6** are the measurement protocol itself, with a clean three-part functional separation:

- **Days 1–2 — Passive envelope observation.** No active HVAC excitation; only fan-mixing for thermal equilibration. The envelope's natural response to weather is observed without confounding HVAC drive signals. Produces **Day2Posterior**, the envelope parameter set's initial value from passive forcing.

- **Days 3–4 — HVAC system commissioning.** Equipment characterization: capacity sweeps, fan-heat fit, COP characterization, sensible/latent split. This characterizes the HVAC *as the active excitation source* for the subsequent envelope work. Produces **Day4Posterior**, the HVAC equipment characterization record.

- **Days 5–6 — Active envelope testing using HVAC.** The now-characterized HVAC equipment drives the envelope through a deliberate four-phase perturbation protocol (continuous cooling drive, decay, reverse drive, closing observation). This refines the envelope parameters identified passively in Days 1–2 by exploiting the controlled excitation HVAC provides. Produces **Day6Posterior**, the envelope parameter set's bootstrap-final value.

Each of these signed records is the parameter set's *initial value* after bootstrap. The records are signed via the §12 attestation chain with corresponding `AttestationMoment` enumerations.

The bootstrap regime is necessary precisely because the home arrives with no prior measurement history. With nothing better than ACCA Manual J table values as the starting prior, the controlled excitation gives the adaptive law enough information per unit time to pull the parameters out of fallback-prior space and into the home's actual physical neighborhood.

> **Reconciliation note (2026-05-15):** The existing greybox §1–12 spec set uses inconsistent day-numbering in places. Notably, `aivu_greybox.active_fit` references `day2_posterior_record_hash` and `day3_map_record_hash`, implying the HVAC characterization landed at Day-3 rather than Day-4, and that the active envelope fit at "Day-5" rather than "Day-6." That labeling does not match the 2+2+2 functional separation described above and needs to be reconciled in the greybox spec. The MRAC framing here (Days 1–2 / 3–4 / 5–6, producing Day2Posterior / Day4Posterior / Day6Posterior) is authoritative; the greybox spec sections referenced above will be updated in a subsequent reconciliation workstream. Until that workstream lands, code-level field names in `active_fit.py` etc. retain their existing labels for backward compatibility, but the *semantics* match this document's framing.

### Continuous regime (Day 7 onward, indefinitely)

Passive, opportunistic, condition-gated re-fitting. The household has moved back in. The HVAC operates under normal occupancy-driven control. Weather happens as it happens. AIVU is no longer driving the home; it is *watching* the home and harvesting parameter-identifying information whenever ambient conditions provide it.

This regime is the lifetime mode. The parameter set continues to evolve — slowly, under quality-gated update events — as the home ages, as components degrade, as window seals weather, as duct insulation settles, as recessed-can penetrations accumulate. The same Bayesian machinery that ran the bootstrap fit continues to run, but with the bootstrap posterior as the prior and with new telemetry-window data continuously updating the running posterior.

**Critical insight:** Under continuous mode, the home is *constantly being re-commissioned*. The 7-day "commissioning" framing is a useful shorthand for what happens to a brand-new home on the AIVU service, but it is misleading if it suggests that commissioning ever stops. Commissioning never stops. It just becomes opportunistic instead of deliberate.

---

## What makes a window "good enough" — the conditions gate

The bootstrap regime forces favorable conditions for parameter identification through the controlled excitation protocols. The continuous regime cannot force conditions, so it must instead *recognize* favorable conditions when they occur naturally and harvest them.

The **conditions gate** is the logic that classifies each telemetry window as "good enough to update parameter X" or "not good enough." It is parameter-specific because different parameters identify under different physical conditions.

**Per-parameter conditions-gate sketch** (illustrative, not authoritative — actual thresholds are downstream spec work):

| Parameter | Identifying conditions | Why |
|---|---|---|
| R_opaque | Night hours, low solar gain, occupancy quiescent | Steady-state envelope conduction dominates; gain noise from occupants is minimized |
| U_fenestration | Clear-sky days with high direct solar | Solar gain through windows is the discriminating signal vs. opaque elements |
| C_house | Long decay tails after HVAC shutoff | The thermal time constant emerges from the relaxation curve |
| C_stack | Large indoor/outdoor ΔT, low wind | Stack-driven infiltration is the dominant driver; wind contribution is suppressed |
| C_wind | High wind, modest ΔT | Wind-driven infiltration is the dominant driver; stack contribution is suppressed |
| C_w | Humid weather with HVAC running steady | Latent moisture transfer through the envelope is the observable signal |
| ceiling_coupling_factor | Hot sunny afternoons with high attic temperature | Drives the largest signal through the attic-coupling path; identifies bypass paths |

**A key property of the conditions gate:** it is *enabling*, not *required*. The continuous fit does not stop when conditions are unfavorable; it continues to update the running posterior using whatever information the current window provides, weighted by the information content available. The conditions gate determines when the running posterior gets *promoted* to a new signed record, not when the fit happens.

This is why AIVU's machinery does not need to "wait for good weather" to operate. It always operates. The gate decides when to publish a new authoritative record from the running posterior — analogous to a "stable" build in a CI/CD pipeline versus the nightly builds that run continuously.

#### Multi-event canonicalization requirement

A single gate-passing window is not sufficient to canonicalize a parameter update. **Two or more independent gate-passing windows** must propose updates that converge to the same parameter neighborhood before the update becomes canonical and gets signed into a new record.

The architectural reasoning: a single window might be informative due to a transient anomaly — a malfunctioning sensor, an unusual occupancy event, a weather event that looks normal in aggregate but isn't. Requiring confirmation from a second (or more) independent window protects against single-window false positives that would otherwise propagate into the signed record chain.

This requirement also gives the system a natural smoothing property: parameter changes accumulate gradually as multiple consistent observations build evidence, rather than ratcheting on whatever the first quality-gated window happened to suggest. The running posterior continues to be updated by every window the fit consumes, but the *canonicalization* event — the moment a new signed record is published — waits for cross-window confirmation.

The specific value of N (two events, three events, parameter-specific N) is downstream tuning, not architecture. The principle of multi-event confirmation is architectural.

---

## The running posterior

Underlying both regimes is a single piece of state: the **running posterior** over the canonical parameter set, maintained continuously by HPM for each home in the corpus.

The running posterior is a Gaussian (mean + covariance) over the seven (or future-N) parameters. It is updated by the same Laplace machinery `aivu_greybox` uses for bootstrap fits, but applied incrementally:

- New telemetry arrives
- HPM constructs a window from the recent past
- The window plus the current running posterior (as prior) goes into the Laplace fit
- The fit returns an updated posterior
- The updated posterior becomes the new running posterior

This is structurally identical to the §5 / §6 fits — the only difference is that §5/§6 use the ACCA Manual J fallback as the prior (cold start), and continuous-mode fits use the previous running posterior as the prior (warm start).

**Signed records as snapshots.** Day2Posterior, Day4Posterior, and Day6Posterior are not the running state. They are *snapshots* of the running state at protocol-defined moments: Day2Posterior is the running posterior at the end of the passive envelope-observation phase (Days 1–2); Day4Posterior is the running posterior at the end of the HVAC commissioning phase (Days 3–4); Day6Posterior is the running posterior at the end of the active envelope-testing phase (Days 5–6). Future signed records produced by the continuous regime are snapshots taken when the conditions gate plus multi-event confirmation promote a parameter-update event.

The running posterior itself is internal HPM state. It updates continuously. It does not get signed at every update — that would produce a meaningless flood of records with marginal changes. Signing happens at canonicalization events, which are sparse by design.

**Why this matters for record integrity.** Every signed record carries a `prior_hash` field linking to whatever record was used as its prior. In bootstrap mode, Day2Posterior's prior_hash points to the ACCA Manual J fallback (or the BDT-supplied initial prior); Day4Posterior's points to Day2Posterior; Day6Posterior's points to Day4Posterior. In continuous mode, each new signed record's prior_hash points to the *previous* signed record for the same home. The chain is unbroken: any signed record can be traced backward through the chain to the home's bootstrap records. This is how AIVU achieves auditability across years of continuous operation without signing every minute of telemetry.

---

## What this implies for the existing spec set

The §1-12 specs were drafted with the bootstrap regime as the primary use case. Some are bootstrap-only; some extend cleanly to continuous mode; some need explicit extension.

**Bootstrap-only specs (these define the Day-0-plus-six-day protocol):**
- §3 — fan-heat protocol (executed during HVAC commissioning, Days 3–4)
- §4 — fan-heat fit (the HVAC characterization that becomes Day4Posterior, Days 3–4)
- §5 — passive batch fit (the Days 1–2 controlled passive observation that produces Day2Posterior)
- §6 — active perturbation (the Days 5–6 active envelope testing using HVAC, producing Day6Posterior)
- §11 — operational-infiltration parameterization (the parameter set itself, which extends to both regimes — this section's definitions are not bootstrap-only)

**Specs that extend cleanly to continuous mode:**
- §5's Laplace machinery (the inverse-identification math is identical; only the prior source changes)
- §6's phase-aware likelihood (becomes a special case of a more general "phase-aware" or "conditions-aware" likelihood)
- §8 — identifiability report (per-update diagnostic, same form)
- §10 — closed-loop validation (extends to continuous-mode validation against ground-truth-where-available)
- §12 — signing and attestation chain (every signed record uses the same machinery, regardless of which regime produced it)

**Specs that need explicit extension for continuous mode (future work, not on tonight's critical path):**
- The conditions-gate logic itself — currently no spec section. Probably becomes a new §13 or sits inside the HPM scoping work.
- The running-posterior update cadence policy — likely an HPM-level spec.
- The continuous-mode AttestationMoment enumeration — currently §12's moments are bootstrap-specific. The continuous regime will need its own moment values.
- The translation/migration logic when running posteriors cross schema versions — possibly a `schemas/` compatibility layer per the multi-version cohort discussion.

---

## What this implies for multi-version cohort management

Earlier in the 2026-05-15 session, the question came up of what happens when AIVU evolves its schema (six → seven parameters in the §11.2 amendment, eight parameters someday, etc.) while older-cohort homes are running on previously-signed records. The MRAC framing significantly relaxes the cohort-migration problem.

**Without MRAC framing:** a home's parameter values are frozen at bootstrap. Schema migration means re-fitting the home, which requires re-commissioning, which requires displacing the occupants for seven days. Operationally prohibitive between owners.

**With MRAC framing:** a home's parameter values are continuously updated post-bootstrap. The running posterior accumulates information across ownership tenure. Schema migrations can leverage the running posterior as a translation prior:

- Adding a new parameter: the new parameter starts at the cold-start fallback, the existing parameters continue at their current running posterior values, and the conditions gate identifies the new parameter opportunistically as conditions allow. No re-commissioning.
- Splitting a parameter: the running posterior on the old parameter becomes a prior for both new parameters, with cross-correlation refined as new data arrives. No re-commissioning.
- Reinterpreting a parameter (changing what it physically represents): the running posterior may or may not translate forward cleanly. This is the case where re-commissioning at the next ownership transfer is the cleanest path.

**The natural re-commissioning window remains the ownership-transfer moment.** A new owner opting into the AIVU service re-commissions the home, which can use the latest schema. So schemas don't have to be supported indefinitely — only across the homeownership-tenure distribution of the homes currently in the corpus.

This is significantly easier than "every schema ever, forever," which was my initial framing in that conversation. The MRAC continuous-adaptation pattern is what makes the relaxation possible.

---

## What this implies for HPM (the orchestrator yet to be specified)

**HPM is the MRAC process manager.** That is its fundamental architectural role. It is not merely the data-flow coordinator between BDT, Clearinghouse, and the home's measurement equipment; it is the component that *operates the adaptive control loop itself* — running the fits, maintaining the running posterior, evaluating the conditions gate, accumulating multi-event confirmations, and emitting signed records when canonicalization events occur. Everything HPM does serves the MRAC adaptation cycle.

HPM has not yet been specified — that work is a separate workstream from this document. But this document establishes some structural requirements that HPM's spec will need to honor:

1. **HPM maintains the running posterior per home.** Not the BDT, not the Clearinghouse — HPM owns the running state. The running posterior is per-home, internal to HPM, and updates continuously.

2. **HPM operates the conditions gate and the multi-event confirmation logic.** Recognizing favorable windows, deciding when individual windows propose parameter updates, accumulating cross-window confirmation evidence, and deciding when to promote a confirmed update to a signed record — all of this is HPM's responsibility.

3. **HPM handles regime transitions.** The transition from bootstrap (Day 0 install plus Days 1–6 protocol) to continuous (Day 7 onward) is a state machine HPM manages. Future regime transitions — for example, "the home is being re-commissioned because the owner changed" — also live in HPM.

4. **HPM is the source of truth for "what schema is this home on."** A home's schema version is HPM state, signed into every record HPM produces. Migrations happen by HPM updating its internal schema for a particular home and the next signed record carrying the new schema version.

5. **HPM emits signed records, but signing itself is the §12 attestation chain.** HPM constructs the record content; §12 handles the threshold-signing and the OpenTimestamps anchoring. The interface between HPM and §12 is the canonical signed-record format.

These are scoping notes for the HPM specification work, not commitments about API shape or implementation detail.

---

## What this document does NOT specify

To keep this document focused on the framing principle, several things are deliberately out of scope:

- **Numerical conditions-gate thresholds.** Which specific values of solar gain, wind speed, occupancy state, ΔT, etc. constitute "good enough" for each parameter. This is downstream calibration work — likely a §13 spec or HPM-level configuration.

- **The running-posterior update cadence.** Whether the fit runs every minute, every hour, every observation window, or under some other policy. Probably a tunable in HPM with sensible defaults.

- **The API shape of the continuous-fit subsystem.** Whether it's a streaming process, a periodic batch job, an event-driven trigger system. An implementation choice for HPM.

- **The schema-migration translation logic.** How exactly a running posterior on schema vN maps to a prior for schema vN+1 when the parameter set changes. Per-migration work, not a general framework.

- **The bootstrap vs. continuous-regime signature of the §12 AttestationMoment enumeration.** Continuous mode will need its own attestation moments; today's enumeration is bootstrap-only. Drafting the new moments is downstream work.

Each of these is a real specification task, and several of them are on the critical path to first-deployment. They are explicitly *out of scope here* because conflating principle with implementation makes both harder to reason about.

---

## How to use this document

When designing any future AIVU component, ask:

1. Which MRAC role does this component fill — plant interaction, reference model, adaptive law, or orchestration?
2. Does this component need to work in both the bootstrap and continuous regimes? If only one, why?
3. If it produces a signed record, what gate-promotion event corresponds to that signing? Is it a bootstrap-protocol moment or a continuous-regime event?
4. If it carries state, is that state per-home running state, per-cohort statistics, or global system state?
5. If it changes schemas in the future, how does the MRAC continuous-adaptation pattern help the migration?

Answers that don't fit cleanly into this framing are warnings: either the component is mis-scoped, or the framing itself needs to evolve. In either case, surface the friction explicitly rather than smoothing it over.

---

## Version history

- **v0.1 (2026-05-15)** — Initial authoritative version. Names the MRAC principle, establishes the Day-0-install-plus-six-day bootstrap protocol with 2+2+2 functional separation (passive envelope / HVAC commissioning / active envelope), distinguishes bootstrap from continuous regimes, sketches the conditions-gate concept with multi-event confirmation requirement, establishes the running posterior, frames HPM as the MRAC process manager, identifies implications for spec extension and multi-version cohort management. Notes the day-numbering reconciliation needed in the existing greybox spec (`active_fit.py`'s `day2_posterior_record_hash` / `day3_map_record_hash` fields) as a tracked downstream workstream.

Subsequent revisions will likely add: explicit conditions-gate threshold rationales as they get calibrated, the continuous-regime AttestationMoment enumeration once §12 is extended, HPM scoping language once that workstream begins, and references to specific Cx pilot findings that exercise the framing in practice.

---

*This document is the project's organizing principle. It sits above the §1-12 spec sections, above the implementation packages (`aivu_physics`, `aivu_dynamic`, `aivu_greybox`, `aivu_hvac_greybox`, `aivu_hpm`), and above the governance documents (Working Preferences, Pilot Roadmap, Dependency Map). When in doubt about an architectural choice, return to this document first.*
