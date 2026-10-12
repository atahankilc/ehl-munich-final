# Deploying SharkSight: Render + Neon (D-063)

The app runs as one free **Render** web service built from the repo's `Dockerfile` (`render.yaml`); the database is a
free **Neon** Postgres (pgvector) in Frankfurt. **Anyone can look; changes need one shared access key**
(`api/access.py`, D-064): decisions, weights, settings, the OpenAI key and AI runs are refused (403) without it. The key
is entered under **Access** (bottom-left dock, next to Guide) and kept in that browser. No user accounts.

```
render.yaml                  the Render service (Docker, free plan, Frankfurt, env vars)
deploy/render/load-data.sh   copy the local database into Neon (once) and print the app's DATABASE_URL
assets/models/               the compressed CC BY car models, baked into the image
```

## Cost and limits (free plans)

- **Render free:** 512 MB RAM (the app uses ~100 MB). Sleeps after 15 min without traffic; the first request then
  takes about a minute. No disk: settings changed in the app (spend limits, agent settings) reset on restart; the
  OpenAI key comes from `OPENAI_API_KEY`.
- **Neon free:** 0.5 GB storage; the database is ~440 MB after a fresh restore — enough for the app's few writes
  (decisions, audit events, AI usage), not for re-running whole pipeline stages in the cloud (run those locally).

## Setup (once)

1. **Neon:** create a project in **AWS Europe Central 1 (Frankfurt)**, Postgres 17; database `neondb` is fine. Copy
   the **owner** connection string (Dashboard → Connect, *not* the pooled one).
2. **Load the data** from this Mac (local database running, `make db`):
   ```bash
   deploy/render/load-data.sh 'postgresql://neondb_owner:…@ep-….eu-central-1.aws.neon.tech/neondb?sslmode=require'
   ```
   It restores a fresh backup, creates the app role and prints the `DATABASE_URL` for Render.
3. **Render:** New → Blueprint → this repo. Fill in the four secrets it asks for:
   `ACCESS_KEY` (the key for changes), `DATABASE_URL` (from step 2), `MIGRATION_DATABASE_URL` (the owner string) and
   `OPENAI_API_KEY`. Render builds and starts it at `https://sharksight-….onrender.com`.

After a code change: push to `main` (auto-deploy). After new local data: `load-data.sh '<owner url>' --replace`, then
restart the service.

## Notes

- Reads (GET) and the weights preview are open to anyone with the link, including the BMW data (Atahan's call,
  D-064); every other request needs the key in `X-Access-Key`.
- The app connects as `sharksight_app` (no UPDATE / DELETE on the append-only tables); the owner string is only used
  for migrations on start.
- An OpenAI key entered in the app is stored on the server and used for everyone until a restart.
- Before more people use it: real logins (the key is shared, `X-Actor` is self-declared) and app settings in the
  database instead of `data/settings.json`.
