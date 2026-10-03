# ArabicMedReason

A controlled Arabic–English benchmark of matched, minimal-pair clinical reasoning cases. It tests whether a small
open-weight language model reasons about clinical evidence equally well in both languages.

## Research Question

> Do small frontier language models perform clinical reasoning consistently in Arabic compared with English,
> particularly when small changes in clinical evidence should change the correct conclusion?

## Motivation

As an Arabic-speaking AI student, I wanted to know whether a model that looks competent in English stays
equally consistent when the same evidence is given in Arabic. I chose clinical cases because the answer often
depends on one specific fact (a date, a time, one record entry), and a model can reach the right label by
matching a familiar pattern ("new drug + rash → drug reaction") without checking that fact. I focused on small
evidence changes because accuracy alone cannot show whether a model is tracking the decisive fact. Minimal pairs
make this testable: if the one decisive fact changes and the answer does not, the model is not following the
evidence.

### Why This Gap Matters

Many standard medical benchmarks report final-answer accuracy. They rarely include matched Arabic and English
versions of the same case, rarely change a single piece of evidence to flip the answer, and do not check whether
the stated reason agrees with the final label. An English-only evaluation that scores only the final answer could
therefore miss instability that appears only in Arabic. This benchmark tests these three things together.

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
- Per-case outputs were reviewed using a structured rubric (`analysis/review_guide.md`). Each case was labelled
  in `analysis/human_review.csv` on:
  - final-answer correctness;
  - whether the reason cites the decisive evidence and is consistent with the final answer;
  - unsupported assumptions;
  - an error type.
- Aggregate metrics were then computed from these labels. **No LLM judge was used.**
  `src/summarize_human_review.py` only aggregates the review labels.

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

- **Lower and less stable performance in Arabic.** In this evaluation, Arabic accuracy was 74% against 88% for
  English, and English was higher in every category. Minimal-pair consistency was 48% in Arabic against 76% in
  English. Across the 50 matched scenarios the difference did not reach statistical significance (exact McNemar
  p = 0.065), so the observed gap is descriptive.
- **Arabic expected-Yes items failed disproportionately.** All 12 Arabic errors on binary items were an expected
  نعم (Yes) answered لا (No). On expected-Yes items, Arabic accuracy was 8/20, against 20/20 on expected-No items
  (English: 16/20 and 18/20). In 12 of the 20 Arabic binary pairs the model gave the same label to both variants,
  so it did not update when the evidence flipped. This suggests a negative-label bias in Arabic for this model and
  prompt.
- **Answer–reason mismatch was the most common error.** It occurred in 8 cases, 6 of them Arabic. The
  explanation identifies the decisive evidence, but the final label contradicts it.
- **False premises were handled comparatively well.** 19/20 were correct. The only failure (AR-FPR-05A)
  treated a *discussed* ICU transfer as an actual one.

## What I Found Most Interesting

What stood out most to me was that many failures were not cases where the model misread the evidence. In the
8 mismatch cases it described the decisive fact correctly and then gave the opposite final label, and all 8
expected Yes. This makes the gap look less like missing knowledge and more like instability between the
reasoning and the answer it selects, which a final-answer-only score would hide.

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
- The labels come from one review pass with no second reviewer. Reasoning-quality judgments involve some
  subjectivity, and inter-annotator agreement was not measured.
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
│   ├── evaluation_raw_outputs.jsonl    # 100 raw model responses
│   └── evaluation_run_config.json      # full-run configuration
├── analysis/
│   ├── human_review.csv                # per-case review labels
│   ├── review_guide.md                 # grading rubric
│   ├── summary_metrics.json            # all computed metrics
│   ├── summary_metrics.csv             # headline metrics (long format)
│   └── error_analysis.md               # results and error analysis
└── hf_submission/                      # Hugging Face dataset card and copies of the released files
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

This project was prepared for the Fatima Institute of Technology "Blind Spots of Frontier Models" challenge.

**Blind spot.** Small frontier models can look competent on standard accuracy benchmarks while their evidence
tracking, minimal-pair robustness and answer–reason consistency are weaker in Arabic than in matched English
cases. In this evaluation of `Qwen/Qwen3.5-4B`, the Arabic results were lower on all three. The evidence is
controlled matched minimal pairs with hidden references and rubric-based per-case labels. The raw outputs, run
configuration, per-case labels, metrics and error analysis are all in this repository.

**Proposed path forward (not tested here):**
- Build Arabic–English matched minimal-pair data so that both languages get the same evidence-sensitive signal.
- Train contrastively on evidence flips, so the model is rewarded for changing its answer when the decisive fact
  changes.
- Supervise answer–reason consistency, so the final label must follow from the stated reason.
- Balance Yes/No polarity in Arabic training and evaluation data to counter the negative-label bias seen here.
- Extend Arabic instruction tuning across Modern Standard Arabic and dialects.
- Add calibration or abstention when the reasoning and the answer disagree, instead of emitting a confident label.

## Hugging Face

Hugging Face dataset: https://huggingface.co/datasets/dataaishahad/ArabicMedReason

## Ethics

All cases are invented and contain no personal or identifiable information. The benchmark evaluates model
behaviour and is not intended for clinical use.
