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

As of 2026-09-02, read from the .xlsx export (see warning below):

- **732 image rows** in the `NEW -Image_Source_Reference` tab, 35 archives
- **465 still need metadata attached**
- 709 rows carry a catalog ID; 707 are unique; 23 rows have none and are
  stubbed `NEEDS-ID-nn` pending a real ID

`In Lightroom = Yes` with `Downloaded` blank is **correct, not drift** — a
number of images were already in Lightroom before this project began, so they
were never downloaded as part of it. Do not "reconcile" those rows.

## Reading the Google Sheet — important

Do NOT read the master sheet through Drive's text/markdown conversion. It
silently truncates: it reported 248 rows when the sheet actually has 732.
Always export the real spreadsheet and parse it:

```
download_file_content(fileId, exportMimeType=
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
```

then decode the base64 and read it with openpyxl. Row counts from any other
path are not trustworthy.

## Naming

`Image ID` in Airtable is the **catalog ID verbatim** — that is the production's
naming convention for every image and it stays short (median 9 characters).
Do not build long composite names for it. The longer
`ARCHIVE_catalogid_caption` form is used only for TIF filenames on disk, where
the archive prefix is a deliberate second layer of provenance.

## Airtable base (tracking)

`Las Vegas Documentary — Archival Images`
- base `appD7Xn4PafIb2a6I`, table `Images` `tbln0l7r7Vhm51jxH`

Fields: Image ID (primary, = catalog ID), Sequence, Category, Script Page,
Archive, Catalog ID, Caption, Source URL, Thumbnail, Keywords, Downloaded,
In Lightroom, Metadata Attached, Editor Notes.

**Sequence is provisional** — derived from the current draft script, regenerate
when the script locks. **Category is stable** and is what the editor groups by
in the meantime. `manifest/editor_manifest.csv` is the git-side mirror.
