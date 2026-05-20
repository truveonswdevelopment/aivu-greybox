# AIVU Operational Reference

**Audience:** Whatever Claude session needs concrete operational procedure beyond what `AIVU_Working_Preferences.md` carries inline.
**Purpose:** Full repository content map, six-step session-close protocol, mid-session recovery, GitHub authentication notes, Claude Temp Folder discipline.
**Location:** `~/aivu-greybox/continuity/AIVU_Operational_Reference.md`. JDS uploads this file when its content is needed — typically at session close, during mid-session recovery, or any time Claude needs to know where a file belongs. Not in the cold-start folder; not read at session start.

This file replaces the prior `AIVU_Working_Preferences_Operational.md` (the "operational addendum"). Renamed because "Operational addendum" echoed the Working Preferences naming and produced confusion. Relocated from cold-start to continuity because its content is needed in specific operational moments rather than at every session start.

---

## Local paths — single source of truth

JDS's Mac, user `drjandspalink`. Both Git clones live at the top of the home directory:

| Repository | Local clone path | GitHub URL |
|---|---|---|
| `aivu-physics` | `/Users/drjandspalink/aivu/` | `https://github.com/truveonswdevelopment/aivu-physics` |
| `aivu-greybox` | `/Users/drjandspalink/aivu-greybox/` | `https://github.com/truveonswdevelopment/aivu-greybox` |

**JDS's shell shorthand:** `~/aivu/` and `~/aivu-greybox/` (the `~` expands to `/Users/drjandspalink/`).

**Important convention:** Claude must use these paths verbatim. Past confusion arose because past-Claude assumed the simulator clone lived at `/Users/drjandspalink/Documents/AIVU_PROJECT_REPOSITORY/project_documents` (which is NOT a Git repository) instead of the actual location `/Users/drjandspalink/aivu/`. Always use the paths in the table above.

**Other paths of interest on JDS's Mac:**

| What | Path | Purpose |
|---|---|---|
| Cold-start folder | `~/Desktop/Claude cold start Uploads/` | Holds the three docs read at session start: `AIVU_Current_State.md`, `AIVU_Working_Preferences.md`, `AIVU_Architectural_Distillation.md` |
| Claude Temp Folder | `~/Desktop/Claude Temp Folder/` | Transit zone for files Claude generates during sessions. Bulk-moved to AIVU Archive at end of working day (no per-file judgment required). |
| Local archive | `~/Desktop/AIVU Archive/` | Flat folder that receives Temp Folder contents in bulk. JDS curates at his own pace — sorts GitHub-canonical duplicates from session-zips-with-chat-content from genuine intermediate drafts. Not synced to Drive. |
| Downloads | `~/Downloads/` | Where session-end zips and downloaded artifacts land. |
| Google Drive archive | (JDS's chosen location) | Off-repo audit-trail archive for files Drive specifically needs to hold: session-end zips that include chat context, intermediate drafts with no GitHub equivalent, partner-facing materials. Lifted from AIVU Archive at JDS's discretion; reserved for content GitHub does NOT carry. |

---

## Repo content map — what goes where

**Why two repos and not one.** The two repositories express an architectural separation. `aivu-physics` is forward-simulator code for builders and HVAC contractors; `aivu-greybox` is inverse-identification code for the Phoenix pilot, aimed at homeowners, Clearinghouse customers, and pilot operators. Different audiences, different physics, asymmetric dependency: `aivu-greybox` imports from `aivu-physics` via the `ForwardChain` Protocol, but `aivu-physics` does not import from `aivu-greybox`. Adding greybox to the simulator repo would dilute the simulator's identity for the builder audience; separate repos express the architectural separation cleanly.

### `aivu-physics` (forward simulator)

```
spec/                                  Authoritative simulator specs (locked)
  phase1/                              Envelope physics
  phase2/increments/                   Phase 2 spec increments
  phase2/handoffs/                     Session-close handoffs for Phase 2
  AIVU_Dynamic_Envelope_Spec_v0_2.md   Dynamic envelope spec

code/                                  Implementation
  phase1/aivu_physics/                 Phase 1 envelope physics package
  aivu_dynamic/                        Dynamic envelope simulator
  aivu_corpus/                         Cohort orchestrator
  (phase2/ subpackages — to be created when Phase 2 v1 code begins)

extraction/                            Working coding-reference documents

engagements/                           One directory per builder engagement
  beazer_v752/                         Beazer V752 (Phoenix demo, active)
    scripts/, findings/, data/

PROJECT_STATE.md                       Living status board — MUST be updated each
                                       time anything in this repo changes
README.md                              Repo-level overview
SESSION3_SIGNOFF.md, etc.              Past session signoffs
.gitignore
```

### `aivu-greybox` (inverse identification / pilot)

```
code/aivu_greybox/                     The Python package
  src/aivu_greybox/                    Package source (passive_fit, active_fit,
                                       fan_heat, forward_chain, real_chain,
                                       epw_loader, records, defaults,
                                       psychrometrics, etc.)
  tests/                               Pytest suite (test_g8_closed_loop.py,
                                       test_passive_fit.py, etc.)
    fixtures/                          Committed test data — Phoenix_AMY_2024.epw
  pyproject.toml, README.md

check_env.sh                           Environment self-check (repo root)
run_tests.sh                           Test runner via the repo's own venv (repo root)
.venv/                                 Virtual environment (repo root; gitignored)

spec/                                  Sec 1-12 v0.1 series spec documents
                                       (plus the Sec 11.2 amendment file)

continuity/                            Cross-session governance documents
  AIVU_Critical_Path_Dependency_Map_vX_Y.md   Authoritative dependency graph
  AIVU_Operational_Reference.md        (this file)
  AIVU_Phoenix_Pilot_Roadmap.md        Workstream status
  AIVU_Unfinished_Work_YYYY_MM_DD*.md  Pending items per session
  AIVU_Due_Diligence_QA.md             Investor and partner Q&A
  DAY_NUMBERING_RECONCILIATION_*.md    Active workstream documents
  YYYY_MM_DD__session_log.md           Session-by-session logs

docs/                                  Project-level architectural documents
                                       (System Architecture of Truth, Operating System)

AIVU_MRAC_Architecture_v0_1.md         Top-of-hierarchy MRAC framing (repo root)
README.md
.gitignore
```

Note: `AIVU_Working_Preferences.md` and `AIVU_Architectural_Distillation.md` live in the cold-start folder only, not in either Git repo. The Git copies were deliberately retired (2026-05-14 decision) to remove the drift risk between cold-start and Git. `AIVU_Current_State.md` follows the same convention.

### What does NOT go on GitHub

- **Bulk simulation outputs** (multi-MB JSON, rendered PNG/PDF charts). Per existing `aivu-physics` convention, these go to Google Drive with each engagement's `data/README.md` pointing at them.
- **`.DS_Store` and other macOS metadata.** Already in `.gitignore` for both repos.
- **Pre-final draft versions of documents.** When §5 v3.4 ships, v3.0 / v3.1 / v3.2 / v3.3 do not go to GitHub. Only the locked version. Older versions flow through AIVU Archive and end up in the Google Drive archive at JDS's discretion for audit trail.
- **Sensitive vendor or partner information** until each partner has signed appropriate NDAs.
- **The three cold-start documents** (`AIVU_Working_Preferences.md`, `AIVU_Architectural_Distillation.md`, `AIVU_Current_State.md`) per the convention named above.

---

## Standard session-close procedure

Claude executes this at the end of every session that produced artifacts. The five-item end-of-session checklist in `AIVU_Working_Preferences.md` references this procedure; the steps below are the full version. Six steps, every time, no shortcuts.

### Step 1 — Identify the destination repo for each artifact

For each file produced in the session, Claude states:

> "This file goes into `aivu-greybox` under `spec/`."
> "This file updates `aivu-physics`'s `PROJECT_STATE.md`."
> "This file is intermediate; it goes to Google Drive archive at session close, not to GitHub."

If a file's destination is unclear, surface to JDS for decision before staging.

### Step 2 — Bring local clones current (`git pull`)

```
cd ~/aivu && git pull origin main
cd ~/aivu-greybox && git pull origin main
```

This catches any commits made from elsewhere (other machines, GitHub web edits) before Claude adds new ones. Fast-forward expected; if a merge conflict appears, stop and surface to JDS.

### Step 3 — Stage files in the appropriate local clone

For new files: copy them into the correct subfolder of the correct clone.

```
cp /home/claude/work/something.py ~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/
```

For modified files: edit them in place in the clone (via text editor or `sed`).

Never stage files in `~/Desktop/Claude Temp Folder/` and expect them to land on GitHub. The Claude Temp Folder is a transit zone, not a Git working tree.

### Step 4 — Commit, one logical change per commit

```
cd ~/aivu-greybox
git add <specific files, not blind `git add .`>
git status      # verify staging is correct
git commit -m "Concise descriptive message"
```

Use multiple commits if the work spans separable concerns (spec edits + code shipped = two commits). Use single-line commit messages with no special characters (`§`, `σ`, em-dashes, smart quotes) that have broken heredoc handling in past sessions — write "sec 5" not "§5", "sigma" not "σ", straight quotes not curly. Full commit detail belongs in the session log, not the commit message.

### Step 5 — Push and verify

```
git push origin main
git status      # must show "Your branch is up to date with 'origin/main'"
git log --oneline -5    # confirm the new commits are present
```

A session is not closed until `git status` returns clean and `git log` shows the new commits.

### Step 6 — Move Temp Folder contents to AIVU Archive

At end of working day (which is when "session close" actually happens — often hours after Claude has stopped responding):

```
mv ~/Desktop/"Claude Temp Folder"/* ~/Desktop/"AIVU Archive"/ 2>/dev/null
```

One operation, no per-file judgment required. The Temp Folder ends up empty; AIVU Archive accumulates the day's output for later curation.

The `2>/dev/null` suppresses the "no matches" message if the Temp Folder is already empty. The double-quotes around the folder names handle the space in each name.

**AIVU Archive curation happens at JDS's pace, not at session close.** When JDS has capacity, the three-bucket disposition applies to the Archive's contents:

- **Canonical version on GitHub →** delete (GitHub is the archive; local duplicates are noise).
- **Not on GitHub but worth keeping** (session-end zip that includes chat context, intermediate draft with no GitHub equivalent, partner-facing material that won't go to Git) **→** lift to Google Drive archive.
- **Duplicates, `.DS_Store`, or other macOS metadata →** delete.

If a file's status is unclear, leave it in AIVU Archive until clarity arrives — there's no penalty for deferring the call.

---

## Cold-start sync at session close

This is the discipline that prevents the cold-start drift that produced the 2026-05-15 → 2026-05-16 near-miss. The cold-start folder is operationally canonical, not the Git copies.

If `AIVU_Current_State.md`, `AIVU_Working_Preferences.md`, or `AIVU_Architectural_Distillation.md` was edited during the session, the cold-start folder must hold the updated version before session close. Operationally:

```
cp ~/Downloads/AIVU_Current_State.md ~/Desktop/"Claude cold start Uploads"/
cp ~/Downloads/AIVU_Working_Preferences.md ~/Desktop/"Claude cold start Uploads"/
cp ~/Downloads/AIVU_Architectural_Distillation.md ~/Desktop/"Claude cold start Uploads"/
ls -la ~/Desktop/"Claude cold start Uploads"/
```

Run the relevant `cp` line for whichever files actually changed. The final `ls` confirms the folder contents and timestamps.

`AIVU_Current_State.md` is updated by Claude every session. The other two are updated rarely.

---

## Mid-session recovery: "Claude doesn't know where the clones are"

If a new Claude session reads context but the local path facts aren't immediately visible, the 30-second recovery is:

```
ls -la ~/aivu/ ~/aivu-greybox/ 2>/dev/null && \
cd ~/aivu && git remote -v && \
cd ~/aivu-greybox && git remote -v
```

This confirms both clones exist, shows what's at top level, and prints the GitHub URLs they point to. If both clones report the URLs in the table above, the setup is intact; proceed with the session.

**If a clone is missing,** that's a real problem and Claude must stop and surface to JDS rather than trying to re-create it from scratch.

Once the clones are confirmed, `bash ~/aivu-greybox/check_env.sh` verifies the greybox environment itself is intact (venv, pytest, scientific libraries, weather fixture) before any test work begins.

---

## GitHub authentication on JDS's Mac

Authentication for `git push` works without prompting JDS for credentials. The credential is cached via `~/.gitconfig` and macOS's keychain. Set up in April 2026.

**If Claude sees a `git push` prompt asking for a username and password:**

1. Do not enter JDS's password — GitHub no longer accepts password authentication for git operations.
2. The fix is a Personal Access Token (PAT) refresh, which JDS handles directly via github.com → Settings → Developer settings → Personal access tokens. Claude does not need to execute this; just surface the issue and pause.

---

## Python environment — use the repo's own scripts, do not transcribe paths

The greybox package runs under a virtual environment at **`~/aivu-greybox/.venv/`** — at the repo root, NOT under `code/aivu_greybox/`. pytest, numpy, and scipy are installed inside that venv only; system `python` will fail because they are not installed system-wide.

Two committed scripts at the greybox repo root make the environment describe and verify itself, so no session ever has to transcribe the venv path again (transcription is what produced the 2026-05-20 failures — a venv path, a test-path prefix, and a sandbox path all stale at once):

- **`bash ~/aivu-greybox/check_env.sh`** — verifies the environment in plain English: venv present, pytest installed, numpy/scipy import, Phoenix EPW fixture in place. Reports `ALL GOOD` or a specific failure. Run this first whenever an environment problem is suspected, or at the start of any work session.
- **`bash ~/aivu-greybox/run_tests.sh [pytest args]`** — runs the test suite via the repo's own venv. Finds the venv itself. Example: `bash ~/aivu-greybox/run_tests.sh code/aivu_greybox/tests/test_g8_closed_loop.py -v`.

Because both scripts live inside the repo, they travel with it and cannot drift from it the way a path written in this document can. If a script and this prose ever disagree, the script is correct.

**Test weather fixture.** Tests that need Phoenix weather load `Phoenix_AMY_2024.epw` from `code/aivu_greybox/tests/fixtures/`. The file is committed to the repo and travels with it. `epw_loader.py` also honours an `AIVU_PHOENIX_EPW_PATH` environment variable as an override, but no override is needed for a normal clone — the fixture is found automatically.

---

## The Claude Temp Folder discipline

The `~/Desktop/Claude Temp Folder/` exists for one reason: JDS uses it as the destination when downloading session-end zips and individual files from Claude during a session. It is **transit only**.

**At end of working day, bulk-move to AIVU Archive:**

```
mv ~/Desktop/"Claude Temp Folder"/* ~/Desktop/"AIVU Archive"/ 2>/dev/null
```

One command. No per-file judgment. Designed to be executable by a tired person at the end of a long day. The Temp Folder ends up empty; AIVU Archive accumulates the day's transit content for later curation.

**Curation of AIVU Archive happens at JDS's pace.** Three-bucket disposition, applied whenever JDS has capacity:

- **Canonical version on GitHub →** delete (GitHub is the archive; local duplicates are noise).
- **Not on GitHub but worth keeping** (session-end zip with chat context, intermediate draft with no GitHub home, partner-facing material) **→** lift to Google Drive archive.
- **Duplicates, `.DS_Store`, or other macOS metadata →** delete.

If a file's status is unclear, leave it in AIVU Archive. No penalty for deferring the decision.

**Why this discipline differs from the original addendum.** The original rule required per-file judgment at session close ("sort everything before declaring done"). It failed in practice — by the time real session close arrives, JDS is tired and decisions don't get made well, so the Temp Folder accumulated weeks of backlog instead. This version replaces a judgment-heavy rule with a muscle-memory operation, and defers judgment to whenever JDS has the bandwidth for it. The Temp Folder gets emptied reliably; the Archive holds content until JDS decides what to do with it.

The original rule also sent GitHub-canonical files to Drive, which produced redundant Drive content over time. Drive's role is now restricted to content GitHub does NOT carry — that restriction holds in this version.

---

*End of operational reference. Final state: both repos in sync with GitHub; Claude Temp Folder discipline in force; cold-start folder holds the current versions of Current State, Working Preferences, and Architectural Distillation.*
