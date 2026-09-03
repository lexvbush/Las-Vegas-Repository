#!/usr/bin/env python3
"""pull_manifest - rebuild the manifests from Airtable, the source of truth.

    export AIRTABLE_TOKEN=pat...
    python3 scripts/pull_manifest.py
    python3 scripts/pull_manifest.py --dry-run      # report, write nothing
    python3 scripts/pull_manifest.py --save records.json
    python3 scripts/pull_manifest.py --from-json records.json   # offline

Replaces build_manifest.py, which parsed the Google Sheet export. The Sheet is
retired: it drifted from Airtable the moment anyone ticked a box in the base,
and a rebuild from it would silently revert that work.

The Sheet's one-time work does not need repeating -- the cleanup it did (float
IDs, splitting "<catalog id> / <download filename>", yes/true normalization)
and the values it derived (Category, Sequence, the keyword join) are already
materialized as Airtable fields. This script is a straight projection.

Nothing downstream changes: the two CSVs keep their columns and their names, so
lvtag audit/plan/apply/verify never know the difference. Keep the generated
CSVs committed -- they are what lets lvtag run without network access.
"""
import argparse, csv, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvlib import ROOT

BASE_ID  = "appntIAZCHnEatgyi"
TABLE_ID = "tblQdrGgTOzZSPr11"

# Airtable field id -> the manifest column it fills. Ids, not names: renaming a
# field in the Airtable UI must not break the pull.
FIELDS = {
    "fldZycqpCbXowegLM": "image_id",
    "fldvz3f14djaEoPl1": "title_caption",
    "fldgEx5Egbb6jTMOo": "sequence",
    "fldNwKddGf5hTKDlL": "category",
    "fldfBs32wvBI2qwwv": "archive",
    "fld9JsqInRFOSihYV": "source_url",
    "fld9JZkpAKC7QDo3z": "script_pages",
    "fldeVwgQNZcxkWlSH": "archive_filename",
    "flddvB1TGCBtAvk1E": "keywords",
    "fld08RC5Tutd1IOFt": "downloaded",
    "fldfh8BAQvFt58bmj": "in_lightroom",
    "fldqtC8YSwVWQhRbu": "metadata_attached",
    "fldstS0EBrlAuFi85": "topic",
}
CHECKBOXES = {"downloaded", "in_lightroom", "metadata_attached"}

MASTER_COLS = ["archive", "catalog_id", "title_caption", "source_url", "topic",
               "script_pages", "downloaded", "in_lightroom", "metadata_attached",
               "archive_filename", "keywords"]
EDITOR_COLS = ["sequence", "image_id", "category", "script_pages", "page_sort",
               "archive", "catalog_id", "archive_filename", "title_caption",
               "source_url", "keywords", "downloaded", "in_lightroom",
               "metadata_attached"]


def fetch(token):
    """Every record in the table, following Airtable's pagination."""
    out, offset = [], None
    while True:
        q = {"pageSize": 100, "returnFieldsByFieldId": "true"}
        if offset:
            q["offset"] = offset
        url = (f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
               f"?{urllib.parse.urlencode(q)}")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req) as r:
                page = json.load(r)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Airtable {e.code}: {e.read().decode()[:200]}")
        out.extend(page["records"])
        offset = page.get("offset")
        if not offset:
            return out


def scalar(v):
    """Airtable hands single-selects back as {id, name, color}."""
    if isinstance(v, dict):
        return str(v.get("name", "")).strip()
    if isinstance(v, list):
        return "; ".join(scalar(x) for x in v)
    return str(v).strip()


def project(records):
    rows = []
    for rec in records:
        cells = rec.get("fields") or rec.get("cellValuesByFieldId") or {}
        d = {col: "" for col in set(MASTER_COLS) | set(EDITOR_COLS)}
        for fid, col in FIELDS.items():
            v = cells.get(fid)
            if v is None:
                continue
            d[col] = "Yes" if col in CHECKBOXES and v is True else scalar(v)
        rows.append(d)

    # Image ID is the catalog ID verbatim, with two carried-over conventions:
    # NEEDS-ID-nn stands in for a row that has no archive ID yet, and a "-n"
    # tail disambiguates an ID the sheet reused across two rows.
    #
    # Stripping that tail is the one place this projection can corrupt data:
    # UNLV catalog IDs legitimately end in a sequence number (pho033930-002,
    # pho021426-011), and pho033930 exists as its own row, so "the bare ID is
    # also present" is not enough of a test. The disambiguating tail is always
    # an unpadded integer of 2 or more; UNLV's is zero-padded. Require that,
    # and report every strip so this can never happen quietly.
    ids = {d["image_id"] for d in rows}
    stripped = []
    for d in rows:
        iid = d["image_id"]
        d["catalog_id"] = iid
        if iid.startswith("NEEDS-ID-"):
            d["catalog_id"] = ""
            continue
        m = re.fullmatch(r"(.*)-([2-9]|[1-9]\d+)", iid)
        if m and m.group(1) in ids:
            d["catalog_id"] = m.group(1)
            stripped.append(iid)
    if stripped:
        print(f"  de-duplicating tail stripped from {len(stripped)}: "
              f"{', '.join(sorted(stripped))}")

    for d in rows:
        m = re.search(r"(\d+)", d["script_pages"])
        d["page_sort"] = int(m.group(1)) if m else 9999
        d["sequence"] = int(d["sequence"]) if str(d["sequence"]).isdigit() else 99999
    rows.sort(key=lambda d: (d["sequence"], d["page_sort"], d["archive"]))
    return rows


def write(rows):
    for name, cols in (("master_manifest.csv", MASTER_COLS),
                       ("editor_manifest.csv", EDITOR_COLS)):
        with open(ROOT / "manifest" / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from-json", metavar="FILE",
                   help="project a saved records dump instead of calling Airtable")
    p.add_argument("--save", metavar="FILE", help="also write the raw records here")
    p.add_argument("--dry-run", action="store_true", help="report without writing")
    a = p.parse_args()

    if a.from_json:
        records = json.load(open(a.from_json, encoding="utf-8"))
        records = records.get("records", records)
    else:
        token = os.environ.get("AIRTABLE_TOKEN")
        if not token:
            raise SystemExit(
                "AIRTABLE_TOKEN is not set. Create a personal access token at\n"
                "https://airtable.com/create/tokens with data.records:read on the\n"
                "'Las Vegas Documentary — Archival Images' base, then:\n"
                "    export AIRTABLE_TOKEN=pat...")
        records = fetch(token)
        if a.save:
            json.dump(records, open(a.save, "w", encoding="utf-8"), indent=1)

    rows = project(records)
    noid = sum(1 for d in rows if not d["catalog_id"])
    dl   = sum(1 for d in rows if d["downloaded"] == "Yes")
    md   = sum(1 for d in rows if d["metadata_attached"] == "Yes")
    topic = sum(1 for d in rows if d["topic"])
    uncat = sum(1 for d in rows if d["category"] == "Uncategorized")
    print(f"{len(rows)} rows | downloaded {dl} | metadata {md} | topic {topic} | "
          f"no catalog id {noid} | uncategorized {uncat}")
    if a.dry_run:
        print("dry run -- nothing written")
        return
    write(rows)
    print("wrote manifest/master_manifest.csv, manifest/editor_manifest.csv")


if __name__ == "__main__":
    main()
