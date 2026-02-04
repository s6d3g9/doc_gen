# frontend

React/Vite UI.

Responsibilities:
- Provide UI for managing documents, versions, templates, and entities (directory).
- Call `backend` REST API.

## UX scope (Doczilla-like)

The intended UI direction is similar to Doczilla AI:

- Upload and store documents
- Version history
- AI actions on whole document and/or selected fragments (future)
- Compare versions
- Summarize / extract / Q&A (future)
- Bilingual translation output

At this stage, backend endpoints are being stabilized first.

Dev:
- `cd frontend`
- `npm install`
- `npm run dev`

Config:
- API base URL via env (e.g. `VITE_API_BASE_URL`).

UI rules:
- `README.ui-rules.md` — light/dark themes, layout/scaling rules, and properties panel behavior.
