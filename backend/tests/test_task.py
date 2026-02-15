"""Tests for src.models.task — Task model, scoring, bucket hashing, Redis persistence."""

import json
import math
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.models.task import (
    Task,
    Priority,
    TaskStatus,
    BUCKET_COUNT,
    TASK_PREFIX,
    BUCKET_PREFIX,
    BACKLOG_KEY,
    ACTIVE_KEY,
)


# ═══════════════════════════════════════════════════════════════════════════
# Task Creation & Defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskDefaults:
    def test_task_defaults(self):
        task = Task(task_id="t1", title="Do something")
        assert task.priority == Priority.P2_NORMAL
        assert task.energy_cost == 3
        assert task.estimated_duration == 30
        assert task.status == TaskStatus.BACKLOG
        assert task.tags == []
        assert task.task_type == "general"
        assert task.cognitive_load == 3
        assert task.description == ""
        assert task.deadline == ""
        assert task.preferred_start == ""

    def test_task_custom_fields(self):
        task = Task(
            task_id="t2",
            title="Urgent fix",
            priority=Priority.P0_URGENT,
            energy_cost=5,
            estimated_duration=120,
            tags=["backend", "hotfix"],
        )
        assert task.priority == Priority.P0_URGENT
        assert task.energy_cost == 5
        assert task.estimated_duration == 120
        assert task.tags == ["backend", "hotfix"]


# ═══════════════════════════════════════════════════════════════════════════
# Deadline Urgency Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestDeadlineUrgency:
    def _make_task_with_deadline(self, hours_from_now, frozen_now):
        deadline = (frozen_now + timedelta(hours=hours_from_now)).isoformat()
        return Task(task_id="t-dl", title="Deadline test", deadline=deadline)

    def test_deadline_urgency_near_deadline(self, frozen_now, freeze_time):
        """1 hour remaining should yield urgency = 10.0."""
        task = self._make_task_with_deadline(1, frozen_now)
        with freeze_time:
            assert task.deadline_urgency == pytest.approx(10.0, abs=0.1)

    def test_deadline_urgency_far_deadline(self, frozen_now, freeze_time):
        """24 hours remaining should yield urgency ~0.42."""
        task = self._make_task_with_deadline(24, frozen_now)
        with freeze_time:
            assert task.deadline_urgency == pytest.approx(10.0 / 24.0, abs=0.05)

    def test_deadline_urgency_2_hours(self, frozen_now, freeze_time):
        """2 hours remaining should yield urgency = 5.0."""
        task = self._make_task_with_deadline(2, frozen_now)
        with freeze_time:
            assert task.deadline_urgency == pytest.approx(5.0, abs=0.1)

    def test_deadline_urgency_no_deadline(self):
        """No deadline string → urgency = 0.0."""
        task = Task(task_id="t-nd", title="No deadline")
        assert task.deadline_urgency == 0.0

    def test_deadline_urgency_invalid_deadline(self):
        """Malformed deadline string → urgency = 0.0."""
        task = Task(task_id="t-bad", title="Bad deadline", deadline="not-a-date")
        assert task.deadline_urgency == 0.0

    def test_deadline_urgency_past_deadline(self, frozen_now, freeze_time):
        """Past deadline → hours_remaining clamped to 0.1, urgency capped at 10.0."""
        task = self._make_task_with_deadline(-2, frozen_now)
        with freeze_time:
            assert task.deadline_urgency == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# Execution Time Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionTimeScore:
    def test_short_task_15min(self):
        """15 min → score ≈ 6.67."""
        task = Task(task_id="t-short", title="Quick", estimated_duration=15)
        assert task.execution_time_score == pytest.approx(100.0 / 15.0, abs=0.01)

    def test_medium_task_30min(self):
        """30 min → score ≈ 3.33."""
        task = Task(task_id="t-med", title="Medium", estimated_duration=30)
        assert task.execution_time_score == pytest.approx(100.0 / 30.0, abs=0.01)

    def test_long_task_120min(self):
        """120 min → score ≈ 0.83."""
        task = Task(task_id="t-long", title="Long", estimated_duration=120)
        assert task.execution_time_score == pytest.approx(100.0 / 120.0, abs=0.01)

    def test_very_short_task_caps_at_10(self):
        """Very short (1 min) → capped at 10.0."""
        task = Task(task_id="t-tiny", title="Instant", estimated_duration=1)
        assert task.execution_time_score == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# Preferred Start Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestPreferredStartScore:
    def test_no_preferred_start_neutral(self):
        """No preferred start → neutral score 5.0."""
        task = Task(task_id="t-nps", title="No pref")
        assert task.preferred_start_score == 5.0

    def test_overdue_preferred_start(self, frozen_now, freeze_time):
        """Preferred start in the past → score = 10.0."""
        past = (frozen_now - timedelta(hours=1)).isoformat()
        task = Task(task_id="t-past", title="Overdue pref", preferred_start=past)
        with freeze_time:
            assert task.preferred_start_score == 10.0

    def test_far_future_preferred_start(self, frozen_now, freeze_time):
        """Preferred start 24h away → low score ≈ 0.42."""
        future = (frozen_now + timedelta(hours=24)).isoformat()
        task = Task(task_id="t-far", title="Far pref", preferred_start=future)
        with freeze_time:
            assert task.preferred_start_score == pytest.approx(10.0 / 24.0, abs=0.05)

    def test_invalid_preferred_start(self):
        """Malformed preferred_start → neutral score 5.0."""
        task = Task(task_id="t-badps", title="Bad pref", preferred_start="nope")
        assert task.preferred_start_score == 5.0


# ═══════════════════════════════════════════════════════════════════════════
# Bucket Computation
# ═══════════════════════════════════════════════════════════════════════════


class TestBucketComputation:
    def test_bucket_range(self, make_task, frozen_now, freeze_time):
        """Bucket is always in [0, BUCKET_COUNT)."""
        with freeze_time:
            for i in range(50):
                dl = (frozen_now + timedelta(hours=i + 1)).isoformat()
                task = make_task(
                    estimated_duration=(i + 1) * 5,
                    deadline=dl,
                )
                assert 0 <= task.bucket < BUCKET_COUNT

    def test_bucket_deterministic(self, make_task):
        """Same task properties → same bucket."""
        t1 = make_task(task_id="det-1", estimated_duration=30, deadline="2026-03-01T10:00:00+00:00")
        t2 = make_task(task_id="det-2", estimated_duration=30, deadline="2026-03-01T10:00:00+00:00")
        assert t1.bucket == t2.bucket

    def test_bucket_no_deadline_no_pref(self):
        """No deadline + no preferred_start → composite based only on execution_time_score."""
        task = Task(task_id="t-plain", title="Plain", estimated_duration=30)
        # D=0, E=100/30≈3.33, P=5.0
        # composite = 0*0.45 + 3.33*0.30 + 5.0*0.25 = 0 + 1.0 + 1.25 = 2.25
        # bucket = floor(2.25) % 16 = 2
        expected = math.floor(0 * 0.45 + (100.0 / 30) * 0.30 + 5.0 * 0.25) % BUCKET_COUNT
        assert task.bucket == expected


# ═══════════════════════════════════════════════════════════════════════════
# Serialization: to_dict / from_dict
# ═══════════════════════════════════════════════════════════════════════════


class TestSerialization:
    def test_to_dict_from_dict_roundtrip(self):
        task = Task(
            task_id="ser-1",
            title="Serialize me",
            priority=Priority.P1_IMPORTANT,
            tags=["a", "b"],
            energy_cost=4,
        )
        d = task.to_dict()
        restored = Task.from_dict(d)
        assert restored.task_id == task.task_id
        assert restored.title == task.title
        assert restored.priority == int(Priority.P1_IMPORTANT)
        assert restored.tags == ["a", "b"]
        assert restored.energy_cost == 4

    def test_from_dict_handles_enum_repr_strings(self):
        """Handle stringified enum reprs like '<Priority.P1_IMPORTANT: 1>'."""
        data = {
            "task_id": "enum-test",
            "title": "Enum edge case",
            "priority": "<Priority.P1_IMPORTANT: 1>",
            "energy_cost": "3",
            "estimated_duration": "45",
            "cognitive_load": "4",
            "tags": "[]",
        }
        task = Task.from_dict(data)
        assert task.priority == 1
        assert task.energy_cost == 3
        assert task.estimated_duration == 45
        assert task.cognitive_load == 4

    def test_tags_json_roundtrip(self):
        """Tags list survives json.dumps / json.loads cycle (as Redis would do)."""
        tags = ["backend", "urgent", "p0"]
        task = Task(task_id="tag-test", title="Tags", tags=tags)
        d = task.to_dict()
        # to_dict json.dumps tags
        assert isinstance(d["tags"], str)
        assert json.loads(d["tags"]) == tags
        # from_dict parses them back
        restored = Task.from_dict(d)
        assert restored.tags == tags


# ═══════════════════════════════════════════════════════════════════════════
# Redis Persistence
# ═══════════════════════════════════════════════════════════════════════════


class TestRedisPersistence:
    def test_to_redis_and_from_redis_roundtrip(self, r, make_task):
        """Store → load → all fields match."""
        task = make_task(
            task_id="redis-rt",
            title="Redis roundtrip",
            priority=Priority.P1_IMPORTANT,
            tags=["integration"],
            energy_cost=4,
            estimated_duration=60,
        )
        task.to_redis(r)
        loaded = Task.from_redis(r, "redis-rt")
        assert loaded is not None
        assert loaded.task_id == task.task_id
        assert loaded.title == task.title
        assert loaded.priority == int(Priority.P1_IMPORTANT)
        assert loaded.tags == ["integration"]
        assert loaded.energy_cost == 4
        assert loaded.estimated_duration == 60

    def test_to_redis_sets_backlog_membership(self, r, make_task):
        """BACKLOG task appears in task:backlog set."""
        task = make_task(task_id="bl-1", status=TaskStatus.BACKLOG)
        task.to_redis(r)
        assert r.sismember(BACKLOG_KEY, "bl-1")
        assert not r.sismember(ACTIVE_KEY, "bl-1")

    def test_to_redis_active_removes_from_backlog(self, r, make_task):
        """ACTIVE task is in task:active and removed from task:backlog."""
        task = make_task(task_id="act-1", status=TaskStatus.BACKLOG)
        task.to_redis(r)
        assert r.sismember(BACKLOG_KEY, "act-1")

        task.status = TaskStatus.ACTIVE
        task.to_redis(r)
        assert r.sismember(ACTIVE_KEY, "act-1")
        assert not r.sismember(BACKLOG_KEY, "act-1")

    def test_to_redis_in_progress_in_active_set(self, r, make_task):
        """IN_PROGRESS task is tracked in the active set."""
        task = make_task(task_id="ip-1", status=TaskStatus.IN_PROGRESS)
        task.to_redis(r)
        assert r.sismember(ACTIVE_KEY, "ip-1")

    def test_from_redis_nonexistent_returns_none(self, r):
        """Loading a nonexistent task returns None."""
        assert Task.from_redis(r, "does-not-exist") is None

    def test_delete_from_redis_removes_all_traces(self, r, make_task):
        """Delete removes the hash, backlog set, active set, and all bucket sets."""
        task = make_task(task_id="del-1", status=TaskStatus.BACKLOG)
        task.to_redis(r)
        bucket = task.bucket
        # Verify it exists
        assert r.exists(f"{TASK_PREFIX}del-1")
        assert r.sismember(BACKLOG_KEY, "del-1")
        assert r.sismember(f"{BUCKET_PREFIX}{bucket}", "del-1")

        Task.delete_from_redis(r, "del-1")

        assert not r.exists(f"{TASK_PREFIX}del-1")
        assert not r.sismember(BACKLOG_KEY, "del-1")
        assert not r.sismember(ACTIVE_KEY, "del-1")
        for b in range(BUCKET_COUNT):
            assert not r.sismember(f"{BUCKET_PREFIX}{b}", "del-1")

    def test_bucket_set_membership(self, r, make_task):
        """Task is added to the correct bucket set in Redis."""
        task = make_task(task_id="bkt-1")
        task.to_redis(r)
        expected_bucket = task.bucket
        assert r.sismember(f"{BUCKET_PREFIX}{expected_bucket}", "bkt-1")


# ═══════════════════════════════════════════════════════════════════════════
# Status Transitions
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusTransitions:
    def test_backlog_to_active(self, r, make_task):
        task = make_task(task_id="st-1", status=TaskStatus.BACKLOG)
        task.to_redis(r)
        assert r.sismember(BACKLOG_KEY, "st-1")

        task.status = TaskStatus.ACTIVE
        task.to_redis(r)
        assert r.sismember(ACTIVE_KEY, "st-1")
        assert not r.sismember(BACKLOG_KEY, "st-1")

        loaded = Task.from_redis(r, "st-1")
        assert loaded.status == TaskStatus.ACTIVE

    def test_active_to_in_progress(self, r, make_task):
        task = make_task(task_id="st-2", status=TaskStatus.ACTIVE)
        task.to_redis(r)

        task.status = TaskStatus.IN_PROGRESS
        task.to_redis(r)
        assert r.sismember(ACTIVE_KEY, "st-2")

        loaded = Task.from_redis(r, "st-2")
        assert loaded.status == TaskStatus.IN_PROGRESS

    def test_active_to_swapped_out(self, r, make_task):
        task = make_task(task_id="st-3", status=TaskStatus.ACTIVE)
        task.to_redis(r)

        task.status = TaskStatus.SWAPPED_OUT
        task.to_redis(r)

        loaded = Task.from_redis(r, "st-3")
        assert loaded.status == TaskStatus.SWAPPED_OUT

    def test_active_to_completed(self, r, make_task):
        task = make_task(task_id="st-4", status=TaskStatus.ACTIVE)
        task.to_redis(r)

        task.status = TaskStatus.COMPLETED
        task.to_redis(r)

        loaded = Task.from_redis(r, "st-4")
        assert loaded.status == TaskStatus.COMPLETED

    def test_backlog_to_delegated(self, r, make_task):
        task = make_task(task_id="st-5", status=TaskStatus.BACKLOG)
        task.to_redis(r)

        task.status = TaskStatus.DELEGATED
        task.to_redis(r)

        loaded = Task.from_redis(r, "st-5")
        assert loaded.status == TaskStatus.DELEGATED
