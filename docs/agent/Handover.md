# Handover

Last updated: 2026-11-06 (model reported by the session: `claude-sonnet-5-5`). Git: not a repository; the user will create it.

## Project objective and status
Turn the EN 630 coursework folder (solar-thermal hostel cooking with Scheffler dishes, Group 05) into a clean repository suitable for GitHub, with a methodology flow document and the engineering-protocol documents. **Status: organisation and documentation complete; nothing committed or pushed.**

## What exists now
- `README.md` — overview, headline results (quoted from CP5), report table, map, data warning.
- `FUTURE_SCOPE.md` — first item: Python re-implementation of the model; then open issues and extensions.
- `docs/agent/Flow.md` — Mermaid methodology flow CP1→CP5, step table, CP4-vs-CP5 comparison, ten source inconsistencies.
- `docs/agent/` also holds `PROTOCOL.md` (the user's Master Prompt, verbatim), `Decisions.md` (D1–D9), `Constraints.md`, `Testing.md`, `Rollback.md`, and (local only, git-ignored) `move_manifest.csv`.
- `reports/` (CP1, CP4 + presentation, CP5, two figures), `data/weather_file_nsrdb.csv`.
- Local-only, git-ignored: `drafts/`, `references/`, `course-material/`, `_review/`.

## Work completed this session
1. Inventory of 55 files; mapping validated by dry run; files moved with md5 manifest (nothing deleted).
2. Read CP1, CP4 and CP5 reports; wrote README and Flow using only figures they state, marking recomputed values "checked".
3. Created `.gitignore`, `CLAUDE.md`, `AGENTS.md`, protocol documents.
4. Verification (see `Testing.md`): md5 55/55, counts, git-hygiene check with a throwaway git directory, rollback rehearsal on a copy, Mermaid render check.

Files modified: none of the original 55 files was edited. New files: see `Rollback.md`.

## Important decisions
See `Decisions.md`. Key ones: final-report selection (D2, **inferred**, needs the author's confirmation), other group's files and the manifest kept out of git (D3, D9), weather file renamed neutrally (D6), reduced documentation set (D7).

## Open issues and risks
1. **Weather file header says Jodhpur** (26.35 N, 73.05 E) but the reports describe IIT Bombay (19.15 N, 72.95 E). Unresolved; do not call the file "IIT Bombay data".
2. **The Python script used for the radiation model is hosted on an online IDE (link in CP5) and is not in the folder.** It should be recovered and archived.
3. **Own-group CP2 and CP3 reports are not in the folder.** The flow for steps 5–8 is inferred from CP4/CP5.
4. **Report inconsistencies** (ten items in `Flow.md` §4) are documented, not fixed.
5. **Personal data:** reports contain teammates' names and roll numbers; confirm with them before making the repository public.
6. `docs/agent/move_manifest.csv` exists only locally; losing it removes the exact record of original paths (the rollback snippet depends on it).
7. CP5 is a `.docx`; it will not preview on GitHub. Consider exporting to PDF.

## Immediate next steps (suggested)
1. Author confirms or corrects the "final" file choices (D2) and that CP5 `Night` is final.
2. Author runs `git init`, reviews `git status` (expected tracked set is in `Testing.md`), commits and pushes.
3. Start the Python re-implementation (`FUTURE_SCOPE.md` §1), beginning with recovering the original script and the correct weather file; at that point add `Architecture.md`, `Bug.md`, `Feature.md`.

## Warnings for the next agent
- Read `Constraints.md` first. Do not delete, edit the reports, or publish `_review/`, `drafts/`, `references/`, `course-material/`.
- The Kartik Sir Project folder is handled by another session; do not touch it from here.
- Do not describe anything as tested unless it appears as **Verified** in `Testing.md`.
