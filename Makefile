# Common commands from the repo root. Python runs in backend/ (uv), the PM app in frontend/ (npm).
# Profiles (D-053): development = API auto-reload + Vite dev server; production = API serves the built app.
.PHONY: install api dev build serve test up up-dev down logs db db-stop migrate testdata backup

install:  ## Python venv + frontend deps
	cd backend && uv sync
	cd frontend && npm install

# ---- database (PostgreSQL + pgvector, D-059)
db:  ## start only the database container (127.0.0.1:5433), wait until it is ready
	docker compose up -d --wait db

db-stop:  ## stop the database container (data stays in the pgdata volume)
	docker compose stop db

migrate: db  ## apply the schema migrations (Alembic) as the owner (MIGRATION_DATABASE_URL)
	cd backend && uv run alembic upgrade head

backup: db  ## pg_dump of the app database → data/backups/sharksight-<UTC time>.dump (restore with pg_restore)
	mkdir -p data/backups
	docker compose exec -T db pg_dump -U sharksight -Fc sharksight > data/backups/sharksight-$$(date -u +%Y%m%dT%H%M%SZ).dump
	@ls -lh data/backups/*.dump | tail -1

testdata: db  ## refresh sharksight_testdata, the real-data copy the API tests clone (works while the app runs)
	docker compose exec -T db sh -c 'dropdb --if-exists -U sharksight sharksight_testdata && createdb -U sharksight sharksight_testdata && pg_dump -U sharksight sharksight | psql -q -U sharksight -d sharksight_testdata'

# ---- native, development profile
api:  ## API on http://127.0.0.1:8600, auto-reload on backend/src changes
	cd backend && APP_ENV=development uv run python -m api

dev:  ## PM app dev server on http://127.0.0.1:5173 (needs `make api`)
	cd frontend && npm run dev

# ---- native, production profile
build:  ## build frontend/dist
	cd frontend && npm run build

serve: build  ## build, then the API alone serves the app on http://127.0.0.1:8600 (no reload)
	cd backend && APP_ENV=production uv run python -m api

test: db  ## Python tests (incl. the PostgreSQL ones) + frontend typecheck
	cd backend && uv run pytest -q
	cd frontend && npm run typecheck

# ---- containers (compose.yaml); stop the native API first: same port, same SQLite file
up:  ## production container on http://127.0.0.1:8600
	docker compose --profile prod up -d --build

up-dev:  ## dev containers: API (reload) on :8600 + Vite on http://127.0.0.1:5173
	docker compose --profile dev up --build

down:  ## stop all containers (the database volume is kept)
	docker compose --profile prod --profile dev down

logs:  ## follow container logs
	docker compose --profile prod --profile dev logs -f
