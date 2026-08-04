-- blood-panel-pipeline schema (SQLite).
-- Generated from the live database; blood_ingest.py is the authority.
--
-- Design: raw_observations is written once and never rewritten. observations_canonical
-- is a parsed twin, one row per raw row, rebuilt on every run. If the parser is wrong,
-- fix the parser and rebuild -- the source of truth is untouched.

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
, panel TEXT, evidence_tier TEXT, ucum_canonical TEXT, loinc_verified TEXT);

CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
