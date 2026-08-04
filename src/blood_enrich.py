# -*- coding: utf-8 -*-
"""
blood_enrich.py — Phase 1.5: curated enrichment on top of the facts.

Adds, without ever touching raw_observations:
  panel          authoritative grouping by an ordered keyword classifier
                 (replaces the approximate running-header 'section' from Phase 1)
  evidence_tier  A / B / C / D — see data/evidence_tiers.md
  ucum_canonical canonical UCUM unit, best effort
  loinc_code     DRAFT standard code, with loinc_verified=0 on EVERY row

  MEDICAL SAFETY: LOINC codes here are a seed for verification, never asserted as
  truth. Nothing downstream may treat loinc_verified=0 as a verified mapping.

Also writes a human-editable analyte dictionary CSV: edit the CSV, re-run.
Deterministic, stdlib-only, idempotent. Run AFTER blood_ingest.py.

Usage:
  python src/blood_enrich.py --db out/blood.db
"""
import argparse, csv, json, os, sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PANELS = os.path.join(_HERE, os.pardir, "data", "panels.json")
DEFAULT_SEED = os.path.join(_HERE, os.pardir, "data", "loinc_seed.json")
ENRICH_VERSION = "phase1.5-v2"


def load_rules(panels_path, seed_path):
    with open(panels_path, encoding="utf-8") as f:
        p = json.load(f)
    with open(seed_path, encoding="utf-8") as f:
        s = json.load(f)
    tiers = p["evidence_tiers"]
    return {
        "rules": [(r["panel"], [k.lower() for k in r["keywords"]]) for r in p["rules"]],
        "default_panel": p.get("default_panel", "OTHER"),
        "tier_default": tiers.get("default", "C"),
        "tier_map": [(t, [k.lower() for k in tiers.get(t, [])]) for t in ("A", "B", "D")],
        # LONGEST KEY FIRST. Substring matching means a short key swallows a longer
        # one that contains it: "hdl cholesterol" matches inside "non-hdl cholesterol"
        # and stamps the HDL code onto non-HDL. Caught on real data 2026-08-04 — see
        # docs/DEVLOG.md. Sorting by descending key length makes the class of bug
        # impossible rather than patching this one pair.
        "seed": sorted(((k.lower(), tuple(v)) for k, v in s["seed"].items()),
                       key=lambda kv: -len(kv[0])),
    }


def classify_panel(text, R):
    t = (text or "").lower()
    for panel, kws in R["rules"]:
        if any(k in t for k in kws):
            return panel
    return R["default_panel"]


def evidence_tier(name_en, R):
    t = (name_en or "").lower()
    for tier, kws in R["tier_map"]:
        if any(k in t for k in kws):
            return tier
    return R["tier_default"]


def _norm(s):
    """Lowercase, unify dash variants, collapse whitespace. Nothing else — normalisation
    that changes meaning is how wrong codes get assigned."""
    s = (s or "").lower().replace("–", "-").replace("—", "-")
    return " ".join(s.split())


def seed_lookup(name_en, R):
    """EXACT name match only.

    Substring matching is unsafe for medical identifiers and produced two real defects
    (docs/DEVLOG.md): 'hdl cholesterol' matched inside 'non-hdl cholesterol', and
    'hemoglobin' matched inside 'mean corpuscular hemoglobin' — stamping the code of one
    marker onto a different one. A wrong LOINC code is invisible: it looks exactly like a
    right one. So the rule is: an unmatched analyte gets NO code, and someone adds an
    explicit entry to data/loinc_seed.json. Missing is recoverable; wrong is not.
    """
    t = _norm(name_en)
    if not t:
        return None, None
    for k, (loinc, ucum) in R["seed"]:
        if _norm(k) == t:
            return loinc, ucum
    return None, None


def enrich(db_path, panels_path, seed_path, dict_path):
    R = load_rules(panels_path, seed_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(analytes)")}
    for col in ["panel", "evidence_tier", "ucum_canonical", "loinc_code", "loinc_verified"]:
        if col not in cols:
            cur.execute(f"ALTER TABLE analytes ADD COLUMN {col} TEXT")

    rows = cur.execute("SELECT analyte_key, abbrev, name_en, name_ru FROM analytes").fetchall()
    n_loinc = 0
    dict_rows = []
    for key, abbr, en, ru in rows:
        text = " ".join(x for x in [en, abbr, key, ru] if x)
        panel = classify_panel(text, R)
        tier = evidence_tier(en, R)
        loinc, ucum = seed_lookup(en, R)
        if loinc:
            n_loinc += 1
        cur.execute(
            """UPDATE analytes SET panel=?, evidence_tier=?, ucum_canonical=?,
               loinc_code=?, loinc_verified=? WHERE analyte_key=?""",
            (panel, tier, ucum, loinc, "0" if loinc else None, key))
        if loinc:
            cur.execute(
                "UPDATE observations_canonical SET loinc_code=?, ucum_unit=? WHERE analyte_key=?",
                (loinc, ucum, key))
        dict_rows.append({"analyte_key": key, "abbrev": abbr or "", "name_en": en or "",
                          "name_local": ru or "", "panel": panel, "evidence_tier": tier,
                          "ucum_canonical": ucum or "", "loinc_code": loinc or "",
                          "loinc_verified": "0" if loinc else ""})
    cur.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('loinc_disclaimer',?)",
                ("DRAFT seed codes; loinc_verified=0 on all. Verify at loinc.org and with a "
                 "clinician before ANY clinical use. Panels and tiers are authoritative.",))
    cur.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('enrich_version',?)", (ENRICH_VERSION,))
    con.commit()

    with open(dict_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["analyte_key", "abbrev", "name_en", "name_local",
                                          "panel", "evidence_tier", "ucum_canonical",
                                          "loinc_code", "loinc_verified"])
        w.writeheader()
        for r in sorted(dict_rows, key=lambda x: (x["panel"], x["name_en"])):
            w.writerow(r)

    print("=== enrichment summary ===")
    print(f"analytes enriched: {len(rows)} | LOINC seeded (DRAFT, unverified): {n_loinc}")
    print("panel distribution:")
    for r in cur.execute("SELECT panel, COUNT(*) FROM analytes GROUP BY panel ORDER BY 2 DESC"):
        print(f"   {r[0]:16} {r[1]}")
    print("evidence_tier distribution:")
    for r in cur.execute(
            "SELECT evidence_tier, COUNT(*) FROM analytes GROUP BY evidence_tier ORDER BY 1"):
        print(f"   tier {r[0]:2} {r[1]}")
    print(f"dictionary: {os.path.abspath(dict_path)}")
    con.close()
    return len(rows), n_loinc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--panels", default=DEFAULT_PANELS)
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--dict-out", default=None)
    a = ap.parse_args()
    out = a.dict_out or os.path.join(os.path.dirname(os.path.abspath(a.db)),
                                     "analyte_dictionary.csv")
    enrich(a.db, a.panels, a.seed, out)
