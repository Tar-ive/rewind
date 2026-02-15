"""Disruption Detector Agent.

Receives ContextChangeEvent from Context Sentinel, classifies disruption
severity (minor/major/critical), calculates freed/lost minutes, and emits
DisruptionEvent to Scheduler Kernel.

Optionally queries Profiler Agent for user patterns to inform classification.
Falls back to defaults if Profiler is unavailable.
"""

from __future__ import annotations

import logging

from uagents import Agent, Context

from src.config.settings import (
    DISRUPTION_DETECTOR_SEED,
    SCHEDULER_KERNEL_ADDRESS,
)
from src.models.messages import (
    ContextChangeEvent,
    DisruptionEvent,
    UserProfile,
)
from src.engine.disruption_classifier import (
    classify_severity,
    calculate_freed_minutes,
    determine_action,
    DEFAULT_PROFILE,
)
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)

# ── Agent Setup ──────────────────────────────────────────────────────────

agent = Agent(
    name="disruption_detector",
    seed=DISRUPTION_DETECTOR_SEED,
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)

# Store profile (updated when Profiler responds)
_cached_profile: dict = dict(DEFAULT_PROFILE)


@agent.on_message(ContextChangeEvent)
async def handle_context_change(ctx: Context, sender: str, event: ContextChangeEvent):
    """Process a context change and emit a DisruptionEvent."""
    logger.info(f"Received ContextChangeEvent: {event.event_type} from {sender}")

    # Classify
    severity = classify_severity(event.event_type, event.affected_task_ids, event.metadata)
    freed_minutes = calculate_freed_minutes(event.event_type, event.metadata)
    action = determine_action(severity, freed_minutes)

    # Build summary
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

    logger.info(f"Emitting DisruptionEvent: {severity} → {action}")

    # Send to Scheduler Kernel
    await ctx.send(SCHEDULER_KERNEL_ADDRESS, disruption)


@agent.on_message(UserProfile)
async def handle_profile_update(ctx: Context, sender: str, profile: UserProfile):
    """Update cached profile when Profiler Agent sends new data."""
    global _cached_profile
    _cached_profile = {
        "peak_hours": profile.peak_hours,
        "estimation_bias": profile.estimation_bias,
        "automation_comfort": profile.automation_comfort,
    }
    logger.info("Updated cached user profile from Profiler Agent")


# Chat Protocol for ASI:One discoverability
async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
    return (
        "I'm the Disruption Detector. I monitor your calendar, email, and Slack "
        "for context changes and classify disruptions by severity (minor/major/critical). "
        "I automatically trigger schedule recovery when disruptions occur."
    )

chat_proto = create_chat_protocol(
    "Disruption Detector",
    "Detects and classifies disruptions to your schedule",
    _chat_handler,
)
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent.run()
