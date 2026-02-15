"""Context Sentinel Agent.

Monitors real-time context signals by polling Google Calendar, Gmail, and Slack
via Composio MCP connections. Detects changes by comparing with Redis-cached state
and emits ContextChangeEvent to downstream agents (Disruption Detector).

Architecture:
─────────────
- Uses ComposioMCPOrchestrator (from composio/main.py) for MCP session management
  and multi-platform API access (Calendar, Gmail, Slack).
- Uses uagents-composio-adapter for Composio + uAgents protocol integration,
  providing the ComposioService protocol layer for tool group management.
- Redis for state caching and change detection against previously polled data.
- uAgents interval-based polling with configurable frequency.

uAgents Key Properties:
───────────────────────
  agent.address    → agent1q... identifier (inter-agent messaging)
  agent.wallet     → Fetch.ai blockchain wallet (FET token interactions)
  agent.storage    → Persistent key-value store (survives restarts)

Inter-Agent Messages (from src.models.messages):
  ContextChangeEvent → emitted when calendar/email/slack changes detected
  DisruptionEvent    → consumed by Disruption Detector (downstream)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import redis
from uagents import Agent, Context

from src.composio.main import ComposioMCPOrchestrator
from src.config.settings import (
    COMPOSIO_API_KEY,
    COMPOSIO_USER_ID,
    CONTEXT_SENTINEL_SEED,
    DISRUPTION_DETECTOR_ADDRESS,
    CALENDAR_LOOKAHEAD_HOURS,
    GMAIL_LOOKBACK_HOURS,
    GOOGLE_CALENDAR_AUTH_CONFIG_ID,
    GMAIL_AUTH_CONFIG_ID,
    SLACK_AUTH_CONFIG_ID,
    REDIS_URL,
    SENTINEL_POLL_INTERVAL,
)
from src.models.messages import ContextChangeEvent
from src.agents.protocols import create_chat_protocol

# Conditionally import uagents-composio-adapter for enhanced protocol support
try:
    from uagents_composio_adapter import (
        ComposioConfig,
        ComposioService,
        ToolConfig,
    )

    HAS_COMPOSIO_ADAPTER = True
except ImportError:
    HAS_COMPOSIO_ADAPTER = False

logger = logging.getLogger(__name__)


# ── Redis Keys for State Caching ────────────────────────────────────────

SENTINEL_PREFIX = "sentinel:"
CALENDAR_CACHE_KEY = f"{SENTINEL_PREFIX}calendar:events"
GMAIL_CACHE_KEY = f"{SENTINEL_PREFIX}gmail:messages"
SLACK_CACHE_KEY = f"{SENTINEL_PREFIX}slack:messages"
LAST_POLL_KEY = f"{SENTINEL_PREFIX}last_poll"


# ── Agent Setup ─────────────────────────────────────────────────────────
#
# KEY CONSTRUCTOR PARAMETERS
# ──────────────────────────
# name        Human-readable name (used in logs and key storage)
# seed        Deterministic identity (uses os.getenv for secrets)
# port        Local HTTP server port (8003 for Context Sentinel)
# endpoint    Public endpoint(s) for receiving messages
# mailbox     True or a mailbox API key string (enables Agentverse connectivity)
# test        Defaults to True for testnet; set False for mainnet

_deploy_mode = os.getenv("AGENT_DEPLOY_MODE", "local")
_endpoint_base = os.getenv("AGENT_ENDPOINT_BASE", "http://localhost")

agent = Agent(
    name="context_sentinel",
    seed=CONTEXT_SENTINEL_SEED,
    port=8004,
    endpoint=[f"{_endpoint_base}:8004/submit"] if _deploy_mode == "local" else [],
    mailbox=True if _deploy_mode == "agentverse" else False,
)

# Redis client for state caching
_redis: redis.Redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Composio MCP Orchestrator (lazy init)
_orchestrator: Optional[ComposioMCPOrchestrator] = None

# Composio adapter service reference (optional enhanced integration)
_composio_service: Optional[Any] = None


# ── Composio MCP Orchestrator ───────────────────────────────────────────


def _get_orchestrator() -> ComposioMCPOrchestrator:
    """Get or initialize the Composio MCP orchestrator.

    Reuses the MCP session management from composio/main.py to access
    Google Calendar, Gmail, Slack, and LinkedIn via a unified MCP endpoint.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ComposioMCPOrchestrator(
            api_key=COMPOSIO_API_KEY,
            user_id=COMPOSIO_USER_ID,
        )
        _orchestrator.initialize_session()
        logger.info("Composio MCP session initialized for Context Sentinel")
    return _orchestrator


# ── Composio Adapter Setup (uagents-composio-adapter) ──────────────────


async def _init_composio_adapter() -> Optional[Any]:
    """Initialize the uagents-composio-adapter service.

    Creates tool groups for Calendar, Gmail, and Slack, then wires them
    into the agent via ComposioService.protocol.
    """
    if not HAS_COMPOSIO_ADAPTER:
        logger.info("uagents-composio-adapter not installed; using MCP-only mode")
        return None

    tool_configs: List[ToolConfig] = []

    # Google Calendar tool group
    if GOOGLE_CALENDAR_AUTH_CONFIG_ID:
        tool_configs.append(
            ToolConfig.from_toolkit(
                tool_group_name="Calendar Monitoring",
                auth_config_id=GOOGLE_CALENDAR_AUTH_CONFIG_ID,
                toolkit="GOOGLECALENDAR",
                limit=5,
            )
        )

    # Gmail tool group
    if GMAIL_AUTH_CONFIG_ID:
        tool_configs.append(
            ToolConfig.from_toolkit(
                tool_group_name="Email Monitoring",
                auth_config_id=GMAIL_AUTH_CONFIG_ID,
                toolkit="GMAIL",
                limit=5,
            )
        )

    # Slack tool group
    if SLACK_AUTH_CONFIG_ID:
        tool_configs.append(
            ToolConfig.from_toolkit(
                tool_group_name="Slack Monitoring",
                auth_config_id=SLACK_AUTH_CONFIG_ID,
                toolkit="SLACK",
                limit=5,
            )
        )

    if not tool_configs:
        logger.warning("No Composio auth config IDs set; adapter skipped")
        return None

    try:
        composio_config = ComposioConfig.from_env(
            tool_configs=tool_configs,
            persona_prompt=(
                "You are the Context Sentinel — a real-time monitoring agent. "
                "Your job is to detect changes in the user's calendar, email, and "
                "communication channels, then report structured change data."
            ),
        )

        service = ComposioService(composio_config=composio_config)
        await service.__aenter__()

        # Include the Composio protocol in the agent for tool-level chat
        agent.include(service.protocol, publish_manifest=True)
        logger.info("Composio adapter service initialized with %d tool groups", len(tool_configs))
        return service

    except Exception as exc:
        logger.warning("Composio adapter init failed (MCP-only fallback): %s", exc)
        return None


# ── Redis State Management ──────────────────────────────────────────────


def _cache_state(key: str, data: Any) -> None:
    """Cache current state in Redis with timestamp."""
    _redis.set(
        key,
        json.dumps(
            {"data": data, "cached_at": datetime.now(timezone.utc).isoformat()}
        ),
    )


def _get_cached_state(key: str) -> Optional[Dict]:
    """Retrieve cached state from Redis."""
    raw = _redis.get(key)
    if raw:
        return json.loads(raw)
    return None


def _get_user_context_from_redis() -> Dict[str, Any]:
    """Aggregate all cached user context data from Redis.

    Pulls from:
    - task:active   → currently active tasks
    - task:backlog  → backlog tasks
    - explicit:*    → explicit user signals (LinkedIn, GitHub, certs, etc.)
    - implicit:*    → implicit behavioral signals
    - sentinel:*    → previously cached polling state
    """
    context: Dict[str, Any] = {
        "active_tasks": [],
        "backlog_tasks": [],
        "last_calendar_state": None,
        "last_gmail_state": None,
        "last_slack_state": None,
    }

    # Active tasks
    active_ids = _redis.smembers("task:active")
    for task_id in active_ids:
        data = _redis.hgetall(f"task:{task_id}")
        if data:
            context["active_tasks"].append(data)

    # Backlog tasks
    backlog_ids = _redis.smembers("task:backlog")
    for task_id in backlog_ids:
        data = _redis.hgetall(f"task:{task_id}")
        if data:
            context["backlog_tasks"].append(data)

    # Cached sentinel states
    for cache_key, field in [
        (CALENDAR_CACHE_KEY, "last_calendar_state"),
        (GMAIL_CACHE_KEY, "last_gmail_state"),
        (SLACK_CACHE_KEY, "last_slack_state"),
    ]:
        cached = _get_cached_state(cache_key)
        if cached:
            context[field] = cached.get("data")

    return context


# ── Change Detection Logic ──────────────────────────────────────────────


def _find_affected_tasks(start_time: str, end_time: str) -> List[str]:
    """Find task IDs whose preferred_start overlaps [start_time, end_time]."""
    affected: List[str] = []
    try:
        for task_id in _redis.smembers("task:active"):
            data = _redis.hgetall(f"task:{task_id}")
            if not data:
                continue
            ps = data.get("preferred_start", "")
            if ps and start_time and end_time:
                if start_time <= ps <= end_time:
                    affected.append(task_id)
    except Exception as exc:
        logger.warning("Error finding affected tasks: %s", exc)
    return affected


def _detect_calendar_changes(
    current_events: List[Dict],
    cached_events: Optional[List[Dict]],
) -> List[ContextChangeEvent]:
    """Compare current calendar events with cached state to detect changes.

    Detects: new events, cancelled events, rescheduled events,
    meetings that ended early.
    """
    events: List[ContextChangeEvent] = []

    if cached_events is None:
        # First poll — seed the cache but emit no events
        return events

    cached_by_id = {e.get("id", e.get("event_id", "")): e for e in cached_events}
    current_by_id = {e.get("id", e.get("event_id", "")): e for e in current_events}
    now_iso = datetime.now(timezone.utc).isoformat()

    # New events
    for eid, event in current_by_id.items():
        if eid and eid not in cached_by_id:
            events.append(
                ContextChangeEvent(
                    event_type="new_calendar_event",
                    source="google_calendar",
                    timestamp=now_iso,
                    affected_task_ids=[],
                    metadata={
                        "event_id": eid,
                        "title": event.get("summary", event.get("title", "")),
                        "start": event.get("start", ""),
                        "end": event.get("end", ""),
                    },
                )
            )

    # Modified / cancelled events
    for eid, cached_event in cached_by_id.items():
        if eid in current_by_id:
            cur = current_by_id[eid]
            # Time change detection
            if cur.get("start") != cached_event.get("start") or cur.get("end") != cached_event.get("end"):
                old_end = cached_event.get("end", "")
                new_end = cur.get("end", "")
                event_type = "schedule_conflict"
                if old_end and new_end and new_end < old_end:
                    event_type = "meeting_ended_early"

                affected = _find_affected_tasks(
                    cur.get("start", ""), cur.get("end", "")
                )
                events.append(
                    ContextChangeEvent(
                        event_type=event_type,
                        source="google_calendar",
                        timestamp=now_iso,
                        affected_task_ids=affected,
                        metadata={
                            "event_id": eid,
                            "title": cur.get("summary", cur.get("title", "")),
                            "old_start": cached_event.get("start"),
                            "old_end": old_end,
                            "new_start": cur.get("start"),
                            "new_end": new_end,
                        },
                    )
                )
        else:
            # Event disappeared — cancelled
            affected = _find_affected_tasks(
                cached_event.get("start", ""), cached_event.get("end", "")
            )
            events.append(
                ContextChangeEvent(
                    event_type="event_cancelled",
                    source="google_calendar",
                    timestamp=now_iso,
                    affected_task_ids=affected,
                    metadata={
                        "event_id": eid,
                        "title": cached_event.get("summary", cached_event.get("title", "")),
                        "cancelled_start": cached_event.get("start"),
                        "cancelled_end": cached_event.get("end"),
                    },
                )
            )

    return events


def _detect_email_changes(
    current_messages: List[Dict],
    cached_messages: Optional[List[Dict]],
) -> List[ContextChangeEvent]:
    """Detect new emails by comparing message IDs."""
    events: List[ContextChangeEvent] = []

    if cached_messages is None:
        return events

    cached_ids = {m.get("id", m.get("message_id", "")) for m in cached_messages}
    now_iso = datetime.now(timezone.utc).isoformat()

    for msg in current_messages:
        msg_id = msg.get("id", msg.get("message_id", ""))
        if msg_id and msg_id not in cached_ids:
            events.append(
                ContextChangeEvent(
                    event_type="new_email",
                    source="gmail",
                    timestamp=now_iso,
                    affected_task_ids=[],
                    metadata={
                        "message_id": msg_id,
                        "subject": msg.get("subject", ""),
                        "from": msg.get("from", msg.get("sender", "")),
                        "snippet": msg.get("snippet", ""),
                        "labels": msg.get("labels", []),
                    },
                )
            )

    return events


def _detect_slack_changes(
    current_messages: List[Dict],
    cached_messages: Optional[List[Dict]],
) -> List[ContextChangeEvent]:
    """Detect urgent/actionable Slack messages."""
    events: List[ContextChangeEvent] = []

    if cached_messages is None:
        return events

    cached_ids = {m.get("id", m.get("ts", "")) for m in cached_messages}
    now_iso = datetime.now(timezone.utc).isoformat()
    urgent_keywords = {"urgent", "asap", "deadline", "blocked", "critical", "p0", "hotfix"}

    for msg in current_messages:
        msg_id = msg.get("id", msg.get("ts", ""))
        if msg_id and msg_id not in cached_ids:
            text_lower = msg.get("text", "").lower()
            is_urgent = any(kw in text_lower for kw in urgent_keywords)
            has_mention = "@" in msg.get("text", "")

            if is_urgent or has_mention:
                events.append(
                    ContextChangeEvent(
                        event_type="slack_urgent_message",
                        source="slack",
                        timestamp=now_iso,
                        affected_task_ids=[],
                        metadata={
                            "message_id": msg_id,
                            "channel": msg.get("channel", ""),
                            "user": msg.get("user", ""),
                            "text": msg.get("text", ""),
                            "is_urgent": is_urgent,
                            "has_mention": has_mention,
                        },
                    )
                )

    return events


# ── Composio MCP Polling Functions ──────────────────────────────────────


def _try_parse_json_array(responses: List[str]) -> List[Dict]:
    """Extract a JSON array from MCP orchestrator responses."""
    for resp in responses:
        cleaned = resp.strip()
        # Direct JSON array
        if cleaned.startswith("["):
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        # Embedded in markdown code block or surrounding text
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                continue
    return []


async def _poll_calendar(user_context: Dict[str, Any]) -> List[Dict]:
    """Poll Google Calendar via Composio MCP for upcoming events.

    Includes user context from Redis (active tasks, signals) to give
    the MCP agent richer context for the extraction.
    """
    orchestrator = _get_orchestrator()
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=CALENDAR_LOOKAHEAD_HOURS)

    # Build context summary from Redis data
    task_summary = ""
    if user_context.get("active_tasks"):
        task_titles = [t.get("title", "unknown") for t in user_context["active_tasks"][:5]]
        task_summary = f"\nUser's active tasks: {', '.join(task_titles)}"

    prompt = f"""List all calendar events between {now.isoformat()} and {end.isoformat()}.{task_summary}

Return ONLY a JSON array of events with fields:
- id: event unique identifier
- summary: event title
- start: ISO 8601 start datetime
- end: ISO 8601 end datetime
- status: confirmed/cancelled/tentative
- attendees: list of attendee emails

If no events, return: []
Return ONLY valid JSON, no other text."""

    try:
        responses = await orchestrator.execute_operation(
            prompt,
            system_context=(
                "You are a calendar data extraction agent. "
                "Always return structured JSON arrays. No explanations or markdown."
            ),
            max_iterations=3,
        )
        return _try_parse_json_array(responses)
    except Exception as exc:
        logger.error("Calendar poll failed: %s", exc)
        return []


async def _poll_gmail(user_context: Dict[str, Any]) -> List[Dict]:
    """Poll Gmail via Composio MCP for recent messages."""
    orchestrator = _get_orchestrator()
    lookback = datetime.now(timezone.utc) - timedelta(hours=GMAIL_LOOKBACK_HOURS)

    prompt = f"""List unread emails received after {lookback.isoformat()}.

Return ONLY a JSON array of messages with fields:
- id: message unique identifier
- subject: email subject line
- from: sender email address
- snippet: first 100 characters of body
- received_at: ISO 8601 timestamp
- labels: list of label names

If no new emails, return: []
Return ONLY valid JSON, no other text."""

    try:
        responses = await orchestrator.execute_operation(
            prompt,
            system_context=(
                "You are an email data extraction agent. "
                "Always return structured JSON arrays. No explanations or markdown."
            ),
            max_iterations=3,
        )
        return _try_parse_json_array(responses)
    except Exception as exc:
        logger.error("Gmail poll failed: %s", exc)
        return []


async def _poll_slack(user_context: Dict[str, Any]) -> List[Dict]:
    """Poll Slack via Composio MCP for recent channel messages."""
    orchestrator = _get_orchestrator()
    lookback = datetime.now(timezone.utc) - timedelta(hours=1)

    prompt = f"""Retrieve messages from the #general Slack channel posted after {lookback.isoformat()}.

Return ONLY a JSON array of messages with fields:
- id: message timestamp/ID
- text: message text
- user: sender username
- channel: channel name
- timestamp: ISO 8601 timestamp

If no new messages, return: []
Return ONLY valid JSON, no other text."""

    try:
        responses = await orchestrator.execute_operation(
            prompt,
            system_context=(
                "You are a Slack data extraction agent. "
                "Always return structured JSON arrays. No explanations or markdown."
            ),
            max_iterations=3,
        )
        return _try_parse_json_array(responses)
    except Exception as exc:
        logger.error("Slack poll failed: %s", exc)
        return []


# ── Agent Event Handlers ────────────────────────────────────────────────


@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Initialize MCP session and optional Composio adapter on startup.

    KEY AGENT PROPERTIES accessible here:
      ctx.agent.address  → agent1q... identifier
      agent.wallet       → Fetch.ai blockchain wallet
      ctx.storage        → persistent key-value store
    """
    global _composio_service
    logger.info("Context Sentinel starting — address: %s", agent.address)

    # Initialize Composio MCP orchestrator (from composio/main.py)
    _get_orchestrator()

    # Initialize uagents-composio-adapter service (if available)
    _composio_service = await _init_composio_adapter()

    # Persist startup state
    ctx.storage.set("startup_time", datetime.now(timezone.utc).isoformat())
    ctx.storage.set("poll_count", "0")
    ctx.storage.set("total_events_emitted", "0")

    logger.info("Context Sentinel initialized — polling every %ds", SENTINEL_POLL_INTERVAL)


@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    """Clean up Composio adapter service on shutdown."""
    global _composio_service
    if _composio_service is not None:
        try:
            await _composio_service.__aexit__(None, None, None)
        except Exception:
            pass
        _composio_service = None
    logger.info("Context Sentinel shut down")


# ── Main Polling Loop ───────────────────────────────────────────────────


@agent.on_interval(period=SENTINEL_POLL_INTERVAL)
async def poll_context_signals(ctx: Context):
    """Poll all context sources, detect changes, emit ContextChangeEvents.

    Flow:
    1. Load existing user context from Redis cache
    2. Poll Google Calendar, Gmail, Slack via Composio MCP
    3. Compare with cached state to detect changes
    4. Emit ContextChangeEvent for each detected change
    5. Update cache with latest state
    """
    poll_count = int(ctx.storage.get("poll_count") or "0") + 1
    ctx.storage.set("poll_count", str(poll_count))
    logger.info("Poll cycle %d started", poll_count)

    # 1. Load all cached user context from Redis
    user_context = _get_user_context_from_redis()
    all_events: List[ContextChangeEvent] = []

    # 2. Poll Google Calendar
    try:
        current_calendar = await _poll_calendar(user_context)
        cached_calendar = user_context.get("last_calendar_state")
        calendar_changes = _detect_calendar_changes(current_calendar, cached_calendar)
        all_events.extend(calendar_changes)
        _cache_state(CALENDAR_CACHE_KEY, current_calendar)
        if calendar_changes:
            logger.info("Detected %d calendar change(s)", len(calendar_changes))
    except Exception as exc:
        logger.error("Calendar polling error: %s", exc)

    # 3. Poll Gmail
    try:
        current_gmail = await _poll_gmail(user_context)
        cached_gmail = user_context.get("last_gmail_state")
        email_changes = _detect_email_changes(current_gmail, cached_gmail)
        all_events.extend(email_changes)
        _cache_state(GMAIL_CACHE_KEY, current_gmail)
        if email_changes:
            logger.info("Detected %d new email(s)", len(email_changes))
    except Exception as exc:
        logger.error("Gmail polling error: %s", exc)

    # 4. Poll Slack
    try:
        current_slack = await _poll_slack(user_context)
        cached_slack = user_context.get("last_slack_state")
        slack_changes = _detect_slack_changes(current_slack, cached_slack)
        all_events.extend(slack_changes)
        _cache_state(SLACK_CACHE_KEY, current_slack)
        if slack_changes:
            logger.info("Detected %d Slack event(s)", len(slack_changes))
    except Exception as exc:
        logger.error("Slack polling error: %s", exc)

    # 5. Emit all detected events to Disruption Detector
    sent_count = 0
    for event in all_events:
        try:
            if DISRUPTION_DETECTOR_ADDRESS:
                await ctx.send(DISRUPTION_DETECTOR_ADDRESS, event)
                sent_count += 1
                logger.info(
                    "Sent %s to Disruption Detector (affected: %s)",
                    event.event_type,
                    event.affected_task_ids,
                )
            else:
                logger.warning(
                    "DISRUPTION_DETECTOR_ADDRESS not set — %s not forwarded",
                    event.event_type,
                )
        except Exception as exc:
            logger.error("Failed to send %s: %s", event.event_type, exc)

    # 6. Update telemetry in Redis + agent storage
    _redis.set(LAST_POLL_KEY, datetime.now(timezone.utc).isoformat())
    total = int(ctx.storage.get("total_events_emitted") or "0") + sent_count
    ctx.storage.set("total_events_emitted", str(total))
    ctx.storage.set("last_poll_events", str(len(all_events)))
    ctx.storage.set("last_poll_time", datetime.now(timezone.utc).isoformat())

    logger.info(
        "Poll cycle %d complete — %d event(s) detected, %d sent",
        poll_count,
        len(all_events),
        sent_count,
    )


# ── Chat Protocol for ASI:One Discoverability ───────────────────────────


async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
    """Handle ASI:One chat queries about the Context Sentinel."""
    poll_count = ctx.storage.get("poll_count") or "0"
    last_events = ctx.storage.get("last_poll_events") or "0"
    last_poll = ctx.storage.get("last_poll_time") or "never"
    total_events = ctx.storage.get("total_events_emitted") or "0"

    return (
        "I'm the Context Sentinel — I monitor your Google Calendar, Gmail, and Slack "
        "for real-time context changes.\n\n"
        f"Status:\n"
        f"- Polls completed: {poll_count}\n"
        f"- Events in last poll: {last_events}\n"
        f"- Total events emitted: {total_events}\n"
        f"- Last poll: {last_poll}\n"
        f"- Polling interval: {SENTINEL_POLL_INTERVAL}s\n\n"
        "When I detect changes (meeting ended early, new email, schedule conflict), "
        "I emit ContextChangeEvent messages to the Disruption Detector for "
        "intelligent rescheduling."
    )


chat_proto = create_chat_protocol(
    "Context Sentinel",
    "Monitors Google Calendar, Gmail, and Slack for real-time context changes and schedule disruptions",
    _chat_handler,
)
agent.include(chat_proto, publish_manifest=True)


# ── Entry Point ─────────────────────────────────────────────────────────


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Context Sentinel agent address: %s", agent.address)
    agent.run()
