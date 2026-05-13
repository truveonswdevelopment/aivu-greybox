# AIVU Working Preferences — Addendum 2026-05-13

**This addendum is to be merged into the canonical `AIVU_Working_Preferences.md` at next maintenance pass. Until then, this file lives alongside it and is read together with it.**

---

## Addendum 1: GitHub workflow discipline

### Why this addendum exists

As of 2026-05-13, the greybox track (spec docs §§1-12, the `aivu_greybox` Python package, session logs, continuity-management docs, the Due-Diligence Q&A) had accumulated across approximately six sessions and was never pushed to GitHub. The work existed only in:

- JDS's `Claude Temp Folder` on the Desktop
- Session-end `.zip` bundles inside that folder
- Chat history of past Claude sessions

The cause: GitHub push was not part of the session-close protocol. Claude provided git commands at session end as if a repo were already set up at the assumed path. That assumption was never verified across sessions; the path was never recorded in a continuity doc; no Claude session checked whether the previous session's commits had actually landed. JDS, not being a programmer, reasonably assumed the procedure was working.

This addendum prevents the drift from recurring.

### Repository structure — established 2026-05-13

The AIVU project uses TWO GitHub repositories, both under the truveonswdevelopment organization:

- truveonswdevelopment/aivu-physics — Forward simulator codebase: Phase 1 envelope physics, Phase 2 HVAC physics, aivu_dynamic, aivu_corpus, plus builder-engagement workspaces. Audience: builders, HVAC contractors. Local clone: /Users/drjandspalink/aivu/

- truveonswdevelopment/aivu-greybox — Inverse identification for the Phoenix pilot: spec docs §§1-12, the aivu_greybox Python package, continuity-management docs, session logs. Audience: homeowners, Clearinghouse customers, pilot operators. Local clone: /Users/drjandspalink/aivu-greybox/

Why two repos and not one: the simulator is forward physics for builder sales; the greybox track is inverse identification for the pilot. Different audiences, different physics, asymmetric dependency (greybox imports from physics via the ForwardChain Protocol, but physics does not import from greybox). Past-Claude scoped aivu-physics carefully around the simulator's identity — adding greybox to it would dilute that. Separate repos express the architectural separation cleanly.

### Mandatory session-close protocol — effective 2026-05-13

Claude MUST do the following at the end of every session that produces artifacts:

1. Identify which repository each artifact belongs to. Greybox specs and code → aivu-greybox. Simulator code and specs → aivu-physics.

2. Stage all artifacts in the appropriate local clone. Not in the Claude Temp Folder. Not in a zip. In the actual Git working tree at the path recorded above.

3. Provide concrete, paste-ready git commands that JDS executes in Terminal:
   - cd to the correct local clone
   - git status to confirm staging is correct
   - git add of the specific files (not blind git add .)
   - git commit -m "..." with a descriptive message
   - git push
   - git status again to confirm tree is clean

4. Verify with JDS that each push succeeded. If JDS reports an error, troubleshoot before declaring session closed. A session is not closed until artifacts are visible on GitHub.

5. Update PROJECT_STATE.md in the affected repo(s) to reflect new artifacts. PROJECT_STATE drift is what made this addendum necessary; the discipline to keep it current matters.

### Cross-cutting documents — where they go

- System Architecture of Truth and An Operating System for Residential Asset Classes: project-level. Live in aivu-greybox under docs/. The pilot is where these documents are most actively read and updated; the simulator repo can reference them via README link.

- Working Preferences, Roadmap, Unfinished Work, Due-Diligence Q&A, session logs: continuity-management docs. Live in aivu-greybox under continuity/. They reference both tracks but are most actively used in the pilot workflow.

- Past session-end .zip bundles: archival. Go to the Google Drive archive, not GitHub. GitHub holds canonical sources, not historical snapshots.

### What does NOT go on GitHub

- Bulk simulation outputs (multi-MB JSON, rendered PNG/PDF charts) — per existing aivu-physics convention, these go to Google Drive with each engagement's data/README.md pointing at them.
- .DS_Store files and other macOS metadata — already in .gitignore (to be added to aivu-greybox in initial commit).
- Pre-final draft versions of documents. When a §5 v3.3 ships, v3.0/v3.1/v3.2 do not go to GitHub. Only the locked version. Older versions go to the Google Drive archive for audit trail.
- Sensitive vendor or partner information (until each partner has signed appropriate NDAs).

### Working-folder discipline going forward

The Claude Temp Folder on JDS's Desktop should be a transit zone, not a long-term store. Files arrive there during sessions, get sorted at session close, and the folder is emptied (with contents either pushed to GitHub or archived to Google Drive). A growing Claude Temp Folder is a signal that session-close protocol has been skipped — the same signal that produced this addendum.

---

## Addendum 2: Working-style note (informal, from 2026-05-13 session)

JDS reframing during the session, worth capturing as ongoing operating principle:

"Your decision was fine; you got the work done; now we can have another go at it."

Useful operating principle: Claude can ship "working but not optimal" without treating the next-iteration improvement as evidence of an initial mistake. The first cut establishes structural correctness; refinement comes after, when the right next-step is visible. This is more productive than gold-plating up front.

Anti-pattern this discourages: Claude proactively warning about all known limitations before the first working cut exists, which delays the moment when JDS can actually see the system and direct the next iteration.

Pattern this encourages: ship the working version; surface limitations honestly in the result summary; let JDS direct what to improve next.

---

End of addendum. To be merged into canonical Working Preferences at next maintenance pass.
