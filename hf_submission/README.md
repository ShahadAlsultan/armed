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

## Motivation

As an Arabic-speaking AI student, I wanted to know whether a model that looks competent in English stays
equally consistent when the same evidence is given in Arabic. I focused on small evidence changes because
accuracy alone cannot show whether a model is tracking the decisive fact. Many standard medical benchmarks score
only the final answer. They rarely include matched Arabic and English cases, rarely flip a single piece of
evidence, and do not check whether the stated reason agrees with the label. An English-only evaluation that
scores only the final answer could therefore miss instability that appears only in Arabic.

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

Per-case outputs were reviewed using a structured rubric covering final-answer correctness, reason support,
unsupported assumptions and error type. Aggregate metrics were then computed from these labels. Reference
answers were hidden from the model, raw outputs are preserved exactly, and no LLM judge was used.

## Results

| Metric | Arabic | English | Overall |
|---|---:|---:|---:|
| Final-answer accuracy | 37/50 (74%) | 44/50 (88%) | 81/100 (81%) |
| Reason supported | 36/50 (72%) | 44/50 (88%) | 80/100 (80%) |
| Minimal-pair consistency (A and B both correct) | 12/25 (48%) | 19/25 (76%) | — |

Matched scenarios: 35 both correct, 9 English only correct, 2 Arabic only correct, 4 both incorrect
(exact McNemar p = 0.065).

Key observations (descriptive; the matched-scenario difference did not reach statistical significance):

- Arabic accuracy was lower in every category. Minimal-pair consistency was 48% in Arabic against 76% in English.
- All 12 Arabic errors on binary items were an expected نعم (Yes) answered لا (No). Arabic accuracy was 8/20 on
  expected-Yes items against 20/20 on expected-No items.
- The most common error was answer–reason mismatch (8 cases, 6 Arabic): the explanation identified the decisive
  evidence, but the final label contradicted it.
- False-premise items were handled comparatively well (19/20).

See `analysis/error_analysis.md` for the full analysis and limitations.

## Blind Spot and Proposed Path Forward

**Blind spot.** Small frontier models can look competent on standard accuracy benchmarks while their evidence
tracking, minimal-pair robustness and answer–reason consistency are weaker in Arabic than in matched English
cases.

**Proposed path forward (not tested here):** Arabic–English matched minimal-pair data; contrastive training on
evidence flips; supervision for answer–reason consistency; balanced Yes/No polarity; Arabic instruction tuning
across Modern Standard Arabic and dialects; and calibration or abstention when the reasoning and the answer
disagree.

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

Code repository: https://github.com/ShahadAlsultan/armed
Hugging Face dataset: https://huggingface.co/datasets/dataaishahad/ArabicMedReason

## Limitations

The cases are synthetic, and only one model, one prompt and one decoding setup were evaluated. With 100 cases
and a single review pass with no second reviewer, the results are descriptive. This work makes no claim about real-world clinical
safety or medical competence.
