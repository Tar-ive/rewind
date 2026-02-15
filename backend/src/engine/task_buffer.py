"""Redis-backed hash table for the Task Buffer.

Implements the composite hash function from spec Section 5.2:
  hash(task) = floor(D * 0.45 + E * 0.30 + P * 0.25) mod BUCKET_COUNT

Provides O(1) bucket lookup + O(k) scan within bucket for MTS swap candidates.
"""

from __future__ import annotations

from typing import Optional

import redis

from src.config.settings import REDIS_URL
from src.models.task import (
    Task,
    TaskStatus,
    BUCKET_COUNT,
    BUCKET_PREFIX,
    BACKLOG_KEY,
    ACTIVE_KEY,
)


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def store_task(task: Task, r: redis.Redis | None = None) -> None:
    """Store a task in the buffer, placing it in the correct bucket."""
    r = r or _get_redis()
    task.to_redis(r)


def get_task(task_id: str, r: redis.Redis | None = None) -> Optional[Task]:
    """Retrieve a single task by ID."""
    r = r or _get_redis()
    return Task.from_redis(r, task_id)


def remove_task(task_id: str, r: redis.Redis | None = None) -> None:
    """Remove a task from the buffer entirely."""
    r = r or _get_redis()
    Task.delete_from_redis(r, task_id)


def get_bucket_tasks(bucket: int, r: redis.Redis | None = None) -> list[Task]:
    """Get all tasks in a specific bucket."""
    r = r or _get_redis()
    task_ids = r.smembers(f"{BUCKET_PREFIX}{bucket}")
    tasks = []
    for tid in task_ids:
        task = Task.from_redis(r, tid)
        if task:
            tasks.append(task)
    return tasks


def get_backlog_tasks(r: redis.Redis | None = None) -> list[Task]:
    """Get all tasks in the backlog."""
    r = r or _get_redis()
    task_ids = r.smembers(BACKLOG_KEY)
    tasks = []
    for tid in task_ids:
        task = Task.from_redis(r, tid)
        if task and task.status == TaskStatus.BACKLOG:
            tasks.append(task)
    return tasks


def get_active_tasks(r: redis.Redis | None = None) -> list[Task]:
    """Get all tasks in today's active schedule."""
    r = r or _get_redis()
    task_ids = r.smembers(ACTIVE_KEY)
    tasks = []
    for tid in task_ids:
        task = Task.from_redis(r, tid)
        if task and task.status in (TaskStatus.ACTIVE, TaskStatus.IN_PROGRESS):
            tasks.append(task)
    return tasks


def find_swap_candidates(
    available_minutes: int,
    energy_level: int,
    peak_hours: list[int] | None = None,
    r: redis.Redis | None = None,
) -> list[Task]:
    """Find backlog tasks that fit into available time and energy.

    MTS swap algorithm from spec Section 5.3:
    1. Query hash table for tasks where estimated_duration <= available_minutes
    2. Filter by energy compatibility (energy_level >= task.energy_cost)
    3. Filter by peak_hours alignment (prefer high-cognitive tasks during peak)
    4. Rank by deadline urgency (highest wins)
    """
    r = r or _get_redis()
    candidates = []

    for bucket in range(BUCKET_COUNT):
        for task in get_bucket_tasks(bucket, r):
            if task.status != TaskStatus.BACKLOG:
                continue
            # Time fit
            if task.estimated_duration > available_minutes:
                continue
            # Energy fit
            if task.energy_cost > energy_level:
                continue
            candidates.append(task)

    # Sort by deadline urgency (highest first)
    candidates.sort(key=lambda t: t.deadline_urgency, reverse=True)

    # If we know peak hours, prefer high-cognitive tasks during peaks
    if peak_hours:
        from datetime import datetime, timezone
        current_hour = datetime.now(timezone.utc).hour
        is_peak = current_hour in peak_hours
        if is_peak:
            # During peak: sort high-cognitive tasks first, then by urgency
            candidates.sort(
                key=lambda t: (t.cognitive_load, t.deadline_urgency),
                reverse=True,
            )

    return candidates


def find_swap_out_candidates(
    minutes_needed: int,
    r: redis.Redis | None = None,
) -> list[Task]:
    """Find active tasks that can be swapped out to free time.

    Returns tasks sorted by priority (lowest/P3 first) then by deadline
    urgency (least urgent first).
    """
    r = r or _get_redis()
    active = get_active_tasks(r)

    # Can't swap out in-progress tasks
    candidates = [t for t in active if t.status == TaskStatus.ACTIVE]

    # Sort: lowest priority first, then least urgent deadline
    candidates.sort(key=lambda t: (-t.priority, t.deadline_urgency))

    # Accumulate tasks until we free enough minutes
    result = []
    freed = 0
    for task in candidates:
        if freed >= minutes_needed:
            break
        result.append(task)
        freed += task.estimated_duration

    return result
