"""Scheduler Kernel Agent.

The brain of Rewind. Receives DisruptionEvent from Disruption Detector,
orchestrates the three-tier scheduling engine (LTS/MTS/STS), queries
Energy Monitor, and emits UpdatedSchedule + DelegationTask messages.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis
from uagents import Agent, Context

from src.config.settings import (
    SCHEDULER_KERNEL_SEED,
    ENERGY_MONITOR_ADDRESS,
    REDIS_URL,
)
from src.models.messages import (
    DisruptionEvent,
    EnergyLevel,
    EnergyQuery,
    UpdatedSchedule,
    ScheduleRequest,
    DelegationTask,
)
from src.models.task import Task, TaskStatus
from src.engine.lts import plan_day, replan_remaining
from src.engine.mts import handle_disruption
from src.engine.sts import ShortTermScheduler
from src.engine.task_buffer import get_active_tasks, store_task
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)

# Default energy when Energy Monitor is unavailable
DEFAULT_ENERGY = EnergyLevel(level=3, confidence=0.5, source="time_based")

# Default profile values (used until Profiler provides real ones)
DEFAULT_PEAK_HOURS = [9, 10, 14, 15]
DEFAULT_ESTIMATION_BIAS = 1.0


# ── Agent Setup ──────────────────────────────────────────────────────────

agent = Agent(
    name="scheduler_kernel",
    seed=SCHEDULER_KERNEL_SEED,
    port=8002,
    endpoint=["http://localhost:8002/submit"],
)

# Shared state
_sts = ShortTermScheduler()
_current_energy = DEFAULT_ENERGY
_peak_hours = DEFAULT_PEAK_HOURS


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _build_schedule_message(trigger: str) -> UpdatedSchedule:
    """Build an UpdatedSchedule message from current STS state."""
    ordered = _sts.get_ordered_schedule(_current_energy.level)
    schedule = []
    for task in ordered:
        schedule.append({
            "task_id": task.task_id,
            "title": task.title,
            "priority": task.priority,
            "estimated_duration": task.estimated_duration,
            "energy_cost": task.energy_cost,
            "status": task.status,
            "deadline": task.deadline,
        })

    return UpdatedSchedule(
        schedule=schedule,
        swaps=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
        trigger=trigger,
    )


def _build_delegation_tasks(tasks: list[Task]) -> list[DelegationTask]:
    """Convert delegatable tasks into DelegationTask messages."""
    delegations = []
    for task in tasks:
        delegations.append(DelegationTask(
            task_id=task.task_id,
            task_type=task.task_type,
            context={
                "title": task.title,
                "description": task.description,
                "tags": task.tags,
            },
            approval_required=True,
            max_cost_fet=0.01,
        ))
    return delegations


# ── Message Handlers ─────────────────────────────────────────────────────

@agent.on_message(DisruptionEvent)
async def handle_disruption_event(ctx: Context, sender: str, event: DisruptionEvent):
    """Handle disruption from Disruption Detector. Core scheduling logic."""
    global _sts
    logger.info(
        f"DisruptionEvent received: severity={event.severity}, "
        f"freed_minutes={event.freed_minutes}, action={event.recommended_action}"
    )

    r = _get_redis()

    # Query Energy Monitor (async, use cached value as fallback)
    try:
        await ctx.send(
            ENERGY_MONITOR_ADDRESS,
            EnergyQuery(
                user_id="default",
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )
    except Exception:
        logger.debug("Energy Monitor unavailable, using cached energy level")

    energy = _current_energy.level

    if event.recommended_action == "reschedule_all":
        # Critical: full replan
        logger.info("CRITICAL disruption — replanning entire day")
        tasks, _sts = plan_day(
            energy_curve=None,
            peak_hours=_peak_hours,
            r=r,
        )
    else:
        # MTS handles swap-in/swap-out
        result = handle_disruption(
            freed_minutes=event.freed_minutes,
            energy_level=energy,
            peak_hours=_peak_hours,
            sts=_sts,
            r=r,
        )
        logger.info(f"MTS result: {result.summary}")

        # Handle delegations
        delegated = result.delegated + _sts.get_delegation_queue()
        if delegated:
            delegation_msgs = _build_delegation_tasks(delegated)
            for d in delegation_msgs:
                logger.info(f"Delegating task {d.task_id} to GhostWorker")
                # In production: await ctx.send(GHOSTWORKER_ADDRESS, d)

    # STS reorder with current energy
    active = get_active_tasks(r)
    _sts.reorder(active)

    # Emit updated schedule
    schedule_msg = _build_schedule_message("disruption")
    logger.info(f"Updated schedule: {len(schedule_msg.schedule)} tasks")
    # In production: push via WebSocket to frontend
    # await ctx.send(FRONTEND_ADDRESS, schedule_msg)


@agent.on_message(EnergyLevel)
async def handle_energy_update(ctx: Context, sender: str, energy: EnergyLevel):
    """Update cached energy level from Energy Monitor."""
    global _current_energy
    _current_energy = energy
    logger.info(f"Energy updated: level={energy.level}, source={energy.source}")

    # Auto-delegate P3 if energy critically low
    if energy.level <= 2:
        delegated = _sts.auto_delegate_p3(energy.level)
        if delegated:
            r = _get_redis()
            for task in delegated:
                store_task(task, r)
            logger.info(f"Auto-delegated {len(delegated)} P3 tasks due to low energy")


@agent.on_message(ScheduleRequest)
async def handle_schedule_request(ctx: Context, sender: str, req: ScheduleRequest):
    """Handle manual scheduling requests."""
    global _sts
    r = _get_redis()

    if req.action == "plan_day":
        hours = req.payload.get("available_hours", 8)
        tasks, _sts = plan_day(
            available_hours=hours,
            peak_hours=_peak_hours,
            r=r,
        )
        logger.info(f"Daily plan created: {len(tasks)} tasks")

    elif req.action == "reoptimize":
        replan_remaining(_sts, _current_energy.level, r)
        logger.info("Schedule reoptimized")

    elif req.action == "add_task":
        task_data = req.payload.get("task")
        if task_data:
            task = Task.from_dict(task_data)
            task.status = TaskStatus.ACTIVE
            store_task(task, r)
            _sts.enqueue(task)
            logger.info(f"Task added: {task.title}")

    schedule_msg = _build_schedule_message(req.action)
    # In production: push to frontend


# ── Startup ──────────────────────────────────────────────────────────────

@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Initialize the scheduling engine on agent startup."""
    logger.info(f"Scheduler Kernel started. Address: {agent.address}")
    logger.info(f"Energy level: {_current_energy.level}/5")

    r = _get_redis()
    active = get_active_tasks(r)
    if active:
        _sts.enqueue_batch(active)
        logger.info(f"Loaded {len(active)} active tasks into STS")
    else:
        logger.info("No active tasks found. Run daily planning to populate.")


# Chat Protocol for ASI:One
async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
    counts = _sts.queue_counts()
    return (
        f"I'm the Scheduler Kernel — the brain of Rewind. "
        f"Current queue: {counts}. "
        f"Energy level: {_current_energy.level}/5. "
        f"I orchestrate LTS (daily planning), MTS (swap engine), and "
        f"STS (MLFQ priority queues) to keep your day on track."
    )

chat_proto = create_chat_protocol(
    "Scheduler Kernel",
    "Optimizes your schedule using OS scheduling theory",
    _chat_handler,
)
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent.run()
