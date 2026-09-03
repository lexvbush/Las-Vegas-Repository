# Session Handoff — September 3, 2026

Read `Las-Vegas-Repository/CLAUDE.md` first; it carries the standing rules and
was updated heavily today. This file is just where things stand and what is next.

All work is committed and pushed — 35 commits on branch
`claude/hello-las-vegas-repo-hrdutj`, nothing uncommitted.

## The numbers

| | |
|---|---|
| Airtable rows | **790** (no duplicate Image IDs) |
| In Lightroom | 704 |
| Metadata attached | 322 |
| Downloaded | 327 |
| Uncategorized | 290 |
| Controlled vocabulary | **296 terms** (was 239) |
| Early 1900s album | **843 assets** |

## Six standing rules established today

These are Alexa's calls. They are in CLAUDE.md and in Claude's memory files.

1. **The Source URL goes in the caption.** Lightroom stores
   `xmpRights:WebStatement` but never displays it, so `build_fields` ends every
   description with `Permalink: <url>`. A URL nobody can see is useless.
2. **TIFs only; a JPEG needs a URL.** JPEGs are placeholders, acceptable only if
   the URL can be followed to buy the TIF.
3. **Always 5–10 keywords**, from `vocabulary/keywords.csv`. Grow the vocabulary
   rather than padding or writing free text.
4. **Naming follows Lightroom.** If an image is already in Lightroom, change
   Airtable to match its filename — never rename in Lightroom.
5. **"In Lightroom" means the Early 1900s album**, not the catalog. The catalog
   holds 19,000+ assets (Alexa's whole library). A file in the catalog but not
   the album needs **moving**, never importing.
6. **Lightroom dedupes on pixels + metadata.** Re-tagging a file after import
   makes it re-importable as a new asset. Finish tagging before the first
   import; never re-tag something already in Lightroom.

Rule 6 explains this session's 11 duplicate groups: a keyword pass ran between
two of Alexa's imports, so the second batch looked like new assets.

## Alexa's queue

1. **Import `September 3/Ready to Upload`** — 1 file, `snv000351.tif` (Jake's
   Dance Hall, Goldfield). Fully to spec.
2. **Move `ESM-01420` into the album** — the last of the 8. It is hard to find
   because the catalog holds it as **`ESM-01420 .jpg`**, with a trailing space
   before the extension. It is also only 450×258 and wants re-sourcing.
3. **Delete 102 duplicate Lightroom assets** — worklist at
   `manifest/lightroom_cleanup_worklist.md`, split into 36 findable by filename
   and 66 needing the date-added column. Nothing is blocked by this.
4. **Empty `Adjust/_low-res duplicates - trash/`** — 9 superseded files, safe to
   delete.
5. **Ask Sarah Patton** for better scans of `ESM-01420` (450×258) and
   `AAB-6092` (302×400, SFPL). Both are near-thumbnail size.

## Next agent's queue

- **`Adjust/` leftovers**: `pho024864-004.tif` (tagged, needs an album move),
  `snv002133.tif`, and `Goldfield_Rawhide_PersonalViews_PhotoAlbum_1904-1909.pdf`
  which has not been looked at at all.
- **The 7 photographs with no Source URL**, six of which also have a blank
  Archive field — `manifest/jpeg_needs_url.csv`. `chs-m958`, `sanfran-sewers`,
  `0038 0037`, `FirstMailPlane`, and the three Reno Mill / lumber files.
- **4 Lightroom orphans** with no Airtable row —
  `manifest/lightroom_orphans.csv`. `2017779954.tif` was imported in **2021** and
  predates this project.
- **The Peter Buol doc's leftovers**: `pho016226`, `pho023883`, `snv001880`,
  `snv001887`, plus the BLM General Land Office survey plats, which the doc
  flags as the federal paperwork Buol actually handled.
- **Mine `manifest/uploaded_files_moved.csv` for script pages.** The 386 files
  moved today came from folders whose names encode script references —
  `P.58 Eldorado Canyon Wagons`, `P.66 Walter Bracken Desk Office`,
  `P.91 Machine Shop Interior 1909-1910`. That information exists **nowhere
  else** now, and Airtable's Script Page field is mostly empty.
- **Two malformed Image IDs left alone deliberately**:
  `182-Reno Mill &amp; Lumber Company` (HTML entity, and Lightroom has the same
  entity in its filename) and `Pile of lumber by RR tracks, cheat:close ups`
  (a caption in the ID field). Both match Lightroom as they stand, so fixing
  either needs a paired Airtable + Lightroom rename.
- **`2RGMMJ1` (Alamy) is deliberately mismatched.** Lightroom holds only a
  46-character slug and adopting it would fail "short enough for a human to use".

## Tooling added today

- `scripts/push_manifest.py` — the write counterpart to `pull_manifest.py`.
  Plans by default, `--apply` to write, `--create` for new records, `--upsert`
  required before it will touch an existing row, every change logged with its
  old value to `manifest/push_log.csv`.
- Token now comes from `.env` at the repo root (gitignored) via `load_token()`.
- `manifest/deleted_records.csv` — contents of every deleted Airtable record.
- `Lightroom Album - Early 1900s - 2026-09-03.json` (843) and
  `Lightroom Compendium - 2026-09-03.json` (792 catalog assets).

## Two scrape gotchas that cost time

- `get_page_text` truncates near 51 KB. For a dump larger than that, print it
  **twice — once reversed** — and merge the two saved files. Also glue back any
  line split by a title containing a newline.
- Paginating the full Lightroom catalog is unreliable: the cursor loops and the
  unique count froze at 19,349 while rows kept arriving. It can confirm a file
  is present but **cannot prove one absent**.

## Disk layout

```
Vegas Downloads Full Folder/
  _Uploaded to Lightroom/          409 files that are in the album (+ _duplicate on disk/)
  Adjust/                          leftovers + _low-res duplicates - trash/
  September 3/Ready to Upload/     snv000351.tif
  September 3/_in catalog - move into album/   ESM-01420.jpg
  September 3/_done - in album/, _already in Lightroom/, Don't want/, _exiftool backups/
  Folder Archive/                  reference only — Alexa asked that it be left alone
  UHS Alexa Bush #26-052/          the Utah 28 + pristine backups
```
