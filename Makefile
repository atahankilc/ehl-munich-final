# Common commands from the repo root. Python runs in backend/ (uv), the PM app in frontend/ (npm).
# Profiles (D-053): development = API auto-reload + Vite dev server; production = API serves the built app.
.PHONY: install api dev build serve test up up-dev down logs

install:  ## Python venv + frontend deps
	cd backend && uv sync
	cd frontend && npm install

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

test:  ## Python tests + frontend typecheck
	cd backend && uv run pytest -q
	cd frontend && npm run typecheck

# ---- containers (compose.yaml); stop the native API first: same port, same SQLite file
up:  ## production container on http://127.0.0.1:8600
	docker compose --profile prod up -d --build

up-dev:  ## dev containers: API (reload) on :8600 + Vite on http://127.0.0.1:5173
	docker compose --profile dev up --build

down:  ## stop all containers
	docker compose --profile prod --profile dev down

logs:  ## follow container logs
	docker compose --profile prod --profile dev logs -f
