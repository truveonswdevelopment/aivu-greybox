# AIVU HVAC Commissioning Protocol — Day 3-4

**Version:** v0.1 first cut, drafted 2026-05-19.
**Status:** Working draft. Specifies the data-acquisition routine that `aivu_hvac_greybox.sweep_orchestrator` implements to produce the inputs H2's joint Laplace fit consumes per H1 v0.2 §3.
**Position in document family:** Sister to H1 v0.2 (defines what data is needed) and H2 v0.1.0 (defines how the fit consumes it). This document defines how the HPM acquires the data H2 fits against.
**Briefed by:** AIVU HVAC Greybox Spec v0.2 (2026-05-18); session 2026-05-18 design discussion; session 2026-05-19 confirmation that Day 3-4's sole deliverable is the measured (Capacity, EER) surface across the operating envelope, recorded with quantified per-measurement uncertainty.

---

## §1 — Scope and position

### §1.1 — What this spec defines

The routine the HPM executes across Days 3 and 4 of the 7-Day Pre-Occupancy Cx window to acquire the operating-envelope sweep H1 v0.2 §3.1 fits against. Specifically:

- The state machine governing the HPM across the 48-hour window.
- The setpoint-driven excitation strategy (Mode 3 per session 2026-05-18) that produces measurements distributed across the (T_odb, T_wbe) operating envelope by riding the natural Phoenix-July diurnal T_odb climb and overlaying setpoint manipulations at each T_odb level.
- The settle criteria, dwell durations, and observation-quality conditions under which a sample becomes a recorded sweep point.
- The audit-log content and telemetry-capture cadence supporting the runtime per-pod sensible/latent decomposition H1 v0.2 §3.4 specifies.
- The failure modes the protocol accommodates and the recovery routines for each.

### §1.2 — What this spec does NOT define

- **What is measured.** H1 v0.2 §§1-3 are authoritative on the parameter scope (D17_pilot delivered capacity, D20_pilot EER), the bi-quadratic functional form, and the AHRI anchor constraint at (95°F, 67°F).
- **How the fit consumes the measurements.** H2 v0.1.0 implements the joint Laplace fit; this protocol produces its inputs.
- **The control law for setpoint manipulation.** The orchestrator's setpoint-tracking algorithm is implementation detail belonging in `sweep_orchestrator.py`; this protocol specifies target conditions, settle criteria, and abort conditions, not the control mathematics by which the orchestrator drives toward them.
- **Equipment-stage selection for staged HVAC.** v0.1 sweeps each equipment stage per H1 v0.2 §4.1 but does not specify the per-stage state machine; that is §11 open work informed by pilot equipment specifics.

### §1.3 — Position in AIVU's measurement architecture

This protocol is one of the two load-bearing measurement campaigns inside the 7-Day Cx window. Days 1-2 produce the envelope's passive characterization (`Day2Posterior`). Days 3-4 produce the HVAC's measured operating-envelope characterization (`Day4Posterior`). Days 5-6 use the now-measured HVAC as a controllable heat source/sink to actively characterize the envelope's thermal-mass and moisture-buffer time constants (`Day6Posterior`).

The dual-track separation is structural: the envelope is not inferred from an uncalibrated HVAC; the HVAC is not commissioned against an unknown envelope. Day 3-4's deliverable is the HVAC half of the Digital Birth Certificate, signed independently of the envelope half.

---

## §2 — Architectural framing

### §2.1 — Day 3-4 produces a primary measurement, not a fit-to-spec

The deliverable is the installed HVAC system's measured delivered capacity Q(T_odb, T_wbe) and delivered EER(T_odb, T_wbe) across the operating envelope, time-stamped, with quantified per-measurement uncertainty. There is no factory specification for installed-system end-to-end delivered performance to compare against. Manufacturers publish AHRI 210/240 ratings for the equipment-side condenser+coil pair under idealized lab conditions; that rating is not a specification of what the installed system delivers in this home with this ductwork at this site. The gap between AHRI-rated equipment performance and installed-system delivered performance is the measurement gap this protocol exists to fill.

The bi-quadratic functional form per H1 v0.2 §2 is the compact recording format for the (T_odb, T_wbe) operating surface, not a physical theory the measurements are validated against. The sweep produces the data to characterize that surface with quantified joint posterior covariance. The deliverable is "this installed HVAC system, in this home, delivers Q at this (T_odb, T_wbe) and consumes P watts to do it, with this uncertainty." Not a verdict, not a comparison to a baseline, not a contractor-quality judgment.

### §2.2 — AIVU Stance in the Day 3-4 protocol

The HPM commands setpoint targets within the equipment's normal user-accessible control envelope (Ecobee API per Hardware Spec v1.1 §4.4 pass-through). The equipment's own factory-set control logic responds — stage selection, fan speed, coil-temperature management. The protocol observes what the equipment does in response. This honors the manufacturer/contractor liability boundary per H1 v0.2 §1.3: the protocol does not assert supervisory authority on contractor-installed control logic; it observes the system as configured.

### §2.3 — Best-effort with quantified uncertainty is the success criterion

Per session 2026-05-19, the success criterion is "as accurately as the pilot circumstances permit," not "must hit a predetermined CI tightness." A sweep point that aborts because the natural T_odb crossing didn't hold or because settle was never reached is honestly recorded as not-acquired; the joint Laplace fit absorbs the reduced information into wider posterior covariance. The Day4Posterior is signed regardless; its confidence reflects what was actually acquired. The target is 5 T_odb levels × 3 setpoint conditions per level = 15 sweep points per day; the Day4Posterior records what the day actually delivered.

### §2.4 — Terminology

Two terms used throughout this protocol come from HVAC industry practice for characterizing equipment performance. Both are defined here on first use; subsequent sections use them as terms of art.

**T_odb crossing.** Outdoor dry-bulb temperature (T_odb) follows a predictable diurnal pattern in Phoenix-July: minimum near 80°F pre-dawn, peak 108-112°F mid-afternoon, declining through evening back toward minimum overnight. The temperature passes through any given intermediate value twice per day — once during the morning climb, once during the afternoon decline. A "T_odb crossing" is the moment T_odb passes through one of the protocol's chosen target levels (nominal: 80, 88, 95, 102, 108°F) within a tolerance band (initial cut: plus/minus 2°F). The protocol uses natural crossings as opportunities to acquire measurements at known outdoor temperatures without artificially manipulating outdoor conditions. The second crossing of each day (during decline) provides a natural retry opportunity at the same outdoor temperature if the first was missed or aborted.

**Sweep point.** One row of recorded measurement data: a tuple of (T_odb, T_wbe, Q_delivered, P_electrical, measurement-noise covariance), time-averaged over one settle-and-dwell cycle. The full sweep is the collection of 15 such points (target) acquired across Days 3-4, distributed across the (T_odb, T_wbe) operating envelope. The joint Laplace fit treats each sweep point as one observation; 15 observations constrain the bi-quadratic fit's 10 free coefficients plus the AHRI anchor. The term "sweep" comes from HVAC industry lab practice — equipment is characterized by sweeping it across an operating range and recording at each operating point. AIVU adopts the terminology because the resulting data products are familiar to HVAC engineers; the innovation is doing the sweep on the installed system in the home, not on equipment in a lab.

---

## §3 — Pre-conditions

The protocol may begin only when all of the following hold. Failure of any precondition delays Day 3 start until cure.

- **Day 0 install complete.** HPM connected, authenticated to the BDT, reporting telemetry at 1 Hz on all 13 pods plus the Eaton equipment-circuit power monitor. Per-pod instrumentation verification per Hardware Spec v1.1 §6 passed.
- **Days 1-2 complete.** Envelope passive observation finished; `Day2Posterior` produced and accessible. The fan_power_w measurement from the Day 1-2 fan-only window is available either via the v0.3 `Day2Posterior.fan_power_w_measured` schema field (when shipped) or via direct read from the §5 pipeline data.
- **House unoccupied.** No occupants, no operating appliances, no internal gains beyond instrumentation. The 7-Day protocol's pre-occupancy structural assumption.
- **HVAC system installed and operable.** The contractor's install is physically complete: refrigerant present and pressures within manufacturer's install range, blower runs at rated speeds, condensate drain unobstructed. These are install-completion checks confirming the equipment is mechanically capable of operating. They are not commissioning. The contractor installs; HERS may rate some operating parameters pro forma; AIVU commissions delivered capacity and EER across the operating envelope. This protocol is the commissioning.
- **Airflow paths open.** Supply registers and return register open, dampers in commissioned position, filter new or recently serviced. Per the AIVU Stance, the protocol observes the system as configured; partial register closure or a loaded filter is part of "as installed" and gets measured into the record.
- **Weather forecast cooperative.** Days 3 and 4 forecast must show clear-sky diurnal sweep with T_odb expected to reach ≥105°F mid-afternoon. Phoenix-July climatologically delivers this on most days; the protocol delays one day on cloud cover or monsoon activity.

---

## §4 — Day 3: the establishing pass

### §4.1 — Target sweep structure

5 T_odb crossing levels × 3 setpoint conditions per crossing = 15 sweep points target. T_odb crossing levels (nominal): 80°F, 88°F, 95°F, 102°F, 108°F. The 95°F crossing aligns with the AHRI rating condition and is acquired at the closest natural pass; the bi-quadratic fit's AHRI anchor constraint pins the coordinate system at (95°F, 67°F) regardless of whether the measured T_wbe at the 95°F crossing exactly hits 67°F.

Each T_odb crossing is acquired during the natural diurnal climb or fall when T_odb passes through the level (within ±2°F). The schedule across Day 3:

| Approximate local time | T_odb crossing | Diurnal phase |
|---|---|---|
| 03:00-05:00 | 80°F | pre-dawn minimum |
| 07:00-08:30 | 88°F | morning ramp |
| 09:30-11:00 | 95°F | late-morning ramp |
| 12:00-13:30 | 102°F | approaching peak |
| 14:00-16:00 | 108°F | afternoon peak |

The afternoon decline (16:00 onward) provides retry windows at 102°F, 95°F, and 88°F if any of those morning crossings missed. Pre-dawn the following morning provides a retry at 80°F.

### §4.2 — Setpoint conditions per crossing

At each T_odb crossing, the HPM commands three setpoint conditions in sequence, each producing one sweep point. The conditions drive the system through three distinct cooling-load levels; T_wbe at the return is whatever the system delivers in response.

- **Condition L (low setpoint = heavy cooling load).** T_db setpoint at low end of comfort range (e.g., 70°F), continuous fan. The system runs sustained against a large temperature differential.
- **Condition M (mid setpoint = moderate cooling load).** T_db setpoint at standard comfort (e.g., 75°F). The system runs against a moderate differential.
- **Condition H (high setpoint = light cooling load).** T_db setpoint at high end (e.g., 78°F); the system cycles against a small differential.

The HPM does not target T_wbe values. T_wbe at the return is the resulting indoor condition under each cooling-load setpoint — measured rather than commanded. In a Phoenix-July unoccupied home, T_wbe across the three conditions will span a narrow range (rough estimate 55-65°F) because outdoor humidity is low and indoor humidity sources are absent. This is the regime a Phoenix home actually operates in; the Day4Posterior records the measured (T_odb, T_wbe) trajectory the sweep produced. The bi-quadratic fit handles the resulting non-orthogonal point distribution without modification; the T_wbe-axis posterior covariance will be wider than the T_odb-axis covariance, accurately reflecting the climate's intrinsic information limit on T_wbe spread.

Per session 2026-05-19: humid operating conditions are not a meaningful concern in Phoenix, so artificial humidification to extend the T_wbe envelope is rejected for v0.1. AHRI's lab characterization of equipment behavior at high T_wbe is trusted as sufficient context for cross-climate generalization; AIVU's per-home measurement is of the regime the home actually lives in. A climate-specific protocol variant for humid climates (e.g., Gulf Coast, Southeast) would revisit this decision.

### §4.3 — Per-point execution

For each (T_odb crossing, setpoint condition) target:

1. Detect T_odb within ±2°F of crossing target on the natural diurnal trajectory.
2. Command setpoint condition via Ecobee pass-through.
3. Monitor for settle per §7. Settle window cap: 30 minutes from command. If not reached, abort sweep point; retry on next available crossing of the same T_odb level.
4. Dwell 10 minutes after settle, sampling per-pod telemetry and Eaton P at 1 Hz.
5. Time-average dwell window: Q_total_delivered = Sum over pods of m_dot_air,i times (h_return minus h_supply,i) across 13 pods; P_electrical = mean(Eaton equipment-circuit power); (T_odb, T_wbe) = window-averaged measured conditions.
6. Record the sweep point with measurement-noise covariance per Hardware Spec v1.1 sensor accuracies.
7. Advance to next setpoint condition; if T_odb still within ±2°F of crossing target, return to step 2 directly. Otherwise, mark remaining setpoint conditions at this crossing as deferred; pursue at next available crossing.

---

## §5 — Day 4: the validation pass

Day 4 repeats Day 3's structure with two procedures per H1 v0.2 §4.2:

1. **Cross-validation.** Day 4 sweep produces a second joint Laplace posterior over the 10 free coefficients; agreement against Day 3 is checked via mode-agreement-fraction-equivalent. Failure raises `HVACFitInconsistency` and halts production of the HVAC_HALF record pending engineering review.
2. **Final fit.** On successful cross-validation, Day 3 and Day 4 sweep points are combined (Day 4 measurements as additional points, not a separate fit) and the joint Laplace fit runs once over the combined data to produce the final Day4Posterior.

If Day 3 was partial (fewer than 15 acquired points), Day 4 prioritizes filling gaps before pursuing repeat measurements. The cross-validation then runs on the subset of points covered by both days; gap-fill-only Day 4 measurements contribute to the final fit but cannot be cross-validated against Day 3.

---

## §6 — Setpoint manipulation mechanics

The HPM's setpoint commands are issued via Ecobee API pass-through per Hardware Spec v1.1 §4.4. The HPM does not command compressor stage or fan speed directly; those remain under the equipment's factory control logic per the AIVU Stance.

Within a setpoint condition, the equipment's own logic determines stage selection, cycle timing, and coil temperature. The protocol observes the result. For staged equipment (single-stage or two-stage common in residential), the equipment may cycle within the dwell window; settle criteria (§7) include a cycling-quiescence check that requires the equipment to be in steady continuous operation OR in a stable repeated cycle pattern before the dwell begins.

For two-stage equipment specifically, H1 v0.2 §4.1 specifies sweeping at each stage. v0.1 of this protocol treats the equipment's natural staging behavior as the system-under-measurement: whatever stage the equipment selects in response to the setpoint condition is what gets measured. Explicit per-stage replication of the 15-point sweep is §11 open work; v0.1 measures the integrated system response.

---

## §7 — Settle criteria, dwell, and abort conditions

### §7.1 — Settle criteria

All five conditions must hold simultaneously for at least 5 consecutive minutes before settle is declared:

- T_db (return) within plus/minus 0.5°F of a running 5-minute mean.
- Indoor RH at the return within plus/minus 2% of a running 5-minute mean.
- T_odb within plus/minus 2°F of the crossing target.
- Eaton P_electrical standard deviation under 50W over the 5-minute window (no large cycling transients).
- All 13 pod ΔP readings within plus/minus 5% of each pod's running 5-minute mean (airflow steady).

The criteria allow stable cycling behavior — the equipment may be repeatedly cycling on/off, provided the cycle is stable enough that 5-minute averages are repeatable. This accommodates single-stage residential equipment, which cycles by design.

### §7.2 — Dwell window

10 minutes after settle declared. Per-pod (T, RH, ΔP) and Eaton P sampled at 1 Hz; outdoor weather station at 1-minute cadence. All telemetry retained in the audit log; sweep-point summary statistics computed as time-averages over the dwell.

### §7.3 — Abort conditions

Any of the following during settle or dwell aborts the sweep point:

- Settle window exceeds 30 minutes without all five criteria simultaneously holding.
- T_odb drifts outside plus/minus 2°F of crossing target.
- Equipment fault (high-pressure trip, fan fault, condensate-pan switch, etc.).
- Loss of telemetry from any pod or from Eaton.

Aborted sweep points retry at the next available T_odb crossing of the same level. If no retry opportunity exists within Days 3-4, the point is honestly recorded as not-acquired per §2.3.

---

## §8 — Telemetry capture and audit log

Continuous capture across the full Day 3 + Day 4 window, not just during dwells:

- Per-pod (T, RH, ΔP) at 1 Hz for all 13 pods.
- Eaton equipment-circuit P at 1 Hz.
- Outdoor (T, RH, wind speed, wind direction) from site weather station at 1-minute cadence.
- HPM-issued setpoint commands, time-stamped.
- Settle and dwell start/end times for each attempted sweep point.
- Sweep-point summary statistics (Q_total_delivered, P_electrical, T_odb, T_wbe, measurement-noise covariance) per acquired point.

The audit log is hash-referenced from the Day4Posterior record per H1 v0.2 §4.3. The continuous (T, RH) telemetry supports the runtime sensible/latent decomposition the §6 envelope active synthesizer consumes per H1 v0.2 §3.4.

---

## §9 — Failure modes and recovery

| Failure | Recovery |
|---|---|
| Single settle window exceeds 30 min | Abort sweep point; retry next T_odb crossing of same level |
| T_odb drift out-of-band during dwell | Abort; retry next crossing |
| Equipment fault | Abort sweep point; flag for contractor attention; continue at next opportunity if fault clears |
| Telemetry loss (one or more pods) | Abort current sweep point; do not begin new sweep points until telemetry restored |
| Weather forecast misses (cloud cover, monsoon) | Delay Day 3 start; protocol may extend into Day 5 if Days 3-4 produce insufficient coverage, at the cost of reduced Day 5-6 active envelope window |
| Day 3 vs Day 4 cross-validation failure | Produce Day4Posterior with `cross_validation_status = "FAILED"` and disagreement statistics; engineering review required before signing |

Day-5 extension is a per-pilot engineering call, not an automatic behavior; the protocol records what Days 3-4 produced and surfaces the coverage state to the human reviewer.

---

## §10 — Interfaces and contracts

### §10.1 — Consumes

- `Day2Posterior` from Days 1-2 envelope passive (specifically, the measured fan_power_w from the Day 1-2 fan-only window).
- Hardware Spec v1.1 Ecobee API (setpoint commands), per-pod sensors (T, RH, ΔP at 1 Hz), Eaton equipment-circuit power monitor.
- Site weather station (1-minute cadence).
- Day 3-4 weather forecast (for pre-Day-3 go/no-go decision).

### §10.2 — Produces

- `Day4Posterior` per H1 v0.2 §4.3, signed at `AttestationMoment.HVAC_HALF` by `aivu_integrity` (pilot-floor stub until G9 ships per session 2026-05-18 decision).
- Audit log of continuous telemetry across Days 3-4, hash-referenced from the Day4Posterior.

### §10.3 — Implementing module

`aivu_hvac_greybox.sweep_orchestrator` (one of the four modules deferred from H2 first-cut completion per Current State 2026-05-18). This protocol is the spec the orchestrator implements.

---

## §11 — Open questions for v0.2

1. **Settle-criteria thresholds.** §7.1 thresholds are first-cut; pilot data informs tuning. If thresholds are too tight, settle never reaches and the protocol acquires nothing; if too loose, sweep-point measurement noise rises beyond the H2 fit's defensibility.

2. **Indoor humidity range achievable in Phoenix unoccupied home.** §4.2 estimates a narrow T_wbe range (~55-65°F) across the three cooling-load conditions in a Phoenix-July unoccupied home, with outdoor humidity low and indoor humidity sources absent. Pilot data will quantify the actual range empirically. The protocol accepts the narrow range as the regime worth measuring per §4.2; the question here is operational characterization for v0.2 climate-specific tuning, not a gate on v0.1 progression. A protocol variant for humid climates would revisit this scope.

3. **T_odb crossing band tolerance (plus/minus 2°F).** Loose enough that natural diurnal climb hits the band reliably; tight enough that "T_odb during sweep point" is well-defined. Adjustment may be needed based on Phoenix-July diurnal rate-of-change empirically.

4. **Two-stage equipment per-stage replication.** §6 v0.1 treats the equipment's natural staging response as the system-under-measurement. For two-stage equipment, this means low-stage sweep points and high-stage sweep points are mixed in the same recorded dataset, distinguished only by the recorded operating-point data. H1 v0.2 §4.1 specifies sweeping each stage; explicit per-stage replication (forcing low-stage for one full sweep, high-stage for another) is an alternative that doubles sweep duration but separates the per-stage records. Decision belongs in v0.2 informed by which pilot equipment is installed.

5. **Day 3 to Day 4 to Day 5 extension policy.** If Days 3-4 produce fewer than [threshold] acquired sweep points, when does Day 5 get borrowed? The threshold and the borrowing-trigger are pilot-engineering calls; v0.1 names this as engineering review rather than automatic.

6. **Variable-speed equipment handling.** Pilot home is presumed single- or two-stage; if variable-speed equipment is installed, the modulation curve is part of the system being measured and may require additional sweep-point design.

7. **Day 3 / Day 4 sweep-point combination rule.** Carry from H1 v0.2 §10 #3. v0.1 combines Day 3 and Day 4 acquired points as additional measurements in one joint fit per H1 v0.2 §4.2 procedure 2; whether this is the right combination rule for partial-coverage Day 3 + gap-fill Day 4 is open.

---

*End of v0.1. First-cut spec; implementation belongs to `aivu_hvac_greybox.sweep_orchestrator` (deferred module per H2 first-cut). v0.2 spec-lock criterion: pilot Day 3-4 execution produces a Day4Posterior that H2 consumes successfully and that the Days 5-6 envelope active commissioning consumes successfully through the Day4Posterior interface defined in H1 v0.2 §5.*
