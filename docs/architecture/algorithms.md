# Execution algorithms

This document describes *how the system executes* the main scenarios end-to-end.

> Scope note: `backend` API exists; `agents` worker exists (Redis consumer); `frontend` UI may be added later.
> This doc is written so we can build consistently without re-deciding flows.

## Entities (current backend schema)

Backend persists these core tables:

- `Document`: logical document container (`id`, `title`, `created_at`)
- `DocumentVersion`: immutable snapshot/version (`id`, `document_id`, `artifact_path`, `content_type`, `created_at`)
- `Task`: async job record (`id`, `kind`, `status`, `document_id?`, `version_id?`, `result_path?`, `error?`)

See implementation in `backend/app/models.py`.

## Algorithm: create document (upload file or text)

**Goal:** Create a new `Document` plus initial `DocumentVersion`.

1. Client calls `POST /documents` with:
   - `title` (required)
   - either `file` (UploadFile) or `text`
2. Backend validates input (must provide `file` or `text`).
3. Backend writes the payload to disk as an artifact:
   - for `file`: bytes are stored as `ARTIFACTS_DIR/<uuid>.<suffix>`
   - for `text`: stored as `.txt`
4. Backend inserts:
   - `Document`
   - `DocumentVersion` pointing to the artifact path
5. Backend returns `Document`.

**Notes**
- In current scaffold, `DocumentVersion` is created but not returned by `POST /documents` (only `Document` is returned). If the UI needs version id immediately, we can adjust the response shape.

## Algorithm: add a new version

1. Client calls `POST /documents/{document_id}/versions` with `file` or `text`.
2. Backend ensures `Document` exists.
3. Backend writes the artifact to disk.
4. Backend inserts a new `DocumentVersion`.
5. Backend returns the new `DocumentVersion`.

## Algorithm: AI action (sync)

Used for quick actions when response size and latency are acceptable.

1. Client calls an AI endpoint, e.g. `POST /ai/summarize` with `version_id`.
2. Backend loads `DocumentVersion`.
3. Backend builds a prompt:
   - `system`: task role and formatting rules
   - `user`: document text (or placeholder if binary)
4. Backend calls the configured provider:
   - `MODEL_PROVIDER=none`: returns deterministic “disabled” output
   - `MODEL_PROVIDER=openai-compatible`: calls `POST {OPENAI_BASE_URL}/chat/completions`
5. Backend returns `{"text": "..."}`.

## Algorithm: AI action (async)

Used for longer actions, “Doczilla-like” editor integrations, and heavy processing.

1. Client calls AI endpoint with query param `?async=true`.
2. Backend creates a `Task` row with `status=pending`.
3. Backend enqueues a JSON payload into Redis list `tasks`.
4. Backend returns `{"text": "queued", "task_id": "..."}`.
5. Worker (`agents`) consumes from Redis and executes the job:
   - sets `Task.status=running`
   - runs provider call
   - writes result to artifact (usually `.txt`)
   - sets `Task.status=succeeded` and `result_path`
   - on error: sets `Task.status=failed` and `error`
6. Client polls `GET /tasks/{task_id}`.

**Important contract**
- Redis queue payloads MUST include `task_id` and `kind`.
- `Task` row in Postgres is the source of truth for status.

## Algorithm: compare versions

Two ways:

- **Sync:** `POST /ai/compare` with left/right version ids
- **Async:** same endpoint with `?async=true` (recommended for large docs)

Prompt strategy:
- Provide both texts with a delimiter.
- Request structured output: summary + list of material changes.

## Algorithm: bilingual translation

1. Client calls `POST /ai/translate/bilingual` with `version_id`, `source_lang`, `target_lang`.
2. Backend prompts the model to return a plain-text “two-column” table-like layout.

> Future improvement: emit `.docx` with real two-column formatting.

## Artifact lifecycle

- Artifacts are written to `ARTIFACTS_DIR`.
- DB rows reference artifacts via paths.

Operational rules (recommended):
- Artifacts are append-only (never overwrite in-place).
- Any cleanup process must ensure no live DB row points to deleted files.
- Consider checksums and size metadata (not implemented in scaffold yet).

## Binary documents (.docx/.pdf)

Current scaffold stores binaries on disk but does not parse them.

Planned implementation options:
- `.docx`: extract plain text for AI actions AND preserve formatting for editor view
- `.pdf`: extract text + page structure as available

## Minimal API reference (current)

- `GET /health`
- `POST /documents`
- `POST /documents/{document_id}/versions`
- `POST /ai/summarize?async=true|false`
- `POST /ai/compare?async=true|false`
- `POST /ai/translate/bilingual?async=true|false`
- `GET /tasks/{task_id}`
