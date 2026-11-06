# Decision log

Format per entry: problem, alternatives, choice, why, trade-offs, future consequences. Date and model are as reported by the session (2026-11-06; model reported by the session: `claude-sonnet-5-5`). Git branch/commit: not applicable (this folder is not a git repository yet).

---

## D1 — Folder layout for a documents-only repository
- **Problem:** the folder mixed the group's reports, drafts, another group's reports, course slides, a textbook, papers, a 66 MB installer and Office lock files.
- **Alternatives:** (a) keep the original CP-based folders; (b) flat folder; (c) split by *kind* (data / reports / drafts / references / course material / review).
- **Choice:** (c): `data/`, `reports/`, `docs/agent/`, plus local-only `drafts/`, `references/`, `course-material/`, `_review/`.
- **Why:** a visitor sees only the final deliverables and the data; everything else is kept but not published.
- **Trade-offs:** the original CP-folder structure is lost; `docs/agent/move_manifest.csv` records every old→new path.
- **Future:** if code is added (see `FUTURE_SCOPE.md` §1) the protocol's `Architecture.md`, `Bug.md`, `Feature.md` should then be created.

## D2 — Which file is the "final" report for each CP
- **Problem:** several drafts exist per CP; the user asked to publish only the group's final reports.
- **Alternatives:** publish all versions; publish the latest by modification time; judge by content.
- **Choice:** CP1 = `CP1/CP1 G05.pdf`; CP4 = `CP 4/CP 4 G05.pdf` (+ `CP4 GP05.pptx`); CP5 = `Progress_CP5_Night.docx`. The "Progress …", "Evening", "Afternoon", "(Repaired)" and `[1]` copies are drafts.
- **Why:** the named PDFs are the exported submissions; for CP5 the *Night* file is the latest modified (2024-11-14) and the longest (about 25k characters of text against about 20k for *Evening*), and contains the cost analysis, results and limitations.
- **Trade-offs:** this is an inference from names, dates and content; the user did not confirm it. If wrong, move the correct file back from `drafts/` using the manifest.
- **Future:** confirm with the author, and export CP5 to PDF.

## D3 — Another group's reports go to `_review/`, not to the repository
- **Problem:** four files (CP2 and CP4 reports, docx and pdf) belong to a different group (G04).
- **Choice:** `_review/other-group-G04/`, git-ignored, not deleted. The move manifest, which records the original file names, is also git-ignored so another student's name is not published (see D9).
- **Why:** they are someone else's work; publishing them would be inappropriate, and the user chose "own group's final reports only".

## D4 — Course material, papers and drafts stay on the PC but out of git
- **Choice:** `course-material/` (lecture slides, tutorials, assignment, formula sheets, textbook, blank templates), `references/` (CP3 journal papers) and `drafts/` are listed in `.gitignore`.
- **Why:** instructor and publisher material is not the author's to redistribute; drafts add noise. Consistent with the earlier EE 467 and EE 769 repositories.
- **Trade-off:** a fresh clone lacks the slides and papers; the README says so.

## D5 — Large and incidental files go to `_review/`
- **Choice:** `sam-windows-2023-12-17-r1.exe` (66 MB installer), `ilovepdf_merged.pdf` (24 MB merge of the slides, redundant with the individual slide files), `Formula.pdf.crdownload` (incomplete download), Office lock files (`~$…`) and `~WRL2710.tmp`.
- **Why:** none is part of the work; the installer is a public download.
- **Trade-off:** none are deleted, so the user can inspect them. `.gitignore` additionally blocks `*.exe`, `~$*`, `*.tmp`, `*.crdownload`.

## D6 — Weather file renamed location-neutrally
- **Problem:** the file `2023-2 EN 630 - Weather file.csv` has a header naming Jodhpur (26.35, 73.05), while the reports say the data is for IIT Bombay (19.15° N, 72.95° E).
- **Choice:** renamed to `data/weather_file_nsrdb.csv` (no city in the name), content untouched, discrepancy documented in README, Flow.md and FUTURE_SCOPE.md.
- **Why:** the discrepancy cannot be resolved from the folder; the file must not be presented as an IIT Bombay dataset.

## D7 — Documentation set is deliberately reduced
- **Problem:** the protocol lists Architecture, Bug and Feature documents; this repository has no software.
- **Choice:** created `PROTOCOL`, `Handover`, `Decisions`, `Flow`, `Constraints`, `Testing`, `Rollback` and `move_manifest.csv`; did not create `Architecture.md`, `Bug.md`, `Feature.md`.
- **Why:** the protocol itself says not to generate meaningless documentation. Source-material inconsistencies are tracked in `Flow.md` §4 and `FUTURE_SCOPE.md` instead of a bug log.

## D8 — Reports are described, not corrected
- **Choice:** no report was edited. Inconsistencies found while reading them are recorded, with arithmetic marked "checked" where recomputed.
- **Why:** the reports are submitted coursework; silently changing them would break traceability.

## D9 — Reversibility through a manifest instead of git
- **Problem:** no git history exists to undo the moves.
- **Choice:** the move script computed an md5 for every file *before* moving it and wrote `docs/agent/move_manifest.csv` (old path, new path, md5, bytes; local only, git-ignored, because the old-path column names another student's files); after the move all 55 files were re-hashed against it (see `Testing.md`). `Rollback.md` explains how to reverse.
