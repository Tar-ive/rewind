"""Long-Term Scheduler (LTS) — Daily Planner.

Pulls tasks from the backlog buffer into today's active schedule based on:
- Deadline pressure (tasks due today/tomorrow get pulled first)
- Priority level
- Estimated durations (bin-pack into available hours)
- Energy curve alignment (high-cognitive tasks → peak hours)

Runs once per day (morning planning) or on user trigger.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis

from src.config.settings import REDIS_URL
from src.models.task import Task, TaskStatus
from src.engine.task_buffer import get_backlog_tasks, get_active_tasks, store_task
from src.engine.sts import ShortTermScheduler

logger = logging.getLogger(__name__)

# Default planning parameters
DEFAULT_AVAILABLE_HOURS = 8
DEFAULT_ENERGY_CURVE = [
    2, 2, 1, 1, 1, 1,  # 00-05: sleep/low
    2, 3, 4, 5, 5, 4,  # 06-11: ramp up, peak mid-morning
    3, 3, 4, 5, 4, 3,  # 12-17: post-lunch dip, afternoon peak
    3, 2, 2, 2, 1, 1,  # 18-23: wind down
]


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def plan_day(
    available_hours: int = DEFAULT_AVAILABLE_HOURS,
    energy_curve: list[int] | None = None,
    peak_hours: list[int] | None = None,
    estimation_bias: float = 1.0,
    r: redis.Redis | None = None,
) -> tuple[list[Task], ShortTermScheduler]:
    """Generate today's schedule from the backlog.

    Returns:
        Tuple of (scheduled_tasks, sts_instance) ready for execution.
    """
    r = r or _get_redis()
    energy_curve = energy_curve or DEFAULT_ENERGY_CURVE
    peak_hours = peak_hours or [9, 10, 14, 15]

    backlog = get_backlog_tasks(r)
    if not backlog:
        logger.info("LTS: No tasks in backlog")
        return [], ShortTermScheduler()

    # Apply estimation bias correction
    for task in backlog:
        task.estimated_duration = int(task.estimated_duration * estimation_bias)

    # Score and sort tasks for selection
    scored = _score_tasks(backlog, peak_hours)
    scored.sort(key=lambda x: x[1], reverse=True)  # highest score first

    # Bin-pack into available time
    available_minutes = available_hours * 60
    selected = []
    used_minutes = 0

    for task, score in scored:
        if used_minutes + task.estimated_duration > available_minutes:
            # Try to fit shorter tasks
            continue
        selected.append(task)
        used_minutes += task.estimated_duration

    # Activate selected tasks
    for task in selected:
        task.status = TaskStatus.ACTIVE
        store_task(task, r)

    # Build STS schedule
    sts = ShortTermScheduler()
    sts.enqueue_batch(selected)

    logger.info(
        f"LTS: Planned {len(selected)} tasks ({used_minutes}min) "
        f"from {len(backlog)} backlog tasks"
    )

    return selected, sts


def _score_tasks(tasks: list[Task], peak_hours: list[int]) -> list[tuple[Task, float]]:
    """Score each task for daily planning selection.

    Scoring factors:
    - Deadline urgency (0-10, weight 0.40)
    - Priority level (0-10, weight 0.30)
    - Peak hour alignment (0-10, weight 0.15)
    - Duration efficiency (0-10, weight 0.15) — shorter tasks score higher for packing
    """
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    is_peak = current_hour in peak_hours

    scored = []
    for task in tasks:
        # Deadline urgency
        urgency = task.deadline_urgency  # 0-10

        # Priority score (P0=10, P1=7, P2=4, P3=1)
        priority_scores = {0: 10, 1: 7, 2: 4, 3: 1}
        priority_score = priority_scores.get(task.priority, 4)

        # Peak alignment: high-cognitive tasks score higher during peak
        peak_score = 5.0  # neutral
        if task.cognitive_load >= 4:
            peak_score = 8.0  # prefer scheduling during peaks
        elif task.cognitive_load <= 2:
            peak_score = 3.0  # prefer off-peak

        # Duration efficiency (SJF-inspired)
        duration_score = task.execution_time_score

        total = (
            urgency * 0.40
            + priority_score * 0.30
            + peak_score * 0.15
            + duration_score * 0.15
        )
        scored.append((task, total))

    return scored


def replan_remaining(
    sts: ShortTermScheduler,
    energy_level: int = 3,
    r: redis.Redis | None = None,
) -> list[Task]:
    """Re-plan remaining active tasks (e.g., after a disruption changes the landscape).

    Pulls the current STS queue, re-scores, and rebuilds.
    """
    r = r or _get_redis()
    active = get_active_tasks(r)
    sts.reorder(active)
    return sts.get_ordered_schedule(energy_level)
