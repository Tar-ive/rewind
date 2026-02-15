"""Tests for the scheduling engine: LTS, MTS, STS, TaskBuffer, DisruptionClassifier."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.models.task import Task, Priority, TaskStatus, BUCKET_COUNT
from src.engine.sts import ShortTermScheduler
from src.engine.disruption_classifier import (
    classify_severity,
    calculate_freed_minutes,
    determine_action,
)


# ═══════════════════════════════════════════════════════════════════════════
# Disruption Classifier (pure functions — no Redis needed)
# ═══════════════════════════════════════════════════════════════════════════


class TestDisruptionClassifier:
    def test_classify_minor_stays_minor(self):
        """meeting_ended_early with 0 affected tasks → minor."""
        severity = classify_severity("meeting_ended_early", [], {})
        assert severity == "minor"

    def test_classify_minor_escalates_to_major(self):
        """meeting_ended_early with >=3 affected tasks → major."""
        ids = ["t1", "t2", "t3"]
        severity = classify_severity("meeting_ended_early", ids, {})
        assert severity == "major"

    def test_classify_major_base(self):
        """schedule_conflict base severity is major."""
        severity = classify_severity("schedule_conflict", [], {})
        assert severity == "major"

    def test_classify_major_escalates_to_critical(self):
        """schedule_conflict with >=4 affected tasks → critical."""
        ids = ["t1", "t2", "t3", "t4"]
        severity = classify_severity("schedule_conflict", ids, {})
        assert severity == "critical"

    def test_classify_meeting_overrun_major(self):
        severity = classify_severity("meeting_overrun", ["t1"], {})
        assert severity == "major"

    def test_classify_urgent_email_escalates(self):
        """new_email with urgent flag → major."""
        severity = classify_severity("new_email", [], {"urgent": True})
        assert severity == "major"

    def test_classify_unknown_event_type(self):
        """Unknown event type → minor (default)."""
        severity = classify_severity("alien_invasion", [], {})
        assert severity == "minor"

    # ── calculate_freed_minutes ──────────────────────────────────────────

    def test_freed_minutes_meeting_ended_early(self):
        result = calculate_freed_minutes("meeting_ended_early", {"freed_minutes": 20})
        assert result == 20

    def test_freed_minutes_meeting_ended_early_default(self):
        result = calculate_freed_minutes("meeting_ended_early", {})
        assert result == 15

    def test_freed_minutes_cancelled_meeting(self):
        result = calculate_freed_minutes("cancelled_meeting", {"freed_minutes": 60})
        assert result == 60

    def test_freed_minutes_meeting_overrun_negative(self):
        result = calculate_freed_minutes("meeting_overrun", {"lost_minutes": 30})
        assert result == -30

    def test_freed_minutes_meeting_overrun_default(self):
        result = calculate_freed_minutes("meeting_overrun", {})
        assert result == -30

    def test_freed_minutes_task_completed(self):
        result = calculate_freed_minutes("task_completed", {"saved_minutes": 10})
        assert result == 10

    def test_freed_minutes_urgent_email(self):
        result = calculate_freed_minutes("new_email", {"urgent": True})
        assert result == -15

    def test_freed_minutes_non_urgent_email(self):
        result = calculate_freed_minutes("new_email", {})
        assert result == 0

    # ── determine_action ─────────────────────────────────────────────────

    def test_action_critical_reschedules_all(self):
        assert determine_action("critical", -60) == "reschedule_all"

    def test_action_critical_positive_still_reschedules(self):
        assert determine_action("critical", 30) == "reschedule_all"

    def test_action_swap_in_on_positive(self):
        assert determine_action("minor", 30) == "swap_in"

    def test_action_major_negative_swap_out(self):
        assert determine_action("major", -30) == "swap_out"

    def test_action_minor_negative_delegate(self):
        assert determine_action("minor", -15) == "delegate"

    def test_action_zero_minutes(self):
        assert determine_action("minor", 0) == "swap_in"


# ═══════════════════════════════════════════════════════════════════════════
# STS (Short-Term Scheduler) — MLFQ
# ═══════════════════════════════════════════════════════════════════════════


class TestSTS:
    @pytest.fixture
    def sts(self):
        return ShortTermScheduler()

    def _make_task(self, task_id, priority, energy_cost=2, duration=30, deadline=""):
        return Task(
            task_id=task_id,
            title=f"Task {task_id}",
            priority=priority,
            energy_cost=energy_cost,
            estimated_duration=duration,
            deadline=deadline,
        )

    def test_enqueue_dequeue_priority_order(self, sts):
        """P0 dequeued before P1 before P3."""
        p3 = self._make_task("p3", Priority.P3_BACKGROUND)
        p0 = self._make_task("p0", Priority.P0_URGENT)
        p1 = self._make_task("p1", Priority.P1_IMPORTANT)

        sts.enqueue(p3)
        sts.enqueue(p0)
        sts.enqueue(p1)

        first = sts.dequeue(energy_level=5)
        assert first.task_id == "p0"
        second = sts.dequeue(energy_level=5)
        assert second.task_id == "p1"
        third = sts.dequeue(energy_level=5)
        assert third.task_id == "p3"

    def test_energy_constraint_skips_costly_task(self, sts):
        """Energy=2 skips a task with energy_cost=4, returns the cheaper one."""
        expensive = self._make_task("exp", Priority.P1_IMPORTANT, energy_cost=4)
        cheap = self._make_task("cheap", Priority.P2_NORMAL, energy_cost=1)
        sts.enqueue(expensive)
        sts.enqueue(cheap)

        result = sts.dequeue(energy_level=2)
        # Should skip expensive P1 (cost 4 > energy 2) and return cheap P2
        assert result.task_id == "cheap"

    def test_energy_constraint_returns_none_when_all_too_costly(self, sts):
        """All tasks too costly → returns None."""
        t = self._make_task("costly", Priority.P0_URGENT, energy_cost=5)
        sts.enqueue(t)
        assert sts.dequeue(energy_level=1) is None

    def test_auto_delegate_p3_low_energy(self, sts):
        """energy <= 2 delegates all P3 tasks."""
        p3a = self._make_task("p3a", Priority.P3_BACKGROUND, energy_cost=1)
        p3b = self._make_task("p3b", Priority.P3_BACKGROUND, energy_cost=1)
        p2 = self._make_task("p2", Priority.P2_NORMAL, energy_cost=2)

        sts.enqueue(p3a)
        sts.enqueue(p3b)
        sts.enqueue(p2)

        delegated = sts.auto_delegate_p3(energy_level=1)
        assert len(delegated) == 2
        assert all(t.status == TaskStatus.DELEGATED for t in delegated)

        # P2 should still be in the queue
        remaining = sts.dequeue(energy_level=5)
        assert remaining.task_id == "p2"

    def test_auto_delegate_p3_high_energy_noop(self, sts):
        """energy > 2 → no delegation."""
        p3 = self._make_task("p3", Priority.P3_BACKGROUND)
        sts.enqueue(p3)
        delegated = sts.auto_delegate_p3(energy_level=3)
        assert delegated == []

    def test_preempt_saves_current_task(self, sts):
        """Preemption: current P2 task is interrupted by P0 urgent task."""
        current = self._make_task("current", Priority.P2_NORMAL)
        urgent = self._make_task("urgent", Priority.P0_URGENT)

        sts.set_current(current)
        preempted = sts.preempt(urgent, energy_level=5)

        assert preempted is not None
        assert preempted.task_id == "current"
        assert sts.get_current().task_id == "urgent"

    def test_preempt_lower_priority_no_preemption(self, sts):
        """P3 cannot preempt currently running P0."""
        current = self._make_task("current", Priority.P0_URGENT)
        low = self._make_task("low", Priority.P3_BACKGROUND)

        sts.set_current(current)
        preempted = sts.preempt(low, energy_level=5)

        assert preempted is None
        assert sts.get_current().task_id == "current"

    def test_queue_counts(self, sts):
        sts.enqueue(self._make_task("a", Priority.P0_URGENT))
        sts.enqueue(self._make_task("b", Priority.P1_IMPORTANT))
        sts.enqueue(self._make_task("c", Priority.P2_NORMAL))
        sts.enqueue(self._make_task("d", Priority.P3_BACKGROUND))
        counts = sts.queue_counts()
        assert counts["P0_URGENT"] == 1
        assert counts["P1_IMPORTANT"] == 1
        assert counts["P2_NORMAL"] == 1
        assert counts["P3_BACKGROUND"] == 1

    def test_get_ordered_schedule_respects_energy(self, sts):
        """Tasks exceeding energy budget are deferred to the end."""
        cheap = self._make_task("cheap", Priority.P1_IMPORTANT, energy_cost=1)
        expensive = self._make_task("exp", Priority.P0_URGENT, energy_cost=5)
        sts.enqueue(cheap)
        sts.enqueue(expensive)

        schedule = sts.get_ordered_schedule(energy_level=2)
        # Cheap should come first despite lower priority (energy-compatible)
        assert schedule[0].task_id == "cheap"
        assert schedule[1].task_id == "exp"  # deferred

    def test_reorder_clears_and_rebuilds(self, sts):
        t1 = self._make_task("t1", Priority.P2_NORMAL)
        t2 = self._make_task("t2", Priority.P0_URGENT)
        sts.enqueue(t1)
        assert sts.total_count == 1

        sts.reorder([t1, t2])
        assert sts.total_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# Task Buffer (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskBuffer:
    """Tests for task_buffer functions using fakeredis."""

    def test_store_and_get_task(self, r, make_task):
        from src.engine.task_buffer import store_task, get_task
        task = make_task(task_id="buf-1")
        store_task(task, r)
        loaded = get_task("buf-1", r)
        assert loaded is not None
        assert loaded.task_id == "buf-1"

    def test_remove_task(self, r, make_task):
        from src.engine.task_buffer import store_task, get_task, remove_task
        task = make_task(task_id="buf-2")
        store_task(task, r)
        remove_task("buf-2", r)
        assert get_task("buf-2", r) is None

    def test_get_backlog_tasks(self, r, make_task):
        from src.engine.task_buffer import store_task, get_backlog_tasks
        t1 = make_task(task_id="bl-1", status=TaskStatus.BACKLOG)
        t2 = make_task(task_id="bl-2", status=TaskStatus.BACKLOG)
        t3 = make_task(task_id="act-1", status=TaskStatus.ACTIVE)
        store_task(t1, r)
        store_task(t2, r)
        store_task(t3, r)
        backlog = get_backlog_tasks(r)
        ids = {t.task_id for t in backlog}
        assert "bl-1" in ids
        assert "bl-2" in ids
        assert "act-1" not in ids

    def test_get_active_tasks(self, r, make_task):
        from src.engine.task_buffer import store_task, get_active_tasks
        t1 = make_task(task_id="act-1", status=TaskStatus.ACTIVE)
        t2 = make_task(task_id="ip-1", status=TaskStatus.IN_PROGRESS)
        t3 = make_task(task_id="bl-1", status=TaskStatus.BACKLOG)
        store_task(t1, r)
        store_task(t2, r)
        store_task(t3, r)
        active = get_active_tasks(r)
        ids = {t.task_id for t in active}
        assert "act-1" in ids
        assert "ip-1" in ids
        assert "bl-1" not in ids

    def test_find_swap_candidates_filters_duration_and_energy(self, r, make_task):
        from src.engine.task_buffer import store_task, find_swap_candidates
        # Fits: 20 min, energy 2
        fits = make_task(task_id="fits", estimated_duration=20, energy_cost=2,
                         status=TaskStatus.BACKLOG)
        # Too long
        too_long = make_task(task_id="toolong", estimated_duration=120, energy_cost=2,
                             status=TaskStatus.BACKLOG)
        # Too costly
        too_costly = make_task(task_id="costly", estimated_duration=20, energy_cost=5,
                               status=TaskStatus.BACKLOG)
        store_task(fits, r)
        store_task(too_long, r)
        store_task(too_costly, r)

        candidates = find_swap_candidates(
            available_minutes=30,
            energy_level=3,
            r=r,
        )
        ids = {t.task_id for t in candidates}
        assert "fits" in ids
        assert "toolong" not in ids
        assert "costly" not in ids

    def test_find_swap_out_candidates_lowest_priority_first(self, r, make_task):
        from src.engine.task_buffer import store_task, find_swap_out_candidates
        # Active tasks
        p0 = make_task(task_id="p0", priority=Priority.P0_URGENT,
                       status=TaskStatus.ACTIVE, estimated_duration=30)
        p3 = make_task(task_id="p3", priority=Priority.P3_BACKGROUND,
                       status=TaskStatus.ACTIVE, estimated_duration=30)
        store_task(p0, r)
        store_task(p3, r)

        candidates = find_swap_out_candidates(minutes_needed=30, r=r)
        # P3 (lowest priority) should be first swap-out candidate
        assert len(candidates) >= 1
        assert candidates[0].task_id == "p3"

    def test_get_bucket_tasks(self, r, make_task):
        from src.engine.task_buffer import store_task, get_bucket_tasks
        task = make_task(task_id="bkt-test")
        store_task(task, r)
        bucket = task.bucket
        tasks_in_bucket = get_bucket_tasks(bucket, r)
        ids = {t.task_id for t in tasks_in_bucket}
        assert "bkt-test" in ids


# ═══════════════════════════════════════════════════════════════════════════
# LTS (Long-Term Scheduler) — needs Redis patching
# ═══════════════════════════════════════════════════════════════════════════


class TestLTS:
    """Tests for the LTS daily planner.

    We patch the module-level _get_redis and task_buffer's _get_redis so
    that all Redis operations use our fakeredis instance.
    """

    def test_plan_day_empty_backlog(self, r):
        from src.engine.lts import plan_day
        tasks, sts = plan_day(r=r)
        assert tasks == []
        assert sts.total_count == 0

    def test_plan_day_selects_and_activates(self, r, sample_backlog):
        from src.engine.lts import plan_day
        tasks, sts = plan_day(available_hours=8, r=r)
        assert len(tasks) > 0
        for t in tasks:
            assert t.status == TaskStatus.ACTIVE

    def test_plan_day_respects_available_hours(self, r, sample_backlog):
        """Total planned duration should not exceed available_hours * 60."""
        from src.engine.lts import plan_day
        tasks, sts = plan_day(available_hours=2, r=r)  # only 120 min
        total_min = sum(t.estimated_duration for t in tasks)
        assert total_min <= 120

    def test_plan_day_builds_sts(self, r, sample_backlog):
        """plan_day returns a populated STS instance."""
        from src.engine.lts import plan_day
        tasks, sts = plan_day(available_hours=8, r=r)
        assert sts.total_count == len(tasks)

    def test_plan_day_estimation_bias(self, r, make_task):
        """Estimation bias > 1 inflates durations → fewer tasks fit."""
        # Create tasks that barely fit into 2 hours at bias=1.0
        for i in range(4):
            t = make_task(task_id=f"bias-{i}", estimated_duration=30)
            t.to_redis(r)

        from src.engine.lts import plan_day
        normal_tasks, _ = plan_day(available_hours=2, estimation_bias=1.0, r=r)
        normal_count = len(normal_tasks)

        # Reset tasks to backlog
        for t in normal_tasks:
            t.status = TaskStatus.BACKLOG
            t.to_redis(r)

        biased_tasks, _ = plan_day(available_hours=2, estimation_bias=2.0, r=r)
        # With 2x bias, 30min tasks become 60min → fewer fit in 120min
        assert len(biased_tasks) <= normal_count


# ═══════════════════════════════════════════════════════════════════════════
# MTS (Medium-Term Scheduler)
# ═══════════════════════════════════════════════════════════════════════════


class TestMTS:
    def test_handle_disruption_swap_in(self, r, make_task):
        """Positive freed_minutes → swap-in from backlog."""
        from src.engine.mts import handle_disruption
        # Seed a small backlog task
        backlog_task = make_task(
            task_id="swap-in-1",
            estimated_duration=15,
            energy_cost=2,
            status=TaskStatus.BACKLOG,
        )
        backlog_task.to_redis(r)

        result = handle_disruption(
            freed_minutes=30,
            energy_level=3,
            r=r,
        )
        assert len(result.swapped_in) >= 1
        assert result.swapped_in[0].task_id == "swap-in-1"
        assert result.swapped_in[0].status == TaskStatus.ACTIVE

    def test_handle_disruption_swap_out(self, r, make_task):
        """Negative freed_minutes → swap-out active tasks."""
        from src.engine.mts import handle_disruption
        active_task = make_task(
            task_id="swap-out-1",
            estimated_duration=60,
            priority=Priority.P3_BACKGROUND,
            status=TaskStatus.ACTIVE,
        )
        active_task.to_redis(r)

        result = handle_disruption(
            freed_minutes=-30,
            energy_level=3,
            r=r,
        )
        assert len(result.swapped_out) >= 1
        assert result.swapped_out[0].status == TaskStatus.SWAPPED_OUT

    def test_handle_disruption_zero_reorders(self, r, make_task):
        """Zero freed_minutes → reorder only, no swaps."""
        from src.engine.mts import handle_disruption
        sts = ShortTermScheduler()
        task = make_task(task_id="reorder-1", status=TaskStatus.ACTIVE)
        task.to_redis(r)
        sts.enqueue(task)

        result = handle_disruption(
            freed_minutes=0,
            energy_level=3,
            sts=sts,
            r=r,
        )
        assert result.swapped_in == []
        assert result.swapped_out == []

    def test_swap_out_auto_delegates_p3_low_energy(self, r, make_task):
        """Swap-out with low energy auto-delegates P3 tasks via STS."""
        from src.engine.mts import handle_swap_out
        sts = ShortTermScheduler()

        # Active P3 in STS
        p3 = make_task(task_id="del-p3", priority=Priority.P3_BACKGROUND,
                       energy_cost=1, status=TaskStatus.ACTIVE,
                       estimated_duration=15)
        p3.to_redis(r)
        sts.enqueue(p3)

        # Another active task to be swapped out
        active = make_task(task_id="swap-out-2", priority=Priority.P2_NORMAL,
                           status=TaskStatus.ACTIVE, estimated_duration=30)
        active.to_redis(r)

        result = handle_swap_out(
            lost_minutes=30,
            energy_level=1,  # very low → triggers delegation
            sts=sts,
            r=r,
        )
        # P3 task should be delegated
        assert len(result.delegated) >= 1
        delegated_ids = {t.task_id for t in result.delegated}
        assert "del-p3" in delegated_ids

    def test_preemption(self, r, make_task):
        """Handle preemption: urgent task preempts current work."""
        from src.engine.mts import handle_preemption
        sts = ShortTermScheduler()
        current = make_task(task_id="curr", priority=Priority.P2_NORMAL,
                            status=TaskStatus.IN_PROGRESS)
        sts.set_current(current)

        urgent = make_task(task_id="urg", priority=Priority.P0_URGENT,
                           estimated_duration=30)

        result = handle_preemption(urgent, energy_level=5, sts=sts, r=r)
        assert len(result.swapped_in) == 1
        assert result.swapped_in[0].task_id == "urg"
