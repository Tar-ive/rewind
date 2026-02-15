"""Short-Term Scheduler (STS) — MLFQ Priority Queues.

Modified Multilevel Feedback Queue adapted for human tasks:
  P0 (Urgent):     Hard deadlines within 2 hours, external dependencies
  P1 (Important):  Deadlines today, high-impact, upstream blockers
  P2 (Normal):     Routine tasks, flexible deadlines, personal goals
  P3 (Background): Nice-to-haves, low-energy fillers, delegatable

Energy constraint: never schedule energy_cost > energy_level.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.models.task import Task, Priority, TaskStatus


@dataclass(order=True)
class _QueueEntry:
    """Priority queue entry. Lower sort_key = higher priority."""
    sort_key: float
    task: Task = field(compare=False)


class ShortTermScheduler:
    """MLFQ with 4 priority levels and energy-aware scheduling."""

    def __init__(self):
        # 4 priority queues (min-heaps)
        self._queues: dict[int, list[_QueueEntry]] = {
            Priority.P0_URGENT: [],
            Priority.P1_IMPORTANT: [],
            Priority.P2_NORMAL: [],
            Priority.P3_BACKGROUND: [],
        }
        # Currently executing task (for preemption)
        self._current_task: Optional[Task] = None
        # Tasks delegated to GhostWorker
        self._delegation_queue: list[Task] = []

    def enqueue(self, task: Task) -> None:
        """Add a task to the appropriate priority queue."""
        priority = self._classify_priority(task)
        task.priority = priority
        # Sort within priority level by deadline urgency (higher urgency = lower sort_key)
        sort_key = -task.deadline_urgency
        heapq.heappush(self._queues[priority], _QueueEntry(sort_key, task))

    def enqueue_batch(self, tasks: list[Task]) -> None:
        """Add multiple tasks, then rebalance."""
        for task in tasks:
            self.enqueue(task)

    def dequeue(self, energy_level: int = 5) -> Optional[Task]:
        """Get the next task to execute, respecting energy constraints.

        Scans from P0 to P3. Skips tasks whose energy_cost > energy_level.
        If energy is low and only P3 tasks remain, auto-delegates them.
        """
        for priority in (Priority.P0_URGENT, Priority.P1_IMPORTANT,
                         Priority.P2_NORMAL, Priority.P3_BACKGROUND):
            queue = self._queues[priority]
            # Find first task that fits energy budget
            skipped = []
            result = None
            while queue:
                entry = heapq.heappop(queue)
                if entry.task.energy_cost <= energy_level:
                    result = entry.task
                    # Put skipped entries back
                    for s in skipped:
                        heapq.heappush(queue, s)
                    break
                skipped.append(entry)
            else:
                # Put all skipped entries back if nothing found
                for s in skipped:
                    heapq.heappush(queue, s)

            if result:
                return result

        return None

    def preempt(self, urgent_task: Task, energy_level: int = 5) -> Optional[Task]:
        """Preemptively interrupt current task for a more urgent one.

        Returns the preempted task (with saved state) or None if no preemption needed.
        """
        if not self._current_task:
            self._current_task = urgent_task
            return None

        current_priority = self._current_task.priority
        urgent_priority = self._classify_priority(urgent_task)

        if urgent_priority < current_priority:  # lower number = higher priority
            # Save state of current task
            preempted = self._current_task
            preempted.status = TaskStatus.ACTIVE  # back to ready queue
            # Re-enqueue preempted task
            self.enqueue(preempted)
            # Switch to urgent task
            self._current_task = urgent_task
            return preempted

        # Not urgent enough to preempt; just enqueue
        self.enqueue(urgent_task)
        return None

    def set_current(self, task: Task) -> None:
        """Mark a task as currently executing."""
        self._current_task = task
        task.status = TaskStatus.IN_PROGRESS

    def get_current(self) -> Optional[Task]:
        return self._current_task

    def clear_current(self) -> None:
        self._current_task = None

    def auto_delegate_p3(self, energy_level: int) -> list[Task]:
        """When energy is low, delegate all P3 tasks to GhostWorker."""
        if energy_level > 2:
            return []

        delegated = []
        queue = self._queues[Priority.P3_BACKGROUND]
        while queue:
            entry = heapq.heappop(queue)
            entry.task.status = TaskStatus.DELEGATED
            delegated.append(entry.task)
            self._delegation_queue.append(entry.task)
        return delegated

    def get_delegation_queue(self) -> list[Task]:
        """Get and clear the delegation queue."""
        q = list(self._delegation_queue)
        self._delegation_queue.clear()
        return q

    def get_ordered_schedule(self, energy_level: int = 5) -> list[Task]:
        """Return all queued tasks in execution order (non-destructive).

        Respects energy constraints: tasks above energy budget are placed
        at the end.
        """
        schedule = []
        deferred = []

        for priority in (Priority.P0_URGENT, Priority.P1_IMPORTANT,
                         Priority.P2_NORMAL, Priority.P3_BACKGROUND):
            entries = sorted(self._queues[priority])
            for entry in entries:
                if entry.task.energy_cost <= energy_level:
                    schedule.append(entry.task)
                else:
                    deferred.append(entry.task)

        return schedule + deferred

    def reorder(self, tasks: list[Task]) -> None:
        """Clear and rebuild all queues from a list of tasks."""
        for q in self._queues.values():
            q.clear()
        self.enqueue_batch(tasks)

    def _classify_priority(self, task: Task) -> int:
        """Auto-classify task priority based on deadline and attributes."""
        # If task already has a manually set priority, respect it
        if task.priority != Priority.P2_NORMAL:
            return task.priority

        now = datetime.now(timezone.utc)

        if task.deadline:
            try:
                dl = datetime.fromisoformat(task.deadline)
                hours_left = (dl - now).total_seconds() / 3600
                if hours_left <= 2:
                    return Priority.P0_URGENT
                elif hours_left <= 24:
                    return Priority.P1_IMPORTANT
            except (ValueError, TypeError):
                pass

        if task.cognitive_load <= 1 and task.energy_cost <= 1:
            return Priority.P3_BACKGROUND

        return task.priority

    @property
    def total_count(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def queue_counts(self) -> dict[str, int]:
        return {
            "P0_URGENT": len(self._queues[Priority.P0_URGENT]),
            "P1_IMPORTANT": len(self._queues[Priority.P1_IMPORTANT]),
            "P2_NORMAL": len(self._queues[Priority.P2_NORMAL]),
            "P3_BACKGROUND": len(self._queues[Priority.P3_BACKGROUND]),
        }
