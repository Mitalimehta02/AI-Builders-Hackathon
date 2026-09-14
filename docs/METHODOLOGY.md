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

### 2026-09-13 — Evaluation protocol adopted: development set and held-out set (start of Stage 6)

Following PROJECT_PLAN.md Part 5b:

- **Development set (7):** CLM-0001, CLM-0006, CLM-0019, CLM-0027, CLM-0030, CLM-0034, CLM-0035.
  All prompt iteration, debugging and design changes happen on these only.
- **Held-out set (33):** every other claim. Not inspected, run or tuned against until Stage 11.
  Headline accuracy and confidently-wrong figures will come from these 33.
- The list lives in `backend/app/synthetic/eval_split.py`; development scripts call
  `require_dev_set()` and stop if a held-out claim is requested.
- Test for every prompt change: would someone who had never seen the dev claims have written it?

**Disclosure: held-out claims seen before the split existed.** Recorded now, before any Stage 11
run, so it is not reconstructed later.

- By design, the generator source defines every claim's label through its scenario table, and
  while checking the dataset at Stage 2 a per-claim listing of all 40 claims (ID, label,
  difficulty, signals, amount) was printed.
- Stage 2: **CLM-0025 and CLM-0032** (now held-out) drove a generator fix — legitimate car repair
  amounts were capped below the car's value.
- Stage 3: an evidence scan of all 40 claims was printed. **CLM-0014, CLM-0024, CLM-0033 and
  CLM-0036** (now held-out) drove an evidence-rule fix — plumber and electrician rules were limited
  to property claims.
- Stage 5: an address check printed CLM-0002, CLM-0007, CLM-0011 and CLM-0015 (now held-out) with
  their labels. No change was made to those claims because of it.

No model had been run on any held-out claim, and no prompt had been changed because of one.
Part 5b says a held-out claim that drove a change moves to the development set. Whether that
applies to the six claims above (which drove data and evidence-rule fixes, not prompt changes) is
an **open decision**, to be settled before Stage 11 and recorded here.

From this point on, any check that has to span all 40 claims prints only pass/fail results or
counts per field name, never per-claim content; per-claim details are printed for dev claims only.

### 2026-09-13 — Benchmark data fixes, then data frozen (Stage 6)

**Bug class.** A value was drawn at random where a value consistent with the rest of the claim was
intended. All templates and modifiers in `generate_claims.py` were swept once; every instance
found was fixed in one pass:

| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | Car theft story | "stolen … from outside my home on {street}" used a random street, not the home street | Incident street is now the policyholder's home street ("outside my home at …") |
| 2 | Burglary story | "while we were away for the weekend" could be dated on a weekday | Date moved forward to the Sunday of that week |
| 3 | Frozen pipe story | "while we were at work" could be dated on a weekend | Date moved forward to the following Monday |
| 4 | Severity-mismatch car claims | The random $14,000–21,000 bill could exceed the car's value, breaking the generator's own rule that only `amount_exceeds_value` claims do so, and adding a second, unplanned clue | Capped at 70% of the car's value, like every other repair claim |
| 5 | Receipt-dated burglary claims | The random claimed amount could be lower than the itemised receipts ($4,398) | If below receipts + $1,000, the receipts total is added |
| 6 | Policyholder date of birth | Minimum age 22 could make the policyholder a minor at policy start or at a prior claim | Drawn exactly as before, then moved back 8 years if under 30 (this field is never shown to any agent) |
| 7 | Vehicle estimated value (related, not random) | Depreciated to 2026 rather than to the incident date, contradicting the guide's "actual cash value just before the loss" | Depreciated to the incident year |

Checked and deliberately unchanged: random streets for other car incidents (they happen elsewhere
in the city); the random other city or street in `location_mismatch` (that is the designed signal);
dates, amounts and cities chosen for the designed signals.

**How.** Every random draw still happens in the same order (streets are still drawn; dates are
shifted deterministically), so nothing else about any claim should change. New `validate()` rules
in the generator check each fix on every claim.

**Verification (field-by-field comparison of the old and new data files).** Claim IDs, ground
truth, and every policyholder name, email, phone and address are identical for all 40 claims.
23 claims changed, only in the intended fields (number of changes across all 40 claims):
vehicle estimated value 16, claim amount 9, incident description 3, incident street 3, incident
date 3, filed date 3, policy start date 3, date of birth 3, supporting documents 1, prior-claim
amount 1. Of the dev claims, CLM-0001, CLM-0019 and CLM-0027 changed (theft street; for 0001 and
0019 also vehicle value and the value-based amount), CLM-0030 changed (vehicle value; the
severity-mismatch bill was capped from $14,758.82 to $3,570.00; date of birth), CLM-0035 changed
(date of birth only), and CLM-0034 is unchanged. Only counts per field were printed for held-out
claims.

**A first attempt was wrong and was replaced before anything used the data.** Fix 6 was first made
by raising faker's minimum age to 30. That changed how many random numbers faker consumed, so
names, emails, phones, addresses, street names and shop names changed on about 11 claims from
CLM-0030 onwards. The comparison caught it; the fix was redone as described above, and the
comparison then showed no unintended changes.

**Known side effect, not changed.** A capped repair bill equals exactly 70% of the vehicle's
value, so `claim_amount_pct_of_vehicle_value` reads exactly 70.0 on capped claims. This already
applied to legitimate repair claims capped at Stage 2 and now also to capped severity-mismatch
claims, so it does not separate fraud from legitimate claims; it is noted here because the data is
now frozen.

**Frozen.** After this regeneration, `backend/data/synthetic_claims.json` is final. Results files
from Stages 4 and 5 predate this version of the data and are kept only as history. The whole dev
set is re-run once, after all fixes, for both the baseline and the full pipeline.

### 2026-09-13 — Case-file guide: meaning of an empty `documents_mentioned_but_absent` (Stage 6)

**Observed.** In the Stage 5 CLM-0019 debate the Prosecutor wrote "documents_mentioned_but_absent is
empty, indicating expected documents are missing" — the opposite of the field's meaning.

**Changed.** The guide now says: "documents_mentioned_but_absent lists document types that the
claim's own description calls for (for example, it mentions police) but that no listed document
matches. An empty list means these checks found no such gap; it does not mean that documents are
missing. The checks cover common document types only, so an empty list also does not prove the
file is complete."

**Part 5b test.** It explains what a field means and says nothing about any claim; anyone
documenting this field would write it. It reaches every agent, baseline included.

### 2026-09-13 — Judge rubric: rebuttals must engage the specific facts (Stage 6)

**Observed.** On CLM-0019 the Judge accepted "policy changes are permitted" as an answer to a point
about the circumstances of a particular change. The response did not engage the facts the point
relied on.

**Changed** (Judge prompt only; the Prosecutor, Defender and baseline prompts are unchanged):

1. New rule: "A response answers a point only if it engages the specific facts that point relies
   on. Saying that something is permitted, common or normal does not answer a point about whether
   it fits the particular facts of this claim; treat a point answered only in that way as
   unanswered."
2. "A point one side raised and the other failed to answer" became "… did not actually answer".
3. HIGH now requires the other side's strongest point to be "actually answered by facts in the case
   file, not merely by an assertion".

**Part 5b test.** Each sentence is a general principle of evaluating arguments — the standard for
what counts as a rebuttal — and names no fact, field or fraud pattern. Someone who had never seen
the dev claims could have written each of them. A test fails if the Judge rubric ever mentions
case-pattern words (theft, weather, coverage, policy, timing, amounts, documents and similar).

**Fairness note.** This changes the Judge only, so it is part of the ClaimLens architecture rather
than a shared input; the baseline keeps its own unchanged instructions. Its effect is measured on
the dev set here and on the held-out set at Stage 11.

### 2026-09-13 — Stage 6 rules, fixed before any Stage 6 output

- **Order swap.** The Judge rules twice on the same Prosecutor and Defender arguments: Prosecutor's
  argument first, then Defender's first. The system prompt, case file and argument text are
  identical; only their order in the message differs.
- **Tier.** HIGH if both orderings agree and both say HIGH; MEDIUM if they agree with either
  saying MEDIUM or LOW; LOW if they disagree.
- **Gate.** Auto-resolve only a HIGH-tier APPROVE; every DENY and every non-HIGH case goes to a
  human.
- **Recommendation.** ClaimLens's decision is the Prosecutor-first Judge's decision. The swap
  feeds only the confidence tier: using it to pick decisions would let presentation order change
  accuracy. A split verdict keeps that decision but is LOW, so a human decides.
- **For Stage 11.** A ClaimLens answer counts as high-confidence for the confidently-wrong rate
  when its final tier is HIGH (the baseline's band stays confidence >= 80).
- **Not built.** The optional `FULL_DOUBLE_DEBATE` mode (re-running the whole debate instead of
  only the Judge).

### 2026-09-13 — Stage 6 development-set results (dev set only; this is the set the system was tuned on)

All 7 dev claims, run once after the data fixes, the guide fix and the Judge rubric change. Same
model and settings for everything. Results and full transcripts:
`backend/data/stage6_dev_results.json`. No held-out claim was loaded or run.

| Claim | Is fraud | Baseline | Judge, Prosecutor first | Judge, Defender first | Tier | Gate | Baseline | ClaimLens |
|---|---|---|---|---|---|---|---|---|
| CLM-0001 | yes | APPROVE (70) | APPROVE / MEDIUM | APPROVE / HIGH | MEDIUM | human review | wrong | wrong |
| CLM-0006 | no | APPROVE (85) | APPROVE / MEDIUM | APPROVE / MEDIUM | MEDIUM | human review | right | right |
| CLM-0019 | yes | APPROVE (93) | APPROVE / HIGH | APPROVE / HIGH | HIGH | **auto-resolved** | wrong | wrong |
| CLM-0027 | no | APPROVE (80) | APPROVE / HIGH | APPROVE / HIGH | HIGH | auto-resolved | right | right |
| CLM-0030 | yes | APPROVE (80) | APPROVE / HIGH | APPROVE / HIGH | HIGH | **auto-resolved** | wrong | wrong |
| CLM-0034 | yes | APPROVE (85) | APPROVE / HIGH | APPROVE / MEDIUM | MEDIUM | human review | wrong | wrong |
| CLM-0035 | yes | DENY (85) | DENY / MEDIUM | DENY / MEDIUM | MEDIUM | human review | right | right |

**What this shows, stated plainly (7 dev claims — far too few for conclusions about the design):**

- Accuracy is 3 of 7 for both systems; they reached the same decision on every claim.
- The order swap flipped **no** decision. It changed the verbalized confidence on two claims
  (CLM-0001, CLM-0034), which lowered their tier to MEDIUM.
- High-confidence answers: baseline 6 (3 wrong: CLM-0019, CLM-0030, CLM-0034); ClaimLens tier HIGH
  3 (2 wrong: CLM-0019, CLM-0030).
- The gate auto-resolved 3 claims, **2 of which are fraud** (CLM-0019, CLM-0030).
- **The Judge rubric change did not fix CLM-0019.** The Defender again answered the point about the
  coverage change with "policies allow riders to be added at any time … the coverage was in force",
  and both Judge orderings accepted it with HIGH confidence.
- On CLM-0030 the Prosecutor raised the mismatch between a walking-speed bump and the listed frame
  damage; the Defender asserted it was plausible, and both Judges accepted the assertion.
- Across claims, both systems repeatedly reason that a missing document or an unexplained
  inconsistency "does not prove fraud", and approve.

**Nothing was changed in response to these results.** Any further change to prompts or rules must
be logged here first, with its Part 5b justification, and re-run on the dev set.

**Tokens (measured).** Per claim on average: baseline 2,321; Prosecutor 3,132, Defender 4,104,
Judge (Prosecutor first) 3,900, Judge (Defender first) 4,008 — pipeline 15,145. The second Judge
call is now measured rather than estimated. Stage 11 projection: 40 × (2,321 + 15,145) = 698,623
tokens and 200 accepted requests, at least 87 minutes at 8,000 tokens per minute. This run used 35
accepted requests and 122,259 tokens; 6 further requests were rejected with HTTP 429 (tokens per
minute) and retried, and did not reduce the daily request count.

### 2026-09-13 — Benchmark solvability check, and a correction to Stage 6 data fix #4

**Why.** A claim labelled fraud with no fraud evidence left would be a broken test case, not a hard
one. After Stage 6, CLM-0030 moved from a correct DENY (Stage 4, v3) to a wrong APPROVE, and the
Stage 6 cap on its repair amount was the obvious suspect.

**Check added.** `backend/app/synthetic/check_signals.py` measures every designed fraud signal of
every fraud claim against the parameters the generator used to create it (no model calls).
`backend/tests/test_signals.py` now runs the same check with the test suite, so no future data
change can silently remove a signal. Measured details are printed for dev claims and failed checks
only.

**Result before repair.** 16 fraud claims, 22 designed signals, **2 missing**, both
`severity_mismatch` and both caused by Stage 6 fix #4 (repair bill capped at 70% of the car's
value): CLM-0030 (dev) at $3,570.00 and CLM-0009 (held-out) at $10,290.00, against a designed range
of $14,000–21,000. The damage description was still extensive in both. Neither claim had lost all
evidence: CLM-0030 still had `early_claim` and `document_gap`; CLM-0009 still had
`duplicate_claim`.

**Correction.** Fix #4 is reversed: severity-mismatch car claims are back in the designed
$14,000–21,000 range, using the same single random draw. On low-value cars this exceeds the car's
value, exactly as in the original Stage 2 data; the generator's "repair bill below the car's value"
rule now exempts `severity_mismatch` as well as `amount_exceeds_value`. The Stage 6 concern about
a "second clue" was wrong to act on — it removed part of the designed signal.

**Verification.** Only 2 claims changed: CLM-0030's claim amount ($3,570.00 → $14,758.82) and
CLM-0009's claim amount plus the amount of its designed duplicate prior claim (which is derived
from the claim amount). Labels and all other fields are identical. The signal check now reports
0 of 22 missing.

**CLM-0009 stays held-out.** Its failed check printed its amount, but the repair was needed for
CLM-0030 in any case and restores CLM-0009's original Stage 2 amount; no prompt or rule was shaped
around it. This is recorded here so the choice can be challenged.

**Consequence.** The Stage 6 dev results (`stage6_dev_results.json`) used the capped CLM-0030 and
are kept only as history. The data is frozen again from this entry.

### 2026-09-13 — Development set enlarged from 7 to 13 claims (open decision settled)

CLM-0014, CLM-0024, CLM-0025, CLM-0032, CLM-0033 and CLM-0036 — the six claims that drove data or
evidence-rule fixes before the split existed — moved to the development set, as Part 5b requires.
**Held-out set: 27 claims.** Headline Stage 11 figures will come from those 27. Updated in
`backend/app/synthetic/eval_split.py` (enforced) and PROJECT_PLAN.md Part 5b and Stage 11.

### 2026-09-13 — Debate protocol: prosecutor rebuttal round (before re-running the dev set)

**Observed.** In the Stage 6 dev run, on both CLM-0019 and CLM-0030 the Prosecutor raised the
relevant fact and the Defender dismissed it by assertion. The Defender always spoke last, so no
such response could be challenged before the Judge ruled.

**Changed.** The protocol is now Prosecutor → Defender → **Prosecutor rebuttal** → Judge. The
rebuttal may only reply to what the Defender said (no new points), may dispute a response only if
it fails to engage the specific facts it answers or misstates a fact, must name the fact left
unaddressed, and is limited to 3 items of one or two sentences each (an empty list is allowed).
The rebuttal appears after both opening arguments in both Judge orderings; the order swap still
exchanges which opening argument comes first.

**Part 5b test.** Alternating rounds is standard in debate formats because the last unchallenged
speaker has a structural advantage. The change concerns who may reply to whom, not any claim,
field or pattern; someone who had never seen the dev claims could have designed it. A test fails if
the rebuttal rules mention case-pattern words.

**Cost.** One more model call per claim (5 per claim for ClaimLens, plus the baseline's 1).

### 2026-09-13 — Structured rebuttal accounting with a mechanical confidence cap (before re-running the dev set)

**Observed.** The Stage 6 rubric sentence ("saying something is permitted, common or normal does
not answer a point") was in the Judge prompt, and both Judge orderings still accepted exactly such
a response with HIGH confidence. Asking the model to be stricter with itself did not work.

**Changed.**
1. The Judge now also returns `point_assessments`: for every numbered point from either side, whether
   it is `significant` (could change the decision if left standing) and its status —
   `answered_with_case_file_fact`, `answered_by_assertion_only` or `unanswered`.
2. **In code** (`calibration.py`), after the tier is combined: if the tier is HIGH and either Judge
   ordering has a significant point *against its own decision* whose status is not
   `answered_with_case_file_fact`, the tier becomes MEDIUM. A point the Judge did not assess
   counts as unresolved. The cap can only lower HIGH to MEDIUM. The Judge is not told the cap
   exists.
3. "Against its own decision" is applied symmetrically: the Prosecutor's points for an APPROVE,
   the Defender's points for a DENY. (Capping only approvals would lower confidence on one kind
   of decision only, which would bias the confidently-wrong comparison.)

**Part 5b test.** Whether each argument was answered with evidence is a general accounting of a
debate, applicable to any dispute; it names no field or pattern, and someone who had never seen
the dev claims could have designed it. The existing test that fails if the Judge rules mention
pattern words stays in place and covers the new text.

**Stated limitation.** Which points are "significant" is still the Judge's own call. The cap makes
the consequence mechanical, not the assessment.

**Fairness.** Both changes are ClaimLens architecture; the baseline's inputs and instructions are
unchanged. For the dev re-run, a baseline result from the Stage 6 dev run is reused only if the
request log shows the baseline input is byte-identical to the current one; otherwise the baseline
is re-run.

### 2026-09-13 — Dev re-run stopped by Groq's daily token limit (partial result only)

**What happened.** The 13-claim dev re-run with the rebuttal round and accounting cap stopped on its
second claim. Groq rejected the CLM-0006 rebuttal call with HTTP 429 on **tokens per day: limit
200,000** ("Used 197,689, Requested 4,103, please try again in 12m54s"). Part 6b had listed a daily
token cap as possible but unconfirmed; it is now confirmed. The shared client correctly stopped
instead of retrying (the requested wait exceeded its 60-second cap), and progress was saved after
every call. The wait matched a gradual refill of about 8,300 tokens per hour, which suggests a rolling
allowance rather than a reset at midnight. Accepted calls logged on this UTC day total 215,562 tokens.

**Completed: 1 of 13 dev claims.** Results in `backend/data/stage6_dev_results_v2.json`.

| Claim | Is fraud | Baseline | Judge, Prosecutor first | Judge, Defender first | Tier before cap | Final tier | Gate | ClaimLens |
|---|---|---|---|---|---|---|---|---|
| CLM-0001 | yes | APPROVE (70), reused (identical input) | APPROVE / MEDIUM | APPROVE / HIGH | MEDIUM | MEDIUM | human review | wrong |

- Compared with the Stage 6 dev run: decision unchanged (APPROVE), tier unchanged (MEDIUM). No
  claim that was previously HIGH and wrong has been re-run yet.
- Both Judge rulings labelled two significant Prosecutor points as `answered_by_assertion_only`, yet
  the Defender-first ruling still verbalized HIGH. The cap did not need to act because the tier was
  already MEDIUM, but this is the behaviour the mechanical cap exists for.
- The rebuttal on CLM-0001 argued that the claimed amount exceeds "vehicle value minus deductible",
  which the case-file guide explicitly says is not how the amount is defined.
- CLM-0006 stopped after the Prosecutor and Defender calls; the other 11 dev claims were not started.

**Measured tokens with the extra call (CLM-0001).** Prosecutor 2,977, Defender 3,977, Prosecutor
rebuttal 4,541, Judge (Prosecutor first) 4,912, Judge (Defender first) 4,901 — **21,308** for the
pipeline, against 15,404 for the same claim in the Stage 6 run (+38%). On a single claim this is an
indication, not an average.

**Consequence for Stage 11 (recorded, not yet acted on).** At about 21,300 tokens per claim for
ClaimLens plus about 2,300 for the baseline, the full 40-claim run would need roughly 945,000
tokens — nearly five days of a 200,000-token daily allowance — and even the 27 held-out claims
alone would need about 640,000. The dev iteration was stopped here rather than resumed, in line with
the decision to move on to Stage 7; how Stage 11 will fit the budget is an open decision.

### 2026-09-14 — Stage 11 evaluation sample pre-registered (before any held-out claim is run)

**Why a sample.** With the confirmed 200,000-token daily cap, the 27-claim held-out run (about
640,000 tokens) cannot finish before the deadline. PROJECT_PLAN.md Part 5b now specifies a
pre-registered stratified random sample of 15 held-out claims, selected and logged before any
held-out claim is run. This entry is that registration.

**Selection.** Produced by `backend/app/synthetic/stage11_sample.py`; the committed record is
`backend/data/stage11_sample.json`.

- **Seed:** 20260914 (Python `random.Random`).
- **Method:** the 15 slots are split between fraud and legitimate in proportion to the held-out
  set (largest-remainder rounding), then across easy / ambiguous / hard within each label in
  proportion to tier size (largest remainder; ties go to the earlier tier in that order), then
  claims are drawn at random within each tier.
- **Only claim IDs and the two label fields were read.** No claim content was inspected and no
  model was run.

| Stratum | Held-out | Selected |
|---|---|---|
| fraud / easy | 4 | 2 |
| fraud / ambiguous | 2 | 1 |
| fraud / hard | 3 | 2 |
| legitimate / easy | 6 | 4 |
| legitimate / ambiguous | 6 | 3 |
| legitimate / hard | 6 | 3 |
| **Total** | **27 (9 fraud, 18 legitimate)** | **15 (5 fraud, 10 legitimate)** |

**Selected claim IDs (15):** CLM-0004, CLM-0007, CLM-0010, CLM-0011, CLM-0015, CLM-0017, CLM-0020,
CLM-0021, CLM-0022, CLM-0026, CLM-0028, CLM-0029, CLM-0037, CLM-0039, CLM-0040.

**Hashes.**
- `claim_ids_sha256` = `bbcdf0fd5693fd7a1be43ee4516dd7c99ef71fbb238e696c6c190dc108d5b49a`
  (the IDs above sorted, joined with newlines, UTF-8).
- `claims_data_sha256` = `f309786c9be4f527190fd61ef07cdaeb07ea22b6f4a1ccf234b5da968fee8e29`
  (`json.dumps` of the parsed frozen claim data with sorted keys, UTF-8), so any later change to
  the data is detectable.
- `backend/tests/test_stage11_sample.py` fails if the selection cannot be reproduced from the
  seed and method, if either hash no longer matches, or if a development claim is in the sample.

**Reference line.** Always answering APPROVE would be correct on 10 of these 15 claims.

**Reporting rules for this sample** (Part 5b): raw counts rather than percentages for
confidence-tier outcomes; the sample size and this pre-registration stated wherever results
appear; the always-approve line next to every accuracy figure; a difference of one or two
claims is described as directionally suggestive, not demonstrated.

**Unused.** The other 12 held-out claims are not run or inspected and are not part of any
reported figure.

**Disclosure.** Every held-out claim appeared in the all-claims listings printed at Stages 2 and 3
(disclosed in the 2026-09-13 protocol entry). Among the selected claims, CLM-0007, CLM-0011 and
CLM-0015 were also printed with their labels by the Stage 5 address check, and CLM-0015, CLM-0029,
CLM-0037, CLM-0039 and CLM-0040 appeared in the signal-check table with their signal names and a
pass result. None of them drove a change. The random draw did not take any of this into account.

**Plan text correction.** The 2026-09-13 revision of PROJECT_PLAN.md reverted the Part 5b and
Stage 11 wording to "7 development / 33 held-out" while its new sample paragraph used 27. The
split itself never changed (it is enforced by `backend/app/synthetic/eval_split.py`), so the 13 / 27
wording was restored.

### 2026-09-14 — Stage 7 live end-to-end API test on two dev claims

**What ran.** The API server was started and two development-set claims were submitted with
`curl.exe` exactly as stored in the benchmark file (answer sheet included; the API drops it). Each
was polled until resolved and its full result fetched. The command log and both full responses are
committed in `backend/data/stage7_e2e/`. No held-out claim was submitted (the API refuses them).

| Claim | Is fraud | Judge, Prosecutor first | Judge, Defender first | Tier before cap | Final tier | Gate | Tokens |
|---|---|---|---|---|---|---|---|
| CLM-0035 | yes | APPROVE / MEDIUM | APPROVE / MEDIUM | MEDIUM | MEDIUM | human review | 19,945 |
| CLM-0027 | no | APPROVE / HIGH | APPROVE / HIGH | HIGH | **MEDIUM (cap applied)** | human review | 24,340 |

10 accepted requests, 44,285 tokens; 5 further requests were rejected on tokens per minute and
retried. Neither API response contains the answer sheet.

**Observations, recorded without any change being made (agent iteration is closed):**

- **CLM-0035 changed decision.** In the Stage 6 dev run it was DENY / MEDIUM; here it is APPROVE /
  MEDIUM. The Defender *conceded* that the weather record contradicts the "frozen pipe" description,
  then argued the water damage itself is documented; both Judge orderings accepted that a
  mischaracterised cause does not make the claim materially misrepresented. The earlier protocol
  had no rebuttal round and no point accounting, and sampling runs at temperature 1.0, so this one
  flip cannot be attributed to a single cause.
- **Gap in the point accounting.** The status list has no "conceded" value. On CLM-0035 the
  Prosecutor-first Judge labelled the conceded weather point `answered_with_case_file_fact` and not
  significant. A conceded point against the decision is therefore not treated as unresolved by the
  cap. It made no difference here (the tier was already MEDIUM), but it is a known weakness of the
  mechanism as built.
- **The cap acted for the first time on CLM-0027**, a legitimate claim: both orderings said
  APPROVE / HIGH, but the Prosecutor-first ruling marked three significant Prosecutor points as
  answered by assertion only, so the tier became MEDIUM and the claim went to human review instead
  of being auto-resolved. The two orderings disagreed on those assessments (the Defender-first
  ruling marked none unresolved).
- **API input is not byte-identical to the evaluation scripts' input.** The API validates claims
  through `ClaimSubmission`, which keeps the same content but orders fields by its schema and writes
  whole-number amounts as decimals (for example `1000` becomes `1000.0`). The case-file text the
  agents see therefore differs slightly from the text built by the dev and Stage 11 scripts.
  Stage 11 runs through the scripts, so evaluation inputs are unaffected; results from the API are
  not directly comparable run-for-run with script results.

**Budget after this test (estimate).** Roughly 43,000 tokens remained after the test; with refill
at about 8,300 tokens per hour, about 430,000 tokens are available before the deadline (2026-09-16
03:00 UTC). The pre-registered 15-claim Stage 11 run is estimated at about 363,000 tokens (baseline
about 2,300 per claim plus pipeline about 21,900 per claim, the average of the three rebuttal-protocol
claims measured so far), leaving a margin of roughly 67,000 tokens. Stages 8-10 must therefore not
call the model; they should use stored results.
