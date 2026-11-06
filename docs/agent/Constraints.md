# Constraints

Authoritative list of project-specific restrictions. Read before moving, adding, publishing or deleting any file.

## What may be published (tracked in git)
- `README.md`, `FUTURE_SCOPE.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`
- `data/weather_file_nsrdb.csv`
- `reports/` — the author's own group's final reports (CP1, CP4 + presentation, CP5) and their figures
- `docs/agent/`

## What must never be published (git-ignored, kept locally)
| Folder | Contents | Reason |
|--------|----------|--------|
| `_review/` | Another group's (G04) reports, the SAM installer, the merged slide PDF, an incomplete download, Office lock/temp files | Other people's work; large or incidental files |
| `drafts/` | Earlier versions of the group's reports, a template carrying the author's name | Not final deliverables |
| `references/` | Journal papers used in CP3 | Publisher copyright |
| `course-material/` | Lecture slides, tutorials, reading assignment, formula sheets, blank templates, textbook | Instructor/publisher material |

## Rules
1. **Do not delete anything.** Files are moved, never removed. Anything uncertain goes to `_review/`.
2. **Do not edit the submitted reports** (`reports/*`) or the weather file. Observations about them belong in `Flow.md` §4 / `FUTURE_SCOPE.md`.
3. **Every move must be recorded** in `docs/agent/move_manifest.csv` with an md5 taken before the move.
4. **Do not commit, push or create a git repository** unless the user asks. (The user said they will handle the GitHub step.)
5. **Quote only what the reports state.** Numbers in README/Flow come from the reports; anything recomputed must be marked "checked". Do not present the weather file as IIT Bombay data (its header says Jodhpur).
6. **Personal data.** The reports list teammates' names and roll numbers. The user chose to include their own group's final reports; do not add more personal data elsewhere, and raise it again before the repository is made public (`FUTURE_SCOPE.md` §4).
7. **Another group's files** (the group-G04 CP2 and CP4 reports) stay in `_review/`. Their names, and the file names of other people's work, must not appear in tracked files. For this reason `docs/agent/move_manifest.csv` (whose old-path column contains those file names) is git-ignored and kept locally; `Rollback.md` explains how to use it.
8. **Do not introduce code or dependencies** without recording the reasoning in `Decisions.md` and adding the protocol documents that then become relevant (Architecture, Bug, Feature).
