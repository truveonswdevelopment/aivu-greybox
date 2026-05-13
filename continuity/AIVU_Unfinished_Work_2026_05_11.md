# AIVU Unfinished Work

**Version:** 2026-05-11 (Phoenix pilot pivot — greybox §4 closed, §5 drafted to v3.2, §6 drafted to v2; revised from earlier 2026-05-11 entries, which revised 2026-05-10, which revised late-April triage)
**Audience:** JDS, and whatever Claude session is reading this.
**Purpose:** What is genuinely pending, organized so prioritization decisions are tractable.

---

## Reading rules

1. **This is a working document.** Update it at the end of any session that closes or opens an item. Treat it like a TODO list with structure, not a deliverable.
2. **No bookkeeping ceremonial.** No `[OPEN]`/`[CLOSED]` markers, no decision IDs. Items are present until they aren't.
3. **The categories are the structure that helps prioritization.** Don't dissolve them into one flat list; the categories distinguish *kinds* of unfinished work that have different costs, risks, and dependencies.
4. **The axes prioritization at the bottom is the load-bearing framing.** Specific items move; the axes are durable. Six axes as of May 11 (started as four; Axis 5 added May 10, Axis 6 added May 11).

---

## Category 1 — Spec-locked, not yet coded

The biggest gap by volume. After the Phoenix pivot (May 11), reordered by pilot-blocking status.

**aivu_greybox v0.1 spec — sections 7–12 (plus §5/§6 awaiting final review).** **Top pilot-blocking item.** Sections 1–3 were drafted April 27 (recovered May 10). §4 (Fan-Heat Consistency Check) closed May 11, v3. §5 (Day-1-2 passive-observation batch fit) drafted May 11, v3.2 — six-parameter canonical set `{R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor}` (extended from §1.2's five to match Phase 1 v4.0 / `aivu_dynamic` v0.2 two-state attic-main model), 10 min/hr fan mixing protocol with return-plenum + terminal-warmup two-channel observation model, Laplace approximation algorithm per April 27 §6.2 lock, EnergyPlus-ahead-of-ACCA prior preference. §6 (Day-4-5 active-perturbation batch fit) drafted May 11, v2 — direct HPM compressor/fan command authority, four-phase protocol (cooling drive 18h / cooling decay 6h / reverse drive 18h / final close 6h), aspirational-not-strict steady state framing, `η_distribution` held at §4 Day-1 value (joint refinement deferred to v0.2). Both §5 and §6 await JDS final review in next session before being formally closed. §§7-12 are the remaining operational definitions — recursive-mode Phase 2 solver + First Law residual (§7), identifiability collapse and posterior tightness (§8), invariants consolidation (§9), test plan (§10), common utilities including the `ε_FH` and `σ_T_attic` derivations (§11), and signing chain (§12). After greybox code is done, the ongoing-Cx slice falls out of §7 without separate work.

**Phase 2 v1 — capacity demand + equipment output + duct delivery (whole-house resolution).** Spec locked across 8 increments on April 23. Code never started. **Scope narrowed by Phoenix pivot:** the slice that is pilot-relevant — greybox in recursive mode against live telemetry — is folded into the greybox work above. The remainder (capacity demand + equipment output + duct delivery as standalone whole-house implementations, 29 invariants) returns as post-pilot work. PROJECT_STATE's original "begins next session" framing is superseded.
- `code/phase2/capacity_demand/` (Layer 1) — postponed past pilot
- `code/phase2/equipment_output/` (Layer 2) — postponed past pilot
- `code/phase2/duct_delivery/` (Layer 3) — postponed past pilot
- 29 invariants to validate against — postponed past pilot

**aivu_integrity v0.1 spec.** Architectural decisions are locked in Delta 7 (§6 of the Addendum in v3.0). **Scope narrowed by Phoenix pivot:** for the pilot, what has to exist is per-packet HPM signing + local append-only signed log. The MMR commitment primitive, OpenTimestamps anchoring to Bitcoin, 2-of-3 threshold attestation, and the aivu_integrity package as a coherent whole all return as post-pilot work. The pilot floor is the evidentiary floor; the v0.1 spec covers what comes after.

---

## Category 2 — Spec-locked, explicitly deferred to v2

Items that have a clear spec but were intentionally pushed past v1 to keep scope bounded.

**Phase 2 Part 2a — per-room analysis.** L5.1–L5.9 + L-Cross.2 + L-Cross.3. Deferred to v2 by JDS authorization on April 23. The V752 demo workaround (`per_zone_v752.py`) substitutes for it for now. Real solution would replace the workaround.

**Multi-zone integrator (Scenario R).** Per-room T_in trajectories with inter-room thermal coupling. Substantial structural lift. Listed as "second-meeting deliverable" in V752 context.

---

## Category 3 — Physics gaps in current code

Self-contained code-level extensions to the existing implementation. **Both items now Phoenix-pilot-blocking (May 11) and fold naturally into greybox code work rather than running as separate items.**

**ERV heat-recovery effectiveness in `infiltration.py`.** Currently treats whole-house mech vent as exhaust-only with no recovery. Half-day to extend. Discussed for Beazer pilot calibration; the pilot home will calibrate empirically, but the code change is independent of any pilot. Pilot-blocking: needed so simulated and measured loads can align during ongoing Cx.

**Latent-side RealCycle excitation that respects available moisture.** Currently constant-rate, which causes W_in negative-overshoot in dry conditions and would also misbehave in humid Houston with low T_in. Half-day build. **Phoenix-blocking specifically:** Phoenix in July hits the exact low-T_in dry-conditions case where the constant-rate model produces negative W_in overshoot. Fix folds into greybox code work.

**Note on architectural alignment (May 10):** The v3.0 architecture doc clarified that ERV / depressurization correction is *post-occupancy* behavior, not 5-Day-window behavior. The code-level physics gap is unchanged; the conceptual placement is now sharper.

---

## Category 4 — Open items from extraction work

**IndoorClimateObjective schema reconciliation against Increment 1 §4.2.** Listed as the one remaining open item from PROJECT_STATE.

**Status note (May 10):** The greybox spec §1.3 (drafted April 27, recovered May 10) explicitly addresses R as design-intent specification distinct from plant identity: *"R is the IndoorClimateObjective object … authored by the BDT … aivu_greybox does not author, modify, or hold R. It produces plant-identity parameters."* This may have already resolved the open item. **Verify before next code session** by reading greybox spec §1.3 against Increment 1 §4.2 directly.

**Greybox §1.2 canonical parameter set is incomplete (surfaced May 11).** §1.2 lists five parameters `{R_eff, C_house, cfm50, F_slab, κ_buffer}` as canonical. The actual `aivu_dynamic` v0.2 inverse-fit target set (line 35) includes six: `{R_eff, C_house, cfm50, F_slab, C_w, foam_coupling_factor}`. The `foam_coupling_factor` parameter is load-bearing for the Phase 1 v4.0 §10 two-state attic-main envelope model, which `aivu_dynamic` v0.2 implements. `κ_buffer` vs. `C_w` is a naming question — `C_w` is the lumped moisture capacity in the state-space sense (paired with `C_house` sensible capacity); whether `κ_buffer` in §1.2 means the same thing under a different name or a different parameter entirely is unresolved. §§5-12 of greybox use the corrected six-parameter set with `C_w` naming. A small §1.2 revision is queued — name `foam_coupling_factor` explicitly, settle the `κ_buffer`/`C_w` question, document in §1.2's "Additional parameters may be committed at code-implementation time" caveat that this revision is the documentation of that commitment.

---

## Category 5 — Non-code work that still matters

**Sales tool UI.** Builder-facing front-end exposing the Part 1a/1b/foam-vs-vented landscape we've planned. Not started. Status unchanged from April triage. Not pilot-blocking.

**Pilot home instrumentation plan.** What sensors, what cadence, what calibration protocol. Discussed at high level; not nailed down. Hardware itself is already tested and installable ahead of the Cx window — this is the operational plan around the hardware, not the hardware procurement.

**5-Day commissioning protocol — *architectural* version.** **Status changed (May 10).** No longer "not written." Substantially documented across (a) v3.0 architecture doc Phase 1 section (three sub-phases described in detail), (b) v9.5 OS doc Implementation section, and (c) Editorial Addendum Delta 4 (Fan-Heat Consistency Check elevated to required Day-1 gate).

**5-Day commissioning protocol — *operational* version.** **Phoenix-pilot-blocking (May 11).** What's documented above is the architectural description — what the protocol is and why. What's *not* yet written is the field-deployable operational version: the technician checklist, the equipment-prep instructions, the failure-handling procedure when (e.g.) a sensor calibration fails Fan-Heat at 9 AM on Day 1. This is the version a Beazer site lead would actually use. Two days of focused writing, late in the timeline. JDS-authored work that Claude assists with — the operational nuance is largely in JDS's head.

**Open-source verification library release (5d-iii).** Referenced in v3.0 §6.5 as a commitment. Architectural decision locked in Delta 7. **Explicitly postponed past pilot (May 11).** For a single-home pilot there are no external verifiers needing to confirm AIVU's records independently of AIVU. Bigger than it looks for v0.1 of aivu_integrity: external verifiers (insurance, courts, regulators) need this code to exist before Delta 7's stronger admissibility argument is operationally true. Returns as work after the pilot lands.

---

## Category 6 — Quality debt

Mostly V752-specific. Lower priority than the categories above, but worth listing so it doesn't accumulate silently.

**Every TBD in `v752.py`.** Zone floor areas for BR2 / BR3 / Bath2 / Service Cluster are explicit estimates. The Wrightsoft data captured during V752 prep supersedes some of these and could be backfilled.

**Per-room CFM allocation in `per_zone_v752.py`.** Hand-transcribed from M-5.0; could be cross-checked against source data.

**ERV heat-recovery effectiveness flagged as known conservative simplification in the methodology doc.** Transparent, not technically debt — but the same item as Category 3, and worth resolving when Category 3 is addressed.

---

## Category 7 — Future packages (architecture only)

Named in v3.0 of the architecture doc as future packages. Scoped at architecture-doc level only — no spec, no code. **Phoenix pivot (May 11) splits both into pilot-needed slices and postponed remainders.**

**aivu_pinn — Born Educated PINN training pipeline.** The cloud-side training infrastructure. Architecture says: trains the PINN once across the full parametric space (climate × orientation × envelope × duct topology × equipment × hour); refines per-cohort as posteriors arrive from the field. **For the Phoenix pilot: skipped entirely.** Rationale: for one home, an EnergyPlus run on the Beazer floor plan would produce a result whose only use is to seed a prior that greybox overwrites in two days under Phoenix-July SNR. Use a defensible default prior (ACCA Manual J-derived values for Phoenix 2B single-family of the relevant size class). The architectural commitment to Born Educated is preserved as a v0.1 commitment for aivu_pinn post-pilot. Spec drafting not started; not pilot-blocking.

**aivu_hpm — real-time controller, sensor stack, orchestrator, OTA mechanism.** The HPM's own software stack. Hosts aivu_greybox locally; runs the bounded MRAC inner loop; authors the modification requests that uplink posteriors to the BDT. **Pilot-needed slice (May 11):** the HPM-side protocol runner described in the path recommendation — protocol sequencer, telemetry recorder, greybox host, Day-3 (Capacity, EER) operating-point map computation, per-packet signing, local append-only log. **Postponed:** OTA, MRAC inner loop, BDT modification-request authoring, fleet orchestration — none of which are pilot Cx or ongoing Cx machinery. The eventual aivu_hpm v0.1 package returns as post-pilot work.

The pilot HPM software is named for what it is (protocol runner + telemetry recorder + greybox host), not pre-named as aivu_hpm v0.0 — to avoid the trap of the pilot scaffolding being mistaken for the start of the real package.

---

## Category 8 — Deferred decisions (not unfinished, but tracked)

Items that *could* be advanced but where deferral was a deliberate call.

**Real financial model.** Explicitly deferred to post-pilot per JDS call on May 10. Numbers in v9.5 OS doc are illustrative, not load-bearing. The right time is when measured COGS replaces assumed COGS — same epistemic discipline AIVU applies to the residential industry.

**Hovnanian 8650 vs 8560 reference home identifier.** Reference removed from v3.0 architecture doc by generalization (May 10). The original Hovnanian floor plan documentation will resolve which identifier is canonical when it becomes operationally relevant. Not blocking anything currently.

---

## Category 9 — Organizational / infrastructure

Not engineering work in the strict sense, but real deliverables on the project's operating system.

**GitHub repo population.** Repo structure exists per JDS confirmation (May 10). Population per the three-layer structure pending: `current/` (v3.0, v9.5, Working Prefs v0.2, Distillation v0.2, this document), `archive/` (prior versions of architecture and OS docs), `decisions/` (April 27 Editorial Addendum, Delta 7, Session Handoff, today's session log graduates here if it captures a structural decision), `session_logs/` (today's log + future ones), `specs/` (greybox spec sections 1–3, future package specs).

**Session log discipline going forward.** One log per substantive session, written at session end, dated. The 2026-05-10 log is the first entry; the discipline is to write the next one.

**Claude Code installation.** Future, after GitHub repo workflow stabilizes. Not urgent.

**Incoming CEO search.** Begins during Tranche 1, runs in parallel with the pilot. The right candidate is the one who will close Series A — not someone hired into the role after the round lands. Sized correctly, the Tranche 1 capital ask includes the runway to conduct a real search alongside the pilot work. JDS transitions to Chief Architect on close of Tranche 2.

---

## Category 10 — Strategic posture commitments

Architectural and commercial commitments that raise the wall against competitors and shape how AIVU appears to Tier-1 VC reviewers. Not engineering work; not exit work; durable commitments about how AIVU positions itself. The Path A engineering sequence runs alongside this category, not in competition with it.

**Clearinghouse as a regulated third party.** The Architecture of Irreversibility already commits to audit-firm methodology validation. Going further means positioning the Clearinghouse under a fiduciary posture — legally obligated to neutrality, analogous to a credit-rating-agency NRSRO designation. Concrete first step during the pilot: one state energy commission (CEC is the natural candidate) and one insurer formally citing the Digital Birth Certificate format. Status: commitment-stage; no work begun.

**aivu_integrity as an open standard.** §6.5 of the v3.0 architecture doc already commits to open-sourcing the verification library. Going further means publishing the commitment format (MMR layout, packet schema, attestation protocol) as a formal specification and donating it to a credible standards body (NIST or IEEE candidates). Status: depends on aivu_integrity v0.1 spec (Category 1) and the 5d-iii release (Category 5) existing first. Standards-track work begins after those land.

**Builder-side cohort exclusivity, formalized.** The v9.5 OS doc mentions "time-limited exclusivity for new subdivisions" in passing. Making this load-bearing means structuring the builder contract so exclusivity is granted at the *cohort* granularity (ASHRAE zone × price band) for a defined window (~36 months), in exchange for the builder paying for HPM hardware. Forces the first-mover builder advantage and creates a real cost for any competing builder to wait. Status: commercial-contract work, not yet begun. Naturally lands during pilot-builder negotiation.

**Sensor and protocol IP — patent filings.** The supply-tail Venturi at Mixed Air Truth, the in-duct return T/RH probe placement, the Fan-Heat Consistency Check as a Day-1 instrument-validation gate, and the dual-track commissioning *sequence* (envelope → HVAC-as-instrument → high-SNR envelope) are patentable as methodology. Three to five well-drafted patents on commissioning protocol and sensor-placement logic create a barrier capital alone can't dissolve. File during Tranche 1, before Series A. Status: not begun. Requires patent counsel engagement.

**Synthetic training set as a separable IP asset.** The training set generated by aivu_physics and aivu_dynamic across the deliberately-sampled parametric space is an asset distinct from the PINN trained on it. Framing it as a separable layer (licenseable, narrow-slice-disclosable to regulators, verifiable against competitor models) is a commitment, not a code change. Status: framing work; can be done independently of any engineering progress. Belongs in the next OS doc revision.

**Homeowner data ownership posture, explicit.** Architecture already supports it (§3.5 Atomic Decoupling, the Zero-Trust Data Vault, the supersession of the v2.5 institutional-custody model). The commitment to make visible: the homeowner owns their home's raw data, AIVU operates as cryptographically-revocable custodian, the Exclusive Source Data License is a *delegation* not a transfer. Defensive against future privacy regulation; offensive against the "Equifax of homes" attack. Status: architecture-doc-level statement work; can be added to the next OS doc revision.

**Role-name decision: Chief Architect (vs. Non-Executive Chairman).** What JDS keeps doing post-transition — dual-track physics, integrity model, Clearinghouse adjudication logic — is irreplaceable architectural work, not honorific oversight. The role name should reflect that. Current v9.5 language ("Non-Executive Chairman governing the BDT architecture") reads administrative; "Chief Architect" reads functional. Status: one-sentence edit to v9.5, pending JDS decision on name (Chief Architect / Founding Architect / Chief Scientist / Founder & Chairman all defensible).

---

## Prioritization — six axes (axes durable, specifics updated May 11)

The categories above are the *what*. The axes below are the *what should drive the choice*. None of the axes is the right answer alone; they have to be weighed against each other based on factors that change between sessions (cash runway, pilot timing, customer-engagement timing, JDS's energy and focus on a given week).

**Axis 1 — Pilot-engagement readiness (Beazer or other near-term).** **Concrete as of May 11:** Beazer Phoenix pilot is likely to green-light, install ~2 months out (driven by Phoenix summer weather window). Pilot agreement creates urgent work on greybox §§7-12 + code (Cat 1; §4 closed, §5/§6 drafted), HPM-side protocol runner including direct compressor/fan command authority (Cat 7 pilot slice — surfaced by §6 v2's INV-FIT45-3), Phoenix-blocking code fixes (Cat 3), per-packet signing + local log (Cat 1 pilot slice of aivu_integrity), operational 5-Day protocol document (Cat 5). See Path recommendation below for the resequenced priority.

**Axis 2 — Pilot home readiness.** Hardware tested and installable ahead of the Cx window. What has to exist on the software side is fully captured in Axis 1 above. The earlier framing ("calibration protocol, multi-zone integrator, latent-side RealCycle, ERV recovery, operational 5-Day protocol") was generic; the May 11 framing is specific. Multi-zone integrator (Cat 2) is *not* pilot-blocking — whole-house resolution is what the pilot Cx works at.

**Axis 3 — Sales-tool / next-builder readiness.** If JDS wants builder demos beyond Beazer, either a UI (months of work, Cat 5) or a more refined version of today's deck workflow. Today's workflow is "Claude generates charts on demand from JSON sims" — works for one builder at a time, doesn't scale. Not pilot-blocking; deferred until pilot lands.

**Axis 4 — Spec-to-code closure.** Pure engineering hygiene. **Phoenix pivot narrows this to greybox §§7-12 (pilot-blocking; §4 closed, §5/§6 drafted pending review) and aivu_integrity per-packet signing slice (pilot-blocking).** Phase 2 v1 whole-house scope and full aivu_integrity package return as post-pilot work — the spec-vs-code gap on those is no longer urgent and will be addressed when the pilot is running and ongoing Cx is producing data.

**Axis 5 — Integrity-model credibility.** The Delta 7 integrity model is in v3.0. The 5d-iii open-source verification library (Cat 5) is what makes the architectural claim operationally true. **Postponed past pilot (May 11):** for a single-home pilot there are no external verifiers, so the credibility argument doesn't yet have to be operationally true. Returns as work in the 12-month horizon, especially if Delta 7's stronger admissibility argument is going to be made to insurers, regulators, or courts.

**Axis 6 — Series-A fundability (strategic posture).** Independent of engineering progress, certain commitments make AIVU more legible and more defensible to Tier-1 VC reviewers. Category 10 items live on this axis. Some are one-sentence document edits (homeowner data ownership posture, role-name decision, training-set IP framing); some are commercial-contract work (cohort exclusivity); some are legal work that runs in parallel with the pilot (sensor and protocol IP). None of them blocks engineering work; collectively they shape what the company looks like from outside when Series A is being raised. The CEO search (Cat 9) is the single highest-leverage item on this axis because the right CEO is the person who closes the round.

---

## Path recommendation — Phoenix pilot pivot (May 11)

**The prior Path A recommendation (Phase 2 v1 code first) is superseded.** A Beazer Phoenix pilot is likely to green-light, with install ~2 months out so as not to miss serious Phoenix summer weather. That puts a date on the work and changes what has to exist first.

**The new question is not "close the spec-to-code gap in order." It is: what is the minimum *real* code that runs the 5-Day Cx and the subsequent ongoing Cx in one Phoenix home?** Everything that is not load-bearing for the pilot Cx or for ongoing Cx is postponed. Throw-away code is avoided — preference is for less scope cleanly done over more scope partially done.

**Pilot-driven sequence:**

1. **aivu_greybox §§7-12 spec, then code (with §5/§6 review).** This is the package that produces the signed posteriors that become the Digital Birth Certificate. The only piece on the list that cannot be cut, cannot be scaffolded, and cannot be scoped down — it is the architectural claim made operational. Sections 1-3 are drafted (April 27); §4 closed May 11. §5 (passive-fit) and §6 (active-perturbation) drafted May 11 to v3.2 and v2 respectively — both await final JDS review before formal closure. §§7-12 are the remaining operational definitions: recursive-mode Phase 2 solver (§7), identifiability and posterior tightness (§8), invariants consolidation (§9), test plan (§10), common utilities (§11), signing chain (§12). After greybox is done, the ongoing-Cx slice falls out of §7 without separate work.

2. **HPM-side protocol runner.** Software the HPM needs to do its pilot job: sequence the 5-Day protocol (Day 1 fan-only with Fan-Heat gate → Day 2 continue passive → Day 3 HVAC sweep → Days 4-5 active perturbation), ingest 1 Hz telemetry, host greybox at the right cadences, compute the Day-3 (Capacity, EER) operating-point map from the sweep telemetry, record everything to a local append-only signed log. **Not** aivu_hpm v0.1 — name it for what it is, "the software the pilot HPM runs." aivu_hpm as the eventual production package (OTA, orchestrator, MRAC inner loop, fleet management) is post-pilot work.

3. **Phoenix-blocking code-level fixes.** Latent-side RealCycle that respects available moisture (Cat 3, half-day) and ERV heat-recovery in `infiltration.py` (Cat 3, half-day). Both fold naturally into greybox code work; doing them inside that work is more efficient than treating them as separate items.

4. **Per-packet signing + local append-only log.** The evidentiary floor for the Digital Birth Certificate. The HPM signs every packet at production; the log is append-only and locally verifiable. This is the slice of aivu_integrity that has to exist for the pilot.

5. **Operational 5-Day protocol document (Cat 5).** Field-deployable technician checklist version. Two days of focused writing, late in the timeline. The operational nuance is largely in JDS's head; this is JDS-authored work that Claude assists with.

**Explicit postponements — what is *not* needed for pilot Cx or ongoing Cx:**

- **aivu_pinn / Born Educated EnergyPlus run on the Beazer floor plan.** For one home, greybox's role is to identify plant parameters from operational telemetry, and §§1-3 says greybox can converge from a defensible prior given Phoenix-July SNR. An EnergyPlus run that produces a result only to seed a prior greybox will overwrite in two days is throw-away work. Use a defensible default prior (ACCA Manual J-derived values for Phoenix 2B single-family of the relevant size class). The architectural commitment to Born Educated is preserved as a v0.1 commitment for aivu_pinn post-pilot.
- **Merkle Mountain Range + OpenTimestamps anchoring to Bitcoin.** Per-packet signing + local append-only log is the pilot floor; MMR and Bitcoin anchoring are v0.1 features of aivu_integrity. The architectural claim is preserved; the implementation is deferred.
- **2-of-3 threshold attestation across HPM, BDT, Clearinghouse.** There is no BDT during the pilot to attest with. One node signs; the architectural model is intact for v0.1.
- **MRAC inner loop on the HPM.** No closed-loop control during the 5-Day window (the protocol is deliberately sweeping the HVAC across operating points, not controlling against a setpoint trajectory). And the ongoing-Cx mode is observation, not actuation. MRAC is post-pilot.
- **Phase 2 v1 whole-house scope beyond the ongoing-Cx slice.** Capacity demand + equipment output + duct delivery at whole-house resolution (29 invariants) is broader than the pilot needs. The slice that's pilot-relevant is greybox in recursive mode against the Day-5 baseline on live 1 Hz telemetry — and that falls out of greybox itself. The rest of Phase 2 v1 returns as work after the pilot lands.
- **Cohort/BDT refinement, Clearinghouse signing infrastructure, Truth Portal, institutional feeds, 90-home statistical anchor, Five Sigma quarantine.** One home means no cohort, no institutional consumers, no statistical aggregation. All v0.1+ work.

**Hardware path:** HPM hardware, Marmon Venturis, Device Solutions enclosure, Eaton breakers, sensors — already tested, installable ahead of the Cx window. Hardware is not the critical path.

**Why this is the right cut:** The pilot's architectural claim is that the 5-Day protocol works and produces a valid Digital Birth Certificate, plus that ongoing Cx detects envelope drift correctly. Everything in the cut list is needed for those two claims. Everything postponed is needed for the *eventual* AIVU — the fleet, the cohort intelligence, the Clearinghouse retailing data products to institutional buyers — but is not pilot Cx machinery. Throw-away code in any of the postponed areas would be code rewritten or deleted later; postponement preserves both the pilot timeline and the cleanness of the eventual real packages.

---

## What to do at the end of each session that touches this list

Two-minute discipline:

1. Items closed → delete them from the list (Git holds the history).
2. Items advanced → update the status line.
3. New items surfaced → add them under the right category.
4. If a category empties, leave it as a placeholder so the structure is preserved for next time.

If it takes more than two minutes, something else is going on — either you're rewriting the document instead of updating it, or the project just had a structural shift worth its own session log entry.
