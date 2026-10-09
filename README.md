# blood-panel-pipeline

Turn a decade of raw lab panels into a queryable, provenance-tracked record with [src/blood_ingest.py](src/blood_ingest.py).

Deterministic rules in [src/blood_ingest.py](src/blood_ingest.py) decide what is mechanically true. A language model, if you add one
later, only explains what it may mean. That boundary is the whole point of this repo.

Stdlib-only Python. No dependencies, no network calls, no account. Clone it and run it.

```
git clone https://github.com/tonydzi/blood-panel-pipeline
cd blood-panel-pipeline
python src/blood_ingest.py --csv examples/synthetic-panel.csv --sheet-id demo --db out/blood.db
python src/blood_enrich.py --db out/blood.db
python tests/test_pipeline.py
python tests/reproduce_miscoding.py
```

The second script re-derives the LOINC miscoding result in [`docs/DEVLOG.md`](docs/DEVLOG.md)
from the two shipped mapping files: 52 codes assigned by substring matching, 12 of them
wrong, and the longest-first "fix" changing exactly one row of 158. It uses no data and
no database -- the defect lives entirely in the public mapping, so the public mapping is
enough to check the claim. [tests/reproduce_miscoding.py](tests/reproduce_miscoding.py) exits non-zero if the published figures no longer reproduce.

The example data is synthetic. Point `--csv` at your own export and edit
`config/sheet_layout.json` to match its geometry.

## What it is, and what it is not

This is a **doctor-prep and self-quantification evidence engine**. It takes the lab results you already have, keeps them verbatim, parses them into facts you can query, and records where every number came from in the tables of [schema/schema.sql](schema/schema.sql).

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

The rule the design hangs on: **map once, never discard the original.** Canonical rows never overwrite raw rows, and [schema/schema.sql](schema/schema.sql) is what enforces that. When the parser turns out to be wrong — and it will — you fix
the parser and rebuild. The source of truth is untouched, so a parser bug is never a data loss event — the argument in full is in [docs/METHOD.md](docs/METHOD.md).

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
`leading_zero_suspect`. A row the parser in [src/blood_ingest.py](src/blood_ingest.py) did not understand is still a row.

## Curation that ships with it

- **[`data/panels.json`](data/panels.json)** — a 16-panel classifier with bilingual
  (English + Russian) keywords. Ordered, first hit wins. Add your own language by
  appending keywords.
- **[`data/evidence_tiers.md`](data/evidence_tiers.md)** — A/B/C/D grading, and why a
  marker sits where it does.
- **[`data/loinc_seed.json`](data/loinc_seed.json)** — draft LOINC codes and canonical
  UCUM units. **Every code this produces is stamped `loinc_verified=0`.** The codes seeded from [data/loinc_seed.json](data/loinc_seed.json) are a scaffold to speed up verification, never asserted as truth. Verify at loinc.org and
  with a clinician before any clinical use.
- **[`data/analyte_dictionary.template.csv`](data/analyte_dictionary.template.csv)** —
  158 real-world analytes already classified in [data/analyte_dictionary.template.csv](data/analyte_dictionary.template.csv), as a starting point. Names and codes only;
  it contains no measurements. (This said 161 until 2026-09-10: three keys contain a
  newline inherited from a wrapped spreadsheet cell, so counting lines gives 161 and
  counting records gives 158. Counted with the convenient tool instead of the correct
  one -- the same class of mistake this repo is about.)

The dictionary is a CSV on purpose. Editing [data/analyte_dictionary.template.csv](data/analyte_dictionary.template.csv) and re-running beats patching Python, and it means the person maintaining the mapping does not have to be the person who wrote the parser.

## Why this exists

Everybody who tracks their own labs writes this parser, once, badly, and never publishes
it. So the same problems get solved again every time: a hyphen that is a range separator
and not a minus sign, a `×10⁹/л` that is a unit and not a second number, a comment
sub-row that looks exactly like an analyte, a "C-Reactive **Protein**" that a naive rule
files under proteins.

Both of the bugs in [`docs/DEVLOG.md`](docs/DEVLOG.md) shipped to production before tests
caught them. They are documented in [docs/METHOD.md](docs/METHOD.md) for the same reason the failure modes are: work you cannot check is not a result.

## Provenance and roadmap

Built at [Palo Alto AI Lab](https://palo-alto.ai/) on top of ten years of one person's
lab panels — 622 observations, 158 analytes, 10 draws, 2016 to 2025. **None of that data
is in this repository, and none of it ever will be.** What is here is the machinery and
the mapping.

What does **not** exist yet, stated plainly: there are **no wearable connectors** — no
Apple Health, no Whoop, no Oura, no Garmin. There is no rule engine, no alerting, no report generation; what is planned instead is in [ROADMAP.md](ROADMAP.md). See [`ROADMAP.md`](ROADMAP.md) for what is designed but unbuilt.
Contributions and counter-examples welcome — especially a lab export whose layout breaks the parser, in the shape of [examples/synthetic-panel.csv](examples/synthetic-panel.csv).

MIT licensed. Author: Anton Dziatkovskii ([ORCID 0000-0001-7408-3054](https://orcid.org/0000-0001-7408-3054)).

---

<!--ecosystem-map:start-->

## 🧩 One piece of a working system

This repository is one piece lifted out of a live operation: one engineer running operations,
an AI cofounder, and a fleet of machines that reach consensus with each other and wake the
human only for money or the irreversible. It was extracted after it survived production,
not written as a demo — and it runs on its own: nothing here phones home to the rest.

**See how the whole thing fits together → [SYSTEM.md](https://github.com/tonydzi/tonydzi/blob/main/SYSTEM.md)**

**Want your machine in the fleet? → [Join the fleet](https://github.com/tonydzi/join-the-fleet)** (15 minutes, one link, no account with us)

<!--ecosystem-map:end-->

## AI contributors

This project is built by a human + AI team, and the git log says so: Claude writes most of
the code, Codex and Grok review it, Gemini feeds the research. Each is credited on a commit
**only if its output changed that commit's content** — no decorative credits. Lab-wide
policy, one source for every repo: [AI-CONTRIBUTORS.md](https://github.com/tonydzi/.github/blob/main/AI-CONTRIBUTORS.md).

<!-- READ-WITH-AI:START (generated by read_with_ai.py - do not hand-edit) -->

### READ THIS WITH AI

One click and an agent reads the repo, pulls out the patterns and helps you apply them to your own work.

<a href="https://chatgpt.com/codex?prompt=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fblood-panel-pipeline%20%28%E2%80%9Cblood-panel-pipeline%E2%80%9D%20-%20Turn%20a%20decade%20of%20raw%20lab%20panels%20into%20a%20queryable%2C%20provenance-tracked%20record.%20Deterministic%20rules%20decide%20what%20is%20true%3B%20the%20model%20only%20explains.%20Stdlib-only%20Python%2C%20no%20dependencies%2C%20no%20data%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Codex - open" src="https://img.shields.io/badge/Codex-open-000000?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://chatgpt.com/?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fblood-panel-pipeline%20%28%E2%80%9Cblood-panel-pipeline%E2%80%9D%20-%20Turn%20a%20decade%20of%20raw%20lab%20panels%20into%20a%20queryable%2C%20provenance-tracked%20record.%20Deterministic%20rules%20decide%20what%20is%20true%3B%20the%20model%20only%20explains.%20Stdlib-only%20Python%2C%20no%20dependencies%2C%20no%20data%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="ChatGPT - open" src="https://img.shields.io/badge/ChatGPT-open-10a37f?style=for-the-badge&logo=openai&logoColor=white"></a> <a href="https://claude.ai/new?q=Read%20this%20repo%3A%20https%3A%2F%2Fgithub.com%2Ftonydzi%2Fblood-panel-pipeline%20%28%E2%80%9Cblood-panel-pipeline%E2%80%9D%20-%20Turn%20a%20decade%20of%20raw%20lab%20panels%20into%20a%20queryable%2C%20provenance-tracked%20record.%20Deterministic%20rules%20decide%20what%20is%20true%3B%20the%20model%20only%20explains.%20Stdlib-only%20Python%2C%20no%20dependencies%2C%20no%20data%29.%20Work%20out%20what%20problem%20it%20actually%20solves%2C%20pull%20out%20the%20reusable%20patterns%20and%20help%20me%20apply%20them%20to%20my%20own%20setup.%20Start%20by%20asking%20what%20I%20am%20working%20on."><img alt="Claude - open" src="https://img.shields.io/badge/Claude-open-d97757?style=for-the-badge&logo=anthropic&logoColor=white"></a>

<details>
<summary>Copy the prompt (works in any agent: Gemini, Grok, a local model, your own CLI)</summary>

```text
Read this repo: https://github.com/tonydzi/blood-panel-pipeline (“blood-panel-pipeline” - Turn a decade of raw lab panels into a queryable, provenance-tracked record. Deterministic rules decide what is true; the model only explains. Stdlib-only Python, no dependencies, no data). Work out what problem it actually solves, pull out the reusable patterns and help me apply them to my own setup. Start by asking what I am working on.
```

</details>

<sub>— TonyDzi, Palo Alto AI Research Lab · second brain, agent coordination, persistent memory: github.com/tonydzi</sub>

<!-- READ-WITH-AI:END -->
