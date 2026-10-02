"""Validate ArabicMedReason benchmark CSVs.

Usage:
    python src/validate_dataset.py [path/to/dataset.csv]

Defaults to data/pilot.csv. Two schemas are supported and detected from the header:

- pilot schema:      id, category, language, pair_id, case_text, question, expected_answer
- evaluation schema: pilot columns + scenario_id, expected_reason, evidence_flip
                     (also checks the full design: 25 pairs x A/B x ar/en = 100 rows)

Exits with status 1 if any error is found.
"""

import re
import sys
from pathlib import Path

import pandas as pd

PILOT_COLUMNS = [
    "id",
    "category",
    "language",
    "pair_id",
    "case_text",
    "question",
    "expected_answer",
]
EVALUATION_EXTRA_COLUMNS = ["scenario_id", "expected_reason", "evidence_flip"]
EVALUATION_COLUMNS = [
    "id",
    "category",
    "language",
    "pair_id",
    "scenario_id",
    "case_text",
    "question",
    "expected_answer",
    "expected_reason",
    "evidence_flip",
]

ALLOWED_CATEGORIES = {
    "temporal_reasoning",
    "contradiction_detection",
    "missing_evidence",
    "false_premise",
    "causal_reasoning",
}
ALLOWED_LANGUAGES = {"ar", "en"}
VARIANTS = ("A", "B")

# Design targets for the full evaluation set.
EXPECTED_PAIRS_PER_CATEGORY = 5
EXPECTED_PAIRS = EXPECTED_PAIRS_PER_CATEGORY * len(ALLOWED_CATEGORIES)
EXPECTED_ROWS = EXPECTED_PAIRS * len(VARIANTS) * len(ALLOWED_LANGUAGES)
EXPECTED_ROWS_PER_LANGUAGE = EXPECTED_ROWS // len(ALLOWED_LANGUAGES)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "pilot.csv"


def detect_schema(columns) -> str:
    return "evaluation" if any(c in columns for c in EVALUATION_EXTRA_COLUMNS) else "pilot"


def validate(path: Path) -> tuple[list[str], list[str], pd.DataFrame | None, str]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"], warnings, None, "unknown"

    # Read everything as text and keep empty cells as "" so blanks are detectable.
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df = df.apply(lambda col: col.str.strip())
    schema = detect_schema(df.columns)
    required = EVALUATION_COLUMNS if schema == "evaluation" else PILOT_COLUMNS

    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns for {schema} schema: {missing}")
        return errors, warnings, df, schema

    extra = [c for c in df.columns if c not in required]
    if extra:
        warnings.append(f"Unexpected extra columns: {extra}")

    # Row numbers reported as they appear in the file (header is line 1).
    def rows(mask: pd.Series) -> list[int]:
        return [i + 2 for i in df.index[mask]]

    # ---- Checks shared by both schemas ----
    non_empty = [c for c in required if c not in ("category", "language")]
    for col in non_empty:
        empty = df[col] == ""
        if empty.any():
            errors.append(f"Empty '{col}' on line(s) {rows(empty)}")

    dup = df["id"].duplicated(keep=False) & (df["id"] != "")
    if dup.any():
        errors.append(f"Duplicate ids: {sorted(df.loc[dup, 'id'].unique())}")

    bad_cat = ~df["category"].isin(ALLOWED_CATEGORIES)
    if bad_cat.any():
        errors.append(
            f"Invalid category on line(s) {rows(bad_cat)}: "
            f"{sorted(df.loc[bad_cat, 'category'].unique())}"
        )

    bad_lang = ~df["language"].isin(ALLOWED_LANGUAGES)
    if bad_lang.any():
        errors.append(
            f"Invalid language on line(s) {rows(bad_lang)}: "
            f"{sorted(df.loc[bad_lang, 'language'].unique())} "
            f"(allowed: {sorted(ALLOWED_LANGUAGES)})"
        )

    dup_case = df.duplicated(subset=["language", "case_text"], keep=False) & (df["case_text"] != "")
    if dup_case.any():
        groups = df[dup_case].groupby(["language", "case_text"])["id"].apply(list).tolist()
        errors.append(f"Duplicate case_text within a language: {groups}")

    # Soft checks on minimal-pair structure (warnings only).
    paired = df[df["pair_id"] != ""]
    for (pid, lang), group in paired.groupby(["pair_id", "language"]):
        pair_id = f"{pid} [{lang}]"
        if len(group) != 2:
            warnings.append(f"pair {pair_id} has {len(group)} item(s), expected 2")
        if group["category"].nunique() > 1:
            warnings.append(f"pair {pair_id} mixes categories")
        if group["expected_answer"].nunique() < len(group):
            warnings.append(f"pair {pair_id} has identical expected answers")

    if schema == "evaluation":
        validate_evaluation_design(df, errors, warnings)

    return errors, warnings, df, schema


def validate_evaluation_design(df: pd.DataFrame, errors: list[str], warnings: list[str]) -> None:
    """Checks specific to the full matched Arabic/English minimal-pair design."""
    # 1-3. Overall counts.
    if len(df) != EXPECTED_ROWS:
        errors.append(f"Expected {EXPECTED_ROWS} rows, found {len(df)}")
    for lang in sorted(ALLOWED_LANGUAGES):
        n = int((df["language"] == lang).sum())
        if n != EXPECTED_ROWS_PER_LANGUAGE:
            errors.append(f"Expected {EXPECTED_ROWS_PER_LANGUAGE} '{lang}' rows, found {n}")
    n_pairs = df["pair_id"].nunique()
    if n_pairs != EXPECTED_PAIRS:
        errors.append(f"Expected {EXPECTED_PAIRS} unique pair_ids, found {n_pairs}")

    # Each pair_id must belong to exactly one category.
    cats_per_pair = df.groupby("pair_id")["category"].nunique()
    for pid in cats_per_pair[cats_per_pair > 1].index:
        errors.append(f"pair {pid} spans several categories: "
                      f"{sorted(df.loc[df['pair_id'] == pid, 'category'].unique())}")

    # 4. Pairs per category.
    pairs_per_cat = df.groupby("category")["pair_id"].nunique()
    for cat in sorted(ALLOWED_CATEGORIES):
        n = int(pairs_per_cat.get(cat, 0))
        if n != EXPECTED_PAIRS_PER_CATEGORY:
            errors.append(f"Category '{cat}' has {n} pair_ids, expected {EXPECTED_PAIRS_PER_CATEGORY}")

    # Identifier consistency: scenario_id = pair_id + A/B; id = LANG-scenario_id.
    for i, r in df.iterrows():
        line = i + 2
        m = re.fullmatch(r"(.+)([AB])", r["scenario_id"])
        if not m or m.group(1) != r["pair_id"]:
            errors.append(f"line {line} ({r['id']}): scenario_id '{r['scenario_id']}' "
                          f"should be pair_id '{r['pair_id']}' + 'A' or 'B'")
        expected_id = f"{r['language'].upper()}-{r['scenario_id']}"
        if r["id"] != expected_id:
            errors.append(f"line {line}: id '{r['id']}' should be '{expected_id}'")

    # 5 & 12. Exactly four rows per pair: ar-A, ar-B, en-A, en-B.
    variant = df["scenario_id"].str[-1]
    expected_slots = {(lang, v) for lang in ALLOWED_LANGUAGES for v in VARIANTS}
    for pid, group in df.groupby("pair_id"):
        slots = list(zip(group["language"], variant[group.index]))
        missing_slots = sorted(expected_slots - set(slots))
        extra_slots = sorted({s for s in slots if slots.count(s) > 1})
        if len(group) != 4 or missing_slots or extra_slots:
            msg = f"pair {pid} has {len(group)} rows"
            if missing_slots:
                msg += f"; missing {['-'.join(s) for s in missing_slots]}"
            if extra_slots:
                msg += f"; duplicated {['-'.join(s) for s in extra_slots]}"
            errors.append(msg + " (expected ar-A, ar-B, en-A, en-B)")

    # 10-11. Each scenario_id has exactly one ar and one en row, with matching metadata.
    for sid, group in df.groupby("scenario_id"):
        langs = sorted(group["language"])
        if langs != sorted(ALLOWED_LANGUAGES):
            errors.append(f"scenario {sid} has languages {langs}, expected exactly one 'ar' and one 'en'")
            continue
        for col in ("category", "pair_id"):
            if group[col].nunique() > 1:
                errors.append(f"scenario {sid}: ar/en rows differ in '{col}': {group[col].tolist()}")
        if group["evidence_flip"].nunique() > 1:
            warnings.append(f"scenario {sid}: ar/en rows have different evidence_flip text")

    # Within a pair and language, the A and B questions should normally be identical so that
    # only the case evidence differs.
    for (pid, lang), group in df.groupby(["pair_id", "language"]):
        if group["question"].nunique() > 1:
            warnings.append(f"pair {pid} [{lang}]: A and B questions differ")
        if group["evidence_flip"].nunique() > 1:
            warnings.append(f"pair {pid} [{lang}]: A and B rows have different evidence_flip text")


def answer_balance(df: pd.DataFrame) -> pd.DataFrame | None:
    """Count Yes/No expected answers per category (English rows), for a balance overview."""
    en = df[df["language"] == "en"]
    if en.empty:
        return None
    label = en["expected_answer"].str.extract(r"^(Yes|No)\b", expand=False).fillna("other")
    return pd.crosstab(en["category"], label)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    errors, warnings, df, schema = validate(path)

    print(f"Dataset: {path}")
    print(f"Schema : {schema}")
    if df is not None and not df.empty and "category" in df.columns:
        print(f"Rows: {len(df)}")
        if "pair_id" in df.columns:
            print(f"Pairs: {df['pair_id'].replace('', pd.NA).nunique()}")
        if "language" in df.columns:
            print("By language: " + ", ".join(
                f"{k}={v}" for k, v in df["language"].value_counts().sort_index().items()))
            print("By category (rows | ar | en):")
            for cat, n in df["category"].value_counts().sort_index().items():
                sub = df[df["category"] == cat]["language"]
                print(f"  {cat:<25} {n:>3} | {int((sub == 'ar').sum()):>2} | {int((sub == 'en').sum()):>2}")
        if schema == "evaluation" and "expected_answer" in df.columns:
            balance = answer_balance(df)
            if balance is not None:
                print("Expected-answer labels per category (English rows):")
                print("  " + balance.to_string().replace("\n", "\n  "))

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"FAILED ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    print(f"PASSED ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
