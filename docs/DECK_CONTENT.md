# ClaimLens — Presentation Deck Content (10 slides)

Content only — build the actual file at Stage 16 once Stage 11 numbers land.
Covers all 8 sections the hackathon requires.

**Placeholder keys used in this file** (align with `fill_results.py --list-keys`; where the
README already defines a key for the same value, rename to the README's spelling rather than
keeping mine):
`baseline_accuracy`, `claimlens_accuracy`, `baseline_confidently_wrong`,
`claimlens_confidently_wrong`, `claimlens_confidently_wrong_before_cap`, `claimlens_auto_resolved`,
`baseline_fraud_dollars_caught`, `claimlens_fraud_dollars_caught`, `sample_and_truncation_note`.

**Narrative spine:** the obvious move is to automate claims decisions with an LLM. We built
that, measured it properly, and found it is *confidently wrong*. ClaimLens is what you build
once you take that failure seriously. The honesty of the measurement is itself the
differentiator — most entries will show a demo, very few will show a held-out set.

---

## Slide 1 — Title
**ClaimLens — the claims AI that knows when it doesn't know**
Subtitle: Adversarial debate + calibrated confidence for insurance claims triage
Mitali Mehta · AI Builders Hackathon 2026

---

## Slide 2 — Problem Statement
- Insurance fraud costs an estimated **$308 billion a year** in the US alone.
- 10–20% of claims contain fraudulent elements — but **75% of flagged claims are never fully
  investigated.** The bottleneck is investigator capacity, not detection appetite.
- Fraud is now AI-powered: deepfake fraud attempts up **2,137%**, AI-enabled document fraud up
  **3,000%** since 2023, with fakes passing traditional verification over 90% of the time.
- Insurers lose **$8.50 for every $1** spent fighting it.

*Speaker note:* land the capacity point hardest — it's what makes an AI copilot the right shape
of answer rather than just another classifier. Cite sources in small text on the slide.

---

## Slide 3 — Why naive AI automation fails here
The obvious build is "give the claim to an LLM and ask." We built exactly that as our baseline.
It fails in a specific, dangerous way: **it is confident and wrong.**

The asymmetry is what makes this domain hard:
- Wrongly **approve** a fraudulent claim → direct loss.
- Wrongly **deny** a legitimate claim → customer harm, churn, regulatory exposure, bad-faith
  liability.

An AI that is 85% confident on both is unusable in a regulated industry. Confidence has to mean
something before automation is safe.

---

## Slide 4 — Solution Overview
ClaimLens investigates each claim and **declares how sure it is** before anything is automated.

`Claim → Evidence agent → Prosecutor vs Defender → Judge (run twice, argument order swapped)
→ Point-by-point accounting → Confidence cap → Gate`

The gate: auto-resolve **only** a HIGH-confidence approval. Every denial and every uncertain
case goes to a human with the full evidence trail and debate attached — so the adjuster starts
from an argued case file, not a blank screen.

*This slide should carry the pipeline diagram.*

---

## Slide 5 — Target Users
- **Primary:** claims adjusters and SIU (Special Investigations Unit) teams drowning in volume.
- **Secondary:** policyholders, who get faster resolution on clear-cut claims.

**ClaimLens never autonomously denies a claim.** It only ever auto-approves, and only when it
can defend every point raised against the claim. Denials are a human decision, always. That
constraint is a deliberate product choice, not a limitation.

---

## Slide 6 — Product Features
- **Case queue** filterable by status, confidence tier and outcome.
- **Case view** — evidence in readable cards, the full debate as two opposing columns, both
  Judge orderings side by side with whether they agreed.
- **The cap explainer** — when confidence is lowered, the product shows exactly which points
  went unanswered, what each Judge said about them, and that the claim would otherwise have
  been auto-approved. Most AI products hide their uncertainty; this one puts it on the page.
- **Portfolio analytics** — accuracy, confidently-wrong counts, auto-resolution, false
  positives/negatives, fraud value caught, adjuster hours saved.

---

## Slide 7 — Technical Architecture & AI Technologies
- **Model:** `openai/gpt-oss-120b` on Groq, temperature 0.2, identical settings for baseline and
  pipeline.
- **Evidence agent:** fully deterministic, no LLM — policy timeline, claim history, document
  consistency, plus **live Open-Meteo historical weather** calls. It reports neutral facts only;
  it never draws conclusions, so the reasoning stays where it can be audited.
- **Debate layer:** Prosecutor / Defender / Judge, a direct application of *AI Safety via
  Debate* (Irving, Christiano & Amodei, OpenAI 2018) — verifying a winning argument is easier
  than verifying a hard claim directly.
- **Calibration layer:** verbalized confidence cross-checked by an order-swap consistency test,
  following current work on verbalized-confidence and self-consistency methods. LLM judges are
  order-sensitive; a verdict that flips when you flip the argument order isn't one to act on.
- **The cap runs in code, not in the prompt** — the model cannot talk itself past it.
- Stack: FastAPI + SQLite backend, Next.js + TypeScript + Tailwind frontend.

---

## Slide 8 — How we evaluated it *(the differentiator — do not cut this slide)*
- **40 synthetic claims** with ground-truth labels and 9 fraud patterns — plus deliberate
  *innocent look-alikes*: legitimate claims with brand-new policies, far-from-home incidents and
  large amounts, each with an innocent explanation. A system can't score well by flagging
  anything unusual.
- **Dev / held-out split.** 13 claims used for all iteration; 27 never inspected or tuned
  against.
- **Pre-registration.** The 15-claim evaluation sample was drawn with a fixed seed, stratified,
  hashed (SHA-256) and committed **before the first held-out claim ran**. So was the
  HIGH-confidence threshold, and the stopping rule for an unfinished batch.
- **A methodology log** records every change to inputs or prompts, with the justification, at
  the time it was made — including the ones that didn't work.
- Reported as **raw counts, not percentages** — n=15 does not support percentages.

*Speaker note:* this is the slide that separates you from entries whose numbers are unfalsifiable.
Say plainly: "we designed this so we couldn't fool ourselves."

---

## Slide 9 — What we found
ClaimLens did not beat the baseline on accuracy. Here's what it bought, and what it cost.

Correct: baseline 12 of 15 correct (always approve: 10 of 15) · ClaimLens 11 of 15 correct (always approve: 10 of 15)

Confidently wrong: baseline 1 of 12 high-confidence answers wrong · ClaimLens 0 of 3 high-confidence answers wrong, before the cap 2 of 11 high-confidence answers wrong

ClaimLens auto-approved no fraudulent claims. Post-hoc comparison, not pre-registered: the same model given the same gate would have auto-approved 11 claims, one of them fraudulent.

The cost of caution: the cap downgraded 8 claims, 6 of which were already correct. Only 2 of 15 claims auto-resolved.

What didn't work: the order-swap check changed no decisions, 0 of 15.

These figures cover 15 completed claims (5 fraud, 10 legitimate) from a stratified random sample of 15 of the 27 held-out claims, pre-registered on 2026-09-14 (seed 20260914) before any held-out claim was run. With a sample this small, results are raw counts. All 15 pre-registered claims completed; nothing was truncated. Every gap here is a single claim — directionally suggestive at most.

*Speaker note (fraud value, for context if asked):* baseline caught $13,363 of $39,411, ClaimLens $8,813 of $39,411. The baseline caught more; every fraud claim ClaimLens missed went to a human rather than being auto-approved.

---

## Slide 10 — Roadmap & Honest Limitations
**Limitations we know about:** synthetic benchmark, not real claims data; 40% fraud rate is
deliberate oversampling for statistical signal (real rates are 10–20%); small evaluation sample
constrained by free-tier quota; document checks are keyword-based and can't judge whether damage
fits a narrative; the confidence cap is blunt — it downgraded 8 claims, 6 of which were already
correct; and the order-swap check changed no decisions (0 of 15), so it needs redesigning or
removing.

**Roadmap:** real insurer data integration and claims-system connectors · learned calibration
(RL with an asymmetric reward that punishes confident errors hardest) · image/document forensics
for AI-generated evidence · adjuster feedback loop so overrides retrain the confidence model ·
audit export for regulators.
