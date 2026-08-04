# Evidence tiers

Not every marker deserves equal weight. The tier is a property of the *marker*, not of
your result: it says how much the measurement is worth paying attention to at all.

Tiers are assigned by keyword in `data/panels.json` and stored on every analyte. The
default is C.

| tier | meaning | examples |
|---|---|---|
| **A** | Strong outcome evidence, standardised assay, actionable. Worth tracking on purpose. | HbA1c, ApoB |
| **B** | Good evidence, adds information beyond the standard panel, assay reasonably standardised. | hs-CRP, homocysteine, Lp(a), omega-3 index, LDL-C, non-HDL-C |
| **C** | Standard clinical chemistry. Useful in context, weak as a standalone longitudinal signal. | most of a routine panel — liver enzymes, electrolytes, CBC |
| **D** | Exploratory or commercial composite. Interesting, poorly standardised between providers, not a basis for decisions. | epigenetic clocks (DunedinPACE, GrimAge, PhenoAge), "biological age" scores |

Two consequences worth stating:

- **Tier D is not an insult.** It means results are not comparable across vendors or even
  across runs, so a trend line built from them is measuring the vendor as much as you.
- **A missing tier-A marker is a finding.** If your panel has never included ApoB or
  Lp(a), that gap is more informative than another year of the same tier-C chemistry.

Change the assignments to match your own reading of the literature — that is what the
config file is for. If you disagree with a placement, open an issue with the citation;
that argument is more useful to everyone than a silent local edit.
