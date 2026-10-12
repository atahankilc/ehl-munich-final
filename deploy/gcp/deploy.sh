#!/usr/bin/env bash
# SharkSight on one Google Compute Engine VM (D-062): Postgres + app + an HTTPS/password proxy via Docker Compose
# (deploy/compose.yaml, deploy/Caddyfile). Made for the Google Cloud free tier: one e2-micro (x86, 1 GB + 2 GB swap)
# with a 30 GB standard disk in us-central1 (free-tier regions: us-west1, us-central1, us-east1).
#
#   deploy/gcp/deploy.sh <command> [options]
#
#   check        prerequisites: gcloud logged in with a project, Compute Engine API on, Docker
#   create       SSH key, its own VPC network + firewall (SSH from your IP only, 80/443 open), the VM (Ubuntu 24.04,
#                Docker and 2 GB swap installed on first boot)
#   build        the app image for linux/amd64 (the Python part is emulated on an ARM Mac: a few minutes)
#   push         image (docker save | ssh docker load — no registry) + compose, Caddyfile, .env, data/settings.json,
#                data/models to the VM
#   up           start db + app (+ the HTTPS proxy unless --private); the app runs the schema migrations on start
#   data         copy the local database into the VM's (pg_dump → pg_restore, data only; refuses a non-empty
#                target, `data --replace` wipes it first)
#   deploy       build + push + up
#   url          address and login (kept in deploy/gcp/.env.vm)
#   status | logs | ssh
#   tunnel       SSH tunnel: app on http://127.0.0.1:8601, the VM's Postgres on 127.0.0.1:5434
#   budget       a $5 monthly budget alert (e-mails the billing account's admins)
#   allow-my-ip  re-open SSH for your current IP (after it changed)
#   stop | start     stop / start the VM (disk and data stay; the public IP changes → run `push` again for HTTPS)
#   destroy      delete the VM (its disk and all data on it), the firewall rules, the network and the SSH key
#
# Settings (environment): GCP_PROJECT (gcloud's current project), GCP_ZONE (us-central1-a), MACHINE_TYPE (e2-micro;
# e2-small = 2 GB if 1 GB is too tight, not free), NAME (sharksight).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/deploy/gcp"
STACK="$ROOT/deploy"
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${GCP_ZONE:-us-central1-a}"
TYPE="${MACHINE_TYPE:-e2-micro}"
NAME="${NAME:-sharksight}"
IMAGE="sharksight:prod-amd64"
KEY="$HERE/$NAME.key"                         # git-ignored (*.key), 0600
ENV_VM="$HERE/.env.vm"                        # secrets for the VM; git-ignored (.env.*), 0600
SSH_USER="sharksight"
REMOTE_DIR="sharksight"
PRIVATE=0
REPLACE=0

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found — $2"; }
gc()   { gcloud --project "$PROJECT" --quiet "$@"; }

vm_exists() { [[ -n "$(gc compute instances list --filter="name=$NAME" --format='value(name)' 2>/dev/null)" ]]; }

public_ip() {
  vm_exists || die "no VM named $NAME in $PROJECT — run: deploy/gcp/deploy.sh create"
  gc compute instances describe "$NAME" --zone "$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
}

my_ip() { curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]'; }

ssh_opts() { echo "-i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$HERE/.known_hosts -o ServerAliveInterval=30"; }

# Run a shell command in the deployment directory on the VM.
remote() {
  # shellcheck disable=SC2046
  ssh $(ssh_opts) "$SSH_USER@$(public_ip)" \
    "mkdir -p ~/$REMOTE_DIR && cd ~/$REMOTE_DIR && COMPOSE_PROJECT_NAME=sharksight DOCKER='sudo docker' bash -c $(printf '%q' "$1")"
}

# Copy local files into the deployment directory (keeps the last path component).
remote_copy() {
  # shellcheck disable=SC2046
  scp $(ssh_opts) -r -C "$@" "$SSH_USER@$(public_ip):$REMOTE_DIR/"
}

# Stream stdin into a command on the VM.
remote_pipe() {
  # shellcheck disable=SC2046
  ssh $(ssh_opts) "$SSH_USER@$(public_ip)" "$1"
}

env_get() { grep -E "^$1=" "$2" 2>/dev/null | tail -1 | cut -d= -f2- || true; }

# ------------------------------------------------------------------------------------------------ commands
cmd_check() {
  need docker "install Docker Desktop or OrbStack"
  need gcloud "brew install --cask google-cloud-sdk, then: gcloud auth login && gcloud config set project <id>"
  [[ -f "$ROOT/.env" ]] || die "no .env at the repo root (see .env.example)"
  [[ -n "$PROJECT" ]] || die "no project: gcloud config set project <id> (or GCP_PROJECT=<id>)"
  local who; who="$(gcloud config get-value account 2>/dev/null)"; [[ -n "$who" ]] || die "not logged in: gcloud auth login"
  gc services list --enabled --filter=name:compute.googleapis.com --format='value(name)' | grep -q compute \
    || { say "enabling the Compute Engine API (needs billing on the project)…"; gc services enable compute.googleapis.com; }
  say "account $who, project $PROJECT, zone $ZONE, machine type $TYPE"
  say "ok"
}

cmd_create() {
  vm_exists && die "a VM named $NAME already exists in $PROJECT"
  if [[ ! -f "$KEY" ]]; then
    say "SSH key $KEY…"
    ssh-keygen -q -t ed25519 -N '' -C "$SSH_USER" -f "$KEY"
  fi
  # Its own network: the default network has an "SSH from anywhere" rule, this one only opens what we add.
  if ! gc compute networks describe "$NAME" >/dev/null 2>&1; then
    say "network $NAME + firewall (SSH from your IP, 80/443 open)…"
    gc compute networks create "$NAME" --subnet-mode=auto >/dev/null
    gc compute firewall-rules create "$NAME-web" --network "$NAME" --allow tcp:80,tcp:443 \
      --source-ranges 0.0.0.0/0 --target-tags "$NAME" >/dev/null
  fi
  cmd_allow_my_ip
  local startup keys
  startup="$(mktemp)"; keys="$(mktemp)"
  cat > "$startup" <<'EOS'
#!/bin/bash
set -e
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
EOS
  echo "$SSH_USER:$(cat "$KEY.pub")" > "$keys"
  say "VM $TYPE in $ZONE (Ubuntu 24.04, 30 GB standard disk)…"
  gc compute instances create "$NAME" --zone "$ZONE" --machine-type "$TYPE" \
    --network "$NAME" --tags "$NAME" --labels project=sharksight \
    --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
    --boot-disk-size 30GB --boot-disk-type pd-standard \
    --metadata enable-oslogin=FALSE --metadata-from-file "startup-script=$startup,ssh-keys=$keys" >/dev/null
  rm -f "$startup" "$keys"
  say "running at $(public_ip). Docker installs on first boot (~2 min); then: deploy/gcp/deploy.sh deploy"
}

cmd_allow_my_ip() {
  local ip; ip="$(my_ip)"
  if gc compute firewall-rules describe "$NAME-ssh" >/dev/null 2>&1; then
    gc compute firewall-rules update "$NAME-ssh" --source-ranges "$ip/32" >/dev/null
  else
    gc compute firewall-rules create "$NAME-ssh" --network "$NAME" --allow tcp:22 \
      --source-ranges "$ip/32" --target-tags "$NAME" >/dev/null
  fi
  say "SSH open for $ip"
}

cmd_build() {
  say "building $IMAGE (linux/amd64)…"
  docker buildx build --platform linux/amd64 --target prod -t "$IMAGE" --load "$ROOT"
}

write_env() {
  # Secrets for the VM, from the local .env; the web login is generated once and kept in .env.vm.
  local ip site user pw hash
  ip="$(public_ip)"
  site="${ip//./-}.sslip.io"   # HTTPS via sslip.io
  user="$(env_get BASIC_AUTH_USER "$ENV_VM")"; user="${user:-pm}"
  pw="$(env_get WEB_PASSWORD "$ENV_VM")"
  [[ -n "$pw" ]] || pw="$(openssl rand -hex 16)"   # no pipe: under pipefail a SIGPIPE'd generator would end the script
  hash="$(docker run --rm caddy:2.10-alpine caddy hash-password --plaintext "$pw")"
  ( umask 077
    { echo "# generated by deploy/gcp/deploy.sh — secrets for the VM, never commit"
      for k in OPENAI_API_KEY OPENAI_MODEL_FAST OPENAI_MODEL_SMART OPENAI_MODEL_EMBED POSTGRES_PASSWORD APP_DB_PASSWORD; do
        echo "$k=$(env_get "$k" "$ROOT/.env")"
      done
      echo "APP_IMAGE=$IMAGE"
      echo "SITE_ADDRESS=$site"
      echo "BASIC_AUTH_USER=$user"
      echo "BASIC_AUTH_HASH='$hash'"   # single quotes: compose must not expand the $ in the bcrypt hash
      echo "WEB_PASSWORD=$pw"          # for you; the proxy only knows the hash
    } > "$ENV_VM" )
}

cmd_push() {
  [[ -n "$(docker images -q "$IMAGE")" ]] || die "no $IMAGE image — run: deploy/gcp/deploy.sh build"
  remote 'command -v docker >/dev/null' || die "Docker is not installed on the VM yet — wait a minute after create"
  write_env
  say "sending the image…"
  docker save "$IMAGE" | gzip -1 | remote_pipe "gunzip | sudo docker load"
  local staged; staged="$(mktemp -d)"
  cp "$STACK/compose.yaml" "$STACK/Caddyfile" "$staged/"
  cp "$ENV_VM" "$staged/.env"
  mkdir -p "$staged/data" "$staged/restore"
  [[ -f "$ROOT/data/settings.json" ]] && cp "$ROOT/data/settings.json" "$staged/data/"
  [[ -d "$ROOT/data/models" ]] && cp -R "$ROOT/data/models" "$staged/data/"
  say "copying compose, Caddyfile, .env, settings and 3D models…"
  remote_copy "$staged/compose.yaml" "$staged/Caddyfile" "$staged/.env" "$staged/data" "$staged/restore"
  rm -rf "$staged"
  remote 'chmod 600 .env'
}

cmd_up() {
  local profile=""; [[ $PRIVATE == 1 ]] || profile="--profile public"
  remote "\$DOCKER compose $profile up -d && \$DOCKER compose ps --format '{{.Name}} {{.Status}}'"
  if [[ $PRIVATE == 1 ]]; then say "private: reach it with deploy/gcp/deploy.sh tunnel"; else cmd_url; fi
}

cmd_data() {
  say "dumping the local database…"
  make -C "$ROOT" backup >/dev/null
  local dump; dump="$(ls -t "$ROOT"/data/backups/sharksight-*.dump | head -1)"
  remote "\$DOCKER compose up -d --wait db app >/dev/null"   # the app creates the schema (migrations) on start
  local rows
  rows="$(remote "\$DOCKER compose exec -T db psql -U sharksight -d sharksight -tAc 'SELECT COUNT(*) FROM source_item'" | tr -d '[:space:]')"
  if [[ "$rows" != "0" ]]; then
    [[ $REPLACE == 1 ]] || die "the VM's database already holds $rows source items — use: deploy/gcp/deploy.sh data --replace"
    say "wiping the VM's database…"
    remote "\$DOCKER compose down && \$DOCKER volume rm sharksight_pgdata && \$DOCKER compose up -d --wait db app >/dev/null"
  fi
  say "copying $(basename "$dump") ($(du -h "$dump" | cut -f1))…"
  remote_copy "$dump"
  remote "mv $(basename "$dump") restore/db.dump && \$DOCKER compose stop app >/dev/null && \
    \$DOCKER compose exec -T db sh -c 'pg_restore -l /restore/db.dump | grep -v alembic_version > /tmp/list && \
      pg_restore -U sharksight -d sharksight --data-only --disable-triggers --single-transaction -L /tmp/list /restore/db.dump' && \
    rm -f restore/db.dump && \$DOCKER compose start app >/dev/null && \
    \$DOCKER compose exec -T db psql -U sharksight -d sharksight -tAc \"SELECT 'source items: ' || COUNT(*) FROM source_item\""
  say "data copied"
}

cmd_url() {
  local site user pw
  site="$(env_get SITE_ADDRESS "$ENV_VM")"; user="$(env_get BASIC_AUTH_USER "$ENV_VM")"; pw="$(env_get WEB_PASSWORD "$ENV_VM")"
  say "https://$site   login: $user / $pw   (the HTTPS certificate takes a minute on first start)"
}

cmd_tunnel() {
  say "app → http://127.0.0.1:8601   Postgres → 127.0.0.1:5434 (Ctrl-C to close)"
  # shellcheck disable=SC2046
  ssh $(ssh_opts) -N -L 8601:127.0.0.1:8600 -L 5434:127.0.0.1:5432 "$SSH_USER@$(public_ip)"
}

cmd_budget() {
  local account
  account="$(gcloud billing projects describe "$PROJECT" --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
  [[ -n "$account" ]] || die "project $PROJECT has no billing account linked"
  gc services enable billingbudgets.googleapis.com
  gcloud billing budgets create --billing-account "$account" --display-name sharksight-5usd \
    --budget-amount 5USD --filter-projects "projects/$PROJECT" \
    --threshold-rule percent=0.5 --threshold-rule percent=0.8 --threshold-rule percent=1.0 >/dev/null
  say "budget sharksight-5usd: e-mails to the billing admins at 50 / 80 / 100 % of \$5 a month"
}

cmd_destroy() {
  read -r -p "Delete $NAME in $PROJECT (its disk and ALL data on it), its firewall rules, network and SSH key? [y/N] " ok
  [[ "$ok" == y ]] || exit 1
  vm_exists && gc compute instances delete "$NAME" --zone "$ZONE"
  for r in "$NAME-web" "$NAME-ssh"; do gc compute firewall-rules delete "$r" 2>/dev/null || true; done
  gc compute networks delete "$NAME" 2>/dev/null || true
  rm -f "$KEY" "$KEY.pub" "$HERE/.known_hosts"
  say "destroyed"
}

# ------------------------------------------------------------------------------------------------ main
cmd="${1:-help}"; shift || true
for a in "$@"; do
  case "$a" in --private) PRIVATE=1 ;; --replace) REPLACE=1 ;; *) die "unknown option $a" ;; esac
done
case "$cmd" in
  check|create|build|push|up|data|url|tunnel|budget|destroy) "cmd_$cmd" ;;
  allow-my-ip) cmd_allow_my_ip ;;
  deploy) cmd_build; cmd_push; cmd_up ;;
  status) remote '$DOCKER compose ps' ;;
  logs)   remote '$DOCKER compose logs --tail 200' ;;
  ssh)    # shellcheck disable=SC2046
          ssh $(ssh_opts) "$SSH_USER@$(public_ip)" ;;
  stop)   gc compute instances stop "$NAME" --zone "$ZONE" && say "stopped (disk and data stay)" ;;
  start)  gc compute instances start "$NAME" --zone "$ZONE" \
            && say "running at $(public_ip) — the IP changed: run push (new HTTPS address), then up" ;;
  *) sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
