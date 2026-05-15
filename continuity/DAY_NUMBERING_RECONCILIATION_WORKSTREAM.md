# Day-Numbering Reconciliation Workstream

**Status:** Identified and scoped 2026-05-15. Not yet executed.
**Inventory:** See `DAY_NUMBERING_RECONCILIATION_INVENTORY_2026_05_15.txt` in this directory (623 lines, complete audit of all day-numbering references in both `~/aivu-greybox` and `~/aivu`).
**Estimated effort:** 3-5 focused sessions plus validation.

---

## The problem

The greybox spec set (§1-12) and code base were written against a **5-Day commissioning protocol**:

- Days 1-2: passive envelope observation → `Day2Posterior` / `ENVELOPE_HALF_INITIAL`
- Day 3: HVAC operating-point map → `Day3Map` / `HVAC_HALF`
- Days 4-5: active envelope perturbation → `Day5Posterior` / `ENVELOPE_HALF_FINAL`

The architecture has evolved to a **6-Day commissioning protocol** with cleaner 2+2+2 functional separation:

- Day 0: equipment installation
- Days 1-2: passive envelope observation → `Day2Posterior` (unchanged)
- Days 3-4: HVAC commissioning (operating-point sweep on Day 3, repeated Day 4 for validation) → `Day4Posterior` / `HVAC_HALF`
- Days 5-6: active envelope testing using calibrated HVAC → `Day6Posterior` / `ENVELOPE_HALF_FINAL`

The new framing is documented authoritatively in:
- `~/aivu-greybox/AIVU_MRAC_Architecture_v0_1.md` (committed 2026-05-15, repo-root)
- `~/aivu-greybox/continuity/AIVU_Critical_Path_Dependency_Map_v0_2.md` (committed earlier)

But §1-12 specs and the greybox source code still use the 5-Day labels throughout. This contradiction must be reconciled before any home signs records that downstream consumers (HPM, BDT, Clearinghouse) might misinterpret.

---

## Scope (4 phases)

### Phase 1 — Spec rewrite (5-Day → 6-Day)

Files affected (all in `~/aivu-greybox/spec/`):

- `aivu_greybox_v0_1_section_5_v3_3.md` — Day-1-2 passive (mostly stays; clarify that Day 1 is the first measurement day, NOT Day 0 install)
- `aivu_greybox_v0_1_section_6_v3.md` — heaviest rewrite. The four-phase table explicitly says "Day 4, 00:00-18:00" / "Day 5, 18:00-24:00" etc. Update to Day 5 / Day 6. Reference to "Day 4-5" throughout becomes "Day 5-6."
- `aivu_greybox_v0_1_section_7_v1_1.md` — ~20 references to "Day-5 posterior" / "§6 Day-5" become "Day-6 posterior" / "§6 Day-6." Section also has many "Day-3 map" references that become "Day-4 map."
- `aivu_greybox_v0_1_section_8_v1.md` — "end-of-Day-2" stays; "end-of-Day-5" becomes "end-of-Day-6." Protocol-string identifier `§6_day5_active_compounded` becomes `§6_day6_active_compounded`.
- `aivu_greybox_v0_1_section_9_v1_1.md` — invariant block names `INV-FIT12-*` and `INV-FIT45-*` are the open question. Two options: (a) keep names as historical labels not literal day references, with a docs note explaining the mismatch; (b) rename to `INV-FIT12-*` and `INV-FIT56-*` (the latter is awkward but accurate). My preference is (a) — these are stable identifier strings that external code may already reference, and renaming creates more churn than it saves. The names become opaque IDs whose specific day-pair etymology is a footnote.
- `aivu_greybox_v0_1_section_10_v1_1.md` — cross-references update following the upstream sections.
- `aivu_greybox_v0_1_section_11_v1.md` — "Day-2 / Day-3 / Day-5 posterior" references become "Day-2 / Day-4 / Day-6."
- `aivu_greybox_v0_1_section_12_v1.md` — AttestationMoment enum value names stay (`ENVELOPE_HALF_INITIAL`, `HVAC_HALF`, `ENVELOPE_HALF_FINAL`) because they describe semantic moments not days. Comment text describing the moments updates to reference the new day numbering.

Estimated: ~1.5 sessions for the spec rewrite. Pass A / Pass B pattern recommended (Pass A = drafts of all updated sections; Pass B = final review + commit).

### Phase 2 — Records dataclass rename

Files affected:
- `~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/records.py` — `Day5Posterior` class → `Day6Posterior`. Field `day3_map_hash` → `day4_map_hash`. `baseline_day5_posterior_hash` → `baseline_day6_posterior_hash`.

This is mechanical but cascades through:
- `active_fit.py` — all `Day5Posterior` imports and instantiation; all `day3_map_record_hash` / `day3_map_hash` references
- `tests/test_active_fit.py` — fixture names, test method names, fixture data
- `tests/test_g8_closed_loop.py` — `result.day2_posterior.common.*` stays; nothing day-5 in this test
- `tests/test_passive_fit.py` — `result.day2_posterior` stays

Estimated: ~0.5 sessions including test re-run.

### Phase 3 — Code field rename in active_fit.py

`active_fit.py` parameters `day2_posterior_record_hash` (stays) and `day3_map_record_hash` (→ `day4_map_record_hash`). The function `run_active_batch_fit` signature changes; all callers update. Internal variables follow. The "§6_day5_active_compounded" protocol string becomes "§6_day6_active_compounded".

The `AttestationMoment` enum stays unchanged (no day numbers in its value strings). The comment in `_signing_stub/integrity_api.py` describing which moments map to which days needs a touch.

Estimated: ~0.5 sessions, mostly mechanical with test re-run.

### Phase 4 — Continuity documents touch-up

Files affected:
- `~/aivu-greybox/continuity/AIVU_Phoenix_Pilot_Roadmap.md` — "§6 Day-4-5 active perturbation" → "§6 Day-5-6 active perturbation"; "signed Day5Posterior" → "signed Day6Posterior"
- `~/aivu-greybox/continuity/2026_05_11__session_log.md` and `2026_05_13__session_log.md` — historical session logs; my preference is to LEAVE THESE as-is (they're an accurate record of work-at-the-time using the then-current labels). Add a one-line note to each: "Day-numbering used in this log is the 5-Day protocol; see AIVU_MRAC_Architecture_v0_1.md for the current 6-Day framing."
- `~/aivu-greybox/continuity/AIVU_Critical_Path_Dependency_Map_v0_2.md` — already uses 6-Day labels; the two TODOs it lists ("Records dataclass rename from `Day5Posterior` to `Day6Posterior`" and "AttestationMoment-emission day labels updated") get crossed off as the reconciliation work completes.

Estimated: ~0.5 sessions.

---

## Recommended execution order

1. **Phase 1 first.** Spec rewrite establishes the authoritative new framing. Other phases reference Phase 1 outputs.
2. **Phase 2 + Phase 3 together.** Single Pass A draft of both code changes (records.py + active_fit.py + test updates), single Pass B verification with full test-suite re-run including G8.
3. **Phase 4 last.** Continuity touch-ups happen after the substantive changes are validated.

After all four phases complete, the day-numbering inventory should re-run and produce a dramatically smaller hit count — only legitimate references like Section 5's "Day 1 is the first measurement day, Day 0 is install."

---

## Inputs

- `DAY_NUMBERING_RECONCILIATION_INVENTORY_2026_05_15.txt` — complete grep audit, 623 lines
- `~/aivu-greybox/AIVU_MRAC_Architecture_v0_1.md` — authoritative new framing
- `~/aivu-greybox/continuity/AIVU_Critical_Path_Dependency_Map_v0_2.md` — already-identified TODOs

## Outputs (when complete)

- Updated §5-§12 spec sections, internally consistent and matching the 6-Day framing
- Renamed `Day5Posterior` → `Day6Posterior` everywhere it appears
- Renamed `day3_map_record_hash` → `day4_map_record_hash` in `active_fit.py` and its tests
- All 79+ tests still passing after the rename cascade
- Cross-out of the two TODOs in Critical Path Dependency Map v0.2

## Out of scope

- The `INV-FIT12-*` and `INV-FIT45-*` invariant block names: kept as historical identifiers, not literal day labels (decision per Phase 1 above; revisit if needed).
- The `AttestationMoment` enum value strings (`envelope_half_initial`, `hvac_half`, `envelope_half_final`): no day numbers in them, no change needed.
- The §11.2 amendment and its seven-parameter canonical set: orthogonal to day-numbering, not affected.
- Re-running G8 with different protocol days: G8 tests greybox machinery at 12-hour cadence and doesn't reference protocol days at all.
