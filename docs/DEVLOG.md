# Dev log — bugs that shipped before tests caught them

Failures are published here, not smoothed over. Each entry is a real defect found on real
data, with the root cause and the fix that closes the whole class rather than the single
case.

---

## 2026-08-04 — a reference range with a negative floor

**Symptom.** `parse_ref("3.9-5.5")` returned `(-5.5, 3.9)`: an inverted range whose lower
bound was negative. Every two-sided reference range in the database was affected.

**Root cause.** The number pattern was signed — `[-+]?\d+(?:[.,]\d+)?`. In `3.9-5.5` the
hyphen is a *range separator*, but a signed pattern reads it as the sign of `-5.5`. The
code then took `min`/`max` of `[3.9, -5.5]` and produced a range no lab ever wrote.

**Why it survived.** It fails silently and plausibly. Nothing crashes, the row still has
bounds, and a single-sided range like `<5.2` — the case a human eyeballs first — parses
correctly. Only a two-sided range is wrong, and only in a field nobody reads directly.

**Fix.** A separate unsigned pattern for reference bounds. Lab reference bounds are
non-negative, so the sign has no business being in the pattern at all. The class of bug —
"a separator character read as part of a token" — is closed, not the one pair.

**Regression.** Four assertions in `tests/test_pipeline.py`, including one that fails if
*any* parsed range has a negative floor.

---

## 2026-08-04 — non-HDL cholesterol wearing the HDL code

**Symptom.** `Non-HDL Cholesterol` was assigned LOINC `2085-9`, which is the code for
`HDL Cholesterol`. A different marker, carrying the wrong standard identifier.

**Root cause.** Code lookup was a substring scan over a dictionary in insertion order.
`"hdl cholesterol"` is a substring of `"non-hdl cholesterol"`, and the shorter key came
first, so it won.

**Why it matters more than the first bug.** A wrong reference range is visibly odd once
you look. A wrong LOINC code is *invisible*: it looks exactly like a correct one, and it
is the field that would carry the marker into any downstream system that trusts standard
identifiers. `loinc_verified=0` limits the blast radius; it does not make the code right.

**First fix, and why it was not enough.** Candidate keys were sorted longest-first, so a
specific name could not lose to a shorter name contained inside it. That repaired the
non-HDL pair — and hid the real problem for about ten minutes. See the next entry.

**Regression.** Two assertions: non-HDL must not share HDL's code, and non-HDL must carry
its own (`43396-1`).

---

## 2026-08-04 — twelve markers wearing another marker's code

**Symptom.** Reviewing the shipped dictionary by eye, three different analytes carried
LOINC `718-7`, the code for haemoglobin. They were `Mean Corpuscular Hemoglobin`,
`Mean Corpuscular Hemoglobin Concentration` and `Reticulocyte Hemoglobin Content` — three
distinct measurements, none of them haemoglobin. In total **12 of 52 assigned codes were
wrong**, including free and total testosterone both carrying the code for testosterone,
an albumin/globulin *ratio* carrying the code for albumin, and red blood cells **in urine**
carrying the code for red blood cells in blood.

**Root cause.** Not the ordering — the *matching strategy*. Substring matching is simply
unsafe for medical identifiers, because clinically distinct markers are routinely named by
extending each other: haemoglobin → mean corpuscular haemoglobin, testosterone → free
testosterone, RBC → RBC (urine). Longest-first ordering only helps when the correct
longer key exists in the table; when it does not, the shorter key still wins and stamps
the wrong code.

**Why the first fix made it worse to spot.** After sorting by length the non-HDL case went
green, which felt like the class was closed. It was not: it was one instance of it. The
lesson is the uncomfortable one — a fix that turns a red test green is not evidence that
the *class* is closed.

**Fix.** Exact normalised-name match only. An analyte that is not in the seed table gets
**no code**, and a human adds an explicit entry. Normalisation is limited to case, dash
variants and whitespace — anything that changes meaning is how wrong codes get assigned
in the first place. The count of assigned codes dropped from 52 to 40, and all twelve
wrong ones are gone.

**The principle worth stealing.** For medical identifiers, *missing is recoverable and
wrong is not*. A blank field prompts someone to look it up. A confidently wrong code
propagates into every downstream system that trusts standard identifiers, and it looks
exactly like a correct one. `loinc_verified=0` limits the blast radius; it never made the
code right.

**Regression.** Nine assertions, including one that re-derives every code in the shipped
dictionary from the seed table and fails if any row cannot be reproduced.

---

## 2026-07-06 — three parser defects from the first real ingestion

Found while building the first database from a ten-year comparison sheet.

1. **Scientific notation read as a second value.** `6.2 ×10⁹/л` produced two numbers, `6.2`
   and `10`, and the multi-value flag fired on a perfectly ordinary blood count. Fix:
   strip scale tokens before scanning for numbers — the scale is part of the *unit*.
2. **Comment and age-range sub-rows ingested as analytes.** The sheet interleaves
   `Комментарий` rows and bare `20-40` age brackets between real markers; both have the
   shape of an analyte row. Fix: an explicit noise-key set plus an age-range pattern,
   both configurable rather than hardcoded.
3. **Panel headers swallowing the markers below them.** Grouping by "the last ALL-CAPS row
   seen" mis-filed the hormone and serology tail under a vitamin header. Fix: stop
   inferring panels from document order. A keyword classifier over the marker's own name
   is authoritative; the running header survives only as an approximate `section` hint,
   and the database says so in `meta.section_reliability`.

The distinguishing signal for defect 3 is worth keeping: a real analyte with no data in
this snapshot still carries an English name or an abbreviation. A bare panel header
carries neither. That is what separates them, not the presence of values.
