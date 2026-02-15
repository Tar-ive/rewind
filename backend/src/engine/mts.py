"""Medium-Term Scheduler (MTS) — Swap Engine.

Handles disruption recovery by swapping tasks between today's active
schedule and the backlog buffer.

SWAP-IN triggers:  free time detected, energy surplus, deadline pressure
SWAP-OUT triggers: time overflow, energy deficit, priority preemption
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis

from src.config.settings import REDIS_URL
from src.models.task import Task, TaskStatus
from src.engine.task_buffer import (
    find_swap_candidates,
    find_swap_out_candidates,
    get_active_tasks,
    store_task,
)
from src.engine.sts import ShortTermScheduler

logger = logging.getLogger(__name__)


@dataclass
class SwapResult:
    """Result of a swap operation."""
    swapped_in: list[Task]
    swapped_out: list[Task]
    delegated: list[Task]
    summary: str


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def handle_swap_in(
    freed_minutes: int,
    energy_level: int,
    peak_hours: list[int] | None = None,
    sts: ShortTermScheduler | None = None,
    r: redis.Redis | None = None,
) -> SwapResult:
    """SWAP-IN: free time detected, pull tasks from buffer into active schedule.

    Algorithm (spec Section 5.3):
    1. Query buffer for tasks where estimated_duration <= freed_minutes
    2. Filter by energy compatibility
    3. Filter by peak_hours alignment
    4. Rank by deadline urgency
    5. Insert into active schedule, notify STS
    """
    r = r or _get_redis()
    candidates = find_swap_candidates(freed_minutes, energy_level, peak_hours, r)

    swapped_in = []
    remaining_minutes = freed_minutes

    for task in candidates:
        if remaining_minutes < task.estimated_duration:
            continue
        # Swap in
        task.status = TaskStatus.ACTIVE
        store_task(task, r)
        if sts:
            sts.enqueue(task)
        swapped_in.append(task)
        remaining_minutes -= task.estimated_duration
        logger.info(f"SWAP-IN: {task.title} ({task.estimated_duration}min, E={task.energy_cost})")

        if remaining_minutes <= 0:
            break

    summary = (
        f"Swapped in {len(swapped_in)} tasks using {freed_minutes - remaining_minutes}min "
        f"of {freed_minutes}min freed time"
    )
    return SwapResult(swapped_in=swapped_in, swapped_out=[], delegated=[], summary=summary)


def handle_swap_out(
    lost_minutes: int,
    energy_level: int,
    sts: ShortTermScheduler | None = None,
    r: redis.Redis | None = None,
) -> SwapResult:
    """SWAP-OUT: time overflow detected, move tasks from active to buffer.

    Selects lowest-priority, least-urgent tasks to free the needed time.
    """
    r = r or _get_redis()
    candidates = find_swap_out_candidates(lost_minutes, r)

    swapped_out = []
    for task in candidates:
        task.status = TaskStatus.SWAPPED_OUT
        store_task(task, r)
        swapped_out.append(task)
        logger.info(f"SWAP-OUT: {task.title} (P{task.priority}, {task.estimated_duration}min)")

    # If energy is low, auto-delegate P3 tasks
    delegated = []
    if sts and energy_level <= 2:
        delegated = sts.auto_delegate_p3(energy_level)
        for task in delegated:
            store_task(task, r)
            logger.info(f"DELEGATE: {task.title} → GhostWorker")

    freed = sum(t.estimated_duration for t in swapped_out)
    summary = (
        f"Swapped out {len(swapped_out)} tasks freeing {freed}min. "
        f"Delegated {len(delegated)} P3 tasks."
    )
    return SwapResult(swapped_in=[], swapped_out=swapped_out, delegated=delegated, summary=summary)


def handle_disruption(
    freed_minutes: int,
    energy_level: int,
    peak_hours: list[int] | None = None,
    sts: ShortTermScheduler | None = None,
    r: redis.Redis | None = None,
) -> SwapResult:
    """Main entry point for disruption handling.

    Positive freed_minutes → swap-in opportunity.
    Negative freed_minutes → swap-out needed.
    """
    if freed_minutes > 0:
        return handle_swap_in(freed_minutes, energy_level, peak_hours, sts, r)
    elif freed_minutes < 0:
        return handle_swap_out(abs(freed_minutes), energy_level, sts, r)
    else:
        # No time change — might still need reordering
        if sts:
            active = get_active_tasks(r or _get_redis())
            sts.reorder(active)
        return SwapResult(
            swapped_in=[], swapped_out=[], delegated=[],
            summary="No time change. Reordered active schedule.",
        )


def handle_preemption(
    urgent_task: Task,
    energy_level: int,
    sts: ShortTermScheduler | None = None,
    r: redis.Redis | None = None,
) -> SwapResult:
    """Handle a high-priority task arrival that preempts active work."""
    r = r or _get_redis()

    # Activate the urgent task
    urgent_task.status = TaskStatus.ACTIVE
    store_task(urgent_task, r)

    swapped_out = []
    if sts:
        preempted = sts.preempt(urgent_task, energy_level)
        if preempted:
            swapped_out.append(preempted)
            logger.info(f"PREEMPT: {preempted.title} interrupted by {urgent_task.title}")

    summary = f"Preempted for urgent task: {urgent_task.title}"
    return SwapResult(
        swapped_in=[urgent_task],
        swapped_out=swapped_out,
        delegated=[],
        summary=summary,
    )
