# -*- coding: utf-8 -*-
"""
blood_ingest.py — Phase 1: turn a wide lab comparison sheet into a fact database.

Reads a FROZEN CSV snapshot of a "one row per analyte, one column block per draw"
comparison sheet and builds a SQLite database as the fact layer.

Design:
  raw_observations       lossless long-format unpivot, every cell VERBATIM
  observations_canonical best-effort parse (value/comparator/ref/flags/qc)
  analytes               one row per analyte
  meta                   provenance (source id, snapshot uri, versions, counts)

Rule: "map once, never discard the original." Canonical NEVER overwrites raw.
If the parser is wrong, you fix the parser and rebuild — the source of truth is
untouched.

Deterministic, stdlib-only, 0 network calls. Idempotent: full rebuild from the
immutable snapshot produces the same database every time.

Usage:
  python src/blood_ingest.py --csv examples/synthetic-panel.csv \
      --sheet-id demo --title "Synthetic demo" --db out/blood.db
"""
import argparse, csv, datetime, json, os, re, sqlite3

MAPPING_VERSION = "phase1-v2"
SCRIPT_VERSION = "2026-08-04"

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LAYOUT = os.path.join(_HERE, os.pardir, "config", "sheet_layout.json")


def load_layout(path):
    """Sheet geometry lives in a JSON file, not in the code — a different lab
    export means editing config/sheet_layout.json, not patching Python."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cols, rows = cfg["columns"], cfg["rows"]
    return {
        "COL_KEY": cols["key"], "COL_RU": cols["name_ru"], "COL_EN": cols["name_en"],
        "COL_PT": cols.get("name_pt", -1), "COL_ABBR": cols["abbrev"],
        "COL_INTERP": cols.get("interpretation", -1),
        "HEADER_LABEL_ROW": rows["header_label"], "DATE_ROW": rows["date"],
        "FIRST_DATA_ROW": rows["first_data"],
        "SECTION_WORDS": set(cfg.get("section_words", [])),
        "NOISE_KEYS": set(k.lower() for k in cfg.get("noise_keys", [])),
        "NONNUMERIC_WORDS": tuple(cfg.get("nonnumeric_words", [])),
        "DERIVED_WORDS": tuple(cfg.get("derived_words", [])),
        "REF_HEADER_WORDS": tuple(cfg.get("reference_header_words", ["норм", "referen", "range"])),
    }


AGE_RANGE_RE = re.compile(r"^\d{1,3}\s*[-–]\s*\d{1,3}$")
NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
# scientific-scale notation is UNIT text, not a value: "× 10⁹/л", "x10^3/uL", "10^12/L"
SCALE_RE = re.compile(r"[×xX]?\s*10\s*(?:\^|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)\d*")


def parse_date(raw):
    """'5.11.2016' / '05.10.2021' (D.M.YYYY) -> ISO 'YYYY-MM-DD', else None."""
    raw = (raw or "").strip()
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", raw)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return None


def _cell(row, i):
    if i is None or i < 0 or i >= len(row):
        return ""
    return (row[i] or "").strip()


def find_draws(rows, L):
    """Each draw is a column block starting at a date cell: result [, unit [, reference]]."""
    date_cells = []
    for c, v in enumerate(rows[L["DATE_ROW"]]):
        iso = parse_date(v)
        if iso:
            date_cells.append((c, v.strip(), iso))
    draws = []
    for i, (c, raw, iso) in enumerate(date_cells):
        next_c = date_cells[i + 1][0] if i + 1 < len(date_cells) else len(rows[L["DATE_ROW"]])
        block = list(range(c, next_c))
        unit_col = c + 1 if (c + 1) in block else None
        norm_col = None
        if (c + 2) in block:
            hdr = _cell(rows[L["HEADER_LABEL_ROW"]], c + 2).lower()
            if any(w in hdr for w in L["REF_HEADER_WORDS"]):
                norm_col = c + 2
        draws.append({"result": c, "unit": unit_col, "norm": norm_col,
                      "date_raw": raw, "date_iso": iso})
    return draws


def is_header_label(row, L):
    """A row with no measurements is a SECTION header iff it is a known category word,
    or a bare ALL-CAPS category. A REAL analyte (even one with no data in this snapshot)
    carries an English name or an abbreviation; a bare panel header carries neither —
    that is the distinguishing signal."""
    key = _cell(row, L["COL_KEY"])
    en = _cell(row, L["COL_EN"])
    if key in L["SECTION_WORDS"] or en in L["SECTION_WORDS"]:
        return True
    txt = key or _cell(row, L["COL_RU"])
    if not txt:
        return False
    if en or _cell(row, L["COL_ABBR"]):
        return False
    letters = [ch for ch in txt if ch.isalpha()]
    return bool(letters) and txt == txt.upper()


def _to_float(tok):
    return float(tok.replace(",", "."))


def parse_value(raw_result, raw_unit, L):
    """Best-effort canonical parse. NEVER raises; qc_flag documents any ambiguity."""
    r = (raw_result or "").strip()
    out = {"comparator": None, "value_number": None,
           "unit_clean": (raw_unit or "").strip() or None,
           "flag_asterisk": 0, "qc_flag": "ok"}
    if not r:
        out["qc_flag"] = "empty"
        return out
    if "*" in r:  # asterisk = lab out-of-range marker
        out["flag_asterisk"] = 1
        r = r.replace("*", " ").strip()
    low = r.lower()
    if any(w in low for w in L["NONNUMERIC_WORDS"]) and not NUM_RE.search(r):
        out["qc_flag"] = "nonnumeric"
        return out
    derived = any(w in low for w in L["DERIVED_WORDS"])
    mcomp = re.match(r"^\s*(<=|>=|≤|≥|<|>)", r)
    if mcomp:
        out["comparator"] = mcomp.group(1)
    # strip scientific-scale tokens so "6.2 ×10⁹/л" yields ONE value, not two
    nums = NUM_RE.findall(SCALE_RE.sub(" ", r))
    if not nums:
        out["qc_flag"] = "nonnumeric"
        return out
    out["value_number"] = _to_float(nums[0])
    if not raw_unit:  # unit embedded in the result cell, e.g. "302 mg/dL"
        um = re.search(r"[A-Za-zµμ%]+/?[A-Za-zµμ%0-9^]*", re.sub(NUM_RE, " ", r))
        if um and um.group(0).strip():
            out["unit_clean"] = um.group(0).strip()
            if out["qc_flag"] == "ok":
                out["qc_flag"] = "embedded_unit"
    if derived:
        out["qc_flag"] = "derived"
    elif len(nums) > 1 and out["qc_flag"] == "ok":
        out["qc_flag"] = "multi_value"
    elif re.match(r"^0\d\.\d", (raw_result or "").strip()) and out["qc_flag"] == "ok":
        out["qc_flag"] = "leading_zero_suspect"  # "01.05" possibly a mangled 1.05
    return out


# Reference ranges must NOT use the signed number regex: in "3.9-5.5" the hyphen is a
# RANGE SEPARATOR, but a signed pattern reads it as the sign of -5.5, so min/max returns
# (-5.5, 3.9) — an inverted range with a negative floor, silently, on every two-sided
# reference. Caught by tests/test_pipeline.py on 2026-08-04. Lab reference bounds are
# non-negative, so the unsigned pattern is the correct tool here.
REF_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def parse_ref(raw_ref):
    """'3.0-5.4' / '<5.5' / '>0.9' -> (low, high, raw)."""
    r = (raw_ref or "").strip()
    if not r:
        return (None, None, None)
    nums = [_to_float(x) for x in REF_NUM_RE.findall(r)]
    low = high = None
    if re.search(r"(<=|<|≤)", r) and nums:
        high = nums[0]
    elif re.search(r"(>=|>|≥)", r) and nums:
        low = nums[0]
    elif len(nums) >= 2:
        low, high = min(nums[0], nums[1]), max(nums[0], nums[1])
    elif len(nums) == 1:
        high = nums[0]  # a single bare bound is ambiguous; ref_raw keeps the original
    return (low, high, r)


SCHEMA = """
DROP TABLE IF EXISTS raw_observations;
DROP TABLE IF EXISTS observations_canonical;
DROP TABLE IF EXISTS analytes;
DROP TABLE IF EXISTS meta;
CREATE TABLE raw_observations(
    id INTEGER PRIMARY KEY,
    source_sheet_id TEXT, snapshot_uri TEXT, source_row INTEGER,
    section TEXT, analyte_key TEXT,
    name_ru TEXT, name_en TEXT, name_pt TEXT, abbrev TEXT,
    draw_date_raw TEXT, draw_date_iso TEXT,
    raw_result TEXT, raw_unit TEXT, raw_ref TEXT
);
CREATE TABLE observations_canonical(
    id INTEGER PRIMARY KEY, raw_id INTEGER,
    analyte_key TEXT, abbrev TEXT, name_en TEXT,
    draw_date_iso TEXT,
    comparator TEXT, value_number REAL, value_text TEXT,
    unit_raw TEXT, unit_clean TEXT,
    ref_low REAL, ref_high REAL, ref_raw TEXT,
    flag_asterisk INTEGER, qc_flag TEXT,
    loinc_code TEXT, ucum_unit TEXT,
    FOREIGN KEY(raw_id) REFERENCES raw_observations(id)
);
CREATE TABLE analytes(
    analyte_key TEXT PRIMARY KEY, abbrev TEXT,
    name_ru TEXT, name_en TEXT, name_pt TEXT, section TEXT,
    interpretation TEXT, n_observations INTEGER, loinc_code TEXT
);
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
"""


def build(csv_path, sheet_id, title, db_path, layout_path):
    L = load_layout(layout_path)
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    draws = find_draws(rows, L)
    snapshot_uri = os.path.abspath(csv_path)

    parent = os.path.dirname(os.path.abspath(db_path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    section = None
    analyte_counts, analyte_rows = {}, {}
    n_raw = n_skipped_labels = 0
    for ri in range(L["FIRST_DATA_ROW"], len(rows)):
        row = rows[ri]
        if not any((c or "").strip() for c in row):
            continue
        key = _cell(row, L["COL_KEY"])
        abbr = _cell(row, L["COL_ABBR"])
        measured = [d for d in draws if _cell(row, d["result"])]
        if not measured:
            if is_header_label(row, L):
                section = key or _cell(row, L["COL_RU"])
            else:
                n_skipped_labels += 1
            continue
        if not (key or abbr):
            continue
        if key.strip().lower() in L["NOISE_KEYS"] or AGE_RANGE_RE.match(key.strip()):
            n_skipped_labels += 1  # reference/comment sub-row, not an analyte
            continue
        name_ru = _cell(row, L["COL_RU"])
        name_en = _cell(row, L["COL_EN"])
        name_pt = _cell(row, L["COL_PT"])
        interp = _cell(row, L["COL_INTERP"])
        if key not in analyte_rows:
            analyte_rows[key] = (abbr, name_ru, name_en, name_pt, section, interp)
            analyte_counts.setdefault(key, 0)
        for d in measured:
            raw_result = _cell(row, d["result"])
            raw_unit = _cell(row, d["unit"])
            raw_ref = _cell(row, d["norm"])
            n_raw += 1
            cur.execute(
                """INSERT INTO raw_observations
                   (id, source_sheet_id, snapshot_uri, source_row, section, analyte_key,
                    name_ru, name_en, name_pt, abbrev, draw_date_raw, draw_date_iso,
                    raw_result, raw_unit, raw_ref)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (n_raw, sheet_id, snapshot_uri, ri, section, key,
                 name_ru, name_en, name_pt, abbr, d["date_raw"], d["date_iso"],
                 raw_result, raw_unit, raw_ref))
            pv = parse_value(raw_result, raw_unit, L)
            rl, rh, rraw = parse_ref(raw_ref)
            cur.execute(
                """INSERT INTO observations_canonical
                   (id, raw_id, analyte_key, abbrev, name_en, draw_date_iso,
                    comparator, value_number, value_text, unit_raw, unit_clean,
                    ref_low, ref_high, ref_raw, flag_asterisk, qc_flag, loinc_code, ucum_unit)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (n_raw, n_raw, key, abbr, name_en, d["date_iso"],
                 pv["comparator"], pv["value_number"], raw_result, raw_unit, pv["unit_clean"],
                 rl, rh, rraw, pv["flag_asterisk"], pv["qc_flag"], None, None))
            analyte_counts[key] = analyte_counts.get(key, 0) + 1

    for key, (abbr, ru, en, pt, sec, interp) in analyte_rows.items():
        cur.execute(
            """INSERT INTO analytes
               (analyte_key, abbrev, name_ru, name_en, name_pt, section,
                interpretation, n_observations, loinc_code)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (key, abbr, ru, en, pt, sec, interp, analyte_counts.get(key, 0), None))

    now = datetime.datetime.now().isoformat(timespec="seconds")
    for k, v in [
        ("source_sheet_id", sheet_id), ("source_title", title),
        ("snapshot_uri", snapshot_uri),
        ("mapping_version", MAPPING_VERSION), ("script_version", SCRIPT_VERSION),
        ("ingested_at", now), ("n_draws", str(len(draws))),
        ("n_analytes", str(len(analyte_rows))), ("n_raw_observations", str(n_raw)),
        ("n_skipped_labels", str(n_skipped_labels)),
        ("section_reliability",
         "APPROXIMATE: running ALL-CAPS-header grouping. Authoritative grouping comes "
         "from blood_enrich.py (panel classifier). Values, dates and units are "
         "unaffected and verbatim."),
    ]:
        cur.execute("INSERT OR REPLACE INTO meta(k, v) VALUES (?,?)", (k, v))
    con.commit()

    # ---- visibility layer: a silent success is indistinguishable from a silent failure ----
    print("=== build summary ===")
    print(f"db: {os.path.abspath(db_path)}")
    print(f"snapshot: {snapshot_uri}")
    print(f"draws: {len(draws)} -> {[d['date_iso'] for d in draws]}")
    print(f"analytes: {len(analyte_rows)} | raw_observations: {n_raw} "
          f"| skipped label/header rows: {n_skipped_labels}")
    print("qc_flag breakdown:")
    for flag, n in cur.execute(
            "SELECT qc_flag, COUNT(*) FROM observations_canonical GROUP BY qc_flag ORDER BY 2 DESC"):
        print(f"   {flag:22} {n}")
    nclean = cur.execute(
        "SELECT COUNT(*) FROM observations_canonical WHERE value_number IS NOT NULL").fetchone()[0]
    print(f"numeric value extracted: {nclean}/{n_raw}")
    con.close()
    return n_raw, len(analyte_rows), len(draws)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--db", required=True)
    ap.add_argument("--layout", default=DEFAULT_LAYOUT)
    a = ap.parse_args()
    build(a.csv, a.sheet_id, a.title, a.db, a.layout)
