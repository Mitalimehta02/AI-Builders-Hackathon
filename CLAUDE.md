# CLAUDE.md — Operating Instructions for This Project

You are helping build **ClaimLens**, a hackathon project for the AI Builders Hackathon
(deadline Sep 16, 2026, 8:30am GMT+5:30). The full specification, research, rubric mapping,
metrics, architecture, and stage-by-stage build plan live in **PROJECT_PLAN.md** in this
same folder. Read that file in full before writing any code, and re-read the relevant
stage section before starting each stage.

**Model provider: Groq (free tier), model `openai/gpt-oss-120b`.** See Part 6 and Part 6b of
PROJECT_PLAN.md for the exact model IDs, the honesty rule about baseline-vs-pipeline
comparisons, and the free-tier quota rules. Quota is a real constraint on this project —
treat every model call as costing something.

## Non-negotiable rules

1. **Work one stage at a time.** PROJECT_PLAN.md defines Stages 1 through 17. Only do the
   stage you are explicitly asked to do. Do not jump ahead, do not "helpfully" pre-build
   later stages, even if it seems efficient.
2. **Stop and report after every stage.** When a stage is done, tell the user in plain
   language: what files you created or changed, what each does, the actual output you got
   when you ran it, and whether that stage's Acceptance Criteria are met. Then stop and wait
   — do not start the next stage until the user explicitly says to continue.
3. **Never mark a stage done if it doesn't actually run.** If a test fails, a server won't
   start, or an API call errors out, say so plainly and fix it before declaring the stage
   complete. Don't paper over errors.
4. **Keep the code readable over clever.** This is a 3-day hackathon build reviewed by a
   non-expert user and, later, by hackathon judges reading the GitHub repo. Prefer simple,
   well-commented code over abstractions. Every file should be understandable by someone
   reading it cold.
5. **Do not add authentication, payments, or any feature not in PROJECT_PLAN.md** unless the
   user asks. Scope creep is the #1 risk on a 3-day deadline.
6. **All secrets (API keys) go in a `.env` file that is gitignored** — never hardcode a key
   in source, never print a real key back to the user in chat.
7. **Every stage should end with something that visibly runs** — a script that prints
   output, a server that starts, a page that loads. If a stage can't produce something
   runnable, flag that to the user before proceeding.
8. **When in doubt about scope or a design choice, ask the user rather than guessing** —
   better to lose two minutes asking than to build the wrong thing for an hour.

## Terminal rules — you run the commands, not the user

9. **Run every command yourself.** Installs, scripts, tests, migrations, HTTP checks, git —
   you execute them in the terminal and report the real output. Do not hand the user a list
   of commands to run and then wait; the only correct time to ask the user to type something
   is when it genuinely requires them (see rule 11). If a command fails, read the error, fix
   it, and run it again — don't hand the failure back to the user as homework.
10. **Servers must never block your terminal or be left running.** To test a dev server:
    start it in the background, wait for it to be ready, make the request that proves it
    works, capture the output, then stop it and confirm the port is free. This machine is
    **Windows / PowerShell**, so: use the venv interpreter directly
    (`.\.venv\Scripts\python.exe`), use `Start-Process -NoNewWindow` or `Start-Job` for
    background servers, and use `curl.exe` or `Invoke-WebRequest` for HTTP checks (bare
    `curl` in PowerShell is an alias for `Invoke-WebRequest` and takes different flags —
    a common source of confusing errors). Always leave ports 8000 and 3000 free when you
    finish a stage.
11. **Only these things go to the user:** pasting their real Groq API key into
    `backend/.env`; signing in to Vercel/Render in a browser during Stage 13; and actually
    *looking* at a page in a browser to judge whether it reads well. Everything else is
    yours.
12. **Git is yours too.** If the repo isn't initialised, run `git init` yourself. Commit at
    the end of every stage with a clear message (e.g. `Stage 3: evidence-gathering agent`),
    after confirming the stage actually runs. Never commit `.env` or `.venv`.

## Where things are

- Full plan, rubric, research citations, metrics, architecture: `PROJECT_PLAN.md`
- Backend code: `/backend`
- Frontend code: `/frontend`
- Synthetic data + results: `/backend/data`

Read `PROJECT_PLAN.md` now if you haven't already.
