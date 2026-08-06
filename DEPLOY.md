# Deploying JobLens (free tier)

Three free services: **Neon** (database), **Render** (backend), **Vercel**
(frontend). End-to-end ~20 minutes. Do them in this order.

---

## 0. Adzuna keys (2 min — do first)

1. Sign up at <https://developer.adzuna.com/> → register an app.
2. Copy your **App ID** and **App Key**. You'll paste them into Render in step 2.
   (Without them the live site still works — it just shows fewer jobs.)

---

## 1. Database — Neon

1. Create a free project at <https://neon.tech>.
2. After it provisions, open **Connection Details** and copy the connection
   string (looks like `postgresql://user:pass@ep-xxx.aws.neon.tech/neondb`).
3. pgvector is supported out of the box — the app's first migration runs
   `CREATE EXTENSION IF NOT EXISTS vector` automatically. Nothing else to do.

Keep that connection string for step 2.

---

## 2. Backend — Render

1. Push this repo to GitHub (already done).
2. At <https://render.com> → **New → Blueprint**, point it at your repo. Render
   reads `render.yaml` and creates the `joblens-api` web service.
3. In the service's **Environment**, set the secret vars (`sync: false` ones):
   - `DATABASE_URL` → the Neon string from step 1 (paste as-is; the app
     normalises `postgresql://` → the psycopg2 driver automatically).
   - `GOOGLE_API_KEY` → a Gemini API key (used for embeddings + résumé parsing).
   - `SCRAPER_API_KEY` → any strong random string.
   - `CORS_ORIGINS` → leave as a placeholder for now; you'll set it to the
     Vercel URL in step 4 (e.g. `https://joblens.vercel.app`).
   - `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` → free job aggregator (from step 0).
   - **Apify (optional — paid LinkedIn/Indeed, weekly):** `APIFY_TOKEN`,
     `APIFY_LINKEDIN_INPUT`, `APIFY_INDEED_INPUT` (copy from `backend/.env.example`).
     Leave `APIFY_TOKEN` blank to disable; the rest of the catalogue still works.
4. **Deploy.** First boot runs migrations + seeds jobs (`start_prod.sh`), then
   serves. Watch the logs; when healthy, hit `https://<service>.onrender.com/api/health`.
5. Copy the backend URL (e.g. `https://joblens-api.onrender.com`).

> Free-tier notes: the instance sleeps after ~15 min idle (first request after
> that takes ~30 s to wake — normal). It runs `EMBEDDING_PROVIDER=gemini` (an
> HTTP call — no torch in the 512 MB image) and eager Celery (no Redis/worker),
> both preset in `render.yaml`. After first deploy, run `POST /api/reembed` once.

---

## 3. Frontend — Vercel

1. At <https://vercel.com> → **Add New → Project**, import the same repo.
2. **Set Root Directory to `frontend`** (Settings → Root Directory). This is the
   key step for the monorepo — Vercel then auto-detects Next.js.
3. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` → your Render backend URL from step 2.
4. **Deploy.** Copy the resulting URL (e.g. `https://joblens.vercel.app`).

---

## 4. Connect them (CORS)

1. Back in **Render → Environment**, set `CORS_ORIGINS` to your exact Vercel URL
   (no trailing slash), e.g. `https://joblens.vercel.app`. Save → redeploys.
2. Open the Vercel URL — Browse should load jobs; upload a résumé and match.

---

## 5. Finishing touches

- Put the live Vercel URL in the GitHub repo's **About → Website** field and at
  the top of `README.md`.
- After the first successful seed you can set `SEED_ON_START=false` in Render so
  redeploys are faster (jobs persist in Neon).
- To re-seed manually later: Render **Shell** → `python -m app.scripts.seed_prod`.

## 6. Keeping the free instance warm (optional)

Render free web services sleep after **15 min** idle. Cold starts are already
handled in-app by `BackendWakingScreen`, so this step is purely a nicety.

**Do not use GitHub Actions for this.** `schedule:` is best-effort and gets
dropped under load — a `*/10` cron on this repo was delivered ~7–8 times/day
(median gap **104 min**), far outside the 15 min window, and the flood of
dispatch requests appeared to delay `maintenance.yml` by 1.5–4 h as well.

Use a dedicated pinger that honours short intervals instead:

1. Sign up at [cron-job.org](https://cron-job.org) (free, 1-min resolution) or
   [UptimeRobot](https://uptimerobot.com) (free, 5-min).
2. New job → URL `https://<your-api>.onrender.com/api/health`, method `GET`.
3. Interval **every 10 min**, restricted to your active hours
   (e.g. 02:30–18:30 UTC ≈ 08:00–24:00 IST).

Keep the window — don't ping 24/7. Render allows 750 free instance-hours/month;
round-the-clock is ~720 h and leaves no headroom for a second service or for
the maintenance runs below. A ~16 h/day window is ~490 h.

## 7. Scraping sources & cost

The catalogue is built from providers on two cadences (GitHub Actions cron):

- **Free (daily, 02:30 UTC):** ATS boards (Greenhouse/Lever/Amazon) + **Adzuna**
  aggregator + curated postings. No per-call cost.
- **Paid (weekly, Mon 03:00 UTC):** **Apify** LinkedIn + Indeed actors
  (pay-per-result). Throttled in-app to once every 7 days via a `scrape_runs`
  ledger; `APIFY_MAX_ITEMS` caps results billed per run. Est. ~$1–2/month, within
  Apify's $5 free monthly credit.

Trigger manually (header `X-API-Key: <SCRAPER_API_KEY>`):
- Free: `POST /api/ingest -d '{"background":true,"tier":"free"}'`
- Paid: `POST /api/ingest -d '{"background":true,"tier":"paid"}'`
  (add `"force":true` to bypass the weekly guard).

> ⏰ Treat those cron times as *earliest*, not exact. GitHub's scheduler has been
> firing them 1.5–4 h late; the jobs are order-independent and self-wake the
> instance, so lateness is cosmetic — but the daily alert email lands mid-
> afternoon IST rather than at 13:30.
>
> Scheduled workflows in a **public** repo are auto-disabled after **60 days with
> no commits**. Push anything (or re-enable them in the Actions tab) to reset it.

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| Frontend loads but no jobs / CORS error in console | `CORS_ORIGINS` on Render must exactly match the Vercel origin |
| Backend 500 on boot | check `DATABASE_URL` is the full Neon string; check logs for migration errors |
| "App refuses to boot in production" | `SCRAPER_API_KEY` is still the default — set a real one |
| First request very slow | free instance waking from sleep — expected |
