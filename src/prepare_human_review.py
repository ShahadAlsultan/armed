#!/usr/bin/env python3
"""Prepare a human-review worksheet from saved ArabicMedReason raw outputs.

This script does *not* grade model reasoning. It only parses the model's requested
FINAL_ANSWER / REASON fields and creates a review sheet with blank human-judgment
columns. Human judgments are required before any final analysis is reported.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


def parse_response(text: str) -> tuple[str, str]:
    text = text or ""
    final_match = re.search(r"(?m)^FINAL_ANSWER:\s*(.*)$", text)
    reason_match = re.search(r"(?ms)^REASON:\s*(.*)$", text)
    final_answer = final_match.group(1).strip() if final_match else ""
    reason = reason_match.group(1).strip() if reason_match else ""
    return final_answer, reason


def normalize_binary(value: str) -> str | None:
    token = re.sub(r"[\s\u200f\u200e]+", " ", (value or "").strip()).rstrip(".。،,")
    mapping = {"yes": "yes", "no": "no", "نعم": "yes", "لا": "no"}
    return mapping.get(token.casefold())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="results/evaluation_raw_outputs.jsonl",
        help="Path to evaluation_raw_outputs.jsonl",
    )
    parser.add_argument(
        "--output",
        default="analysis/human_review.csv",
        help="Destination CSV review worksheet",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing review sheet (this discards any human judgments in it)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if output_path.exists() and not args.force:
        raise SystemExit(f"{output_path} already exists; refusing to overwrite human judgments (use --force).")

    rows = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            model_text = record.get("raw_model_output_no_special_tokens") or record.get("raw_model_output", "")
            model_final, model_reason = parse_response(model_text)

            expected_binary = normalize_binary(str(record.get("expected_answer", "")))
            model_binary = normalize_binary(model_final)
            binary_auto_match = ""
            if expected_binary is not None and model_binary is not None:
                binary_auto_match = "yes" if expected_binary == model_binary else "no"

            rows.append(
                {
                    "id": record.get("id", ""),
                    "pair_id": record.get("pair_id", ""),
                    "scenario_id": record.get("scenario_id", ""),
                    "category": record.get("category", ""),
                    "language": record.get("language", ""),
                    "case_text": record.get("case_text", ""),
                    "question": record.get("question", ""),
                    "expected_answer": record.get("expected_answer", ""),
                    "expected_reason": record.get("expected_reason", ""),
                    "evidence_flip": record.get("evidence_flip", ""),
                    "model_final_answer": model_final,
                    "model_reason": model_reason,
                    "binary_auto_match": binary_auto_match,
                    "n_output_tokens": record.get("n_output_tokens", ""),
                    "truncated": "yes" if not bool(record.get("stopped_on_eos", True)) else "no",
                    # Human-owned fields. Leave blank until reviewed by the applicant.
                    "human_final_correct": "",
                    "human_reason_supported": "",
                    "human_unsupported_assumption": "",
                    "human_error_type": "",
                    "human_notes": "",
                }
            )

    df = pd.DataFrame(rows)
    if len(df) != 100:
        print(f"WARNING: expected 100 rows, found {len(df)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Wrote {len(df)} rows to {output_path}")
    print("Human-review fields are intentionally blank.")
    print("binary_auto_match is only a mechanical aid for simple Yes/No labels; it is not a human grade.")


if __name__ == "__main__":
    main()
