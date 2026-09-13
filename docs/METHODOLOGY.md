# ClaimLens Methodology Log

This file records evaluation decisions and changes **at the time they were made**, so the
Stage 11 comparison (naive baseline vs. ClaimLens) can be audited afterwards. Entries are
added in order and not rewritten later; a correction gets its own new entry.

## Fixed evaluation settings

| Decision | Value | Fixed at | Where |
|---|---|---|---|
| Benchmark | 40 synthetic claims (16 fraud / 24 legitimate; 14 easy / 14 ambiguous / 12 hard), seed 42 | Stage 2 | `backend/app/synthetic/generate_claims.py` |
| Label isolation | Ground truth is removed by one shared `sanitize_claim()`; tests check that no label, difficulty tag or signal name reaches any agent input | Stage 3 | `backend/app/agents/sanitize.py`, `backend/tests/` |
| Model | `openai/gpt-oss-120b` on Groq, for the baseline and every pipeline agent | Stage 4 | `backend/app/agents/llm_client.py` |
| Generation settings | temperature 1.0, reasoning_effort "medium", max_completion_tokens 4096, JSON output | Stage 4 | `GENERATION_SETTINGS` in `llm_client.py` |
| Shared inputs | Sanitized claim + Stage 3 evidence, rendered by `build_case_file()`; personal identifiers (name, phone, email, date of birth) removed for every agent | Stage 4 | `backend/app/agents/case_file.py` |
| Baseline HIGH-confidence band | confidence >= 80 — **fixed before any results were observed** | Stage 4 | `BASELINE_HIGH_CONFIDENCE_THRESHOLD` |

## Change log

### 2026-09-13 — Case-file conventions made explicit (start of Stage 5)

**What was observed.** During Stage 4 testing, the naive baseline was run on a fixed 5-claim
sample (CLM-0030, CLM-0019, CLM-0006, CLM-0027, CLM-0035). On CLM-0027, a legitimate claim, it
answered DENY because the claimed amount ($4,841.89) was higher than the vehicle's estimated
value minus the deductible. On CLM-0019, a fraud claim, it answered DENY for the same reason
and did not mention the actual inconsistency (theft cover added 5 days before the theft). The
case file never said whether the claimed amount is before or after the deductible, so a
careful reader could reasonably assume either.

**What changed.** The shared `CASE_FILE_GUIDE` now states these conventions explicitly
(previously all were unstated):

1. `claim_amount` is the total loss **before** the deductible; the insurer subtracts the
   deductible when paying.
2. `claim_amount` includes parts, labor and any sales tax. All amounts are US dollars; all day
   counts are calendar days.
3. `estimated_value` is the vehicle's actual cash value just before the loss (what a total loss
   is settled on) — not replacement cost and not a trade-in offer.
4. `policy.start_date` is when the policy first took effect with this insurer, not the latest
   renewal.
5. `coverages` are those in force on the incident date, with what Collision, Comprehensive and
   Liability each pay for.
6. `dwelling_coverage` / `contents_coverage` are maximum payouts for the building / belongings.
7. The incident description and damage are the policyholder's unverified account.
8. `supporting_documents` are document titles only; an unlisted document was not submitted.
9. `claim_history` covers this insurer and an industry-wide database of other insurers; an
   empty list means none found anywhere. `words_shared_with_this_claim` is a mechanical word
   overlap, not a similarity judgement.
10. `location` compares city and state only (no distance).
11. `documents_mentioned_but_absent` comes from keyword rules covering common document types, so
    an empty list does not prove the file is complete.
12. Weather is measured at the incident city's coordinates (not the exact street), with units
    stated; `status: "unavailable"` means the lookup failed, not that the weather was calm.

The baseline's existing review instructions were moved, word for word, into a shared
`REVIEW_GUIDANCE` constant so the Stage 5 debate agents receive exactly the same instructions.

**Why this is a specification fix, not metric tuning.**
- It changes only the description of the inputs, in one shared constant that the baseline and
  every pipeline agent (Prosecutor, Defender, Judge) receive identically. A test enforces that.
- The HIGH-confidence threshold stays at 80. The model, generation settings, benchmark data,
  labels and the 5-claim sample are unchanged.
- No results for the 40-claim benchmark existed for either system when this change was made.

**Stated honestly.** The ambiguity was noticed by reading baseline outputs on a 5-claim sample.
That is the reason for writing this entry now rather than reconstructing it later.

**Consequences.** The Stage 4 sample is re-run with the clarified guide. The original results
are kept unchanged in `backend/data/stage4_baseline_sample_v1_before_case_file_fix.json`, and
the raw requests and responses for both runs are in `backend/data/llm_logs/`.

### 2026-09-13 — Debate Judge confidence levels tied to the baseline's band (Stage 5, before any debate results)

The Judge reports confidence as HIGH / MEDIUM / LOW. If HIGH were defined more strictly than the
baseline's band, ClaimLens would show fewer "confidently wrong" answers simply because its bar
was higher. To keep the Stage 11 comparison like-for-like, the Judge prompt defines:

- **HIGH**: expected to be correct at least **80** times out of 100 on similar claims — the
  same number as the baseline's pre-registered threshold (the prompt is built from that
  constant, and a test enforces it);
- **MEDIUM**: roughly 65–79 times out of 100;
- **LOW**: fewer than 65 times out of 100.

This was decided before any debate output had been produced.

### 2026-09-13 — Decision definition separated from payout (Stage 5, second correction)

**Result of the first re-run.** With the clarified case-file guide, the 5-claim baseline sample
gave (confidence in brackets; HIGH = 80 or more):

| Claim | Is fraud | Original run (v1) | After guide fix (v2) |
|---|---|---|---|
| CLM-0030 | yes | DENY (75) — correct | DENY (85) — correct |
| CLM-0019 | yes | DENY (70) — correct, but for the deductible misreading | APPROVE (85) — **wrong** |
| CLM-0006 | no | APPROVE (85) — correct | DENY (90) — **wrong** |
| CLM-0027 | no | DENY (70) — **wrong** (deductible misreading) | APPROVE (85) — correct |
| CLM-0035 | yes | DENY (80) — correct | DENY (85) — correct |

**What was observed.** On CLM-0006 the baseline agreed the loss was genuine and documented, but
answered DENY because the claimed amount ($2,335.09) is below the $2,500 deductible, so "the
claim cannot be paid as submitted". The shared decision definition had read: "APPROVE = … should
be paid" / "DENY = … should not be paid as submitted". That wording mixes two different
questions — whether the claim is genuine, and whether money will be paid. Only 1 of the 40
benchmark claims (CLM-0006) has a claimed amount at or below its deductible.

**Missed in the first sweep.** The previous entry's review of conventions did not catch this
wording. It was found only when the re-run output was read.

**What changed.** `DECISION_DEFINITIONS` (shared by the baseline and the Judge, and seen by the
Prosecutor and Defender) now reads:

> APPROVE = the claim describes a genuine loss, as reported.
> DENY = the claim is fraudulent or materially misrepresented.
> The decision is only about whether the claim is genuine. Deductibles, coverage limits and payout
> amounts are applied separately when a claim is paid, so a genuine loss is APPROVE even if the
> deductible means little or nothing will be paid.

A test enforces this wording and that the baseline and Judge prompts contain it.

**Deliberately not changed.** CLM-0019 became a confidently wrong APPROVE after the first fix. That
is the baseline's own judgement on correctly described inputs, not an input ambiguity, so nothing
was changed in response to it.

**Unchanged.** Threshold 80, model, generation settings, benchmark data and labels, the sample.

**Consequences.** The v2 results are kept in
`backend/data/stage4_baseline_sample_v2_after_first_guide_fix.json`; the sample is re-run again
and the current results are in `backend/data/stage4_baseline_sample.json`.

**From here on** the input description and decision definitions are treated as frozen for the
evaluation. Any further change needs its own entry in this log and a re-run of every result it
affects.

### 2026-09-13 — Baseline sample after both corrections (v3, current)

Same 5 claims, same model and settings, threshold still 80. Results in
`backend/data/stage4_baseline_sample.json`.

| Claim | Is fraud | v1 (original) | v2 (guide fix) | v3 (guide + definition fix) |
|---|---|---|---|---|
| CLM-0030 | yes | DENY (75) ✓ | DENY (85) ✓ | DENY (80) ✓ |
| CLM-0019 | yes | DENY (70) ✓* | APPROVE (85) ✗ | APPROVE (85) ✗ — confidently wrong |
| CLM-0006 | no | APPROVE (85) ✓ | DENY (90) ✗ | APPROVE (85) ✓ |
| CLM-0027 | no | DENY (70) ✗ | APPROVE (85) ✓ | APPROVE (80) ✓ |
| CLM-0035 | yes | DENY (80) ✓ | DENY (85) ✓ | DENY (75) ✓ |

\* correct decision reached through the deductible misreading, not the actual inconsistency.

v3: 4 of 5 correct; 4 of 5 answers in the HIGH band; one confidently wrong answer (CLM-0019, which
cites the Comprehensive coverage added 5 days before the theft as proof coverage was in force).
Five claims is far too few to estimate accuracy or calibration; this only confirms the inputs are
now read as intended. Token use: 11,366 tokens for 5 calls (about 2,270 per call, up from about
1,800 before the longer guide).

### 2026-09-13 — Stage 5 debate sample and measured token budget

**Sample.** CLM-0027 (legitimate, the claim the original baseline got wrong), CLM-0035 (fraud) and
CLM-0019 (fraud), chosen by ID before running. One debate per claim (Prosecutor → Defender →
Judge); the Stage 6 order-swapped Judge call does not exist yet. Full transcripts and evidence
are stored in `backend/data/stage5_debate_sample.json`.

| Claim | Is fraud | Baseline (v3) | Debate Judge |
|---|---|---|---|
| CLM-0027 | no | APPROVE (80) ✓ | APPROVE, HIGH ✓ |
| CLM-0035 | yes | DENY (75) ✓ | DENY, MEDIUM ✓ |
| CLM-0019 | yes | APPROVE (85) ✗ | APPROVE, HIGH ✗ — confidently wrong |

Three claims say nothing about which system is better. On CLM-0019 the Prosecutor raised the
right point (Comprehensive cover added 5 days before the theft); the Defender answered that
policy changes are permitted and the Judge accepted that. Nothing was changed in response.

**Measured tokens** (Groq `usage` fields, not estimates):

| Claim | Prosecutor | Defender | Judge | Debate total |
|---|---|---|---|---|
| CLM-0027 | 3,601 | 4,963 | 4,285 | 12,849 |
| CLM-0035 | 3,020 | 4,237 | 3,789 | 11,046 |
| CLM-0019 | 3,308 | 3,849 | 3,600 | 10,757 |
| **Average** | **3,310** | **4,350** | **3,891** | **11,551** |

Baseline average (v3 sample): 2,273 tokens per claim.

**Stage 11 projection from these measurements.** Pipeline per claim = Prosecutor + Defender +
2 × Judge = 15,442 tokens. The second Judge call (Stage 6) is the only estimated term, taken as
equal to the measured Judge call because its input is the same content in a different order.
40 × (2,273 + 15,442) = **708,608 tokens and 200 accepted requests**, which needs at least
**89 minutes** at 8,000 tokens per minute. With `FULL_DOUBLE_DEBATE` it would be about 1,015,000
tokens, 280 requests and at least 127 minutes.

**Rate limiting observed.** 3 of the 12 requests sent were rejected with HTTP 429 (tokens per
minute) and succeeded on retry after Groq's 3–5 second `retry-after`. Groq's remaining-requests
header did not go down for the rejected requests, so they did not use daily request quota. About
66,400 tokens were used on this day with no tokens-per-day rejection; whether a daily token cap
exists is still unknown.

**Known data issue found — not changed.** The Stage 2 template for car thefts reads "stolen
overnight from outside my home on {street}", but fills in a random street rather than the
policyholder's home street. So CLM-0001 and CLM-0019 (fraud) and CLM-0027 (legitimate) contain an
address inconsistency that was never designed as a signal. It appears on both fraud and
legitimate claims, so it does not reveal labels, but it is noise: the Prosecutor used it against
CLM-0027 (the Judge dismissed it). Fixing it changes the benchmark data, so it is left unchanged
pending a decision. If it is fixed, the affected claims' Stage 4 and Stage 5 results must be
re-run and the change logged here.
