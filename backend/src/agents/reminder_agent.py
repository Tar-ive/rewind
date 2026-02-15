"""Reminder Agent — Agentic Proactive Notifications via Claude LLM.

Uses direct Anthropic API calls to evaluate the current schedule context
and decide intelligently when/what to remind the user about. No hardcoded
rules — the LLM reasons about timing, urgency, energy, and user patterns.

Publishes ReminderNotification events to Redis for server relay to
WebSocket clients (web dashboard + iOS bridge app).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis

from src.config.settings import (
    ANTHROPIC_API_KEY,
    REDIS_URL,
)
from src.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


# ── System Prompt ────────────────────────────────────────────────────────

REMINDER_SYSTEM_PROMPT = """\
You are the Reminder Agent for Rewind, an intelligent scheduling system.

Your job: given the user's current schedule state, current time, energy level,
and behavioral profile, decide whether the user needs any notifications RIGHT NOW.

## Reminder Types
- "upcoming_task": A task or event is approaching and the user should prepare.
- "check_in": A task should have started by now — ask if the user has begun.
- "completion_check": A task's estimated duration has elapsed — ask if it's done.
- "transition": The current task is ending and the next one begins soon — prompt the switch.

## Decision Criteria
- Consider the user's adherence_score: low adherence means they benefit from more nudges; \
high adherence means they're self-directed and need fewer.
- Consider energy level: don't nag a fatigued user (energy <= 2) about low-priority tasks. \
Only remind about P0/P1 tasks when energy is low.
- Respect snooze: if a task is marked as snoozed, DO NOT remind about it.
- Respect cooldowns: if a task was reminded about recently (< 10 minutes), skip it unless \
the situation has changed (e.g., deadline is now imminent).
- Be contextual and human: messages should sound like a helpful assistant, not a robot timer.
- Only generate reminders that are genuinely useful. If nothing warrants attention, say so.

## Response Format
Return ONLY valid JSON (no markdown, no explanation):
{
  "should_remind": true | false,
  "reasoning": "brief explanation of your decision",
  "reminders": [
    {
      "type": "upcoming_task" | "check_in" | "completion_check" | "transition",
      "task_id": "the task ID",
      "title": "short headline (5-8 words)",
      "message": "natural, conversational reminder message",
      "urgency": "low" | "medium" | "high",
      "actions": ["start_task", "snooze", "mark_complete", "skip"]
    }
  ]
}

If should_remind is false, reminders should be an empty array.
"""


# ── Context Builder ──────────────────────────────────────────────────────


def build_evaluation_context(
    active_tasks: List[Task],
    energy_json: Optional[str],
    profile_json: Optional[str],
    calendar_events_json: Optional[str],
    now: datetime,
    r: redis.Redis,
) -> str:
    """Build a detailed context prompt for the LLM from Redis state.

    Gathers all relevant signals — active tasks, energy, profile, calendar,
    reminder history, and snooze state — into a single prompt string.
    """
    lines = [f"Current time: {now.isoformat()}"]
    lines.append(f"Day of week: {now.strftime('%A')}")
    lines.append(f"Hour: {now.hour}:{now.strftime('%M')}")
    lines.append("")

    # Energy
    if energy_json:
        try:
            energy = json.loads(energy_json)
            lines.append(f"Energy level: {energy.get('level', '?')}/5 "
                         f"(confidence: {energy.get('confidence', '?')}, "
                         f"source: {energy.get('source', '?')})")
        except (json.JSONDecodeError, TypeError):
            lines.append("Energy level: unknown")
    else:
        lines.append("Energy level: unknown")
    lines.append("")

    # User profile summary
    if profile_json:
        try:
            profile = json.loads(profile_json)
            user_profile = profile.get("user_profile", {})
            lines.append("User profile:")
            lines.append(f"  Adherence score: {user_profile.get('adherence_score', '?')}")
            lines.append(f"  Peak hours: {user_profile.get('peak_hours', '?')}")
            lines.append(f"  Estimation bias: {user_profile.get('estimation_bias', '?')}x")
        except (json.JSONDecodeError, TypeError):
            lines.append("User profile: unavailable")
    else:
        lines.append("User profile: unavailable")
    lines.append("")

    # Calendar events
    if calendar_events_json:
        try:
            events = json.loads(calendar_events_json)
            if events:
                lines.append("Upcoming calendar events:")
                for ev in events[:10]:
                    start = ev.get("start", {}).get("dateTime", ev.get("start", "?"))
                    end = ev.get("end", {}).get("dateTime", ev.get("end", "?"))
                    summary = ev.get("summary", "Untitled")
                    lines.append(f"  - {summary}: {start} to {end}")
            else:
                lines.append("No upcoming calendar events.")
        except (json.JSONDecodeError, TypeError):
            lines.append("Calendar events: unavailable")
    else:
        lines.append("Calendar events: unavailable")
    lines.append("")

    # Active tasks with reminder metadata
    if active_tasks:
        lines.append(f"Active tasks ({len(active_tasks)}):")
        for task in active_tasks:
            status_str = task.status.name if hasattr(task.status, 'name') else str(task.status)
            line = (f"  - [{task.task_id}] {task.title} "
                    f"(P{task.priority}, status: {status_str}, "
                    f"duration: {task.estimated_duration}min, "
                    f"energy_cost: {task.energy_cost}/5")

            if task.deadline:
                line += f", deadline: {task.deadline}"
            if task.preferred_start:
                line += f", preferred_start: {task.preferred_start}"
            line += ")"

            # Last reminded
            last_sent = r.get(f"reminder:last_sent:{task.task_id}")
            if last_sent:
                line += f"\n    Last reminded: {last_sent}"
            else:
                line += "\n    Last reminded: never"

            # Snoozed?
            is_snoozed = r.exists(f"reminder:snoozed:{task.task_id}")
            if is_snoozed:
                ttl = r.ttl(f"reminder:snoozed:{task.task_id}")
                line += f" | SNOOZED (expires in {ttl}s)"

            lines.append(line)
    else:
        lines.append("No active tasks.")

    return "\n".join(lines)


# ── Claude API Caller ────────────────────────────────────────────────────


async def call_claude(system_prompt: str, user_prompt: str) -> str:
    """Call Claude via direct Anthropic API for fast reasoning.

    Uses claude-sonnet-4-5-20250929 for low latency and cost.
    """
    import anthropic

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not configured — cannot evaluate reminders")
        return '{"should_remind": false, "reasoning": "API key not configured", "reminders": []}'

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        return '{"should_remind": false, "reasoning": "API call failed", "reminders": []}'


# ── Response Parser ──────────────────────────────────────────────────────


def parse_reminder_response(llm_output: str) -> List[Dict[str, Any]]:
    """Extract structured reminder decisions from LLM JSON response.

    Handles malformed responses gracefully — returns empty list on failure.
    """
    try:
        # Strip markdown code fences if present
        text = llm_output.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)

        if not data.get("should_remind", False):
            return []

        reminders = data.get("reminders", [])
        validated = []
        for rem in reminders:
            validated.append({
                "type": rem.get("type", "check_in"),
                "task_id": rem.get("task_id", ""),
                "title": rem.get("title", "Reminder"),
                "message": rem.get("message", ""),
                "urgency": rem.get("urgency", "medium"),
                "actions": rem.get("actions", []),
            })
        return validated

    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Failed to parse reminder LLM response: %s", exc)
        logger.debug("Raw LLM output: %s", llm_output[:500])
        return []
