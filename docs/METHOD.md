# Method

How a marker gets interpreted here, and the rules an assistant must obey when it helps.
This is the part that survives when the code is rewritten.

## Order of operations

1. **Facts first.** Parse and store before interpreting anything. A number whose
   provenance you cannot state is not evidence yet.
2. **Trend beats point.** One reading is a data point with unknown noise. Three readings
   of the same assay at the same lab are a signal. A change of lab or method resets the
   series — record it.
3. **Within-person before population.** A result inside a population reference range can
   still be a large move for one person; a result outside it can be that person's normal.
   Reference ranges exclude, they do not diagnose.
4. **Assay before biology.** Before believing a shift, rule out the boring explanations:
   different lab, different method, different units, fasting or not, time of day, an
   acute illness, a new supplement. Most surprises are pre-analytical.
5. **Tier weights attention.** See [`../data/evidence_tiers.md`](../data/evidence_tiers.md).
   A dramatic move in a tier-D composite is worth less than a quiet drift in a tier-A
   marker.

## Rules of engagement for any model or assistant

Written as constraints, because they are constraints.

- **State the evidence level with the claim.** Established, emerging, speculative — every
  time. A claim without its level is not usable.
- **Never frame a substance as a solution.** No "miracle", no "optimal", no protocol
  recommendation. Describe the evidence and its limits; the decision belongs to the person
  and their clinician.
- **Never invent a number, a range, or a citation.** If a value is not in the data, say it
  is not in the data. A fabricated reference range is worse than silence, because it looks
  like an answer.
- **Separate measured from derived.** A calculated value carries its formula. In this
  pipeline that is enforced: `qc_flag=derived`.
- **Name the risks and the monitoring.** Anything discussed comes with what to watch and
  what would mean stop.
- **Interactions before additions.** Existing medications and conditions are considered
  before anything new is discussed.
- **The model explains, the rules decide.** No alert, no threshold, no classification may
  originate in a language model. If removing the model changes which facts exist, the
  boundary has been violated.

## Template for a self-experiment

If you are going to test something on yourself, write it down before you start. The
template is short on purpose:

```
hypothesis    what should change, in one sentence
metric        which marker, which assay, which lab
baseline      how many readings before, over what period
duration      how long, decided in advance
measurement   when and under what conditions (fasting, time of day)
stop rule     what result means stop immediately
rollback      how to undo it
confounders   what else changes in the same window (and how you'll know)
```

An experiment with no stop rule and no predefined duration is not an experiment. It is a
habit acquiring evidence for itself.

## Where to check a claim

Grouped by what they are good for, because the failure mode is checking a safety question
against a mechanism database.

- **Primary literature and synthesis** — PubMed/MEDLINE, Cochrane, Europe PMC,
  ClinicalTrials.gov (including the trials that ended and never published).
- **Regulatory and label data** — FDA, EMA, DailyMed. What a regulator accepted is a
  different question from what a study suggested.
- **Safety, interactions, quality** — LiverTox, NIH ODS, CYP450 interaction references,
  independent product testing. This is where supplement questions actually get answered.
- **Ageing-specific resources** — LongevityMap, Aging Atlas, CellAge, Open Genes.
- **Reputation of the source itself** — Retraction Watch, PubPeer, scite.ai. Checking
  whether a paper still stands takes a minute and changes conclusions more often than
  people expect.

A live URL is not a verified citation. If you have not read what the link says, you have
a link, not evidence.
