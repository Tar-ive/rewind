"""Seed Redis with demo tasks matching Sarah's Stanford schedule.

Run: python -m src.scripts.seed_demo (from backend/)
"""

import redis

from src.config.settings import REDIS_URL
from src.models.task import Task, TaskStatus, Priority, BUCKET_PREFIX, BACKLOG_KEY, ACTIVE_KEY, TASK_PREFIX, BUCKET_COUNT


def clear_tasks(r: redis.Redis) -> None:
    """Remove all existing tasks from Redis."""
    # Clear task hashes
    for key in r.scan_iter(f"{TASK_PREFIX}*"):
        r.delete(key)
    # Clear buckets
    for b in range(BUCKET_COUNT):
        r.delete(f"{BUCKET_PREFIX}{b}")
    # Clear sets
    r.delete(BACKLOG_KEY)
    r.delete(ACTIVE_KEY)


def seed():
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    clear_tasks(r)

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Active tasks (Sarah's day) ───────────────────────────────────────
    active_tasks = [
        Task(
            task_id="task-1",
            title="CS 161 Lecture",
            description="Operating Systems lecture, Gates B01",
            priority=Priority.P1_IMPORTANT,
            energy_cost=3,
            estimated_duration=80,
            preferred_start=f"{today}T09:00:00",
            status=TaskStatus.ACTIVE,
            task_type="general",
            cognitive_load=4,
        ),
        Task(
            task_id="task-2",
            title="Study Group — CS 229",
            description="Machine learning pset review with group",
            priority=Priority.P1_IMPORTANT,
            energy_cost=4,
            estimated_duration=90,
            preferred_start=f"{today}T10:30:00",
            status=TaskStatus.ACTIVE,
            task_type="general",
            cognitive_load=4,
        ),
        Task(
            task_id="task-3",
            title="Gym — Cardio",
            description="AOERC, 30 min run + stretching",
            priority=Priority.P3_BACKGROUND,
            energy_cost=2,
            estimated_duration=60,
            preferred_start=f"{today}T12:00:00",
            status=TaskStatus.ACTIVE,
            task_type="general",
            cognitive_load=1,
        ),
        Task(
            task_id="task-4",
            title="CS 229 Problem Set",
            description="Pset 4 — due tomorrow 11:59pm",
            priority=Priority.P0_URGENT,
            energy_cost=5,
            estimated_duration=120,
            deadline=f"{today}T23:59:00",
            preferred_start=f"{today}T14:00:00",
            status=TaskStatus.ACTIVE,
            task_type="general",
            cognitive_load=5,
        ),
        Task(
            task_id="task-5",
            title="Office Hours — Prof. Ng",
            description="Ask about gradient descent question",
            priority=Priority.P2_NORMAL,
            energy_cost=3,
            estimated_duration=60,
            preferred_start=f"{today}T16:00:00",
            status=TaskStatus.ACTIVE,
            task_type="general",
            cognitive_load=3,
        ),
        Task(
            task_id="task-6",
            title="Reply to Prof. Martinez email",
            description="RE: Research assistant position follow-up",
            priority=Priority.P2_NORMAL,
            energy_cost=1,
            estimated_duration=15,
            preferred_start=f"{today}T17:00:00",
            status=TaskStatus.ACTIVE,
            task_type="email_reply",
            cognitive_load=1,
        ),
        Task(
            task_id="task-7",
            title="Slack — Update study group",
            description="Let group know about schedule change for tomorrow",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=10,
            preferred_start=f"{today}T17:15:00",
            status=TaskStatus.ACTIVE,
            task_type="slack_message",
            cognitive_load=1,
        ),
    ]

    # ── Backlog tasks (for swap-in demos) ────────────────────────────────
    backlog_tasks = [
        Task(
            task_id="task-b1",
            title="Review ML paper (Attention is All You Need)",
            description="Read and annotate for next week's presentation",
            priority=Priority.P2_NORMAL,
            energy_cost=4,
            estimated_duration=45,
            deadline=f"{today}T23:59:00",
            status=TaskStatus.BACKLOG,
            task_type="general",
            cognitive_load=4,
        ),
        Task(
            task_id="task-b2",
            title="Order textbook — CS 161",
            description="Operating Systems: Three Easy Pieces",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=5,
            status=TaskStatus.BACKLOG,
            task_type="general",
            cognitive_load=1,
        ),
        Task(
            task_id="task-b3",
            title="Draft lab report intro",
            description="Physics 41 — due Friday",
            priority=Priority.P2_NORMAL,
            energy_cost=3,
            estimated_duration=30,
            status=TaskStatus.BACKLOG,
            task_type="general",
            cognitive_load=3,
        ),
        Task(
            task_id="task-b4",
            title="Cancel dentist appointment",
            description="Conflicts with Thursday study session",
            priority=Priority.P2_NORMAL,
            energy_cost=1,
            estimated_duration=5,
            status=TaskStatus.BACKLOG,
            task_type="cancel_appointment",
            cognitive_load=1,
        ),
        Task(
            task_id="task-b5",
            title="Notion — update project tracker",
            description="Mark completed milestones for CS 229 project",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=10,
            status=TaskStatus.BACKLOG,
            task_type="doc_update",
            cognitive_load=1,
        ),
    ]

    all_tasks = active_tasks + backlog_tasks
    for task in all_tasks:
        task.to_redis(r)

    print(f"Seeded {len(active_tasks)} active tasks + {len(backlog_tasks)} backlog tasks")
    print(f"\nActive schedule:")
    for t in active_tasks:
        print(f"  [{t.task_id}] P{t.priority} {t.title} ({t.estimated_duration}min, E={t.energy_cost})")
    print(f"\nBacklog (swap-in candidates):")
    for t in backlog_tasks:
        print(f"  [{t.task_id}] P{t.priority} {t.title} ({t.estimated_duration}min, E={t.energy_cost})")


if __name__ == "__main__":
    seed()
