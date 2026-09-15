# ClaimLens — Demo Video Script (5:00 max)

Covers all five required points: problem, how the solution works, key features, the role of AI,
and a live demonstration.

**Placeholder keys used in this file** (align with `fill_results.py --list-keys`; reuse the
README's key spellings where they already exist):
`baseline_accuracy`, `claimlens_accuracy`, `sample_and_truncation_note` (shown as an on-screen
caption, not spoken).

**Before recording:** the intake and dashboard samples already show the Stage 11 results, and the
analytics page shows the final numbers. Reserve ~20k tokens so one live submission can run on
camera; live submission is off on the deployed site, so film it locally or switch it on in Render
only for the take. Do a silent dry run first; the live call takes ~60-90 seconds.

---

## 0:00–0:40 — The problem
> Insurance fraud costs around three hundred and eight billion dollars a year in the US. But
> here's the number that actually matters: three quarters of claims that get flagged as
> suspicious are never fully investigated. Not because nobody wants to — because there aren't
> enough investigators. And fraud itself has gone AI-powered, with deepfake attempts up two
> thousand percent in three years.
>
> So the obvious answer is to put an AI on it. We did exactly that. Then we measured it, and
> found a problem.

*Visual: title card, then the two statistics.*

---

## 0:40–1:15 — Why the obvious answer fails
> A single-pass LLM deciding claims isn't just sometimes wrong. It's *confidently* wrong. And in
> insurance the two mistakes aren't symmetric: wrongly approving fraud costs money, but wrongly
> denying a legitimate claim costs you a customer and brings the regulator. An AI that's
> eighty-five percent sure of both is not something you can deploy.
>
> Confidence has to mean something before you automate anything. That's what ClaimLens is for.

*Visual: two side-by-side wrong answers from the baseline, both high-confidence.*

---

## 1:15–1:45 — How it works
> A claim comes in. A deterministic evidence agent builds the case file — policy timeline, claim
> history, document consistency, and a real historical weather lookup. It reports facts only; it
> never draws conclusions.
>
> Then two AI agents argue. A prosecutor makes the case that the claim is suspicious. A defender
> answers. A judge weighs them — and we run that judge twice, with the arguments in opposite
> orders, because a verdict that flips when you flip the order isn't a verdict you should act on.

*Visual: the pipeline diagram, animating left to right.*

---

## 1:45–3:30 — Live demonstration *(the core — keep it moving)*
> Here's a real claim going through, live.

*Submit a claim. Let the step tracker run — narrate over it.*

> Evidence gathering, then the debate, then the judge in both orderings.

*Open the case view.*

> Here's the debate. The prosecutor raises specific points. The defender answers them. And here's
> the part I want to show you —

*Scroll to the cap card.*

> The judge said HIGH confidence. Our system overruled it. Two of the prosecutor's points were
> never answered with an actual fact from the case file — they were answered by assertion. So the
> confidence gets capped, and instead of being auto-approved, this claim goes to a human, with the
> whole argument attached.
>
> That rule runs in code, not in the prompt. The model can't talk its way past it.

*Open the dashboard, then analytics.*

> The adjuster sees a queue, and every case arrives pre-argued rather than blank.

---

## 3:30–4:20 — How we know it works
> Any team can show you a demo. So here's how we tested it — and what we found.
>
> Forty synthetic claims with known answers, including legitimate ones deliberately built to look
> suspicious. Thirteen for development, twenty-seven never touched. We drew a fifteen-claim sample
> with a fixed seed, hashed it, and committed it before running a single one.
>
> And it didn't beat the baseline. 12 of 15 correct (always approve: 10 of 15) against 11 of 15 correct (always approve: 10 of 15), where always-approve scores ten of fifteen. We're telling you that because we pre-registered it — and we weren't going to un-pre-register it when the number came back.
>
> What the architecture did buy is narrower: none of ClaimLens's high-confidence answers were
> wrong, and it auto-approved no fraud at all. The same model given that same gate would have
> auto-approved eleven claims, one of them fraudulent.

*Delivery note: say only the leading score for each system ("... of fifteen") and skip the
parenthetical after it; always-approve is already said in words.*

*Visual: the pre-registration statement and analytics page. On-screen caption, not spoken:
These figures cover 15 completed claims (5 fraud, 10 legitimate) from a stratified random sample of 15 of the 27 held-out claims, pre-registered on 2026-09-14 (seed 20260914) before any held-out claim was run. With a sample this small, results are raw counts. All 15 pre-registered claims completed; nothing was truncated.*

---

## 4:20–5:00 — Impact and close
> The baseline actually caught more fraud value than we did. What we didn't do is auto-approve any
> of it.
>
> ClaimLens never denies a claim on its own. It only auto-approves, and only when it can defend
> every point raised against that claim — so thirteen of fifteen went to a human, with the argument
> already made.
>
> What we'd change: the cap is blunt. It caught the two mistakes we wanted, and downgraded six
> correct answers doing it. And the order-swap check never changed a decision, so it needs
> redesigning or removing.
>
> The question for claims AI isn't whether it can decide. It's whether it knows when it shouldn't.

---

## Delivery notes
- Under 5:00 strictly. Time the dry run; the live call is the only variable-length segment.
- The cap card at ~2:40 is the moment the product earns its keep — slow down there.
- Don't apologise for the sample size; state it flatly and move on. Confidence about limitations
  reads as rigour, hedging reads as doubt.
