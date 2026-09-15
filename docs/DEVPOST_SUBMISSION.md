# ClaimLens — Devpost Submission Text

Paste into the matching fields. Devpost's story section usually uses these exact headings; map
to whatever the form actually shows. The result markers use the key names from `fill_results.py --list-keys`.

---

## Tagline (one line)
The claims AI that knows when it doesn't know.

## Short description
ClaimLens investigates insurance claims through an adversarial debate between AI agents, then
declares calibrated confidence before anything is automated — auto-approving only claims it can
fully defend, and routing everything else to a human with the full argument attached.

---

## Inspiration

Insurance fraud costs an estimated $308 billion a year in the US, but the statistic that shaped
this project was a different one: **75% of claims flagged as suspicious are never fully
investigated.** The bottleneck isn't detection, it's investigator capacity. Meanwhile fraud
itself has gone AI-powered, with deepfake attempts up 2,137% and document fraud up 3,000% since
2023.

The obvious response is to put an LLM on it. So we built exactly that first — a single-pass
agent that reads a claim and decides. Then we measured it properly, and found the problem that
became the whole project: it isn't just sometimes wrong, it's *confidently* wrong. In a
regulated industry where wrongly denying a legitimate claim costs you a customer and a
regulator, an AI that's 85% sure of both its right and wrong answers is unusable.

## What it does

A claim arrives. A deterministic evidence agent builds a case file — policy timeline, claim
history, document consistency, and a live historical weather lookup — reporting facts only,
never conclusions. Then a Prosecutor agent argues the claim is suspicious, a Defender answers,
and a Judge weighs both. We run that Judge twice, with the arguments in opposite orders,
because LLM judges are order-sensitive and a verdict that flips when you flip the order isn't
one to act on.

A point-by-point accounting then checks whether each argument was actually answered with a fact
from the case file or merely waved away by assertion. If any significant point went unanswered,
**code — not the prompt — caps the confidence**, so the model cannot talk its way past its own
uncertainty.

ClaimLens never autonomously denies a claim. It only ever auto-approves, and only when it can
defend every point raised against that claim. Everything else goes to an adjuster with the full
evidence trail and debate attached, so they start from an argued case rather than a blank screen.

## How we built it

Python/FastAPI and SQLite on the backend, Next.js + TypeScript + Tailwind on the front, running
`openai/gpt-oss-120b` on Groq at a fixed temperature, with identical model settings for the
baseline and the full pipeline.

The debate structure is a direct application of *AI Safety via Debate* (Irving, Christiano &
Amodei, OpenAI 2018) — verifying a winning argument is easier than verifying a hard claim
directly. The calibration layer follows current work on verbalized confidence and
self-consistency. The evidence layer makes real Open-Meteo API calls, disk-cached, with failures
recorded as unavailable rather than silently invented.

## Challenges we ran into

The honest answer is that **the architecture didn't work at first, and finding that out was the
hard part.** Early on, the debate pipeline produced identical decisions to the naive baseline on
every development claim, including the same confident mistakes. Diagnosing why — the Defender
always spoke last and was never challenged, and the Judge accepted non-responsive rebuttals —
took longer than building the thing.

The second challenge was resisting the temptation to fix it dishonestly. Every time we found a
failure, the fastest fix would have been to tell the model what to look for on that specific
claim. Instead we split the data into a development set and a held-out set, wrote down a
distinction between fixing a general reasoning defect and encoding a specific answer, and logged
every change with its justification at the time it was made.

Third: a free-tier token budget of 200,000 a day against an evaluation needing roughly 280,000.
That forced a pre-registered 15-claim sample, a checkpointing batch runner that survives
rate-limit exhaustion, and a run that took most of a day at the refill rate.

## Accomplishments that we're proud of

ClaimLens did not beat the baseline on accuracy. We're reporting that plainly because we
pre-registered the evaluation, and what the architecture did buy is narrower: it auto-approved no
fraudulent claims. What we're proud of is that all of this can be checked. We drew the evaluation sample with a
fixed seed, hashed the claim IDs, and committed them **before running a single held-out claim**.
The confidence threshold was fixed before any results were seen. The stopping rule for an
unfinished batch was written down in advance. `docs/METHODOLOGY.md` records every input change,
every prompt change, and the ones that didn't work — including an accidental glimpse of one
interim result.

These figures cover 15 completed claims (5 fraud, 10 legitimate) from a stratified random sample of 15 of the 27 held-out claims, pre-registered on 2026-09-14 (seed 20260914) before any held-out claim was run. With a sample this small, results are raw counts. All 15 pre-registered claims completed; nothing was truncated.

Baseline: 12 of 15 correct (always approve: 10 of 15). ClaimLens: 11 of 15 correct (always approve: 10 of 15).
Confidently wrong: 1 of 12 high-confidence answers wrong versus
0 of 3 high-confidence answers wrong.

We're also proud that the product shows its own uncertainty rather than hiding it: when the cap
fires, the interface tells you exactly which points went unanswered and that the claim would
otherwise have been auto-approved.

## What we learned

That the interesting problem in applied AI often isn't capability, it's calibration — and that
measuring your own system honestly is harder, and more valuable, than making it look good. We
learned how easily a benchmark corrupts itself: one of our own data "fixes" silently deleted the
fraud evidence from a claim still labelled as fraud, which we only caught because a previously
correct answer regressed.

We also learned that an unchallenged last word decides debates, for AI agents much as for people.

## What's next for ClaimLens

Real insurer data and claims-system integration. Learned calibration — training against an
asymmetric reward where confident errors are punished hardest, rather than prompting for it.
Forensics for AI-generated documents and images, since that's where the fraud is heading. An
adjuster feedback loop, so human overrides improve the confidence model. And an audit export, so
a regulator can see why any given claim was decided the way it was.

## Built with
python · fastapi · sqlite · nextjs · typescript · tailwindcss · groq · gpt-oss-120b ·
open-meteo · pytest · vercel · render
