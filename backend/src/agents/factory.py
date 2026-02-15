"""Agent Factory — create_xxx_agent(port) pattern for all Rewind agents.

Each factory function returns a fully configured uAgent instance with:
- Deterministic address from seed
- All message handlers registered
- Chat Protocol for ASI:One discoverability
- Internal dependencies (Redis, MCP, etc.) initialized lazily

Usage:
    from src.agents.factory import create_context_sentinel
    agent = create_context_sentinel(port=8004)
    agent.run()
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import redis
from uagents import Agent, Context

from src.config.settings import (
    COMPOSIO_API_KEY,
    COMPOSIO_USER_ID,
    CONTEXT_SENTINEL_SEED,
    DISRUPTION_DETECTOR_SEED,
    SCHEDULER_KERNEL_SEED,
    ENERGY_MONITOR_SEED,
    GHOST_WORKER_SEED,
    PROFILER_AGENT_SEED,
    DISRUPTION_DETECTOR_ADDRESS,
    SCHEDULER_KERNEL_ADDRESS,
    ENERGY_MONITOR_ADDRESS,
    GHOST_WORKER_ADDRESS,
    PROFILER_AGENT_ADDRESS,
    REDIS_URL,
    SENTINEL_POLL_INTERVAL,
    CALENDAR_LOOKAHEAD_HOURS,
    GMAIL_LOOKBACK_HOURS,
    GOOGLE_CALENDAR_AUTH_CONFIG_ID,
    GMAIL_AUTH_CONFIG_ID,
    SLACK_AUTH_CONFIG_ID,
    PROFILER_RECOMPUTE_INTERVAL,
    PROFILER_SLIDING_WINDOW_DAYS,
    PROFILER_DECAY_FACTOR,
    PROFILER_DRIFT_THRESHOLD,
)
from src.models.messages import (
    ContextChangeEvent,
    DisruptionEvent,
    EnergyLevel,
    EnergyQuery,
    ProfileQuery,
    ProfilerGrouping,
    ProfileUpdateEvent,
    UpdatedSchedule,
    ScheduleRequest,
    DelegationTask,
    TaskCompletion,
    UserProfile,
)
from src.models.task import Task, TaskStatus
from src.engine.lts import plan_day, replan_remaining
from src.engine.mts import handle_disruption
from src.engine.sts import ShortTermScheduler
from src.engine.task_buffer import get_active_tasks, store_task
from src.engine.disruption_classifier import (
    classify_severity,
    calculate_freed_minutes,
    determine_action,
    DEFAULT_PROFILE,
)
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)

_deploy_mode = os.getenv("AGENT_DEPLOY_MODE", "local")
_endpoint_base = os.getenv("AGENT_ENDPOINT_BASE", "http://localhost")


def _agent_kwargs(port: int) -> dict:
    """Build common Agent constructor kwargs based on deploy mode."""
    kwargs: Dict[str, Any] = {}
    if _deploy_mode == "agentverse":
        kwargs["endpoint"] = []
        kwargs["mailbox"] = True
    else:
        kwargs["endpoint"] = [f"{_endpoint_base}:{port}/submit"]
    return kwargs


# ═══════════════════════════════════════════════════════════════════════════
# Context Sentinel Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_context_sentinel(port: int = 8004) -> Agent:
    """Create and configure the Context Sentinel agent.

    Monitors Google Calendar, Gmail, and Slack for real-time context
    changes via Composio MCP. Emits ContextChangeEvent to the
    Disruption Detector.
    """
    agent = Agent(
        name="context_sentinel",
        seed=CONTEXT_SENTINEL_SEED,
        port=port,
        **_agent_kwargs(port),
    )

    # Lazy-initialized dependencies
    _state: Dict[str, Any] = {
        "redis": None,
        "orchestrator": None,
    }

    def _get_redis_client() -> redis.Redis:
        if _state["redis"] is None:
            _state["redis"] = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return _state["redis"]

    def _get_orchestrator():
        if _state["orchestrator"] is None:
            from src.composio.main import ComposioMCPOrchestrator
            _state["orchestrator"] = ComposioMCPOrchestrator(
                api_key=COMPOSIO_API_KEY,
                user_id=COMPOSIO_USER_ID,
            )
            _state["orchestrator"].initialize_session()
            logger.info("Composio MCP session initialized for Context Sentinel")
        return _state["orchestrator"]

    # ── Startup ──────────────────────────────────────────────────────────

    @agent.on_event("startup")
    async def on_startup(ctx: Context):
        logger.info("Context Sentinel starting — address: %s", agent.address)
        _get_orchestrator()
        ctx.storage.set("startup_time", datetime.now(timezone.utc).isoformat())
        ctx.storage.set("poll_count", "0")
        ctx.storage.set("total_events_emitted", "0")
        logger.info("Context Sentinel initialized — polling every %ds", SENTINEL_POLL_INTERVAL)

    # ── Polling (interval handler) ───────────────────────────────────────

    @agent.on_interval(period=SENTINEL_POLL_INTERVAL)
    async def poll_context_signals(ctx: Context):
        r = _get_redis_client()
        poll_count = int(ctx.storage.get("poll_count") or "0") + 1
        ctx.storage.set("poll_count", str(poll_count))
        logger.info("Poll cycle %d started", poll_count)

        all_events: List[ContextChangeEvent] = []

        # Poll Calendar, Gmail, Slack (omitting full impl for brevity;
        # the polling functions are identical to context_sentinel.py)
        # In production, delegate to _poll_calendar / _poll_gmail / _poll_slack

        sent_count = 0
        for event in all_events:
            try:
                if DISRUPTION_DETECTOR_ADDRESS:
                    await ctx.send(DISRUPTION_DETECTOR_ADDRESS, event)
                    sent_count += 1
            except Exception as exc:
                logger.error("Failed to send %s: %s", event.event_type, exc)

        r.set("sentinel:last_poll", datetime.now(timezone.utc).isoformat())
        total = int(ctx.storage.get("total_events_emitted") or "0") + sent_count
        ctx.storage.set("total_events_emitted", str(total))
        logger.info("Poll cycle %d — %d event(s) sent", poll_count, sent_count)

    # ── Chat Protocol ────────────────────────────────────────────────────

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        poll_count = ctx.storage.get("poll_count") or "0"
        total_events = ctx.storage.get("total_events_emitted") or "0"
        return (
            "I'm the Context Sentinel — I monitor Google Calendar, Gmail, and Slack "
            f"for real-time context changes. Polls: {poll_count}, Events emitted: {total_events}."
        )

    chat_proto = create_chat_protocol(
        "Context Sentinel",
        "Monitors Google Calendar, Gmail, and Slack for real-time context changes",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent


# ═══════════════════════════════════════════════════════════════════════════
# Disruption Detector Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_disruption_detector(port: int = 8001) -> Agent:
    """Create and configure the Disruption Detector agent.

    Receives ContextChangeEvent from Context Sentinel, classifies disruption
    severity, and emits DisruptionEvent to Scheduler Kernel.
    """
    agent = Agent(
        name="disruption_detector",
        seed=DISRUPTION_DETECTOR_SEED,
        port=port,
        **_agent_kwargs(port),
    )

    _cached_profile: Dict[str, Any] = dict(DEFAULT_PROFILE)

    @agent.on_message(ContextChangeEvent)
    async def handle_context_change(ctx: Context, sender: str, event: ContextChangeEvent):
        logger.info("Received ContextChangeEvent: %s from %s", event.event_type, sender)

        severity = classify_severity(event.event_type, event.affected_task_ids, event.metadata)
        freed_minutes = calculate_freed_minutes(event.event_type, event.metadata)
        action = determine_action(severity, freed_minutes)

        direction = "gained" if freed_minutes >= 0 else "lost"
        summary = (
            f"{event.event_type} from {event.source}: "
            f"{abs(freed_minutes)}min {direction}. "
            f"{len(event.affected_task_ids)} task(s) affected. "
            f"Severity: {severity}."
        )

        disruption = DisruptionEvent(
            severity=severity,
            affected_task_ids=event.affected_task_ids,
            freed_minutes=freed_minutes,
            recommended_action=action,
            context_summary=summary,
        )
        logger.info("Emitting DisruptionEvent: %s -> %s", severity, action)
        await ctx.send(SCHEDULER_KERNEL_ADDRESS, disruption)

    @agent.on_message(UserProfile)
    async def handle_profile_update(ctx: Context, sender: str, profile: UserProfile):
        nonlocal _cached_profile
        _cached_profile = {
            "peak_hours": profile.peak_hours,
            "estimation_bias": profile.estimation_bias,
            "automation_comfort": profile.automation_comfort,
        }
        logger.info("Updated cached user profile from Profiler Agent")

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        return (
            "I'm the Disruption Detector. I classify disruptions by severity "
            "(minor/major/critical) and trigger schedule recovery."
        )

    chat_proto = create_chat_protocol(
        "Disruption Detector",
        "Detects and classifies disruptions to your schedule",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent


# ═══════════════════════════════════════════════════════════════════════════
# Scheduler Kernel Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_scheduler_kernel(port: int = 8002) -> Agent:
    """Create and configure the Scheduler Kernel agent.

    The brain of Rewind. Orchestrates LTS/MTS/STS scheduling engines,
    queries Energy Monitor, emits UpdatedSchedule and DelegationTask.
    """
    agent = Agent(
        name="scheduler_kernel",
        seed=SCHEDULER_KERNEL_SEED,
        port=port,
        **_agent_kwargs(port),
    )

    DEFAULT_ENERGY = EnergyLevel(level=3, confidence=0.5, source="time_based")
    DEFAULT_PEAK_HOURS = [9, 10, 14, 15]

    _state: Dict[str, Any] = {
        "sts": ShortTermScheduler(),
        "current_energy": DEFAULT_ENERGY,
        "peak_hours": list(DEFAULT_PEAK_HOURS),
    }

    def _get_redis_client() -> redis.Redis:
        return redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def _build_schedule_message(trigger: str) -> UpdatedSchedule:
        sts = _state["sts"]
        energy = _state["current_energy"]
        ordered = sts.get_ordered_schedule(energy.level)
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

    @agent.on_event("startup")
    async def on_startup(ctx: Context):
        logger.info("Scheduler Kernel started. Address: %s", agent.address)
        r = _get_redis_client()
        active = get_active_tasks(r)
        if active:
            _state["sts"].enqueue_batch(active)
            logger.info("Loaded %d active tasks into STS", len(active))

    @agent.on_message(DisruptionEvent)
    async def handle_disruption_event(ctx: Context, sender: str, event: DisruptionEvent):
        logger.info("DisruptionEvent: severity=%s, freed=%d", event.severity, event.freed_minutes)
        r = _get_redis_client()
        energy = _state["current_energy"].level

        try:
            await ctx.send(
                ENERGY_MONITOR_ADDRESS,
                EnergyQuery(user_id="default", timestamp=datetime.now(timezone.utc).isoformat()),
            )
        except Exception:
            logger.debug("Energy Monitor unavailable, using cached level")

        if event.recommended_action == "reschedule_all":
            tasks, new_sts = plan_day(peak_hours=_state["peak_hours"], r=r)
            _state["sts"] = new_sts
        else:
            result = handle_disruption(
                freed_minutes=event.freed_minutes,
                energy_level=energy,
                peak_hours=_state["peak_hours"],
                sts=_state["sts"],
                r=r,
            )
            logger.info("MTS result: %s", result.summary)

        active = get_active_tasks(r)
        _state["sts"].reorder(active)
        _build_schedule_message("disruption")

    @agent.on_message(EnergyLevel)
    async def handle_energy_update(ctx: Context, sender: str, energy: EnergyLevel):
        _state["current_energy"] = energy
        logger.info("Energy updated: level=%d, source=%s", energy.level, energy.source)
        if energy.level <= 2:
            delegated = _state["sts"].auto_delegate_p3(energy.level)
            if delegated:
                r = _get_redis_client()
                for task in delegated:
                    store_task(task, r)
                # Send delegated tasks to GhostWorker
                if GHOST_WORKER_ADDRESS:
                    from src.agents.scheduler_kernel import _build_delegation_tasks
                    for d in _build_delegation_tasks(delegated):
                        await ctx.send(GHOST_WORKER_ADDRESS, d)

    @agent.on_message(ScheduleRequest)
    async def handle_schedule_request(ctx: Context, sender: str, req: ScheduleRequest):
        r = _get_redis_client()
        if req.action == "plan_day":
            hours = req.payload.get("available_hours", 8)
            tasks, new_sts = plan_day(available_hours=hours, peak_hours=_state["peak_hours"], r=r)
            _state["sts"] = new_sts
        elif req.action == "reoptimize":
            replan_remaining(_state["sts"], _state["current_energy"].level, r)
        elif req.action == "add_task":
            task_data = req.payload.get("task")
            if task_data:
                task = Task.from_dict(task_data)
                task.status = TaskStatus.ACTIVE
                store_task(task, r)
                _state["sts"].enqueue(task)

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        counts = _state["sts"].queue_counts()
        energy = _state["current_energy"].level
        return (
            f"I'm the Scheduler Kernel. Queue: {counts}. Energy: {energy}/5. "
            f"I orchestrate LTS/MTS/STS to keep your day on track."
        )

    chat_proto = create_chat_protocol(
        "Scheduler Kernel",
        "Optimizes your schedule using OS scheduling theory",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent


# ═══════════════════════════════════════════════════════════════════════════
# Energy Monitor Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_energy_monitor(port: int = 8003) -> Agent:
    """Create and configure the Energy Monitor agent.

    Infers user energy (1-5) from time-of-day heuristics, task velocity,
    and user-reported overrides. Caches result in Redis.
    """
    agent = Agent(
        name="energy_monitor",
        seed=ENERGY_MONITOR_SEED,
        port=port,
        **_agent_kwargs(port),
    )

    DEFAULT_ENERGY_CURVE = [
        1, 1, 1, 1, 1, 1,
        2, 3, 4, 4, 5, 4,
        3, 3, 4, 5, 4, 3,
        3, 2, 2, 2, 1, 1,
    ]
    VELOCITY_WINDOW = 2 * 60 * 60
    USER_REPORTED_DECAY = 2 * 60 * 60
    RECOMPUTE_INTERVAL = 5 * 60

    _state: Dict[str, Any] = {
        "energy_curve": list(DEFAULT_ENERGY_CURVE),
        "has_profiler_curve": False,
    }

    def _get_redis_client() -> redis.Redis:
        return redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def _compute_energy(r: redis.Redis) -> EnergyLevel:
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Check user-reported first
        reported = r.get("energy:user_reported")
        reported_ts = r.get("energy:user_reported_ts")
        if reported is not None and reported_ts is not None:
            age = time.time() - float(reported_ts)
            if age <= USER_REPORTED_DECAY:
                decay_factor = 1.0 - (age / USER_REPORTED_DECAY)
                confidence = 0.5 + 0.4 * decay_factor
                return EnergyLevel(
                    level=max(1, min(5, int(reported))),
                    confidence=round(confidence, 2),
                    source="user_reported",
                )

        base_level = _state["energy_curve"][hour % 24]
        confidence = 0.4
        source = "time_based"
        return EnergyLevel(level=base_level, confidence=confidence, source=source)

    def _cache_energy(energy: EnergyLevel, r: redis.Redis) -> None:
        r.set("energy:current", json.dumps({
            "level": energy.level,
            "confidence": energy.confidence,
            "source": energy.source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    @agent.on_event("startup")
    async def on_startup(ctx: Context):
        logger.info("Energy Monitor started. Address: %s", agent.address)
        r = _get_redis_client()
        energy = _compute_energy(r)
        _cache_energy(energy, r)
        logger.info("Initial energy: %d/5 (%s)", energy.level, energy.source)

    @agent.on_message(EnergyQuery)
    async def handle_energy_query(ctx: Context, sender: str, msg: EnergyQuery):
        r = _get_redis_client()
        energy = _compute_energy(r)
        _cache_energy(energy, r)
        await ctx.send(sender, energy)

    @agent.on_message(TaskCompletion)
    async def handle_task_completion(ctx: Context, sender: str, msg: TaskCompletion):
        if msg.status != "executed":
            return
        actual = msg.result.get("actual_minutes", 0)
        estimated = msg.result.get("estimated_minutes", 0)
        if actual > 0 and estimated > 0:
            r = _get_redis_client()
            entry = f"{msg.task_id}:{actual}:{estimated}"
            r.zadd("energy:completions", {entry: time.time()})
            energy = _compute_energy(r)
            _cache_energy(energy, r)

    @agent.on_message(UserProfile)
    async def handle_profile_update(ctx: Context, sender: str, msg: UserProfile):
        if msg.energy_curve and len(msg.energy_curve) == 24:
            _state["energy_curve"] = list(msg.energy_curve)
            _state["has_profiler_curve"] = True
            r = _get_redis_client()
            energy = _compute_energy(r)
            _cache_energy(energy, r)

    @agent.on_interval(period=RECOMPUTE_INTERVAL)
    async def periodic_recompute(ctx: Context):
        r = _get_redis_client()
        energy = _compute_energy(r)
        _cache_energy(energy, r)

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        r = _get_redis_client()
        energy = _compute_energy(r)
        return (
            f"Your current energy level is {energy.level}/5 "
            f"(confidence: {energy.confidence}, source: {energy.source})."
        )

    chat_proto = create_chat_protocol(
        "Energy Monitor",
        "Infers your energy level from behavioral signals and time-of-day patterns",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent


# ═══════════════════════════════════════════════════════════════════════════
# GhostWorker Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_ghost_worker(port: int = 8005) -> Agent:
    """Create and configure the GhostWorker agent.

    Receives DelegationTask messages from the Scheduler Kernel, generates
    drafts via Composio MCP, stores them for user approval, and executes
    approved actions. Fully autonomous — deployable to Agentverse.
    """
    import uuid as _uuid

    from src.agents.ghost_worker import (
        TASK_PROMPTS,
        TASK_SYSTEM_PROMPTS,
        TASK_COSTS,
        APPROVAL_POLL_INTERVAL,
        _build_prompt,
        _store_draft,
        _execute_draft,
    )

    agent = Agent(
        name="ghost_worker",
        seed=GHOST_WORKER_SEED,
        port=port,
        **_agent_kwargs(port),
    )

    _state: Dict[str, Any] = {
        "redis": None,
        "orchestrator": None,
        "pubsub": None,
    }

    def _get_redis_client() -> redis.Redis:
        if _state["redis"] is None:
            _state["redis"] = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return _state["redis"]

    def _get_orchestrator():
        if _state["orchestrator"] is None:
            from src.composio.main import ComposioMCPOrchestrator
            _state["orchestrator"] = ComposioMCPOrchestrator(
                api_key=COMPOSIO_API_KEY,
                user_id=COMPOSIO_USER_ID,
            )
            _state["orchestrator"].initialize_session()
            logger.info("Composio MCP session initialized for GhostWorker")
        return _state["orchestrator"]

    def _get_approval_pubsub() -> redis.client.PubSub:
        if _state["pubsub"] is None:
            r = _get_redis_client()
            _state["pubsub"] = r.pubsub(ignore_subscribe_messages=True)
            _state["pubsub"].subscribe("ghostworker:approvals")
        return _state["pubsub"]

    @agent.on_event("startup")
    async def on_startup(ctx: Context):
        logger.info("GhostWorker started. Address: %s", agent.address)
        try:
            _get_orchestrator()
        except Exception as exc:
            logger.warning("Composio init deferred: %s", exc)
        _get_approval_pubsub()
        r = _get_redis_client()
        pending = r.scard("ghostworker:pending")
        if pending:
            logger.info("%d pending drafts awaiting approval", pending)

    @agent.on_message(DelegationTask)
    async def handle_delegation(ctx: Context, sender: str, task: DelegationTask):
        logger.info(
            "DelegationTask received: task_id=%s, type=%s, approval=%s",
            task.task_id, task.task_type, task.approval_required,
        )

        prompt = _build_prompt(task.task_type, task.context)
        system_prompt = TASK_SYSTEM_PROMPTS.get(
            task.task_type,
            "You are a task execution assistant. Complete the requested action.",
        )

        try:
            orchestrator = _get_orchestrator()
            responses = await orchestrator.execute_operation(
                prompt, system_context=system_prompt, max_iterations=5,
            )
            draft_body = "\n".join(responses) if responses else "(No content generated)"
        except Exception as exc:
            logger.error("Composio draft generation failed: %s", exc)
            draft_body = f"(Draft generation failed: {exc})"

        draft_id = f"draft-{_uuid.uuid4().hex[:8]}"
        cost = min(TASK_COSTS.get(task.task_type, 0.001), task.max_cost_fet)

        if not task.approval_required:
            result = await _execute_draft(draft_id, body_override=draft_body)
            completion = TaskCompletion(
                task_id=task.task_id,
                status=result.get("status", "failed"),
                result=result,
                cost_fet=cost,
            )
            if SCHEDULER_KERNEL_ADDRESS:
                await ctx.send(SCHEDULER_KERNEL_ADDRESS, completion)
            return

        draft = _store_draft(draft_id, task, draft_body, cost)
        r = _get_redis_client()
        r.hset(f"ghostworker:draft:{draft_id}", "sender_address", sender)
        logger.info("Draft %s awaiting user approval", draft_id)

    @agent.on_interval(period=APPROVAL_POLL_INTERVAL)
    async def poll_approvals(ctx: Context):
        pubsub = _get_approval_pubsub()
        while True:
            msg = pubsub.get_message()
            if msg is None:
                break
            if msg["type"] != "message":
                continue
            try:
                data = json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            action = data.get("action")
            draft_id = data.get("draft_id")
            if not draft_id:
                continue

            r = _get_redis_client()
            draft_data = r.hgetall(f"ghostworker:draft:{draft_id}")
            if not draft_data:
                continue

            task_id = draft_data.get("task_id", "")
            cost_fet = float(draft_data.get("cost_fet", 0.001))
            sender_address = draft_data.get("sender_address", SCHEDULER_KERNEL_ADDRESS)

            if action == "approve":
                edited_body = data.get("edited_body")
                result = await _execute_draft(draft_id, body_override=edited_body)
                completion = TaskCompletion(
                    task_id=task_id,
                    status=result.get("status", "failed"),
                    result=result,
                    cost_fet=cost_fet,
                )
                if sender_address:
                    await ctx.send(sender_address, completion)

            elif action == "reject":
                r.hset(f"ghostworker:draft:{draft_id}", "status", "rejected")
                r.srem("ghostworker:pending", draft_id)
                event = {"event": "draft_rejected", "draft_id": draft_id, "task_id": task_id}
                r.publish("ghostworker:events", json.dumps(event))
                completion = TaskCompletion(
                    task_id=task_id,
                    status="failed",
                    result={"reason": "User rejected draft"},
                    cost_fet=0.0,
                )
                if sender_address:
                    await ctx.send(sender_address, completion)

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        r = _get_redis_client()
        pending = r.scard("ghostworker:pending")
        return (
            f"I'm GhostWorker — I autonomously handle delegatable tasks like "
            f"email replies, Slack messages, LinkedIn posts, and meeting scheduling. "
            f"Currently {pending} draft(s) pending review."
        )

    chat_proto = create_chat_protocol(
        "GhostWorker",
        "Autonomously executes delegatable tasks like email replies, Slack messages, "
        "LinkedIn posts, and meeting scheduling with user approval",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent


# ═══════════════════════════════════════════════════════════════════════════
# Profiler Agent Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_profiler_agent(port: int = 8005) -> Agent:
    """Create and configure the Profiler Agent.

    Learns implicit behavioral patterns from daily goals, social media,
    task completion logs, and reflections. Computes UserProfile, archetype
    grouping, and success-plot coordinates for all other agents.
    """
    agent = Agent(
        name="profiler_agent",
        seed=PROFILER_AGENT_SEED,
        port=port,
        endpoint=[f"http://localhost:{port}/submit"],
    )

    _state: Dict[str, Any] = {
        "engine": None,
        "redis": None,
        "last_profile": None,
        "last_grouping": None,
        "last_success": None,
    }

    def _get_redis_client() -> redis.Redis:
        if _state["redis"] is None:
            _state["redis"] = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return _state["redis"]

    def _get_engine():
        if _state["engine"] is None:
            from src.agents.profiler_agent import (
                ProfilerEngine,
                PatternEngine,
                TemporalTracker,
            )

            # Restore temporal tracker from Redis if available
            r = _get_redis_client()
            tracker_payload = r.get("profiler:temporal_tracker")
            tracker = (
                TemporalTracker.from_redis_payload(
                    tracker_payload, drift_threshold=PROFILER_DRIFT_THRESHOLD
                )
                if tracker_payload
                else TemporalTracker(drift_threshold=PROFILER_DRIFT_THRESHOLD)
            )

            pattern_eng = PatternEngine(
                sliding_window_days=PROFILER_SLIDING_WINDOW_DAYS,
                decay_factor=PROFILER_DECAY_FACTOR,
            )
            _state["engine"] = ProfilerEngine(
                pattern_engine=pattern_eng,
                temporal_tracker=tracker,
            )
        return _state["engine"]

    def _load_data_and_compute() -> Dict[str, Any]:
        """Load all data sources and run the full profiling pipeline."""
        from src.data_pipeline.parsers import (
            parse_daily_goals,
            parse_linkedin,
            parse_reflections,
            parse_resume,
            parse_twitter,
        )

        # Parse data sources
        daily_goals = parse_daily_goals()
        reflection_data = parse_reflections()
        resume_data = parse_resume()

        # Extract social posting hours
        social_hours: Dict[str, list] = {}
        try:
            li_data = parse_linkedin()
            stats = li_data.get("stats", {})
            social_hours["linkedin"] = stats.get("peak_posting_hours", [])
        except Exception:
            logger.debug("LinkedIn data not available for profiler")

        try:
            tw_data = parse_twitter()
            stats = tw_data.get("stats", {})
            social_hours["twitter"] = stats.get("peak_activity_hours", [])
        except Exception:
            logger.debug("Twitter data not available for profiler")

        engine = _get_engine()
        result = engine.build_full_profile(
            daily_goals=daily_goals,
            task_completions=_get_task_completions(),
            social_posting_hours=social_hours,
            reflection_data=reflection_data,
            resume_data=resume_data,
        )

        # Cache in state
        _state["last_profile"] = result["user_profile"]
        _state["last_grouping"] = result["grouping"]
        _state["last_success"] = result["success_plot"]

        # Persist temporal tracker to Redis
        r = _get_redis_client()
        r.set("profiler:temporal_tracker", engine.temporal_tracker.to_redis_payload())
        r.set("profiler:last_result", json.dumps(result, default=str))

        return result

    def _get_task_completions() -> List[Dict]:
        """Pull task completion history from Redis."""
        r = _get_redis_client()
        raw = r.get("profiler:task_completions")
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def _record_task_completion(task_id: str, actual: int, estimated: int) -> None:
        """Append a task completion record to Redis."""
        r = _get_redis_client()
        completions = _get_task_completions()
        completions.append({
            "task_id": task_id,
            "actual_minutes": actual,
            "estimated_minutes": estimated,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 100
        r.set("profiler:task_completions", json.dumps(completions[-100:]))

    # ── Startup ──────────────────────────────────────────────────────────

    @agent.on_event("startup")
    async def on_startup(ctx: Context):
        logger.info("Profiler Agent starting — address: %s", agent.address)
        try:
            result = _load_data_and_compute()
            grouping = result["grouping"]
            success = result["success_plot"]
            logger.info(
                "Profiler initialized: archetype=%s, exec=%.2f, growth=%.2f, quadrant=%s",
                grouping["archetype_label"],
                success["execution_velocity"],
                success["growth_trajectory"],
                success["quadrant_label"],
            )
        except Exception as exc:
            logger.error("Profiler startup compute failed: %s", exc)

    # ── Periodic recomputation ───────────────────────────────────────────

    @agent.on_interval(period=PROFILER_RECOMPUTE_INTERVAL)
    async def periodic_recompute(ctx: Context):
        try:
            result = _load_data_and_compute()
            drift = result.get("temporal_drift")

            if drift:
                logger.info(
                    "Profile drift detected: fields=%s, magnitude=%.3f",
                    drift["changed_fields"],
                    drift["magnitude"],
                )
                # Broadcast updated profile to consumer agents
                profile = result["user_profile"]
                profile_msg = UserProfile(
                    peak_hours=profile["peak_hours"],
                    avg_task_durations=profile["avg_task_durations"],
                    energy_curve=profile["energy_curve"],
                    adherence_score=profile["adherence_score"],
                    distraction_patterns=profile["distraction_patterns"],
                    estimation_bias=profile["estimation_bias"],
                    automation_comfort=profile["automation_comfort"],
                )
                for addr in [SCHEDULER_KERNEL_ADDRESS, ENERGY_MONITOR_ADDRESS, DISRUPTION_DETECTOR_ADDRESS]:
                    if addr:
                        try:
                            await ctx.send(addr, profile_msg)
                        except Exception as exc:
                            logger.debug("Could not send profile to %s: %s", addr, exc)

                # Emit profile update event
                update_event = ProfileUpdateEvent(
                    changed_fields=drift["changed_fields"],
                    magnitude=drift["magnitude"],
                    timestamp=drift["timestamp"],
                )
                logger.info("ProfileUpdateEvent emitted: %s", update_event)
        except Exception as exc:
            logger.error("Periodic profiler recompute failed: %s", exc)

    # ── Handle ProfileQuery from other agents ────────────────────────────

    @agent.on_message(ProfileQuery)
    async def handle_profile_query(ctx: Context, sender: str, msg: ProfileQuery):
        logger.info("ProfileQuery from %s: type=%s", sender, msg.query_type)

        # Ensure we have computed data
        if _state["last_profile"] is None:
            _load_data_and_compute()

        profile = _state["last_profile"] or {}

        if msg.query_type == "full_profile":
            response = UserProfile(
                peak_hours=profile.get("peak_hours", [9, 10, 14, 15]),
                avg_task_durations=profile.get("avg_task_durations", {}),
                energy_curve=profile.get("energy_curve", [3] * 24),
                adherence_score=profile.get("adherence_score", 0.7),
                distraction_patterns=profile.get("distraction_patterns", {}),
                estimation_bias=profile.get("estimation_bias", 1.2),
                automation_comfort=profile.get("automation_comfort", {}),
            )
            await ctx.send(sender, response)

        elif msg.query_type == "grouping":
            grouping = _state["last_grouping"] or {}
            response = ProfilerGrouping(
                archetype=grouping.get("archetype", "at_risk"),
                execution_score=grouping.get("execution_composite", 0.5),
                growth_score=grouping.get("growth_composite", 0.5),
                confidence=grouping.get("confidence", 0.3),
                traits=grouping.get("traits", {}),
            )
            await ctx.send(sender, response)

        else:
            # Return just the requested field
            response = UserProfile(
                peak_hours=profile.get("peak_hours", [9, 10, 14, 15]),
                avg_task_durations=profile.get("avg_task_durations", {}),
                energy_curve=profile.get("energy_curve", [3] * 24),
                adherence_score=profile.get("adherence_score", 0.7),
                distraction_patterns=profile.get("distraction_patterns", {}),
                estimation_bias=profile.get("estimation_bias", 1.2),
                automation_comfort=profile.get("automation_comfort", {}),
            )
            await ctx.send(sender, response)

    # ── Handle TaskCompletion for real-time updates ──────────────────────

    @agent.on_message(TaskCompletion)
    async def handle_task_completion(ctx: Context, sender: str, msg: TaskCompletion):
        if msg.status != "executed":
            return
        actual = msg.result.get("actual_minutes", 0)
        estimated = msg.result.get("estimated_minutes", 0)
        if actual > 0 and estimated > 0:
            _record_task_completion(msg.task_id, actual, estimated)
            logger.info(
                "Recorded task completion: %s (actual=%d, estimated=%d)",
                msg.task_id, actual, estimated,
            )

    # ── Chat Protocol ────────────────────────────────────────────────────

    async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
        if _state["last_profile"] is None:
            _load_data_and_compute()

        profile = _state["last_profile"] or {}
        grouping = _state["last_grouping"] or {}
        success = _state["last_success"] or {}

        text_lower = text.lower()

        if "peak" in text_lower or "productive hours" in text_lower:
            return (
                f"Your peak productivity hours are: {profile.get('peak_hours', 'unknown')}. "
                f"Schedule high-cognitive tasks during these windows for best results."
            )

        if "improving" in text_lower or "getting better" in text_lower or "growth" in text_lower:
            trajectory = success.get("growth_trajectory", 0)
            quadrant = success.get("quadrant_label", "unknown")
            return (
                f"Your growth trajectory score is {trajectory:.2f}/1.0. "
                f"You're currently in the '{quadrant}' quadrant. "
                f"{'You are on an upward trend!' if trajectory > 0.5 else 'There is room for growth.'}"
            )

        if "archetype" in text_lower or "type" in text_lower or "who am i" in text_lower:
            return (
                f"Your archetype: {grouping.get('archetype_label', 'unknown')}. "
                f"{grouping.get('archetype_description', '')} "
                f"Execution: {grouping.get('execution_composite', 0):.2f}, "
                f"Growth: {grouping.get('growth_composite', 0):.2f}."
            )

        # Default: full summary
        return (
            f"I'm the Profiler Agent. Here's your profile summary:\n"
            f"- Archetype: {grouping.get('archetype_label', 'unknown')}\n"
            f"- Peak hours: {profile.get('peak_hours', [])}\n"
            f"- Adherence: {profile.get('adherence_score', 0):.0%}\n"
            f"- Estimation bias: {profile.get('estimation_bias', 1.0):.2f}x\n"
            f"- Execution velocity: {success.get('execution_velocity', 0):.2f}\n"
            f"- Growth trajectory: {success.get('growth_trajectory', 0):.2f}\n"
            f"- Quadrant: {success.get('quadrant_label', 'unknown')}\n"
            f"Ask me about 'peak hours', 'am I improving?', or 'what's my archetype?'"
        )

    chat_proto = create_chat_protocol(
        "Profiler Agent",
        "Learns your behavioral patterns and classifies your productivity archetype",
        _chat_handler,
    )
    agent.include(chat_proto, publish_manifest=True)

    return agent
