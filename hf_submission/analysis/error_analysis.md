# Error Analysis

All numbers below are computed by `src/summarize_human_review.py` from the human review in
`analysis/human_review.csv` and are stored in `analysis/summary_metrics.json` /
`analysis/summary_metrics.csv`. Case IDs refer to `data/evaluation.csv` and
`results/evaluation_raw_outputs.jsonl`.

## 1. Evaluation Overview

- **Model:** `Qwen/Qwen3.5-4B` (float16, no quantization), run `20261002T132459Z`.
- **Dataset:** 100 synthetic clinical reasoning cases: 50 Arabic (Modern Standard Arabic) and 50 English.
  Every Arabic case has one semantically equivalent English case (`scenario_id`).
- **Minimal pairs:** 25 pairs (A/B), each present in both languages. Within a pair, one decisive piece of
  evidence differs and flips the correct answer.
- **Categories (20 cases each):** `temporal_reasoning`, `contradiction_detection`, `missing_evidence`,
  `false_premise`, `causal_reasoning`. The four binary categories are balanced at 5 Yes / 5 No answers per
  language.
- **Generation:** thinking disabled, greedy decoding (`do_sample=False`, `num_beams=1`), `max_new_tokens=512`,
  seed 42, batch size 1, Kaggle with 2 × Tesla T4.

## 2. Evaluation Method

- The prompt contained only `case_text` and `question` inside a fixed template. It asked for
  `FINAL_ANSWER:` and `REASON:` in the language of the case.
- `expected_answer`, `expected_reason`, `evidence_flip` and all identifiers were hidden from the model. The
  notebook asserts that none of them appear in any rendered prompt.
- Raw responses are stored unmodified in `results/evaluation_raw_outputs.jsonl`.
- Per-case outputs were reviewed using a structured rubric (`analysis/review_guide.md`), and aggregate metrics
  were computed from these labels. Each row records:
  - `human_final_correct`: whether `FINAL_ANSWER` matches the reference. For false-premise items, an explicit
    rejection of an unsupported premise counts as correct; exact wording is not required.
  - `human_reason_supported`: whether `REASON` uses the decisive evidence in the case **and** is consistent with
    the final answer. A response whose explanation is correct but contradicts its own final answer is marked `no`.
  - `human_unsupported_assumption`: whether the response relies on information that is not in the case.
  - `human_error_type` and `human_notes`: a short error label and an explanation.
- If a response contained more than one `FINAL_ANSWER` line, the **first** one was graded (3 cases; see §8).
- No LLM judge was used. The scripts only parse and aggregate. `binary_auto_match` in the review sheet is a
  mechanical string comparison that helped the reviewer; it is not a grade.

## 3. Quantitative Results

### Overall final-answer accuracy

| | n | Correct | Accuracy |
|---|---:|---:|---:|
| Arabic | 50 | 37 | 74% |
| English | 50 | 44 | 88% |
| **Overall** | 100 | 81 | 81% |

### Accuracy by category and language

| Category | Arabic | English | Both languages |
|---|---:|---:|---:|
| temporal_reasoning | 6/10 | 8/10 | 14/20 (70%) |
| contradiction_detection | 8/10 | 9/10 | 17/20 (85%) |
| missing_evidence | 7/10 | 8/10 | 15/20 (75%) |
| false_premise | 9/10 | 10/10 | 19/20 (95%) |
| causal_reasoning | 7/10 | 9/10 | 16/20 (80%) |

English accuracy is equal to or higher than Arabic accuracy in all five categories.

### Reasoning quality and unsupported assumptions

| | Reason supported | Final correct **and** reason supported | Unsupported assumption |
|---|---:|---:|---:|
| Arabic | 36/50 (72%) | 36/50 (72%) | 3/50 (6%) |
| English | 44/50 (88%) | 44/50 (88%) | 2/50 (4%) |
| **Overall** | 80/100 (80%) | 80/100 (80%) | 5/100 (5%) |

Reason supported, by category: temporal 13/20, contradiction 17/20, missing evidence 15/20,
false premise 19/20, causal 16/20.

Every response with a supported reason also had a correct final answer. The single correct answer without a
supported reason is AR-TMP-05A, where the right label came with a misordered timeline. Eight further responses
gave an explanation that pointed to the correct evidence but then a wrong final label. Under the rubric these
count as neither correct nor reason-supported, and they are tracked separately as answer–reason mismatches (§5).

### Yes/No polarity (binary categories, 40 items per language)

| | Expected Yes: correct | Expected No: correct | Model answered No |
|---|---:|---:|---:|
| Arabic | 8/20 (40%) | 20/20 (100%) | 32/40 (80%) |
| English | 16/20 (80%) | 18/20 (90%) | 22/40 (55%) |

### Minimal-pair consistency (both A and B correct)

| Category | Arabic | English |
|---|---:|---:|
| temporal_reasoning | 1/5 | 3/5 |
| contradiction_detection | 3/5 | 4/5 |
| missing_evidence | 2/5 | 3/5 |
| false_premise | 4/5 | 5/5 |
| causal_reasoning | 2/5 | 4/5 |
| **Overall** | **12/25 (48%)** | **19/25 (76%)** |

### Cross-language matched scenarios (50 scenarios)

| Outcome | Count |
|---|---:|
| Both correct | 35 |
| Arabic only correct | 2 |
| English only correct | 9 |
| Both incorrect | 4 |

Exact McNemar test on the 11 discordant scenarios (2 vs 9): two-sided p = 0.065.

## 4. Main Error Patterns

Error labels from the human review (20 rows carry a label other than `none`; a row may have several labels):

| Label | Arabic | English | Total |
|---|---:|---:|---:|
| answer_reason_mismatch | 6 | 2 | 8 |
| format_self_correction | 2 | 1 | 3 |
| temporal_order_error | 1 | 1 | 2 |
| unsupported_reconciliation | 1 | 1 | 2 |
| overconstraint_extra_item | 1 | 1 | 2 |
| evidence_extraction_error | 1 | 0 | 1 |
| false_premise_acceptance | 1 | 0 | 1 |
| reasoning_contradiction | 1 | 0 | 1 |
| unsupported_medical_assumption | 1 | 0 | 1 |
| unsupported_requirement | 1 | 0 | 1 |
| truncated_output | 1 | 0 | 1 |
| causal_temporal_error | 0 | 1 | 1 |
| unsupported_assumption | 0 | 1 | 1 |

**Arabic–English gap.** The model was correct on 37/50 Arabic and 44/50 English cases, and English was at
least as accurate in every category. Among the 11 matched scenarios where the two languages disagree,
English was correct in 9. With 50 scenarios this is a descriptive difference: the exact McNemar test does not
reach p < 0.05 (p = 0.065).

**Yes/No polarity.** This is the clearest pattern in the data. Every Arabic error on a binary item (12/12)
was an expected **نعم** (Yes) answered **لا** (No). Arabic accuracy was 20/20 when the expected answer was No and
8/20 when it was Yes. The model answered لا on 32 of 40 Arabic binary items, against 22 of 40 English
binary items answered No. Question polarity was counterbalanced (e.g. "contradict?" vs "consistent?"), so a
"No" here does not always mean the same clinical judgment. The skew therefore points to a bias toward the
negative label in Arabic, not a bias toward one clinical conclusion. In English, the errors were split
(4 expected-Yes, 2 expected-No).

**Answer–reason mismatch.** This was the most frequent error label (8 rows: 6 Arabic, 2 English). In all 8,
the expected answer was Yes and the model answered No. It is discussed in §5.

**Temporal-order mistakes.** These were infrequent. Two final answers were wrong because dates were put in the
wrong order: AR-TMP-01B (correct dates, reversed conclusion) and EN-TMP-05A (treats 9 June as earlier than
7 June). AR-TMP-05A reached the correct label with an explanation that made the same 7/9 June ordering error.
Most of the Arabic temporal errors were answer–reason mismatches (AR-TMP-02A, -03A, -05B), not misread
timelines.

**Unsupported reconciliation of contradictions.** In scenario CON-01A, the model failed in both languages. It
explained the conflict between "no regular medications" and "takes metformin" with record timing or scope
that the case does not state. The Arabic response later corrected itself (§8).

**Over-constraining missing-evidence questions.** In scenario MIS-05A, the model failed in both languages. It
treated an extra, non-required field (ward) as a reason the label did not meet the rule. AR-MIS-04A added
requirements that were not in the rule (patient name/history). AR-MIS-01A claimed the weight was missing
although the case states it.

**False-premise failures.** These were rare (1/20). AR-FPR-05A treated a *discussed* ICU transfer as an actual
transfer and returned a date. The English counterpart rejected the premise correctly. All other false-premise
items were handled correctly in both languages, including the B variants, where the premise holds and an entity
must be returned.

**Causal reasoning mistakes.** These were few and varied. AR-CAU-02A relied on outside medical knowledge ("seven
days is usually too short"), although the prompt restricted the model to the case. EN-CAU-02B accepted a
causal link even though the medication started after the swelling. AR-CAU-04B and AR-CAU-05A are
answer–reason mismatches.

Unsupported assumptions were uncommon overall (5/100: 3 Arabic, 2 English).

## 5. Answer–Reason Mismatch

In 8 responses (AR-TMP-02A, AR-TMP-03A, AR-TMP-05B, AR-CON-05B, AR-CAU-04B, AR-CAU-05A, EN-TMP-03A,
EN-MIS-04A), the `REASON` stated the decisive evidence correctly, but `FINAL_ANSWER` gave the opposite
label. Representative cases:

- **AR-TMP-02A:** the reason states that the blood sample (09:15) was drawn before the first antibiotic dose
  (10:00), but the final answer is لا.
- **AR-CON-05B:** the reason totals the transfusions to 3 units and says the two records match, but the final
  answer to "are they consistent?" is لا.
- **AR-CAU-04B:** the reason reports pain on 6 of 7 milk days against 1 of 7 non-milk days and calls milk the
  likely cause, but the final answer is لا.
- **EN-TMP-03A:** the reason says the low reading (14:00) came after the infusion started (12:00), but the final
  answer is No.

All 8 mismatches have an expected answer of Yes and a final answer of No, and 6 of the 8 are Arabic. In this
sample, many errors scored as wrong final answers reflect a failure to map correct reasoning onto the output
label, not a misreading of the case. Because the rubric requires the reason to be consistent with the final
answer, these 8 rows are scored `human_reason_supported = no`. They carry the `answer_reason_mismatch` label, so
the error can be distinguished from a genuine misreading of the evidence.

## 6. Minimal-Pair Robustness

A pair is consistent only when both A and B are answered correctly, i.e. when the model updates its
conclusion after the single evidence flip.

- **English:** 19/25 pairs (76%) were consistent.
- **Arabic:** 12/25 pairs (48%) were consistent. The weakest category was temporal reasoning (1/5).

Among the 20 binary pairs, the model gave the same label to both variants in 12 Arabic pairs and 6 English
pairs. Such a pair cannot be fully correct, because the evidence flip reverses the expected label. In all 12
Arabic cases the shared label was لا. So in Arabic, most pair failures happened because the model did not move
from No to Yes when the evidence required it. Random errors on either side of the flip were not the main cause.
False-premise pairs were the most robust in both languages (Arabic 4/5, English 5/5).

## 7. Cross-Language Consistency

The final-answer outcome was the same in both languages for 39 of 50 scenarios (35 both correct, 4 both
incorrect).

- **English only correct (9):** TMP-01B, TMP-02A, TMP-05B, CON-05B, MIS-01A, FPR-05A, CAU-02A, CAU-04B, CAU-05A.
  Eight of these have an expected answer of Yes. The only exception is FPR-05A, a false-premise item.
- **Arabic only correct (2):** TMP-05A and CAU-02B. In both, the English response made a temporal error
  (treating a later date as earlier, or accepting causation when the drug started after the symptom). AR-TMP-05A
  reached the correct label with a flawed explanation.
- **Both incorrect (4):** CON-01A (unsupported reconciliation), MIS-04A (extra requirements / self-correction),
  MIS-05A (over-constraint on an extra field) and TMP-03A (answer–reason mismatch in both languages). These look
  like weaknesses in the item type itself, not language effects.

The same reasoning problem therefore tends to fail in Arabic in one direction: when the correct answer is
affirmative.

## 8. Truncation / Generation Anomalies

- **Truncation:** one response hit `max_new_tokens = 512` without an end-of-sequence token: **AR-MIS-04A**
  (512 tokens; the next longest response was 365 tokens). It opens with `FINAL_ANSWER: لا` and then argues
  back and forth about whether the answer should be Yes, until generation stops. The reviewer graded the
  visible first answer as incorrect, with labels `unsupported_requirement;truncated_output`. The error was
  recorded because the stated answer is wrong, not because the output was truncated.
- **Multiple `FINAL_ANSWER` lines:** AR-CON-01A, AR-CAU-05A and EN-MIS-04A each give an initial answer, reason
  at length, and then output a second `FINAL_ANSWER` that reverses the first. Following the grading rule in §2,
  the first answer was graded, so all three are counted as incorrect. In each case the second answer matches
  the reference label. Under a "last answer" rule, accuracy would be 39/50 for Arabic and 45/50 for English.
  This is a sensitivity note, not a separate grading.
- **Non-standard answer text:** EN-FPR-01A answered `FINAL_ANSWER: None`. The explanation shows that this
  means "no medication was stopped", and it was graded as a correct premise rejection.

## 9. Limitations

- All cases are synthetic, short and controlled. They are simpler than real clinical records.
- Only one model, `Qwen/Qwen3.5-4B`, was evaluated, with thinking disabled.
- One prompt template and one deterministic decoding setup were used. The results may change with other
  prompts, answer formats or sampling.
- The evaluation is small: 100 cases, 25 pairs per language and 10 cases per language × category cell. All
  differences are descriptive, and per-cell percentages move 10 points with a single case.
- The Arabic items are Modern Standard Arabic only, with no dialects or other registers.
- The labels come from one review pass with no second reviewer. Judgments about reasoning support and unsupported assumptions
  involve some subjectivity, and inter-annotator agreement was not measured.
- The items have not been independently reviewed by clinicians or professional Arabic linguists.
- These results make no claim about real-world clinical safety or medical competence.

## 10. Path Forward

- Expand to a larger multilingual benchmark with more pairs per category, so that language and category effects
  can be tested with adequate statistical power.
- Evaluate more models and sizes, including thinking-enabled modes, to see whether the Arabic negative-label
  bias is specific to this model.
- Add Arabic dialects and other registers, and have clinicians and native speakers review the items.
- Use structured answer formats, e.g. a constrained label field or a JSON schema, to separate label-mapping
  errors from reasoning errors.
- Add automatic answer–reason consistency checks that flag responses whose explanation contradicts the label,
  for human follow-up.
- Study calibration and abstention: let the model mark items as undecidable, and measure confidence on flipped
  pairs.
- Strengthen minimal-pair testing with multiple flips per scenario, paraphrased questions, and swapped question
  polarity on the same evidence, to isolate label bias from evidence sensitivity.
- Use two independent reviewers and report inter-annotator agreement.
