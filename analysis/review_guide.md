# Human Review Guide — ArabicMedReason

This review is intentionally human-owned. The scripts may parse the model output and compute metrics **after** judgments are entered, but they do not decide whether the model's reasoning is correct.

## Review each row

Open `analysis/human_review.csv` and fill these columns:

- `human_final_correct`: `yes` or `no`
- `human_reason_supported`: `yes` or `no`
- `human_unsupported_assumption`: `yes` or `no`
- `human_error_type`: optional short label from the list below
- `human_notes`: optional explanation in your own words

## Decision rules

### 1. Final answer

Mark `human_final_correct = yes` when the model's `FINAL_ANSWER` matches the case and the reference answer in meaning.

For binary cases, `binary_auto_match` is only a mechanical helper. Read the case and response before accepting it.

For `false_premise`, **do not require exact wording**. Accept a response when it either:
- explicitly rejects the unsupported premise when the premise is false, or
- gives the requested fact/entity/date when the premise is supported.

### 2. Reasoning support

Mark `human_reason_supported = yes` only when the model's `REASON` uses the decisive evidence in the case and does not contradict the final answer.

A correct final label with a wrong, reversed, or unsupported explanation should be:
- `human_final_correct = yes`
- `human_reason_supported = no`

### 3. Unsupported assumptions

Mark `human_unsupported_assumption = yes` if the response introduces information not present in the case and uses it to justify the answer.

## Suggested error labels

Use only when helpful:

- `wrong_final_answer`
- `reason_final_mismatch`
- `missed_temporal_order`
- `missed_contradiction`
- `assumed_missing_evidence`
- `accepted_false_premise`
- `causal_overreach`
- `unsupported_assumption`
- `truncated_generation`
- `other`

## Truncated output

`AR-MIS-04A` reached the 512-token generation cap. Review the visible answer normally, but keep `truncated_generation` in the notes/error type so the limitation is not hidden.

## After all 100 rows are reviewed

Run:

```bash
python src/summarize_human_review.py
```

The script refuses to compute metrics until `human_final_correct`, `human_reason_supported` and `human_unsupported_assumption` contain only `yes`/`no`, and `human_error_type` (`none` if no error) and `human_notes` are filled, for all 100 rows. It writes `analysis/summary_metrics.json` and `analysis/summary_metrics.csv`.
