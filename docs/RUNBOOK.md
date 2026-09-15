# ClaimLens — post-batch runbook

The sequence from "the Stage 11 batch has finished" to "submitted", as commands. Follow it in order;
each step says what it depends on and what "done" looks like. Written so a fresh session can take over
with nothing but this file and the repository.

**Deadline: Sep 16, 2026, 08:30 IST = 03:00 UTC.** (01:00 IST on Sep 16 = 19:30 UTC on Sep 15.)

All commands run from the repository root, `C:\Users\HP\Desktop\AI Builders Hackathon`, in PowerShell.

---

## Rules that still apply

- **No model calls** other than the Stage 11 batch itself. No live claim submissions.
- **No pipeline changes**: prompts, cap rule, tier rule, gate and model settings stay frozen.
- **Don't look at held-out results before the batch finishes.** Until `BATCH COMPLETE` is in the log,
  read the log only through the filtered command below, never the raw log, results files or `/analytics`.
- **Report raw counts, never percentages**, with the always-approve reference beside every accuracy
  figure. `scripts/fill_results.py` enforces this; never type result numbers into a document by hand.
- **Never commit `.env` or `.venv`.** Every commit below runs a key scan first.
- **Step 3 is a hard stop**: the real fill (step 4) happens only after Mitali has seen the numbers and
  said to go ahead.

## Update, 2026-09-15 06:19 UTC

- **Crash and restart.** The laptop shut down uncleanly at about 05:42 UTC, and Windows Update restarted it
  four times while installing updates. No further reboot is pending, and the power settings survived.
  The batch was restarted at 06:17 UTC with the step 0 command below (logged in `docs/METHODOLOGY.md`).
  It is now **14 of 15**, 264,311 tokens used, runner pid 29448. It is waiting for the token refill
  before CLM-0040, the last claim.
- **Deployed:**
  - frontend https://ai-builders-hackathon.vercel.app
  - backend https://claimlens-api.onrender.com

  Both verified: `/health`, `/samples` and `/analytics` return 200; the frontend and its `/api` proxy
  reach the backend; CORS allows the Vercel origin and rejects unrelated ones; live submission is off.
  `preflight.py` with both URLs passes frontend, backend and endpoints.
- **Use the short production domain `ai-builders-hackathon.vercel.app` everywhere:** README, Devpost,
  CORS, command arguments. Never use a deployment-specific hashed Vercel URL; it changes on every push.

## State when this runbook was written (2026-09-15 05:23 UTC)

- Batch: running as pid 29068. **13 of 15** claims finished (the 13th at 04:43 UTC); 253,317 tokens used
  over 89 accepted requests. It was on claim 14 (CLM-0039), waiting for the token allowance to refill.
  Remaining: the rest of CLM-0039 and all of CLM-0040. Rough estimate for `BATCH COMPLETE`: 08:00–09:30 UTC.
  No permanent failures (CLM-0026 failed once, then completed on retry).
- Power: on charger. Sleep and hibernate on charger: never. Lid close: do nothing, on charger and battery.
  A Windows power-plan change can reset these; step 0 re-checks them.
- GitHub: https://github.com/Mitalimehta02/AI-Builders-Hackathon is **public** (checked anonymously).
  Local `master` = `origin/master`.
- Held back, not committed: `backend/data/results_naive.json`, `results_claimlens.json`,
  `stage11_batch_output.log`, `llm_logs/2026-09-14.jsonl`, `llm_logs/2026-09-15.jsonl`, `weather_cache.json`.
- Documents on disk: `README.md`, `docs/DECK_CONTENT.md`, `docs/VIDEO_SCRIPT.md` (deck and video are not
  committed yet). **`docs/DEVPOST_SUBMISSION.md` is not on disk yet.**
- Deck and video keys already use the README spellings. `preflight.py` failed on documents, git and
  snapshot and skipped the three live checks, all expected at this point. The secrets, tests (92) and
  build checks passed.

---

## Step 0 — Confirm the batch finished and the machine is safe

**Depends on:** nothing.

```powershell
# Progress without per-claim results (safe to run at any time)
Select-String -Path backend\data\stage11_batch_output.log -Pattern "PROGRESS|BATCH COMPLETE|failure [0-9]|giving up|Traceback|STOP" | Select-Object -Last 6 | ForEach-Object { $_.Line }
Get-Content backend\data\stage11_batch_status.json
Get-Process -Id 29068 -ErrorAction SilentlyContinue

# Power: must be on charger, standby 0, lid action 0
Get-CimInstance Win32_Battery | ForEach-Object { "on charger: $($_.BatteryStatus -eq 2); charge: $($_.EstimatedChargeRemaining)%" }
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC|Current DC"
```

- **Still running:** wait. The runner sleeps through refills by itself.
- **Process gone and no `BATCH COMPLETE`:** restart it. The runner resumes from saved results and never
  repeats a finished call. This exact command was used successfully after the 05:42 UTC crash on Sep 15.
  It runs as its own hidden process, independent of any terminal or session, and appends to the log:
  ```powershell
  $backend = 'C:\Users\HP\Desktop\AI Builders Hackathon\backend'
  if (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'run_full_batch' }) { 'already running' } else {
    Start-Process -FilePath cmd.exe -ArgumentList '/c', 'set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe -u -m app.synthetic.run_full_batch >> data\stage11_batch_output.log 2>&1' -WorkingDirectory $backend -WindowStyle Hidden
  }
  ```
  The runner refuses to start while the status file shows a live run (a heartbeat within the last
  15 minutes). After a crash, wait until the heartbeat is older than that. Then record the restart in
  `docs/METHODOLOGY.md`: when, why, and that it wasn't prompted by any result.
- **Windows Update can restart the machine** outside active hours, which are 08:00–02:00 IST, so a
  restart is possible 02:00–08:00 IST (20:30–02:30 UTC). After any reboot, run the checks above again.
- **Not finished and the documents must be finalised now:** this is Mitali's decision. Stop the batch
  (`Stop-Process -Id 29068`) and report under the pre-registered stopping rule: the first N claims in
  ascending-ID order. Steps 3 and 4 then need `--truncated-at-deadline`. The fill script adds the
  truncation disclosure automatically.

**Done when:** the filtered log shows `BATCH COMPLETE`, and the status file says `"running": false`.

---

## Step 1 — Commit and push the Stage 11 results

**Depends on:** step 0.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\commit_stage11_results.ps1
```

The script:
1. Refuses to run unless `BATCH COMPLETE` is logged, the batch is no longer running, and nothing is already staged.
2. Stages exactly the six held-back files, plus any newer model-call log (which it lists).
3. Checks nothing else got staged and runs a key scan.
4. Commits with a written message, pushes, and checks that local and GitHub match.

If Render is connected to the repo, this push redeploys the API with the real results.

**Done when:** it prints `in sync: True`, and `git status --short` lists only the uncommitted documents.

---

## Step 2 — Rename the two keys in the Devpost document (once it exists)

**Depends on:** `docs/DEVPOST_SUBMISSION.md` being on disk. If it never arrives, skip this step. The fill
script skips a missing document with a warning, and the Devpost form is then filled in by hand from the
approved numbers.

The Devpost file uses two key names that differ from the README's. Rename them, markers and key list:

```powershell
backend\.venv\Scripts\python.exe -c "import pathlib; p = pathlib.Path('docs/DEVPOST_SUBMISSION.md'); t = p.read_text(encoding='utf-8'); t = t.replace('[[PLACEHOLDER:auto_resolved]]', '[[PLACEHOLDER:claimlens_auto_resolved]]').replace('[[PLACEHOLDER:fraud_value_caught]]', '[[PLACEHOLDER:claimlens_fraud_dollars_caught]]').replace('`auto_resolved`', '`claimlens_auto_resolved`').replace('`fraud_value_caught`', '`claimlens_fraud_dollars_caught`'); p.write_text(t, encoding='utf-8')"
Select-String -Path docs\DEVPOST_SUBMISSION.md -Pattern "auto_resolved\]\]|fraud_value_caught"
```

**Done when:** the second command prints only `claimlens_`-prefixed matches (or nothing), and step 3
reports no unknown marker in `docs/DEVPOST_SUBMISSION.md`.

---

## Step 3 — Preview the numbers, then STOP for approval

**Depends on:** step 1 (and step 2 if the Devpost file exists).

```powershell
# The complete analytics output
Push-Location backend
.\.venv\Scripts\python.exe -c "import json; from app.routes.analytics import compute_analytics; print(json.dumps(compute_analytics(), indent=2))"
Pop-Location

# Exactly what would be written into the documents (writes nothing)
backend\.venv\Scripts\python.exe scripts\fill_results.py --check
```

For a truncated run, add `--truncated-at-deadline` to the second command.

Show Mitali, without writing to any document:
- accuracy for both systems with the always-approve line;
- confidently-wrong counts for the baseline, and for ClaimLens before and after the cap;
- auto-resolved count;
- false positives and false negatives;
- fraud value caught;
- adjuster hours saved;
- how many claims the cap acted on;
- the full `--check` preview.

**STOP here.** Do not run step 4 until Mitali explicitly approves.

**Done when:** `--check` prints `validation passed; nothing was written`, with no unknown or unkeyed
markers in any document, and Mitali has approved in writing.

---

## Step 4 — Fill the documents for real

**Depends on:** step 3 approval, and both deployed URLs.

```powershell
backend\.venv\Scripts\python.exe scripts\fill_results.py --frontend-url https://ai-builders-hackathon.vercel.app --backend-url https://claimlens-api.onrender.com
git diff --stat
```

Add `--truncated-at-deadline` only if step 0 ended in truncation.

**Done when:**
- It prints `filled N result marker(s)` for README.md, DECK_CONTENT.md, VIDEO_SCRIPT.md and, if present,
  DEVPOST_SUBMISSION.md.
- `backend/data/stage11_final_analytics.json` exists.
- No URL-marker warning is printed.
- `git diff` shows only number, note and URL substitutions.

---

## Step 5 — Point the sample loader at the Stage 11 results

**Depends on:** step 1 (the results must be committed, or the deployed API won't have them).

**Why:** the intake and dashboard pages load six stored development-set results. They were produced with
the since-removed rebuttal round at temperature 1.0, which `docs/METHODOLOGY.md` marks as not comparable
with the final run. Demoing them would show output the current system wouldn't produce.

This is a code change. It makes no model calls and changes no pipeline setting.

1. **`backend/app/samples.py`:** build the samples from `backend/data/results_claimlens.json`. Use each
   pre-registered claim whose ClaimLens status is `complete`: evidence from `claims[id]["evidence"]`, result
   from `claims[id]["result"]`, and the claim itself from `synthetic_claims.json` passed through
   `sanitize_claim`.
   - Keep `_case_detail` and its output shape, so the frontend needs no type changes.
   - **Keep the source labels**: every sample carries `stored_sample.source`. The new label should say what
     produced it, e.g. "Stage 11 evaluation run, 2026-09-14/15: final configuration (temperature 0.2, no
     rebuttal round), pre-registered held-out sample".
   - Replace the `is_dev_claim` guard with a check that the claim is in `stage11_sample.json`, and serve
     nothing while the batch status says running.
   - Update the module docstring and `NOTE` accordingly.
2. **`POST /claims`** still refuses held-out claim IDs (403). Leave that as it is: showing stored results
   is not the same as re-running a claim.
3. **Tests:** update `backend/tests/test_samples_and_config.py`, which asserts development-set samples
   (CLM-0035). Check `test_dashboard_api.py` and `test_deploy_config.py`, which call `/samples`. Add a test
   that samples come only from the pre-registered sample. If the test count changes, update
   `EXPECTED_TESTS` in `scripts/preflight.py` in the same commit.
4. **Frontend:** search `frontend/` for "development-set" or "dev sample" wording on the intake and
   dashboard pages, and update it. Keep the label display.
5. **README:** update the "stored sample cases predate the final configuration" bullet under Known quirks.
   Then add a dated entry to `docs/METHODOLOGY.md`: per-claim held-out results are shown only after the
   run finished, and only as stored results.

**Checks:**
```powershell
Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests -q; Pop-Location
Push-Location frontend; npm run build; npm run lint; Pop-Location
```
Then start the backend and frontend locally (README "Run it locally"). Confirm three things: `/samples`
lists the Stage 11 claims with the new label, a case page opens, and ports 8000 and 3000 are free
afterwards.

**Done when:** tests and build pass, the intake loader shows Stage 11 samples with their source label,
and a case page renders the debate, both Judge orderings and the cap card.

---

## Step 6 — Commit and push the documents and the loader change

**Depends on:** steps 4 and 5.

```powershell
git add -A -- README.md docs backend/app backend/tests frontend/app frontend/components frontend/lib scripts backend/data/stage11_final_analytics.json
git status --short
if (git diff --cached | Select-String -Pattern "gsk_[A-Za-z0-9]{10,}", "GROQ_API_KEY\s*=\s*\S" -Quiet) { "KEY SCAN FAILED"; git reset -q } else {
  git commit -m "Stage 11 results in documents; sample loader shows the Stage 11 run" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
  git push origin master
}
```

Read `git status --short` before the commit: nothing unexpected should be staged. Then wait for Vercel
and Render to finish redeploying (check each dashboard).

**Done when:** `git status --short` is empty, `git rev-parse HEAD` equals `git rev-parse origin/master`,
and both deployments show the new commit as live.

---

## Step 7 — Preflight until it exits 0

**Depends on:** step 6 deployed.

```powershell
backend\.venv\Scripts\python.exe scripts\preflight.py --frontend-url https://ai-builders-hackathon.vercel.app --backend-url https://claimlens-api.onrender.com
"exit code: $LASTEXITCODE"
```

The first live request can take about a minute while the free Render instance wakes up. Fix whatever
fails, commit and push, redeploy if needed, and run it again.

| Failing check | Usual fix |
|---|---|
| documents | A marker was missed or a document is missing: go back to step 2 or 4. |
| git | Something was left uncommitted or unpushed: commit and push it (key scan first). |
| secrets | Stop. Remove the secret from the file and from history before anything is public. |
| snapshot | Step 4 didn't run, or ran with the wrong data: re-run step 4. |
| tests / build | Fix the code, commit, push. |
| frontend `/api/health` | Vercel's `BACKEND_URL` is wrong or missing: fix it in Vercel settings and redeploy (see `docs/DEPLOYMENT.md`). |
| endpoints | Render hasn't finished deploying, or is missing the results files: check the Render dashboard and logs. |

**Done when:** it prints `READY: all 9 checks passed.` with exit code 0.

---

## Step 8 — Submit

**Depends on:** step 7 exiting 0.

Go through PART 9 of `PROJECT_PLAN.md` one line at a time:
- Devpost form;
- the live URL tested fresh;
- the public repo with the full README;
- the video under 5 minutes;
- the deck at 10 slides or fewer.

Submit with time to spare before 03:00 UTC.
