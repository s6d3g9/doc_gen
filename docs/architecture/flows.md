# Main flows

## User → system

1. User → `frontend` (UI)
2. `frontend` → `backend` (REST)
3. `backend` → `db` (Postgres) for documents, templates, entities, task status
4. `backend` → `redis` for queues and/or pub/sub
5. `backend` → AI API (summarize/compare/translate/help fill forms) over HTTP
6. Optional: `backend` → `agents` via Redis (enqueue tasks)

## Backend → AI

- `backend` calls external/internal AI API endpoints (HTTP client, e.g. `httpx`).
- Results are persisted as artifacts on disk and referenced from Postgres.

## Backend → Agents

- `backend` enqueues background jobs to Redis.
- `agents` workers consume jobs, execute heavy ML/AI/backtests, and write artifacts.
- `backend` exposes status via REST by reading state from Postgres (and optionally Redis).

## Artifact writes

- On upload or generation, `backend` writes artifacts to `ARTIFACTS_DIR`.
- Postgres stores artifact paths in `DocumentVersion.artifact_path` (and related rows for generation and tasks).
