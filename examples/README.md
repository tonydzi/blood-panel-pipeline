# Synthetic example

`synthetic-panel.csv` contains **invented numbers for a person who does not exist.**
Round values, first-of-January draw dates, and a header row that says so. It exists to
make the pipeline runnable without anyone's real data.

It deliberately includes the cases that break naive parsers:

| row | what it exercises |
|---|---|
| `Glucose` 2024 draw `6.0*` | asterisk = lab out-of-range marker |
| `CRP` 2020 draw `<1.0` | comparator instead of a value |
| `Non-HDL` all draws `расчет 2.5` | calculated, not measured → `qc_flag=derived` |
| `WBC` `6.0 ×10⁹/л` | scientific scale is part of the **unit**, not a second value |
| `HERPES VIRUS I` `нет` | non-numeric result that must be kept, not dropped |
| `ApoB` empty until 2024 | a marker introduced mid-history |
| `Комментарий` row | comment sub-row that looks like an analyte and must be rejected |
| `20-40` row | bare age bracket that must be rejected |
| `БИОХИМИЯ` / `ГЕМАТОЛОГИЯ` | section headers with no measurements |
| reference ranges `3.9-5.5` | hyphen is a separator, not a minus sign (see `docs/DEVLOG.md`) |

Run it:

```
python src/blood_ingest.py --csv examples/synthetic-panel.csv --sheet-id demo --db out/blood.db
python src/blood_enrich.py --db out/blood.db
```

Expected: 3 draws, 21 analytes, 61 observations, 2 rejected noise rows.

## Using your own export

Do not edit the code. Copy `config/sheet_layout.json`, adjust the column and row indices
to your sheet, and pass `--layout your_layout.json`. Column indices are 0-based; each draw
is a block that starts at a date cell and may be followed by a unit column and a reference
column.

Freeze your export first — export once to CSV and treat that file as immutable. The
database records its path, so a rebuild always refers to a snapshot that has not moved
under you.
