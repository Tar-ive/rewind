"""FastAPI server bridging the scheduling engine to the frontend.

WebSocket for real-time schedule updates + REST endpoints for
triggering actions and querying state.

Integrations:
- Composio: Gmail, Google Calendar, LinkedIn via /api/email/*, /api/calendar/*, /api/auth/*
- Profiler: Full profiler intelligence via /api/profile/*
- Schedule Intelligence: How profiler drives LTS/STS via /api/schedule/intelligence
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config.settings import REDIS_URL, TASK_BUCKET_COUNT
from src.models.task import Task, TaskStatus
from src.engine.task_buffer import get_active_tasks, get_backlog_tasks, store_task
from src.engine.lts import plan_day
from src.engine.mts import handle_disruption
from src.engine.sts import ShortTermScheduler
from src.engine.disruption_classifier import (
    classify_severity,
    calculate_freed_minutes,
    determine_action,
)
from src.services.composio_service import get_composio_service
from src.agents.profiler_agent import ProfilerEngine

logger = logging.getLogger(__name__)

app = FastAPI(title="Rewind", description="The Intelligent Life Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared State ─────────────────────────────────────────────────────────

_sts = ShortTermScheduler()
_energy_level = 3
_peak_hours = [9, 10, 14, 15]

PRIORITY_MAP = {0: "P0", 1: "P1", 2: "P2", 3: "P3"}
STATUS_MAP = {
    TaskStatus.ACTIVE: "scheduled",
    TaskStatus.IN_PROGRESS: "in_progress",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.DELEGATED: "delegated",
    TaskStatus.BACKLOG: "buffered",
    TaskStatus.SWAPPED_OUT: "buffered",
}


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _task_to_frontend(task: Task) -> dict:
    """Convert backend Task to frontend Task format."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Use preferred_start for start_time if available, otherwise use a placeholder
    start_time = task.preferred_start or f"{today}T09:00:00"
    try:
        start_dt = datetime.fromisoformat(start_time)
    except (ValueError, TypeError):
        start_dt = datetime.fromisoformat(f"{today}T09:00:00")

    from datetime import timedelta
    end_dt = start_dt + timedelta(minutes=task.estimated_duration)

    automatable_types = {"email_reply", "slack_message", "uber_book",
                         "cancel_appointment", "doc_update", "meeting_reschedule"}

    return {
        "id": task.task_id,
        "title": task.title,
        "description": task.description,
        "priority": PRIORITY_MAP.get(task.priority, "P2"),
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "energy_cost": task.energy_cost,
        "estimated_duration": task.estimated_duration,
        "status": STATUS_MAP.get(task.status, "scheduled"),
        "delegatable": task.task_type in automatable_types,
        "task_type": task.task_type if task.task_type != "general" else None,
    }


def _build_ws_message(msg_type: str, payload: dict) -> str:
    """Build a JSON WebSocket message matching frontend WSMessage format."""
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── WebSocket Manager ────────────────────────────────────────────────────

class ConnectionManager:
    """WebSocket connection manager with heartbeat and agent activity support."""

    HEARTBEAT_INTERVAL = 30  # seconds between pings

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")
        # Start heartbeat if this is the first connection
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")
        # Stop heartbeat if no connections remain
        if not self._connections and self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

    async def broadcast(self, message: str):
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast_agent_activity(
        self,
        agent_name: str,
        message: str,
        activity_type: str = "info",
    ):
        """Broadcast an agent_activity event to all connected clients.

        Args:
            agent_name: Which agent produced this activity (e.g. "Context Sentinel").
            message: Human-readable description of what happened.
            activity_type: One of info | disruption | swap | delegation | ghostworker.
        """
        msg = _build_ws_message("agent_activity", {
            "agent": agent_name,
            "message": message,
            "type": activity_type,
        })
        await self.broadcast(msg)

    async def _heartbeat_loop(self):
        """Send periodic ping frames to detect dead connections."""
        try:
            while self._connections:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                disconnected = []
                for ws in self._connections:
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    if ws in self._connections:
                        self._connections.remove(ws)
                        logger.info("Heartbeat: removed dead connection")
        except asyncio.CancelledError:
            pass

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ── WebSocket Endpoint ───────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send initial schedule on connect
        r = _get_redis()
        active = get_active_tasks(r)
        frontend_tasks = [_task_to_frontend(t) for t in active]

        initial_msg = _build_ws_message("updated_schedule", {
            "tasks": frontend_tasks,
            "swaps": [],
            "energy": {"level": _energy_level, "confidence": 0.5, "source": "time_based"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await ws.send_text(initial_msg)

        # Keep connection alive, listen for client messages
        while True:
            data = await ws.receive_text()
            # Client can send commands (future: voice commands, manual triggers)
            try:
                msg = json.loads(data)
                logger.info(f"Client message: {msg}")
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── REST Endpoints ───────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    r = _get_redis()
    try:
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ok",
        "redis": redis_ok,
        "ws_connections": manager.count,
        "sts_queue": _sts.queue_counts(),
        "energy_level": _energy_level,
    }


@app.get("/api/schedule")
async def get_schedule():
    """Get current active schedule."""
    r = _get_redis()
    active = get_active_tasks(r)
    return {
        "tasks": [_task_to_frontend(t) for t in active],
        "energy": {"level": _energy_level, "confidence": 0.5, "source": "time_based"},
        "queue_counts": _sts.queue_counts(),
    }


class PlanDayRequest(BaseModel):
    available_hours: int = 8


@app.post("/api/schedule/plan-day")
async def trigger_plan_day(req: PlanDayRequest):
    """Trigger LTS daily planning."""
    global _sts
    r = _get_redis()

    tasks, _sts = plan_day(
        available_hours=req.available_hours,
        peak_hours=_peak_hours,
        r=r,
    )

    frontend_tasks = [_task_to_frontend(t) for t in tasks]

    # Broadcast to all connected clients
    msg = _build_ws_message("updated_schedule", {
        "tasks": frontend_tasks,
        "swaps": [],
        "energy": {"level": _energy_level, "confidence": 0.5, "source": "time_based"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await manager.broadcast(msg)

    return {"planned": len(tasks), "tasks": frontend_tasks}


class DisruptionRequest(BaseModel):
    event_type: str = "meeting_overrun"  # meeting_overrun | meeting_ended_early | cancelled_meeting | new_email
    source: str = "google_calendar"
    affected_task_ids: list[str] = []
    freed_minutes: Optional[int] = None  # override auto-calculation
    lost_minutes: Optional[int] = None   # convenience: sets freed_minutes negative
    metadata: dict = {}


@app.post("/api/disruption")
async def simulate_disruption(req: DisruptionRequest):
    """Simulate a disruption and run the full pipeline.

    This is the demo endpoint: trigger it to show agents coordinating in real-time.
    """
    global _sts
    r = _get_redis()

    # Build metadata for classification
    meta = dict(req.metadata)
    if req.lost_minutes:
        meta["lost_minutes"] = req.lost_minutes
    if req.freed_minutes and req.freed_minutes > 0:
        meta["freed_minutes"] = req.freed_minutes

    # Step 1: Disruption Detector classifies
    severity = classify_severity(req.event_type, req.affected_task_ids, meta)
    freed_minutes = (
        req.freed_minutes if req.freed_minutes is not None
        else calculate_freed_minutes(req.event_type, meta)
    )
    if req.lost_minutes:
        freed_minutes = -abs(req.lost_minutes)
    action = determine_action(severity, freed_minutes)

    direction = "gained" if freed_minutes >= 0 else "lost"
    summary = (
        f"{req.event_type} from {req.source}: "
        f"{abs(freed_minutes)}min {direction}. "
        f"{len(req.affected_task_ids)} task(s) affected. "
        f"Severity: {severity}."
    )

    # Broadcast disruption event
    disruption_msg = _build_ws_message("disruption_event", {
        "severity": severity,
        "affected_task_ids": req.affected_task_ids,
        "freed_minutes": freed_minutes,
        "recommended_action": action,
        "context_summary": summary,
    })
    await manager.broadcast(disruption_msg)

    # Agent activity: Context Sentinel detected the change
    await manager.broadcast_agent_activity(
        "Context Sentinel",
        f"Detected {req.event_type} from {req.source}",
        "info",
    )

    # Agent activity: Disruption Detector classified
    await manager.broadcast_agent_activity(
        "Disruption Detector",
        f"Classified as {severity} — {action} ({abs(freed_minutes)}min {'gained' if freed_minutes >= 0 else 'lost'})",
        "disruption",
    )

    # Step 2: Scheduler Kernel runs MTS
    result = None
    if action == "reschedule_all":
        tasks, _sts = plan_day(peak_hours=_peak_hours, r=r)
    else:
        result = handle_disruption(
            freed_minutes=freed_minutes,
            energy_level=_energy_level,
            peak_hours=_peak_hours,
            sts=_sts,
            r=r,
        )

        # Rebuild STS with current active tasks
        active = get_active_tasks(r)
        _sts.reorder(active)

    # Step 3: Build updated schedule with swap info
    active = get_active_tasks(r)
    frontend_tasks = [_task_to_frontend(t) for t in active]

    swaps = []
    if result:
        for t in result.swapped_in:
            swaps.append({
                "action": "swap_in",
                "task_id": t.task_id,
                "reason": f"Fits {abs(freed_minutes)}min gap, energy OK",
                "new_time_slot": t.preferred_start or None,
            })
        for t in result.swapped_out:
            swaps.append({
                "action": "swap_out",
                "task_id": t.task_id,
                "reason": f"Displaced by {severity} disruption",
                "new_time_slot": None,
            })
        for t in result.delegated:
            swaps.append({
                "action": "delegate",
                "task_id": t.task_id,
                "reason": "Auto-delegated (low energy)",
                "new_time_slot": None,
            })

    schedule_msg = _build_ws_message("updated_schedule", {
        "tasks": frontend_tasks,
        "swaps": swaps,
        "energy": {"level": _energy_level, "confidence": 0.5, "source": "time_based"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await manager.broadcast(schedule_msg)

    # Agent activity: Scheduler Kernel completed rescheduling
    swap_summary_parts = []
    if result and result.swapped_in:
        swap_summary_parts.append(f"{len(result.swapped_in)} swapped in")
    if result and result.swapped_out:
        swap_summary_parts.append(f"{len(result.swapped_out)} swapped out")
    if result and result.delegated:
        swap_summary_parts.append(f"{len(result.delegated)} delegated")
    swap_text = ", ".join(swap_summary_parts) if swap_summary_parts else "schedule reordered"

    await manager.broadcast_agent_activity(
        "Scheduler Kernel",
        f"Rescheduled: {swap_text}. {len(frontend_tasks)} tasks active.",
        "swap" if swaps else "info",
    )

    # Agent activity for individual delegations
    if result and result.delegated:
        for t in result.delegated:
            await manager.broadcast_agent_activity(
                "GhostWorker",
                f"Task '{t.title}' delegated for autonomous execution",
                "delegation",
            )

    return {
        "severity": severity,
        "freed_minutes": freed_minutes,
        "action": action,
        "summary": summary,
        "swaps": swaps,
        "schedule_size": len(frontend_tasks),
    }


class EnergyUpdateRequest(BaseModel):
    level: int  # 1-5


@app.post("/api/energy")
async def update_energy(req: EnergyUpdateRequest):
    """Update the current energy level.

    Writes user-reported energy to Redis where the Energy Monitor agent
    picks it up as a high-confidence override signal.
    """
    global _energy_level
    _energy_level = max(1, min(5, req.level))

    # Write to Redis so the Energy Monitor agent reads it as user-reported
    r = _get_redis()
    r.set("energy:user_reported", str(_energy_level))
    r.set("energy:user_reported_ts", str(time.time()))

    # Auto-delegate P3 if energy critically low
    delegated = []
    if _energy_level <= 2:
        delegated_tasks = _sts.auto_delegate_p3(_energy_level)
        for task in delegated_tasks:
            store_task(task, r)
        delegated = [t.task_id for t in delegated_tasks]

    msg = _build_ws_message("energy_update", {
        "level": _energy_level,
        "confidence": 0.8,
        "source": "user_reported",
    })
    await manager.broadcast(msg)

    return {"energy_level": _energy_level, "delegated": delegated}


@app.get("/api/energy/status")
async def get_energy_status():
    """Read current energy level from the Energy Monitor agent's Redis cache.

    The Energy Monitor agent is the authoritative source — it computes
    energy periodically and on every query/completion, caching the result
    at the 'energy:current' key. This endpoint simply reads that cache.
    """
    r = _get_redis()
    cached = r.get("energy:current")
    if cached:
        return json.loads(cached)
    # Fallback if agent hasn't run yet
    return {"level": _energy_level, "confidence": 0.3, "source": "fallback"}


@app.get("/api/backlog")
async def get_backlog():
    """Get all backlog tasks."""
    r = _get_redis()
    backlog = get_backlog_tasks(r)
    return {"tasks": [_task_to_frontend(t) for t in backlog]}


# ══════════════════════════════════════════════════════════════════════════
# Composio Integration — Auth / Email / Calendar / LinkedIn
# ══════════════════════════════════════════════════════════════════════════

# ── Auth Routes ──────────────────────────────────────────────────────────

class AuthConnectRequest(BaseModel):
    toolkit: str  # "gmail" | "calendar" | "linkedin" | "slack"
    callback_url: str = "http://localhost:3000/auth/callback"


@app.post("/api/auth/connect")
async def auth_connect(req: AuthConnectRequest):
    """Initiate OAuth connection for a Composio toolkit.

    Returns a redirect_url the frontend should open in a new window/tab.
    """
    svc = get_composio_service()
    result = svc.initiate_connection(req.toolkit, req.callback_url)
    return result


@app.get("/api/auth/status")
async def auth_status():
    """Check which Composio toolkits have active OAuth connections."""
    svc = get_composio_service()
    return svc.check_connections()


# ── Email Routes ─────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    is_html: bool = False
    cc: Optional[str] = None
    bcc: Optional[str] = None


@app.post("/api/email/send")
async def send_email(req: SendEmailRequest):
    """Send an email via Composio Gmail integration."""
    svc = get_composio_service()
    result = svc.send_email(
        to=req.to,
        subject=req.subject,
        body=req.body,
        is_html=req.is_html,
        cc=req.cc,
        bcc=req.bcc,
    )
    # Broadcast agent activity
    await manager.broadcast_agent_activity(
        "GhostWorker",
        f"Email sent to {req.to}: {req.subject}",
        "ghostworker",
    )
    return result


@app.get("/api/email/list")
async def list_emails(
    q: str = Query("", description="Gmail search query"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Fetch emails from Gmail via Composio."""
    svc = get_composio_service()
    return svc.fetch_emails(query=q, max_results=max_results)


@app.get("/api/email/{message_id}")
async def get_email(message_id: str):
    """Fetch a specific email by message ID."""
    svc = get_composio_service()
    return svc.fetch_email_by_id(message_id)


# ── Calendar Routes ──────────────────────────────────────────────────────

@app.get("/api/calendar/events")
async def list_calendar_events(
    time_min: Optional[str] = Query(None, description="RFC3339 start (deep past OK)"),
    time_max: Optional[str] = Query(None, description="RFC3339 end (deep future OK)"),
    max_results: int = Query(250, ge=1, le=2500),
):
    """List Google Calendar events via Composio.

    Supports deep past/future time ranges.
    Defaults to today if no range given.
    """
    svc = get_composio_service()
    result = svc.list_events(
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )

    # Push to WebSocket so dashboard stays in sync
    cal_msg = _build_ws_message("calendar_update", {
        "events": result.get("data", result),
        "time_min": time_min,
        "time_max": time_max,
    })
    await manager.broadcast(cal_msg)

    return result


class CreateEventRequest(BaseModel):
    summary: str
    start_datetime: str  # ISO 8601
    duration_hours: int = 0
    duration_minutes: int = 30
    description: str = ""
    attendees: list[str] = []
    timezone: str = "America/Los_Angeles"
    create_meeting_room: bool = False


@app.post("/api/calendar/events")
async def create_calendar_event(req: CreateEventRequest):
    """Create a Google Calendar event via Composio."""
    svc = get_composio_service()
    result = svc.create_event(
        summary=req.summary,
        start_datetime=req.start_datetime,
        duration_hours=req.duration_hours,
        duration_minutes=req.duration_minutes,
        description=req.description,
        attendees=req.attendees if req.attendees else None,
        timezone_str=req.timezone,
        create_meeting_room=req.create_meeting_room,
    )
    await manager.broadcast_agent_activity(
        "Context Sentinel",
        f"Calendar event created: {req.summary}",
        "info",
    )
    return result


@app.get("/api/calendar/search")
async def search_calendar_events(
    q: str = Query(..., description="Search query"),
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
):
    """Search Google Calendar events via Composio."""
    svc = get_composio_service()
    return svc.find_event(query=q, time_min=time_min, time_max=time_max)


# ── Profile + Profiler Intelligence Routes ───────────────────────────────

@app.get("/api/profile/linkedin")
async def get_linkedin_profile():
    """Get authenticated user's LinkedIn profile via Composio."""
    svc = get_composio_service()
    return svc.get_linkedin_profile()


@app.get("/api/profile/full")
async def get_full_profile():
    """Get full profiler output: user_profile, grouping, success_plot, sentiment, drift.

    Reads from Redis cache (profiler:last_result) if available,
    otherwise computes fresh from local data files.
    """
    r = _get_redis()

    # Try cached result first
    cached = r.get("profiler:last_result")
    if cached:
        try:
            profile_data = json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            profile_data = None
    else:
        profile_data = None

    if not profile_data:
        # Compute fresh from local data
        profile_data = _compute_profiler_fresh(r)

    # Enrich with live LinkedIn data (best-effort)
    try:
        svc = get_composio_service()
        linkedin = svc.get_linkedin_profile()
        if linkedin.get("successful"):
            profile_data["linkedin_live"] = linkedin.get("data", linkedin)
        else:
            profile_data["linkedin_live"] = None
    except Exception:
        profile_data["linkedin_live"] = None

    return profile_data


def _compute_profiler_fresh(r: redis.Redis) -> dict[str, Any]:
    """Run the ProfilerEngine on local data files and return the result."""
    from src.data_pipeline.parsers import (
        parse_daily_goals,
        parse_linkedin,
        parse_twitter,
        parse_reflections,
        parse_resume,
    )

    # Load data from parsers
    daily_goals = parse_daily_goals()
    social_hours: dict[str, list[int]] = {}

    try:
        li_data = parse_linkedin()
        if li_data and "posting_hours" in li_data:
            social_hours["linkedin"] = li_data["posting_hours"]
    except Exception:
        pass

    try:
        tw_data = parse_twitter()
        if tw_data and "posting_hours" in tw_data:
            social_hours["twitter"] = tw_data["posting_hours"]
    except Exception:
        pass

    reflection_data: dict[str, Any] = {}
    try:
        reflection_data = parse_reflections()
    except Exception:
        pass

    resume_data: dict[str, Any] = {}
    try:
        resume_data = parse_resume()
    except Exception:
        pass

    # Task completions from Redis
    task_completions: list[dict[str, Any]] = []
    try:
        tc_raw = r.get("profiler:task_completions")
        if tc_raw:
            task_completions = json.loads(tc_raw)
    except Exception:
        pass

    # Run the profiler engine
    engine = ProfilerEngine()
    result = engine.build_full_profile(
        daily_goals=daily_goals,
        task_completions=task_completions,
        social_posting_hours=social_hours,
        reflection_data=reflection_data,
        resume_data=resume_data,
    )

    # Cache the result
    try:
        r.set("profiler:last_result", json.dumps(result), ex=1800)  # 30 min TTL
    except Exception:
        pass

    return result


@app.get("/api/schedule/intelligence")
async def get_schedule_intelligence():
    """Return how profiler data drives LTS/STS scheduling decisions.

    Exposes the scheduling configuration, MLFQ queue state,
    task buffer distribution, and profiler influence summary.
    """
    r = _get_redis()

    # Get profiler data
    cached = r.get("profiler:last_result")
    profile_data = None
    if cached:
        try:
            profile_data = json.loads(cached)
        except Exception:
            pass

    if not profile_data:
        profile_data = _compute_profiler_fresh(r)

    user_profile = profile_data.get("user_profile", {})
    grouping = profile_data.get("grouping", {})

    # LTS configuration — how the Long-Term Scheduler scores tasks
    lts_config = {
        "peak_hours": user_profile.get("peak_hours", _peak_hours),
        "estimation_bias_correction": user_profile.get("estimation_bias", 1.0),
        "scoring_weights": {
            "deadline_urgency": 0.40,
            "priority": 0.30,
            "peak_alignment": 0.15,
            "duration_efficiency": 0.15,
        },
    }

    # STS configuration — current MLFQ queue state
    queue_counts = _sts.queue_counts()
    sts_config = {
        "mlfq_queue_counts": queue_counts,
        "energy_level": _energy_level,
        "energy_constraint": f"tasks with energy_cost > {_energy_level} blocked",
    }

    # Task buffer — hash distribution across 16 buckets
    bucket_distribution = [0] * TASK_BUCKET_COUNT
    try:
        backlog = get_backlog_tasks(r)
        for t in backlog:
            bucket_idx = t.bucket % TASK_BUCKET_COUNT
            bucket_distribution[bucket_idx] += 1
    except Exception:
        pass

    task_buffer = {
        "bucket_count": TASK_BUCKET_COUNT,
        "hash_weights": {
            "deadline_urgency": 0.45,
            "estimated_execution": 0.30,
            "preferred_start": 0.25,
        },
        "bucket_distribution": bucket_distribution,
    }

    # Profiler influence summary
    peak_hours = user_profile.get("peak_hours", _peak_hours)
    bias = user_profile.get("estimation_bias", 1.0)
    automation = user_profile.get("automation_comfort", {})
    energy_curve = user_profile.get("energy_curve", [])

    # Count how many active tasks are delegatable
    active = get_active_tasks(r)
    automatable_types = {"email_reply", "slack_message", "uber_book",
                         "cancel_appointment", "doc_update", "meeting_reschedule"}
    auto_count = sum(1 for t in active if t.task_type in automatable_types)

    profiler_influence = {
        "peak_hour_alignment": f"High-cognitive tasks scheduled during {peak_hours}",
        "energy_curve_24h": energy_curve,
        "energy_curve_effect": f"Low-energy P3 tasks deferred to evening hours",
        "automation_delegated": auto_count,
        "estimation_correction": f"Durations inflated by {bias:.2f}x based on historical bias",
        "automation_comfort": automation,
        "archetype": grouping.get("archetype", "unknown"),
        "archetype_label": grouping.get("archetype_label", "Unknown"),
        "drift_direction": user_profile.get("drift_direction", "balanced"),
    }

    return {
        "lts_config": lts_config,
        "sts_config": sts_config,
        "task_buffer": task_buffer,
        "profiler_influence": profiler_influence,
    }


# ── Agentverse Integration ────────────────────────────────────────────────

@app.get("/status")
async def agentverse_status():
    """Chat Protocol health check — required for Agentverse registration."""
    return {"status": "OK - Rewind server is running"}


class AgentverseSearchRequest(BaseModel):
    query: str
    limit: int = 10


@app.post("/api/agentverse/search")
async def agentverse_search(req: AgentverseSearchRequest):
    """Proxy Agentverse search to keep API key server-side."""
    import os
    import httpx

    token = os.getenv("AGENTVERSE_API_TOKEN", "")
    if not token:
        return {"agents": [], "error": "AGENTVERSE_API_TOKEN not configured"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://agentverse.ai/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "search_text": req.query,
                    "filters": {"state": ["active"]},
                    "sort": "relevancy",
                    "direction": "asc",
                    "offset": 0,
                    "limit": req.limit,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                return {"agents": resp.json()}
            return {"agents": [], "error": f"Agentverse returned {resp.status_code}"}
    except Exception as exc:
        return {"agents": [], "error": str(exc)}


class AgentverseChatRequest(BaseModel):
    agent: str
    message: str


@app.post("/api/agentverse/chat")
async def agentverse_chat(req: AgentverseChatRequest):
    """Placeholder for agent chat — routes to local agent handlers."""
    # In production, this would send a Chat Protocol message to the agent
    # For now, return a description of the agent's capabilities
    agent_responses = {
        "Context Sentinel": "I monitor Google Calendar, Gmail, and Slack for real-time context changes. I can tell you about upcoming events and recent emails.",
        "Profiler Agent": "I learn your behavioral patterns — peak hours, estimation bias, energy curves, schedule adherence. Ask me about your productivity patterns.",
        "Disruption Detector": "I classify disruptions by severity (minor/major/critical) and recommend recovery actions (swap_in/swap_out/reschedule_all/delegate).",
        "Scheduler Kernel": "I orchestrate the three-tier scheduling engine: LTS for daily planning, MTS for disruption recovery, STS for task ordering. I can optimize your schedule.",
        "Energy Monitor": "I infer your energy level (1-5) from behavioral signals and time-of-day patterns. I track completion velocity and user-reported overrides.",
        "GhostWorker": "I autonomously execute delegatable tasks — email replies, Slack messages, appointment cancellations. I draft first, you approve.",
    }
    response = agent_responses.get(
        req.agent,
        f"Agent '{req.agent}' is available but chat routing is not yet configured for this agent.",
    )
    return {"response": response, "agent": req.agent}


# ── Draft Execution via Composio ─────────────────────────────────────────

class DraftExecuteRequest(BaseModel):
    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


@app.post("/api/drafts/{draft_id}/execute")
async def execute_draft(draft_id: str, req: DraftExecuteRequest = None):
    """Execute an approved draft by sending it via Composio.

    Reads draft data from Redis, sends the email, and cleans up.
    """
    r = _get_redis()
    svc = get_composio_service()

    # Read draft from Redis
    draft_data = r.hgetall(f"ghostworker:draft:{draft_id}")

    # Determine email fields
    to = (req and req.to) or draft_data.get("recipient", "")
    subject = (req and req.subject) or draft_data.get("subject", "")
    body = (req and req.body) or draft_data.get("body", "")

    if not to or not body:
        return {"successful": False, "error": "Missing recipient or body"}

    # Send via Composio
    result = svc.send_email(to=to, subject=subject, body=body)

    if result.get("successful", False):
        # Clean up draft from Redis
        r.delete(f"ghostworker:draft:{draft_id}")
        r.srem("ghostworker:pending", draft_id)

        # Notify WebSocket
        await manager.broadcast_agent_activity(
            "GhostWorker",
            f"Draft {draft_id} executed — email sent to {to}",
            "ghostworker",
        )

        # Publish event for GhostWorker agent
        r.publish("ghostworker:events", json.dumps({
            "event": "draft_executed",
            "draft_id": draft_id,
            "task_id": draft_data.get("task_id", ""),
        }))

    return result


# ── GhostWorker Relay ───────────────────────────────────────────────────
# The server relays GhostWorker events between Redis pub/sub and WebSocket.
# It contains NO GhostWorker business logic — the agent is fully autonomous.

_ghostworker_listener_task: Optional[asyncio.Task] = None


async def _ghostworker_event_listener():
    """Background task: subscribe to ghostworker:events and relay to WebSocket.

    The GhostWorker agent publishes events (draft_created, draft_executed,
    draft_rejected) to the ghostworker:events Redis channel. This listener
    relays them to all connected WebSocket clients.
    """
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("ghostworker:events")
    logger.info("GhostWorker event listener started")

    try:
        while True:
            msg = pubsub.get_message(timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.5)
                continue
            if msg["type"] != "message":
                continue

            try:
                data = json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            event_type = data.get("event", "")

            if event_type == "draft_created":
                # Relay new draft to frontend
                ws_msg = _build_ws_message("ghostworker_draft", data.get("draft", {}))
                await manager.broadcast(ws_msg)
                await manager.broadcast_agent_activity(
                    "GhostWorker",
                    f"Draft created for task {data.get('draft', {}).get('task_type', 'unknown')}",
                    "ghostworker",
                )

            elif event_type == "draft_executed":
                ws_msg = _build_ws_message("ghost_worker_status", {
                    "task_id": data.get("task_id", ""),
                    "draft_id": data.get("draft_id", ""),
                    "status": "executed",
                    "message": f"Task {data.get('task_id', '')} executed successfully",
                })
                await manager.broadcast(ws_msg)
                await manager.broadcast_agent_activity(
                    "GhostWorker",
                    f"Task {data.get('task_id', '')} executed via Composio",
                    "ghostworker",
                )

            elif event_type == "draft_rejected":
                ws_msg = _build_ws_message("ghost_worker_status", {
                    "task_id": data.get("task_id", ""),
                    "draft_id": data.get("draft_id", ""),
                    "status": "rejected",
                    "message": f"Draft for task {data.get('task_id', '')} rejected",
                })
                await manager.broadcast(ws_msg)

            elif event_type == "draft_failed":
                ws_msg = _build_ws_message("ghost_worker_status", {
                    "task_id": data.get("task_id", ""),
                    "draft_id": data.get("draft_id", ""),
                    "status": "failed",
                    "message": f"Task {data.get('task_id', '')} execution failed",
                })
                await manager.broadcast(ws_msg)

    except asyncio.CancelledError:
        pubsub.unsubscribe("ghostworker:events")
        pubsub.close()
    except Exception as exc:
        logger.error("GhostWorker event listener error: %s", exc)


@app.on_event("startup")
async def start_ghostworker_listener():
    """Start the GhostWorker event relay on server startup."""
    global _ghostworker_listener_task
    _ghostworker_listener_task = asyncio.create_task(_ghostworker_event_listener())


@app.on_event("shutdown")
async def stop_ghostworker_listener():
    """Stop the GhostWorker event relay on server shutdown."""
    if _ghostworker_listener_task and not _ghostworker_listener_task.done():
        _ghostworker_listener_task.cancel()
        try:
            await _ghostworker_listener_task
        except asyncio.CancelledError:
            pass


@app.get("/api/ghostworker/drafts")
async def get_ghostworker_drafts():
    """Read pending drafts from Redis.

    Pure relay — reads what the GhostWorker agent stored.
    """
    r = _get_redis()
    pending_ids = r.smembers("ghostworker:pending")
    drafts = []
    for draft_id in pending_ids:
        draft_data = r.hgetall(f"ghostworker:draft:{draft_id}")
        if draft_data:
            drafts.append(draft_data)
    return {"drafts": drafts}


class DraftApprovalRequest(BaseModel):
    edited_body: Optional[str] = None


@app.post("/api/ghostworker/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, req: DraftApprovalRequest = None):
    """Approve a draft — publishes to Redis for GhostWorker agent to execute.

    Pure relay — the server does NOT execute the action.
    """
    r = _get_redis()

    # Verify draft exists
    if not r.exists(f"ghostworker:draft:{draft_id}"):
        return {"error": "Draft not found"}, 404

    approval = {"action": "approve", "draft_id": draft_id}
    if req and req.edited_body:
        approval["edited_body"] = req.edited_body

    r.publish("ghostworker:approvals", json.dumps(approval))
    logger.info("Approval published for draft %s", draft_id)

    return {"status": "approval_sent", "draft_id": draft_id}


@app.post("/api/ghostworker/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str):
    """Reject a draft — publishes to Redis for GhostWorker agent to handle.

    Pure relay — the server does NOT modify draft state.
    """
    r = _get_redis()

    if not r.exists(f"ghostworker:draft:{draft_id}"):
        return {"error": "Draft not found"}, 404

    rejection = {"action": "reject", "draft_id": draft_id}
    r.publish("ghostworker:approvals", json.dumps(rejection))
    logger.info("Rejection published for draft %s", draft_id)

    return {"status": "rejection_sent", "draft_id": draft_id}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)
