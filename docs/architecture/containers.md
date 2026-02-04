# Containers & networking

## Connectivity

- `frontend` ⇄ `backend` (REST)
- `backend` ⇄ `db` (SQL)
- `backend` ⇄ `redis` (queues, pub/sub)
- `backend` ⇄ `agents` (indirect via Redis)
- `backend` ⇄ AI API (HTTP)

## Ports (suggested)

- `frontend`: 5173 (dev)
- `backend`: 8000
- `db`: 5432
- `redis`: 6379

## Notes

- In local development, `frontend` usually runs on host and proxies to `backend`.
- In containerized deployment, `frontend` can be served as static assets behind a reverse proxy.
