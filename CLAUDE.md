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
credits and rights clearance. It is written to eleven embedded fields (run
`build_fields` and count them if that number is ever in doubt).

## Layout

```
manifest/master_manifest.csv   731 rows, generated from Airtable — do not edit
vocabulary/                    controlled keywords + merge rules
scripts/pull_manifest.py       Airtable -> the two manifest CSVs
scripts/push_manifest.py       a reviewed CSV -> Airtable (plan, then --apply)
scripts/lvtag.py               CLI: audit, plan, apply, verify, rename, daily
scripts/lvlib.py               field mapping, matching, exiftool wrapper
daily/<date>/                  staged for Lightroom upload (gitignored)
```

## Conventions

- Always `plan` before `apply`. Never write to TIFs without previewing.
- Re-running `lvtag apply` on a staged upload folder leaves a second
  `*_original` beside every file, which doubles the folder and is not what
  should be dragged into Lightroom. Clean them out, or pass `--no-backup` when
  the files have already been verified.
- Before staging anything for Lightroom, check `In Lightroom` **and** the
  compendium. Re-uploading an asset Lightroom already holds duplicates it.
- `apply` keeps `*_original` backups unless `--no-backup` is passed.
- Filenames: `<catalog id>.tif` and nothing else — see "the one invariant"
  below. `lvlib.target_name` is the only place that decides this.
- Copyright, credit line and usage terms live in `scripts/lvlib.py` — edit
  there, not inline. They are three separate fields on purpose: **Copyright is
  the rights holder and nothing else** (just `Nevada Historical Society`, not
  "Courtesy ..." and not the licence text) because it is what a viewer reads at
  a glance in Lightroom. The licence text stays in `XMP-xmpRights:UsageTerms`
  and the credit in `XMP-photoshop:Credit`, so nothing is lost. All three
  copyright tags (`XMP-dc:Rights`, `IPTC:CopyrightNotice`, `EXIF:Copyright`)
  get the same value — Lightroom's panel reads the EXIF and IPTC ones.
- Files are matched to manifest rows by catalog ID, normalized to alphanumerics.
  When a match fails it is usually because the archive's download name bears no
  relation to the catalog ID; `audit` lists those as "files not in the sheet".

## Known state

As of 2026-09-02, read from the .xlsx export (see warning below):

- **756 rows** as of 2026-09-03 (731 + the 25 Nevada Historical Society records
  created that day), 35 archives
- **465 still need metadata attached**

**`metadata_attached = Yes` does not mean the file carries this toolkit's
spec.** Audited on 2026-09-03: of 303 TIFs on disk, only 10 carried
`XMP-photoshop:Credit` and `XMP-xmpRights:UsageTerms`, 34 carried
`XMP-dc:Identifier` and 89 `IPTC:Source`. 231 carry a short copyright that is
the *archive's own* embedded Rights, not ours, and 225 carry no copyright at
all. `lvtag apply` has essentially never been run over this library — the rows
ticked `Metadata Attached` were tagged by hand under the thinner 2026-09-01
convention. The tick records that someone tagged the file, not that it matches
`build_fields`. Re-tagging is only useful for files not yet in Lightroom.
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
`file?id=`. All 28 arks in manifest/uhs_id_remap.csv were re-verified against
the live pages on 2026-09-03 -- every one returns exactly one `file?id=`, and
all 24 agreed with the Source URL already in Airtable.

Those 24 files were renamed on disk that day and their XMP-dc:Title,
IPTC:ObjectName and XMP-dc:Identifier set to the digital ID, with the old name
and old metadata kept together in the `<old name>.tif_original` backup beside
each file. **Two thirds of that fix are still open**, because all 24 were
already `In Lightroom = Yes`:

- Airtable still holds the shelf numbers. `manifest/uhs_id_push.csv` is staged
  for `push_manifest.py` -- 24 cells, 3 API calls.
- Lightroom still holds the old filenames, and it never re-reads a file it has
  already imported, so this cannot be fixed from here at all. The 24 renamed
  TIFs have to be re-imported and the old-named assets deleted, in the UI.

Do not treat the disk/Airtable/Lightroom disagreement on those 24 as fresh
drift to reconcile -- it is this migration, half-finished.

### CHS-5711 and CHS-5712 are two photographs, not one

Confirmed visually on 2026-09-03, so do not re-merge them. They are adjacent
frames of one C. C. Pierce panorama sweep over downtown Los Angeles, shot from
the same vantage and panning: 5711 looks toward the LA Times clock tower, a
gasometer frame and a "GENERAL ARTHUR" sign; 5712 toward the Merchants Trust
Building, Hotel Seymour and a tall Norfolk pine. The negative numbers are
etched into the plates themselves — `5711 PIERCE.` and `5712 PIERCE.` in the
lower left of each — so they are the photographer's own sequential numbers.
Consecutive numbers, one panorama and one shared caption is how they came to
be filed under a composite `CHS-5711/CHS-5712` id in the first place.

`CHS-5712` is in Lightroom. `CHS-5711` is downloaded and is not, and it is a
1200px JPEG rather than a 300 DPI TIF, so it wants re-sourcing before upload.

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

## manifest/caption_proposal.csv is retired — do not push it

It was overtaken by a better caption pass applied directly in Airtable. Re-run
against the live base on 2026-09-03 it came to 51 cells, and 46 of them would
have made the base worse: 22 injected duplicate subject terms, 10 only added a
trailing full stop, 6 replaced a good value with a worse one, 4 appended
`Suggested script page(s): ...` into Caption (production commentary, which this
base deliberately excludes), and 2 truncated a caption — `Wilson and Park
families camping near Mt. Charleston (Album 4).` became `... near Mt.`, because
whatever generated the file split sentences on `.` and broke on the
abbreviation. `snv001117` would have lost its archive subject terms for the
shorthand `vegas; school; kids; teachers; outside`.

The 5 salvageable cells were extracted to `manifest/caption_salvage.csv` and
applied. Treat the proposal file as history, like the Sheet below.

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

**That route has now been used and it works.** Sarah supplied scans plus three
PastPerfect search-result PDFs and a covering note (both in the wetransfer
folder under `Vegas Downloads Full Folder`). The PDFs are XFRX table reports:
`pdftotext -layout` renders them cleanly, records begin `P <catalog id>` at
column 0 with the description at the column where the header's "Description"
starts, and continuation lines carry the object type on the left and more
description on the right. 241 records parsed out of the three; all 15 wanted
IDs matched. Her note also corrects a card-catalogue typo -- the Oddie photo at
the Mizpah Saloon is `NYE-01593`, not `NYE-01592`.

Her covering note lists many more Oddie images (BIO-O-*) than were scanned, and
several leads not yet pursued: `WA-01012` (children's playground, Sparks,
1909), `HU-00207` (children sledding, 1911-12), `LN-00524` (children boxing,
Caliente, c1918), `MIN-00720` (trash wagon, c1890). She found nothing at all
for cesspools, a Pioche tax office, or Charles 'Corky' Corkhill.

**Bulk Airtable writes go through scripts/push_manifest.py, not the browser.**
Printing each record and retyping it into an update call was the expensive part
of every session. The push script does a whole pass locally:

```
python3 scripts/push_manifest.py --csv manifest/caption_proposal.csv
python3 scripts/push_manifest.py --csv manifest/caption_proposal.csv --apply
python3 scripts/pull_manifest.py                          # bring the CSVs back in step
```

The token comes from `.env` at the repo root (gitignored) or `AIRTABLE_TOKEN`
in the environment — `load_token()` in both scripts checks the environment
first, then the file:

```
AIRTABLE_TOKEN=pat...
```

Make it at https://airtable.com/create/tokens with **data.records:read** and
**data.records:write** scoped to this base. Never put it on a command line: it
lands in shell history. Never paste it into a chat transcript.

Plan first, as everywhere else here -- it writes nothing without `--apply`, and
the plan shows old -> new for every cell and drops the cells that already
agree, so a 227-row proposal comes out as 756 real changes in 23 API calls.

It takes any CSV keyed on `image_id` or `catalog_id` whose remaining columns
name Airtable fields. The review files this repo already writes work unchanged:
where a file uses `NEW_<field>` beside `current_<field>`, only the `NEW_` side
is read and the bare context columns are ignored. A generated manifest can be
pushed back too, which is the route for an offline bulk edit.

`--create` makes rows whose key is not already in the table into new records
instead of reporting them as not found. It dedupes repeated keys within the
file, omits blank cells rather than writing empties, and refuses to run at all
without the flag — so a typo'd ID in an update file can never silently become
a new record.

**A create file's cells are defaults, not decisions**, so `--create` alone
leaves any row that turns out to already exist untouched and says so; add
`--upsert` to update those too. This guard exists because on 2026-09-03 a
create file for `CHS-5711` met a record that already existed and silently
flipped its Downloaded, In Lightroom and Metadata Attached flags. Restored
from `manifest/push_log.csv`, which is what that log is for.

Three things it will not do quietly:

- A blank cell means "leave alone", not "clear" -- the proposal files are
  sparse, so blanks-as-deletions would empty most of the base. `--allow-blank`
  if clearing is actually what you want.
- `Editor Notes` and `Thumbnail` columns are refused by name, not ignored, so a
  proposal file carrying one cannot recreate a field that was deleted on
  purpose.
- A single-select value that is not already in use is flagged, because Airtable
  rejects it without `--typecast` and *creates* the choice with it -- that is
  how a base grows an "Uncategorised" next to its "Uncategorized".

Every applied cell is appended to `manifest/push_log.csv` with its old value,
so a bad pass can be read back and reverted.

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
  one (`DPW-46`) did not survive the import. **It is back as of 2026-09-03**:
  one row, Image ID `DPW-46`, San Francisco Public Library, "Vicente Street
  sewer near 30th Ave.", digitalsf.org/record/6563, all three boxes ticked. The
  `DPW-46-2` that the manifests used to carry is gone, so this was a rename of
  the surviving row rather than a re-add — the record count stayed at 731.
- `Topic` carries the retired Sheet's topic column (118 rows). Free text; a
  handful of those rows hold a script page reference rather than a topic.
- `Description`, `Collection` and `Archive Subjects` were added 2026-09-02 to
  give each archive's own record room rather than forcing it into Caption.
- `Editor Notes` and `Thumbnail` were deleted 2026-09-02 -- not wanted. Do not
  recreate them; production commentary found inside archive metadata is simply
  left out of the base (it stays in manifest/caption_proposal.csv).

The 16 fields, in table order:

    Image ID (primary)   Caption        Topic              Category
    Source URL           Archive        Script Page        Sequence
    Archive Filename     Keywords       Downloaded         In Lightroom
    Metadata Attached    Description    Collection         Archive Subjects

There is **no Catalog ID field** — Image ID *is* the catalog ID, and the
`catalog_id` manifest column is derived from it by `pull_manifest.py` (which
blanks it for the `NEEDS-ID-nn` stubs and strips a disambiguating `-n` tail).
`Sequence` is provisional, derived from the current draft script — regenerate
it when the script locks. `Category` is stable and is what the editor groups by
in the meantime; `manifest/editor_manifest.csv` is the git-side mirror.

Both scripts address fields by **field id, not name**, so renaming a field in
the Airtable UI cannot silently break a pull or redirect a write. The ids are
in `FIELDS` at the top of each script.

Reloading is far cheaper by CSV import than through the API: writes cap at
10 records per call (`push_manifest.py` batches to that), while Airtable's
built-in importer takes the whole file and auto-detects single-select and
checkbox fields correctly. Regenerate the CSV from the base itself, import
to a new table, delete the old one, then rename it and re-add the field
descriptions (the CSV cannot carry an empty column, so any field that is
entirely blank at export time has to be recreated by hand). Both scripts'
`FIELDS` maps hold field ids, so a reload into a new table means updating the
ids in `pull_manifest.py` and `push_manifest.py`.
