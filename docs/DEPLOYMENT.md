# Deploying ClaimLens

- **Backend (FastAPI) → Render**, using the `render.yaml` Blueprint in the repository root.
- **Frontend (Next.js) → Vercel**, importing the `frontend/` folder.

The browser only ever talks to the Vercel site. The Next.js server forwards `/api/*` requests to the
Render backend (see `frontend/next.config.ts`), so the frontend needs just one setting: `BACKEND_URL`.

## Why Render for the backend

- It has a free web-service plan that needs no credit card, and it runs Python natively.
- The `render.yaml` Blueprint already contains the build command, start command, health check and
  environment variables, so setup is a few clicks.
- Trade-off: a free Render service **sleeps after about 15 minutes without traffic**, and the first
  request after that takes up to about a minute. The site shows "Can't reach the ClaimLens backend"
  with a **Try again** button while it wakes. Open the site a minute before a demo.
- The free plan's disk is not persistent. That is fine here: stored samples and evaluation results
  are files in the repository, and live submission is switched off on the public site.

## What the public deployment shows

- Dashboard and case views for the stored development-set samples.
- Analytics from `backend/data/results_naive.json` and `results_claimlens.json`. **These files must be
  committed and pushed** (at Stage 11) before the deployed analytics page has results; until then it
  shows 0 of 15.
- Live submission is **off** (`CLAIMLENS_LIVE_SUBMISSION=off`), so visitors cannot spend the daily
  model allowance. The intake page explains this.

## Settings

| Where | Variable | Value |
|---|---|---|
| Render | `GROQ_API_KEY` | your Groq key (entered in the Render dashboard only, never in the repository or in chat) |
| Render | `CLAIMLENS_CORS_ORIGINS` | your Vercel URL, e.g. `https://claimlens.vercel.app` |
| Render | `CLAIMLENS_LIVE_SUBMISSION` | `off` (already set by the Blueprint) |
| Render | `PYTHON_VERSION` | `3.13.5` (already set by the Blueprint) |
| Vercel | `BACKEND_URL` | your Render URL, e.g. `https://claimlens-api.onrender.com` — no trailing slash |

---

## Step 1 — Put the code on GitHub

1. Go to <https://github.com> and sign in.
2. Click **+** (top right) → **New repository**.
3. Repository name: `claimlens`. Visibility: **Public** (the hackathon requires a public repository).
4. Leave **Add a README**, **.gitignore** and **license** all unticked. Click **Create repository**.
5. In a terminal in the project folder, run (replace `YOUR-USERNAME`):

   ```powershell
   git remote add origin https://github.com/YOUR-USERNAME/claimlens.git
   git push -u origin master
   ```

   The first push opens a browser window asking you to sign in to GitHub. Approve it.
6. Refresh the GitHub page: the files should be there, including `render.yaml`. Check that there is
   **no `.env` file** in the list.

## Step 2 — Deploy the backend on Render

1. Go to <https://render.com> → **Get Started** → **GitHub**, and authorise Render.
2. In the Render dashboard click **New +** → **Blueprint**.
3. Under **Connect a repository**, find `claimlens`. If it isn't listed, click **Configure account**
   (or **Configure GitHub App**), give Render access to the `claimlens` repository, then return.
   Click **Connect**.
4. Render reads `render.yaml` and shows one service, **claimlens-api**. Blueprint name: `claimlens`.
5. It asks for the values marked `sync: false`:
   - **GROQ_API_KEY**: paste your Groq key here.
   - **CLAIMLENS_CORS_ORIGINS**: enter `http://localhost:3000` for now (you'll change it in Step 4).
6. Click **Apply**. The first build takes about 3–5 minutes (**Logs** shows progress).
7. When the service shows **Live**, copy its URL from the top of the service page, e.g.
   `https://claimlens-api.onrender.com`.
8. Check in your browser:
   - `https://YOUR-RENDER-URL/health` → `{"status":"ok"}`
   - `https://YOUR-RENDER-URL/config` → `"live_submission_enabled": false`
   - `https://YOUR-RENDER-URL/samples` → a list of 6 stored samples

## Step 3 — Deploy the frontend on Vercel

1. Go to <https://vercel.com> → **Sign Up** → **Continue with GitHub**, and authorise Vercel.
2. Click **Add New…** → **Project**.
3. Find `claimlens` under **Import Git Repository** and click **Import**. (If it isn't listed, click
   **Adjust GitHub App Permissions** and allow the repository.)
4. On **Configure Project**:
   - **Root Directory**: click **Edit**, select `frontend`, click **Continue**.
   - **Framework Preset**: should show **Next.js** automatically.
   - Open **Environment Variables** and add: Key `BACKEND_URL`, Value your Render URL from Step 2
     (for example `https://claimlens-api.onrender.com`, no trailing slash).
5. Click **Deploy**. The build takes about 1–2 minutes.
6. Click **Continue to Dashboard**, then **Visit** (or copy the domain shown, e.g.
   `https://claimlens-xyz.vercel.app`).

## Step 4 — Tell the backend the frontend's address

1. In Render, open **claimlens-api** → **Environment**.
2. Edit **CLAIMLENS_CORS_ORIGINS** and set it to your Vercel URL (e.g. `https://claimlens-xyz.vercel.app`).
3. Click **Save Changes**. Render redeploys automatically (about 1–2 minutes).

## Step 5 — Check the live site

Open your Vercel URL and check:

- [ ] **Dashboard** lists 6 stored samples. (If you see "Can't reach the ClaimLens backend", wait a
      minute for Render to wake up and click **Try again**.)
- [ ] Click **CLM-0027** → the case view shows the red **"Confidence cap applied: HIGH → MEDIUM"** card.
- [ ] **Analytics** shows the "N of 15 complete" banner and the pre-registration statement.
- [ ] **Intake** says live submission is switched off on this deployment; loading a sample still works.
- [ ] On your phone, the same pages are readable without sideways scrolling.

## Updating after a change

Push to GitHub (`git push`). Render and Vercel both redeploy automatically. If you change
`BACKEND_URL` in Vercel, trigger a redeploy: **Deployments** → **⋯** on the latest deployment → **Redeploy**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Can't reach the ClaimLens backend" | Render is waking up: wait a minute and click **Try again**. If it persists, open the Render URL's `/health` directly and check Render's **Logs**. |
| Vercel page loads but every request fails | `BACKEND_URL` is missing, has a typo or a trailing slash. Fix it in Vercel → **Settings** → **Environment Variables**, then **Redeploy**. |
| Render build fails on the Python version | In Render → **Environment**, change `PYTHON_VERSION` to a version Render lists as supported (for example `3.12.8`) and redeploy. |
| Analytics shows 0 of 15 | The Stage 11 result files aren't committed and pushed yet. |
