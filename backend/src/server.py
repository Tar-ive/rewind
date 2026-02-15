"""FastAPI server bridging the scheduling engine to the frontend.

WebSocket for real-time schedule updates + REST endpoints for
triggering actions and querying state.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config.settings import REDIS_URL
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


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)
