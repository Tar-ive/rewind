"""Energy Monitor Agent.

Infers user energy level (1-5) from behavioral signals and time-of-day
patterns. Provides EnergyLevel to Scheduler Kernel so it never schedules
tasks with energy_cost > energy_level.

Three signal sources:
1. Time-of-day heuristic (circadian baseline)
2. Task velocity tracking (completion speed vs. estimates)
3. User-reported energy (high-confidence override, decays over 2h)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import redis
from uagents import Agent, Context

from src.config.settings import ENERGY_MONITOR_SEED, REDIS_URL
from src.models.messages import (
    EnergyLevel,
    EnergyQuery,
    TaskCompletion,
    UserProfile,
)
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

# Default circadian energy curve (24 hours, index = hour of day)
# Models typical human energy: low overnight, morning ramp, post-lunch dip,
# afternoon peak, evening decline.
DEFAULT_ENERGY_CURVE: list[int] = [
    1, 1, 1, 1, 1, 1,  # 00-05: sleep
    2, 3, 4, 4, 5, 4,  # 06-11: morning ramp + peak
    3, 3, 4, 5, 4, 3,  # 12-17: post-lunch dip + afternoon peak
    3, 2, 2, 2, 1, 1,  # 18-23: evening decline
]

# Redis keys
COMPLETIONS_KEY = "energy:completions"
USER_REPORTED_KEY = "energy:user_reported"
USER_REPORTED_TS_KEY = "energy:user_reported_ts"

# Velocity window: only consider completions from the last 2 hours
VELOCITY_WINDOW_SECONDS = 2 * 60 * 60

# User-reported override decay: valid for 2 hours
USER_REPORTED_DECAY_SECONDS = 2 * 60 * 60

# If no completions in this many seconds, assume energy dip
INACTIVITY_THRESHOLD_SECONDS = 30 * 60


# ── Agent Setup ──────────────────────────────────────────────────────────

agent = Agent(
    name="energy_monitor",
    seed=ENERGY_MONITOR_SEED,
    port=8003,
    endpoint=["http://localhost:8003/submit"],
)

# Cached energy curve (overridden when Profiler sends UserProfile)
_energy_curve: list[int] = list(DEFAULT_ENERGY_CURVE)
_has_profiler_curve: bool = False


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


# ── Energy Inference ─────────────────────────────────────────────────────

def _get_time_based_energy(hour: int) -> int:
    """Get baseline energy from circadian curve for given hour."""
    return _energy_curve[hour % 24]


def _get_velocity_adjustment(r: redis.Redis) -> tuple[int, int]:
    """Compute energy adjustment from recent task completion velocity.

    Returns (adjustment, completion_count) where adjustment is -1, 0, or +1.
    """
    now = time.time()
    window_start = now - VELOCITY_WINDOW_SECONDS

    # Get completions within the velocity window
    entries = r.zrangebyscore(COMPLETIONS_KEY, window_start, now)

    if not entries:
        # Check if there are ANY completions ever (to distinguish
        # "no tasks today" from "stalled")
        all_entries = r.zcard(COMPLETIONS_KEY)
        if all_entries > 0:
            # Had completions before but none recently → possible stall
            latest = r.zrange(COMPLETIONS_KEY, -1, -1, withscores=True)
            if latest:
                last_ts = latest[0][1]
                if now - last_ts > INACTIVITY_THRESHOLD_SECONDS:
                    return -1, 0
        return 0, 0

    # Parse completions: "task_id:actual_minutes:estimated_minutes"
    total_actual = 0
    total_estimated = 0
    count = 0

    for entry in entries:
        parts = entry.split(":")
        if len(parts) >= 3:
            try:
                actual = float(parts[1])
                estimated = float(parts[2])
                total_actual += actual
                total_estimated += estimated
                count += 1
            except (ValueError, IndexError):
                continue

    if count == 0 or total_estimated == 0:
        return 0, 0

    # Velocity ratio: < 1.0 means faster than expected, > 1.0 means slower
    velocity_ratio = total_actual / total_estimated

    if velocity_ratio < 0.8:
        # Completing tasks 20%+ faster → energy surplus
        return 1, count
    elif velocity_ratio > 1.3:
        # Taking 30%+ longer → energy deficit
        return -1, count
    else:
        return 0, count


def _get_user_reported(r: redis.Redis) -> tuple[int | None, float]:
    """Check for a recent user-reported energy level.

    Returns (level_or_None, seconds_since_report).
    """
    reported = r.get(USER_REPORTED_KEY)
    reported_ts = r.get(USER_REPORTED_TS_KEY)

    if reported is None or reported_ts is None:
        return None, 0.0

    age = time.time() - float(reported_ts)
    if age > USER_REPORTED_DECAY_SECONDS:
        return None, age

    return int(reported), age


def compute_energy(r: redis.Redis | None = None) -> EnergyLevel:
    """Compute current energy level from all signal sources."""
    r = r or _get_redis()
    now = datetime.now(timezone.utc)
    hour = now.hour

    # Check user-reported first (highest priority)
    user_level, age = _get_user_reported(r)
    if user_level is not None:
        # Confidence decays linearly from 0.9 to 0.5 over the decay window
        decay_factor = 1.0 - (age / USER_REPORTED_DECAY_SECONDS)
        confidence = 0.5 + 0.4 * decay_factor
        return EnergyLevel(
            level=max(1, min(5, user_level)),
            confidence=round(confidence, 2),
            source="user_reported",
        )

    # Time-based baseline
    base_level = _get_time_based_energy(hour)

    # Velocity adjustment
    velocity_adj, completion_count = _get_velocity_adjustment(r)
    final_level = max(1, min(5, base_level + velocity_adj))

    # Confidence depends on data quality
    if _has_profiler_curve and completion_count >= 3:
        confidence = 0.8
        source = "inferred"
    elif _has_profiler_curve:
        confidence = 0.7
        source = "inferred"
    elif completion_count >= 3:
        confidence = 0.6
        source = "inferred"
    else:
        confidence = 0.4
        source = "time_based"

    return EnergyLevel(
        level=final_level,
        confidence=round(confidence, 2),
        source=source,
    )


def record_completion(
    task_id: str,
    actual_minutes: float,
    estimated_minutes: float,
    r: redis.Redis | None = None,
) -> None:
    """Record a task completion for velocity tracking."""
    r = r or _get_redis()
    now = time.time()
    entry = f"{task_id}:{actual_minutes}:{estimated_minutes}"
    r.zadd(COMPLETIONS_KEY, {entry: now})

    # Trim old entries outside the velocity window
    cutoff = now - VELOCITY_WINDOW_SECONDS
    r.zremrangebyscore(COMPLETIONS_KEY, "-inf", cutoff)


def record_user_reported(level: int, r: redis.Redis | None = None) -> None:
    """Record a user-reported energy level."""
    r = r or _get_redis()
    r.set(USER_REPORTED_KEY, str(max(1, min(5, level))))
    r.set(USER_REPORTED_TS_KEY, str(time.time()))


# ── Message Handlers ─────────────────────────────────────────────────────

@agent.on_message(EnergyQuery)
async def handle_energy_query(ctx: Context, sender: str, query: EnergyQuery):
    """Compute and return current energy level."""
    r = _get_redis()
    energy = compute_energy(r)
    logger.info(
        f"EnergyQuery from {sender}: level={energy.level}, "
        f"confidence={energy.confidence}, source={energy.source}"
    )
    await ctx.send(sender, energy)


@agent.on_message(TaskCompletion)
async def handle_task_completion(ctx: Context, sender: str, completion: TaskCompletion):
    """Record task completion for velocity tracking."""
    if completion.status != "executed":
        return

    actual = completion.result.get("actual_minutes", 0)
    estimated = completion.result.get("estimated_minutes", 0)

    if actual > 0 and estimated > 0:
        r = _get_redis()
        record_completion(completion.task_id, actual, estimated, r)
        logger.info(
            f"Recorded completion: {completion.task_id} "
            f"({actual}min actual vs {estimated}min estimated)"
        )


@agent.on_message(UserProfile)
async def handle_profile_update(ctx: Context, sender: str, profile: UserProfile):
    """Cache the energy curve from Profiler Agent."""
    global _energy_curve, _has_profiler_curve
    if profile.energy_curve and len(profile.energy_curve) == 24:
        _energy_curve = list(profile.energy_curve)
        _has_profiler_curve = True
        logger.info("Updated energy curve from Profiler Agent")


# ── Startup ──────────────────────────────────────────────────────────────

@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Log agent startup."""
    logger.info(f"Energy Monitor started. Address: {agent.address}")
    logger.info(f"Using {'profiler' if _has_profiler_curve else 'default'} energy curve")


# ── Chat Protocol for ASI:One ────────────────────────────────────────────

async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
    r = _get_redis()
    energy = compute_energy(r)
    velocity_adj, count = _get_velocity_adjustment(r)

    adj_desc = ""
    if velocity_adj > 0:
        adj_desc = " Your recent task velocity suggests higher energy."
    elif velocity_adj < 0:
        adj_desc = " Your recent task velocity suggests lower energy."

    return (
        f"Your current energy level is {energy.level}/5 "
        f"(confidence: {energy.confidence}, source: {energy.source}).{adj_desc} "
        f"Based on {count} recent task completions."
    )


chat_proto = create_chat_protocol(
    "Energy Monitor",
    "Infers your current energy level from behavioral signals and time-of-day patterns",
    _chat_handler,
)
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent.run()
