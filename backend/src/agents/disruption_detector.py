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
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)

# Default user profile when Profiler Agent is unavailable
DEFAULT_PROFILE = UserProfile(
    peak_hours=[9, 10, 14, 15],
    avg_task_durations={"email": 5, "deep_work": 52, "admin": 15},
    energy_curve=[2, 2, 1, 1, 1, 1, 2, 3, 4, 5, 5, 4, 3, 3, 4, 5, 4, 3, 3, 2, 2, 2, 1, 1],
    adherence_score=0.7,
    distraction_patterns={"slack_notification": 0.7, "phone_check": 0.4},
    estimation_bias=1.2,
    automation_comfort={"email": 0.9, "slack": 0.8, "booking": 0.5},
)

# Severity classification rules
SEVERITY_RULES = {
    "meeting_ended_early": {
        "base": "minor",
        "escalate_if_tasks_affected": 3,  # → major if 3+ tasks freed
    },
    "new_email": {
        "base": "minor",
        "escalate_if_urgent": True,
    },
    "schedule_conflict": {
        "base": "major",
        "escalate_if_tasks_affected": 4,  # → critical if 4+ tasks cascaded
    },
    "task_completed": {
        "base": "minor",
    },
    "meeting_overrun": {
        "base": "major",
        "escalate_if_tasks_affected": 3,  # → critical if 3+ cascaded
    },
    "cancelled_meeting": {
        "base": "minor",
        "escalate_if_tasks_affected": 0,  # always minor (it's a gain)
    },
}


def classify_severity(event: ContextChangeEvent, profile: UserProfile) -> str:
    """Classify disruption severity based on event type and impact."""
    rules = SEVERITY_RULES.get(event.event_type, {"base": "minor"})
    severity = rules["base"]
    num_affected = len(event.affected_task_ids)

    escalate_threshold = rules.get("escalate_if_tasks_affected")
    if escalate_threshold is not None and num_affected >= escalate_threshold:
        if severity == "minor":
            severity = "major"
        elif severity == "major":
            severity = "critical"

    # Check for urgent metadata
    if rules.get("escalate_if_urgent") and event.metadata.get("urgent"):
        severity = "major" if severity == "minor" else "critical"

    return severity


def calculate_freed_minutes(event: ContextChangeEvent) -> int:
    """Calculate time gained or lost from the context change.

    Positive = gained time (meeting ended early, cancellation)
    Negative = lost time (meeting overrun, conflict)
    """
    meta = event.metadata

    if event.event_type in ("meeting_ended_early", "cancelled_meeting"):
        return max(int(meta.get("freed_minutes", 15)), 0)

    if event.event_type in ("meeting_overrun", "schedule_conflict"):
        return -abs(int(meta.get("lost_minutes", 30)))

    if event.event_type == "task_completed":
        # Time saved if completed ahead of estimate
        return max(int(meta.get("saved_minutes", 0)), 0)

    if event.event_type == "new_email":
        # Urgent emails cost attention
        if meta.get("urgent"):
            return -15  # ~15min disruption cost
        return 0

    return 0


def determine_action(severity: str, freed_minutes: int) -> str:
    """Determine recommended action based on severity and time impact."""
    if severity == "critical":
        return "reschedule_all"
    if freed_minutes > 0:
        return "swap_in"
    if freed_minutes < 0:
        if severity == "major":
            return "swap_out"
        return "delegate"
    return "swap_in"  # no time change, but maybe reorder


# ── Agent Setup ──────────────────────────────────────────────────────────

agent = Agent(
    name="disruption_detector",
    seed=DISRUPTION_DETECTOR_SEED,
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)

# Store profile (updated when Profiler responds)
_cached_profile: UserProfile = DEFAULT_PROFILE


@agent.on_message(ContextChangeEvent)
async def handle_context_change(ctx: Context, sender: str, event: ContextChangeEvent):
    """Process a context change and emit a DisruptionEvent."""
    logger.info(f"Received ContextChangeEvent: {event.event_type} from {sender}")

    profile = _cached_profile

    # Classify
    severity = classify_severity(event, profile)
    freed_minutes = calculate_freed_minutes(event)
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
    _cached_profile = profile
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
