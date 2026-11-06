# Test and verification record

Date: 2026-11-06. This repository has no code, so "tests" are checks that the reorganisation lost nothing, that nothing private can be published by accident, and that the documentation is accurate and usable. Status words follow the protocol: **Verified**, **Failed**, **Not tested**, **Blocked**.

## Checklist and results
| # | Check | How it was run | Result |
|---|-------|----------------|--------|
| T1 | Every one of the 55 original files has exactly one destination; no unmapped file, no missing source, no duplicate destination | Move script in dry-run mode (validation only) before any file was touched | **Verified**: `files present=55 mapped=55 unmapped=0 missing_sources=0 duplicate_dests=0` |
| T2 | File contents unchanged by the move | md5 of every file computed *before* moving (written to `move_manifest.csv`), then recomputed at the new path, also compared with byte size | **Verified**: 55 manifest rows, 0 md5/size mismatches (run right after the move and again at the end of the session) |
| T3 | No file lost or created by the move | File count before = 55; after the move 55 + manifest = 56; after documentation 68 (55 moved + 13 new files, see `Rollback.md`) | **Verified** |
| T4 | Private/large material cannot be tracked | Throwaway git directory kept outside the project (`GIT_DIR` in the scratchpad, `git add -A`, `git ls-files`); no `.git` was created in the project folder | **Verified**: `_review/`, `drafts/`, `references/`, `course-material/` are all ignored; no `.exe`, `.crdownload`, `~$` or `.tmp` tracked; the manifest is ignored. Tracked set and size are listed under "Final result" below |
| T5 | Rollback procedure works | Copied the whole folder to a scratch location, ran the exact Python snippet from `Rollback.md` there, re-hashed the restored files | **Verified**: `restored 55 files`, `0` md5 mismatches. (The original folders `CP 2`, `Assignment` etc. are recreated automatically; the docs and new folders remain, as documented.) |
| T6 | The Mermaid flowchart in `Flow.md` is valid | The diagram block was extracted programmatically and rendered with Mermaid 10.9.1 in the built-in browser | **Verified**: `RENDER_OK`, 12 nodes. GitHub's own renderer was **not tested** |
| T7 | Arithmetic marked "checked" in `Flow.md` §4 | Recomputed in Python | **Verified**: 9679287.61 + 62739.86 − 797360.5 − 5241600 = 3,703,066.97; 9976370 + 67029.77 − 851881 − 5600000 = 3,591,518.77; 14 × 400,000 = 5,600,000; 0.943822 × 0.92 × 0.7 = 0.607821 (with 0.9 it would be 0.5946); sizing product = 14.03; 1.6488 × 0.607 × 0.868 × 16 × 14 = 194.59 |
| T8 | Report figures quoted in README/Flow match the reports | Text extracted from `CP1_G05.pdf`, `CP4_G05.pdf` and `CP5_final_report.docx` and read | **Verified by reading** for the numbers quoted; figures inside images (charts, tables rendered as pictures) were **not read** |
| T9 | Relative links in the Markdown files resolve | Script checked every relative link target exists | See "Final result" |
| T10 | CP5 `Night` is the final CP5 report | Judged by latest modification date and content length | **Not confirmed with the author** (see `Decisions.md` D2) |
| T11 | Weather file location | Header read directly | **Verified fact**: header says Jodhpur (26.35, 73.05). Which site the group's DNI used is **not known** |
| T12 | .docx / .pptx files open in Office; PDFs render | — | **Not tested** |
| T13 | GitHub rendering of README and docs | — | **Not tested** (repository not pushed) |

## Commands (summary)
- Dry-run and apply: `python move_en630.py` / `python move_en630.py --apply` (script kept in the author's session scratchpad, not in the repo; its full mapping is reproduced by `move_manifest.csv`).
- md5/size re-check: Python loop over `move_manifest.csv`.
- Git hygiene: `GIT_DIR=<scratch>/gd630 GIT_WORK_TREE=<repo> git init; git add -A; git ls-files; git status --ignored --short`.
- Rollback test: copy of the folder, snippet from `Rollback.md`.
- Mermaid: static page served from `127.0.0.1` (server stopped afterwards) and opened in the browser pane.

## Final result (end of session)
| Item | Value |
|------|-------|
| Files in project folder | 68 (55 moved originals + 13 new: 12 documents/config files and the manifest) |
| md5 + size check against manifest | 55 rows, **0 mismatches** |
| Relative Markdown links checked (T9) | 21 checked, **0 broken** |
| Files that git would track | **19**: `README.md`, `FUTURE_SCOPE.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`, `data/weather_file_nsrdb.csv`, 6 files under `reports/`, 7 files under `docs/agent/` |
| Tracked size | 3.15 MB; largest file `reports/CP5_final_report.docx` (0.81 MB) |
| Ignored (not tracked) | `_review/`, `drafts/`, `references/`, `course-material/`, `docs/agent/move_manifest.csv` |
| Leaks (anything private/large that would be tracked) | none |
| `.git` directory inside the project folder | none (the check used a separate throwaway git directory) |
