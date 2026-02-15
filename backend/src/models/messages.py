"""Typed message models for inter-agent communication.

All messages are uAgents Model subclasses providing schema validation
and serialization across the Fetch.ai ecosystem.
"""

from uagents import Model


class ContextChangeEvent(Model):
    """Emitted by Context Sentinel when a real-time signal changes."""
    event_type: str          # meeting_ended_early | new_email | schedule_conflict | task_completed
    source: str              # google_calendar | gmail | slack
    timestamp: str           # ISO 8601
    affected_task_ids: list  # task IDs impacted
    metadata: dict           # source-specific data (new end time, email subject, etc.)


class UserProfile(Model):
    """Returned by Profiler Agent with learned behavioral patterns."""
    peak_hours: list         # [9, 10, 14, 15] (24h format)
    avg_task_durations: dict # {'email': 5, 'deep_work': 52, 'admin': 15}
    energy_curve: list       # 24-element array: predicted energy per hour
    adherence_score: float   # 0.0-1.0, how well user follows schedule
    distraction_patterns: dict  # {'slack_notification': 0.7, 'phone_check': 0.4}
    estimation_bias: float   # >1.0 means user underestimates duration
    automation_comfort: dict # {'email': 0.9, 'slack': 0.8, 'booking': 0.5}


class ProfileQuery(Model):
    """Request to Profiler Agent for user patterns."""
    query_type: str          # full_profile | peak_hours | estimation_bias
    user_id: str


class DisruptionEvent(Model):
    """Emitted by Disruption Detector after classifying a context change."""
    severity: str            # minor | major | critical
    affected_task_ids: list
    freed_minutes: int       # positive = gained time, negative = lost time
    recommended_action: str  # swap_in | swap_out | reschedule_all | delegate
    context_summary: str     # human-readable explanation


class EnergyLevel(Model):
    """Returned by Energy Monitor with current energy state."""
    level: int               # 1-5
    confidence: float        # 0.0-1.0
    source: str              # inferred | user_reported | time_based


class EnergyQuery(Model):
    """Request to Energy Monitor for current energy level."""
    user_id: str
    timestamp: str           # ISO 8601


class SwapOperation(Model):
    """A single swap action performed by the MTS."""
    action: str              # swap_in | swap_out | preempt | delegate
    task_id: str
    reason: str              # human-readable
    new_time_slot: str       # ISO 8601 start time (empty string if swapped out)


class UpdatedSchedule(Model):
    """Emitted by Scheduler Kernel after rescheduling."""
    schedule: list           # list of scheduled task dicts with time slots
    swaps: list              # list of SwapOperation dicts
    timestamp: str           # ISO 8601
    trigger: str             # disruption | daily_plan | manual


class DelegationTask(Model):
    """Sent to GhostWorker for autonomous execution."""
    task_id: str
    task_type: str           # email_reply | slack_message | uber_book | cancel_appointment
    context: dict            # all info needed: recipient, thread, tone, constraints
    approval_required: bool  # True = draft only, False = auto-execute
    max_cost_fet: float      # spending limit for this task


class TaskCompletion(Model):
    """Returned by GhostWorker after task execution."""
    task_id: str
    status: str              # drafted | executed | failed
    result: dict             # output data (draft text, confirmation, error)
    cost_fet: float          # actual cost charged


class ScheduleRequest(Model):
    """Request to Scheduler Kernel for on-demand scheduling."""
    action: str              # plan_day | reoptimize | add_task
    payload: dict            # action-specific data


class ProfilerGrouping(Model):
    """User classification on the achiever spectrum (exclusive — high bar)."""
    archetype: str           # "compounding_builder" | "reliable_operator" | "emerging_talent" | "at_risk"
    execution_score: float   # 0.0-1.0 (x-axis of success function)
    growth_score: float      # 0.0-1.0 (y-axis of success function)
    confidence: float        # 0.0-1.0
    traits: dict             # detailed trait breakdown


class ProfileUpdateEvent(Model):
    """Emitted when profiler detects significant pattern change."""
    changed_fields: list     # which profile fields changed
    magnitude: float         # 0.0-1.0 how much changed
    timestamp: str           # ISO 8601
