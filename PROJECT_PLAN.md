# PROJECT_PLAN.md — ClaimLens: AI Claims Investigation Copilot

This is the single source of truth for this build. Read this whole file before writing
any code. Work through the Stages in order — never skip ahead.

---

## PART 1 — The Hackathon, in full

**Event:** AI Builders Hackathon (Devpost) — "Building the Future of Intelligent Systems"
**Deadline:** Sep 16, 2026 @ 8:30am GMT+5:30
**Theme:** Fully open-ended. No fixed topic. Judges explicitly say they do NOT want "pitch
decks, concept videos, or AI wrappers with minimal differentiation" — they want products
people would actually adopt.

### Required submission materials
1. **Project Submission Form** — team info, project name, description, links.
2. **Working Product** — a functional prototype judges can understand and evaluate.
3. **Source Code** — a **public GitHub repo**, with clear documentation and setup
   instructions. Must be original work.
4. **Demo Video** — up to 5 minutes. Must cover: the problem being solved, how the
   solution works, key features, the role of AI in the product, and a live demonstration.
5. **Presentation Deck** — up to 10 slides. Must cover: Problem Statement, Solution
   Overview, Target Users, Product Features, Technical Architecture, AI Technologies Used,
   Impact and Value Proposition, Future Roadmap.

### Judging criteria and weights (design every decision around this)
| Criterion | Weight | What judges are actually checking |
|---|---|---|
| Technical Implementation | 25% | Quality of AI model/agent/workflow design and system architecture |
| Problem Solving & Impact | 25% | Does it address a real need, is it practically applicable, is impact clearly demonstrated |
| Innovation & Creativity | 20% | Originality, how creatively AI is applied |
| User Experience & Design | 15% | UI quality, ease of use, workflow design, accessibility, polish |
| Presentation & Demo | 15% | How effectively the team communicates vision, solution, and technical decisions |

Technical + Impact alone are **half the score**. Polish and pitch quality make up the
rest. Innovation matters but is weighted less than "does this work and does it matter."

---

## PART 2 — Research grounding (so the pitch is credible, not just plausible-sounding)

### The problem, with real numbers
- US insurance fraud losses are estimated at **~$308 billion/year** (2025 estimate; health
  $68B, workers' comp $34B, auto $29B, general P&C ~$45B). [Hesper AI](https://gethesperai.com/blog/insurance-fraud-statistics-2026/), [Fortunly](https://fortunly.com/statistics/insurance-fraud-statistics/)
- **10–20% of all insurance claims contain fraudulent elements**, but **75% of flagged
  claims are never fully investigated** — this is a capacity problem, not just a detection
  problem, which is exactly what an AI copilot (not a black-box auto-denier) is positioned
  to fix. [Hesper AI](https://gethesperai.com/blog/insurance-fraud-statistics-2026/)
- Fraud costs the average US household **$400–$932/year** in higher premiums. [Fortunly](https://fortunly.com/statistics/insurance-fraud-statistics/)
- Only **32% of insurers** currently use algorithmic fraud-detection tools (up from 10% a
  decade ago) — meaning most of the market still isn't automated. [Fortunly](https://fortunly.com/statistics/insurance-fraud-statistics/)
- Fraud itself is becoming AI-powered: deepfake fraud attempts are up **2,137%** and
  AI-enabled document fraud is up **3,000%** since 2023, with AI-generated fakes passing
  traditional verification **>90%** of the time. This is the strongest framing hook: *fraud
  is now an AI-vs-AI arms race, and insurers need an AI-native defense, not legacy rules
  engines.* [Hesper AI](https://gethesperai.com/blog/insurance-fraud-statistics-2026/)
- Industry-wide, insurers spend **$5.3B/year** fighting fraud and lose **$8.50 for every
  $1 spent** — AI adoption in investigation could save an estimated **$80–160B cumulatively
  by 2032**. [Hesper AI](https://gethesperai.com/blog/insurance-fraud-statistics-2026/)

**Use these numbers in the deck's Problem Statement and Impact slides — cite the source
links above on the slide in small text for credibility.**

### The technical idea, with real grounding
- **Adversarial debate as a verification mechanism** is an established AI safety/oversight
  technique, not something we invented from nothing: Irving, Christiano & Amodei (OpenAI),
  *"AI Safety via Debate"* (2018), proposed having two AI agents argue opposing sides of a
  question in front of a judge, on the theory that it's easier to verify a winning argument
  in a debate than to directly verify a hard claim. [arXiv](https://arxiv.org/pdf/1805.00899), [OpenAI](https://openai.com/index/debate/)
  ClaimLens's Prosecutor/Defender/Judge structure is a direct, practical application of this
  idea to claims investigation. Say this explicitly in the deck's Technical Architecture
  slide — it shows judges you understand *why* the design works, not just that it looks
  interesting.
- **Calibrated / verbalized confidence** is an active area of LLM research: asking a model
  to state its confidence in words, cross-checked via self-consistency (asking it multiple
  times / from different angles and checking agreement), is a documented way to get usable
  uncertainty estimates without needing to retrain the model. [On Verbalized Confidence Scores](https://arxiv.org/html/2412.14737v2), [Two Samples Are Enough](https://openreview.net/forum?id=66D3rZrNjV)
  This is our **practical, time-boxed calibration approach** (see Stage 6). A full
  reinforcement-learning approach that trains a model against an asymmetric reward
  (confidently-wrong punished harder than uncertain) is a real, more powerful technique —
  it's the stretch goal in Stage 6b, only if time and GPU access allow.

---

## PART 3 — Rubric-to-feature mapping (nothing in the product should be unmapped)

| Judging criterion | Weight | What ClaimLens delivers against it | Where it's proven |
|---|---|---|---|
| Technical Implementation | 25% | Multi-agent adversarial debate (Prosecutor/Defender/Judge), tool-use evidence gathering incl. a real external API call, verbalized-confidence + self-consistency calibration layer, auto-resolution gate, a measured baseline-vs-calibrated comparison | Live demo + GitHub code + Architecture slide |
| Problem Solving & Impact | 25% | Targets a $308B/year problem; solves both fraud losses AND wrongful-denial risk; quantifies $ saved, hours saved, and confidently-wrong-rate reduction on a transparent synthetic benchmark | Analytics dashboard scorecard + Impact slide |
| Innovation & Creativity | 20% | "AI that admits uncertainty" is a distinctive angle almost no other team will build; grounded in real debate/calibration research, not just a chatbot wrapper | Technical Architecture slide + demo narration |
| User Experience & Design | 15% | Real adjuster dashboard: case queue, per-case debate transcript viewer, evidence exhibits, confidence gauge, portfolio analytics charts — not a raw API or notebook | Live product walkthrough |
| Presentation & Demo | 15% | Clean 5-min demo script: submit claim → watch investigation → verdict + confidence → scorecard with real numbers | Demo video |

---

## PART 4 — Product spec

**Name:** ClaimLens
**Target users:** Insurance claims adjusters and SIU (Special Investigations Unit) teams
(primary). Policyholders benefit secondarily via faster resolution on clear-cut claims.

**Responsible-AI framing (use this exact framing in the deck and demo — it is what makes
the product credible instead of naive):** ClaimLens never autonomously *denies* a claim.
It only auto-resolves claims where it is highly confident **and** the outcome is a clean
approval. Anything uncertain, or any case pointing toward denial, is always escalated to a
human adjuster with full evidence and reasoning attached. The AI's job is to bring
transparent, evidence-backed triage to overloaded adjusters — not to replace their
judgment on high-stakes decisions.

**Core user flow:**
1. A claim is submitted (policyholder details, claim description, amount, supporting
   documents/photos — for the hackathon, most claims come from our synthetic generator,
   plus a manual "submit one yourself" form for the live demo).
2. The evidence-gathering agent assembles a case file (policy terms, claim history,
   document consistency checks, an external weather check for accident claims).
3. The debate engine runs: Prosecutor argues suspicion, Defender argues legitimacy, Judge
   weighs both and produces a recommendation.
4. The calibration layer attaches a confidence tier (HIGH / MEDIUM / LOW) to that
   recommendation.
5. The auto-resolution gate: HIGH-confidence clean approvals resolve instantly. Everything
   else (MEDIUM, LOW, or any recommendation leaning toward denial) goes to the human
   adjuster queue with the full case file attached.
6. The adjuster dashboard shows the case queue, lets an adjuster open any case to see the
   full debate transcript and evidence, and shows portfolio-wide analytics.

---

## PART 5 — Metrics ("measures") — build every one of these, they are the proof-it-works layer

**Must-have (build these, they carry the demo):**
1. **Decision Accuracy** — % of recommendations matching synthetic ground truth.
2. **Confidently-Wrong Rate** — % of HIGH-confidence recommendations that were actually
   wrong. This is the headline metric — the whole point of calibration is to make this
   number small.
3. **Baseline Comparison** — run the same synthetic claims through (a) a naive single-pass
   "just ask the model to decide" baseline and (b) the full ClaimLens pipeline. Report
   Confidently-Wrong Rate and Accuracy for both, side by side. This single comparison is
   the most convincing technical proof point in the whole project.
4. **Auto-Resolution Rate** — % of claims resolved without human involvement.
5. **False Positive Rate** — legitimate claims wrongly flagged as fraud (customer-harm
   metric).
6. **False Negative Rate** — fraudulent claims wrongly approved (loss metric).
7. **Estimated Fraud $ Caught** — sum of claim amounts correctly identified as fraud.
8. **Estimated Adjuster Hours Saved** — auto-resolved count × assumed avg. manual review
   time (make this assumption explicit and visible, e.g. "assuming 22 min/claim").

**Nice-to-have (build if time allows in Stage 11/12):**
9. Escalation rate broken down by confidence tier.
10. Evidence completeness score (% of evidence sources successfully retrieved per case).
11. Average time-to-decision per claim.
12. Cost-benefit ratio ($ saved ÷ estimated cost of running the AI pipeline on that volume).

All of these get computed once in Stage 11 across the full synthetic batch and displayed
on the Portfolio Analytics page (Stage 10) and restated on the Impact slide of the deck.

---

## PART 5b — Evaluation protocol (added at Stage 5 — this is what makes the numbers credible)

**Development set (13 claims): CLM-0001, CLM-0006, CLM-0014, CLM-0019, CLM-0024, CLM-0025,
CLM-0027, CLM-0030, CLM-0032, CLM-0033, CLM-0034, CLM-0035, CLM-0036.** The first 7 were
inspected and run during Stages 2-5; the other 6 drove data or evidence-rule fixes before the
split existed and were moved here after Stage 6 (see docs/METHODOLOGY.md). All are
contaminated by definition. All prompt iteration, debugging and design changes happen here and only here.

**Held-out set (the other 27 claims).** Not inspected, not run, not tuned against until the
final Stage 11 batch. No looking at individual held-out transcripts to decide how to change a
prompt. If a held-out claim is ever used to drive a change, it moves to the dev set
permanently and is excluded from the headline numbers.

**Budget-constrained sample (locked Sep 13):** Groq's free tier has a confirmed 200,000
tokens/day cap, leaving ~475,000 tokens before the deadline for all remaining work. The full
27-claim held-out run (~640k) does not fit. Stage 11 therefore evaluates a **pre-registered
stratified random sample of 15 held-out claims**, selected with a fixed seed, stratified to
preserve the held-out set's fraud/legitimate ratio and spread across difficulty tiers, chosen
and logged (with a hash of the ID list) **before any held-out claim is run**. The remaining 12
held-out claims stay unused and unseen.

**Reporting rules for a small sample — follow these exactly:**
- **Report raw counts, not percentages**, for confidence-tier outcomes. "3 of 7 HIGH-confidence
  answers were wrong" is honest; "43% confidently wrong" implies precision that n=15 cannot
  support and is the kind of overclaim a technical judge spots immediately.
- State the sample size and the pre-registration plainly on the results slide, in the README
  and in the demo narration. Volunteering the limitation is what makes the rest credible.
- Report the "always approve" reference line alongside every accuracy figure.
- If the difference between baseline and ClaimLens is within one or two claims, say so — call
  it directionally suggestive rather than demonstrated.

**Reporting rule:** the headline accuracy and confidently-wrong figures come from the
pre-registered held-out sample. Dev-set figures may be shown but must be labelled as the set the system was
tuned on. State this split in the README, METHODOLOGY.md and on the results slide.

**Why this exists:** without it, every prompt improvement made after seeing a failure is
partly memorisation, and the Stage 11 comparison measures how well we fitted 40 known cases
rather than whether the architecture works. Train/test hygiene is cheap here — it costs
discipline, not tokens — and it is the difference between a number a judge can rely on and a
number they have to take on faith.

**The tuning line, for prompt changes:** fixing a general reasoning defect is engineering
("a rebuttal asserting that a practice is permissible does not address whether its timing is
suspicious"). Encoding a specific case's answer is cheating ("watch for comprehensive cover
added days before a theft"). Test each proposed change by asking: would someone who had never
seen the dev claims have written this? If no, don't write it. Log every prompt change in
METHODOLOGY.md with that justification.

---

## PART 6 — Technical architecture (final decisions — do not relitigate these mid-build)

- **Backend:** Python + FastAPI. Reasons: fast to build, official Groq SDK support, easy
  synthetic-data generation with `faker`.
- **Frontend:** Next.js + TypeScript + Tailwind CSS.
- **LLM provider:** **Groq** (free tier). Groq's API is OpenAI-compatible — use the official
  `groq` Python SDK (`pip install groq`), base URL `https://api.groq.com/openai/v1`, key read
  from `GROQ_API_KEY` in `.env`.
- **Models (use these exact IDs):**
  - **Primary — every debate, judge, calibration and baseline call: `openai/gpt-oss-120b`.**
    131k context, ~500 tokens/sec on Groq, and it is a *reasoning* model, which is what the
    Prosecutor / Defender / Judge roles actually need. Set `reasoning_effort` to `"low"` or
    `"medium"` to keep token burn under control.
  - **Fallback if that model is unavailable or quota-blocked: `llama-3.3-70b-versatile`**
    (131k context). If you switch, switch it for the baseline *and* the pipeline together.
  - **Utility only — never for anything that feeds the Stage 11 comparison:
    `llama-3.1-8b-instant`** (fast, cheap; fine for throwaway formatting helpers).
- **HONESTY RULE — do not break this.** The naive baseline (Stage 4) and the full ClaimLens
  pipeline (Stages 5–6) must run on the **same model with the same settings**. The entire
  claim of the Stage 11 comparison is "same model, better architecture." Giving our pipeline
  a stronger model than the baseline would make the headline number meaningless, and it is
  exactly the kind of thing a sharp judge will ask about.
- **Always request JSON output** for decisions and confidence values (Groq supports a JSON
  response format) so results are parsed reliably instead of regex-scraped out of prose.
- **A note in our favour:** open models like these tend to be *more* overconfident than
  frontier models. That makes the naive baseline's "confidently wrong" rate higher and the
  improvement from our calibration layer more visible. The free tier isn't just a cost
  workaround here — it makes the demo's core point land harder.
- **Storage:** SQLite (via `sqlmodel` or plain `sqlite3`) for claims, evidence, debate
  transcripts, and results. Simple, no external DB server needed, still supports the
  analytics queries the dashboard needs.
- **Live external API (real tool-use, not simulated):** [Open-Meteo](https://open-meteo.com/)
  for historical weather lookups on accident-date/location claims — it's free and needs no
  API key, so it's a genuine external tool call with zero setup friction.
- **Progress updates:** simple polling (frontend calls `GET /claims/{id}/status` every
  1–2 seconds) rather than WebSockets — much less to get wrong in 3 days.
- **Deployment:** Frontend → Vercel. Backend → Render or Railway (either's free tier is
  fine).
- **Explicitly out of scope for the hackathon build:** user authentication/login, payment
  processing, real insurer data integration, a production-grade database. Note these as
  "Future Roadmap" items in the deck instead of building them.

---

## PART 6b — Free-tier budget: the real constraint, and how not to run out

Groq's free tier is generous but **rate-limited per model**, and on this project the limits —
not the code — are the thing most likely to cost you a day. Reported free-tier limits are
around **30 requests/minute, ~6,000 tokens/minute, ~1,000 requests/day** for most models
([TokenMix](https://tokenmix.ai/blog/groq-free-tier-limits-2026),
[Grizzly Peak](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)).
**These are third-party figures and change often — check your own account's real numbers at
`console.groq.com/settings/limits` before the Stage 11 batch run.**

**Our budget maths (why the plan is sized the way it is):**
- Full pipeline per claim = **4 model calls**: Prosecutor, Defender, Judge, then the Judge a
  second time with the two arguments presented in the opposite order (the order-swap
  consistency check — see Stage 6). Verbalized confidence is returned inside the Judge calls
  rather than costing a separate call.
- Naive baseline per claim = 1 call.
- At **40 claims**: (40 × 4) + (40 × 1) = **200 calls** for one complete Stage 11 run — inside
  the confirmed 1,000/day request budget with room to re-run.
- **Requests are not the binding limit — tokens are.** Confirmed from Groq's response headers:
  1,000 requests/day and 8,000 tokens/minute. A tokens-per-day cap may also exist and is not
  exposed in the headers; third-party figures for it have already proved unreliable, so do not
  plan around a guessed number. Instead: measure real tokens-per-claim on 3 claims at Stage 5,
  multiply, and schedule from that.
- Observed cost reference: a single baseline call ran ~1,800 tokens, of which ~1,786 output
  tokens were *reasoning* tokens. Reasoning effort is by far the largest cost lever if the
  batch needs to shrink.
- The Stage 11 runner checkpoints per claim and resumes, so hitting a daily cap is a
  scheduling problem, not a lost run: it resumes the next day. This only works if the batch is
  started early — Day 3 morning at the very latest.

**Rules that follow from this — build them in, don't bolt them on later:**
1. **Checkpoint after every claim.** Write each result to the results JSON as soon as it's
   done, and on startup skip any claim already present. A crash or a 429 at claim 38 must
   never mean starting over.
2. **Retry with exponential backoff on HTTP 429** (rate limit), with a cap. Every model call
   goes through one shared helper function that handles this — not scattered try/excepts.
3. **Keep prompts tight.** Pass a compact evidence object, not raw dumps. Every wasted token
   is quota.
4. **No LLM calls in Stage 2.** Synthetic claim generation is deterministic (faker +
   templates). Save the request budget for the agent pipeline.
5. **Test on 3–5 claims, never the full set,** until Stage 11. Debug cheap, run expensive
   once.
6. If you do burn the daily quota, the answer is to wait for the reset or switch to the
   fallback model **for both pipelines** — never to quietly run the baseline on a weaker
   model than ClaimLens.

---

## PART 7 — Target repository structure

```
claimlens/
  CLAUDE.md
  PROJECT_PLAN.md
  README.md
  .gitignore
  backend/
    app/
      main.py                # FastAPI app entrypoint
      models.py               # SQLModel/DB models
      db.py                    # DB setup
      synthetic/
        generate_claims.py     # Stage 2
      agents/
        evidence_agent.py       # Stage 3
        naive_baseline_agent.py # Stage 4
        debate_agent.py          # Stage 5
        calibration.py            # Stage 6
      routes/
        claims.py                 # Stage 7
        analytics.py
      tools/
        weather_tool.py            # Open-Meteo call
    data/
      synthetic_claims.json
      results_naive.json
      results_claimlens.json
    tests/
    requirements.txt
    .env.example
  frontend/
    app/ (or pages/)
      intake/                     # Stage 8
      dashboard/                  # Stage 9
      analytics/                  # Stage 10
    components/
    package.json
```

---

## PART 8 — Stage-by-stage execution plan

For every stage below: copy the **PROMPT TO USE** text into Claude Code exactly as
written (fill in only what's marked to fill in). Do not proceed to the next stage until
you have personally checked the **Acceptance Criteria** and they pass.

**Who runs the commands:** Claude runs them. Claude installs packages, runs scripts, starts
and stops servers, and hits endpoints itself, then reports the real output — see rules 9–11
in CLAUDE.md. The only things left to the human are: pasting the real API key into
`backend/.env`, browser-based deployment sign-ins (Vercel / Render), and *looking* at pages
in a browser to judge whether they read well. The "You verify" notes under each stage mean
"read Claude's reported output and sanity-check it", not "go type these commands yourself" —
except where a stage explicitly says to open a browser.

### Stage 0 — Local setup (you do this yourself, no Claude prompt yet)
1. On your laptop, create a new folder, e.g. `claimlens`, anywhere you like (Desktop or
   a Projects folder).
2. Open that folder in VS Code (`File > Open Folder`).
3. Make sure Node.js (v18+) and Python (3.10+) are installed (`node -v`, `python3 -V` in
   a terminal). Install whichever is missing from nodejs.org / python.org.
4. Install/open Claude Code in VS Code if you haven't already (the Claude Code extension
   or `claude` CLI in the VS Code terminal).
5. Put the two files `CLAUDE.md` and `PROJECT_PLAN.md` (this file) directly inside the
   `claimlens` folder — not in a subfolder.
6. Get a **free Groq API key** from `console.groq.com/keys` (no credit card needed). Keep it
   handy — you'll paste it into `backend/.env` yourself, never into chat.
7. Open a terminal inside VS Code and run `git init` to start version control.

**Acceptance check:** the folder contains exactly `CLAUDE.md` and `PROJECT_PLAN.md`, `git
init` ran with no errors, and you can open a terminal inside VS Code.

---

### Stage 1 — Project scaffolding
**Goal:** create the folder/file skeleton from Part 7, with working "hello world" checks
for both backend and frontend, nothing else.

**PROMPT TO USE:**
> I've placed CLAUDE.md and PROJECT_PLAN.md in this folder. Read both completely. Then do
> ONLY Stage 1 (Project Scaffolding) from PROJECT_PLAN.md: create the backend (Python
> FastAPI) and frontend (Next.js + TypeScript + Tailwind) skeletons matching the repo
> structure in Part 7, a `.gitignore`, a `requirements.txt` for the backend, and a
> `.env.example` with `GROQ_API_KEY=` as a placeholder. Add a single working "health
> check" endpoint on the backend (`GET /health` returning `{"status": "ok"}`) and confirm
> the frontend starts and shows a default page. Do not build any business logic yet. When
> done, tell me exactly which commands to run to start each one myself, and wait for me to
> confirm before continuing.

**You verify:** run the commands Claude gives you. Backend: visiting `/health` in a
browser or `curl localhost:8000/health` should return `{"status":"ok"}`. Frontend:
`npm run dev` should start and a default page should load in the browser.

---

### Stage 2 — Synthetic claims generator
**Goal:** a script that generates a batch of realistic, labeled synthetic insurance
claims (ground truth: fraud or legitimate, plus a difficulty tag) for later stages to run
against.

**PROMPT TO USE:**
> Continue to Stage 2 (Synthetic Claims Generator) from PROJECT_PLAN.md only. Build
> `backend/app/synthetic/generate_claims.py` using `faker` that generates exactly 40
> synthetic insurance claims (mix of auto and property claims) with realistic fields
> (policyholder, policy number, claim amount, incident date/location/description,
> supporting document list). Each claim must include a hidden ground-truth label
> (`is_fraud: true/false`) and a difficulty tag (`easy`/`ambiguous`/`hard`) — include a
> real mix, not just obvious cases, so the calibration test later is meaningful. Bake in
> a handful of realistic fraud patterns (e.g. claim filed suspiciously soon after policy
> start, inconsistent incident location vs policyholder address, duplicate claim
> patterns, damage severity inconsistent with described incident). Generate everything
> deterministically with faker and templates — do NOT call an LLM anywhere in this stage,
> the free-tier request budget is reserved for the agent pipeline. Save the output to
> `backend/data/synthetic_claims.json` and print a summary count (total, fraud vs
> legitimate, by difficulty) when run. When done, show me that summary output and wait
> for me to confirm before continuing.

**You verify:** you should see a printed summary with realistic-looking numbers (e.g.
~60 claims, a mix of fraud/legit, a mix of difficulty). Open `synthetic_claims.json` and
skim a few entries — they should read like real (if fictional) claims.

---

### Stage 3 — Evidence-gathering agent
**Goal:** for any given claim, gather a structured "case file" of evidence: policy terms,
claim history, document consistency, and a real weather check.

**PROMPT TO USE:**
> Continue to Stage 3 (Evidence-Gathering Agent) from PROJECT_PLAN.md only. Build
> `backend/app/agents/evidence_agent.py` that, given one claim from synthetic_claims.json,
> assembles a structured evidence object covering: policy terms lookup (simulated from
> claim data), claim history check (e.g. how many prior claims this policyholder has
> filed, timing patterns), document consistency check (compare claimed damage/incident
> description against submitted document list for red flags), and — as a real external
> tool call — a historical weather lookup via the Open-Meteo API (no key required) for
> accident-date and location claims, to sanity-check weather-related claim narratives.
> Write a small script `backend/app/synthetic/test_evidence.py` that runs this against 3
> sample claims and prints the resulting evidence object for each. When done, run it and
> show me the output, then wait for me to confirm.

**You verify:** the printed evidence objects should look complete and sensible for all 3
sample claims, and at least one of them should show a real (not obviously fake/hardcoded)
weather API response.

---

### Stage 4 — Naive baseline agent
**Goal:** a simple single-pass "just ask the model" decision agent, built BEFORE the fancy
version, so we have an honest baseline to compare against later.

**PROMPT TO USE:**
> Continue to Stage 4 (Naive Baseline Agent) from PROJECT_PLAN.md only. Build
> `backend/app/agents/naive_baseline_agent.py`: given a claim + its evidence object, make
> ONE Groq API call using model `openai/gpt-oss-120b` that asks the model to directly decide
> APPROVE or DENY and state a confidence (as a plain 0-100% number) in a single pass, no
> debate, no cross-checking. Return JSON, not prose. Also create the shared Groq client
> helper here (`backend/app/agents/llm_client.py`) with retry + exponential backoff on 429
> rate-limit errors — every later stage must call the model through this one helper.
> This is intentionally simple — it exists only so we can later prove the fancier pipeline
> is actually better calibrated, not just fancier. Write a test script that runs it on 5
> sample claims and prints decision + confidence for each. When done, show me the output
> and wait for me to confirm.

**You verify:** you get 5 decisions with confidence numbers, format looks consistent.

---

### Stage 5 — Debate engine (Prosecutor / Defender / Judge)
**Goal:** the core adversarial reasoning pipeline.

**PROMPT TO USE:**
> Continue to Stage 5 (Debate Engine) from PROJECT_PLAN.md only. Build
> `backend/app/agents/debate_agent.py` implementing three Groq API calls (model
> `openai/gpt-oss-120b`, via the shared llm_client helper from Stage 4) in sequence for
> a given claim + evidence: (1) a Prosecutor agent that argues, using only the evidence
> provided, why this claim is suspicious/fraudulent; (2) a Defender agent that argues why
> it's legitimate, responding to the Prosecutor's points; (3) a Judge agent that reads both
> arguments and produces a recommendation (APPROVE or DENY) with reasoning, referencing
> specific evidence. Store the full transcript (all three outputs) alongside the claim.
> Write a test script that runs the full debate on 3 sample claims and prints each full
> transcript. When done, show me one full example transcript and wait for me to confirm.

**You verify:** read the transcript — the Prosecutor and Defender should each make
distinct, evidence-grounded arguments (not generic filler), and the Judge's recommendation
should clearly reference points raised in the debate.

---

### Stage 6 — Calibration layer + auto-resolution gate
**Goal:** attach an honest confidence tier to the Judge's recommendation, and decide what
auto-resolves vs. what goes to a human.

**PROMPT TO USE:**
> Continue to Stage 6 (Calibration Layer) from PROJECT_PLAN.md only. Use the same model and
> settings as Stages 4 and 5 — see the HONESTY RULE in Part 6. Build
> `backend/app/agents/calibration.py`: the Judge is run twice on the same Prosecutor and
> Defender arguments — once with the Prosecutor's case presented first, once with the
> Defender's first. This is an **order-swap consistency check**: LLM judges are known to be
> sensitive to the order in which arguments are presented, so a verdict that flips when the
> order flips is not a verdict worth acting on. Each Judge call also returns its own
> verbalized confidence (HIGH/MEDIUM/LOW) with a justification. Combine the two signals into
> a final tier: HIGH only if both orderings agree on the decision AND both verbalized HIGH;
> MEDIUM if the orderings agree but confidence is lower or mixed; LOW if the orderings
> disagree at all. (An optional `FULL_DOUBLE_DEBATE` config flag may re-run the entire
> three-call debate instead of just the Judge, for a stronger check at ~75% more tokens —
> use it for the final run only if the measured token budget allows.) Then
> implement the auto-resolution gate: auto-resolve ONLY if confidence is HIGH and the
> decision is APPROVE. Every DENY recommendation and every non-HIGH case is marked for
> human review, regardless of confidence. Test on 5 sample claims and print: decision,
> confidence tier, and whether it was auto-resolved or sent to human review. When done,
> show me that output and wait for me to confirm.

**You verify:** confirm the gate logic actually matches the rule above (spot-check: any
DENY case, whatever its confidence, should show "sent to human review").

**Stage 6b — stretch goal (optional, only attempt if you have ML/RL experience and GPU
access, e.g. a free Colab GPU, and are ahead of schedule):** instead of the prompt-based
calibration above, fine-tune a small open model with an asymmetric reward (correct+HIGH >
correct+MED > correct+LOW > wrong+LOW > wrong+MED > wrong+HIGH), similar in spirit to the
ClaimCourt research project that inspired this idea — but trained on our own original
synthetic dataset with our own original code. Do this as an addition alongside the
prompt-based approach, not a replacement — if it doesn't work by the time Stage 11 needs
to run, fall back to the Stage 6 approach without hesitation.

---

### Stage 7 — Backend API layer
**Goal:** wire everything into a real API so the frontend has something to call.

**PROMPT TO USE:**
> Continue to Stage 7 (Backend API Layer) from PROJECT_PLAN.md only. Build
> `backend/app/routes/claims.py` with endpoints: `POST /claims` (submit a new claim, kicks
> off evidence gathering + debate + calibration, returns a claim ID immediately),
> `GET /claims/{id}/status` (poll for progress: pending / gathering_evidence / debating /
> calibrating / resolved), `GET /claims/{id}` (full result: evidence, transcript,
> decision, confidence, auto-resolved or not), and `GET /claims` (list/queue, filterable
> by status). Wire these to the Stage 3/5/6 code. Test the whole flow with curl or the
> FastAPI docs page (`/docs`) end to end on at least 2 real claims from the synthetic set.
> When done, show me the exact curl commands (or /docs screenshots) proving it works end
> to end, and wait for me to confirm.

**You verify:** submit a claim via `/docs` or curl, poll its status until `resolved`, then
fetch the full result and confirm it contains evidence + transcript + decision +
confidence.

---

### Stage 8 — Frontend: claim intake
**PROMPT TO USE:**
> Continue to Stage 8 (Claim Intake UI) from PROJECT_PLAN.md only. Build a simple intake
> page where a claim can be submitted (either manually filled in, or "load a sample
> claim" from the synthetic set) and calls `POST /claims`, then shows a live status
> indicator polling `GET /claims/{id}/status` until resolved, then links to the case
> detail view. Keep styling clean and simple with Tailwind — this doesn't need to be
> fancy yet, Stage 12 is for polish. When done, tell me how to try it in the browser and
> wait for me to confirm.

**You verify:** submit a claim in the browser, watch the status update, land on a result.

---

### Stage 9 — Frontend: adjuster dashboard
**PROMPT TO USE:**
> Continue to Stage 9 (Adjuster Dashboard) from PROJECT_PLAN.md only. Build a dashboard
> page showing the case queue from `GET /claims` (filterable by status), and a case detail
> view for any claim showing: the evidence object in readable form, the full debate
> transcript (Prosecutor/Defender/Judge, clearly labeled), a visual confidence gauge
> (HIGH/MEDIUM/LOW), and whether it was auto-resolved or needs human review. When done,
> tell me how to try it and wait for me to confirm.

**You verify:** open the dashboard, click into a few cases, confirm the transcript and
evidence are both legible and clearly laid out.

---

### Stage 10 — Frontend: portfolio analytics
**PROMPT TO USE:**
> Continue to Stage 10 (Portfolio Analytics) from PROJECT_PLAN.md only. Build
> `backend/app/routes/analytics.py` computing the Part 5 "must-have" metrics across all
> processed claims, and a frontend analytics page displaying them clearly (simple charts
> are fine — bar/line, nothing fancy). Leave placeholder/zero values for now if Stage 11
> hasn't been run yet — this stage is about the page existing and reading correctly, not
> the final numbers. When done, show me how it looks and wait for me to confirm.

---

### Stage 11 — Full batch run + baseline comparison (the proof-it-works stage)
**PROMPT TO USE:**
> Continue to Stage 11 from PROJECT_PLAN.md only. Respect the Part 5b evaluation protocol:
> report headline numbers on the pre-registered held-out sample (Part 5b), and dev-set numbers separately and
> clearly labelled. Also report the trivial "always approve" reference line (60% accuracy on
> the full set) so the accuracy figures are interpretable. Write a script
> `backend/app/synthetic/run_full_batch.py` that runs EVERY claim in synthetic_claims.json
> through both (a) the naive baseline agent (Stage 4) and (b) the full ClaimLens pipeline
> (Stages 3/5/6), saving results to `results_naive.json` and `results_claimlens.json`.
> This run is quota-sensitive (see Part 6b): write each claim's result to disk as soon as it
> completes, skip any claim already present in the results file on startup so an interrupted
> run resumes instead of restarting, route every model call through the retry/backoff helper,
> and print running progress (claim N of 40) so it's clear it's alive during the ~1-2 hours
> this takes.
> Then compute and print a comparison table: Accuracy and Confidently-Wrong Rate for naive
> vs. ClaimLens, plus all Part 5 must-have metrics for ClaimLens. Wire these real numbers
> into the analytics page from Stage 10. When done, show me the full comparison table and
> wait for me to confirm the numbers look right (ClaimLens's confidently-wrong rate should
> be meaningfully lower than the naive baseline's — if it isn't, tell me honestly and we'll
> debug the calibration logic before moving on).

**You verify:** ClaimLens's confidently-wrong rate is clearly lower than the naive
baseline's. If not, this stage isn't actually done — go back to Stage 6 and fix it. Do not
move on with a comparison that doesn't favor the design; it needs to be true, not just
presented as true.

---

### Stage 12 — UX polish
**PROMPT TO USE:**
> Continue to Stage 12 from PROJECT_PLAN.md only. Polish the intake, dashboard, and
> analytics pages: consistent styling, loading states, error handling (what happens if the
> backend is down or a claim fails), empty states, and a quick check that the pages don't
> break on a narrow/mobile browser width. Don't add new features. When done, walk me
> through what changed and wait for my confirmation.

---

### Stage 13 — Deployment
**PROMPT TO USE:**
> Continue to Stage 13 from PROJECT_PLAN.md only. Prepare the frontend for Vercel
> deployment and the backend for Render or Railway deployment (whichever you recommend as
> simpler given the current code) — env var configuration, build scripts, CORS settings so
> the deployed frontend can call the deployed backend. Give me the exact click-by-click or
> CLI steps to actually deploy both, since you can't deploy for me. When done, wait for me
> to confirm the live URLs work before continuing.

**You do:** actually follow the deployment steps (you'll need free accounts on Vercel and
Render/Railway). Test the live URL yourself before moving on.

---

### Stage 14 — Documentation
**PROMPT TO USE:**
> Continue to Stage 14 from PROJECT_PLAN.md only. Write a complete `README.md`: what
> ClaimLens is and why (use the Part 2 research numbers), architecture overview, setup
> instructions to run locally (backend + frontend), the live demo URL, and a summary of
> the Stage 11 comparison numbers. Make sure it reads well to someone who has never seen
> this project before — a judge will read this cold.

---

### Stage 15 — Demo video
Do this yourself (Claude Code can help draft the script, but you record it):
> Help me write a tight 5-minute demo video script for ClaimLens following the required
> structure: problem, solution, key features, AI's role, live demo. Use the Part 2 numbers
> for the problem framing and the Stage 11 comparison numbers for the payoff. Keep the live
> demo portion to under 2 minutes: submit one clean-legitimate claim (shows auto-resolve)
> and one suspicious claim (shows escalation with full evidence trail), then end on the
> analytics scorecard.

---

### Stage 16 — Presentation deck
> Help me draft the content (not design) for a 10-slide deck covering: Problem Statement,
> Solution Overview, Target Users, Product Features, Technical Architecture (mention the
> debate + calibration research grounding from Part 2), AI Technologies Used, Impact and
> Value Proposition (use Part 2 + Stage 11 numbers), Future Roadmap (mention the things we
> explicitly left out of scope, e.g. real insurer integrations, as roadmap items, and the
> Stage 6b stretch goal if not completed). One slide per topic, keep bullets short.

---

### Stage 17 — Final submission
Manual checklist — go through PART 9 below one line at a time before submitting.

---

## PART 9 — Final submission checklist
- [ ] Project Submission Form completed on Devpost
- [ ] Working product deployed and live URL tested fresh (not just "it worked once")
- [ ] GitHub repo is public, has the full README, and contains only original code
- [ ] Demo video uploaded, under 5 minutes, covers all 5 required points
- [ ] Deck finalized, 10 slides or fewer, covers all 8 required sections
- [ ] Re-read Part 3 (rubric mapping) and confirm every row still has a real proof point
- [ ] Submitted with time buffer before Sep 16, 2026, 8:30am GMT+5:30 — do not submit at
      the last minute, Devpost/network issues at deadline time are a real risk

## PART 10 — Risk notes
- The single biggest risk is scope creep — resist adding features not in this plan.
- **Free-tier quota is the second biggest risk.** Burning the daily request budget on
  debugging, or discovering at 2am that the Stage 11 batch needs two hours it doesn't have,
  is a very real way to lose this. Follow Part 6b: test on 3–5 claims, checkpoint every
  result, start the full batch early on Day 3 at the latest.
- The second biggest risk is an unconvincing or dishonest-feeling Stage 11 comparison —
  if the numbers don't actually favor the calibrated pipeline, fix the pipeline, don't
  fix the numbers.
- Always keep the "never auto-denies, only auto-approves when certain" framing front and
  center — it's what makes this pitch credible instead of naive to anyone who knows the
  insurance industry is regulated and liability-heavy.
