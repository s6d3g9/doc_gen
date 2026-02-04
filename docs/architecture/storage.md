# Storage model

## Postgres (source of truth)

Stores:
- Documents, versions, and generation metadata:
	- `Document`, `DocumentVersion`
	- `GeneratedDocument` (which template/version + which structured data was used)
- Template catalogue:
	- `DocumentTemplate`, `DocumentTemplateVersion`, `DocumentTemplateField`
- Entity directory (source-of-truth values used in templates):
	- `Organization` (and later: people/signers)
- Async task records:
	- `Task` (status, result artifact path, error)
- Google Calendar sync idempotency links:
	- `CalendarEventLink` (version_id ↔ event_id, start/end)

## Redis (ephemeral)

Stores:
- Job queue payloads for async actions (`tasks` list)
- (Optional later) pub/sub notifications for UI updates
- (Optional later) short-lived locks / rate-limit counters

## Disk (artifacts)

Stores:
- Uploaded document artifacts (pdf/docx/txt)
- Generated document artifacts (currently `.txt`, later `.docx/.pdf`)
- AI outputs (summaries, translations, comparisons) as text artifacts

Postgres links to artifacts via paths/URIs and metadata.

## Git (source)

- Application source code lives in Git.
- Contract templates are stored in Postgres (versioned) and rendered deterministically.
