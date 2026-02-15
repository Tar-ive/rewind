"""Context Sentinel Agent — monitors real-time context signals.

Polls Google Calendar, Gmail, Slack APIs. Detects changes.
Emits ContextChangeEvent to Disruption Detector.
"""

import asyncio
from datetime import datetime, timezone

from uagents import Agent, Context, Protocol

from protocols.chat_setup import create_chat_protocol
from protocols.models import ContextChangeEvent
from protocols.rewind_protocol import rewind_protocol_spec
from integrations.google_calendar import GoogleCalendarClient
from integrations.gmail_client import GmailClient
from config.settings import (
    SENTINEL_SEED,
    SENTINEL_PORT,
    DETECTOR_ADDRESS,
    SENTINEL_MAILBOX,
)

# ─── Create Agent ───
sentinel = Agent(
    name="context_sentinel",
    port=SENTINEL_PORT,
    seed=SENTINEL_SEED,
    mailbox=SENTINEL_MAILBOX,  # True for Agentverse registration
)

# ─── Rewind Protocol (sender role) ───
rewind_proto = Protocol(spec=rewind_protocol_spec, role="sentinel")

# ─── State ───
calendar_cache = {}


# ─── Polling Logic (runs on interval) ───
@sentinel.on_interval(period=30.0)
async def poll_calendar(ctx: Context):
    """Poll Google Calendar every 30 seconds for changes."""
    cal_client = GoogleCalendarClient()
    current_events = await cal_client.get_today_events()

    # Diff against cache
    changes = diff_calendar(calendar_cache, current_events)
    calendar_cache.update({e["id"]: e for e in current_events})

    for change in changes:
        event = ContextChangeEvent(
            event_type=change["type"],
            source="google_calendar",
            timestamp=datetime.now(timezone.utc).isoformat(),
            affected_task_ids=change.get("affected_tasks", []),
            metadata=change.get("metadata", {}),
        )
        ctx.logger.info(f"[Sentinel] Detected: {event.event_type}")
        await ctx.send(DETECTOR_ADDRESS, event)


def diff_calendar(old: dict, new: list) -> list:
    """Compare cached vs current calendar state. Returns list of changes."""
    changes = []
    new_map = {e["id"]: e for e in new}

    for eid, old_event in old.items():
        if eid in new_map:
            new_event = new_map[eid]
            if old_event.get("end") != new_event.get("end"):
                changes.append({
                    "type": "meeting_extended" if new_event["end"] > old_event["end"] else "meeting_ended_early",
                    "metadata": {"old_end": old_event["end"], "new_end": new_event["end"], "event_id": eid},
                    "affected_tasks": [],  # Kernel resolves this
                })
        else:
            changes.append({
                "type": "meeting_cancelled",
                "metadata": {"event_id": eid},
                "affected_tasks": [],
            })

    for eid in new_map:
        if eid not in old:
            changes.append({
                "type": "new_event",
                "metadata": new_map[eid],
                "affected_tasks": [],
            })

    return changes


# ─── Chat Protocol (ASI:One discoverability) ───
async def chat_handler(ctx: Context, sender: str, user_text: str) -> str:
    """Handle ASI:One chat queries about calendar status."""
    cal_client = GoogleCalendarClient()
    events = await cal_client.get_today_events()
    summary = "\n".join([f"- {e['summary']} ({e['start']} → {e['end']})" for e in events])
    return f"Here's your calendar for today:\n{summary}"

chat_proto = create_chat_protocol("context_sentinel", chat_handler)

# ─── Include Protocols ───
sentinel.include(rewind_proto, publish_manifest=True)
sentinel.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    sentinel.run()