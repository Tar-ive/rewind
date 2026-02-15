"""Shared test fixtures for the Rewind backend test suite."""

import os
import pytest
import fakeredis
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.models.task import Task, Priority, TaskStatus, BUCKET_COUNT


# ── Redis ────────────────────────────────────────────────────────────────

@pytest.fixture
def r():
    """Fresh fakeredis instance per test (decode_responses=True like production)."""
    return fakeredis.FakeRedis(decode_responses=True)


# ── ASI LLM Config ──────────────────────────────────────────────────────

@pytest.fixture
def asi_config():
    """ASI:One LLM configuration from environment variables."""
    return {
        "api_key": os.getenv("ASI_API_KEY"),
        "api_url": os.getenv("ASI_API_URL", "https://api.asi1.ai/v1/chat/completions"),
        "model": os.getenv("ASI_MODEL", "asi1-mini"),
    }


# ── Time Freezing ───────────────────────────────────────────────────────

@pytest.fixture
def frozen_now():
    """Return a fixed 'now' datetime for deterministic scoring tests.

    Default: 2026-02-15T12:00:00Z (noon UTC on a Saturday).
    """
    return datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def freeze_time(frozen_now):
    """Context-manager fixture that patches datetime.now in the task module.

    Usage in tests:
        with freeze_time:
            score = task.deadline_urgency
    """
    class _Freezer:
        def __enter__(self_):
            self_._patcher = patch("src.models.task.datetime")
            mock_dt = self_._patcher.start()
            mock_dt.now.return_value = frozen_now
            mock_dt.fromisoformat = datetime.fromisoformat
            return mock_dt

        def __exit__(self_, *args):
            self_._patcher.stop()

    return _Freezer()


# ── Task Factories ──────────────────────────────────────────────────────

@pytest.fixture
def make_task():
    """Factory fixture that creates Task instances with sensible defaults.

    Usage:
        task = make_task(title="Write report", priority=Priority.P1_IMPORTANT)
    """
    _counter = 0

    def _factory(**overrides):
        nonlocal _counter
        _counter += 1
        defaults = {
            "task_id": f"test-task-{_counter}",
            "title": f"Test Task {_counter}",
            "description": "A test task",
            "priority": Priority.P2_NORMAL,
            "energy_cost": 3,
            "estimated_duration": 30,
            "status": TaskStatus.BACKLOG,
            "tags": ["test"],
            "task_type": "general",
            "cognitive_load": 3,
        }
        defaults.update(overrides)
        return Task(**defaults)

    return _factory


@pytest.fixture
def sample_backlog(make_task, r):
    """Seed Redis with a diverse set of backlog tasks and return them."""
    now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
    tasks = [
        make_task(
            task_id="urgent-1",
            title="Fix production bug",
            priority=Priority.P0_URGENT,
            energy_cost=4,
            estimated_duration=60,
            deadline=(now + timedelta(hours=1)).isoformat(),
            cognitive_load=5,
        ),
        make_task(
            task_id="important-1",
            title="Prepare presentation",
            priority=Priority.P1_IMPORTANT,
            energy_cost=3,
            estimated_duration=90,
            deadline=(now + timedelta(hours=6)).isoformat(),
            cognitive_load=4,
        ),
        make_task(
            task_id="normal-1",
            title="Review PRs",
            priority=Priority.P2_NORMAL,
            energy_cost=2,
            estimated_duration=30,
            cognitive_load=3,
        ),
        make_task(
            task_id="normal-2",
            title="Write documentation",
            priority=Priority.P2_NORMAL,
            energy_cost=2,
            estimated_duration=45,
            cognitive_load=2,
        ),
        make_task(
            task_id="bg-1",
            title="Organize bookmarks",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=15,
            cognitive_load=1,
            task_type="admin",
        ),
        make_task(
            task_id="bg-2",
            title="Send thank-you emails",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=10,
            cognitive_load=1,
            task_type="email_reply",
        ),
    ]
    for t in tasks:
        t.to_redis(r)
    return tasks
