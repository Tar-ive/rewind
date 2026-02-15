"""Task model for the OS scheduling engine.

Redis-backed task with all fields needed by LTS/MTS/STS schedulers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional

import redis

BUCKET_COUNT = 16
TASK_PREFIX = "task:"
BUCKET_PREFIX = "bucket:"
BACKLOG_KEY = "task:backlog"
ACTIVE_KEY = "task:active"


class Priority(IntEnum):
    P0_URGENT = 0      # Hard deadlines within 2 hours, external dependencies
    P1_IMPORTANT = 1   # Deadlines today, high-impact, upstream blockers
    P2_NORMAL = 2      # Routine tasks, flexible deadlines, personal goals
    P3_BACKGROUND = 3  # Nice-to-haves, low-energy fillers, delegatable


class TaskStatus:
    BACKLOG = "backlog"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SWAPPED_OUT = "swapped_out"
    DELEGATED = "delegated"


@dataclass
class Task:
    task_id: str
    title: str
    description: str = ""
    priority: int = Priority.P2_NORMAL
    energy_cost: int = 3            # 1-5
    estimated_duration: int = 30    # minutes
    deadline: str = ""              # ISO 8601
    preferred_start: str = ""       # ISO 8601
    status: str = TaskStatus.BACKLOG
    tags: list = field(default_factory=list)
    task_type: str = "general"      # general | email_reply | slack_message | ...
    cognitive_load: int = 3         # 1-5
    progress_notes: str = ""        # state save for preemption
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def deadline_urgency(self) -> float:
        """Inverse of time-to-deadline normalized to 0-10. Higher = more urgent."""
        if not self.deadline:
            return 0.0
        try:
            dl = datetime.fromisoformat(self.deadline)
            now = datetime.now(timezone.utc)
            hours_remaining = max((dl - now).total_seconds() / 3600, 0.1)
            # Inverse: 2 hours left → 5.0, 24 hours → ~0.4, 1 hour → 10.0
            return min(10.0, 10.0 / hours_remaining)
        except (ValueError, TypeError):
            return 0.0

    @property
    def execution_time_score(self) -> float:
        """Normalized execution time score 0-10. Shorter tasks score higher (SJF-inspired)."""
        # 15 min → ~6.7, 30 min → 3.3, 60 min → 1.7, 120 min → 0.8
        return min(10.0, 100.0 / max(self.estimated_duration, 1))

    @property
    def preferred_start_score(self) -> float:
        """Score based on preferred start proximity. 0-10."""
        if not self.preferred_start:
            return 5.0  # neutral
        try:
            ps = datetime.fromisoformat(self.preferred_start)
            now = datetime.now(timezone.utc)
            hours_until = (ps - now).total_seconds() / 3600
            if hours_until <= 0:
                return 10.0  # overdue preferred start
            return min(10.0, 10.0 / max(hours_until, 0.1))
        except (ValueError, TypeError):
            return 5.0

    @property
    def bucket(self) -> int:
        """Composite hash for task buffer placement."""
        D = self.deadline_urgency
        E = self.execution_time_score
        P = self.preferred_start_score
        composite = D * 0.45 + E * 0.30 + P * 0.25
        return math.floor(composite) % BUCKET_COUNT

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = json.dumps(d["tags"])
        # Ensure enums are stored as plain ints
        d["priority"] = int(self.priority)
        d["energy_cost"] = int(self.energy_cost)
        d["cognitive_load"] = int(self.cognitive_load)
        d["estimated_duration"] = int(self.estimated_duration)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        data = dict(data)  # copy
        if isinstance(data.get("tags"), str):
            data["tags"] = json.loads(data["tags"])
        # Ensure int fields — handle enum repr strings like '<Priority.P1_IMPORTANT: 1>'
        for int_field in ("priority", "energy_cost", "estimated_duration", "cognitive_load"):
            if int_field in data and isinstance(data[int_field], str):
                val = data[int_field]
                # Handle enum repr: '<Priority.P1_IMPORTANT: 1>'
                if ":" in val and val.startswith("<"):
                    val = val.split(":")[-1].strip().rstrip(">")
                data[int_field] = int(val)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_redis(self, r: redis.Redis) -> None:
        """Persist task to Redis hash and update bucket membership."""
        key = f"{TASK_PREFIX}{self.task_id}"
        self.updated_at = datetime.now(timezone.utc).isoformat()
        r.hset(key, mapping=self.to_dict())
        # Add to appropriate bucket set
        r.sadd(f"{BUCKET_PREFIX}{self.bucket}", self.task_id)
        # Track in status set
        if self.status == TaskStatus.BACKLOG:
            r.sadd(BACKLOG_KEY, self.task_id)
            r.srem(ACTIVE_KEY, self.task_id)
        elif self.status in (TaskStatus.ACTIVE, TaskStatus.IN_PROGRESS):
            r.sadd(ACTIVE_KEY, self.task_id)
            r.srem(BACKLOG_KEY, self.task_id)

    @classmethod
    def from_redis(cls, r: redis.Redis, task_id: str) -> Optional[Task]:
        """Load task from Redis by ID."""
        key = f"{TASK_PREFIX}{task_id}"
        data = r.hgetall(key)
        if not data:
            return None
        decoded = {k.decode() if isinstance(k, bytes) else k:
                   v.decode() if isinstance(v, bytes) else v
                   for k, v in data.items()}
        return cls.from_dict(decoded)

    @classmethod
    def delete_from_redis(cls, r: redis.Redis, task_id: str) -> None:
        """Remove task from Redis entirely."""
        key = f"{TASK_PREFIX}{task_id}"
        r.delete(key)
        r.srem(BACKLOG_KEY, task_id)
        r.srem(ACTIVE_KEY, task_id)
        # Clean from all buckets
        for b in range(BUCKET_COUNT):
            r.srem(f"{BUCKET_PREFIX}{b}", task_id)
