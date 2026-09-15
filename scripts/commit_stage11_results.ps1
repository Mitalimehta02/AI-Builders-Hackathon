# Stage 11 results commit. Run ONLY after "BATCH COMPLETE" appears in the batch log:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<this file>"
# Stages exactly the files held back during the run, checks them, commits, pushes, and verifies the push.
# It refuses to do anything if the batch has not finished or if anything unexpected would be committed.

$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\HP\Desktop\AI Builders Hackathon'

function Fail($message) { Write-Host "STOPPED: $message" -ForegroundColor Red; exit 1 }

# 1. The batch must be finished.
if (-not (Select-String -Path 'backend/data/stage11_batch_output.log' -Pattern 'BATCH COMPLETE' -Quiet)) {
    Fail 'BATCH COMPLETE is not in backend/data/stage11_batch_output.log yet.'
}
$status = Get-Content 'backend/data/stage11_batch_status.json' -Raw | ConvertFrom-Json
if ($status.running) { Fail 'backend/data/stage11_batch_status.json still says the batch is running.' }
if (git diff --cached --name-only) { Fail 'something is already staged; unstage it so this commit holds only the results.' }

# 2. The held-back files. Any further model-call log (e.g. a new UTC day) is included and listed.
$files = @(
    'backend/data/results_naive.json',
    'backend/data/results_claimlens.json',
    'backend/data/stage11_batch_output.log',
    'backend/data/llm_logs/2026-09-14.jsonl',
    'backend/data/llm_logs/2026-09-15.jsonl',
    'backend/data/weather_cache.json'
)
foreach ($file in $files) { if (-not (Test-Path $file)) { Fail "missing $file" } }
$extraLogs = @(git status --porcelain -- backend/data/llm_logs | ForEach-Object { $_.Substring(3).Trim('"') } |
    Where-Object { $_ -notin $files })
if ($extraLogs) { Write-Host "Also including model-call logs: $($extraLogs -join ', ')"; $files += $extraLogs }

git add -- $files
if ($LASTEXITCODE -ne 0) { Fail 'git add failed.' }

# 3. Exactly these files, no secrets.
$staged = @(git diff --cached --name-only)
$unexpected = @($staged | Where-Object { $_ -notin $files })
if ($unexpected) { git reset -q; Fail "unexpected staged files: $($unexpected -join ', ')" }
if (git diff --cached | Select-String -Pattern 'gsk_[A-Za-z0-9]{10,}', 'GROQ_API_KEY\s*=\s*\S' -Quiet) {
    git reset -q; Fail 'a key-shaped string is in the staged files; nothing was committed.'
}
Write-Host "Staged ($($staged.Count)):"; $staged | ForEach-Object { Write-Host "  $_" }

# 4. Commit, push, verify.
git commit -q -m @'
Stage 11 results: pre-registered held-out evaluation, naive baseline vs ClaimLens

Raw results for both systems on the 15-claim sample registered 2026-09-14 (seed 20260914,
claim_ids_sha256 bbcdf0fd5693fd7a1be43ee4516dd7c99ef71fbb238e696c6c190dc108d5b49a), processed in
ascending claim-ID order with the final configuration fixed before any held-out run
(openai/gpt-oss-120b, temperature 0.2, reasoning effort medium, no rebuttal round).

- backend/data/results_naive.json, results_claimlens.json: every baseline result and every
  ClaimLens step (evidence, Prosecutor, Defender, both Judge orderings, tier, cap, gate)
- backend/data/stage11_batch_output.log: the run's log, including rate-limit waits, the CLM-0026
  failure and retry, the operator restart for the runner ordering fix, and the overnight stall
  while the laptop slept
- backend/data/llm_logs/: every model request and response made during the run
- backend/data/weather_cache.json: Open-Meteo lookups made during the run

The reported figures are computed from these files by GET /analytics
(backend/app/routes/analytics.py). Protocol, stopping rule and disclosures: docs/METHODOLOGY.md.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
'@
if ($LASTEXITCODE -ne 0) { Fail 'git commit failed.' }
$env:GIT_TERMINAL_PROMPT = '0'
git push origin master
if ($LASTEXITCODE -ne 0) { Fail 'commit made locally, but the push failed; run: git push origin master' }
git fetch -q origin
$head, $remote = (git rev-parse HEAD), (git rev-parse origin/master)
Write-Host "HEAD $head; origin/master $remote; in sync: $($head -eq $remote)"
git status --short
