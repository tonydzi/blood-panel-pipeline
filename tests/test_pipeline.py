# -*- coding: utf-8 -*-
"""Regression tests. stdlib only: python tests/test_pipeline.py

Every test here exists because something actually broke. A test that has never
been red is not a test.
"""
import os, sqlite3, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import blood_enrich  # noqa: E402
import blood_ingest  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def main():
    layout = os.path.join(ROOT, "config", "sheet_layout.json")
    panels = os.path.join(ROOT, "data", "panels.json")
    seed = os.path.join(ROOT, "data", "loinc_seed.json")
    csv_path = os.path.join(ROOT, "examples", "synthetic-panel.csv")
    tmp = tempfile.mkdtemp(prefix="bpp-test-")
    db = os.path.join(tmp, "t.db")
    dic = os.path.join(tmp, "dict.csv")

    print("== end-to-end on the synthetic example ==")
    n_raw, n_analytes, n_draws = blood_ingest.build(csv_path, "test", "t", db, layout)
    check("3 draws detected", n_draws == 3, f"got {n_draws}")
    check("observations ingested", n_raw > 40, f"got {n_raw}")
    check("analytes ingested", n_analytes > 15, f"got {n_analytes}")
    blood_enrich.enrich(db, panels, seed, dic)

    con = sqlite3.connect(db)
    cur = con.cursor()

    print("== the LOINC substring bug (caught on real data 2026-08-04) ==")
    # "hdl cholesterol" is a substring of "non-hdl cholesterol": a naive first-hit
    # scan stamps the HDL code onto non-HDL. Longest-key-first must prevent it.
    non_hdl = cur.execute(
        "SELECT loinc_code FROM analytes WHERE lower(name_en) LIKE 'non-hdl%'").fetchone()
    hdl = cur.execute(
        "SELECT loinc_code FROM analytes WHERE lower(name_en)='hdl cholesterol'").fetchone()
    check("non-HDL does not steal the HDL code",
          not (non_hdl and hdl and non_hdl[0] and non_hdl[0] == hdl[0]),
          f"non-HDL={non_hdl and non_hdl[0]} HDL={hdl and hdl[0]}")
    check("non-HDL carries its own code", non_hdl and non_hdl[0] == "43396-1",
          f"got {non_hdl and non_hdl[0]}")

    print("== LOINC exact-match: a code may never leak onto a different marker ==")
    R = blood_enrich.load_rules(panels, seed)
    hgb = blood_enrich.seed_lookup("Hemoglobin", R)[0]
    for impostor in ("Mean Corpuscular Hemoglobin",
                     "Mean Corpuscular Hemoglobin Concentration",
                     "Reticulocyte Hemoglobin Content"):
        got = blood_enrich.seed_lookup(impostor, R)[0]
        check(f"'{impostor}' does not inherit the Hemoglobin code",
              got != hgb, f"got {got}, hemoglobin is {hgb}")
    tst = blood_enrich.seed_lookup("Testosterone", R)[0]
    for impostor in ("Free Testosterone", "Dihydrotestosterone (Serum)"):
        check(f"'{impostor}' does not inherit the Testosterone code",
              blood_enrich.seed_lookup(impostor, R)[0] != tst)
    check("Red Blood Cells (Urine) does not inherit the blood RBC code",
          blood_enrich.seed_lookup("Red Blood Cells (Urine)", R)[0]
          != blood_enrich.seed_lookup("Red Blood Cells", R)[0])
    check("an exact name still resolves", hgb == "718-7", f"got {hgb}")
    check("dash variants normalise", blood_enrich.seed_lookup("Glucose – Fasting", R)[0]
          == blood_enrich.seed_lookup("glucose - fasting", R)[0])

    print("== shipped dictionary carries no wrong codes ==")
    import csv as _csv
    tmpl = os.path.join(ROOT, "data", "analyte_dictionary.template.csv")
    with open(tmpl, encoding="utf-8") as f:
        bad = [r["name_en"] for r in _csv.DictReader(f)
               if r["loinc_code"] and blood_enrich.seed_lookup(r["name_en"], R)[0] != r["loinc_code"]]
    check("every code in the template is reproducible from the seed", not bad, str(bad[:3]))

    print("== medical safety ==")
    unverified = cur.execute(
        "SELECT COUNT(*) FROM analytes WHERE loinc_code IS NOT NULL AND loinc_verified<>'0'"
    ).fetchone()[0]
    check("every seeded LOINC is marked unverified", unverified == 0, f"{unverified} unmarked")

    print("== panel classifier ordering ==")
    crp = cur.execute(
        "SELECT panel FROM analytes WHERE lower(name_en) LIKE 'c-reactive%'").fetchone()
    check("C-Reactive PROTEIN lands in INFLAMMATION, not PROTEINS",
          crp and crp[0] == "INFLAMMATION", f"got {crp and crp[0]}")

    print("== parser edge cases ==")
    L = blood_ingest.load_layout(layout)
    v = blood_ingest.parse_value("6.0 ×10⁹/л", "", L)
    check("scientific scale is a unit, not a second value", v["value_number"] == 6.0,
          f"got {v['value_number']}")
    v = blood_ingest.parse_value("6.0*", "mmol/L", L)
    check("asterisk flagged as out-of-range", v["flag_asterisk"] == 1)
    v = blood_ingest.parse_value("расчет 2.5", "mmol/L", L)
    check("calculated values flagged derived", v["qc_flag"] == "derived", v["qc_flag"])
    v = blood_ingest.parse_value("нет", "", L)
    check("non-numeric result kept, not crashed", v["qc_flag"] == "nonnumeric")
    lo, hi, _ = blood_ingest.parse_ref("<5.2")
    check("'<5.2' parses as an upper bound", hi == 5.2 and lo is None)
    lo, hi, _ = blood_ingest.parse_ref("3.9-5.5")
    check("'3.9-5.5' parses as a range, hyphen is not a minus sign",
          (lo, hi) == (3.9, 5.5), f"got ({lo}, {hi})")
    lo, hi, _ = blood_ingest.parse_ref("62-106")
    check("integer range not inverted", (lo, hi) == (62.0, 106.0), f"got ({lo}, {hi})")
    lo, hi, _ = blood_ingest.parse_ref("130 – 170")
    check("en-dash range parses", (lo, hi) == (130.0, 170.0), f"got ({lo}, {hi})")
    bad = [r for r in (blood_ingest.parse_ref(x) for x in ("3.9-5.5", "62-106", "0.4-4.0"))
           if r[0] is not None and r[0] < 0]
    check("no reference range has a negative floor", not bad, str(bad))

    print("== raw layer is lossless ==")
    n_raw_db = cur.execute("SELECT COUNT(*) FROM raw_observations").fetchone()[0]
    n_can = cur.execute("SELECT COUNT(*) FROM observations_canonical").fetchone()[0]
    check("one canonical row per raw row", n_raw_db == n_can, f"{n_raw_db} vs {n_can}")
    nulls = cur.execute(
        "SELECT COUNT(*) FROM raw_observations WHERE raw_result IS NULL OR raw_result=''"
    ).fetchone()[0]
    check("no empty raw results stored", nulls == 0, f"{nulls} empty")

    print("== noise rows rejected ==")
    noise = cur.execute(
        "SELECT COUNT(*) FROM analytes WHERE lower(analyte_key) IN ('комментарий','comment')"
    ).fetchone()[0]
    check("comment sub-rows are not analytes", noise == 0, f"{noise} leaked")
    con.close()

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} -> {FAILS}")
        return 1
    print("ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
