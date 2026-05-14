# AIVU Working Preferences — Operational Addendum 2026-05-13

**This addendum complements `AIVU_Working_Preferences_Addendum_2026_05_13.md` (which establishes the "what" and "why" of the two-repo GitHub workflow). This file establishes the "how" — the concrete operational procedure, local paths, and recovery patterns. Read both addenda together. Both are to be merged into the canonical Working Preferences at next maintenance pass.**

---

## Read order at the start of any new session

A new Claude session must read continuity-management documents in this exact order. Doing so prevents repeating the detective work that produced these addenda.

1. `continuity/AIVU_Working_Preferences.md` — operating conventions, working style.
2. `continuity/AIVU_Working_Preferences_Addendum_2026_05_13.md` — what the two repos are, what goes where, the session-close protocol.
3. `continuity/AIVU_Working_Preferences_Addendum_2026_05_13_Operational.md` (this file) — concrete paths, commands, recovery procedures.
4. `continuity/AIVU_Phoenix_Pilot_Roadmap.md` — current workstream status.
5. `continuity/2026_05_DD__session_log.md` — most recent session log.
6. `continuity/AIVU_Unfinished_Work_2026_05_DD*.md` — pending items.

Only after this read does Claude propose next steps for the new session.

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
| Claude Temp Folder | `~/Desktop/Claude Temp Folder/` | Transit zone for files Claude generates during sessions. Must be emptied at session close (see below). |
| Downloads | `~/Downloads/` | Where session-end zips and downloaded artifacts land. |
| Google Drive archive | (JDS's chosen location) | Off-repo audit-trail archive for intermediate document versions and old session-end zips. Replaces what GitHub does not hold (only canonical versions go on GitHub). |

---

## Repo content map — what goes where

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
SESSION3_SIGNOFF.md, SESSION4A_SIGNOFF.md, etc.   Past session signoffs
.gitignore
```

### `aivu-greybox` (inverse identification / pilot)

```
code/aivu_greybox/                     The Python package
  src/aivu_greybox/                    Package source (passive_fit, active_fit,
                                       fan_heat, forward_chain, epw_loader, etc.)
  tests/                               Pytest suite
  pyproject.toml, README.md

spec/                                  §§1-12 v0.1 series spec documents

continuity/                            Cross-session governance documents
  AIVU_Working_Preferences.md          ← read first
  AIVU_Working_Preferences_Addendum_2026_05_13.md     ← read second
  AIVU_Working_Preferences_Addendum_2026_05_13_Operational.md  ← read third (this file)
  AIVU_Phoenix_Pilot_Roadmap.md        Workstream status
  AIVU_Unfinished_Work_2026_MM_DD*.md  Pending items per session
  AIVU_Due_Diligence_QA.md             Investor and partner Q&A
  2026_MM_DD__session_log.md           Session-by-session logs

docs/                                  Project-level architectural documents
                                       (System Architecture of Truth, Operating System)

README.md                              Repo-level overview
.gitignore
```

---

## Standard session-close procedure

Claude executes this at the end of every session that produces artifacts. Six steps, every time, no shortcuts.

### Step 1 — Identify the destination repo for each artifact

For each file produced in the session, Claude states:

> "This file goes into `aivu-greybox` under `spec/`."
> "This file updates `aivu-physics`'s `PROJECT_STATE.md`."
> "This file is intermediate; it goes to Google Drive archive at session close, not to GitHub."

If a file's destination is unclear, surface to JDS for decision before staging.

### Step 2 — Bring local clones current (`git pull`)

```bash
cd ~/aivu && git pull origin main
cd ~/aivu-greybox && git pull origin main
```

This catches any commits made from elsewhere (other machines, GitHub web edits) before Claude adds new ones. Fast-forward expected; if a merge conflict appears, stop and surface to JDS.

### Step 3 — Stage files in the appropriate local clone

For new files: copy them into the correct subfolder of the correct clone. Example:

```bash
cp /home/claude/work/something.py ~/aivu-greybox/code/aivu_greybox/src/aivu_greybox/
```

For modified files: edit them in place in the clone (via text editor or `sed`).

Never stage files in `~/Desktop/Claude Temp Folder/` and expect them to land on GitHub. The Claude Temp Folder is a transit zone, not a Git working tree.

### Step 4 — Commit, one logical change per commit

```bash
cd ~/aivu-greybox
git add <specific files, not blind `git add .`>
git status      # verify staging is correct
git commit -m "Concise descriptive message"
```

Use multiple commits if the work spans separable concerns (spec edits + code shipped = two commits). Use single-line commit messages with no `§`, `σ`, or other special characters that have broken heredoc handling in past sessions. Full commit detail belongs in the session log, not the commit message.

### Step 5 — Push and verify

```bash
git push origin main
git status      # must show "Your branch is up to date with 'origin/main'"
git log --oneline -5    # confirm the new commits are present
```

A session is not closed until `git status` returns clean and `git log` shows the new commits.

### Step 6 — Empty the Claude Temp Folder

Any file that ended up in `~/Desktop/Claude Temp Folder/` during the session must be sorted before session close:

- **Canonical version now on GitHub →** move the file in the Temp Folder to Google Drive archive.
- **Intermediate version (older than what's on GitHub) →** Google Drive archive.
- **`.DS_Store` or other macOS metadata →** delete.

Target state: at session close, `~/Desktop/Claude Temp Folder/` is empty (apart from possibly a fresh `.DS_Store` which macOS regenerates and is harmless).

---

## Mid-session recovery: "Claude doesn't know where the clones are"

If a new Claude session reads context but the local path facts aren't immediately visible, the 30-second recovery is:

```bash
ls -la ~/aivu/ ~/aivu-greybox/ 2>/dev/null && \
cd ~/aivu && git remote -v && \
cd ~/aivu-greybox && git remote -v
```

This confirms both clones exist, shows what's at top level, and prints the GitHub URLs they point to. If both clones report the URLs in the table above, the setup is intact; proceed with the session.

**If a clone is missing,** that's a real problem and Claude must stop and surface to JDS rather than trying to re-create it from scratch.

---

## GitHub authentication on JDS's Mac

As of 2026-05-13: authentication for `git push` works without prompting JDS for credentials. The credential is cached via `~/.gitconfig` and macOS's keychain. Past-Claude set this up in April 2026.

**If Claude sees a `git push` prompt asking for a username and password:**

1. Do not enter JDS's password — GitHub no longer accepts password authentication for git operations.
2. The fix is a Personal Access Token (PAT) refresh, which JDS handles directly via github.com → Settings → Developer settings → Personal access tokens. Claude does not need to execute this; just surface the issue and pause.

---

## The Claude Temp Folder discipline

The `~/Desktop/Claude Temp Folder/` exists for one reason: JDS uses it as the destination when downloading session-end zips and individual files from Claude during a session. It is **transit only**.

**The Folder must be empty at session close.** A non-empty Folder at the start of a new session signals that the previous session's close protocol was incomplete. The first task of any session that opens to a non-empty Folder is to sort its contents before any new work begins:

- Identify each file's canonical version (almost always on GitHub by now).
- Move intermediate / superseded versions to Google Drive archive.
- Delete `.DS_Store` and macOS metadata.
- If a file's status is unclear, surface to JDS for decision.

This is the discipline that prevents the six-session GitHub-state drift that produced these addenda in the first place.

---

## What this addendum's existence implies

The first addendum (the one about workflow discipline and repo structure) is *aspirational*: it states what the protocol should be. This second addendum is *operational*: it states the concrete steps and paths. **Both are required.** A future Claude session that has only the first addendum but not the second has the policy but not the execution recipe, and that's exactly the gap that produced today's hour-long detective work.

If a future session of Claude reads both addenda and still finds itself confused about where files live or what step to run next, the gap is real and should be captured by writing a third addendum (or — better — by merging all three into the main `AIVU_Working_Preferences.md` at maintenance pass). The continuity-management documents are themselves continuity-managed.

---

*End of operational addendum. Final state: both repos in sync with GitHub; Claude Temp Folder discipline in force; session-close protocol mandatory.*
