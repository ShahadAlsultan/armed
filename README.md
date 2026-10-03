# ArabicMedReason

A controlled Arabic–English benchmark of matched, minimal-pair clinical reasoning cases. It tests whether a small
open-weight language model reasons about clinical evidence equally well in both languages.

## Research Question

> Do small frontier language models perform clinical reasoning consistently in Arabic compared with English,
> particularly when small changes in clinical evidence should change the correct conclusion?

## Motivation

Most medical evaluations of language models are in English and measure knowledge recall. A model can score
well by matching familiar patterns ("new drug + rash → drug reaction") without checking whether the evidence in
a case supports the conclusion. Arabic is spoken by hundreds of millions of people, but it is far less
represented in clinical NLP evaluation. If a model's reasoning is weaker or less stable in Arabic, an
English-only evaluation will not show it. Minimal pairs make this testable: if one decisive fact changes and the
answer does not, the model is not tracking the evidence.

## Benchmark Design

- **100 cases:** 50 Arabic (Modern Standard Arabic) and 50 English. Every Arabic case has one semantically
  equivalent English case.
- **25 minimal pairs** (A/B) in each language. The two variants differ in **one** decisive piece of evidence
  (a date, a time, one record entry), and that change flips the correct answer. The question is identical
  for A and B.
- **5 reasoning categories, 20 cases each:**

  | Category | What it tests |
  |---|---|
  | `temporal_reasoning` | Whether the order of events makes a claimed relationship possible |
  | `contradiction_detection` | Whether conflicting statements in a record are noticed |
  | `missing_evidence` | Whether required information is checked rather than assumed |
  | `false_premise` | Whether a question built on an unsupported assumption is rejected |
  | `causal_reasoning` | Whether the evidence (e.g. dechallenge/rechallenge) supports a causal claim |

- **Controls:** any rule needed to answer is stated inside the case. Binary categories are balanced at 5 Yes /
  5 No per language, and question polarity is counterbalanced.
- **Synthetic only:** all cases are invented and contain no patient data.

Schema: `data/evaluation.csv` contains `id, category, language, pair_id, scenario_id, case_text, question,
expected_answer, expected_reason, evidence_flip`. Only `case_text` and `question` are shown to the model.
`data/pilot.csv` is an earlier 10-item Arabic pilot used to debug the pipeline.

## Model and Inference Setup

| Setting | Value |
|---|---|
| Model | `Qwen/Qwen3.5-4B` (`AutoModelForMultimodalLM`, float16, no quantization) |
| Thinking | disabled (`enable_thinking=False`) |
| Decoding | greedy: `do_sample=False`, `num_beams=1`, `max_new_tokens=512`, `repetition_penalty=1.0` |
| Seed / batch size | 42 / 1 |
| Hardware | Kaggle, 2 × Tesla T4 |
| Software | Python 3.12.13, PyTorch 2.10.0+cu128, Transformers 5.18.0, Accelerate 1.15.0 |
| Model input | a fixed template containing only `case_text` and `question`; the model answers with `FINAL_ANSWER:` and `REASON:` |

The full configuration, prompt template and dataset SHA-256 are recorded in `results/evaluation_run_config.json`.

## Evaluation Method

- Reference answers, gold rationales, evidence-flip notes and all identifiers were hidden from the model. The
  notebook asserts that none of them appear in any prompt.
- Raw responses are preserved exactly in `results/evaluation_raw_outputs.jsonl`.
- All 100 responses were graded manually. The final grading decisions were reviewed by the applicant
  (`analysis/human_review.csv`; rubric in `analysis/review_guide.md`). Each response was graded on:
  - final-answer correctness;
  - whether the reason cites the decisive evidence and is consistent with the final answer;
  - unsupported assumptions;
  - an error type.
- **No LLM judge was used.** `src/summarize_human_review.py` only aggregates the human labels.

## Results

| Metric | Arabic | English | Overall |
|---|---:|---:|---:|
| Final-answer accuracy | 37/50 (74%) | 44/50 (88%) | 81/100 (81%) |
| Reason supported | 36/50 (72%) | 44/50 (88%) | 80/100 (80%) |
| Final correct **and** reason supported | 36/50 (72%) | 44/50 (88%) | 80/100 (80%) |
| Unsupported assumption | 3/50 (6%) | 2/50 (4%) | 5/100 (5%) |
| Minimal-pair consistency (A and B both correct) | 12/25 (48%) | 19/25 (76%) | — |

| Category | Arabic | English |
|---|---:|---:|
| temporal_reasoning | 6/10 | 8/10 |
| contradiction_detection | 8/10 | 9/10 |
| missing_evidence | 7/10 | 8/10 |
| false_premise | 9/10 | 10/10 |
| causal_reasoning | 7/10 | 9/10 |

Across the 50 matched scenarios: 35 both correct, 9 English only correct, 2 Arabic only correct, 4 both
incorrect (exact McNemar p = 0.065).

Full metrics: [`analysis/summary_metrics.json`](analysis/summary_metrics.json) and
[`analysis/summary_metrics.csv`](analysis/summary_metrics.csv). Analysis:
[`analysis/error_analysis.md`](analysis/error_analysis.md).

## Key Findings

- **Lower and less stable performance in Arabic.** English accuracy was equal or higher in every category.
  Minimal-pair consistency fell from 76% (English) to 48% (Arabic). With 50 matched scenarios the gap is
  descriptive, not statistically established.
- **Arabic negative-label bias.** All 12 Arabic errors on binary items were an expected نعم (Yes) answered
  لا (No). On expected-Yes items, Arabic accuracy was 8/20, against 20/20 on expected-No items (English: 16/20 and
  18/20). In 12 of the 20 Arabic binary pairs the model answered لا to both variants, so it did not update when
  the evidence flipped.
- **Answer–reason mismatch.** This was the most common error (8 cases, 6 of them Arabic). The explanation
  identifies the decisive evidence correctly, but the final label contradicts it.
- **False premises were handled well.** 19/20 were correct. The only failure (AR-FPR-05A) treated a
  *discussed* ICU transfer as an actual one.

## Example Failure Cases

- **AR-TMP-02A (answer–reason mismatch):** the reason says the blood sample (09:15) was drawn before the
  antibiotic (10:00), but the final answer is لا.
- **CON-01A, both languages (unsupported reconciliation):** the model explains away "no regular
  medications" vs "takes metformin" with a timing or scope difference that the case does not state.
- **MIS-05A, both languages (over-constraint):** an extra, non-required label field is treated as a reason
  the label fails the rule.
- **EN-TMP-05A (temporal order):** 9 June is treated as earlier than 7 June.
- **AR-MIS-04A (truncation):** the only response that hit the 512-token limit. It argues back and forth after
  an initial wrong answer.

## Limitations

- The cases are synthetic, short and controlled, and simpler than real clinical records.
- One model, one prompt template and one deterministic decoding setup were used, with thinking disabled.
- The evaluation is small: 100 cases, 10 per language × category cell. All results are descriptive.
- Arabic coverage is Modern Standard Arabic only, with no dialects.
- A single human reviewer graded the responses. Reasoning-quality judgments involve some subjectivity, and
  inter-annotator agreement was not measured.
- The items were not independently validated by clinicians.
- **No claim is made about real-world clinical safety or medical competence.**

## Repository Structure

```
ArabicMedReason/
├── README.md
├── requirements.txt
├── data/
│   ├── pilot.csv                       # 10-item Arabic pilot (pipeline debugging)
│   └── evaluation.csv                  # 100-case benchmark
├── notebooks/
│   └── evaluation.ipynb                # Kaggle inference notebook
├── src/
│   ├── validate_dataset.py             # schema and design checks
│   ├── prepare_human_review.py         # builds the review sheet from raw outputs
│   └── summarize_human_review.py       # aggregates the human review into metrics
├── results/
│   ├── raw_outputs.jsonl               # pilot raw outputs
│   ├── run_config.json                 # pilot run configuration
│   ├── evaluation_raw_outputs.jsonl    # 100 raw model responses
│   └── evaluation_run_config.json      # full-run configuration
└── analysis/
    ├── human_review.csv                # per-case human grading
    ├── review_guide.md                 # grading rubric
    ├── summary_metrics.json            # all computed metrics
    ├── summary_metrics.csv             # headline metrics (long format)
    └── error_analysis.md               # results and error analysis
```

## Reproducibility

Validation and analysis run locally with only pandas:

```bash
pip install -r requirements.txt
python src/validate_dataset.py data/evaluation.csv   # 100 rows, 25 pairs, 0 warnings expected
python src/summarize_human_review.py                 # regenerates analysis/summary_metrics.*
```

The saved outputs are the results of record, so re-running inference is not needed to check them. To
reproduce inference:
1. Open `notebooks/evaluation.ipynb` on Kaggle with GPU and Internet enabled, and `DATASET = "evaluation"`.
2. Run the install cell, restart the kernel, then run the rest of the notebook.

The notebook refuses to overwrite existing result files. `data_sha256` in the run config is computed on the
file with LF line endings.

## FIT Challenge

This project was prepared for the Fatima Institute of Technology technical challenge.

- It probes a potential blind spot in a frontier open-weight model: whether clinical reasoning that works in
  English holds up in Arabic when a single piece of evidence changes the answer.
- The evaluation uses controlled, matched Arabic–English minimal-pair cases with hidden references and manual
  grading.
- The raw outputs, run configuration, per-case grading, computed metrics and error analysis are all included in
  this repository.

## Hugging Face

Hugging Face dataset: https://huggingface.co/datasets/dataaishahad/ArabicMedReason

## Ethics

All cases are invented and contain no personal or identifiable information. The benchmark evaluates model
behaviour and is not intended for clinical use.
