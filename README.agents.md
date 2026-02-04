# agents

Optional workers for heavy/background tasks.

Responsibilities:
- Consume jobs from Redis.
- Run background AI actions.
- Write artifacts to disk and update metadata/state in Postgres.

## Execution contract

Workers consume JSON from Redis list `tasks`.

Minimum payload fields:

- `task_id`: id of `Task` row in Postgres
- `kind`: action kind (e.g. `summarize`, `compare`, `translate_bilingual`)

Recommended fields (depending on `kind`):

- `version_id` OR `left_version_id` + `right_version_id`
- `system` and `instructions` (for provider calls)

Workers update the `Task` record:

- `pending` → `running` → `succeeded|failed`
- write output to disk and set `result_path`
- on exception set `error`

## Status

Worker implementation lives in `backend/app/worker.py` and is run in Docker Compose as service `agents`.
