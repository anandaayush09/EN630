# Rollback plan

## What changed
On 2026-11-06, 55 files were **moved** (renamed within the same folder tree) from their original locations into the layout described in `README.md`, and 12 documentation files were added. No file was deleted, edited or overwritten.

- Moved files and their original paths: `docs/agent/move_manifest.csv` (columns `old_path,new_path,md5,bytes`; paths relative to the repository root, forward slashes). The manifest is **git-ignored and exists only on the author's PC** (its old-path column contains another student's file names); do not delete it, and back it up before cleaning the folder.
- Files added: `README.md`, `FUTURE_SCOPE.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`, and in `docs/agent/`: `PROTOCOL.md`, `Handover.md`, `Decisions.md`, `Flow.md`, `Constraints.md`, `Testing.md`, `Rollback.md`, `move_manifest.csv`.
- Folders created: `data/`, `reports/`, `docs/`, `drafts/`, `references/`, `course-material/`, `_review/`. Seven original folders (`Assignment`, `CP 2`, `CP 3`, `CP 4`, `CP1`, `Lecture Slides`, `Tutorials`) were removed **only after becoming empty**.

## Existing behaviour that must be preserved
All 55 files keep their exact content (md5 verified, see `Testing.md`). Renames apply only to paths, not content.

## When to roll back
- The user decides the original structure should be restored; or
- the md5 check in `Testing.md` is rerun and any mismatch appears (content changed after the move); or
- a file turns out to be mis-classified (e.g. a draft that is really the final report) — then roll back **that file only**.

## Restore a single file
Look up the row in `docs/agent/move_manifest.csv`, create the old parent folder if needed and move the file back, for example:

```bash
mkdir -p "CP 4"
mv "reports/CP4_G05.pdf" "CP 4/CP 4 G05.pdf"
```

## Restore everything (non-destructive; only moves files)
Run from the repository root with Python 3. It stops at the first problem and never overwrites an existing file.

```python
import csv, os, shutil
rows = list(csv.DictReader(open("docs/agent/move_manifest.csv", encoding="utf-8")))
for r in rows:
    if os.path.exists(r["old_path"]):
        raise SystemExit("refusing to overwrite: " + r["old_path"])
for r in rows:
    os.makedirs(os.path.dirname(r["old_path"]) or ".", exist_ok=True)
    shutil.move(r["new_path"], r["old_path"])
print("restored", len(rows), "files")
```

Afterwards the added documentation files and the now-empty new folders (`data/`, `reports/`, `drafts/`, `references/`, `course-material/`, `_review/`) can be removed manually if wanted; this plan does not delete them automatically.

## Rollback of documentation only
The documentation files are new and independent; any of them can be removed or edited without affecting the moved material. Their authoritative record of what happened is this folder, `docs/agent/`.
