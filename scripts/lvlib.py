"""Shared helpers for the Las Vegas archival metadata workflow."""
import csv, os, re, subprocess, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest" / "master_manifest.csv"
VOCAB    = ROOT / "vocabulary" / "keywords.csv"
MERGES   = ROOT / "vocabulary" / "merge_map.csv"

# --- Production identity (from the VISUALS tab of the master sheet) -----------
PRODUCTION   = "Boyd Productions LLC on behalf of the City of Las Vegas"
USAGE_TERMS  = ("Licensed for use by Boyd Productions LLC on behalf of the City of "
                "Las Vegas. Not for redistribution. Confirm clearance before broadcast.")
IMAGE_TARGET = "300 DPI TIF"

TIF_EXT = {".tif", ".tiff", ".TIF", ".TIFF"}


# --- Loading -----------------------------------------------------------------
def load_manifest(path=MANIFEST):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_vocab(path=VOCAB):
    """-> {normalized_keyword: (Canonical Keyword, Category)}"""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[norm_kw(r["keyword"])] = (r["keyword"], r["category"])
    return out


def load_merges(path=MERGES):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[norm_kw(r["from"])] = r["to"]
    return out


# --- Normalization -----------------------------------------------------------
def norm_kw(s):
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9&'/ -]+", "", s).strip()


def norm_file(s):
    """Aggressive normalization for filename <-> catalog-ID matching."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def normalize_keywords(raw, vocab, merges):
    """Split, apply merge map, snap to controlled vocabulary.

    Semicolons are the primary delimiter. A comma only splits a piece when the
    piece is not itself a vocabulary term -- place names like "Los Angeles, CA"
    contain commas and must survive intact.

    Returns (canonical_keywords, unknown_terms). Order preserved, deduped.
    """
    if not raw:
        return [], []
    keep, unknown, seen = [], [], set()

    def add(term):
        """Append the canonical form. Returns True if it was a known term."""
        n = norm_kw(term)
        if n in merges:
            n = norm_kw(merges[n])
        known = n in vocab
        canon = vocab[n][0] if known else term.strip()
        if canon and canon.lower() not in seen:
            seen.add(canon.lower())
            keep.append(canon)
        return known

    for piece in raw.split(";"):
        piece = piece.strip()
        if not piece:
            continue
        n = norm_kw(piece)
        if n in vocab or n in merges:
            add(piece)
            continue
        parts = [x.strip() for x in piece.split(",") if x.strip()]
        if len(parts) > 1:
            for x in parts:
                if not add(x):
                    unknown.append(x)
        else:
            if not add(piece):
                unknown.append(piece)
    return keep, unknown


def extract_year(*texts):
    """First plausible 4-digit year (1800-2030) found in the given strings."""
    for t in texts:
        for m in re.finditer(r"\b(1[89]\d{2}|20[0-3]\d)\b", t or ""):
            return m.group(1)
    return None


# --- Field mapping -----------------------------------------------------------
def build_fields(row, keywords):
    """Map a manifest row to embedded metadata fields.

    Lightroom's web UI only surfaces Title, Caption, Creator, Copyright and
    keywords -- so provenance is packed into those. Everything else is still
    embedded for the archival record and travels with the file.
    """
    archive = (row.get("archive") or "").strip()
    cat_id  = (row.get("catalog_id") or "").strip()
    caption = (row.get("title_caption") or "").strip()
    url     = (row.get("source_url") or "").strip()
    pages   = (row.get("script_pages") or "").strip()
    arc_file = (row.get("archive_filename") or "").strip()

    # Caption is the widest field the team can read in the browser, so it
    # carries the human description *and* the provenance trail.
    bits = [caption] if caption else []
    prov = " ".join(x for x in (archive, cat_id) if x)
    if prov:
        bits.append(prov)
    if arc_file and arc_file != cat_id:
        bits.append(f"archive file {arc_file}")
    if pages:
        bits.append(f"Script {pages}")
    description = " - ".join(bits)

    credit = f"Courtesy {archive}" if archive else PRODUCTION

    f = {
        # visible in Lightroom web
        "XMP-dc:Title":              cat_id,
        "IPTC:ObjectName":           cat_id,
        "XMP-dc:Description":        description,
        "IPTC:Caption-Abstract":     description,
        "EXIF:ImageDescription":     description,
        "XMP-dc:Creator":            archive,
        "IPTC:By-line":              archive,
        "XMP-dc:Rights":             f"{credit}. {USAGE_TERMS}",
        "IPTC:CopyrightNotice":      f"{credit}. {USAGE_TERMS}",
        # embedded for the record (not shown in LR web)
        "XMP-photoshop:Credit":      credit,
        "XMP-photoshop:Source":      archive,
        "IPTC:Source":               archive,
        "XMP-photoshop:Headline":    caption,
        "XMP-dc:Identifier":         cat_id,
        "XMP-photoshop:TransmissionReference": arc_file or cat_id,
        "IPTC:OriginalTransmissionReference":  arc_file or cat_id,
        "XMP-xmpRights:UsageTerms":  USAGE_TERMS,
        "XMP-xmpRights:Marked":      "True",
        "XMP-photoshop:Instructions": f"Script {pages}" if pages else "",
    }
    if url:
        f["XMP-xmpRights:WebStatement"] = url
    year = extract_year(caption, cat_id)
    if year:
        # XMP tolerates a bare year; EXIF does not, so it is left alone.
        f["XMP-photoshop:DateCreated"] = year
    return {k: v for k, v in f.items() if v}, keywords


# --- exiftool ----------------------------------------------------------------
def exiftool_available():
    try:
        subprocess.run(["exiftool", "-ver"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def write_metadata(path, fields, keywords, backup=True):
    """Embed fields + keywords into one file. Returns (ok, message)."""
    args = ["exiftool", "-charset", "iptc=UTF8", "-codedcharacterset=utf8"]
    if not backup:
        args.append("-overwrite_original")
    for k, v in fields.items():
        args.append(f"-{k}={v}")
    # clear then re-add so repeat runs stay idempotent
    args += ["-XMP-dc:Subject=", "-IPTC:Keywords="]
    for kw in keywords:
        args.append(f"-XMP-dc:Subject={kw}")
        args.append(f"-IPTC:Keywords={kw}")
    args.append(str(path))
    r = subprocess.run(args, capture_output=True, text=True)
    ok = r.returncode == 0
    return ok, (r.stdout or r.stderr).strip()


def read_metadata(path, tags=None):
    args = ["exiftool", "-j", "-charset", "iptc=UTF8"]
    if tags:
        args += [f"-{t}" for t in tags]
    args.append(str(path))
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    import json
    try:
        return json.loads(r.stdout)[0]
    except (ValueError, IndexError):
        return {}


# --- Matching ----------------------------------------------------------------
def index_files(folder):
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")
    return [p for p in sorted(folder.rglob("*")) if p.suffix in TIF_EXT]


MIN_ID = 4  # shorter than this, a token is too generic to trust as a substring


def match_files(rows, files):
    """Match manifest rows to files on disk by catalog ID token.

    Exact normalized matches are claimed first, then substring matches in
    either direction -- a catalog ID buried in a longer filename
    (pho033930 -> pho033930-002) or a filename that is the tail of a longer
    ID (3c37464 -> master-pnp-cph-...-3c37464u). Both sides must be at least
    MIN_ID characters for a substring match: without that floor a file named
    45.tif swallows every catalog ID that happens to contain "45". The exact
    pass still matches short IDs, so 523 -> 523.tif survives.

    Each file is claimed by at most one row, so a single file can no longer
    stand in as evidence for twenty of them.

    Returns (matches, unmatched_rows, unmatched_files).
    """
    by_norm = [(norm_file(p.stem), p) for p in files]
    matched = {}
    used = set()

    def claim(i, cid, exact):
        for n, path in by_norm:
            if path in used or not n:
                continue
            if exact:
                hit = n == cid
            else:
                hit = (len(cid) >= MIN_ID and len(n) >= MIN_ID
                       and (cid in n or n in cid))
            if hit:
                matched[i] = path
                used.add(path)
                return

    for exact in (True, False):
        for i, row in enumerate(rows):
            if i in matched:
                continue
            cid = norm_file(row.get("catalog_id"))
            if cid:
                claim(i, cid, exact)

    matches = [(rows[i], matched[i]) for i in range(len(rows)) if i in matched]
    unmatched_rows = [rows[i] for i in range(len(rows)) if i not in matched]
    return matches, unmatched_rows, [p for p in files if p not in used]


# --- Filename provenance -----------------------------------------------------
ARCHIVE_ABBREV = {
    "unlv special collections": "UNLV",
    "unlv special collections (not digitized)": "UNLV",
    "utah historical society": "UTHS",
    "nevada historical society": "NVHS",
    "library of congress": "LOC",
    "new york public library": "NYPL",
    "san francisco public library": "SFPL",
    "usc digital library": "USC",
    "huntington library": "HUNT",
    "wikimedia commons": "WIKI",
    "town of tonopah": "TONOPAH",
    "alamy": "ALAMY",
}


def archive_code(archive):
    """Short, stable code for an archive -- used as a filename prefix."""
    a = (archive or "").strip()
    if not a:
        return "UNKNOWN"
    hit = ARCHIVE_ABBREV.get(a.lower())
    if hit:
        return hit
    words = [w for w in re.split(r"[^A-Za-z0-9]+", a) if w]
    if len(words) == 1:
        return words[0][:8].upper()
    return "".join(w[0] for w in words if w[0].isupper() or w[0].isalpha())[:6].upper()


def slug(s, maxlen=48):
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:maxlen].strip("-")


def target_name(row, ext=".tif"):
    """The catalog ID and nothing else.

    Production convention: Catalog ID == Image ID == filename == Lightroom
    Title. One value in all four places, so a file can never drift from its
    record. The archive is carried in the embedded metadata, not the filename.
    """
    cid = (row.get("catalog_id") or "").strip()
    if not cid:
        cid = row.get("image_id") or "UNKNOWN"
    return slug_filename(cid) + ext


def slug_filename(s):
    """Make a catalog ID safe as a filename without disguising it."""
    s = (s or "").strip()
    for bad, good in (("/", "-"), ("\\", "-"), (":", "-"), ("*", ""), ("?", ""),
                      ('"', ""), ("<", ""), (">", ""), ("|", "-")):
        s = s.replace(bad, good)
    return re.sub(r"\s+", " ", s).strip()
