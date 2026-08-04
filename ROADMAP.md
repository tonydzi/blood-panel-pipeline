# Roadmap

What exists, and what does not. Stated plainly so nobody has to guess.

## Phase 1 — ingestion ✅ shipped

Wide lab sheet → `raw_observations` + `observations_canonical` + `analytes` + `meta`.
Lossless raw layer, QC flags, provenance. This is what you can run today.

## Phase 1.5 — curation ✅ shipped

Panel classifier, evidence tiers, canonical UCUM units, draft LOINC seeding with
`loinc_verified=0`, human-editable analyte dictionary.

## Phase 2 — rule engine ⬜ designed, not built

Deterministic derived measurements with recorded provenance: which formula, which version,
which inputs. Candidates: non-HDL, remnant cholesterol, eGFR, TyG index, ratios that labs
report inconsistently or not at all.

The rule: a derived value is a first-class row that names its formula, never a number
quietly overwritten into a measured field.

## Phase 3 — constrained explanation ⬜ designed, not built

A language model that may *describe* what the rules found, and may not decide anything.
It never computes a value, never fires an alert, never sees a row the rules did not
already classify. If the model is removed, every fact and every alert must survive
unchanged — that is the test of whether the boundary is real.

## Phase 4 — tiered alerting ⬜ designed, not built

Silent by default. An alert requires at least two of three independent gates:

1. absolute threshold breached
2. within-person shift large relative to that person's own variance
3. persistence across draws, not a single reading

**No alerting ships before it is backtested against a full history.** An alert rule that
has never been run against the past is a guess wearing a uniform.

## Not planned, not started

- **Wearable connectors.** No Apple Health, no Whoop, no Oura, no Garmin. Continuous
  streams are a different data model with different failure modes; pretending otherwise
  would be the fastest way to make this repo dishonest.
- **PDF and image OCR** of lab reports.
- **FHIR export.** The canonical schema was designed with FHIR `Observation` in mind, but
  no exporter exists.
- **A hosted anything.** Local-first is a design decision, not a missing feature.

## Where help is most useful

1. **A lab export that breaks the parser.** Different country, different lab, different
   layout — that is the contribution with the highest value per minute. Open an issue with
   the sheet geometry (never with real values).
2. **LOINC verification.** Every seeded code is `loinc_verified=0`. Turning any of them
   into verified mappings, with the source, is durable work.
3. **Tier arguments with citations.** Disagreeing with a placement in
   `data/evidence_tiers.md` is welcome when it comes with a reference.
