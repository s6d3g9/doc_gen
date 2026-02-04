# Monorepo

This repository contains multiple components:

- `frontend/` — UI (React/Vite), talks to `backend` via REST
- `backend/` — FastAPI: business logic, DB, AI integration, queues
- `agents/` — optional workers for heavy ML/AI/backtest tasks (consume Redis jobs)
- `docs/` — architecture and interaction docs

Convenience docs (moved to repo root):

- `README.frontend.md`
- `README.backend.md`
- `README.agents.md`
- `README.architecture.md`
- `README.product.md`
- `README.ui-rules.md`

## Architecture

See:

- `docs/architecture/flows.md`
- `docs/architecture/storage.md`
- `docs/architecture/containers.md`
- `docs/architecture/algorithms.md`

## Roadmap

- `docs/roadmap.md`

## Product spec (UX)

- `docs/product/tz-client-journey.md`
- `docs/product/tz-freshdoc-like-generator.md`
- `docs/product/ui-display-requirements.md`

UI display rules:
- `README.ui-rules.md`

## High-level flows (summary)

- User → frontend → backend → db/redis/AI
- backend → agents (via Redis)
- backend writes artifacts (uploads, generated docs, AI outputs) to disk and stores metadata in Postgres

## Status

Scaffolding is in progress: service code will be added under `frontend/`, `backend/`, and `agents/`.

## Development (local)

- Infra + backend API (Postgres + Redis + FastAPI): `docker compose up -d --build`
- Backend API docs/setup: see `README.backend.md`

Frontend dev server:
- `cd frontend && npm install && npm run dev`

Frontend and agents are intentionally minimal at this stage; we add them as the API contract stabilizes.