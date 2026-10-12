# Deploying SharkSight to Google Cloud (D-062)

One Compute Engine VM runs the same containers as your laptop: **db** (PostgreSQL 17 + pgvector), **app** (API + the
built PM app) and a small **proxy** (Caddy: HTTPS + one password, because the app has no login of its own yet).

```
deploy/compose.yaml   the stack on the VM (provider-neutral)
deploy/Caddyfile      HTTPS for <ip>.sslip.io + basic auth in front of the app
deploy/gcp/deploy.sh  the CLI: create the VM, ship the image and files, start, copy data, tunnel, destroy
```

## Cost

Made for the **Google Cloud free tier**: one e2-micro VM (2 shared vCPUs, 1 GB RAM) and 30 GB of standard disk are
free every month in `us-west1`, `us-central1` or `us-east1`, plus 1 GB of outbound traffic. A public IPv4 address may
be billed (a few dollars a month). New accounts also get a **$300 / 90-day trial credit**; as long as you don't
upgrade to a paid account, nothing is charged when it runs out. `deploy.sh budget` adds a $5 monthly alert.

1 GB is tight for Postgres + the app: the VM gets 2 GB of swap and Postgres is tuned small. If it is too slow,
`MACHINE_TYPE=e2-small` (2 GB, ≈ $12 / month, from the trial credit) — `destroy`, then `create` with it.

## One-time setup (you)

1. Create a Google Cloud account at https://console.cloud.google.com (card needed for verification; trial credit).
2. Create a project (e.g. `sharksight`) and make sure billing is linked to it.
3. On this Mac: `brew install --cask google-cloud-sdk`, then `gcloud auth login` and
   `gcloud config set project <project-id>`.
4. `deploy/gcp/deploy.sh check` (also switches on the Compute Engine API)

## Deploy

```bash
deploy/gcp/deploy.sh create          # SSH key, network + firewall, e2-micro (Ubuntu 24.04); wait ~2 min for Docker
deploy/gcp/deploy.sh deploy          # build the x86 image, send it + compose + .env + settings + 3D models, start
deploy/gcp/deploy.sh data            # copy your local database into the VM (once; --replace to overwrite)
deploy/gcp/deploy.sh url             # https://<ip>.sslip.io — user pm, password in deploy/gcp/.env.vm
deploy/gcp/deploy.sh budget
```

After a code change: `deploy/gcp/deploy.sh deploy` again (data stays; the app migrates the schema on start).

## Day to day

| Command | What it does |
|---|---|
| `status`, `logs`, `ssh` | container state, last 200 log lines, a shell on the VM |
| `tunnel` | app on http://127.0.0.1:8601 and the VM's Postgres on 127.0.0.1:5434 — e.g. run a pipeline stage from this Mac against the cloud database with `DATABASE_URL=postgresql://sharksight_app:…@127.0.0.1:5434/sharksight` |
| `up --private` | db + app only, no public proxy; use `tunnel` to reach it |
| `allow-my-ip` | your IP changed and SSH is refused |
| `stop` / `start` | pause the VM (disk and data stay; the public IP changes → `push` then `up`) |
| `destroy` | delete the VM and its disk (all cloud data), firewall rules, network and SSH key |

Settings: `GCP_PROJECT` (default: gcloud's current project), `GCP_ZONE` (`us-central1-a`), `MACHINE_TYPE` (`e2-micro`).

## What is where

- Secrets: `deploy/gcp/.env.vm` (generated from your `.env`: OpenAI key, database passwords, the web login) and the SSH
  key `deploy/gcp/sharksight.key` — both git-ignored, 0600. On the VM they are `~sharksight/sharksight/.env`.
- Ports: the VM has its own network `sharksight` (not the default one, which allows SSH from anywhere): only 80/443
  (proxy) are open to the world, SSH only from your IP; the app (8600) and Postgres (5432) listen on the VM's localhost.
- The image is built for linux/amd64; on an ARM Mac the Python part is emulated (the frontend builds natively).

## Before anyone else uses it

The proxy password is shared, so the audit trail still records whatever name the browser sends (`X-Actor`). Real
logins for people, app settings in the database instead of `data/settings.json`, and the 3D models in object storage
are the next steps for a proper deployment (STATE → Next up).
