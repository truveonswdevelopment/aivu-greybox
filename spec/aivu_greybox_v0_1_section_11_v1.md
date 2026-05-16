# `aivu_greybox` v0.1 — Section 11: Common utilities

**Status:** v1.1 (day-numbering reconciliation pass per Reconciliation Workstream Phase 1, 2026-05-16: §11.2 §6 sub-table header "Day-4-5" → "Days 5-6"; Phase A and Phase B "Day 4" window references → "Day 5"; Phase C and Phase D "Day 5" window references → "Day 6"; Phase D residual rationale references to "end-of-Day-5 posterior" → "end-of-Day-6 posterior". Substantive numerical defaults unchanged. Prior v1 draft 2026-05-13, anchored against §§1-10 with §§4-6 closing notes as origin. Per the roadmap softening, the *derivations* of why each numerical default holds the value it holds are v0.2 work; v0.1 pins the values and references the originating section.

---

## 11.1 Position of §11 in the greybox spec

Two roles:

- **Numerical-defaults reference.** §§4, 5, and 6 each pin numerical defaults at the end of their closing notes. §11 collects them so a code reviewer or test author can find the canonical value of any default in one place, with a back-reference to the section that authored it.
- **Psychrometric utility surface.** §4's Fan-Heat residual and §5's two-channel likelihood both consume moist-air specific enthalpy and humidity-ratio computations. §11 names the closed-form relations used and the pinned coordinate conventions (units, reference state) so multiple `aivu_greybox` consumers agree on how T and RH translate to h and W.

§11 introduces no normative content of its own. The numerical defaults are normative in their origin sections; §11 is the index. Updates to a default happen in the origin section and propagate to §11 by reference, mirroring §9's discipline.

---

## 11.2 Numerical defaults — canonical table

Every numerical default pinned in §§4-6 closing notes, with origin section, scope of application, and the v0.2 derivation status.

### §4 — Fan-Heat Consistency Check

| Symbol | Value | Scope | Derivation status |
| --- | --- | --- | --- |
| `τ_FH` | 30 min | Minimum Fan-Heat window duration. The window must be at least this long for the time-averaged residual to settle within sensor noise. | v0.2 — derive from sensor noise spectrum and the dominant slow-thermal-mass timescale of supply ducts. |
| `τ_warmup` | 15 min | Window after fan turn-on before residual computation begins. Allows duct interior to reach thermal quasi-equilibrium with the air stream. | v0.2 — derive from supply-duct thermal mass and typical airflow. |
| `ε_FH` | 4% | Pass threshold on the relative Fan-Heat residual `R_FH / (η̂_distribution · ⟨P_fan⟩)`. | v0.2 derivation: RSS propagation across Sensirion SHT35 stack, per-terminal Venturi calibration, Eaton-breaker electrical accuracy, with √12 spatial-averaging benefit on independent noise terms and correlated treatment of systematic contributions. The 1-σ floor is ~3.6%; the threshold sits one quarter-sigma above. Tightening below 4% would put the check below its noise floor and produce spurious failures under conditions where all sensors are within spec. |
| `η_min` | 0.85 | Lower bound on physically plausible identified `η̂_distribution`. Outside-range identification triggers Fan-Heat fail. | v0.2 — derive from end-to-end delivery-instrument efficiency bounds (AHU + ducts + terminals). |
| `η_max` | 0.96 | Upper bound on physically plausible identified `η̂_distribution`. | v0.2 — same derivation as `η_min`. |
| `ΔW_max` | 0.0002 kg/kg | Maximum allowed return-side humidity-ratio drift over the Fan-Heat window. Larger drift implies an uncontrolled moisture source and disqualifies the window. | v0.2 — derive from SHT35 RH sensor noise floor and acceptable moisture-mass-balance precision. |
| `σ_spatial_max` | 0.5 kJ/kg | Maximum allowed spatial standard deviation of terminal enthalpies during a Fan-Heat window. Larger spread implies non-uniform delivery (a damper, dirty filter, or partial duct blockage) and disqualifies the window. | v0.2 — derive from the residual after `η_distribution` calibration on a known-good home. |

### §5 — Day-1-2 passive batch fit

| Symbol | Value | Scope | Derivation status |
| --- | --- | --- | --- |
| Fan-mixing schedule | 10 min/hr at clock-aligned hours | Programmed schedule for fan-only operation during the 48-hour passive window. Schedule timestamps are signed window metadata per INV-FIT12-6. | v0.1 settled. The 10 min/hr cadence is the minimum that provides 48 attic-channel observations across two diurnal cycles while leaving fans off for the bulk of the window so passive dynamics dominate. |
| Warmup exclusion | 60 s | Per fan-on interval, the first 60 s are observed for the attic channel (terminal probes during duct warmup) and excluded from the main channel (return-plenum reading). | v0.1 settled. The 60 s span matches typical duct-air thermal equilibration time after a fan-off interval. |
| `σ_T_attic` | 0.05°C | Standard deviation on the spatial-averaged attic observation during the warmup window. | v0.1 conservative; pilot validation will tighten. §5 v3.3 documents the reasoning: single-probe floor is 0.1°C, full-independent-√12 floor is 0.029°C, partial-correlation midpoint is 0.05°C. v0.2 hardens the value once pilot data constrains the actual inter-probe scatter. |
| `σ_T` | 0.1°C | Standard deviation on the main-channel return-plenum temperature observation. | v0.1 settled from Sensirion SHT35 single-probe accuracy. |
| `σ_W` | derived from SHT35 RH | Standard deviation on the moisture-ratio observation, derived from SHT35 ±1.5% RH translated to humidity-ratio space via §11.3 psychrometrics. | v0.1 settled (RH-to-W translation is a §11.3 closed-form computation, not a free parameter). |
| Mode-agreement failure threshold | 5% of prior σ | If the four prior-perturbed Laplace restarts return modes that disagree by more than 5% of the prior σ on any parameter, convergence is flagged as failed per INV-FIT12-4 and no `Day2Posterior` is signed. | v0.1 settled. |
| Prior-perturbed restarts | 4 | Number of independent L-BFGS-B starts from prior-perturbed initial values, used for the Laplace mode-agreement check. | v0.1 settled. Four is the minimum that detects multi-modal posteriors at acceptable wall-clock cost; tighter coverage is v0.2 NUTS/HMC work per §5.6. |

### §6 — Days 5-6 active-perturbation batch fit

| Symbol | Value | Scope | Derivation status |
| --- | --- | --- | --- |
| Phase A duration | 18 h | Continuous-fan continuous-compressor cooling drive at full capacity. The 18-hour hold is what drives the home toward the quasi-asymptote that the inverse fit reads against the §6.4 `R_eff` posterior tightness. | v0.1 settled. Aspirational-not-strict steady state framing per §6.2. |
| Phase B duration | 6 h | Decay phase with mixing fan, compressor off. Provides the post-perturbation decay trajectory that further constrains envelope time constants. | v0.1 settled. |
| Phase C duration | 18 h | Reverse drive — fan-only extended duty 50/10 schedule, no compressor. The fan-heat injection plus passive solar gain reverses the indoor trajectory upward and provides the slab-coupling and moisture-side identification per §6.4. | v0.1 settled. |
| Phase D duration | 6 h | Closing observation with mixing fan, no command from the protocol. Phase D is the held-out validation window per §6.2 architectural purpose. | v0.1 settled. |
| Phase A asymptote rate threshold | 0.1°C/hr | Indoor temperature rate-of-change below which Phase A is considered to have reached the quasi-asymptote regime. Used in §6.6 convergence diagnostics. | v0.1 settled. |
| Phase D residual tolerance | 5% relative | Maximum allowed relative residual between Phase D observed trajectory and the trajectory predicted by the posterior derived from Phases A+B+C. Exceeding this triggers §6.6 convergence failure per INV-FIT45-6. | v0.1 settled. |
| Protocol-adherence tolerance | ±15 min on phase transitions | Maximum allowed deviation between programmed and actual phase-transition timestamps per INV-FIT45-4. | v0.1 settled. |
| `σ_T_attic_degraded` | 0.10°C | Wider uncertainty bound on attic-channel observations during Phase C's 50/10 schedule, where the 10-minute fan-off intervals are too short for ducts to fully equilibrate with attic air. Doubles `σ_T_attic` from §5. | v0.1 settled. Documented inline in §6.3. |

---

## 11.3 Psychrometric utility surface

§4's Fan-Heat residual and §5's two-channel likelihood both consume moist-air specific enthalpy and humidity ratio computed from measured T and RH. §11.3 names the closed-form relations used by every greybox computation so consumers agree on units, sign conventions, and the reference state.

### 11.3.1 Pinned coordinate conventions

- **Temperature** is in °C unless otherwise specified. Conversions to/from °F happen only at the report-emission boundary per §1.3 unit conventions; all internal computations use SI.
- **Humidity ratio** `W` is in kg water vapor per kg dry air.
- **Pressure** is the local atmospheric pressure, computed from elevation (Phoenix pilot: 335 m, P_atm ≈ 97.3 kPa). v0.1 treats P_atm as a constant per home; v0.2 may pull live barometric pressure from the weather station if Phase 2 work requires the precision.
- **Moist-air specific enthalpy** `h(T, W)` is referenced to 0°C dry air and 0°C saturated liquid water per ASHRAE Fundamentals.

### 11.3.2 Closed-form relations

**Moist-air specific enthalpy** (ASHRAE Fundamentals Chapter 1):

> h(T, W) = 1.006·T + W·(2501 + 1.86·T)  [kJ/kg dry air]

with `T` in °C and `W` in kg/kg dry air. This is the form §4.5 quotes verbatim; it is reproduced here for canonical reference.

**Saturation vapor pressure** uses **Hyland-Wexler 1983** (ASHRAE Fundamentals, IAPWS-equivalent for the air-conditioning temperature range):

> ln(P_ws) = c1/T + c2 + c3·T + c4·T² + c5·T³ + c6·T⁴ + c7·ln(T)

with `T` in K and `P_ws` in Pa. Coefficients are the standard Hyland-Wexler 1983 values for liquid water saturation (240 K ≤ T ≤ 533 K); the implementing library is named in the package version pins per §3.3.

**Partial pressure from RH:**

> P_w = (RH / 100) · P_ws(T)

**Humidity ratio from partial pressures:**

> W = 0.62198 · P_w / (P_atm − P_w)

where 0.62198 is the ratio of molecular weights (water vapor / dry air).

These four relations compose into the T-and-RH-to-h pipeline that §4.5 calls. They also compose into the saturation, dewpoint, and coil-dewpoint computations §6's latent-side excitation reference (roadmap B4 fix recipe) requires when greybox code lands.

### 11.3.3 Implementation library binding

Per §3.3 reproducibility commitment, the psychrometric library used by greybox is pinned in the package version manifest. v0.1 uses a single library across macOS and embedded Linux (the specific library is a §3.3 numerical-stack pin, not §11 content). The closed-form relations above are the contract; the library is the implementation of the contract.

Two consequences:

- Multiple psychrometric libraries (e.g., CoolProp, ASHRAE's IP-3 reference implementation, psychrolib, hand-rolled) produce numerically slightly different `h(T, W)` and `W(T, RH)` results due to internal precision and series-truncation choices. The §3.3 bit-identity commitment makes the choice of library a load-bearing decision; a v0.2 swap to a different library is a spec change with bit-identity regression implications, not a free reimplementation.
- The closed-form relations above are the *interface*; an implementation that uses a different internal formulation (e.g., a polynomial regression on tabulated steam data) but reproduces the §11.3 closed forms to within bit-identity is conformant. v0.1 v.s. v0.2 swaps must pass §10.4 reproducibility tests.

---

## 11.4 What §11 does not do

- **Does not derive the §§4-6 numerical defaults.** Derivations are v0.2 work. The "Derivation status" column in §11.2 names the v0.2 deliverable; v0.1 pins values, code references them.
- **Does not modify any default.** Updates land in the origin section's closing notes; §11.2 follows. A discrepancy between §11.2 and an origin section is always resolved in favor of the origin section.
- **Does not introduce new utilities.** If a future greybox computation needs a new closed-form relation (e.g., the latent-side coil-dewpoint computation from roadmap B4), it lands here when the section that consumes it lands.
- **Does not specify the implementing library.** The pinned library is a §3.3 numerical-stack item, not §11 content. §11 specifies the interface; §3.3 pins the implementation.
- **Does not contain test code.** Verification that the §11.3 closed forms match the implementing library to within bit-identity is a §10.4 reproducibility test.

---

## 11.5 Out of scope

The following are explicitly out of §11 v0.1:

- **The derivations of the numerical defaults**, deferred to v0.2 per the roadmap softening. The "Derivation status" column names each v0.2 deliverable.
- **Pressure-corrected psychrometrics for variable elevation.** v0.1 treats P_atm as a per-home constant; v0.2 may pull weather-station pressure for higher-precision Phase 2 work.
- **Ice/frost regime psychrometrics.** Hyland-Wexler 1983 has a separate set of coefficients for the ice regime (T < 0°C). Phoenix-July does not exercise this regime; greybox v0.1 omits the cold-side coefficients. Cohort expansion into northern climates triggers a v0.2 §11 extension.
- **Real-gas / high-precision deviations.** The ideal-mixture form of the moist-air enthalpy relation is sufficient for greybox's measurement precision; real-gas corrections (compressibility factors, dry-air enthalpy beyond the 1.006·T term) are below the noise floor of the SHT35 sensor stack and are v0.2 work if they ever earn their place.

---

*End of §11 v1 draft. Numerical defaults canonical table reproduces 22 values pinned across §§4-6 with v0.2 derivation status flagged for each. Psychrometric utility surface specifies four closed-form relations (ASHRAE Fundamentals enthalpy, Hyland-Wexler 1983 saturation vapor pressure, partial pressure from RH, humidity ratio from partial pressures) with pinned coordinate conventions (SI internal, °C, kg/kg dry air, P_atm per-home constant). Implementation library binding deferred to §3.3 numerical-stack pin. §12 (signing chain) opens next.*
