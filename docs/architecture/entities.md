# Entities (what we work with)

This file lists the core entities of the product (primarily persisted in Postgres), plus related storage objects.

## Core document registry

### DocumentType
- Purpose: high-level classification for documents (e.g. “Договоры”, “Кадровые документы”).
- Stored in Postgres: `DocumentType`
- Key fields: `id`, `key` (stable machine key), `title`, `description`, `created_at`, `updated_at`

### Document
- Purpose: logical container for a real-life document; versions are attached to it.
- Stored in Postgres: `Document`
- Key fields: `id`, `title`, `created_at`

### DocumentTypeAssignment
- Purpose: attach a type to a document.
- Stored in Postgres: `DocumentTypeAssignment`
- Key fields: `document_id`, `type_id`, `created_at`
- Invariant (app-level): treat as **0..1 type per Document** (enforced by API behavior).

### DocumentVersion
- Purpose: immutable snapshot of a document’s content at a point in time.
- Stored in Postgres: `DocumentVersion`
- Key fields: `id`, `document_id`, `artifact_path`, `content_type`, `created_at`
- Storage: `artifact_path` points to a file under `ARTIFACTS_DIR` (see “Artifacts”).

## Async processing

### Task
- Purpose: track async work (AI operations, heavy processing) executed by the worker.
- Stored in Postgres: `Task`
- Key fields: `id`, `kind`, `status`, `document_id?`, `version_id?`, `result_path?`, `error?`, `created_at`, `updated_at`
- Status: `pending` → `running` → `succeeded | failed`

### Redis queue item (not a DB row)
- Purpose: transport for async tasks to the worker.
- Storage: Redis list `tasks` (payload is JSON).
- Must include: `task_id`, `kind` (and usually `version_id` / `document_id` depending on kind).

## Organizations (requisites)

### Organization
- Purpose: reusable “party” entity (executor/customer) used in templates and generated documents.
- Stored in Postgres: `Organization`
- Key fields: `id`, `name`, `inn?`, `ogrn?`, `kpp?`, `address?`, `phone?`, `email?`, `created_at`, `updated_at`

## Legal domain model (RU-first, extensible)

Goal: represent **formal legal semantics** of a contract in a structured way (subjects ↔ actions ↔ objects, conditions, deadlines, payments, liability), with an explicit link to normative sources (citations) when needed.

Scope note:
- This is a **generic model** (works for РФ first) and is designed to support other jurisdictions later by storing `country_code`/`jurisdiction_country_code` and keeping most clause details in structured `data`.
- It does not try to encode “all legislation”; instead it provides primitives that can model most contracts and can reference specific norms via `LegalNormReference`.

### LegalSubject
- Purpose: unified “subject of law” (физлицо, юрлицо, госорган, и т.д.).
- Stored in Postgres: `LegalSubject`
- Key fields: `id`, `kind` (`person|organization|government_body|other`), `country_code` (e.g. `RU`), `display_name`, `organization_id?`, person attributes (`first_name?`, `last_name?`, …), contacts/address, `created_at`, `updated_at`
- Notes: `organization_id` links to `Organization` when the subject is an organization.

### Representation
- Purpose: representation / authority basis ("действует на основании …") between two subjects.
- Stored in Postgres: `Representation`
- Key fields: `id`, `principal_subject_id`, `agent_subject_id`, `basis_kind` (`power_of_attorney|charter|order|other`), `basis_number?`, `basis_date?`, `valid_from?`, `valid_to?`, `created_at`, `updated_at`

### Contract
- Purpose: structured “contract record” attached (optionally) to a `Document`.
- Stored in Postgres: `Contract`
- Key fields: `id`, `title`, `kind` (e.g. `services|works|supply|nda|lease|license|mixed|other`), `jurisdiction_country_code` (default `RU`), `governing_law_text?`, `document_id?`, `created_at`, `updated_at`

### ContractParty
- Purpose: link a `LegalSubject` to a contract with a role.
- Stored in Postgres: `ContractParty`
- Key fields: `id`, `contract_id`, `subject_id`, `role_key` (stable machine key like `customer`, `executor`), `role_label?` (human override), `created_at`

### ContractObject
- Purpose: what the contract is about (object of relations): work result, services, goods, IP, premises, etc.
- Stored in Postgres: `ContractObject`
- Key fields: `id`, `contract_id`, `kind` (free string), `title`, `description?`, `address?`, `created_at`

### ContractEvent
- Purpose: time anchors: start/end, milestones, acceptance, payment triggers.
- Stored in Postgres: `ContractEvent`
- Key fields: `id`, `contract_id`, `kind`, `title`, `start_date?`, `end_date?`, `created_at`

### ContractCondition
- Purpose: conditions/triggers (“если … то …”), including preconditions for obligations/rights.
- Stored in Postgres: `ContractCondition`
- Key fields: `id`, `contract_id`, `kind`, `expression` (text), `created_at`

### NormativeStatement
- Purpose: the core **subject–action–object** unit.
- Stored in Postgres: `NormativeStatement`
- Key fields:
	- `id`, `contract_id`, `kind` (`obligation|right|prohibition|permission`)
	- `actor_party_id` (who must/may)
	- `counterparty_party_id?` (to/against whom)
	- `object_id?` (what it’s about)
	- `action_verb?` (optional short verb)
	- `description` (human-readable)
	- `condition_id?`
	- due fields: `due_date?` and/or `due_event_id?`
	- `created_at`

### PaymentTerm
- Purpose: formalize payment logic (amount/percent, payer/payee, due triggers).
- Stored in Postgres: `PaymentTerm`
- Key fields: `id`, `contract_id`, `payer_party_id`, `payee_party_id`, `kind`, `amount_minor?`, `currency_code`, `percent?`, `due_date?`, `due_event_id?`, `description?`, `created_at`

### ContractClause
- Purpose: store structured clauses (governing law, dispute resolution, liability, confidentiality, personal data, IP, force majeure, termination, notices, etc.).
- Stored in Postgres: `ContractClause`
- Key fields: `id`, `contract_id`, `kind` (stable machine key), `title?`, `body?`, `data?` (JSON), `created_at`
- Notes: clause details may vary by jurisdiction; `data` is used for extensibility.

### LegalNormReference
- Purpose: reference/citation to a legal norm/source (e.g. “ГК РФ, ст. 432”).
- Stored in Postgres: `LegalNormReference`
- Key fields: `id`, `jurisdiction_country_code` (default `RU`), `citation`, `url?`, `created_at`

### ClauseNormLink / StatementNormLink
- Purpose: attach citations to clauses/statements.
- Stored in Postgres: `ClauseNormLink`, `StatementNormLink`
- Key fields: `clause_id` / `statement_id`, `norm_id`, `created_at`

## Templates & generation

### DocumentTemplate
- Purpose: template “card” (human-readable title, category).
- Stored in Postgres: `DocumentTemplate`
- Key fields: `id`, `title`, `category?`, `description?`, `created_at`

### DocumentTemplateVersion
- Purpose: versioned template body.
- Stored in Postgres: `DocumentTemplateVersion`
- Key fields: `id`, `template_id`, `version` (int), `body` (Jinja2), `created_at`

### DocumentTemplateField
- Purpose: schema of user inputs required to render a template.
- Stored in Postgres: `DocumentTemplateField`
- Key fields: `template_version_id`, `key`, `label`, `field_type`, `required`, `order`, `options?`, `default_value?`
- Field types: `text | number | date | boolean | choice | organization_ref`
- `organization_ref` convention: generator expands `executor_org_id` into `executor_org_id_name`, `executor_org_id_inn`, etc.

### GeneratedDocument
- Purpose: audit trail of generation inputs used to produce a document.
- Stored in Postgres: `GeneratedDocument`
- Key fields: `document_id`, `template_version_id`, `data` (JSON), `created_at`

## Calendar integration

### CalendarEventLink
- Purpose: idempotent link between a document version and a Google Calendar event created from extracted dates.
- Stored in Postgres: `CalendarEventLink`
- Key fields: `version_id`, `google_calendar_id`, `google_event_id`, `start_date`, `end_date`, `created_at`

## Artifacts (filesystem)

Artifacts are files stored on disk under `ARTIFACTS_DIR` and referenced by DB rows.

- Uploads and document versions: referenced by `DocumentVersion.artifact_path`
- AI outputs / task results: referenced by `Task.result_path`

API serves artifacts via download endpoints (no direct filesystem exposure).

## Source of truth

- DB models live in: backend/app/models.py
- Document type API: backend/app/routers/document_types.py
- Documents API: backend/app/routers/documents.py
- Templates API: backend/app/routers/templates.py
- Generation API: backend/app/routers/generate.py
- Legal model API: backend/app/routers/contracts.py
