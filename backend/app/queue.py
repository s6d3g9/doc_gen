from __future__ import annotations

import json
from typing import Any

import redis

from .settings import settings


TASK_QUEUE_KEY = "tasks"


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_task(payload: dict[str, Any]) -> None:
    r = get_redis()
    r.rpush(TASK_QUEUE_KEY, json.dumps(payload))


def dequeue_task(block_seconds: int = 5) -> dict[str, Any] | None:
    r = get_redis()
    item = r.blpop(TASK_QUEUE_KEY, timeout=block_seconds)
    if not item:
        return None
    _, raw = item
    return json.loads(raw)
