# Las Vegas documentary — archival image workflow

Context for Claude Code working in this repo.

## The job

Archival images are sourced to match the documentary script, tagged with
provenance metadata, then uploaded to Lightroom (cloud) for the team.

Working folder on disk: `Vegas Downloads Full Folder` (TIFs, 300 DPI).
Master record: `Image_Source_Reference-1911 Production` in Google Drive,
mirrored here as `manifest/master_manifest.csv`.

## The constraint that drives everything

Lightroom cloud does not write metadata back into original files. Metadata must
be embedded **before** upload or the archive source is lost on re-download.
Lightroom web only displays Title, Caption, Creator, Copyright and keywords —
so provenance is packed into those fields, not just the IPTC ones nobody sees.

**The archive source is the priority field.** It is needed for documentary
credits and rights clearance. It is written to nine fields plus the filename.

## Layout

```
manifest/master_manifest.csv   248 rows, source of truth in git
vocabulary/                    controlled keywords + merge rules
scripts/lvtag.py               CLI: audit, plan, apply, verify, rename, daily
scripts/lvlib.py               field mapping, matching, exiftool wrapper
daily/<date>/                  staged for Lightroom upload (gitignored)
```

## Conventions

- Always `plan` before `apply`. Never write to TIFs without previewing.
- `apply` keeps `*_original` backups unless `--no-backup` is passed.
- Filenames: `ARCHIVE_catalogid_short-caption.tif`.
- Credit line and usage terms live in `scripts/lvlib.py` — edit there, not inline.
- Files are matched to manifest rows by catalog ID, normalized to alphanumerics.
  When a match fails it is usually because the archive's download name bears no
  relation to the catalog ID; `audit` lists those as "files not in the sheet".

## Known state

As of the last sync: 248 rows, 111 still needing metadata. The sheet's own
status columns have drifted (more rows marked in Lightroom than marked
downloaded) — `audit` reports the real state from disk.
