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
   - `SCRAPER_API_KEY` → any strong random string.
   - `CORS_ORIGINS` → leave as a placeholder for now; you'll set it to the
     Vercel URL in step 4 (e.g. `https://joblens.vercel.app`).
   - `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` → from step 0.
4. **Deploy.** First boot runs migrations + seeds jobs (`start_prod.sh`), then
   serves. Watch the logs; when healthy, hit `https://<service>.onrender.com/api/health`.
5. Copy the backend URL (e.g. `https://joblens-api.onrender.com`).

> Free-tier notes: the instance sleeps after ~15 min idle (first request after
> that takes ~30 s to wake — normal). It runs `EMBEDDING_PROVIDER=deterministic`
> and eager Celery to fit in 512 MB, both preset in `render.yaml`.

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

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| Frontend loads but no jobs / CORS error in console | `CORS_ORIGINS` on Render must exactly match the Vercel origin |
| Backend 500 on boot | check `DATABASE_URL` is the full Neon string; check logs for migration errors |
| "App refuses to boot in production" | `SCRAPER_API_KEY` is still the default — set a real one |
| First request very slow | free instance waking from sleep — expected |
