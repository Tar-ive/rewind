"""Tests for src.models.messages — uAgents Model serialization roundtrips."""

import pytest
from src.models.messages import (
    ContextChangeEvent,
    DisruptionEvent,
    EnergyLevel,
    UpdatedSchedule,
    DelegationTask,
    TaskCompletion,
    ScheduleRequest,
    SwapOperation,
    UserProfile,
    ProfileQuery,
    EnergyQuery,
)


class TestContextChangeEvent:
    def test_roundtrip(self):
        evt = ContextChangeEvent(
            event_type="meeting_ended_early",
            source="google_calendar",
            timestamp="2026-02-15T12:00:00Z",
            affected_task_ids=["t1", "t2"],
            metadata={"freed_minutes": 15, "meeting_id": "cal-123"},
        )
        data = evt.json()
        restored = ContextChangeEvent.parse_raw(data)
        assert restored.event_type == "meeting_ended_early"
        assert restored.source == "google_calendar"
        assert restored.affected_task_ids == ["t1", "t2"]
        assert restored.metadata["freed_minutes"] == 15

    def test_empty_affected_tasks(self):
        evt = ContextChangeEvent(
            event_type="new_email",
            source="gmail",
            timestamp="2026-02-15T12:00:00Z",
            affected_task_ids=[],
            metadata={},
        )
        assert evt.affected_task_ids == []


class TestDisruptionEvent:
    def test_roundtrip(self):
        evt = DisruptionEvent(
            severity="major",
            affected_task_ids=["t1"],
            freed_minutes=-30,
            recommended_action="swap_out",
            context_summary="Meeting overrun by 30 minutes",
        )
        data = evt.json()
        restored = DisruptionEvent.parse_raw(data)
        assert restored.severity == "major"
        assert restored.freed_minutes == -30
        assert restored.recommended_action == "swap_out"

    def test_positive_freed_minutes(self):
        evt = DisruptionEvent(
            severity="minor",
            affected_task_ids=[],
            freed_minutes=20,
            recommended_action="swap_in",
            context_summary="Meeting ended 20 minutes early",
        )
        assert evt.freed_minutes == 20


class TestEnergyLevel:
    def test_roundtrip(self):
        lvl = EnergyLevel(level=4, confidence=0.85, source="inferred")
        data = lvl.json()
        restored = EnergyLevel.parse_raw(data)
        assert restored.level == 4
        assert restored.confidence == 0.85
        assert restored.source == "inferred"

    def test_user_reported(self):
        lvl = EnergyLevel(level=2, confidence=1.0, source="user_reported")
        assert lvl.level == 2
        assert lvl.confidence == 1.0


class TestUpdatedSchedule:
    def test_roundtrip(self):
        sched = UpdatedSchedule(
            schedule=[
                {"task_id": "t1", "title": "Fix bug", "start_time": "2026-02-15T09:00:00Z"},
                {"task_id": "t2", "title": "Write docs", "start_time": "2026-02-15T10:00:00Z"},
            ],
            swaps=[
                {"action": "swap_in", "task_id": "t2", "reason": "Time freed"},
            ],
            timestamp="2026-02-15T12:00:00Z",
            trigger="disruption",
        )
        data = sched.json()
        restored = UpdatedSchedule.parse_raw(data)
        assert len(restored.schedule) == 2
        assert len(restored.swaps) == 1
        assert restored.trigger == "disruption"

    def test_empty_schedule(self):
        sched = UpdatedSchedule(
            schedule=[],
            swaps=[],
            timestamp="2026-02-15T12:00:00Z",
            trigger="daily_plan",
        )
        assert sched.schedule == []


class TestDelegationTask:
    def test_roundtrip(self):
        dt = DelegationTask(
            task_id="del-1",
            task_type="email_reply",
            context={"recipient": "alice@example.com", "tone": "professional"},
            approval_required=True,
            max_cost_fet=0.5,
        )
        data = dt.json()
        restored = DelegationTask.parse_raw(data)
        assert restored.task_id == "del-1"
        assert restored.task_type == "email_reply"
        assert restored.approval_required is True
        assert restored.max_cost_fet == 0.5
        assert restored.context["recipient"] == "alice@example.com"


class TestTaskCompletion:
    def test_roundtrip(self):
        tc = TaskCompletion(
            task_id="tc-1",
            status="executed",
            result={"confirmation": "Email sent successfully"},
            cost_fet=0.1,
        )
        data = tc.json()
        restored = TaskCompletion.parse_raw(data)
        assert restored.status == "executed"
        assert restored.cost_fet == 0.1


class TestScheduleRequest:
    def test_roundtrip(self):
        req = ScheduleRequest(
            action="plan_day",
            payload={"available_hours": 8},
        )
        data = req.json()
        restored = ScheduleRequest.parse_raw(data)
        assert restored.action == "plan_day"
        assert restored.payload["available_hours"] == 8


class TestSwapOperation:
    def test_roundtrip(self):
        op = SwapOperation(
            action="swap_in",
            task_id="t1",
            reason="Fits 15min gap",
            new_time_slot="2026-02-15T14:00:00Z",
        )
        data = op.json()
        restored = SwapOperation.parse_raw(data)
        assert restored.action == "swap_in"
        assert restored.task_id == "t1"


class TestUserProfile:
    def test_roundtrip(self):
        profile = UserProfile(
            peak_hours=[9, 10, 14, 15],
            avg_task_durations={"email": 5, "deep_work": 52},
            energy_curve=[2] * 24,
            adherence_score=0.75,
            distraction_patterns={"slack": 0.7},
            estimation_bias=1.2,
            automation_comfort={"email": 0.9},
        )
        data = profile.json()
        restored = UserProfile.parse_raw(data)
        assert restored.peak_hours == [9, 10, 14, 15]
        assert restored.estimation_bias == 1.2


class TestEnergyQuery:
    def test_roundtrip(self):
        q = EnergyQuery(user_id="user-1", timestamp="2026-02-15T12:00:00Z")
        data = q.json()
        restored = EnergyQuery.parse_raw(data)
        assert restored.user_id == "user-1"


class TestProfileQuery:
    def test_roundtrip(self):
        q = ProfileQuery(query_type="full_profile", user_id="user-1")
        data = q.json()
        restored = ProfileQuery.parse_raw(data)
        assert restored.query_type == "full_profile"
