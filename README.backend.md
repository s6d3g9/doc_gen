# backend

FastAPI service.

Responsibilities:
- REST API for UI.
- Business logic.
- Postgres persistence.
- Redis queues/pubsub.
- AI API integration.
- Writes artifacts to disk (uploaded docs, generated docs, AI outputs).

## What is implemented now

Minimal API + persistence scaffold:

- DB schema: `Document`, `DocumentVersion`, `Task`
- Artifacts: stored on disk in `ARTIFACTS_DIR`
- Redis queue: list `tasks` (JSON payload)
- AI providers:
  - `none` (disabled stub)
  - `openai-compatible` (calls `{OPENAI_BASE_URL}/chat/completions`)

Endpoints:

- `GET /health`
- `POST /documents`
- `POST /documents/{document_id}/versions`
- `GET /documents/index`
- `GET /documents/versions/{version_id}`
- `GET /documents/versions/{version_id}/artifact`
- `POST /ai/summarize?async=true|false`
- `POST /ai/compare?async=true|false`
- `POST /ai/translate/bilingual?async=true|false`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/artifact`
- `POST /generate`
- `GET /google/status`
- `GET /google/login?return_to=...`
- `GET /google/callback?code=...&state=...`
- `POST /google/logout`
- `POST /google/docs/save`

## Sample generator: design-project contract

This repo includes a ready-to-use example template: **"Договор на разработку дизайн‑проекта"**.

Seed it into Postgres:

- with Docker running: `docker compose exec backend python -m app.seed.design_project_contract`

It prints `template_version_id` (latest). Use it with `/generate`:

```bash
api=http://localhost:8000
template_version_id=REPLACE_ME

curl -sS "$api/generate" \
	-H 'content-type: application/json' \
	-d @- <<JSON
{
	"template_version_id": "$template_version_id",
	"title": "Договор: дизайн-проект (пример)",
	"data": {
		"contract_number": "1/DP-2026",
		"contract_date": "2026-02-03",
		"city": "Москва",

		"executor_org_id": "REPLACE_WITH_ORG_ID",

		"customer_name": "Иванов Иван Иванович",
		"customer_phone": "+7 900 000-00-00",
		"customer_email": "customer@example.com",

		"project_title": "Дизайн-проект квартиры",
		"object_address": "г. Москва, ул. Примерная, д. 1, кв. 1",
		"deliverables": "планировки, коллажи, 3D-визуализации, чертежи, спецификации",
		"start_date": "2026-02-10",
		"end_date": "2026-03-20",

		"price_total": "150 000 руб.",
		"prepayment_percent": 50,
		"payment_method": "банковский перевод",
		"input_deadline": "в течение 3 рабочих дней",
		"delivery_format": "PDF + исходники (по согласованию)",
		"acceptance_days": 3
	}
}
JSON
```

Execution details live in `docs/architecture/algorithms.md`.

## Sample legal model: design-project contract semantics

This repo also includes a seed for the **formal legal domain model** (subjects/parties/obligations/payments/clauses) for the same “design‑project contract” example.

Seed it into Postgres:

- with Docker running: `docker compose exec backend python -m app.seed.design_project_contract_legal_model`

It prints ids like `contract_id`, `document_id`, `version_id` and party/subject ids.

## Run (local)

1. Start infra:
	- from repo root: `docker compose up -d --build`
2. Configure env:
	- copy `backend/.env.example` → `backend/.env`
3. Install deps:
	- `python -m venv .venv && source .venv/bin/activate`
	- `pip install -r backend/requirements.txt`
4. Run API:
	- `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload`

## Run (Docker)

From repo root:

- `docker compose up -d --build`
- API will be available at `http://localhost:8000`

Notes:
- Compose sets `DATABASE_URL` and `REDIS_URL` for the container.
- Artifacts are stored in a named volume `backend_artifacts` mounted at `/var/artifacts`.

## Google Calendar sync

This backend can create Google Calendar events for dates/ranges detected in a contract.

1. Create a Google service account and download JSON key.
2. Share the target calendar with the service account email.
3. Configure env in `backend/.env`:
	- `GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json`
	- `GOOGLE_CALENDAR_ID=...`
4. Call:
	- `POST /calendar/sync` with `{ "version_id": "..." }`

Notes:
- The current extractor supports numeric date formats (`DD.MM.YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`) and common ranges (`с ... по ...`, `A - B`).
- Created event ids are persisted in Postgres (`CalendarEventLink`) to keep sync idempotent.

## Google Drive / Google Docs (OAuth)

This backend supports connecting a Google account via OAuth and exporting a document version into Google Docs.

Configure env in `backend/.env`:

- `GOOGLE_OAUTH_CLIENT_ID=...`
- `GOOGLE_OAUTH_CLIENT_SECRET=...`
- `GOOGLE_OAUTH_REDIRECT_URL=http://localhost:8000/google/callback`
- `FRONTEND_BASE_URL=http://localhost:5173`
- `AUTH_STATE_SECRET=...` (any long random string)

Notes:
- In Google Cloud Console, add `GOOGLE_OAUTH_REDIRECT_URL` to **Authorized redirect URIs**.
- `FRONTEND_BASE_URL` is used to validate `return_to` and avoid open-redirects.
- Tokens are stored in Postgres (`GoogleOAuthConnection`) as a single “connected account” (MVP).

## Async tasks contract

- When `?async=true` is used, backend creates a `Task` row and enqueues JSON into Redis.
- Workers MUST update the `Task` row in Postgres; clients poll `GET /tasks/{id}`.

Workers are described in `README.agents.md`.
