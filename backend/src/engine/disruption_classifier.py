"""Disruption classification logic — pure functions, no uagents dependency.

Used by both the Disruption Detector agent and the FastAPI server.
"""

from __future__ import annotations


# Severity classification rules
SEVERITY_RULES = {
    "meeting_ended_early": {
        "base": "minor",
        "escalate_if_tasks_affected": 3,
    },
    "new_email": {
        "base": "minor",
        "escalate_if_urgent": True,
    },
    "schedule_conflict": {
        "base": "major",
        "escalate_if_tasks_affected": 4,
    },
    "task_completed": {
        "base": "minor",
    },
    "meeting_overrun": {
        "base": "major",
        "escalate_if_tasks_affected": 3,
    },
    "cancelled_meeting": {
        "base": "minor",
        "escalate_if_tasks_affected": 0,
    },
}

# Default user profile values
DEFAULT_PROFILE = {
    "peak_hours": [9, 10, 14, 15],
    "avg_task_durations": {"email": 5, "deep_work": 52, "admin": 15},
    "energy_curve": [2, 2, 1, 1, 1, 1, 2, 3, 4, 5, 5, 4, 3, 3, 4, 5, 4, 3, 3, 2, 2, 2, 1, 1],
    "adherence_score": 0.7,
    "estimation_bias": 1.2,
    "automation_comfort": {"email": 0.9, "slack": 0.8, "booking": 0.5},
}


def classify_severity(
    event_type: str,
    affected_task_ids: list,
    metadata: dict,
) -> str:
    """Classify disruption severity based on event type and impact."""
    rules = SEVERITY_RULES.get(event_type, {"base": "minor"})
    severity = rules["base"]
    num_affected = len(affected_task_ids)

    escalate_threshold = rules.get("escalate_if_tasks_affected")
    if escalate_threshold is not None and num_affected >= escalate_threshold:
        if severity == "minor":
            severity = "major"
        elif severity == "major":
            severity = "critical"

    if rules.get("escalate_if_urgent") and metadata.get("urgent"):
        severity = "major" if severity == "minor" else "critical"

    return severity


def calculate_freed_minutes(event_type: str, metadata: dict) -> int:
    """Calculate time gained or lost from the context change.

    Positive = gained time, Negative = lost time.
    """
    if event_type in ("meeting_ended_early", "cancelled_meeting"):
        return max(int(metadata.get("freed_minutes", 15)), 0)

    if event_type in ("meeting_overrun", "schedule_conflict"):
        return -abs(int(metadata.get("lost_minutes", 30)))

    if event_type == "task_completed":
        return max(int(metadata.get("saved_minutes", 0)), 0)

    if event_type == "new_email":
        if metadata.get("urgent"):
            return -15
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
    return "swap_in"
