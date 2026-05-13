# Session log — 2026-05-12

**Author:** Jan-Dieter Spalink + Claude (Opus 4.7)
**Duration:** Tuesday morning / afternoon, Switzerland time — extended session
**Status:** session closed cleanly; substantial progress on spec items A1-A3 plus procedural framework

---

## What got done

### Cold-start ingestion, then a misfire and its recovery

Session opened with JDS uploading the May 11 end-of-session zip plus the standing reference docs. Ingestion ran clean; Claude held position until JDS set the agenda. Two zips were byte-identical; loose files included a filename collision (`AIVU_Unfinished_Work_2026_05_11.md` actually contained the 05-10 content, with the current 05-11 version in the zip). Surfaced and flagged.

JDS supplied three additional specs Claude had asked for (Phase 1 v4.0, aivu_dynamic v0.2, greybox §§1-3). Claude then read aivu_dynamic v0.2 §4.1 and Phase 1 v4.0 §10 and concluded the §§5/6 v3 drafts contained an architectural contradiction (two-state attic-main vs. single-state forward chain). Surfaced this as a four-path structured architectural question requiring JDS decision.

JDS responded with "we already decided this yesterday, please check." Claude searched conversation history and found that the May 11 session had resolved the matter — but in a direction that required reading the Phase 1 v4.0 quasi-steady §10 as the *limit case* of a dynamic extension rather than as a contradiction of it. Claude had read the specs as if looking for contradiction rather than continuity, found it, and escalated.

The postmortem named three specific failures: structural reading rather than substantive; confusion of inverse-identification parameterization with forward-physics structure; premature escalation to "JDS decides" mode. The recovery itself produced a durable lesson — see lessons section below.

### Phoenix Pilot Roadmap created as a fifth continuity-management document

JDS asked for "an outlook for the steps needed to be ready for the Phoenix one-home pilot." Claude began with questions before drafting, surfacing eight items where the roadmap's shape depended on JDS-only knowledge (pilot home identity, plan-document maturity, hardware procurement state, SoC selection, timeline, homeowner involvement timing, JDS bandwidth allocation, §7 ongoing-Cx scope). JDS answered all eight.

Roadmap drafted as a standalone tracking document with seven workstreams (A spec, B code, C HPM protocol runner, D hardware/platform, E aivu_integrity pilot floor, F operational, G strategic posture), dependency map, decision-vs-work separation, and end-of-session update discipline matching the session-log discipline. Joins Working Preferences, Architectural Distillation, Unfinished Work, and the current session log as the fifth member of the continuity-management family — distinct from Unfinished Work because the roadmap tracks one specific deliverable to one specific date, where Unfinished Work organizes work by kinds.

### Decision board cleared in one focused pass

JDS asked "what exactly am I supposed to decide, in plain English?" Claude listed five JDS-decision blocks (G1 sponsor name, G2 role name, C4 Day-3 map placement, A4 §7 scope timing, D2 SoC selection) with reasoning and a recommended order from easiest to hardest. JDS ruled on all five in one response: Beazer alone as named sponsor; Founder & Chairman as post-transition role; Day-3 map as thin Phase 2 v1 slice (Option B); §7 ongoing-Cx scope resolves at home closing (not currently decidable); SoC selection moves to active conversation with Device Solutions.

### Roadmap tightening pass

JDS asked whether anything could be tightened by giving up "non-essential" items. Claude walked through Workstreams A, B, C identifying actual slack (A8 derivations deferable, A9 short pass, B2 narrowed to pilot-specific protocols, B3 gate relaxed from bit-identity to 10⁻⁵ relative for pilot, C4 explicitly one function, C5 days-not-weeks verification, C reframed as thin orchestrator). JDS accepted all softenings.

B3 specifically: agreement floor relaxed to 10⁻⁵ relative for pilot, defended as five orders of magnitude below measurement noise floor; §3.3 bit-identity commitment stays as architectural target for v0.2. B4 (latent-side RealCycle moisture-respecting fix) and B5 (ERV heat-recovery effectiveness) approaches explained in detail and confirmed; fix recipes pinned in roadmap so they don't need to be re-derived at code time.

### §5 v3.3 closed — A1

Walk-through chosen via Option 2 (Claude-led batch walk-through, three batches, surfacing what was novel vs. what was already settled). Batch 1 (§§5.1-5.3) covered position, operational setup, fit problem. Batch 2 (§§5.4-5.6) covered prior interface, identifiability, solver. Batch 3 not needed — JDS surfaced that the relevant content "all rehearses what was discussed and decided yesterday."

One substantive addition during batch 2: Claude flagged the Laplace approximation's residual risk on non-Gaussian posteriors that the §5.7 diagnostics happen to miss. JDS directed: "v0.2 with NUTS/HMC fallback is the architectural answer — please implement." Added as v0.2 commitment in §5.6 with rationale; algorithm-class abstraction in the implementation API preserves the interface contract across substitutions. A broader operational-adaptation principle — "plans are pre-pilot; pilot data is what they get adapted against" — added to the roadmap's reading rules as rule 8. Both edits captured the same epistemic discipline: v0.1 carries the risk transparently; v0.2 architectural answer is committed; pilot data determines which homes need the fallback.

### EcoBee API command-pass-through architectural correction — folded into §6 v3

Early in the §6 walk-through, JDS surfaced that §6 v2's language about "direct HPM command bypassing the thermostat" was wrong: the actual architecture is HPM-authored commands transmitted to the equipment via EcoBee's programmable API as a command pass-through, with EcoBee not exercising its own control loop. The protocol math is unchanged (HPM still commands specific operating points and observes the response); the architectural framing is corrected.

Claude found five §6 passages needing the correction plus INV-FIT45-3's invariant statement, edited each. Roadmap C5 reworded to match. May 11 session log left alone per the principle established earlier (correct now, don't retroactively rewrite). Insight 8 in the May 11 log noted as needing revisit (architectural-vs-operational-coupling principle still stands; the specific HPM-bypasses-thermostat claim doesn't).

### Parameter renamed `foam_coupling_factor` → `ceiling_coupling_factor`

JDS asked Claude to explain how the term "foam coupling" was being used. Claude distinguished Use 1 (the parameter as a dimensionless handle on inter-zone thermal coupling) from Use 2 (the dynamical-systems phenomenon of the two coupled states), then noted that the parameter name was genuinely misleading — the spray foam at the roof deck is the envelope boundary, not the coupling element; the ceiling assembly is what conducts heat between attic and main space.

JDS decided to fix it. `ceiling_coupling_factor` chosen as the new name (descriptive, keeps "coupling_factor" so grammatical role in equations stays familiar). Rename applied across §5 v3.3 (14 occurrences), §6 v3 (9 occurrences), Phoenix Pilot Roadmap (1 occurrence), Unfinished Work doc (2 occurrences). Breadcrumb sentences in §5 v3.3 and §6 v3 status blocks document the rename for cross-document continuity. aivu_dynamic v0.2 left at old name pending its own next-version bump (principle: locked specs don't get retroactive edits). May 11 session log left alone.

### §6 v3 closed — A2

Walk-through resumed in three batches after the architectural correction and rename. Batch 1 (§6.1-6.2 position + four-phase protocol), Batch 2 (§6.3-6.5 fit problem / identifiability / solver), Batch 3 (§6.6-6.9 diagnostics / output / invariants / out-of-scope). JDS accepted all batches without further substantive change. §6 v3 closes with EcoBee architectural correction and the `ceiling_coupling_factor` rename folded in.

### §§1-3 v0.1.1 closed — A3

Greybox §§1-3 bumped from v0.1 to v0.1.1 with three coordinated changes documented in a single header revision note: parameter set extended from five to six (added `ceiling_coupling_factor` under §1.2's "Additional parameters may be committed at code-implementation time" caveat); `κ_buffer` → `C_w` settled in favor of `aivu_dynamic` v0.2 convention; the `foam_coupling_factor` → `ceiling_coupling_factor` rename documented for cross-document continuity. §2.5 parameter set updated to match. ACCA Manual J-derived defaults named as the v0.1-no-PINN-no-gbXML prior path. No other content of §§1-3 changed.

### Procedural framework named and added to Working Preferences

Toward end of session, JDS observed that the session had consisted largely of "revisiting work done before" rather than producing net-new content. Claude confirmed: no new physics, no new spec content, no new code; everything shipped was editorial polish, scope tightening, architectural correction, or decision-resolution on earlier-open questions. Reading 1 (this is a problem if the pattern repeats) and Reading 2 (cold-start sessions are structurally different) both partly true.

JDS clarified that "cold-start" had been a term-misunderstanding on Claude's part — every new session/chat is a cold-start by Claude's definition. The right question is "how do we make the post-ingestion part of a session productive?"

JDS then named the procedural shift directly: architectural bookkeeping should be Claude's call (naming, scope tightening, parameter renames, organization, code structure, default thresholds, v0.1 vs. v0.2 deferrals); system-architectural questions should be JDS's call but rare, with the bar being "this contradicts the architecture doc" or "I genuinely don't understand the architecture here" rather than "let me run this past JDS to be safe"; code is Claude writes, JDS reviews the result, wrong calls get fixed. The alternative — pre-vetting every implementation choice — is what generates the inefficiency.

JDS's framing: *"This is the discipline that makes the next 20 sessions add up to a working pilot rather than a polished set of documents about a pilot — what differentiates AIVU from a standards committee."*

Working Preferences updated with this rule in the "How Claude should behave" section, adding two lines including the standards-committee framing as the rule's diagnostic close. Net growth: two lines.

### Hardware Specification v1.1 shipped — D2 conversation now has a current spec to anchor on

JDS uploaded the April 12 Hardware Specification draft (v1.0) and asked for CPU-choice edits plus any other productive changes. Claude read the doc end-to-end, separated bookkeeping edits (Claude's call) from system-architectural questions (JDS's call) per the procedural rule landed earlier in the session, and proposed both.

JDS ruled on the three architectural questions: single spec (not split by assembly), no references to AIVU-internal docs (let Device Solutions ask), and firmware-ownership split — Device Solutions builds hardware with a minimum-viable Linux installation, AIVU loads its application stack post-delivery. JDS also surfaced a substantive architectural addition: outdoor T/RH (for the condenser-intake air) is sourced from HVAC OEM equipment data, not from an AIVU-installed sensor. Claude initially proposed integrating the OEM-API as a new HPM requirement in §4.4; JDS corrected scope — focus is what Device Solutions quotes and delivers for the pilot, period. OEM-HVAC-API integration is AIVU's job and doesn't belong in the spec.

JDS confirmed return-plenum T/RH is a thirteenth PoE-connected pod (identical electrical/mechanical to the 12 supply pods, sans SDP810 connection), not an internal-ASC SHT45.

v1.1 edit pass applied 32 substitutions: header (version, date, Beazer V752-class pilot home identifier); 13-pod architecture propagated through §1 / §1.1 / §2.3-§2.6 / §3 / §5 / §7 / §8.1; §4.3 compute requirements tightened (Cortex-A53/A55 minimum / A72/A76 preferred, ≥4 cores at ≥1.8 GHz, ≥4 GB DDR4, Ed25519 + SHA-256 hardware crypto replacing AES-256, 12+ months audit log retention); §4.4 Ecobee API language sharpened to command-pass-through architecture during active commissioning protocol; §9 firmware-ownership row rewritten per Q3 ruling; §9 production-volume row narrowed to pilot scope; §9 return-side and outdoor-T/RH rows struck entirely.

Initial repack of the .docx caused Word to flag an error (omitted `customXml/` files plus added bare directory entries during the zip). Rebuilt cleanly with the original docx's exact 19-member list and order; second attempt opened cleanly in Word.

JDS then surfaced one more architectural rule the v1.1 pass had implicitly violated: when something is out of a vendor's scope, the right move is to delete it from the document, not annotate it as out-of-scope. Annotation reveals architecture the vendor doesn't need to see. Both §9 rows (return-side, outdoor T/RH) re-struck cleanly with no residual annotation. Lesson captured below.

The v1.1 spec is now ready to send to Device Solutions and frame the D2 (SoC and Linux stack selection) conversation. Per today's risk assessment, D2 settling cleanly is the single biggest risk-reducing move available in the two-month window; v1.1 puts that conversation on a current architectural footing rather than the April 12 draft.

---

## Lessons captured for possible future promotion

**When apparent contradiction surfaces between a current draft and a locked inherited spec, the first hypothesis is missing continuity, not drafter error.** The morning's misfire was Claude reading specs for contradiction instead of for continuity, finding it, and escalating to a structured architectural question. The recovery showed that Phase 1 v4.0 §10's quasi-steady attic equation is the fast-equilibrium *limit case* of a dynamic two-state extension rather than a contradiction of it; the language differs across specs because forward-physics parameterization (`U_roof`, `U_ceil`, `A_roof`, `A_ceil`) and inverse-identification parameterization (`ceiling_coupling_factor` as dimensionless reparametrization) describe the same physics from different angles. The lesson for future Claude: when a current draft appears to contradict an inherited locked spec, the first move is to assume continuity and look for the reconciling reading. The second is to assume different notation for the same physics. Only if both fail does a real architectural question exist.

**After ingestion, Claude's default offering should be "what's the next un-drafted item?" not "let's review what exists."** Walk-throughs of existing drafts are valuable when something genuinely needs surfacing; they should not be the default. Today's session caught two real issues via walk-through (the EcoBee architectural correction and the rename) which justified the time spent — but the default shouldn't require waiting for issues to justify the pattern. If nothing's suspected to be wrong, drafts should be assumed coherent and the agenda should move forward to net-new work.

**Standards-committee energy is a real failure mode for Claude.** The org-design intuition JDS named — "I always sent our most inefficient staff to attend standards committee work" — describes a structural pattern Claude can fall into. Procedural motion (surfacing decisions, structuring options, producing taxonomies, asking "should I do A or B?") feels like rigor; it's actually substitution of procedure for substance. The Working Preferences rule added today is the structural fix; the standards-committee line at the end of that rule is the diagnostic test for whether a future session is failing in this way.

**Vendor-facing specs: delete out-of-scope items, don't annotate them.** When working on documents whose audience is an outside vendor, the right move for material that's out of scope is to delete it from the document — not to flag it as "out of scope" with explanatory text. Annotation reveals architecture the vendor doesn't need to see and invites cross-boundary questions about how that out-of-scope work gets done. Deletion is silent. The v1.1 hardware spec pass caught this twice (return-side annotation, outdoor-T/RH annotation), both corrected before shipping. The principle applies to every vendor-facing artifact and is worth holding regardless of the specific spec.

---

## Pending — handed off to next session

- **Next-session opener: A5 (§8 spec — identifiability collapse + posterior tightness).** §§5/6 both invoke §8's flag-firing logic; §8 has to exist before greybox code can implement what §§5/6 already promised. Architecturally substantive (not bookkeeping). Natural next opener.

- **A4 (§7) scope timing.** Resolves at home closing — whether the homeowner agrees to ongoing measurement determines whether §7 code is pilot-blocking or post-pilot. JDS will know mid-window when Beazer's home closing happens; until then, only §7 spec is committed as pilot-blocking.

- **D2 (SoC + Linux stack) in active conversation.** JDS to discuss with Device Solutions, now with Hardware Spec v1.1 in hand as the anchoring document. The single biggest risk-reducing move available in the two-month window. Blocks B3 (cross-platform reproducibility check) and platform-binding half of Workstream C. Worth getting on the calendar this week.

- **Hardware Spec v1.1 sent to Device Solutions.** Ready to ship; opens the D2 conversation on current architectural footing rather than the April 12 draft.

- **Architecture doc v3.0.1 fresh-eyes read (G4).** JDS to read with fresh eyes, regenerate TOC in Word for Mac, annotate anything that wince-tests. Independent of engineering track.

- **OS doc v9.6 (G3).** Three decisions now unblock it: Beazer named (G1), Founder & Chairman as role (G2), front-page named-partner sentence, Tranche 1 outcome rewrite, Tranche 2 paragraph rewritten around Founder & Chairman / incoming-CEO framing. Optional additions per JDS call: homeowner data ownership posture, training-set IP framing, displacement-curve over TAM number. Drafting can happen whenever JDS commissions it; not engineering-blocking.

- **Insight 8 (May 11 session log) needs revisit in light of EcoBee correction.** The architectural-vs-operational-coupling principle stands; the specific HPM-bypasses-thermostat claim doesn't. Worth re-examining what should graduate to Architectural Distillation when the candidate-list is next reviewed.

---

## Closing observation

Today's most durable output is not the spec sections closed or the parameter renamed. It's the procedural rule added to Working Preferences naming what Claude should decide vs. what JDS should decide vs. what code should just get written. Spec sections close once. Renames happen once. Decision-discipline shapes every session for the rest of the project.

The standards-committee framing closes the rule because it makes the diagnostic test legible to any future Claude session: if the session is generating procedural motion in proportion to substantive output, something is wrong. The corrective is to default forward — to the next un-drafted item, the next bookkeeping decision Claude can make and ship, the next piece of code that needs writing. Not back to relitigation.

Five spec items closed today (A1, A2, A3, plus G1, G2, C4 plus D2 reframed plus A4 scoping clarified). The Phoenix Pilot Roadmap exists. The decision board for engineering work is essentially clear. The hardware spec went from April 12 draft to v1.1 ready-to-send, and is the artifact that will anchor the D2 conversation. The post-Working-Preferences-rule second half of the session demonstrated the productivity gain immediately — the hardware spec edit pass was 32 substitutions decided unilaterally per the new rule, with JDS-only judgment surfaced for three architectural questions (single spec / no AIVU references / firmware ownership) plus one architectural addition (OEM-sourced outdoor T/RH) plus the late catch (delete-don't-annotate on vendor-facing material). Five JDS decisions in the second half against ~40 Claude decisions made unilaterally — the ratio the new rule is supposed to produce.

Technical work next.
