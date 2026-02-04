from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime
from typing import Any

from .ai.factory import get_provider
from .artifacts import ensure_artifacts_dir, write_text
from .db import get_session, init_db
from .models import DocumentVersion, Task, TaskStatus
from .queue import dequeue_task
from .text import read_version_text


logger = logging.getLogger("app.worker")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _set_task_status(
    *,
    task_id: str,
    status: TaskStatus,
    result_path: str | None = None,
    error: str | None = None,
) -> None:
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise RuntimeError(f"Task not found: {task_id}")
        task.status = status
        task.updated_at = _utcnow()
        if result_path is not None:
            task.result_path = result_path
        if error is not None:
            task.error = error
        session.add(task)
        session.commit()


def _get_version(version_id: str) -> DocumentVersion:
    with get_session() as session:
        version = session.get(DocumentVersion, version_id)
        if not version:
            raise RuntimeError(f"Version not found: {version_id}")
        return version


async def _run_ai(*, system: str, user: str) -> str:
    provider = get_provider()
    resp = await provider.run(system=system, user=user)
    return resp.text


async def _handle_payload(payload: dict[str, Any]) -> None:
    task_id = payload.get("task_id")
    kind = payload.get("kind")

    if not isinstance(task_id, str) or not task_id:
        logger.error("Invalid payload: missing task_id: %s", payload)
        return
    if not isinstance(kind, str) or not kind:
        _set_task_status(task_id=task_id, status=TaskStatus.failed, error="missing kind")
        return

    logger.info("Starting task %s kind=%s", task_id, kind)
    try:
        _set_task_status(task_id=task_id, status=TaskStatus.running)

        if kind in {"summarize"}:
            version_id = payload.get("version_id")
            system = payload.get("system")
            instructions = payload.get("instructions")
            if not isinstance(version_id, str) or not version_id:
                raise RuntimeError("missing version_id")
            if not isinstance(system, str) or not system:
                raise RuntimeError("missing system")
            version = _get_version(version_id)
            user = read_version_text(version)
            if isinstance(instructions, str) and instructions.strip():
                user = instructions.strip() + "\n\n" + user
            text = await _run_ai(system=system, user=user)

        elif kind in {"translate_bilingual"}:
            system = payload.get("system")
            user = payload.get("instructions")
            if not isinstance(system, str) or not system:
                raise RuntimeError("missing system")
            if not isinstance(user, str) or not user:
                raise RuntimeError("missing instructions")
            text = await _run_ai(system=system, user=user)

        elif kind in {"compare"}:
            left_version_id = payload.get("left_version_id")
            right_version_id = payload.get("right_version_id")
            instructions = payload.get("instructions")
            if not isinstance(left_version_id, str) or not left_version_id:
                raise RuntimeError("missing left_version_id")
            if not isinstance(right_version_id, str) or not right_version_id:
                raise RuntimeError("missing right_version_id")

            left = _get_version(left_version_id)
            right = _get_version(right_version_id)

            system = (
                "You are a legal assistant. Compare two versions of a document and describe changes in a structured way."
            )
            user = read_version_text(left) + "\n\n---\n\n" + read_version_text(right)
            if isinstance(instructions, str) and instructions.strip():
                user = instructions.strip() + "\n\n" + user
            text = await _run_ai(system=system, user=user)

        else:
            raise RuntimeError(f"Unknown kind: {kind}")

        result_path = write_text(text, suffix=".txt")
        _set_task_status(task_id=task_id, status=TaskStatus.succeeded, result_path=result_path)
        logger.info("Task %s succeeded", task_id)

    except Exception as exc:
        logger.exception("Task %s failed", task_id)
        _set_task_status(task_id=task_id, status=TaskStatus.failed, error=str(exc)[:2000])


async def run_forever() -> None:
    logging.basicConfig(level=logging.INFO)
    ensure_artifacts_dir()
    init_db()

    stop_event = asyncio.Event()

    def _stop(*_args: object) -> None:
        stop_event.set()

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except Exception:
        # Signal handlers may not be available on some platforms.
        pass

    logger.info("Worker started; waiting for jobs...")

    while not stop_event.is_set():
        payload = await asyncio.to_thread(dequeue_task, 5)
        if not payload:
            continue
        await _handle_payload(payload)

    logger.info("Worker stopping")


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
