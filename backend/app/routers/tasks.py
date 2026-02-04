from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..db import get_session
from ..models import Task
from ..files import resolve_artifact_path

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task(task_id: str) -> Task:
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task


@router.get("/{task_id}/artifact")
def download_task_artifact(task_id: str) -> FileResponse:
    with get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if not task.result_path:
            raise HTTPException(status_code=404, detail="Task has no result")

        path = resolve_artifact_path(task.result_path)
        return FileResponse(path=str(path), media_type="text/plain", filename=path.name)
