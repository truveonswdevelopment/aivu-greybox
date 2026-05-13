# Session log — 2026-05-11

**Author:** Jan-Dieter Spalink + Claude (Opus 4.7)
**Duration:** Sunday afternoon / evening, Switzerland time — a few hours
**Status:** session resumed three times. First continuation: Phoenix pilot pivot reframed near-term engineering priorities and Unfinished Work doc updated. Second continuation: greybox §4 (Fan-Heat Consistency Check) drafted to v3, three architectural insights surfaced. Third continuation: greybox §5 drafted through v3.2 (passive-observation batch fit with two-channel measurement model, six-parameter canonical set extended for two-state attic-main envelope, Laplace algorithm), greybox §6 drafted to v2 (active-perturbation batch fit with direct HPM capacity command and aspirational-not-strict steady-state framing). Five additional architectural insights surfaced. Technical work resumes next session with greybox §§5 and §6 final review, then §7.

---

## What got done

### Cold-start, executed clean

First session running against the three-layer document structure that emerged on May 10. JDS uploaded the cold-start zip plus the two top-level docs. Claude read all five and held position until JDS set the agenda. The structure worked as designed. One small benefit showed up immediately: Claude noticed v3.0 TOC anomalies during ingestion and flagged them as a noticing rather than a task.

### v3.0 architecture doc — Class 1 hygiene fixes shipped (v3.0.1)

Six paragraphs in the v3.0 docx had heading-equivalent typography but lacked the `Heading2` / `Heading3` style, so the TOC silently skipped them:

- Clearinghouse §0.1, §0.2, §0.3 — promoted to Heading3 (peers of §0.4).
- Clearinghouse §1.1 "The Adjudication Engine," §1.2 "The Integrity Layer" — promoted to Heading3 (peers of §1.3).
- Addendum §5 "Computational Economics" — promoted to Heading2. This was the cause for Nodes 1/2/3 of compute economics appearing at the same TOC level as their parent wrapper.

Implementation: direct XML edit on `document.xml`, repacked with `[Content_Types].xml` as first member. Verified via python-docx that style counts changed by exactly the expected deltas. Visible body appearance unchanged; TOC updates on regeneration. Distinct from Class 2 (numbering — none required) and Class 3 (content-level cleanup — held back as judgment calls).

### Strategic posture work — two tasks, executed in reversed order

JDS asked for two analyses for Tier-1 VC fundability. Task 2 (raising hurdles to entry) went first because the answer to "what makes AIVU uncopiable" feeds into "what makes AIVU fundable."

Task 2 mapped six adjacent player categories, assessed current moats (Physics strongest, Data conditionally compounding, Procedural weakest), and identified six wall-raising moves: Clearinghouse as regulated third party, aivu_integrity as open standard, builder-side cohort exclusivity, sensor and protocol IP, training-set as separable IP asset, homeowner data ownership posture.

Task 1 reduced to two load-bearing missing pieces — pilot-derived number and named first builder customer — plus three pitch-surface refinements (displacement curve over TAM number, founder-CEO sentence rewrite, what not to add).

### Named partners and CEO succession

JDS confirmed Hovnanian or Beazer as pilot sponsor, BASF supplying spray-foam under empirical measurement, Marmon (Berkshire Hathaway operating company) manufacturing the proprietary Venturi devices, Device Solutions (Raleigh NC) building HPM enclosures. Combined with the prior knowledge that v9.1 landed at a Berkshire VP, this is a credible four-name stack. Recommended placement: one inline sentence on the front page of the OS doc, not a logo bar, no "Partners" section. Berkshire-VP context stays verbal, off-document. Hovnanian-or-Beazer needs to collapse to one name before the doc edit.

JDS then surfaced the load-bearing fact that age requires CEO handover after the pilot is in good shape, and that *the incoming CEO should raise Series A, not JDS*. This recalibrated Task 1: the Tranche 2 paragraph in v9.5 should not be softened (Claude's first instinct) but sharpened — succession stated plainly as architecture rather than concession. Role name proposal: Chief Architect (vs. v9.5's "Non-Executive Chairman"), retaining responsibility for dual-track physics, integrity model, and Clearinghouse adjudication logic. Tranche 1 sizes in CEO-search runway; the CEO who closes Series A is the CEO recruited during the pilot.

### Unfinished Work doc — Category 10 and Axis 6 added

JDS uploaded the Unfinished Work doc as the missing fourth piece of the continuity-management system. Three additions: one line to Category 9 for the incoming CEO search; new Category 10 (Strategic posture commitments) with seven entries — the six wall-raising moves from Task 2 plus the role-name decision; new Axis 6 (Series-A fundability) appended to the prioritization axes block. Path A recommendation untouched; Category 10 runs alongside engineering work on a different track. Two judgment calls flagged before drafting: named partners stay in the pitch-document track (not this one), and the new category name was confirmed.

### Document-format conversation

Toward end of session, JDS asked whether `.docx` is the right format for the four reference documents. Answer: keep the four reference docs as markdown (three of them already are), keep OS doc and Architecture doc as `.docx`. The distinction is internal-working-document vs. external-deliverable. See lesson below.

---

## Lessons captured for possible future promotion

These aren't yet stable enough to belong in Working Preferences, but should be visible to future Claude sessions reading this log:

**File formats: working docs are markdown, external deliverables are .docx.** The four documents JDS maintains for continuity management (Working Preferences, Architectural Distillation, Unfinished Work, current session log) have no external reader. Claude reads them at session start; JDS reads them at session start; no one opens them in Word. Markdown is the right format — fast to read with a single `view` call, no extraction overhead, no risk of the structural bugs that accumulate in .docx files (heading-plus-body-in-one-paragraph, hand-bolded paragraphs missing heading styles, etc.), and diffable in Git for the snapshot discipline.

The OS doc and the Architecture doc are the opposite case. Their audience is outside the project — Tier-1 VC reviewers, the Berkshire VP, the IBM consulting engineer, an eventual CEO candidate's diligence team. They will be read in Word. Heading styles, the Table of Contents, and the rendered appearance matter. The `.docx` is the deliverable.

The durable reason to keep working docs as markdown isn't tool-call efficiency; it's that markdown is structurally simpler and the documents are more likely to stay clean over a long project lifespan. Three of the four working docs are already markdown; the fourth (Unfinished Work) is too. The pattern is established; this lesson is the explicit naming of it.

**The named-partner stack is a structural moment, not a list of names.** When JDS surfaced the four named partners (Hovnanian/Beazer, BASF, Marmon, Device Solutions) plus the Berkshire-VP context, the temptation was to enumerate what each brings individually. The stronger framing came from reading the four as a system: a real builder demanding the product, a real OEM betting their product datasheet on AIVU's measurements, a Berkshire-Hathaway-owned industrial scaler manufacturing the most physics-critical sensor, and an industrial electronics shop building the enclosures. Five years ago none of these companies had a reason to engage. The fact that the configuration has been assembled is itself evidence of the "why now" claim. The lesson for future Claude sessions: when JDS provides a list of credentials or relationships, the question to ask first is what they prove *together*, not what each one is worth alone.

**Trust the doc's own discipline before adding to it.** Twice in this session Claude was about to add material to documents that had explicit rules against accretion — the Working Preferences (five-minute read, no subsections, shrinks more than grows) and the Unfinished Work doc (categories distinguish *kinds* of work, the four-axes framing is load-bearing). Both times JDS's discipline from prior sessions caught the issue before it became a problem: the May 10 Working Preferences rule "session lessons live in Layer 2 first" prevented an early-stage observation from being crowbarred into Layer 1; the Unfinished Work doc's own structure prompted the question of *where* the new material fits before *how* it gets written. The lesson: when a document has rules at the top, those rules are the result of prior failure modes the document was rebuilt to prevent. Read them first, then act.

---

## Pending — handed off to next session

- **JDS reads v3.0.1 carefully today** with fresh eyes, regenerates TOC in Word for Mac, annotates anything else that wince-tests.
- **JDS rules on Hovnanian vs. Beazer** as the named pilot sponsor for the next OS doc revision (current state is "or/both," which won't survive a Tier-1 reading).
- **JDS rules on role name** for the post-transition founder role (Chief Architect / Founding Architect / Chief Scientist / Founder & Chairman all defensible).
- **Next OS doc revision (v9.6)** absorbing: front-page named-partner sentence, Tranche 1 outcome rewrite with the named sponsor, Tranche 2 paragraph rewritten around the Chief Architect / incoming-CEO framing, and (separately, JDS's call) any of the homeowner data ownership / training-set IP / displacement-curve additions.
- **Technical work resumes next session.** Per the Phoenix pilot pivot (added later this session), Path A is superseded. The natural starting point is **aivu_greybox §4 — the Fan-Heat Consistency Check math** — followed by §§5-12 in sequence, then greybox code, then the HPM-side protocol runner. See the Unfinished Work doc's updated Path recommendation for the full resequenced priorities and the explicit postponements.
- **Distillation v0.2 still has "What's missing from this document"** as a placeholder JDS may or may not fill in. Carried forward from the May 10 log.

---

## Session continuation — Phoenix pilot pivot

After the initial close, JDS raised the near-term objective: Beazer Homes is likely to green-light a one-home pilot in Phoenix, with install timed to capture serious Phoenix summer weather — meaning roughly two months out from May 11. That puts a date on the work and forced a reframing of the resequenced priorities Path A had set up.

### What changed in the framing

The Path A recommendation (Phase 2 v1 code → greybox → integrity) was right when the pilot date was abstract. With Phoenix two months out, the load-bearing question became different: *what is the minimum real code that runs the 5-Day Cx and the subsequent ongoing Cx in one Phoenix home?* Two anchoring constraints from JDS shaped the answer:

1. **"Claude habitually provides estimates about needed times that are substantially longer than what eventually transpires."** This called out a procedural-caution pattern that Working Preferences explicitly flags as the wrong mode. Substance, not workflow. Time estimates dropped out of subsequent proposals.
2. **"Generate as little throw-away code as possible, even if that limits the scope of what 'it' can actually do. No need to be 'holier than the pope' as far as compliance with the system architecture is concerned — postpone what isn't really needed for the Cx work, or for the subsequent ongoing Cx."** This is the cleaner disciplinary principle. Every line of scaffolding is a line that has to be rewritten or deleted; the architectural claim is stronger when the code that exists is the code that's meant to exist.

### The cut list, settled in conversation

**Pilot-needed (the real code):**
- aivu_greybox §§4-12 spec, then code. The package that produces the signed posteriors that become the Digital Birth Certificate. Cannot be cut or scaffolded. Next session opens with §4 (Fan-Heat Consistency Check math).
- HPM-side protocol runner: protocol sequencer, telemetry recorder, greybox host, Day-3 (Capacity, EER) operating-point map computation, per-packet signing, local append-only log. Named for what it is — not pre-named as aivu_hpm v0.0, to avoid the trap of pilot scaffolding being mistaken for the start of the real package.
- Phoenix-blocking code fixes (latent-side RealCycle, ERV heat-recovery) — fold into greybox code work rather than running as separate items.
- Per-packet signing + local append-only log: the evidentiary floor for the Digital Birth Certificate.
- Operational 5-Day protocol document — field-deployable technician checklist version. JDS-authored work that Claude assists with.

**Explicitly postponed (not pilot Cx or ongoing Cx machinery):**
- aivu_pinn / Born Educated EnergyPlus run on the Beazer floor plan. For one home, greybox can converge from a defensible default prior (ACCA Manual J-derived values for Phoenix 2B single-family of the relevant size class). An EnergyPlus run that produces a result greybox overwrites in two days is throw-away work.
- Merkle Mountain Range + OpenTimestamps anchoring to Bitcoin. Per-packet signing is the pilot floor.
- 2-of-3 threshold attestation across HPM/BDT/Clearinghouse (there is no BDT during the pilot).
- MRAC inner loop on the HPM (no closed-loop control during the 5-Day window; ongoing Cx mode is observation, not actuation).
- Phase 2 v1 whole-house scope beyond the ongoing-Cx slice (which falls out of greybox in recursive mode).
- Cohort/BDT refinement, Clearinghouse signing infrastructure, Truth Portal, institutional feeds, 90-home statistical anchor, Five Sigma quarantine — one home means no cohort, no institutional consumers, no statistical aggregation.

### One architectural clarification surfaced during the conversation

The Day-3 HVAC operating-point map computation — Q_cool = ṁ_air × (h_return − h_supply), EER = Q_cool / W across the operating-point sweep — is **not** greybox's math. Greybox does envelope identification; the map computation lives in the HPM-side protocol runner that consumes 1 Hz telemetry during the Day 3 sweeps. JDS confirmed. Worth being explicit about so it doesn't fall in a crack between packages when both get written.

### Lessons captured for possible future promotion

**Time estimates default to procedural caution and should be cut out.** When the question is "what's the substance of the work," writing an estimated timeline alongside the substance imports a workflow-flavored framing that Working Preferences specifically flags against. JDS's correction was direct: estimates are habitually too long; the right framing is the substance itself, with timing emerging from how the work actually goes. Promote this to Working Preferences if it holds across more sessions.

**The throw-away/real-code distinction is sharper than the scaffolding/production distinction.** In an earlier draft of the pilot sequencing, Claude reached for "scaffolding" framing (aivu_hpm v0.0 as an explicitly-scaffolded stepping stone to v0.1). JDS pushed harder: postpone what isn't needed, rather than scaffolding the eventual thing in a minimal form. The result is cleaner — the pilot HPM software is named for what it actually is, not as an early draft of something else. The lesson: when in doubt between "build a minimal version of the architecturally-correct thing" and "build only what's needed and name it for that," the second is usually right. The architectural claim is preserved through *postponement* of the unneeded pieces, not through their *anticipation* in scaffold form.

### Doc updates shipped this session

- Unfinished Work doc revised to 2026-05-11 (Phoenix pilot pivot). Category 1 reordered with greybox §§4-12 first; Phase 2 v1 scope explicitly narrowed; aivu_integrity scope explicitly narrowed. Category 3 marked Phoenix-pilot-blocking, folded into greybox work. Category 5 — operational 5-Day protocol now pilot-blocking; 5d-iii explicitly postponed. Category 7 — aivu_pinn skipped for pilot; aivu_hpm pilot slice defined; full packages return post-pilot. Axes 1, 2, 4, 5 updated. Path recommendation fully rewritten as the Phoenix-driven sequence.
- Session log (this section) appended.

### Pending — updated

- All prior Pending items still pending (v3.0.1 read, Hovnanian-vs-Beazer ruling, role-name ruling, v9.6 OS doc revision, Distillation v0.2 placeholder).
- **New: next session opens with aivu_greybox §4 — Fan-Heat Consistency Check math**, then §§5-12 in sequence. Long session, not a short one.
- **New: hardware procurement state worth confirming early** — Marmon Venturi lead time, Device Solutions enclosure status, Eaton breakers in hand, SoC selection finalized. JDS indicated hardware is already tested; confirming "installable ahead of the Cx window" stays true through the two months would close out any hardware-side critical path uncertainty.

---

## Session continuation 2 — greybox §4 (Fan-Heat Consistency Check)

Session resumed for technical work on greybox §4 after the Phoenix-pivot continuation closed. Three iterations (v1 → v2 → v3); the section landed at v3 with material architectural content that the project documents did not previously carry.

### What got done

- **§4 draft v1** — first-pass full-section draft. Claude assumed §§1-3 placed Fan-Heat math inside greybox, drafted accordingly, and flagged the assumption "for verify on read." JDS correctly pushed back that the assumption was load-bearing and should have been resolved before drafting rather than handed off as a verify-later question. Procedural correction taken on board.
- **§§1-3 read** (file: `aivu_greybox_spec_v0_1_through_section3.md`, April 27 draft recovered May 10). Confirmed Fan-Heat math is greybox's; surfaced three v1 errors (four-self-test framing was missed in §4.1; canonical parameter set `{R_eff, C_house, cfm50, F_slab, κ_buffer}` was unstated; signing-mechanics restated rather than delegated to `aivu_integrity`).
- **§4 draft v2** — rewritten to honor §§1-3. Cleaner section, ~25% shorter than v1. Five numerical placeholders carried forward as defaults: `ε_FH = 8%`, `τ_FH = 30 min`, `τ_warmup = 15 min`, `η_distribution = 0.92`, `ΔW_max = 0.0002 kg/kg`.
- **JDS surfaced the actual sensor stack and AHU geometry.** Sensirion SHT35 (±0.1°C, ±1.5% RH), Sensirion SDP8xx Venturi (3% measured, ≤1.5% tube), Eaton breaker electrical (1%). AHU inside a separate first-floor conditioned mechanical room; supply and return plenums reaching into a spray-foam-insulated *conditioned* attic where the ductwork resides. Stated requirement: HVAC system capacity determined as tightly as reasonably possible because the HVAC system is to be used as a continuously calibrated measurement instrument.
- **JDS surfaced terminal-probe architectural requirement.** T/RH sensors are at the supply terminals, not at the supply plenum. Three reasons in order of weight: (i) Sensirion RH sensors cannot read accurately at saturation, which is the regime immediately downstream of an active cooling coil; readings would be structurally invalid during all of Days 3-5; (ii) TXV-circuit stratification persists for several diameters downstream, and a single plenum probe samples whichever stratum it sits in; (iii) what matters architecturally is the enthalpy *delivered to the conditioned space* rather than the enthalpy at the AHU output. The duct run mixes stratification out and pulls air off the saturation line via mild conduction reheat from the conditioned attic.
- **JDS confirmed per-terminal Venturis are calibrated to each duct diameter's expected CFM range.** Per-terminal mass flow is measured, not estimated from M-5.0 design. Removes the ~3% CFM-weighting uncertainty term entirely.
- **§4 draft v3** — rewritten with terminal-probe geometry (12 terminals for the Beazer Phoenix pilot home), the Sensirion-specific sensor stack named at every point, and "Option B" identification framing: Fan-Heat *identifies* `η_distribution` as a per-home Day-1 prior for §6 joint refinement rather than consuming it as a fixed prior. Two pass conditions instead of one: residual tolerance `ε_FH = 4%` *and* physical-bound check `η_min = 0.85 ≤ η̂_distribution ≤ η_max = 0.96`. Sixth numerical default added: spatial-uniformity gate `σ_spatial_max = 0.5 kJ/kg` as a §4.4 window-rejection criterion (non-uniformity under fan-only conditions points to something operationally wrong rather than to an envelope/equipment fact worth signing). INV-FH-4 inverted from "η_distribution is a prior, not fitted" to "η_distribution identified by Fan-Heat is the Day-1 prior for §6, not the final value." All four invariants confirmed.

### Three architectural insights surfaced during §4 work

These belong at the project level, not buried in greybox §4. They are flagged here for promotion to the Architectural Distillation when they've held across more sessions.

**Insight 1 — Terminal-probe placement is architecturally required, not a design preference.** The Architecture of Truth carries the dual-track commissioning sequence (envelope → HVAC-as-instrument → high-SNR envelope) but does not currently name *why* the supply T/RH sensors sit at the terminals rather than the plenum. The reason is load-bearing: capacitive RH sensors cannot read accurately at saturation, and the immediate-downstream-of-coil location is at saturation during all cooling operation. A plenum-probe architecture would return structurally invalid readings during the very operating mode Days 3-5 exercise. The duct run does two things — sensible reheat from the conditioned attic pulls air off the saturation line, and flex-duct turbulent mixing homogenizes the TXV-induced stratification — that together restore probe validity at the terminals. This is not a measurement-convenience choice; it is what makes the dual-track architecture *operable*. Worth a one-paragraph statement in AOT at the next revision, in the section discussing sensor placement or the dual-track sequence.

**Insight 2 — `η_distribution` is a per-home identified quantity that anchors the delivery instrument.** The dual-track commissioning architecture treats the HVAC system as a continuously calibrated measurement instrument that probes the envelope during Days 3-5. What that means concretely, surfaced during §4 v3 work: the AHU + distribution + terminal probe stack is a *unified delivery instrument*, and its calibration coefficient `η_distribution` is a per-home quantity that varies with duct geometry, insulation R-value, and run length. Fan-Heat is the Day-1 identification of this coefficient. It is then refined under active excitation in §6 jointly with envelope and equipment parameters. The successive-refinement architecture (Day-1 → Day-1-2 passive → Day-4-5 active) is what makes envelope and equipment parameters independently observable rather than confounded. The current AOT discusses the dual-track sequence at the protocol level but does not name the instrument-grade reading floor as architecture. It should.

**Insight 3 — The Day-3 (Capacity, EER) map is automatically a delivered-capacity map.** Because the supply probes are at the terminals, the Day-3 sweep measures cooling capacity *as delivered to the conditioned space*, not as output from the coil. This means `aivu_physics` Phase 2 Layer 3 (duct delivery) folds naturally into Day-3 — there is no separate layer-by-layer reconciliation step needed between Layer 2 coil output and Layer 3 delivered capacity, because the measurement geometry pins them together. The Fan-Heat-identified `η_distribution` is the bridge: it relates fan electrical input to delivered enthalpy, which is the same delivery instrument that Days 3-5 will use under active excitation. AOT does not currently surface this Layer 2 / Layer 3 / measurement-geometry alignment. Worth naming.

### Lessons captured for possible future promotion

**The "verify on read" pattern is a procedural shortcut that hides incompleteness.** v1 of §4 was drafted with a load-bearing assumption about §§1-3 flagged for the reader to verify rather than resolved before drafting. JDS caught it and pushed back: the answer is in the document, the document was available, the right move was to read it before drafting. Generalizable form: when Claude is about to flag an assumption for "verify on review," ask first whether the source of truth for the assumption is accessible right now. If yes, resolve it before drafting. "Verify on read" is appropriate when the source is genuinely outside Claude's reach; it is procedural caution masquerading as thoroughness when the source is one tool call away.

**JDS carries architectural intuition; Claude carries cross-reference bookkeeping; the division of labor is structural.** During §4 work, Claude asked JDS several cross-reference questions ("are the other three self-tests their own sections or tucked into §5/§6?") that should have been answered by re-reading §§1-3 directly. JDS named the right concern — "intuitive idiot, terrible at anything methodical, that is why I'm working with Claude" — and the right framing came back: it is not that JDS is bad at methodical and outsources it. It is that the methodical work at this project's scale exceeds one human's clock-time budget, and a partner who can hold it cheaply is the rational architecture. The intuition is where the irreplaceable work lives; bookkeeping is what supports it. The continuity-management system (Working Preferences, Distillation, Unfinished Work, session log) is the discipline that keeps this division of labor functioning. Worth promoting to Working Preferences as a one-liner if the pattern holds across more sessions.

**Numerical defaults derived against actual procurement beat numerical defaults derived against generic spec language.** v2's `ε_FH = 8%` was defensibly derived from "spec-grade T/RH probe" and "typical Venturi accuracy" — generic assumptions. v3's `ε_FH = 4%` was derived against SHT35 / SDP8xx / Eaton with √12 spatial averaging and Option B identification eliminating the `η_distribution` prior contribution. The factor of two between them is real, not a calibration choice. When a draft is about to pin a numerical default, ask first whether the actual procurement is known; if it is, derive against that, not against generic placeholders. Saves a revision cycle.

### Doc updates shipped this session

- Unfinished Work doc edited in five surgical places to reflect §4 closing: Category 1 reordered with §§5-12 first and §4 closure annotated; Path recommendation step 1 rewritten; Axis 1 and Axis 4 updated; version line updated. Body unchanged.
- This session log updated with §4 work, three architectural insights, and three lessons.

### Pending — updated

- Prior Pending items still pending (v3.0.1 read, Hovnanian-vs-Beazer ruling, role-name ruling, v9.6 OS doc revision, Distillation v0.2 placeholder).
- The three architectural insights surfaced today are candidates for Architectural Distillation v0.3 once they hold across one or two more sessions.
- The `ε_FH` derivation (§11 work) is queued — §11 carries common utilities including this propagation. Not pilot-blocking; numerical default `4%` is pinned in §4 v3 and §11 will document the derivation when written.
- **New: next session opens with aivu_greybox §5 — passive-fit procedure for Days 1-2.** Spec content: how envelope UA-equivalent, slab F-factor, infiltration ELA, and the moisture-side parameters are jointly identified from the Day 1-2 passive observation window using `aivu_dynamic.dynamic.run(...)` as the forward-chain likelihood, with the Day-1 Fan-Heat-validated terminal stack as the supply-side boundary condition. §6 (active perturbation) follows §5.

---

## Session continuation 3 — greybox §5 and §6

Session resumed for technical work on greybox §§5-6 after §4 closed. §5 went through three drafts (v1 → v2 → v3.2 with two intermediate corrections); §6 went through two (v1 → v2). Both sections await JDS final review next session before formal closure. The drafting surfaced five additional architectural insights and resolved one structural inconsistency in greybox §1.2.

### What got done

**§5 v1.** First-pass draft of Day-1-2 passive-observation batch fit. Assumed "HVAC fully off" operational mode, single-channel observation (single primary indoor T/RH probe), five-parameter canonical set from greybox §1.2, NUTS as default algorithm. EnergyPlus listed below ACCA in the prior-path preference order, copied from the Phoenix-pivot Unfinished Work doc's framing.

**§5 v2.** Path preference order corrected — EnergyPlus ahead of ACCA. JDS pointed out EnergyPlus is based on DOE-2 heat-balance physics (time-domain, structurally compatible with the locked forward chain), while ACCA Manual J is a steady-state load-calculation methodology that produces an *assumption set* rather than physics-grounded parameter values. The Phoenix-pivot doc's "throw-away" framing was conditional on data dominating the prior for all parameters, which §5.5 establishes is not true for the loose parameters (`F_slab`, `C_w`, `cfm50`).

**§5 protocol correction.** JDS surfaced that "HVAC fully off" was wrong: probes need mixing to read representative indoor state, requiring the AHU fan to operate intermittently. Initial analysis sized the mixing schedule from spatial-stratification considerations (~15 min/hr to keep spatial σ below identifiability bound for a single-probe-location scenario). Then JDS surfaced the actual measurement geometry: §4 SHT35 probes at 12 supply terminals and the return plenum (behind air filter, far from fan) are the indoor instrument stack. The return-plenum probe is the volume-integrating indoor T/RH instrument — every fan-on interval is a measurement interval, not a "mixing for probe validity" workaround. The 15 min/hr derivation was solving the wrong problem; 10 min/hr per JDS's original gut number is sufficient and correct under the actual architecture.

**§5 duct-flush warmup turned into a second observation channel.** JDS surfaced that the 60-second duct-flush warmup window at fan-on is itself useful — during the preceding fan-off interval, supply ductwork air equilibrates with the conditioned attic; when the fan kicks on, terminal probes briefly read attic-equilibrated air before being replaced by freshly mixed conditioned-space air. The 60s warmup yields one attic-air-temperature observation per fan-on interval. The architectural framing: exploiting structural transients in the measurement protocol yields "free" identifiability gains the protocol designer didn't initially plan for.

**§5 v3 (six-parameter set).** The conditioned-attic two-state architecture surfaced and was resolved against the locked specs. Initial reading of greybox §2.1 ("two-state vector `x = (T_in, W_in)`") suggested single-state (sensible+latent), conflicting with JDS's clear architectural memory that attic and main are separate states coupled through ceiling sheetrock. `conversation_search` recovered the April 18 geometry discussion: Phase 1 v4.0 §10 commits to the two-state attic-main model with empirical confirmation (~3°F differential under spray-foam-deck Phoenix-July conditions). April 27 spec work confirmed `aivu_dynamic` v0.2 line 35 lists six parameters for inverse fit, including `foam_coupling_factor`. **Greybox §1.2's five-parameter canonical set is incomplete** — sixth parameter `foam_coupling_factor` was missing. §5 v3 extended canonical set to six and added the two-channel observation model accordingly.

**§5 v3.1 (numerical corrections).** Two corrections from JDS review: softened `σ_T_attic` from 0.029°C (full-√12 averaging) to 0.05°C (partial-correlation conservative midpoint) pending pilot validation; corrected `foam_coupling_factor` empirical anchor from "~3°F average" (occupant-report hearsay) to "~2.5°F at 3pm-July" (prior simulation, more reliable anchor with specific solar-moment context). Expected posterior tightness on `foam_coupling_factor` softened from 10% to 15% accordingly.

**§5 v3.2 (algorithm and naming corrections).** `conversation_search` for the April 27 spec work surfaced two more inconsistencies: (a) algorithm class for v0.1 is Laplace approximation per April 27 §6.2 spec lock, not NUTS — the April 27 spec explicitly reasons that "the forward chain from `aivu_physics` and `aivu_dynamic` is smooth and deterministic in the parameters; with an informative prior and 48 hours of 1 Hz data the negative-log-posterior is well-approximated as quadratic near its mode for the canonical parameter set." (b) Moisture parameter naming: April 27 spec uses `C_w` (lumped moisture capacity in state-space sense, paired with `C_house` sensible capacity), greybox §1.2 lists `κ_buffer`. §5 v3.2 adopts `C_w` to match the April 27 work. §1.2 small revision queued to settle both questions.

**§6 v1 first draft.** Day-4-5 active-perturbation batch fit. Initial draft used thermostat-setpoint protocol (cool to 20°C / hold 12 hours → decay 6 hours → reverse setpoint 30°C overnight → repeat hold), Laplace algorithm, expected end-of-Day-5 posterior tightness 1.5/2/12/8/10/5.

**§6 v2 substantive restructuring driven by JDS push for maximum SNR.** Four corrections compounded:
- *No appliances or occupants during pilot pre-occupancy* — removes constraints I had assumed from typical residential operation
- *Direct HPM compressor/fan command authority confirmed available* — allows bypassing thermostat entirely; "compressor full-on, fan continuous, ignore thermostat" is an executable HPM command
- *35°C reverse-drive setpoint acceptable* — Phoenix homes routinely see this; cosmetic risks negligible; no fridge or appliance constraints
- *Strict steady state in 48 hours is not achievable* given main-space τ ≈ 60 hours and slab τ ≈ 24-72 hours; the April 27 framing "energy balance collapses to a single equation in R_eff" oversimplified — the Laplace fit identifies parameters from the full driven trajectory, not from a clean steady-state energy-balance closure

§6 v2 restructured around direct HPM commands, longer driven phases (18h cooling drive / 6h decay / 18h reverse drive / 6h final close), aspirational-not-strict steady state framing, fan-only-plus-solar reverse drive (no heat strip), `η_distribution` held at Day-1 value to avoid `R_eff × η_distribution` degeneracy in Phase A, Phase D as held-out validation against fit overfit risk. Expected end-of-Day-5 posterior tightness improved to 1/1.5/8/5/8/4.

### Five architectural insights surfaced during §5/§6 work

These belong at the project level. Flagged here for promotion to Architectural Distillation when they've held across more sessions.

**Insight 4 — Exploiting structural transients yields "free" identifiability gains.** The 60s duct-flush warmup at fan-on was initially treated as a noise-source-to-be-excluded. JDS surfaced that it contains attic-equilibrated air, turning a transient-to-be-discarded into a second observation channel that directly identifies `foam_coupling_factor`. The general lesson: when the measurement protocol has unavoidable transients, ask first what physical quantity *each* transient encodes before deciding which to discard. The architecture often pays unexpected dividends from instrumentation choices made for unrelated reasons (here, the §4 Fan-Heat-validated terminal stack became the §5 primary indoor instrument; the duct-flush transient became the attic observation channel).

**Insight 5 — Prior provenance is load-bearing metadata, not bookkeeping decoration.** §5.4 commits to signing prior provenance into the posterior record because loose-parameter posteriors are prior-sensitive. External verifiers later interpreting a `Day2Posterior` on (e.g.) `cfm50` need to know whether the supporting prior came from a trained PINN, an EnergyPlus simulation, or a Manual J table — the inferential weight of the posterior on that parameter depends on which. The "throw-away" framing for EnergyPlus in the Phoenix-pivot doc was conditional on data dominating the prior for all parameters; §5.5's identifiability analysis establishes that for `F_slab`, `C_w`, and `cfm50` at end-of-Day-2, data does not dominate prior. Provenance becomes part of the inferential chain.

**Insight 6 — Strict steady state is aspirational for residential envelopes; the Laplace fit identifies from full trajectories.** The April 27 §6 framing — "Under steady state, energy balance collapses to a single equation in `R_eff`" — assumed that the Days 4-5 protocol could *reach* steady state. Honest analysis shows main-space thermal time constant is ~60 hours and slab thermal time constant 24-72 hours, making strict steady state unachievable in 48 hours. The architecturally honest framing: §6's Laplace fit identifies parameters from the full driven trajectory, including the slow approach toward thermal balance and the slab transient that never equilibrates. The math doesn't change; the framing does. This is the kind of correction that surfaces only under technical pressure (sizing protocol durations) and would never appear from architecture-level reasoning alone.

**Insight 7 — `aivu_dynamic` v0.2's inverse-fit parameter list is the source of truth, not greybox §1.2.** Greybox §1.2 lists five canonical parameters; `aivu_dynamic` v0.2 line 35 lists six (adding `foam_coupling_factor` for the two-state attic-main model). §1.2 was written before the two-state geometry work landed in Phase 1 v4.0 §10 and was not updated. The lesson: when multiple specs co-evolve, the source-of-truth document on a specific question is the one specifying the relevant *operation* (here, the inverse fit and the forward chain it inverts), not the one summarizing the package's overall scope. Greybox §1.2 summarizes; `aivu_dynamic` v0.2 line 35 specifies. The summary needs to track the specification.

**Insight 8 — Direct HPM command authority over equipment is architecturally load-bearing for §6.** The §6 v2 protocol assumes the HPM can issue "compressor full-on, fan continuous, ignore thermostat" as a direct command. This is more than a convenience; it's what enables the maximum-SNR protocol. Thermostat-only control would force the spec into a setpoint-driven protocol that operates at whatever capacity the equipment chooses to deliver, with no guarantee of reaching the operating points the SNR analysis assumes. INV-FIT45-3 makes this explicit: §6 v0.1 cannot run on a building where the thermostat is the only HVAC controller available. This constrains the pilot-builder choice (HPM must have the right hardware authority) and constrains future deployments (commercial buildings with proprietary BAS controllers may require v0.2 fallback protocol).

### Lessons captured for possible future promotion

**The verify-on-read pattern can hide more than one assumption per draft.** The §4 v1 mistake (drafting on an assumption flagged for verification rather than resolving it) recurred in §5 v1 in three places simultaneously: NUTS-vs-Laplace algorithm class, κ_buffer-vs-C_w naming, and five-vs-six parameter cardinality. All three were resolvable by reading the April 27 spec work via `conversation_search`. The compounding effect: each unverified assumption shipped is one more thing to correct in subsequent revisions, and they tend to surface together rather than separately. Generalizable form: when a draft has *multiple* assumptions flagged for verification, treat that as a signal that the source-of-truth document needs to be read in one pass before drafting, not progressively as each assumption surfaces.

**Procurement-grounded numerical defaults vs. assumption-grounded ones — second example.** The §4 work surfaced this lesson with `ε_FH = 4%` (Sensirion-stack-derived) replacing `ε_FH = 8%` (generic-spec-derived). §5 surfaced a parallel pattern: the `foam_coupling_factor` empirical anchor was initially "~3°F average" (occupant-report hearsay) and got corrected to "~2.5°F at 3pm-July" (prior simulation). Both moves are from looser-source-of-truth to tighter-source-of-truth. The general lesson, sharpened: when a numerical anchor enters a spec, ask what *grade of evidence* it represents and prefer the highest-grade source available. Provenance of the anchor should be visible in the spec citation, not just the number.

**Active perturbation protocols rest on equipment-command authority, not just equipment behavior.** §6's expected SNR gains depend on the HPM's ability to drive the equipment to specific known operating points. If the protocol designer assumes setpoint-driven control, they get a different (and weaker) protocol than if they assume direct capacity command. This is a non-obvious architectural-vs-operational coupling that surfaces only when the protocol's quantitative claims are pushed against the equipment's command surface. Worth being explicit about in any future active-excitation spec work in adjacent packages (`aivu_pinn` cohort-perturbation experiments, ongoing-Cx active diagnostics).

### Doc updates shipped this session continuation

- Unfinished Work doc Category 1 reordered to reflect §4 closed, §5 v3.2 / §6 v2 drafted pending review, §§7-12 ahead. New Category 4 entry for the greybox §1.2 parameter-set incompleteness finding. Path recommendation step 1, Axis 1, Axis 4 updated. Version line bumped.
- Session log updated with §5/§6 work, five additional architectural insights, three additional lessons.

### Pending — updated

- Prior Pending items still pending (v3.0.1 read, Hovnanian-vs-Beazer ruling, role-name ruling, v9.6 OS doc revision, Distillation v0.2 placeholder).
- Eight architectural insights surfaced today are candidates for Architectural Distillation v0.3 once they hold across one or two more sessions.
- The `ε_FH` and `σ_T_attic` derivations (§11 work) are queued. Not pilot-blocking.
- The greybox §1.2 small revision is queued (name `foam_coupling_factor` explicitly, settle `κ_buffer`/`C_w` naming, document the parameter-set extension under §1.2's "Additional parameters may be committed at code-implementation time" caveat).
- **New: next session opens with JDS final review of §5 v3.2 and §6 v2 before formal closure**, then either §7 (recursive-mode Phase 2 solver) directly or a brief pause to flag any v0.2 questions surfaced by the review.
- **New: HPM direct-compressor/fan-command-authority requirement** for the §6 protocol — INV-FIT45-3 makes this load-bearing. Confirming the pilot hardware actually supports this is part of the Beazer-pilot hardware-readiness check.

---

## Closing observation

The most useful thing this session demonstrated is that the cold-start discipline works. The five-document continuity system (Working Preferences, Architectural Distillation, Unfinished Work, session log, plus whichever top-level docs are active) was sufficient to bring a fresh session up to working speed on a complex project, without procedural drift or false starts.

The second-most useful thing is the explicit naming of the file-format rule. Working documents have been markdown for a while in practice, but the *reason* — internal-working-document vs. external-deliverable, with the durable argument being structural simplicity rather than tool-call cost — wasn't named until today. That belongs in Layer 2 first; it earns its way to Layer 1 only if it holds up across more sessions.

The third — surfaced only in the session continuation — is that *the Path recommendation can pivot mid-session*. The Unfinished Work doc was designed for that. When the operational reality changed (Beazer pilot date materialized), the Path A framing didn't need to be defended; it needed to be superseded. The doc structure absorbed it cleanly, the four reference docs remained the source of truth, and the resequenced priorities sit in the same place anyone reading the doc cold would expect to find them. The structure passed a real test, not a synthetic one.

The fourth — surfaced in the §4 work — is that *the architecture surfaces best under technical pressure*. Three substantive insights about AIVU (terminal-probe placement as architectural requirement; `η_distribution` as per-home identified delivery-instrument calibration coefficient; Day-3 map as automatically delivered-capacity by virtue of measurement geometry) were not visible at the Architecture of Truth level until §4 work forced them into precision. The architecture document carries the names; the spec work carries the load-bearing detail; the architecture document gains from being revisited after spec work has clarified what the names actually mean. This is a healthy compounding loop that the three-layer document structure is built to support.

The fifth — surfaced across §5 and §6 work — is that the compounding loop runs harder than expected. Five additional architectural insights surfaced in the third continuation, including a correction to the April 27 "steady state collapses to one equation" framing, an inversion of the Phoenix-pivot doc's "EnergyPlus is throw-away" framing, and the discovery that greybox §1.2's canonical parameter set was incomplete relative to `aivu_dynamic` v0.2's actual inverse-fit target list. None of these would have surfaced from reading the architecture document alone, nor from reading any single spec alone. They surface from the interaction between the spec being drafted and the locked specs it inherits from, under the pressure of making the new spec actually executable. The structure's value compounds: each spec drafted produces architectural corrections that improve every downstream spec.

Technical work next: greybox §5 v3.2 and §6 v2 final review, then §7 (recursive-mode Phase 2 solver).
