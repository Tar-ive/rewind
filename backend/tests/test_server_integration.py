"""Integration tests for FastAPI server endpoints.

Uses httpx.AsyncClient with ASGITransport to test the REST API
without starting a real server. Redis is patched to use fakeredis.
"""

import json
import pytest
import fakeredis
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from src.models.task import Task, Priority, TaskStatus


# ── Patch Redis before importing the server ──────────────────────────────

@pytest.fixture
def fake_redis():
    """Create a shared fakeredis instance for this test."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def patched_app(fake_redis):
    """Import and patch the FastAPI app to use fakeredis everywhere."""
    # Patch all _get_redis functions across modules
    with (
        patch("src.server._get_redis", return_value=fake_redis),
        patch("src.engine.task_buffer._get_redis", return_value=fake_redis),
        patch("src.engine.lts._get_redis", return_value=fake_redis),
        patch("src.engine.mts._get_redis", return_value=fake_redis),
    ):
        from src.server import app
        yield app


@pytest.fixture
async def client(patched_app):
    transport = ASGITransport(app=patched_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _seed_tasks(r, make_task):
    """Seed a set of test tasks into Redis."""
    tasks = [
        make_task(
            task_id="api-t1",
            title="Write API docs",
            priority=Priority.P1_IMPORTANT,
            energy_cost=3,
            estimated_duration=45,
            status=TaskStatus.BACKLOG,
        ),
        make_task(
            task_id="api-t2",
            title="Fix login bug",
            priority=Priority.P0_URGENT,
            energy_cost=4,
            estimated_duration=60,
            status=TaskStatus.BACKLOG,
        ),
        make_task(
            task_id="api-t3",
            title="Refactor tests",
            priority=Priority.P3_BACKGROUND,
            energy_cost=1,
            estimated_duration=20,
            status=TaskStatus.BACKLOG,
            task_type="admin",
        ),
    ]
    for t in tasks:
        t.to_redis(r)
    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "redis" in data
        assert "energy_level" in data


# ═══════════════════════════════════════════════════════════════════════════
# Schedule Endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestScheduleEndpoints:
    @pytest.mark.asyncio
    async def test_get_schedule_empty(self, client):
        resp = await client.get("/api/schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []

    @pytest.mark.asyncio
    async def test_plan_day_activates_tasks(self, client, fake_redis, make_task):
        _seed_tasks(fake_redis, make_task)
        resp = await client.post("/api/schedule/plan-day", json={"available_hours": 8})
        assert resp.status_code == 200
        data = resp.json()
        assert data["planned"] > 0
        assert len(data["tasks"]) > 0

    @pytest.mark.asyncio
    async def test_plan_day_schedule_visible_via_get(self, client, fake_redis, make_task):
        _seed_tasks(fake_redis, make_task)
        await client.post("/api/schedule/plan-day", json={"available_hours": 8})
        resp = await client.get("/api/schedule")
        data = resp.json()
        assert len(data["tasks"]) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Disruption Endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestDisruptionEndpoint:
    @pytest.mark.asyncio
    async def test_disruption_meeting_ended_early(self, client, fake_redis, make_task):
        """Simulate a meeting ending early — should classify and return swap info."""
        _seed_tasks(fake_redis, make_task)
        # First, plan day so we have active tasks
        await client.post("/api/schedule/plan-day", json={"available_hours": 8})

        resp = await client.post("/api/disruption", json={
            "event_type": "meeting_ended_early",
            "source": "google_calendar",
            "affected_task_ids": ["api-t1"],
            "freed_minutes": 30,
            "metadata": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] in ("minor", "major", "critical")
        assert data["freed_minutes"] == 30
        assert "action" in data

    @pytest.mark.asyncio
    async def test_disruption_meeting_overrun(self, client, fake_redis, make_task):
        _seed_tasks(fake_redis, make_task)
        await client.post("/api/schedule/plan-day", json={"available_hours": 8})

        resp = await client.post("/api/disruption", json={
            "event_type": "meeting_overrun",
            "source": "google_calendar",
            "affected_task_ids": ["api-t1"],
            "lost_minutes": 45,
            "metadata": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["freed_minutes"] == -45
        assert data["action"] in ("swap_out", "delegate", "reschedule_all")


# ═══════════════════════════════════════════════════════════════════════════
# Energy Endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestEnergyEndpoint:
    @pytest.mark.asyncio
    async def test_update_energy(self, client):
        resp = await client.post("/api/energy", json={"level": 4})
        assert resp.status_code == 200
        data = resp.json()
        assert data["energy_level"] == 4

    @pytest.mark.asyncio
    async def test_update_energy_clamps(self, client):
        resp = await client.post("/api/energy", json={"level": 10})
        assert resp.status_code == 200
        assert resp.json()["energy_level"] == 5

    @pytest.mark.asyncio
    async def test_energy_status(self, client):
        resp = await client.get("/api/energy/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "level" in data


# ═══════════════════════════════════════════════════════════════════════════
# Backlog Endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestBacklogEndpoint:
    @pytest.mark.asyncio
    async def test_get_backlog_empty(self, client):
        resp = await client.get("/api/backlog")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    @pytest.mark.asyncio
    async def test_get_backlog_with_tasks(self, client, fake_redis, make_task):
        _seed_tasks(fake_redis, make_task)
        resp = await client.get("/api/backlog")
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) == 3
