"""Profiler Agent — Behavioral Intelligence Engine.

Learns implicit behavioral patterns from daily goals, social media, task
completion logs, resume data, and reflections.  Produces:

1. UserProfile (peak_hours, avg_task_durations, energy_curve, adherence_score,
   distraction_patterns, estimation_bias, automation_comfort)
2. ProfilerGrouping (archetype on the achiever spectrum + 2-axis success plot)
3. ProfileUpdateEvent (emitted when significant drift detected)

The profiler is consumed by every other agent in the Rewind system.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Population-level defaults (cold-start)
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_PEAK_HOURS: list[int] = [9, 10, 14, 15]
DEFAULT_ENERGY_CURVE: list[int] = [
    1, 1, 1, 1, 1, 1,   # 00-05: sleep
    2, 3, 4, 4, 5, 4,   # 06-11: morning ramp
    3, 3, 4, 5, 4, 3,   # 12-17: afternoon
    3, 2, 2, 2, 1, 1,   # 18-23: evening wind-down
]
DEFAULT_AVG_TASK_DURATIONS: dict[str, int] = {
    "email": 5,
    "deep_work": 52,
    "admin": 15,
    "meeting": 30,
}
DEFAULT_ADHERENCE: float = 0.7
DEFAULT_ESTIMATION_BIAS: float = 1.2
DEFAULT_AUTOMATION_COMFORT: dict[str, float] = {
    "email": 0.9,
    "slack": 0.8,
    "booking": 0.5,
}
DEFAULT_DISTRACTION_PATTERNS: dict[str, float] = {
    "slack_notification": 0.5,
    "phone_check": 0.4,
    "context_switch": 0.3,
}


# ═══════════════════════════════════════════════════════════════════════════
# Archetype definitions
# ═══════════════════════════════════════════════════════════════════════════

# Reference calibration (exclusive — only the best of the best):
#
# Profile              | Archetype           | X (Exec) | Y (Growth) | Description
# Sam Altman / Zuck    | Compounding Builder | 0.95     | 0.93       | Extremely high shipping + steep learning curve
# Steady Builder       | Reliable Operator   | 0.86     | 0.36       | Ships consistently but plateauing in growth
# Sporadic Sprinter    | Emerging Talent     | 0.38     | 0.83       | Low/volatile output but learning velocity is elite
# Stuck Dreamer        | At Risk             | 0.14     | 0.20       | Low completion, no improvement trend

ARCHETYPES = {
    "compounding_builder": {
        "label": "Compounding Builder",
        "description": (
            "Extremely high shipping rate combined with a steep learning curve. "
            "Every output compounds into larger scope. Think Sam Altman, Zuckerberg."
        ),
        "min_execution": 0.85,
        "min_growth": 0.80,
    },
    "reliable_operator": {
        "label": "Reliable Operator",
        "description": (
            "Highly consistent and ships on time, but has reached a plateau in "
            "skill acquisition or scope expansion. Dependable, not accelerating."
        ),
        "min_execution": 0.70,
        "min_growth": 0.0,
    },
    "emerging_talent": {
        "label": "Emerging Talent",
        "description": (
            "Currently low output or volatile schedule, but showing high learning "
            "velocity and rapidly improving metrics. Raw potential, unrefined execution."
        ),
        "min_execution": 0.0,
        "min_growth": 0.65,
    },
    "at_risk": {
        "label": "At Risk",
        "description": (
            "Low completion rates and no significant improvement trend. "
            'Often stuck in the "planning" phase without acting.'
        ),
        "min_execution": 0.0,
        "min_growth": 0.0,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Engine
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PatternEngine:
    """Computes the 6 core behavioral patterns from the spec.

    All computations use a sliding window with exponential decay.
    """

    sliding_window_days: int = 14
    decay_factor: float = 0.85

    # Accumulated data
    daily_goal_entries: list[dict[str, Any]] = field(default_factory=list)
    task_completions: list[dict[str, Any]] = field(default_factory=list)
    social_posting_hours: dict[str, list[int]] = field(default_factory=dict)
    reflection_data: dict[str, Any] = field(default_factory=dict)
    resume_data: dict[str, Any] = field(default_factory=dict)
    ghostworker_events: list[dict[str, Any]] = field(default_factory=list)

    def load_signals(
        self,
        daily_goals: list[dict[str, Any]] | None = None,
        task_completions: list[dict[str, Any]] | None = None,
        social_posting_hours: dict[str, list[int]] | None = None,
        reflection_data: dict[str, Any] | None = None,
        resume_data: dict[str, Any] | None = None,
    ) -> None:
        """Ingest signal data for pattern computation."""
        if daily_goals is not None:
            self.daily_goal_entries = daily_goals
        if task_completions is not None:
            self.task_completions = task_completions
        if social_posting_hours is not None:
            self.social_posting_hours = social_posting_hours
        if reflection_data is not None:
            self.reflection_data = reflection_data
        if resume_data is not None:
            self.resume_data = resume_data

    # -- Decay helper --

    def _decay_weight(self, age_days: int) -> float:
        """Exponential decay: weight = decay_factor ^ age_days."""
        if age_days < 0:
            age_days = 0
        return self.decay_factor ** min(age_days, self.sliding_window_days)

    def _apply_decay(self, values: list[float]) -> float:
        """Weighted mean with exponential recency decay.

        values[0] is oldest, values[-1] is most recent.
        """
        if not values:
            return 0.0
        weights = [self._decay_weight(len(values) - 1 - i) for i in range(len(values))]
        total_w = sum(weights)
        if total_w == 0:
            return 0.0
        return sum(v * w for v, w in zip(values, weights)) / total_w

    # -- Pattern 1: Peak Productivity Hours --

    def compute_peak_hours(self) -> list[int]:
        """Aggregate task completion timestamps to find peak productivity hours.

        Cross-references with social media posting hours.
        """
        hour_scores: dict[int, float] = {h: 0.0 for h in range(24)}

        # From daily goals: infer hours from completion patterns
        # (since files don't have timestamps, use social media as proxy)
        for source, hours in self.social_posting_hours.items():
            for h in hours:
                hour_scores[h] = hour_scores.get(h, 0.0) + 1.0

        # From task completion logs (if available)
        for tc in self.task_completions:
            ts = tc.get("completed_at", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    hour_scores[dt.hour] += 2.0  # task completions weighted higher
                except (ValueError, TypeError):
                    pass

        # If we have daily goal data with high-completion days,
        # boost typical working hours
        for entry in self.daily_goal_entries:
            if entry.get("completion_rate", 0) > 0.7:
                # Assume productive hours were 9-11, 14-16
                for h in [9, 10, 11, 14, 15, 16]:
                    hour_scores[h] += entry["completion_rate"]

        if not any(hour_scores.values()):
            return list(DEFAULT_PEAK_HOURS)

        # Return top-4 hours
        sorted_hours = sorted(hour_scores.items(), key=lambda x: -x[1])
        peak = [h for h, _ in sorted_hours[:4] if sorted_hours[0][1] > 0]
        return sorted(peak) if peak else list(DEFAULT_PEAK_HOURS)

    # -- Pattern 2: Task Duration Bias --

    def compute_estimation_bias(self) -> float:
        """Ratio of actual/estimated durations across task types.

        > 1.0 means user underestimates (tasks take longer than expected).
        """
        ratios: list[float] = []
        for tc in self.task_completions:
            est = tc.get("estimated_minutes", 0)
            actual = tc.get("actual_minutes", 0)
            if est > 0 and actual > 0:
                ratios.append(actual / est)

        if not ratios:
            return DEFAULT_ESTIMATION_BIAS

        return round(self._apply_decay(ratios), 4)

    # -- Pattern 3: Disruption Recovery --

    def compute_disruption_recovery(self) -> dict[str, float]:
        """Analyze recovery patterns from daily goals.

        Detects days where morning tasks failed but afternoon tasks succeeded.
        """
        recovery_scores: list[float] = []

        for entry in self.daily_goal_entries:
            tasks = entry.get("tasks", [])
            if len(tasks) < 3:
                continue

            mid = len(tasks) // 2
            first_half = tasks[:mid]
            second_half = tasks[mid:]

            first_completion = sum(1 for t in first_half if t["completed"]) / max(len(first_half), 1)
            second_completion = sum(1 for t in second_half if t["completed"]) / max(len(second_half), 1)

            # Recovery = doing better in second half despite poor first half
            if first_completion < 0.5 and second_completion > first_completion:
                recovery_scores.append(second_completion - first_completion)
            elif first_completion >= 0.5:
                recovery_scores.append(0.8)  # consistent = good recovery baseline
            else:
                recovery_scores.append(0.2)  # poor throughout

        avg_recovery = self._apply_decay(recovery_scores) if recovery_scores else 0.5
        return {
            "avg_recovery_score": round(avg_recovery, 4),
            "num_observations": len(recovery_scores),
        }

    # -- Pattern 4: Energy Curve --

    def compute_energy_curve(self) -> list[int]:
        """Build 24-element energy curve from activity patterns.

        Seeds from social posting hours, refines with goal completion data.
        """
        curve = list(DEFAULT_ENERGY_CURVE)

        # Boost hours with social activity
        hour_activity: dict[int, float] = {h: 0.0 for h in range(24)}
        for source, hours in self.social_posting_hours.items():
            for h in hours:
                hour_activity[h] += 1.0

        # Boost hours implied by high-completion days
        for entry in self.daily_goal_entries:
            rate = entry.get("completion_rate", 0)
            if rate > 0.6:
                for h in [9, 10, 11, 14, 15, 16]:
                    hour_activity[h] += rate * 0.5

        if any(hour_activity.values()):
            max_act = max(hour_activity.values()) or 1.0
            for h in range(24):
                # Blend default curve with observed activity
                observed_boost = (hour_activity[h] / max_act) * 2
                curve[h] = max(1, min(5, round(curve[h] * 0.6 + (curve[h] + observed_boost) * 0.4)))

        return curve

    # -- Pattern 5: Schedule Adherence --

    def compute_adherence_score(self) -> float:
        """Exponentially-decayed mean of daily completion rates."""
        rates = [e.get("completion_rate", 0.0) for e in self.daily_goal_entries]
        if not rates:
            return DEFAULT_ADHERENCE
        return round(self._apply_decay(rates), 4)

    def compute_drift_direction(self) -> str:
        """Detect whether incomplete tasks cluster at end-of-list (evening fade)
        or are scattered (distraction pattern)."""
        end_incomplete = 0
        scattered_incomplete = 0

        for entry in self.daily_goal_entries:
            tasks = entry.get("tasks", [])
            if not tasks:
                continue
            incomplete_positions = [
                i / max(len(tasks) - 1, 1)
                for i, t in enumerate(tasks) if not t["completed"]
            ]
            if not incomplete_positions:
                continue
            avg_pos = sum(incomplete_positions) / len(incomplete_positions)
            if avg_pos > 0.65:
                end_incomplete += 1
            else:
                scattered_incomplete += 1

        if end_incomplete > scattered_incomplete:
            return "evening_fade"
        elif scattered_incomplete > end_incomplete:
            return "distraction"
        return "balanced"

    # -- Pattern 6: Automation Comfort --

    def compute_automation_comfort(self) -> dict[str, float]:
        """Initialize from working style, update from GhostWorker events."""
        comfort = dict(DEFAULT_AUTOMATION_COMFORT)

        for event in self.ghostworker_events:
            task_type = event.get("task_type", "")
            outcome = event.get("outcome", "")
            if not task_type:
                continue

            current = comfort.get(task_type, 0.5)
            if outcome == "approved_quickly":
                comfort[task_type] = min(1.0, current + 0.05)
            elif outcome == "edited":
                comfort[task_type] = max(0.1, current - 0.02)
            elif outcome == "rejected":
                comfort[task_type] = max(0.1, current - 0.1)

        return {k: round(v, 4) for k, v in comfort.items()}

    # -- Aggregate: compute full profile --

    def compute_profile(self) -> dict[str, Any]:
        """Compute all pattern fields and return a UserProfile-compatible dict."""
        peak_hours = self.compute_peak_hours()
        estimation_bias = self.compute_estimation_bias()
        recovery = self.compute_disruption_recovery()
        energy_curve = self.compute_energy_curve()
        adherence = self.compute_adherence_score()
        drift = self.compute_drift_direction()
        automation = self.compute_automation_comfort()

        distraction = dict(DEFAULT_DISTRACTION_PATTERNS)
        if drift == "distraction":
            distraction["context_switch"] = min(1.0, distraction["context_switch"] + 0.2)
        elif drift == "evening_fade":
            distraction["fatigue"] = 0.6

        return {
            "peak_hours": peak_hours,
            "avg_task_durations": dict(DEFAULT_AVG_TASK_DURATIONS),
            "energy_curve": energy_curve,
            "adherence_score": adherence,
            "distraction_patterns": distraction,
            "estimation_bias": estimation_bias,
            "automation_comfort": automation,
            "disruption_recovery": recovery,
            "drift_direction": drift,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Sentiment Analyzer
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SentimentAnalyzer:
    """Lightweight sentiment analysis for reflections and social posts."""

    POSITIVE_WORDS = {
        "great", "good", "better", "improving", "learning", "progress",
        "productive", "focused", "accomplished", "succeeded", "motivated",
        "disciplined", "excellent", "achieved", "interesting", "excited",
        "proud", "strong", "confident", "love", "wonderful", "growth",
        "succeed", "success", "win", "winning", "ship", "shipped",
        "impact", "milestone", "breakthrough", "innovation",
    }
    NEGATIVE_WORDS = {
        "wasted", "distracted", "lazy", "failed", "bad", "low",
        "procrastinated", "forgot", "missed", "stressed",
        "anxious", "overwhelmed", "tired", "burnout", "unfocused",
        "comfortable", "waste", "struggle", "stuck", "confused",
        "frustrated", "lost", "behind", "overcommitted", "scattered",
    }

    def analyze(self, text: str) -> dict[str, Any]:
        """Return sentiment analysis for a text block."""
        if not text.strip():
            return {"label": "neutral", "score": 0.0, "word_count": 0}

        import re
        words = set(re.findall(r"[a-z']+", text.lower()))
        pos = len(words & self.POSITIVE_WORDS)
        neg = len(words & self.NEGATIVE_WORDS)
        total = pos + neg

        if total == 0:
            score = 0.0
            label = "neutral"
        else:
            score = (pos - neg) / total
            if score > 0.2:
                label = "positive"
            elif score < -0.2:
                label = "negative"
            else:
                label = "neutral"

        return {
            "label": label,
            "score": round(score, 4),
            "positive_count": pos,
            "negative_count": neg,
            "word_count": len(words),
        }

    def analyze_trend(self, texts: list[str], window: int = 7) -> dict[str, Any]:
        """Compute rolling sentiment trend over a list of texts."""
        scores = [self.analyze(t)["score"] for t in texts]
        if not scores:
            return {"trend": "neutral", "avg_score": 0.0, "scores": []}

        avg = sum(scores) / len(scores)

        # Check if improving
        if len(scores) >= 3:
            first_half = scores[: len(scores) // 2]
            second_half = scores[len(scores) // 2:]
            f_avg = sum(first_half) / len(first_half)
            s_avg = sum(second_half) / len(second_half)
            if s_avg > f_avg + 0.1:
                trend = "improving"
            elif s_avg < f_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "avg_score": round(avg, 4),
            "scores": [round(s, 4) for s in scores],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Grouping Function (Achiever Spectrum)
# ═══════════════════════════════════════════════════════════════════════════

def _signal_normalize(
    vectors: dict[str, float],
    temperature: float = 8.0,
) -> dict[str, float]:
    """Adapted softmax normalization — amplify signal, suppress noise.

    Applies a temperature-controlled sigmoid per dimension::

        f(x) = 1 / (1 + exp(-T * (x - 0.5)))

    At T = 8 the effect is:

        0.10 → 0.04   (crushed)
        0.30 → 0.17   (compressed)
        0.50 → 0.50   (inflection — unchanged)
        0.70 → 0.83   (amplified)
        0.90 → 0.96   (near-ceiling)

    This makes the distribution bimodal: strong signals converge toward 1,
    weak signals converge toward 0, and the middle is a cliff.  Only
    genuinely elite performance survives the normalization.

    Parameters
    ----------
    vectors : dict of raw scores in [0, 1]
    temperature : float, higher = more selective / exclusive
    """
    def _sigmoid(x: float) -> float:
        clamped = max(-20.0, min(20.0, temperature * (x - 0.5)))
        return 1.0 / (1.0 + math.exp(-clamped))

    return {k: round(_sigmoid(v), 4) for k, v in vectors.items()}


@dataclass
class GroupingFunction:
    """Classifies users into archetypes using multi-vector scoring.

    This is an **exclusive** classifier.  The bar is set high:

    1. Compounding Builder — elite execution AND elite growth (top ~5%)
    2. Reliable Operator   — strong execution but stagnant growth
    3. Emerging Talent     — low/volatile execution but elite learning velocity
    4. At Risk             — neither shipping nor improving (**the default**)

    Raw vectors pass through an adapted-softmax normalization (temperature-
    controlled sigmoid) before compositing.  This amplifies genuinely
    strong signal and crushes noise, ensuring only sustained excellence
    clears the thresholds.
    """

    # Normalization temperature — higher = more exclusive
    temperature: float = 8.0

    def compute_vectors(
        self,
        daily_goals: list[dict[str, Any]],
        reflection_data: dict[str, Any],
        resume_data: dict[str, Any],
    ) -> dict[str, float]:
        """Compute the 6 scoring vectors (each 0.0 - 1.0)."""
        # -- completion_consistency: low stddev = high score --
        rates = [e.get("completion_rate", 0.0) for e in daily_goals]
        if len(rates) >= 2:
            stddev = statistics.stdev(rates)
            completion_consistency = max(0.0, 1.0 - stddev * 3)
        else:
            completion_consistency = 0.5

        # -- execution_rate: mean completion --
        execution_rate = sum(rates) / len(rates) if rates else 0.5

        # -- growth_velocity: slope of completion rates over time --
        if len(rates) >= 3:
            first_half = rates[: len(rates) // 2]
            second_half = rates[len(rates) // 2:]
            slope = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
            growth_velocity = max(0.0, min(1.0, 0.5 + slope * 2))
        else:
            growth_velocity = 0.5

        # -- self_awareness: from reflection data --
        gi = reflection_data.get("growth_indicators", {})
        self_awareness = gi.get("self_awareness_score", 0.3)

        # -- ambition_calibration: ratio of goals set to achievable --
        total_tasks = sum(e.get("total_tasks", 0) for e in daily_goals)
        completed_tasks = sum(e.get("completed_count", 0) for e in daily_goals)
        if total_tasks > 0:
            raw_ratio = completed_tasks / total_tasks
            ambition_calibration = 1.0 - abs(raw_ratio - 0.8) * 2
            ambition_calibration = max(0.0, min(1.0, ambition_calibration))
        else:
            ambition_calibration = 0.3

        # -- recovery_speed: how fast patterns improve after bad streaks --
        # Default is 0.5 (neutral) — we don't assume recovery until proven.
        bad_streaks = 0
        recoveries = 0
        for i in range(1, len(rates)):
            if rates[i - 1] < 0.4:
                bad_streaks += 1
                if rates[i] > rates[i - 1] + 0.2:
                    recoveries += 1
        recovery_speed = recoveries / max(bad_streaks, 1) if bad_streaks > 0 else 0.5

        return {
            "completion_consistency": round(completion_consistency, 4),
            "execution_rate": round(execution_rate, 4),
            "growth_velocity": round(growth_velocity, 4),
            "self_awareness": round(self_awareness, 4),
            "ambition_calibration": round(ambition_calibration, 4),
            "recovery_speed": round(recovery_speed, 4),
        }

    def classify(
        self,
        daily_goals: list[dict[str, Any]],
        reflection_data: dict[str, Any],
        resume_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Return archetype classification + trait vectors.

        Classification is deliberately exclusive.  The default is At Risk.
        You must earn your way up through sustained, high-signal behavior.

        Pipeline:
        1. Compute raw 6-dim vectors from data
        2. Pass through adapted-softmax normalization (sigmoid @ temperature)
        3. Gate consistency on execution quality (consistent failure ≠ good)
        4. Composite into execution / growth scores
        5. Match against exclusive thresholds
        """
        raw_vectors = self.compute_vectors(daily_goals, reflection_data, resume_data)

        # ── Phase 1: Adapted-softmax normalization ──
        vectors = _signal_normalize(raw_vectors, temperature=self.temperature)

        # ── Phase 2: Consistency gate ──
        # Being consistently terrible is not a signal of quality.
        # Scale consistency by execution so it only counts when you ship.
        effective_consistency = vectors["completion_consistency"]
        if vectors["execution_rate"] < 0.50:
            effective_consistency *= vectors["execution_rate"] * 2.0

        # ── Phase 3: Composite scores ──
        exec_composite = (
            vectors["execution_rate"] * 0.40
            + effective_consistency * 0.30
            + vectors["ambition_calibration"] * 0.15
            + vectors["recovery_speed"] * 0.15
        )
        growth_composite = (
            vectors["growth_velocity"] * 0.40
            + vectors["self_awareness"] * 0.30
            + vectors["recovery_speed"] * 0.15
            + vectors["ambition_calibration"] * 0.15
        )

        # ── Phase 4: Exclusive thresholds ──
        # Compounding Builder: elite execution AND elite growth (Altman/Zuck bar)
        if exec_composite >= 0.85 and growth_composite >= 0.80:
            archetype = "compounding_builder"
        # Reliable Operator: strong execution, stagnant growth
        elif exec_composite >= 0.70 and growth_composite < 0.50:
            archetype = "reliable_operator"
        # Emerging Talent: weak execution but exceptional learning velocity
        elif exec_composite < 0.50 and growth_composite >= 0.65:
            archetype = "emerging_talent"
        # At Risk: the default.  No participation trophies.
        else:
            archetype = "at_risk"

        confidence = min(1.0, len(daily_goals) / 10.0)

        return {
            "archetype": archetype,
            "archetype_label": ARCHETYPES[archetype]["label"],
            "archetype_description": ARCHETYPES[archetype]["description"],
            "execution_composite": round(exec_composite, 4),
            "growth_composite": round(growth_composite, 4),
            "confidence": round(confidence, 4),
            "traits": raw_vectors,  # expose raw vectors for transparency
            "normalized_traits": vectors,  # expose normalized for debugging
        }


# ═══════════════════════════════════════════════════════════════════════════
# Success Function (Two-Axis Plot)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SuccessFunction:
    """Computes the two-axis success plot — exclusive calibration.

    X-axis: Execution Velocity — "Does this person ship?"
    Y-axis: Growth Trajectory  — "Is this person getting better?"

    Reference calibration:
        Sam Altman / Zuck  → (0.95, 0.93) Compounding Builder
        Steady Builder     → (0.86, 0.36) Reliable Operator
        Sporadic Sprinter  → (0.38, 0.83) Emerging Talent
        Stuck Dreamer      → (0.14, 0.20) At Risk

    Quadrant boundaries are set HIGH. The default is At Risk.
    """

    def compute(
        self,
        profile: dict[str, Any],
        grouping: dict[str, Any],
        sentiment_trend: dict[str, Any],
        social_engagement_growth: float = 0.0,
    ) -> dict[str, Any]:
        """Compute the two-axis success coordinates."""
        traits = grouping.get("traits", {})

        # ── X-axis: Execution Velocity ──
        completion_rate = traits.get("execution_rate", 0.5)
        adherence = profile.get("adherence_score", DEFAULT_ADHERENCE)
        estimation_accuracy = 1.0 - min(abs(profile.get("estimation_bias", 1.0) - 1.0), 1.0)
        consistency = traits.get("completion_consistency", 0.5)

        execution_velocity = (
            completion_rate * 0.40
            + adherence * 0.25
            + estimation_accuracy * 0.20
            + consistency * 0.15
        )

        # ── Y-axis: Growth Trajectory ──
        learning_velocity = traits.get("self_awareness", 0.3)
        rate_improvement = traits.get("growth_velocity", 0.5)
        ambition_expansion = traits.get("ambition_calibration", 0.3)
        sentiment_score = max(0.0, min(1.0, 0.5 + sentiment_trend.get("avg_score", 0.0)))
        engagement_growth = max(0.0, min(1.0, 0.5 + social_engagement_growth))

        growth_trajectory = (
            learning_velocity * 0.30
            + rate_improvement * 0.25
            + ambition_expansion * 0.20
            + sentiment_score * 0.15
            + engagement_growth * 0.10
        )

        # ── Exclusive quadrant classification ──
        # Compounding Builder: must clear BOTH high bars
        if execution_velocity >= 0.80 and growth_trajectory >= 0.75:
            quadrant = "compounding_builder"
            quadrant_label = "Compounding Builder"
        # Reliable Operator: ships hard but growth has plateaued
        elif execution_velocity >= 0.70 and growth_trajectory < 0.50:
            quadrant = "reliable_operator"
            quadrant_label = "Reliable Operator"
        # Emerging Talent: raw potential, execution not yet there
        elif execution_velocity < 0.50 and growth_trajectory >= 0.65:
            quadrant = "emerging_talent"
            quadrant_label = "Emerging Talent"
        # At Risk: the default. No participation trophies.
        else:
            quadrant = "at_risk"
            quadrant_label = "At Risk"

        return {
            "execution_velocity": round(execution_velocity, 4),
            "growth_trajectory": round(growth_trajectory, 4),
            "quadrant": quadrant,
            "quadrant_label": quadrant_label,
            "components": {
                "x": {
                    "completion_rate": round(completion_rate, 4),
                    "adherence": round(adherence, 4),
                    "estimation_accuracy": round(estimation_accuracy, 4),
                    "consistency": round(consistency, 4),
                },
                "y": {
                    "learning_velocity": round(learning_velocity, 4),
                    "rate_improvement": round(rate_improvement, 4),
                    "ambition_expansion": round(ambition_expansion, 4),
                    "sentiment": round(sentiment_score, 4),
                    "engagement_growth": round(engagement_growth, 4),
                },
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# Temporal Tracker
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TemporalTracker:
    """Stores daily snapshots and detects regime changes."""

    drift_threshold: float = 0.15
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    def add_snapshot(self, date_key: str, scores: dict[str, float]) -> None:
        """Record a daily snapshot of all scores."""
        self.snapshots.append({
            "date": date_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scores": dict(scores),
        })

    def detect_drift(self) -> dict[str, Any] | None:
        """Compare latest snapshot to previous to detect significant changes.

        Returns drift info if magnitude > threshold, else None.
        """
        if len(self.snapshots) < 2:
            return None

        prev = self.snapshots[-2]["scores"]
        curr = self.snapshots[-1]["scores"]

        # Compute per-field drift
        changed: list[str] = []
        magnitudes: list[float] = []
        for key in curr:
            if key in prev:
                diff = abs(curr[key] - prev[key])
                if diff > self.drift_threshold:
                    changed.append(key)
                    magnitudes.append(diff)

        if not changed:
            return None

        return {
            "changed_fields": changed,
            "magnitude": round(max(magnitudes), 4),
            "avg_magnitude": round(sum(magnitudes) / len(magnitudes), 4),
            "direction": {
                f: "improved" if curr[f] > prev[f] else "declined"
                for f in changed
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_trend(self, field: str, window: int = 7) -> list[float]:
        """Return recent values for a specific score field."""
        recent = self.snapshots[-window:]
        return [s["scores"].get(field, 0.0) for s in recent]

    def to_redis_payload(self) -> str:
        """Serialize snapshots for Redis persistence."""
        return json.dumps(self.snapshots[-30:])  # keep last 30 days

    @classmethod
    def from_redis_payload(cls, payload: str, drift_threshold: float = 0.15) -> "TemporalTracker":
        """Deserialize from Redis."""
        snapshots = json.loads(payload) if payload else []
        tracker = cls(drift_threshold=drift_threshold)
        tracker.snapshots = snapshots
        return tracker


# ═══════════════════════════════════════════════════════════════════════════
# ProfilerEngine — orchestrates all components
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ProfilerEngine:
    """Top-level orchestrator that ties all profiler components together.

    Call `build_full_profile()` to compute everything from raw data.
    """

    pattern_engine: PatternEngine = field(default_factory=PatternEngine)
    sentiment_analyzer: SentimentAnalyzer = field(default_factory=SentimentAnalyzer)
    grouping_function: GroupingFunction = field(default_factory=GroupingFunction)
    success_function: SuccessFunction = field(default_factory=SuccessFunction)
    temporal_tracker: TemporalTracker = field(default_factory=TemporalTracker)

    def build_full_profile(
        self,
        daily_goals: list[dict[str, Any]] | None = None,
        task_completions: list[dict[str, Any]] | None = None,
        social_posting_hours: dict[str, list[int]] | None = None,
        reflection_data: dict[str, Any] | None = None,
        resume_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the full profiling pipeline and return all computed data.

        Returns a dict with keys:
            user_profile   — UserProfile-compatible fields
            grouping       — archetype classification
            success_plot   — two-axis success coordinates
            sentiment      — sentiment trend
            temporal_drift — drift info (or None)
        """
        # Load data into pattern engine
        self.pattern_engine.load_signals(
            daily_goals=daily_goals or [],
            task_completions=task_completions or [],
            social_posting_hours=social_posting_hours or {},
            reflection_data=reflection_data or {},
            resume_data=resume_data or {},
        )

        # 1. Compute behavioral patterns -> UserProfile
        profile = self.pattern_engine.compute_profile()

        # 2. Sentiment analysis on reflections
        reflection_texts = []
        if daily_goals:
            reflection_texts = [
                e.get("reflection_text", "")
                for e in daily_goals
                if e.get("has_reflection")
            ]
        sentiment = self.sentiment_analyzer.analyze_trend(reflection_texts)

        # 3. Grouping function -> archetype
        grouping = self.grouping_function.classify(
            daily_goals=daily_goals or [],
            reflection_data=reflection_data or {},
            resume_data=resume_data or {},
        )

        # 4. Success function -> two-axis plot
        success = self.success_function.compute(
            profile=profile,
            grouping=grouping,
            sentiment_trend=sentiment,
        )

        # 5. Temporal tracking
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        snapshot_scores = {
            "execution_velocity": success["execution_velocity"],
            "growth_trajectory": success["growth_trajectory"],
            "adherence_score": profile["adherence_score"],
            "estimation_bias": profile["estimation_bias"],
        }
        self.temporal_tracker.add_snapshot(date_key, snapshot_scores)
        drift = self.temporal_tracker.detect_drift()

        return {
            "user_profile": profile,
            "grouping": grouping,
            "success_plot": success,
            "sentiment": sentiment,
            "temporal_drift": drift,
        }
