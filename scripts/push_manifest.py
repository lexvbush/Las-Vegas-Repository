#!/usr/bin/env python3
"""push_manifest - write a reviewed CSV back into Airtable, the source of truth.

    export AIRTABLE_TOKEN=pat...              # data.records:read AND :write
    python3 scripts/push_manifest.py --csv manifest/caption_proposal.csv
    python3 scripts/push_manifest.py --csv manifest/caption_proposal.csv --apply

The counterpart to pull_manifest.py. Bulk Airtable writes were the expensive
part of every session: each record had to be printed by the browser and then
retyped into an update call, one permission prompt at a time. This does the
whole pass in one local run.

Plan first, like everything else here -- it writes nothing without --apply.
The plan is the point: it shows old -> new for every cell it would touch, and
skips the cells that already agree, so a 200-row proposal usually turns out to
be a few dozen real changes.

Input is any CSV keyed by image_id or catalog_id whose other columns name
Airtable fields. The review files this repo already produces work as they are:
harvest_disk.csv and caption_proposal.csv use NEW_<field> for the proposed
value beside a current_<field> column, and only the NEW_ side is read. The
generated manifests work too, so master_manifest.csv can be pushed back after
an offline edit.

Two safety defaults, both overridable:

- A blank cell means "leave this alone", not "clear it". The proposal files are
  sparse -- most rows fill in a caption and nothing else -- so treating blanks
  as deletions would wipe most of the base. --allow-blank to actually clear.
- Single-select values are checked against the choices already in use on other
  records. Airtable rejects an unknown choice unless --typecast is passed, and
  typecast on a select field creates the choice, which is how a base grows a
  "Uncategorised" beside its "Uncategorized".

Every applied change is appended to manifest/push_log.csv with its old value,
so a bad pass can be read back and reverted.
"""
import argparse, csv, datetime as dt, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvlib import ROOT

BASE_ID  = "appntIAZCHnEatgyi"
TABLE_ID = "tblQdrGgTOzZSPr11"

API   = "https://api.airtable.com/v0"
BATCH = 10     # Airtable's hard cap on records per create/update call
RATE  = 0.22   # 5 requests/second/base is the documented limit

C = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "b": "\033[1m",
     "d": "\033[2m", "x": "\033[0m"}


def c(s, k):
    return f"{C[k]}{s}{C['x']}"


# Field ids, not names: renaming a field in the Airtable UI must not silently
# redirect a write. Mirrors pull_manifest.FIELDS, plus the three fields added
# 2026-09-02 that the pull does not project.
FIELDS = {
    "fldZycqpCbXowegLM": "Image ID",
    "fldvz3f14djaEoPl1": "Caption",
    "fldstS0EBrlAuFi85": "Topic",
    "fldNwKddGf5hTKDlL": "Category",
    "fld9JsqInRFOSihYV": "Source URL",
    "fldfBs32wvBI2qwwv": "Archive",
    "fld9JZkpAKC7QDo3z": "Script Page",
    "fldgEx5Egbb6jTMOo": "Sequence",
    "fldeVwgQNZcxkWlSH": "Archive Filename",
    "flddvB1TGCBtAvk1E": "Keywords",
    "fld08RC5Tutd1IOFt": "Downloaded",
    "fldfh8BAQvFt58bmj": "In Lightroom",
    "fldqtC8YSwVWQhRbu": "Metadata Attached",
    "fldbILRugea6R5XzA": "Description",
    "fldZALA7NYBeaNN6u": "Collection",
    "fldKRdoXq8pKrWta2": "Archive Subjects",
}
NAME_TO_ID  = {v: k for k, v in FIELDS.items()}
CHECKBOXES  = {"fld08RC5Tutd1IOFt", "fldfh8BAQvFt58bmj", "fldqtC8YSwVWQhRbu"}
NUMBERS     = {"fldgEx5Egbb6jTMOo"}
SELECTS     = {"fldNwKddGf5hTKDlL", "fldfBs32wvBI2qwwv"}
KEY_FIELD   = "fldZycqpCbXowegLM"           # Image ID, the primary field

# The manifest column names, so a generated CSV can be pushed back unchanged.
COLUMN_ALIASES = {
    "image_id": "Image ID",
    "title_caption": "Caption",
    "caption": "Caption",
    "description": "Description",
    "collection": "Collection",
    "subjects": "Archive Subjects",
    "archive_subjects": "Archive Subjects",
    "keywords": "Keywords",
    "source_url": "Source URL",
    "url": "Source URL",
    "archive": "Archive",
    "archive_filename": "Archive Filename",
    "category": "Category",
    "topic": "Topic",
    "sequence": "Sequence",
    "script_pages": "Script Page",
    "script_page": "Script Page",
    "downloaded": "Downloaded",
    "in_lightroom": "In Lightroom",
    "metadata_attached": "Metadata Attached",
}

# Columns that name a field this base deliberately does not have. Editor Notes
# and Thumbnail were deleted 2026-09-02 and must not be recreated -- production
# commentary found in archive metadata stays in caption_proposal.csv. Named
# here so a proposal file carrying the column is reported, not silently pushed.
REFUSED = {"editor_note": "Editor Notes was deleted 2026-09-02 -- do not recreate",
           "editor_notes": "Editor Notes was deleted 2026-09-02 -- do not recreate",
           "thumbnail": "Thumbnail was deleted 2026-09-02 -- do not recreate"}

# Columns that carry the *current* value in a review file, for comparison only.
IGNORE_PREFIX = ("current_", "previous_", "harvested_", "old_")
IGNORE_EXACT  = {"file", "change", "catalog_id", "page_sort", "confidence",
                 "evidence", "group", "reason", "status", "keep_or_merge"}


# --- HTTP --------------------------------------------------------------------
def request(method, path, token, body=None, tries=4):
    """One Airtable call, retried on rate limit and transient server error."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(tries):
        req = urllib.request.Request(
            f"{API}/{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                wait = 2 ** attempt
                print(c(f"    {e.code} -- retrying in {wait}s", "y"))
                time.sleep(wait)
                continue
            raise SystemExit(f"Airtable {e.code}: {detail}")
        except urllib.error.URLError as e:
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"network error: {e}")


def fetch(token):
    """Every record in the table, following Airtable's pagination."""
    out, offset = [], None
    while True:
        q = {"pageSize": 100, "returnFieldsByFieldId": "true"}
        if offset:
            q["offset"] = offset
        page = request("GET", f"{BASE_ID}/{TABLE_ID}?{urllib.parse.urlencode(q)}",
                       token)
        out.extend(page["records"])
        offset = page.get("offset")
        if not offset:
            return out


# --- Values ------------------------------------------------------------------
def norm_key(s):
    """Image IDs differ only in capitalisation across sources (UNLV writes
    pho... lowercase, the retired Sheet had Pho...), so match case-folded."""
    return re.sub(r"\s+", "", (s or "").strip().lower())


def coerce(fid, raw):
    """CSV text -> the JSON type Airtable wants for that field."""
    s = (raw or "").strip()
    if fid in CHECKBOXES:
        return s.lower() in ("yes", "true", "1", "y", "checked", "x")
    if fid in NUMBERS:
        if not s:
            return None
        try:
            return int(s) if re.fullmatch(r"-?\d+", s) else float(s)
        except ValueError:
            return None
    return s


def current(cells, fid):
    """The record's present value, in the same shape coerce() produces."""
    v = cells.get(fid)
    if fid in CHECKBOXES:
        return v is True
    if fid in NUMBERS:
        return v if isinstance(v, (int, float)) else None
    if isinstance(v, dict):          # single-select comes back {id, name, color}
        return str(v.get("name", "")).strip()
    if isinstance(v, list):
        return "; ".join(str(x) for x in v).strip()
    return "" if v is None else str(v).strip()


def same(a, b):
    """Equal for push purposes -- whitespace and case are not a change."""
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if a is None or b is None:
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return re.sub(r"\s+", " ", str(a)).strip() == re.sub(r"\s+", " ", str(b)).strip()


def show(v, width=58):
    if v is True:
        return "Yes"
    if v is False:
        return "(unticked)"
    if v is None or v == "":
        return "(blank)"
    s = re.sub(r"\s+", " ", str(v))
    return s if len(s) <= width else s[:width - 1] + "…"


# --- Column mapping ----------------------------------------------------------
def map_columns(headers):
    """CSV header -> field id. Returns (mapping, key_column, notes).

    A review file marks its proposals with NEW_ and keeps the archive's present
    value beside them for comparison. Some of those context columns are named
    after a real field ("archive" in caption_proposal.csv), so once any NEW_
    column is seen the bare ones are treated as context and left out -- a
    proposal file must never push a column it only meant to show.
    """
    headers = [h for h in headers if (h or "").strip()]
    proposal = any((h or "").strip().lower().startswith("new_") for h in headers)
    mapping, notes, key_col = {}, [], None
    for h in headers:
        raw = (h or "").strip()
        low = raw.lower()
        if not raw:
            continue
        if low in ("image_id", "image id") and key_col is None:
            key_col = raw
            continue
        if low in ("catalog_id", "catalog id") and key_col is None:
            key_col = raw          # only if no image_id column turns up
            continue
        bare = re.sub(r"^new_", "", low)
        if bare in REFUSED:
            notes.append((raw, c(REFUSED[bare], "r")))
            continue
        if low in IGNORE_EXACT or low.startswith(IGNORE_PREFIX):
            continue
        if proposal and not low.startswith("new_"):
            continue
        name = (COLUMN_ALIASES.get(bare)
                or next((n for n in NAME_TO_ID if n.lower() == bare.replace("_", " ")), None)
                or next((n for n in NAME_TO_ID if n.lower() == bare), None))
        if name:
            mapping[raw] = NAME_TO_ID[name]
        else:
            notes.append((raw, "no matching Airtable field -- ignored"))
    return mapping, key_col, notes


# --- Planning ----------------------------------------------------------------
def plan(rows, key_col, mapping, records, allow_blank):
    by_key, dupes = {}, set()
    for rec in records:
        cells = rec.get("fields") or {}
        k = norm_key(current(cells, KEY_FIELD))
        if k in by_key:
            dupes.add(k)
        by_key.setdefault(k, rec)

    known = {fid: {current(r.get("fields") or {}, fid)
                   for r in records} - {""} for fid in SELECTS}

    edits, missing, blanks, newchoice = {}, [], 0, {}
    for row in rows:
        key = norm_key(row.get(key_col))
        if not key:
            continue
        rec = by_key.get(key)
        if not rec:
            missing.append(row.get(key_col))
            continue
        cells = rec.get("fields") or {}
        for col, fid in mapping.items():
            raw = row.get(col)
            if raw is None:
                continue
            if not str(raw).strip() and fid not in CHECKBOXES and not allow_blank:
                blanks += 1
                continue
            new, old = coerce(fid, raw), current(cells, fid)
            if same(new, old):
                continue
            if fid in SELECTS and new and new not in known[fid]:
                newchoice.setdefault(fid, set()).add(new)
            edits.setdefault(rec["id"], {"key": row.get(key_col), "cells": {}})
            edits[rec["id"]]["cells"][fid] = (old, new)
    return edits, missing, blanks, newchoice, dupes


def log_edits(edits, applied):
    path = ROOT / "manifest" / "push_log.csv"
    new = not path.exists()
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["when", "record_id", "image_id", "field",
                        "old_value", "new_value", "result"])
        for rid, e in edits.items():
            for fid, (old, new) in e["cells"].items():
                w.writerow([stamp, rid, e["key"], FIELDS[fid],
                            "" if old is None else old,
                            "" if new is None else new,
                            applied.get(rid, "not attempted")])
    return path


# --- Applying ----------------------------------------------------------------
def apply(edits, token, typecast):
    items = [{"id": rid, "fields": {fid: v[1] for fid, v in e["cells"].items()}}
             for rid, e in edits.items()]
    results, done = {}, 0
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        body = {"records": chunk}
        if typecast:
            body["typecast"] = True
        request("PATCH", f"{BASE_ID}/{TABLE_ID}", token, body)
        for r in chunk:
            results[r["id"]] = "ok"
        done += len(chunk)
        print(f"    {done}/{len(items)} records")
        if i + BATCH < len(items):
            time.sleep(RATE)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="reviewed CSV to push")
    p.add_argument("--apply", action="store_true",
                   help="actually write; without it this only plans")
    p.add_argument("--field", action="append", metavar="NAME",
                   help="restrict to this Airtable field (repeatable)")
    p.add_argument("--limit", type=int, default=40,
                   help="rows of the plan to print (default 40)")
    p.add_argument("--allow-blank", action="store_true",
                   help="treat an empty cell as 'clear this field'")
    p.add_argument("--typecast", action="store_true",
                   help="let Airtable coerce values and CREATE new select choices")
    p.add_argument("--from-json", metavar="FILE",
                   help="read current records from a dump instead of the API")
    p.add_argument("--save", metavar="FILE", help="also write the raw records here")
    a = p.parse_args()

    src = Path(a.csv)
    if not src.is_absolute() and not src.exists():
        src = ROOT / a.csv
    if not src.exists():
        raise SystemExit(f"no such CSV: {a.csv}")
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{src.name} has no data rows")

    mapping, key_col, notes = map_columns(rows[0].keys())
    if not key_col:
        raise SystemExit("no image_id or catalog_id column -- nothing to key on")
    if a.field:
        want = {f.lower() for f in a.field}
        mapping = {k: v for k, v in mapping.items() if FIELDS[v].lower() in want}
    if not mapping:
        raise SystemExit("no pushable columns in this CSV")

    token = None
    if a.from_json:
        records = json.load(open(a.from_json, encoding="utf-8"))
        if isinstance(records, dict):          # a raw API page, not a --save dump
            records = records.get("records", records)
    else:
        token = os.environ.get("AIRTABLE_TOKEN")
        if not token:
            raise SystemExit(
                "AIRTABLE_TOKEN is not set. Create a personal access token at\n"
                "https://airtable.com/create/tokens with data.records:read AND\n"
                "data.records:write on the 'Las Vegas Documentary -- Archival\n"
                "Images' base, then:\n"
                "    export AIRTABLE_TOKEN=pat...")
        records = fetch(token)
        if a.save:
            json.dump(records, open(a.save, "w", encoding="utf-8"), indent=1)

    print(c(f"\n  {src.name}: {len(rows)} rows, keyed on {key_col}", "b"))
    print(f"  {len(records)} records in Airtable\n")
    print("  pushing columns:")
    for col, fid in mapping.items():
        print(f"    {col:<24} -> {FIELDS[fid]}")
    for col, why in notes:
        print(f"    {c(col,'d'):<24}    {why}")

    edits, missing, blanks, newchoice, dupes = plan(
        rows, key_col, mapping, records, a.allow_blank)
    cells = sum(len(e["cells"]) for e in edits.values())

    print(c(f"\n  {cells} cells to change across {len(edits)} records", "b"))
    if blanks:
        print(f"  {c(blanks,'d')} blank cells left alone "
              f"({c('--allow-blank','d')} to clear them instead)")
    if missing:
        print(c(f"  {len(missing)} keys not found in Airtable: "
                f"{', '.join(str(x) for x in missing[:6])}"
                f"{' ...' if len(missing) > 6 else ''}", "y"))
    if dupes:
        print(c(f"  {len(dupes)} Image IDs appear on more than one record -- "
                f"the first was used", "y"))
    for fid, vals in newchoice.items():
        print(c(f"  {FIELDS[fid]}: {len(vals)} value(s) are not an existing "
                f"choice: {', '.join(sorted(vals)[:5])}", "r"))
        print(c(f"    Airtable will reject these without --typecast, and "
                f"--typecast CREATES them as new choices.", "r"))

    if not edits:
        print(c("\n  nothing to do\n", "g"))
        return

    print()
    shown = 0
    for e in edits.values():
        if shown >= a.limit:
            break
        print(f"  {c(e['key'], 'b')}")
        for fid, (old, new) in e["cells"].items():
            print(f"    {FIELDS[fid]:<18} {c(show(old),'d')}")
            print(f"    {'':<18} {c(show(new),'g')}")
        shown += 1
    if len(edits) > shown:
        print(f"  ... {len(edits) - shown} more records")

    if not a.apply:
        calls = -(-len(edits) // BATCH)
        print(c(f"\n  plan only -- add --apply to write "
                f"({calls} API call{'s' if calls != 1 else ''})\n", "y"))
        return

    print(c(f"\n  writing {len(edits)} records...", "b"))
    results = apply(edits, token, a.typecast)
    path = log_edits(edits, results)
    print(c(f"\n  {sum(1 for v in results.values() if v == 'ok')} records updated", "g"))
    print(f"  logged to {path.relative_to(ROOT)}")
    print(c("  re-run pull_manifest.py to bring the CSVs back in step\n", "y"))


if __name__ == "__main__":
    main()
