# blood-panel-pipeline

Turn a decade of raw lab panels into a queryable, provenance-tracked record.

Deterministic rules decide what is mechanically true. A language model, if you add one
later, only explains what it may mean. That boundary is the whole point of this repo.

Stdlib-only Python. No dependencies, no network calls, no account. Clone it and run it.

```
git clone https://github.com/tonydzi/blood-panel-pipeline
cd blood-panel-pipeline
python src/blood_ingest.py --csv examples/synthetic-panel.csv --sheet-id demo --db out/blood.db
python src/blood_enrich.py --db out/blood.db
python tests/test_pipeline.py
```

The example data is synthetic. Point `--csv` at your own export and edit
`config/sheet_layout.json` to match its geometry.

## What it is, and what it is not

This is a **doctor-prep and self-quantification evidence engine**. It takes the lab
results you already have, keeps them verbatim, parses them into facts you can query, and
records where every number came from.

It is **not** a physician and does not pretend to be one. Explicitly out of scope:

- no diagnoses, no treatment suggestions, no drug or supplement advice
- no single "health score" — a number that compresses a body into one digit hides more
  than it shows
- no alerts that have not been backtested against your own history
- no upload of your data anywhere; the pipeline is local and offline by construction

**This is not medical advice.** Bring the output to a clinician; do not substitute it for
one.

## The four planes

```
  raw          immutable, verbatim, lossless      never rewritten
  canonical    parsed values, units, ranges, QC   rebuilt on every run
  rules        deterministic, testable, boring    decide what is TRUE
  model        explanation and language           decides NOTHING
```

The rule the design hangs on: **map once, never discard the original.** Canonical rows
never overwrite raw rows. When the parser turns out to be wrong — and it will — you fix
the parser and rebuild. The source of truth is untouched, so a parser bug is never a data
loss event.

The model plane is deliberately empty in this release. Nothing here calls an LLM. If you
wire one in, it must sit above the rules, never inside them.

## Schema

Four tables, defined in [`schema/schema.sql`](schema/schema.sql):

| table | what it holds |
|---|---|
| `raw_observations` | one row per cell, exactly as the lab wrote it, with source row and snapshot URI |
| `observations_canonical` | parsed twin of each raw row: value, comparator, unit, reference bounds, QC flag |
| `analytes` | one row per marker: names, panel, evidence tier, UCUM unit, draft LOINC |
| `meta` | provenance — source id, snapshot URI, mapping version, script version, counts |

Every canonical row keeps a `qc_flag` instead of silently dropping what it could not
parse: `ok`, `empty`, `nonnumeric`, `derived`, `multi_value`, `embedded_unit`,
`leading_zero_suspect`. A row the parser did not understand is still a row.

## Curation that ships with it

- **[`data/panels.json`](data/panels.json)** — a 16-panel classifier with bilingual
  (English + Russian) keywords. Ordered, first hit wins. Add your own language by
  appending keywords.
- **[`data/evidence_tiers.md`](data/evidence_tiers.md)** — A/B/C/D grading, and why a
  marker sits where it does.
- **[`data/loinc_seed.json`](data/loinc_seed.json)** — draft LOINC codes and canonical
  UCUM units. **Every code this produces is stamped `loinc_verified=0`.** They are a
  scaffold to speed up verification, never asserted as truth. Verify at loinc.org and
  with a clinician before any clinical use.
- **[`data/analyte_dictionary.template.csv`](data/analyte_dictionary.template.csv)** —
  161 real-world analytes already classified, as a starting point. Names and codes only;
  it contains no measurements.

The dictionary is a CSV on purpose. Editing a spreadsheet and re-running beats patching
Python, and it means the person maintaining the mapping does not have to be the person
who wrote the parser.

## Why this exists

Everybody who tracks their own labs writes this parser, once, badly, and never publishes
it. So the same problems get solved again every time: a hyphen that is a range separator
and not a minus sign, a `×10⁹/л` that is a unit and not a second number, a comment
sub-row that looks exactly like an analyte, a "C-Reactive **Protein**" that a naive rule
files under proteins.

Both of the bugs in [`docs/DEVLOG.md`](docs/DEVLOG.md) shipped to production before tests
caught them. They are documented for the same reason the failure modes are: work you
cannot check is not a result.

## Provenance and roadmap

Built at [Palo Alto AI Lab](https://palo-alto.ai/) on top of ten years of one person's
lab panels — 622 observations, 158 analytes, 10 draws, 2016 to 2025. **None of that data
is in this repository, and none of it ever will be.** What is here is the machinery and
the mapping.

What does **not** exist yet, stated plainly: there are **no wearable connectors** — no
Apple Health, no Whoop, no Oura, no Garmin. There is no rule engine, no alerting, no
report generation. See [`ROADMAP.md`](ROADMAP.md) for what is designed but unbuilt.
Contributions and counter-examples welcome — especially a lab export whose layout breaks
the parser.

MIT licensed. Author: Anton Dziatkovskii ([ORCID 0000-0001-7408-3054](https://orcid.org/0000-0001-7408-3054)).
