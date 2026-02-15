"""Typed message models for all Rewind inter-agent communication.

All models inherit from uagents Model (which is pydantic BaseModel).
These provide schema validation, serialization, and compose into
ProtocolSpecification for Agentverse registration.

Reference: https://github.com/fetchai/uAgents/blob/main/python/uagents-core/uagents_core/protocol.py
"""

from uagents import Model


# ─── Context Sentinel → Disruption Detector ───
class ContextChangeEvent(Model):
    """Emitted by Context Sentinel when a real-time signal changes."""
    event_type: str          # meeting_ended_early | new_email | schedule_conflict | task_completed | meeting_extended
    source: str              # google_calendar | gmail | slack
    timestamp: str           # ISO 8601
    affected_task_ids: list  # task IDs impacted by this change
    metadata: dict           # source-specific data (new end time, email subject, sender, etc.)


# ─── Profiler Agent → any requester ───
class UserProfileRequest(Model):
    """Request to Profiler Agent for current user profile."""
    user_id: str
    fields_requested: list   # e.g. ["peak_hours", "estimation_bias"] or ["all"]


class UserProfile(Model):
    """Returned by Profiler Agent with learned behavioral data."""
    peak_hours: list              # e.g. [9, 10, 14, 15] (24h format)
    avg_task_durations: dict      # {'email': 5, 'deep_work': 52, 'admin': 15}
    energy_curve: list            # 24-element array: predicted energy per hour (1-5)
    adherence_score: float        # 0.0-1.0
    distraction_patterns: dict    # {'slack_notification': 0.7, 'phone_check': 0.4}
    estimation_bias: float        # >1.0 means user underestimates task duration
    automation_comfort: dict      # {'email': 0.9, 'slack': 0.8, 'booking': 0.5}


# ─── Disruption Detector → Scheduler Kernel ───
class DisruptionEvent(Model):
    """Emitted by Disruption Detector after classifying a context change."""
    severity: str                 # minor | major | critical
    affected_task_ids: list       # task IDs cascaded by this disruption
    freed_minutes: int            # positive = gained time, negative = lost time
    recommended_action: str       # swap_in | swap_out | reschedule_all | delegate
    context_summary: str          # human-readable explanation for UI/logging


# ─── Energy Monitor → Scheduler Kernel ───
class EnergyLevelRequest(Model):
    """Request to Energy Monitor for current energy level."""
    user_id: str


class EnergyLevel(Model):
    """Current inferred energy level of the user."""
    level: int                    # 1-5
    confidence: float             # 0.0-1.0
    source: str                   # inferred | user_reported | time_based


# ─── Scheduler Kernel → Frontend (via WebSocket) ───
class SwapOperation(Model):
    """A single schedule swap operation for logging/animation."""
    action: str                   # swap_in | swap_out | preempt | delegate
    task_id: str
    reason: str                   # human-readable
    new_time_slot: str            # ISO 8601 start time (empty string if swapped out)


class UpdatedSchedule(Model):
    """The full updated schedule after a disruption + reschedule cycle."""
    schedule: list                # Ordered list of task dicts with time slots
    swap_operations: list         # List of SwapOperation dicts
    time_saved_minutes: int       # Running total of time saved by automation
    tasks_delegated: int          # Count of tasks sent to GhostWorker


# ─── Scheduler Kernel → GhostWorker ───
class DelegationTask(Model):
    """A task delegated to GhostWorker for autonomous execution."""
    task_id: str
    task_type: str                # email_reply | slack_message | uber_book | cancel_appointment
    context: dict                 # all info: recipient, thread, tone, constraints
    approval_required: bool       # True = draft only, False = auto-execute
    max_cost_fet: float           # spending limit for this task


# ─── GhostWorker → Scheduler Kernel ───
class TaskCompletion(Model):
    """Result from GhostWorker after executing/drafting a task."""
    task_id: str
    status: str                   # drafted | executed | failed
    result: dict                  # output data (draft text, confirmation URL, error msg)
    cost_fet: float               # actual cost charged via Payment Protocol