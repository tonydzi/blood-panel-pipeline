# -*- coding: utf-8 -*-
"""
reproduce_miscoding.py — re-derive the LOINC miscoding result from the shipped files.

WHY THIS EXISTS
    docs/DEVLOG.md reports that substring matching assigned a wrong LOINC code to 12 of
    52 matched analytes, and that the first fix (sorting candidate keys longest-first)
    turned the failing test green without closing the class. That is a claim about our
    own past behaviour, and a claim you cannot check is not a result.

    Everything needed to check it is public: data/loinc_seed.json holds the 38 seed
    entries, data/analyte_dictionary.template.csv holds the 158 analyte names. No
    measurement, no patient data, and no private corpus is involved — the defect lives
    entirely in the mapping, so the mapping is enough to reproduce it.

WHAT IT DOES
    Runs three matching strategies over the shipped names and counts the damage:

      A  substring, file order      the original bug
      B  substring, longest key first   the fix that turned the test green
      C  exact normalised name only     what ships today

    "Wrong" means: the strategy assigned a code where exact matching assigns a different
    code or none. Note the honest limit of that definition — it measures agreement with
    exact matching, not clinical correctness. Exact matching is our reference here
    because an unmatched analyte gets no code at all, so it cannot invent one; it is not
    an expert-validated gold standard, and this script does not pretend to be one.

    Read-only. Touches no database. Stdlib only. Prints a table and exits 0 if the
    published figures reproduce, 1 if they do not.

Usage:
  python tests/reproduce_miscoding.py
"""
import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, os.pardir)
SEED_PATH = os.path.join(_ROOT, "data", "loinc_seed.json")
DICT_PATH = os.path.join(_ROOT, "data", "analyte_dictionary.template.csv")

# The figures published in docs/DEVLOG.md and in the accompanying preprint.
EXPECTED = {
    "names": 158,
    "seed_entries": 38,
    "assigned": {"A": 52, "B": 52, "C": 40},
    "wrong": {"A": 13, "B": 12, "C": 0},
    "rows_changed_by_first_fix": 1,
}


def norm(s):
    """Lowercase, unify dash variants, collapse whitespace. Nothing that changes meaning
    — meaning-changing normalisation is how wrong codes get assigned in the first place."""
    s = (s or "").lower().replace("–", "-").replace("—", "-")
    return " ".join(s.split())


def substring_lookup(name, table):
    """First seed key contained in the analyte name wins. `table` fixes the order."""
    n = norm(name)
    for key, code in table:
        if norm(key) in n:
            return code
    return None


def exact_lookup(name, seed):
    n = norm(name)
    for key, code in seed.items():
        if norm(key) == n:
            return code
    return None


def load():
    with open(SEED_PATH, encoding="utf-8") as f:
        seed = {k: v[0] for k, v in json.load(f)["seed"].items()}
    with open(DICT_PATH, encoding="utf-8") as f:
        names = [r["name_en"] for r in csv.DictReader(f)]
    return seed, names


def main():
    seed, names = load()
    in_file_order = list(seed.items())
    longest_first = sorted(seed.items(), key=lambda kv: -len(kv[0]))

    assigned = {"A": 0, "B": 0, "C": 0}
    wrong = {"A": 0, "B": 0, "C": 0}
    wrong_rows, changed_by_first_fix = [], []

    for name in names:
        a = substring_lookup(name, in_file_order)
        b = substring_lookup(name, longest_first)
        c = exact_lookup(name, seed)
        for key, code in (("A", a), ("B", b), ("C", c)):
            if code:
                assigned[key] += 1
                if code != c:
                    wrong[key] += 1
        if b and b != c:
            wrong_rows.append((name, b, c))
        if a != b:
            changed_by_first_fix.append((name, a, b))

    print("=== LOINC matching strategies over the shipped dictionary ===")
    print(f"analyte names: {len(names)} | seed entries: {len(seed)}\n")
    print(f"{'strategy':38} {'assigned':>9} {'wrong':>7}")
    for key, label in (("A", "substring, file order"),
                       ("B", "substring, longest key first"),
                       ("C", "exact normalised name only")):
        print(f"  {label:36} {assigned[key]:>9} {wrong[key]:>7}")

    print(f"\nwrong under longest-first ({len(wrong_rows)}) — the codes a green test certified:")
    for name, got, want in wrong_rows:
        print(f"   {name:44} -> {got:9} (exact: {want or 'no code'})")

    print(f"\nrows the longest-first fix actually changed: {len(changed_by_first_fix)} of {len(names)}")
    for name, a, b in changed_by_first_fix:
        print(f"   {name:44} {a} -> {b}")
    print("   ^ this is the point: the fix went green having repaired one defect of "
          f"{wrong['A']}.")

    ok = (len(names) == EXPECTED["names"]
          and len(seed) == EXPECTED["seed_entries"]
          and assigned == EXPECTED["assigned"]
          and wrong == EXPECTED["wrong"]
          and len(changed_by_first_fix) == EXPECTED["rows_changed_by_first_fix"])
    if ok:
        print("\nREPRODUCED — figures match docs/DEVLOG.md and the preprint.")
        return 0
    print("\nDID NOT REPRODUCE — the shipped data has changed since publication.")
    print(f"  expected assigned {EXPECTED['assigned']} wrong {EXPECTED['wrong']} "
          f"names {EXPECTED['names']} seed {EXPECTED['seed_entries']} "
          f"changed {EXPECTED['rows_changed_by_first_fix']}")
    print(f"  got      assigned {assigned} wrong {wrong} "
          f"names {len(names)} seed {len(seed)} changed {len(changed_by_first_fix)}")
    print("  If you edited the dictionary or the seed table, that is expected: update")
    print("  EXPECTED above in the same commit, so the published figures stay checkable.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
