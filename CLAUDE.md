# Las Vegas documentary — archival image workflow

Context for Claude Code working in this repo.

## The job

Archival images are sourced to match the documentary script, tagged with
provenance metadata, then uploaded to Lightroom (cloud) for the team.

Working folder on disk: `Vegas Downloads Full Folder` (TIFs, 300 DPI).
Master record: the **Airtable base** (see below). `manifest/master_manifest.csv`
and `manifest/editor_manifest.csv` are generated projections of it — read them,
never hand-edit them. The Google Sheet that used to hold this is retired.

## The constraint that drives everything

Lightroom cloud does not write metadata back into original files. Metadata must
be embedded **before** upload or the archive source is lost on re-download.
Lightroom web only displays Title, Caption, Creator, Copyright and keywords —
so provenance is packed into those fields, not just the IPTC ones nobody sees.

**The archive source is the priority field.** It is needed for documentary
credits and rights clearance. It is written to nine fields plus the filename.

## Layout

```
manifest/master_manifest.csv   731 rows, generated from Airtable — do not edit
vocabulary/                    controlled keywords + merge rules
scripts/pull_manifest.py       Airtable -> the two manifest CSVs
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

## Naming — the one invariant

**filename == Image ID == the best ID that archive offers.** Always. Alexa owns
this call: the best ID is the shortest string that is still unique and specific
at that archive, and it must stay short enough for a human to use.

It is one string in three places, so a file can never drift from its record.
When an ID changes, all three change together. `scripts/harvest_disk.py`
reports drift; as of 2026-09-02, 235 files match exactly, 23 differ only in
capitalisation (UNLV writes `pho...` lowercase, the sheet had `Pho...`).

Watch out: archives publish several ID species for one image and only one of
them is the digital object ID. Utah, for example, offers an ark, a 6-digit
digital ID (`455340`), a 14-digit barcode (`39222001650899`), and a zero-padded
shelf number (`00523`). The digital ID is the one on the ark page as
`file?id=` — see manifest/uhs_id_remap.csv for the 24 still misnamed.

## Caption vs Description — the per-archive rule

Archives are inconsistent: titles are short, descriptions are long, and some
put the whole caption in one and a bare shelf number in the other.

- **Caption** = the sentence the archive uses to describe the photo.
- **Description** = any further paragraphs.
- **Never** put an ID in the Caption, and never leave the ID prefix on it.

In practice: if the embedded/page title actually describes the photo (UNLV),
that is the Caption. If it is a shelf label (`... P.5`, Utah) or just the
catalog number (LOC, SFPL, NYPL), the Caption is the first descriptive
sentence of the archive's description and the rest becomes Description.

`scripts/harvest_disk.py` reads all of this back out of the downloaded TIFs --
archives embed their catalogue record, including the permalink -- and writes
manifest/harvest_disk.csv for review before anything is pushed.

## The Google Sheet is retired — do not rebuild from it

`Image_Source_Reference-1911 Production` was the source of truth until
2026-09-02. It is now archived and **must not be used to regenerate anything**.

It went stale the moment work started happening in Airtable and on disk, and a
rebuild from it silently reverts that work — it still carries the pre-rename
Utah IDs (523, 573) and the pre-reconcile Downloaded ticks. `build_manifest.py`
is retired with it.

To refresh the CSVs, pull from Airtable instead:

```
export AIRTABLE_TOKEN=pat...          # data.records:read on the base
python3 scripts/pull_manifest.py      # --dry-run to preview
```

Keep the generated CSVs committed: they are what lets `lvtag` run with no
network access.

## Naming — one value, four places

**Catalog ID == Image ID == `<filename>.tif` == Lightroom Title.** All four are
the archive's catalog ID verbatim, so a file can never drift from its record.
Do not build composite names anywhere. `lvtag.py rename` renames to
`<catalog id>.tif` and `build_fields` writes that same string to XMP-dc:Title
and IPTC:ObjectName, which is what Lightroom shows as the Title.

The archive is NOT in the filename -- it is carried in nine embedded fields
(Creator, Rights, Credit, IPTC Source, Caption, and others), which is what
protects credits and clearance.

**Archives that give a catalog ID *and* a download filename** (Utah Historical
Society records both, as "<id> / <filename>") keep both: the ID drives the
naming convention, and the archive's own filename goes to `archive_filename`
in the manifest, the `Archive Filename` field in Airtable, and
XMP-photoshop:TransmissionReference + IPTC:OriginalTransmissionReference in the
file. It is also appended to the Caption as "archive file <name>".

## Airtable base (tracking)

`Las Vegas Documentary — Archival Images`
- base `appD7Xn4PafIb2a6I`, table `Images` `tbln0l7r7Vhm51jxH`

Fields: Image ID (primary, = catalog ID), Sequence, Category, Script Page,
Archive, Catalog ID, Archive Filename, Caption, Source URL, Thumbnail, Keywords, Downloaded,
In Lightroom, Metadata Attached, Editor Notes.

**Sequence is provisional** — derived from the current draft script, regenerate
when the script locks. **Category is stable** and is what the editor groups by
in the meantime. `manifest/editor_manifest.csv` is the git-side mirror.

## Harvesting from an archive — the recipe that works

Archive sites sit behind bot protection: a plain WebFetch of a UNLV or Utah
item page returns 418, and the metadata is client-rendered so the raw HTML is
empty. What works is to open ONE page in the browser tool and then run
same-origin `fetch` from inside it -- the browser has already cleared the
challenge, so every later request is cheap.

UNLV (special.library.unlv.edu), proven on 221 IDs:

    fetch('/search?keys=' + encodeURIComponent(id))

Parse `Displaying results 1 - 1 of N` out of `body.innerText`. Three rules:

1. **Accept only N == 1.** Unquoted hyphenated IDs explode -- pho021428-006
   returns 9,003 fuzzy hits and the top result is a different photograph.
   If N != 1, retry the query wrapped in double quotes; if it is still not 1,
   record it as ambiguous rather than guessing.
2. **Take either link shape.** Items live at `/ark%3A/62930/...` or `/node/NNNN`;
   both are valid permalinks.
3. **Ignore the facet sidebar.** On a multi-hit page the "Archival Collection"
   label picks up the whole facet list. Reject any value over ~110 chars or
   containing a "(123)" count.

The search result also carries Title, Date, Archival Collection and
Description -- richer than the item page, which only reliably yields the title.

Run it with ~5 concurrent workers writing into one object, and poll for
completion; serial is ~11s per ID, five workers ~1s. 209 IDs took about four
minutes with a 100% hit rate.

Library of Congress needs no scraping at all: a `master-pnp-<prefix>-...-<id>u`
filename decomposes to `https://hdl.loc.gov/loc.pnp/<prefix>.<id>`, which is
LOC's own permalink. Alamy is `https://www.alamy.com/stock-photo/<ID>.html`.
Nevada Historical Society's PastPerfect matches the exact hyphenated ID, but
only about half its holdings are online -- 16 of ours return zero results
against controls that return exactly one, so those need Sarah Patton
(Archivist, Nevada Historical Society), not a scraper.

**Bulk Airtable writes are the expensive part of any session.** Each record has
to be printed by the browser and then retyped into the update call. Build the
push counterpart to pull_manifest.py -- a local script with AIRTABLE_TOKEN --
before doing another large write pass.

## Division of labour — hand UI work back

When a job is one or two clicks in a web UI but many approval-gated API calls
here, **say so and hand it over**. Do not grind through batched calls that each
need a permission prompt. Known cases:

- **Deleting an Airtable base** — no API for it at all; the UI is the only way.
- **Bulk-deleting records** — 50 per call, one approval each. Deleting the base
  or table in the UI is faster when the whole thing is going anyway.
- **Creating a shared view link** — UI only.
- **Connector sign-in / switching accounts** — UI only, and the connector's
  account identity is *only* visible there. The API exposes workspaces and
  bases but never the account email.

State the exact click path, then move on to work that actually needs an agent.

## Airtable base (tracking)

`Las Vegas Documentary — Archival Images`
- base `appntIAZCHnEatgyi`, table `Images` `tblQdrGgTOzZSPr11`
- workspace: Las Vegas Production (lexvbush@gmail.com account)
- 731 records. **This base is the source of truth** as of 2026-09-02.
- Loaded by CSV import of `manifest/airtable_import.csv`, which had 732 rows —
  one (`DPW-46`, "San Francisco sewers, 1910, being built") did not survive the
  import and has never been re-added.
- `Topic` carries the retired Sheet's topic column (118 rows). Free text; a
  handful of those rows hold a script page reference rather than a topic.
- `Description`, `Collection` and `Archive Subjects` were added 2026-09-02 to
  give each archive's own record room rather than forcing it into Caption.
- `Editor Notes` and `Thumbnail` were deleted 2026-09-02 -- not wanted. Do not
  recreate them; production commentary found inside archive metadata is simply
  left out of the base (it stays in manifest/caption_proposal.csv).

Reloading is far cheaper by CSV import than through the API: the API caps at
50 records per call and each call needs a permission prompt, while Airtable's
built-in importer takes the whole file and auto-detects single-select and
checkbox fields correctly. Regenerate the CSV from the base itself, import
to a new table, delete the old one, then rename and re-add the field
descriptions and the Thumbnail / Editor Notes fields (the CSV cannot carry
attachments or empty columns).
