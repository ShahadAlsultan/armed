---
pretty_name: ArabicMedReason
language:
- ar
- en
size_categories:
- n<1K
tags:
- clinical-reasoning
- arabic
- multilingual
- evaluation
- minimal-pairs
- synthetic
---

# ArabicMedReason

A controlled Arabic–English benchmark of matched, minimal-pair clinical reasoning cases. It tests whether a small
open-weight language model (`Qwen/Qwen3.5-4B`) reasons about clinical evidence equally well in both languages.
Prepared for the Fatima Institute of Technology (FIT) technical challenge.

## Research Question

> Do small frontier language models perform clinical reasoning consistently in Arabic compared with English,
> particularly when small changes in clinical evidence should change the correct conclusion?

## Benchmark

- 100 synthetic cases: 50 Arabic (Modern Standard Arabic) and 50 semantically matched English cases.
- 25 minimal pairs (A/B) per language. One decisive fact differs between A and B and flips the correct answer.
- 5 categories with 20 cases each: `temporal_reasoning`, `contradiction_detection`, `missing_evidence`,
  `false_premise`, `causal_reasoning`.
- Columns: `id, category, language, pair_id, scenario_id, case_text, question, expected_answer,
  expected_reason, evidence_flip`. Only `case_text` and `question` were shown to the model.

## Setup

`Qwen/Qwen3.5-4B`, float16, thinking disabled, greedy decoding (`do_sample=False`, `num_beams=1`),
`max_new_tokens=512`, seed 42, batch size 1, Kaggle 2 × Tesla T4. The full configuration and prompt template are
in `results/evaluation_run_config.json`.

All responses were graded manually, and the final grading decisions were reviewed by the applicant. Reference
answers were hidden from the model, raw outputs are preserved exactly, and no LLM judge was used.

## Results

| Metric | Arabic | English | Overall |
|---|---:|---:|---:|
| Final-answer accuracy | 37/50 (74%) | 44/50 (88%) | 81/100 (81%) |
| Reason supported | 36/50 (72%) | 44/50 (88%) | 80/100 (80%) |
| Minimal-pair consistency (A and B both correct) | 12/25 (48%) | 19/25 (76%) | — |

Matched scenarios: 35 both correct, 9 English only correct, 2 Arabic only correct, 4 both incorrect
(exact McNemar p = 0.065).

Key observations:

- Arabic accuracy was lower in every category. Minimal-pair consistency fell from 76% (English) to 48% (Arabic).
- All 12 Arabic errors on binary items were an expected نعم (Yes) answered لا (No).
- The most common error was answer–reason mismatch (8 cases, 6 Arabic): the explanation was correct, but the
  final label contradicted it.

See `analysis/error_analysis.md` for the full analysis and limitations.

## Files

```
data/evaluation.csv                  100-case benchmark
results/evaluation_raw_outputs.jsonl raw model responses (one JSON record per case)
results/evaluation_run_config.json   model, decoding, environment and dataset hash
analysis/summary_metrics.json        all computed metrics
analysis/summary_metrics.csv         headline metrics (long format)
analysis/error_analysis.md           results and error analysis
notebooks/evaluation.ipynb           Kaggle inference notebook
```

The validation and summary scripts are in the project code repository.

Code repository: TO_BE_ADDED
Hugging Face project/bucket: TO_BE_ADDED

## Limitations

The cases are synthetic, and only one model, one prompt and one decoding setup were evaluated. With 100 cases
and a single human reviewer, the results are descriptive. This work makes no claim about real-world clinical
safety or medical competence.
