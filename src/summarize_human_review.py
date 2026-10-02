#!/usr/bin/env python3
"""Summarize the completed ArabicMedReason human-review sheet.

The script only aggregates the human judgments recorded in
`analysis/human_review.csv`. It does not grade responses, infer labels or call an
LLM judge. It refuses to run while any required judgment is blank or invalid.

The raw outputs file is read only to report generation anomalies (responses that
hit `max_new_tokens`, and responses containing more than one FINAL_ANSWER line).
These are mechanical facts about the output, not grades.

Outputs:
- analysis/summary_metrics.json  structured metrics
- analysis/summary_metrics.csv   long-format table of the headline metrics
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd

YES_NO = {"yes", "no"}
REQUIRED_YES_NO = [
    "human_final_correct",
    "human_reason_supported",
    "human_unsupported_assumption",
]
REQUIRED_TEXT = ["human_error_type", "human_notes"]
LANGS = ["ar", "en"]
CATEGORIES = [
    "temporal_reasoning",
    "contradiction_detection",
    "missing_evidence",
    "false_premise",
    "causal_reasoning",
]


def rate(num: int, den: int) -> dict:
    return {"n": int(den), "count": int(num), "rate": round(num / den, 4) if den else None}


def normalize_binary(value: str) -> str | None:
    token = re.sub(r"[\s\u200f\u200e]+", " ", (value or "").strip()).rstrip(".。،,").casefold()
    return {"yes": "yes", "no": "no", "نعم": "yes", "لا": "no"}.get(token)


def load_review(path: Path) -> pd.DataFrame:
    # keep_default_na=False: a literal model answer such as "None" must stay a string.
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    problems = []
    for col in REQUIRED_YES_NO + REQUIRED_TEXT:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    for col in REQUIRED_YES_NO:
        df[col] = df[col].str.strip().str.casefold()
        bad = ~df[col].isin(YES_NO)
        if bad.any():
            problems.append(f"{col}: {df.loc[bad, 'id'].tolist()}")
    for col in REQUIRED_TEXT:
        df[col] = df[col].str.strip()
        bad = df[col] == ""
        if bad.any():
            problems.append(f"{col} blank: {df.loc[bad, 'id'].tolist()}")
    if problems:
        raise SystemExit("Human review is incomplete; not computing metrics.\n" + "\n".join(problems))
    if df["id"].duplicated().any():
        raise SystemExit(f"Duplicate ids: {df.loc[df['id'].duplicated(), 'id'].tolist()}")
    return df


def load_raw(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as f:
        return {r["id"]: r for r in (json.loads(line) for line in f if line.strip())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="analysis/human_review.csv")
    parser.add_argument("--raw", default="results/evaluation_raw_outputs.jsonl")
    parser.add_argument("--config", default="results/evaluation_run_config.json")
    parser.add_argument("--json", default="analysis/summary_metrics.json")
    parser.add_argument("--csv", default="analysis/summary_metrics.csv")
    args = parser.parse_args()

    df = load_review(Path(args.input))
    raw = load_raw(Path(args.raw))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if set(raw) != set(df["id"]):
        raise SystemExit("Review sheet ids do not match the raw outputs.")

    df["correct"] = df["human_final_correct"] == "yes"
    df["reason_ok"] = df["human_reason_supported"] == "yes"
    df["assumption"] = df["human_unsupported_assumption"] == "yes"
    df["both_ok"] = df["correct"] & df["reason_ok"]

    def block(g: pd.DataFrame) -> dict:
        n = len(g)
        return {
            "final_answer_accuracy": rate(g["correct"].sum(), n),
            "reason_supported": rate(g["reason_ok"].sum(), n),
            "final_correct_and_reason_supported": rate(g["both_ok"].sum(), n),
            "unsupported_assumption": rate(g["assumption"].sum(), n),
        }

    by_language = {lang: block(df[df["language"] == lang]) for lang in LANGS}
    by_category = {cat: block(df[df["category"] == cat]) for cat in CATEGORIES}
    by_language_category = {
        lang: {cat: block(df[(df["language"] == lang) & (df["category"] == cat)]) for cat in CATEGORIES}
        for lang in LANGS
    }

    # D. Minimal-pair consistency: a pair counts only if both A and B are correct.
    pairs = df.groupby(["language", "pair_id", "category"])["correct"].agg(["count", "sum"]).reset_index()
    if not (pairs["count"] == 2).all():
        raise SystemExit("Every language/pair must have exactly an A and a B row.")
    pairs["both"] = pairs["sum"] == 2
    pair_consistency = {}
    for lang in LANGS:
        p = pairs[pairs["language"] == lang]
        pair_consistency[lang] = {
            "overall": rate(p["both"].sum(), len(p)),
            "by_category": {c: rate(p[p["category"] == c]["both"].sum(), (p["category"] == c).sum()) for c in CATEGORIES},
            "inconsistent_pairs": sorted(p.loc[~p["both"], "pair_id"].tolist()),
        }

    # E. Cross-language matched outcomes per scenario.
    piv = df.pivot_table(index=["scenario_id", "category"], columns="language", values="correct", aggfunc="first").reset_index()
    outcome = pd.Series("both_incorrect", index=piv.index)
    outcome[piv["ar"] & piv["en"]] = "both_correct"
    outcome[piv["ar"] & ~piv["en"]] = "arabic_only_correct"
    outcome[~piv["ar"] & piv["en"]] = "english_only_correct"
    piv["outcome"] = outcome
    labels = ["both_correct", "arabic_only_correct", "english_only_correct", "both_incorrect"]
    b, c = int((piv["outcome"] == labels[1]).sum()), int((piv["outcome"] == labels[2]).sum())
    # Exact two-sided McNemar test on the discordant matched scenarios.
    mcnemar_p = min(1.0, 2 * sum(math.comb(b + c, k) for k in range(min(b, c) + 1)) / 2 ** (b + c)) if b + c else None
    cross = {
        "n_scenarios": int(len(piv)),
        "mcnemar_exact_p_two_sided": round(mcnemar_p, 4) if mcnemar_p is not None else None,
        "overall": {k: int((piv["outcome"] == k).sum()) for k in labels},
        "by_category": {c: {k: int(((piv["outcome"] == k) & (piv["category"] == c)).sum()) for k in labels} for c in CATEGORIES},
        "scenarios": {k: sorted(piv.loc[piv["outcome"] == k, "scenario_id"].tolist()) for k in labels[1:]},
    }

    # Yes/No polarity on binary items: accuracy split by the expected label.
    binary = df[df["category"] != "false_premise"].copy()
    binary["expected_label"] = binary["expected_answer"].map(normalize_binary)
    binary["model_label"] = binary["model_final_answer"].map(normalize_binary)
    polarity = {
        lang: {
            f"expected_{lab}": rate(g[g["expected_label"] == lab]["correct"].sum(), (g["expected_label"] == lab).sum())
            for lab in ["yes", "no"]
        }
        | {"model_answered_no": rate((g["model_label"] == "no").sum(), len(g))}
        for lang, g in ((lang, binary[binary["language"] == lang]) for lang in LANGS)
    }
    # Binary pairs where the model gave the same label to A and B (it did not update on the flip).
    for lang in LANGS:
        labels_ab = binary[binary["language"] == lang].groupby("pair_id")["model_label"].agg(lambda s: s.nunique() == 1)
        pair_consistency[lang]["binary_pairs_same_label_for_A_and_B"] = {
            **rate(labels_ab.sum(), len(labels_ab)),
            "pair_ids": sorted(labels_ab[labels_ab].index.tolist()),
        }

    # F. Error taxonomy (semicolon-separated labels; "none" excluded).
    errs = df.loc[df["human_error_type"].str.casefold() != "none", ["id", "language", "human_error_type"]]
    exploded = errs.assign(label=errs["human_error_type"].str.split(";")).explode("label")
    exploded["label"] = exploded["label"].str.strip()
    error_types = {
        "rows_with_error_label": int(len(errs)),
        "label_counts": {
            lab: {"total": int(len(g)), "ar": int((g["language"] == "ar").sum()), "en": int((g["language"] == "en").sum()), "ids": sorted(g["id"])}
            for lab, g in sorted(exploded.groupby("label"), key=lambda kv: (-len(kv[1]), kv[0]))
        },
    }

    # G. Generation anomalies (mechanical facts from raw outputs, not grades).
    max_new = config["generation_params"]["max_new_tokens"]
    truncated = sorted(i for i, r in raw.items() if not r.get("stopped_on_eos", True) or r.get("n_output_tokens", 0) >= max_new)
    multi_final = sorted(
        i for i, r in raw.items()
        if len(re.findall(r"(?m)^FINAL_ANSWER:", r.get("raw_model_output_no_special_tokens") or "")) > 1
    )
    review = df.set_index("id")
    truncation = {
        "max_new_tokens": max_new,
        "n_truncated": len(truncated),
        "cases": [
            {
                "id": i,
                "n_output_tokens": raw[i].get("n_output_tokens"),
                "stopped_on_eos": raw[i].get("stopped_on_eos"),
                "human_final_correct": review.loc[i, "human_final_correct"],
                "human_error_type": review.loc[i, "human_error_type"],
            }
            for i in truncated
        ],
        "multiple_final_answer_lines": [
            {"id": i, "human_final_correct": review.loc[i, "human_final_correct"]} for i in multi_final
        ],
        "grading_note": "When a response contains more than one FINAL_ANSWER line, the first one was graded.",
    }

    summary = {
        "source": {
            "review_file": args.input,
            "raw_outputs": args.raw,
            "model": config["model_name"],
            "run_id": config["run_id"],
            "n_cases": int(len(df)),
        },
        "overall": block(df),
        "by_language": by_language,
        "by_category": by_category,
        "by_language_category": by_language_category,
        "binary_polarity": polarity,
        "minimal_pair_consistency": pair_consistency,
        "cross_language_consistency": cross,
        "error_types": error_types,
        "truncation": truncation,
    }
    Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Long-format CSV with the headline metrics.
    rows = []
    for metric, key in [
        ("final_answer_accuracy", "final_answer_accuracy"),
        ("reason_supported_rate", "reason_supported"),
        ("final_correct_and_reason_supported_rate", "final_correct_and_reason_supported"),
        ("unsupported_assumption_rate", "unsupported_assumption"),
    ]:
        groups = [("all", "all", summary["overall"])]
        groups += [(lang, "all", by_language[lang]) for lang in LANGS]
        groups += [("all", cat, by_category[cat]) for cat in CATEGORIES]
        groups += [(lang, cat, by_language_category[lang][cat]) for lang in LANGS for cat in CATEGORIES]
        rows += [{"metric": metric, "language": l, "category": c, **m[key]} for l, c, m in groups]
    for lang in LANGS:
        pc = pair_consistency[lang]
        rows.append({"metric": "minimal_pair_consistency", "language": lang, "category": "all", **pc["overall"]})
        rows += [{"metric": "minimal_pair_consistency", "language": lang, "category": c, **pc["by_category"][c]} for c in CATEGORIES]
    for k, v in cross["overall"].items():
        rows.append({"metric": f"cross_language_{k}", "language": "ar+en", "category": "all", "n": cross["n_scenarios"], "count": v, "rate": round(v / cross["n_scenarios"], 4)})
    pd.DataFrame(rows, columns=["metric", "language", "category", "n", "count", "rate"]).to_csv(args.csv, index=False, encoding="utf-8")

    o = summary["overall"]
    print(f"Cases: {len(df)}")
    print(f"Final-answer accuracy: overall {o['final_answer_accuracy']['count']}/100"
          + "".join(f", {l} {by_language[l]['final_answer_accuracy']['count']}/50" for l in LANGS))
    print("Minimal-pair consistency: " + ", ".join(f"{l} {pair_consistency[l]['overall']['count']}/25" for l in LANGS))
    print(f"Cross-language: {cross['overall']}")
    print(f"Truncated: {truncated}; multiple FINAL_ANSWER lines: {multi_final}")
    print(f"Saved: {args.json}\nSaved: {args.csv}")


if __name__ == "__main__":
    main()
