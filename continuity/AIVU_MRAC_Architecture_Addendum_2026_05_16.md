# AIVU MRAC Architecture — Addendum 2026-05-16

**Status:** Addendum to `AIVU_MRAC_Architecture_v0_1.md`. Folds into the canonical document at next maintenance pass. Until then, this addendum is read together with the main document.

**Purpose:** Captures the temporal-identification dimension that emerged from the 2026-05-16 afternoon diagnostic dive on the §5 fit. The MRAC framing already covered the real-time control loop and the bootstrap-vs-continuous regime distinction. The addendum extends the framing to the *measurement* dimension: the same MRAC principle that handles drift-tracking for well-identified parameters also handles initial identification of weakly-identified parameters at multi-month and multi-year horizons.

---

## What the addendum adds, in one paragraph

The MRAC doc v0.1 articulates the HPM running a continuous-adaptation real-time control loop using current posterior estimates. The addendum names a second MRAC operation at a different time horizon: opportunistic capture of regime-clean observation windows, accumulated per-regime over months and years, feeding the BDT periodically for posterior refinement on parameters that 7-Day Cx cannot pin. One mechanism, two roles. The continuous-adaptation principle covers both regimes; the difference is the accumulation horizon and what gets refined.

---

## Per-parameter epistemic horizon

The §11.2 amendment's seven-parameter canonical set names *what* AIVU characterizes. The 2026-05-16 afternoon diagnostic surfaced that §5 + §6 jointly cannot identify all seven parameters within 7 days regardless of fit cleverness. The architectural response: each parameter has a primary identification horizon and (for weakly-identified parameters) a secondary refinement horizon.

Provisional per-parameter horizon assignment, to be formalized in the §11.x amendment (T4 in Critical Path Dependency Map v0.4):

- **R_opaque, U_fenestration, ceiling_coupling_factor:** primary horizon = Cx (§5 Stage 1, diurnal-thermal band, night-weighted residuals). These are the parameters §5 passive observation is structurally suited to identify under sequential identification.
- **C_stack, C_wind:** primary horizon = Cx (§5 Stage 2, synoptic-wind band) with secondary refinement over operational months. Wind-driven infiltration's signature requires both clean wind events of the right magnitude AND Stage 1 parameters pinned; 7 days of Phoenix-July weather may have a few clean events, operational telemetry accumulates many.
- **C_house:** primary horizon = Cx (§6 Stage 3, active thermal night transients) with secondary refinement over operational months. Thermal-mass time constant identifiable from HVAC-driven excursions at night with §5 parameters pinned.
- **C_w:** primary horizon = Cx (§6 Stage 4, active moisture night transients) with secondary refinement over operational months. Moisture-buffer time constant identifiable from compressor-on dehumidification at night.

Refinement horizons may extend further than "operational months" for parameters with rare regime-clean events. C_stack/C_wind in a low-wind climate may have meaningfully tight posteriors only after multiple seasonal cycles.

---

## The HPM gains an opportunistic-measurement role

The MRAC doc v0.1 describes the HPM as MRAC process manager running the bounded real-time control loop. The addendum extends this:

The HPM also tags observation windows by their regime classification, accumulates per-regime statistics in local storage, and feeds them to the BDT periodically. Specifically:

- The HPM carries the same regime-classification machinery the Cx fit uses (diurnal-thermal night, synoptic-wind, active-thermal-transient, active-moisture-transient).
- Each observation window the HPM classifies "regime-clean" (matches one regime cleanly, with no contamination from other regimes' active signals) is tagged and stored.
- Per-regime sufficient statistics accumulate locally over weeks/months. The HPM doesn't try to do the fit itself; it accumulates the data the BDT will fit.
- Periodically (cadence TBD; likely daily-to-weekly), the HPM ships per-regime sufficient statistics to the BDT. The BDT runs the staged fit at its scale, updating per-home posteriors with the new data.
- The updated per-home posterior comes back to the HPM as informative prior for ongoing control decisions, refining what the real-time loop trusts.

This is the same MRAC continuous-adaptation principle the v0.1 doc describes, applied at a different timescale. Real-time loop: fast adaptation against control-relevant disturbances using current posterior. Measurement loop: slow refinement of the posterior itself using accumulated regime-clean windows.

---

## Signed-record schema evolves

The Digital Birth Certificate from §5/§6 Cx carries (mean, covariance) per parameter today. With per-parameter horizons surfaced, the signed-record format gains per-parameter epistemic status:

- **Mean and covariance** (as today)
- **Identification horizon** — at what point in time will this parameter's posterior be considered production-threshold? "Cx" for parameters identified within the 7 days; "Cx + 6mo" or "Cx + 12mo" for parameters requiring operational refinement.
- **Vintage** — when was this record signed? A record's vintage tells the consumer how much operational telemetry has been folded in.
- **Confidence state** — "pinned-at-Cx", "preliminary-refining", "production-threshold-at-vintage". Tells the consumer how to weight the parameter in downstream decisions.

A consumer of the Clearinghouse data products who needs C_house tighter than the Cx posterior provides knows whether the record is too young (preliminary) or vintage-enough (production). The Clearinghouse can offer products differentiated by vintage. This is the §12.x amendment scope (T5 in Critical Path Dependency Map v0.4).

---

## Asymmetry with HERS deepens further

The MRAC doc v0.1 already articulates the structural displacement of HERS as cumulative-measurement replacing ceremonial-paperwork. The addendum sharpens: AIVU is not just "better measurement at commissioning" but "measurement that gets sharper with operational history." HERS produces a snapshot that is final at the moment it is signed. AIVU produces a signed record that is honest about its preliminary state at Cx and gets refined over the asset's life. HERS-replaced-by-AIVU is not a feature comparison; it is a category difference.

A 5-year-old AIVU-instrumented home has tighter posteriors than a 7-day-old one. A 50-year-old home has tighter still. The fleet-level Clearinghouse data asset compounds along this dimension separately from the N-homes dimension. This is the moat that the System Architecture and OS docs need to make explicit at the strategic level.

---

*End of addendum 2026-05-16. Folds into canonical AIVU_MRAC_Architecture_v0_1.md at next maintenance pass. Companion documents that will follow this addendum into Git: the AIVU Temporal Identification Architecture document (T1 in Critical Path Dependency Map v0.4), the §11.x amendment for per-parameter horizon assignment (T4), and the §12.x amendment for signed-record schema evolution (T5).*
