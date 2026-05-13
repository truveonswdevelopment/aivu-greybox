# aivu-greybox

Inverse identification of envelope and equipment parameters from commissioning-window telemetry. The Phoenix-pilot half of the AIVU project.

## What this repo contains

This repository holds the **greybox track**: the `aivu_greybox` Python package, the §§1-12 spec series it implements, the continuity-management documents that govern multi-session work, and the project-level architectural documents (System Architecture of Truth, the Operating System doc).

The companion repository [`aivu-physics`](https://github.com/truveonswdevelopment/aivu-physics) holds the forward-simulator codebase: `aivu_physics` Phase 1 + Phase 2, `aivu_dynamic`, `aivu_corpus`, plus builder-engagement workspaces (Beazer V752, etc.). Greybox depends on the simulator (it imports forward physics via the `ForwardChain` Protocol); the simulator does not depend on greybox.

## Why two repos

The simulator and the greybox track have different audiences (builders/HVAC contractors vs. pilot operators/homeowners/Clearinghouse customers), different physics (forward simulation vs. Bayesian inverse identification), and asymmetric dependency. Keeping them in separate repositories expresses that separation cleanly. See `continuity/AIVU_Working_Preferences_Addendum_2026_05_13.md` for the full rationale.

## Repo layout

```
code/aivu_greybox/        The Python package — §§4, 5, 6, 11, 12 implemented
  src/aivu_greybox/         Package source
  tests/                    Pytest suite — 69 tests passing against real Phoenix EPW 2024
  pyproject.toml
  README.md                 Package-level documentation

spec/                     Locked specification documents §§1-12 v0.1
                          (§§1-3 v0.1.1, §4 v3, §5 v3.3, §6 v3, §7 v1.1,
                          §8 v1, §9 v1.1, §10 v1.1, §11 v1, §12 v1)

continuity/               Continuity-management documents
  AIVU_Working_Preferences.md             Read first — how Claude and JDS work together
  AIVU_Working_Preferences_Addendum_2026_05_13.md   GitHub workflow discipline + session-close protocol
  AIVU_Phoenix_Pilot_Roadmap.md           Workstream status
  AIVU_Unfinished_Work_*.md               Items pending across sessions
  AIVU_Due_Diligence_QA.md                Investor and partner Q&A capture
  2026_*__session_log.md                  Session-by-session logs

docs/                     Project-level architectural documents
                          System Architecture of Truth v3.0.1, Operating System v9.5
```

## Current status (as of 2026-05-13)

**Spec workstream:** all 12 sections of `aivu_greybox` v0.1 spec locked. See `continuity/AIVU_Phoenix_Pilot_Roadmap.md` workstream A.

**Code workstream (B1):** §4 Fan-Heat Consistency Check, §5 Day-1-2 passive batch fit, §6 Day-4-5 active perturbation fit all implemented, with full §11 utilities and §12 signing stub. 69 tests passing against real Phoenix Sky Harbor AMY 2024 EPW weather. §7 recursive solver deferred to post-pilot per A4. See `continuity/2026_05_13__session_log.md` for the most recent session record.

**Companion-repo status:** Phase 1 envelope physics locked at v4.0, Phase 2 specs locked across eight increments. `aivu_dynamic` v0.2 locked. `aivu_corpus` implemented. Active engagement: Beazer V752 Phoenix demo.

## Next-session entry points

Read in this order:

1. `continuity/AIVU_Working_Preferences.md` — operating conventions
2. `continuity/AIVU_Working_Preferences_Addendum_2026_05_13.md` — GitHub workflow + session-close protocol
3. `continuity/2026_05_13__session_log.md` — most recent session
4. `continuity/AIVU_Phoenix_Pilot_Roadmap.md` — what's open

Then proceed with the workstream items listed in the Roadmap.

## Maintainer

Jan-Dieter Spalink.

## AI partner

Claude (Anthropic), collaborating per the working-preferences discipline. See the addendum for session-close protocol.
