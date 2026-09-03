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

- **Always add keywords — at least 5, up to 10.** Alexa's rule, 2026-09-03.
  Draw them from `vocabulary/keywords.csv`; where a needed term is genuinely
  missing, add it to the vocabulary rather than writing free text, and never
  pad to reach the count with vague parent terms. `lvtag keywords` flags
  anything off-list. Place, county and named-railway terms are the honest way
  to reach 5 on a sparse record.
- Always `plan` before `apply`. Never write to TIFs without previewing.
- Re-running `lvtag apply` on a staged upload folder leaves a second
  `*_original` beside every file, which doubles the folder and is not what
  should be dragged into Lightroom. Clean them out, or pass `--no-backup` when
  the files have already been verified.
- Before staging anything for Lightroom, check `In Lightroom` **and** the
  compendium. Re-uploading an asset Lightroom already holds duplicates it.
- **Empty the staging folder as soon as a batch is imported.** A `Ready to
  Upload` folder that still holds imported files is the trap that produced 11
  duplicate groups on 2026-09-03: the folder gets dragged in again and every
  file in it lands twice. Move imported files to `_uploaded <date>` and leave
  only what is still outstanding. `September 3` is now laid out that way —
  `Ready to Upload`, `_uploaded 2026-09-03`, `_already in Lightroom` (files
  that arrived already imported and needed no work) and `_exiftool backups`.
- **"In Lightroom" means the Early 1900s ALBUM, not the catalog.** The catalog
  is Alexa's whole Lightroom library — 19,000+ assets and still paginating —
  and only the `Early 1900s` album is this project. Established 2026-09-03 the
  hard way: 13 files staged for upload as "not in Lightroom" were already in
  the catalog, just outside the album, and `CHS-5711` was the same story. They
  needed **moving into the album**, not uploading. So a file can be absent from
  the album scrape and still be in Lightroom — check the catalog before
  concluding anything is missing, and remember the fix for one of these is a
  move, never an import.
  Paginating the whole catalog does not work reliably: the cursor loops, and
  the unique count froze at 19,349 while rows kept arriving. It is usable to
  *confirm* a file is present, not to prove one is absent.
- **Re-scrape the compendium before trusting it.** Re-scraped 2026-09-03:
  `manifest/lightroom_compendium_2026-09-03.json`, **792 assets** across 726
  distinct filenames, with assetId and created timestamp per asset. The
  2026-09-01 file held 701 and was already missing `CHS-5711`, which Alexa
  confirmed is in Lightroom — so a stale compendium under-reports and a miss in
  it proves nothing. The scrape needs a logged-in Adobe session: the in-app
  browser is not signed in and redirects to Adobe auth, so use the real
  browser. Technique is in `Session Handoff - 2026-09-01.md`, with two
  additions — capture `asset.id` so a real duplicate can be told from a grid
  re-render, and `get_page_text` truncates around 51 KB, so dump the list twice
  (once reversed) and merge, and glue back any line split by a title that
  contains a newline.
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

## Land & Survey — the Peter Buol / open-land beat (script P.33)

Research doc: the Google Doc "Peter Buol / 'wide open land' — image options,
c. 1902-1906" (Drive id `1isEBCPY71MpzGeqlNvtbfWJxGBbGOGhI5oZv0hEjr-w`). The
narration is about **land as a commodity**, so the strong frames are ground with
a transit and a stake in it, not scenery.

Its find is the **Ferron and Bracken Photograph Collection** at UNLV — a run of
railroad survey camp and transit photographs around Las Vegas. Walter Bracken
was the railroad's land agent, Buol's opposite number, so the collection is the
land business's own photo album. `snv001879` (transit on a hillside, valley
behind) is the single best frame. The dated 1902/1903 items are the ones safe
to attach to a specific year; the `snv0018xx` run is catalogued only as
1900-1925.

20 were recorded 2026-09-03 with a new **`Land & Survey`** vocabulary category:

    Surveyors  Survey Camp  Railroad Survey  Surveying Instruments
    Land Sale  Townsite  Townsite Auction

plus `Open Land` (Landscape & Terrain), `Tents` (Commerce & Buildings) and
`Eldorado Canyon, NV`. Those are the terms to reuse for this beat rather than
inventing near-synonyms.

Still on the doc's list and not yet sourced: `pho016226`, `pho023883`,
`snv001865`, `snv001874`, `snv001873`, `snv001894`, `snv001880`, `snv001887`,
`pho013952`, `hln000101`, `pho015065`. The doc also flags the BLM General Land
Office survey plats as unchased — that is the federal paperwork Buol actually
handled, if a document insert is wanted.

### Verify presence per asset, not from a bulk crawl

Alexa was right to doubt the "already in the catalog" list. The way to settle it
is to fetch each asset by id — `GET /v2c/catalogs/<catalogId>/assets/<assetId>`
— and check for HTTP 200 with `removed_from_catalog` false. Done for all 20 on
2026-09-03: every one is a live asset, some imported as long ago as 2023-12-01,
and the disk copies match the Lightroom copies pixel-dimension for
pixel-dimension, so there was nothing to replace.

Album membership is the separate question, and it moves under you: the album
went 814 -> 836 during that same check as Alexa moved files in. Read membership
from the album's own asset ids rather than assuming.

**Two assets are near-thumbnail size and want re-sourcing**, in Lightroom and on
disk alike: `AAB-6092` (302x400, San Francisco Public Library) and `ESM-01420`
(450x258, Nevada Historical Society). `pho017606` at 947x1629 is marginal.

## TIFs only — and a JPEG must be traceable

**Lightroom should hold 300 DPI TIFs.** Alexa's rule, 2026-09-03: "ideally we
don't want jpegs, we want tif files only in lightroom. if we do have the jpeg
it definitely needs a url so we can trace it back to where we can purchase the
tif."

So a JPEG is a placeholder, not a deliverable, and it is only acceptable with a
**Source URL** — that link is how the TIF gets bought later. A JPEG with no URL
is a dead end: nobody can find it again.

Audited 2026-09-03 against the fresh scrape. Of 792 Lightroom assets, 588 are
TIFs and 201 are not (3 are video). `manifest/jpeg_needs_url.csv` lists every
non-TIF lacking a URL, split three ways:

-   **7 photographs** — the real problem. `chs-m958`, `sanfran-sewers`,
    `0038 0037`, `FirstMailPlane` (`1993_5P_2_002a.jpg`), and the three Reno
    Mill / lumber files. Each needs its archive found so a URL can be recorded
    and a TIF ordered. Six of the seven also have a **blank Archive field**,
    which is why they were never traceable.
-   **84 newspaper and clipping scans** — reference material, not photographs
    to re-source. A URL would still help but no TIF is being bought.
-   **3 duplicates** already on the deletion list.

When staging a JPEG, check it carries a Source URL before it goes up. The 18
staged on 2026-09-03 all do.

## Naming — the one invariant

**filename == Image ID == whatever name Lightroom already holds.** If the image
is not yet in Lightroom, that name is the best ID the archive offers — the
shortest string still unique and specific at that archive, short enough for a
human to use. Alexa owns this call.

**An image already in Lightroom is never renamed to suit the archive.** Airtable
is changed to match Lightroom instead (2026-09-03: "it is a waste of time to
rename the files in lightroom... if there is an image in lightroom already,
update the airtable to match what the name is"). Renaming in Lightroom means a
re-import and a deletion per file, and it buys nothing the embedded metadata
does not already carry.

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

**That migration was abandoned and reverted on 2026-09-03.** The 24 were
renamed to the digital ID on disk and in Airtable, then put back: Lightroom
already held all 24 as `<shelf number>.tif`, and renaming there costs a
re-import plus a deletion for each. The shelf number is adequate, so Airtable
and the files now carry it and match Lightroom. All 24 verified: filename ==
XMP-dc:Title == XMP-dc:Identifier == the Airtable Image ID.

The digital ids are still recorded in `manifest/uhs_id_remap.csv` alongside the
verified arks, so nothing learned was lost -- they are simply not the naming
convention. The keyword, copyright and credit tagging done during the migration
was kept; only the id fields went back.

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

Both are in Lightroom — Alexa confirmed CHS-5711 on 2026-09-03, so its tick is
correct and neither needs uploading. CHS-5711 is a 1200px JPEG rather than a
300 DPI TIF, so it is worth re-sourcing from USC on quality grounds alone.

A second, separate problem was a duplicate: an empty record also carrying
Image ID `CHS-5712` (Nevada Historical Society, Uncategorized, Sequence 462,
nothing else). It came in with the 2026-09-02 CSV import and surfaced when the
composite was renamed onto the same id. Deleted 2026-09-03 at Alexa's request;
its contents are in `manifest/deleted_records.csv`. No duplicated Image ID
remains in the base.

### Prose in the Keywords field

Several Utah rows carried a caption sentence in `Keywords` instead of keyword
terms, some of it with a Shipler negative number attached. Replaced with
controlled terms on 2026-09-03; nothing was lost, because every one of those
sentences was already in `Description`. One was worse than redundant: `439106`
("Pocatello, Ida., steel car shop under construction") held *another
photograph's* caption, the dining-car text belonging to `439958`. Dropped.
Worth re-checking the other archives' rows for the same pattern.

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

## Verify metadata by reading Lightroom back, not by re-uploading

Lightroom's API returns the XMP it actually stored, so a batch can be checked
without uploading it twice. Read one asset with
`GET /v2c/catalogs/<catalogId>/assets/<assetId>` from inside a logged-in tab
and look at `payload.xmp`. Asset ids come from the album scrape.

**The Source URL goes in the Caption, because that is the only place it can be
read.** Lightroom *stores* `xmpRights:WebStatement` but never *displays* it,
and Caption is one of the five fields its UI shows. So `build_fields` ends the
description with `Permalink: <url>` — the same habit the archives themselves
have. Alexa's call, 2026-09-03: "the url needs to be in the caption or else i
cannot see it in lightroom". `WebStatement` is still written as well; the
caption is what makes it visible. This matters because a JPEG is only allowed
in Lightroom if its URL can be followed to buy the TIF, and a URL nobody can
see does not satisfy that.

**Of everything this toolkit writes, Lightroom keeps exactly nine fields.**
Compared across two assets on 2026-09-03 — `CL-00560` (NHS) and `pho005494`
(UNLV) — the surviving set is identical in both:

    dc:title  dc:creator  dc:description  dc:rights  dc:subject
    xmpRights:Marked  xmpRights:UsageTerms  xmpRights:WebStatement
    tiff:Orientation

Dropped in both: the `photoshop` namespace except `DateCreated` (so Credit,
Source, Headline, TransmissionReference and Instructions all go), every IPTC
field, `EXIF:Copyright`, and `dc:Identifier`.

Do not read the namespace *count* as the rule — it varies with the original
file, not with our tagging. `pho005494` shows seven namespaces against
`CL-00560`'s three, but every extra one is camera or scanner metadata carried
in by the archive's own scan (`aux:SerialNumber`, `exif:DateTimeOriginal`,
`tiff:Make`/`Model`, `xmp:CreateDate`). None of it is ours.

This is why the fields are deliberately redundant, and it vindicates packing
the archive into Caption/Creator/Rights rather than trusting Credit and
IPTC:Source alone — those are invisible here. `xmpRights:WebStatement` survives
too, so a Source URL does reach Lightroom: `pho005494` carries its UNLV ark in
all three places (Airtable, the TIF, and the Lightroom asset). Everything dropped still lives
**in the file**, which is the layer that matters on re-download; it is only
Lightroom that cannot see it. It also confirms the shortened copyright works:
`dc:rights` reads `Nevada Historical Society` and nothing more.

## Why the duplicates happened — Lightroom dedupes on metadata

Alexa, 2026-09-03: "when I reupload an image into lightroom that has sightly
different metadata, it will accept it. if i try to upload the same image with
the same metadata it will reject as a duplicate."

So Lightroom's duplicate check is over pixels **plus** metadata. That explains
this session's 11 duplicate groups completely, and the fault is a tagging
pass run between two imports: the 17:20 copy of `CL-00560` had no keywords, the
keyword pass added them, and the 18:45 import therefore looked like a different
asset and was accepted. Nothing was wrong with the import — the metadata moved
underneath it.

Two rules follow:

- **Do not re-tag a file after it has been imported** unless you intend to
  replace the asset, and if you do, delete the old one. Lightroom will not
  protect you: changed metadata reads as a new image.
- **Finish tagging before the first import.** Get keywords, captions and the
  permalink right, then upload once. A file that is already in Lightroom and
  then re-tagged can no longer be safely re-uploaded at all.

The corollary bit: an untouched file *is* protected — re-dragging a folder whose
files have not been re-tagged is safe, because Lightroom rejects those as
duplicates. It is only the edited ones that slip through.

## Duplicates in Lightroom — 94 groups, 102 redundant assets

Measured 2026-09-03 across every archive from the fresh scrape:
`manifest/lightroom_duplicates_all_archives.csv`, one row per asset with its
id, timestamp, and which copy to keep. 792 assets stand for 698 images.

    54  UNLV Special Collections        2  San Francisco Public Library
    21  Utah Historical Society         1  Northwest Museum (Ferris Archives)
    14  Nevada Historical Society       1  Library of Congress
     5  Alamy

**Group by the image, not the filename.** A filename grouping finds only 66 of
these. The rest are the same photograph under two names: the archive's own
download name beside the numbered file (`Rio_Grande_Western_Railroad_P_29.jpg`
next to `16322.tif`), a `.jpg` and a `.tif` of the same number, or a title
carrying a zero-padded or barcode form of the id (`00523`, `39222001650915`).
So the match runs on filename stem, then `dc:title`, then the leading token of
the title, then the Utah caption, with leading zeros stripped throughout — and
every asset in a duplicate group matched exactly, none by the loose prefix
rule, so the list is safe to delete from.

Keeper is the numbered `.tif`: the 300 DPI master and the name Airtable holds.
Where several copies tie, the newest wins, because later imports carry the
fuller metadata — proven on `CL-00560`, whose 17:20 copy has no keywords and
whose second 17:20 copy is a **completely empty** failed import.

Deleting is UI work; the CSV is the worklist. Two related notes:

- **`2RGMMJ1` (Alamy) is the one place the naming rule does not apply.** Airtable
  holds `2RGMMJ1`, the real Alamy id, and Lightroom holds only
  `interior-of-dgs-store-wash-dc-ca-1910s-2RGMMJ1.jpg`. Matching Airtable to
  Lightroom would mean a 46-character Image ID, which fails "short enough for a
  human to use". Left as a mismatch on purpose.
- **4 assets are in Lightroom with no Airtable row at all** —
  `manifest/lightroom_orphans.csv`. `2017779954.tif` (imported 2021, predating
  this project) and `GP_0045_image_primary.tif` are unidentified.
  `Denver_Rio_Grande_Western_Railroad_P_287.jpg` and
  `San_Pedro_Los_Angeles_Salt_Lake_RR_P_5.jpg` are Utah copies titled with the
  14-digit barcode rather than the shelf number, so they are really duplicates
  of `29430` and `22582`.

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
