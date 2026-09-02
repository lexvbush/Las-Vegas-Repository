#!/usr/bin/env python3
"""lvtag - embed archival metadata into Las Vegas documentary TIFs.

    python3 scripts/lvtag.py audit    --folder "~/Vegas Downloads Full Folder"
    python3 scripts/lvtag.py plan     --folder "~/Vegas Downloads Full Folder"
    python3 scripts/lvtag.py apply    --folder "~/Vegas Downloads Full Folder"
    python3 scripts/lvtag.py verify   --folder "~/Vegas Downloads Full Folder"
    python3 scripts/lvtag.py daily    --folder "~/Vegas Downloads Full Folder"
    python3 scripts/lvtag.py keywords

Metadata is embedded before upload because Lightroom's cloud version never
writes metadata back into original files -- whatever is in the TIF at upload
time is what teammates get when they download it again.
"""
import argparse, csv, datetime as dt, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lvlib import (ROOT, target_name, archive_code, load_manifest, load_vocab, load_merges, normalize_keywords,
                   build_fields, index_files, match_files, write_metadata,
                   read_metadata, exiftool_available, norm_kw)

C = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "b": "\033[1m", "x": "\033[0m"}


def c(s, k):
    return f"{C[k]}{s}{C['x']}"


def _prepare(args):
    rows = load_manifest()
    if args.pending:
        rows = [r for r in rows if r["metadata_attached"].strip().lower() != "yes"]
    vocab, merges = load_vocab(), load_merges()
    files = index_files(args.folder)
    matches, miss_rows, extra_files = match_files(rows, files)
    return rows, vocab, merges, files, matches, miss_rows, extra_files


def cmd_audit(args):
    """Reconcile the sheet against what is actually on disk."""
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    print(c(f"\n  {len(files)} TIFs on disk / {len(rows)} manifest rows\n", "b"))
    print(f"  matched to a sheet row      {c(len(matches),'g')}")
    print(f"  sheet rows with no file     {c(len(miss_rows),'y')}")
    print(f"  files not in the sheet      {c(len(extra),'y')}")

    # where the sheet's own status columns disagree with reality
    drift = []
    for row, path in matches:
        said = row["downloaded"].strip().lower() == "yes"
        if not said:
            drift.append((row, "on disk but Downloaded is blank"))
    for row in miss_rows:
        if row["downloaded"].strip().lower() == "yes":
            drift.append((row, "marked Downloaded but no file found"))
    print(f"  status drift vs. the sheet  {c(len(drift),'r' if drift else 'g')}")

    if drift and not args.quiet:
        print(c("\n  Status drift\n", "b"))
        for row, why in drift[:args.limit]:
            print(f"    {row['archive'][:28]:<28} {row['catalog_id'][:24]:<24} {why}")
        if len(drift) > args.limit:
            print(f"    ... {len(drift)-args.limit} more")

    if miss_rows and not args.quiet:
        print(c("\n  Sheet rows with no matching file\n", "b"))
        for row in miss_rows[:args.limit]:
            flag = "needs metadata" if row["metadata_attached"].strip().lower() != "yes" else ""
            print(f"    {row['archive'][:28]:<28} {row['catalog_id'][:24]:<24} {flag}")
        if len(miss_rows) > args.limit:
            print(f"    ... {len(miss_rows)-args.limit} more")

    if extra and not args.quiet:
        print(c("\n  Files on disk not in the sheet\n", "b"))
        for p in extra[:args.limit]:
            print(f"    {p.name}")
        if len(extra) > args.limit:
            print(f"    ... {len(extra)-args.limit} more")

    out = ROOT / "manifest" / "audit_report.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["status", "archive", "catalog_id", "title_caption", "file", "note"])
        for row, path in matches:
            w.writerow(["matched", row["archive"], row["catalog_id"],
                        row["title_caption"], path.name, ""])
        for row in miss_rows:
            w.writerow(["no_file", row["archive"], row["catalog_id"],
                        row["title_caption"], "", "in sheet, not on disk"])
        for p in extra:
            w.writerow(["no_row", "", "", "", p.name, "on disk, not in sheet"])
    print(f"\n  report -> {c(out.relative_to(ROOT), 'g')}\n")


def cmd_plan(args):
    """Show exactly what would be written, without touching a file."""
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    if not matches:
        print(c("\n  Nothing matched. Run `audit` to see why.\n", "y"))
        return
    unknown_all = set()
    for row, path in matches[:args.limit]:
        kws, unknown = normalize_keywords(row.get("keywords", ""), vocab, merges)
        unknown_all.update(unknown)
        fields, kws = build_fields(row, kws)
        print(c(f"\n  {path.name}", "b"))
        for k in ("XMP-dc:Title", "XMP-dc:Description", "XMP-dc:Creator", "XMP-dc:Rights"):
            if k in fields:
                print(f"    {k.split(':')[1]:<14} {fields[k][:96]}")
        if kws:
            print(f"    {'Keywords':<14} {', '.join(kws)}")
    print(c(f"\n  {len(matches)} file(s) ready to tag.", "b"))
    if unknown_all:
        print(c(f"  {len(unknown_all)} keyword(s) outside the vocabulary: ", "y")
              + ", ".join(sorted(unknown_all)[:12]))
    print()


def cmd_apply(args):
    if not exiftool_available():
        raise SystemExit(c("\n  exiftool not found. See README for install.\n", "r"))
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    if not matches:
        print(c("\n  Nothing matched. Run `audit` first.\n", "y"))
        return
    print(c(f"\n  Tagging {len(matches)} file(s)\n", "b"))
    ok = fail = 0
    done = []
    for row, path in matches:
        kws, _ = normalize_keywords(row.get("keywords", ""), vocab, merges)
        fields, kws = build_fields(row, kws)
        good, msg = write_metadata(path, fields, kws, backup=not args.no_backup)
        if good:
            ok += 1
            done.append((row, path))
            print(f"    {c('ok','g')}   {path.name}")
        else:
            fail += 1
            print(f"    {c('fail','r')} {path.name}  {msg[:70]}")
    print(f"\n  {c(ok,'g')} tagged, {c(fail,'r' if fail else 'g')} failed")
    if not args.no_backup and ok:
        print(c("  originals kept as *_original alongside each file", "y"))
    print()
    if done and args.stage:
        _stage(done)


def _stage(done):
    day = dt.date.today().isoformat()
    out = Path(ROOT) / "daily" / day
    out.mkdir(parents=True, exist_ok=True)
    for row, path in done:
        shutil.copy2(path, out / path.name)
    print(f"  staged {len(done)} file(s) -> {c(out, 'g')}\n")


def cmd_verify(args):
    if not exiftool_available():
        raise SystemExit(c("\n  exiftool not found. See README for install.\n", "r"))
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    need = ["XMP:Title", "XMP:Description", "XMP:Creator", "XMP:Rights", "XMP:Subject"]
    print(c(f"\n  Verifying {len(matches)} file(s)\n", "b"))
    clean = 0
    for row, path in matches:
        got = read_metadata(path, ["Title", "Description", "Creator", "Rights", "Subject"])
        missing = [k for k in ("Title", "Description", "Creator", "Rights") if not got.get(k)]
        if missing:
            print(f"    {c('gap','y')}  {path.name}  missing: {', '.join(missing)}")
        else:
            clean += 1
    print(f"\n  {c(clean,'g')} fully tagged / {len(matches)} checked\n")


def cmd_daily(args):
    """Copy every already-tagged file into today's upload folder."""
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    _stage(matches)


def cmd_keywords(args):
    """Report keyword hygiene across the manifest."""
    rows, vocab, merges = load_manifest(), load_vocab(), load_merges()
    unknown = {}
    for row in rows:
        _, unk = normalize_keywords(row.get("keywords", ""), vocab, merges)
        for u in unk:
            unknown.setdefault(u, 0)
            unknown[u] += 1
    print(c(f"\n  {len(vocab)} controlled terms / {len(merges)} merge rules\n", "b"))
    if unknown:
        print(c("  Terms not in the vocabulary\n", "y"))
        for k, n in sorted(unknown.items(), key=lambda x: -x[1])[:args.limit]:
            print(f"    {n:>3}x  {k}")
    else:
        print(c("  Every keyword in the manifest is in the vocabulary.", "g"))
    print()


def cmd_rename(args):
    """Put the archive and catalog ID into the filename itself.

    Metadata can be stripped by a careless export; a filename cannot be lost
    without someone noticing. This is the last line of provenance defence.
    """
    rows, vocab, merges, files, matches, miss_rows, extra = _prepare(args)
    planned, clashes = [], set()
    for row, path in matches:
        want = target_name(row, path.suffix.lower())
        if path.name == want:
            continue
        dest = path.with_name(want)
        if dest.exists() or want in clashes:
            print(f"    {c('skip','y')} {path.name} -> {want} (name taken)")
            continue
        clashes.add(want)
        planned.append((path, dest))
    if not planned:
        print(c("\n  Every matched file is already named correctly.\n", "g"))
        return
    print(c(f"\n  {len(planned)} rename(s){'' if args.apply else ' (dry run)'}\n", "b"))
    for src, dest in planned[:args.limit]:
        print(f"    {src.name}\n      -> {c(dest.name,'g')}")
    if len(planned) > args.limit:
        print(f"    ... {len(planned)-args.limit} more")
    if args.apply:
        for src, dest in planned:
            src.rename(dest)
        print(c(f"\n  renamed {len(planned)} file(s)\n", "g"))
    else:
        print(c("\n  add --apply to perform the renames\n", "y"))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, helptext in [
        ("audit", cmd_audit, "reconcile the sheet against files on disk"),
        ("plan", cmd_plan, "preview the metadata without writing"),
        ("apply", cmd_apply, "embed the metadata into the TIFs"),
        ("verify", cmd_verify, "read metadata back out and check it stuck"),
        ("daily", cmd_daily, "copy tagged files into today's upload folder"),
        ("rename", cmd_rename, "rename files to ARCHIVE_catalogid_caption.tif"),
        ("keywords", cmd_keywords, "report keywords outside the vocabulary"),
    ]:
        s = sub.add_parser(name, help=helptext)
        s.set_defaults(func=fn)
        if name != "keywords":
            s.add_argument("--folder", required=True, help="folder holding the TIFs")
            s.add_argument("--pending", action="store_true",
                           help="only rows whose metadata column is not Yes")
            s.add_argument("--quiet", action="store_true")
        s.add_argument("--limit", type=int, default=25)
        if name == "rename":
            s.add_argument("--apply", action="store_true",
                           help="actually rename (default is a dry run)")
        if name == "apply":
            s.add_argument("--no-backup", action="store_true",
                           help="overwrite in place without keeping *_original")
            s.add_argument("--stage", action="store_true",
                           help="also copy tagged files into daily/<today>/")
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
