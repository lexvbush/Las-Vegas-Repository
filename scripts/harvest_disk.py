#!/usr/bin/env python3
"""harvest_disk - read the archive's own metadata out of the downloaded TIFs.

    python3 scripts/harvest_disk.py --folder "~/Downloads/Vegas Downloads Full Folder"

Archives embed their catalogue record in the file they hand you: the item
title, a longer description, the owning collection, subject terms, and -- most
usefully -- the permalink back to the record. That is the archive speaking
directly, so it is better evidence than anything typed into a sheet later.

This reads it back out and writes a side-by-side review file. It writes nothing
to Airtable and touches no image: you read the proposal, then decide.

Output: manifest/harvest_disk.csv, one row per matched file, with the current
Airtable value beside the harvested one and a "change" column saying whether
the harvested value would add something new, differ from what is there, or
match it already.
"""
import argparse, csv, json, os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvlib import ROOT, load_manifest, index_files, norm_file

TAGS = ["FileName", "Title", "ObjectName", "Description", "Caption-Abstract",
        "ImageDescription", "Creator", "Artist", "Rights", "Copyright",
        "Subject", "Keywords", "WebStatement", "Source"]

# Archives park the permalink at the end of the description rather than in a
# dedicated field, so it has to be pulled back out and trimmed off the caption.
PERMALINK = re.compile(r"\s*Permalink:\s*(\S+)\s*$", re.I)
# UNLV appends the owning collection in brackets; that belongs with the archive,
# not in the middle of a caption.
COLLECTION = re.compile(r"\s*\[([^\]]+)\]\s*$")


def first(d, *keys):
    for k in keys:
        v = str(d.get(k) or "").strip()
        if v:
            return v
    return ""


def harvest(path_list):
    out = subprocess.run(["exiftool", "-j", "-charset", "iptc=UTF8",
                          *[f"-{t}" for t in TAGS], *path_list],
                         capture_output=True, text=True)
    if out.returncode != 0 and not out.stdout:
        raise SystemExit(f"exiftool failed: {out.stderr[:200]}")
    return json.loads(out.stdout)


def parse(d):
    """-> {caption, description, url, archive_collection, subjects}"""
    title = first(d, "Title", "ObjectName")
    desc = first(d, "Description", "Caption-Abstract", "ImageDescription")

    url = first(d, "WebStatement")
    m = PERMALINK.search(desc)
    if m:
        url = url or m.group(1)
        desc = PERMALINK.sub("", desc)

    collection = ""
    m = COLLECTION.search(desc)
    if m:
        collection = m.group(1)
        desc = COLLECTION.sub("", desc)

    subj = first(d, "Subject", "Keywords")
    if isinstance(d.get("Subject"), list):
        subj = "; ".join(str(x) for x in d["Subject"])

    return {"caption": title.strip(), "description": desc.strip(), "url": url.strip(),
            "collection": (collection or first(d, "Rights", "Copyright")).strip(),
            "subjects": subj.strip()}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--folder", required=True)
    a = p.parse_args()

    rows = load_manifest()
    by_id = {}
    for r in rows:
        k = norm_file(r["catalog_id"])
        if k:
            by_id.setdefault(k, r)

    files = index_files(a.folder)
    data = harvest([str(f) for f in files])

    out = ROOT / "manifest" / "harvest_disk.csv"
    counts = {"new": 0, "differs": 0, "same": 0, "nothing to harvest": 0, "no row": 0}
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "catalog_id", "archive", "change",
                    "current_caption", "harvested_caption", "harvested_description",
                    "current_url", "harvested_url", "collection", "subjects"])
        for d in data:
            stem = Path(d["FileName"]).stem
            row = by_id.get(norm_file(stem))
            h = parse(d)
            if not row:
                counts["no row"] += 1
                change = "no row"
            elif not h["caption"] and not h["description"]:
                counts["nothing to harvest"] += 1
                change = "nothing to harvest"
            elif not row["title_caption"].strip():
                counts["new"] += 1
                change = "new"
            elif norm_file(row["title_caption"]) != norm_file(h["caption"]):
                counts["differs"] += 1
                change = "differs"
            else:
                counts["same"] += 1
                change = "same"
            w.writerow([d["FileName"], row["catalog_id"] if row else "",
                        row["archive"] if row else "", change,
                        row["title_caption"] if row else "",
                        h["caption"], h["description"],
                        row["source_url"] if row else "", h["url"],
                        h["collection"], h["subjects"]])

    print(f"\n  {len(files)} files read")
    for k, v in counts.items():
        print(f"    {v:>4}  {k}")
    gained = sum(1 for d in data if parse(d)["url"])
    print(f"\n  {gained} files carry a permalink")
    print(f"  review -> {out.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
