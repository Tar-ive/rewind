"""WebSocket communication layer tests.

Uses Starlette's TestClient for WebSocket testing and httpx for
REST endpoints that trigger broadcasts.
"""

import json
import pytest
import fakeredis
from unittest.mock import patch
from starlette.testclient import TestClient

from src.models.task import Task, Priority, TaskStatus


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def patched_app(fake_redis):
    """Import and patch the FastAPI app to use fakeredis."""
    with (
        patch("src.server._get_redis", return_value=fake_redis),
        patch("src.engine.task_buffer._get_redis", return_value=fake_redis),
        patch("src.engine.lts._get_redis", return_value=fake_redis),
        patch("src.engine.mts._get_redis", return_value=fake_redis),
    ):
        from src.server import app
        yield app


@pytest.fixture
def test_client(patched_app):
    """Starlette test client for sync WebSocket testing."""
    return TestClient(patched_app)


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWebSocket:
    def test_ws_connect_receives_initial_schedule(self, test_client):
        """On connect, the server sends an initial updated_schedule message."""
        with test_client.websocket_connect("/ws") as ws:
            data = ws.receive_text()
            msg = json.loads(data)
            assert msg["type"] == "updated_schedule"
            assert "payload" in msg
            assert "timestamp" in msg
            assert "tasks" in msg["payload"]

    def test_ws_initial_schedule_has_energy(self, test_client):
        """Initial schedule message includes energy info."""
        with test_client.websocket_connect("/ws") as ws:
            data = ws.receive_text()
            msg = json.loads(data)
            payload = msg["payload"]
            assert "energy" in payload
            assert "level" in payload["energy"]

    def test_ws_message_format(self, test_client):
        """All WS messages follow the {type, payload, timestamp} schema."""
        with test_client.websocket_connect("/ws") as ws:
            data = ws.receive_text()
            msg = json.loads(data)
            assert set(msg.keys()) == {"type", "payload", "timestamp"}

    def test_disruption_broadcasts_to_ws(self, test_client, fake_redis, make_task):
        """POST /api/disruption sends disruption_event, agent_activity, and updated_schedule."""
        # Seed a task
        t = make_task(task_id="ws-t1", status=TaskStatus.BACKLOG, estimated_duration=20,
                      energy_cost=2)
        t.to_redis(fake_redis)
        # Plan day to get active tasks
        test_client.post("/api/schedule/plan-day", json={"available_hours": 8})

        with test_client.websocket_connect("/ws") as ws:
            # Consume the initial schedule message
            ws.receive_text()

            # Trigger disruption via REST
            test_client.post("/api/disruption", json={
                "event_type": "meeting_ended_early",
                "source": "google_calendar",
                "affected_task_ids": [],
                "freed_minutes": 15,
                "metadata": {},
            })

            # Collect all messages from this disruption
            messages = []
            for _ in range(10):  # read up to 10 messages (safety bound)
                raw = ws.receive_text()
                msg = json.loads(raw)
                messages.append(msg)
                # Stop when we see the final updated_schedule
                if msg["type"] == "updated_schedule":
                    break

            types = [m["type"] for m in messages]

            # Must contain disruption_event
            assert "disruption_event" in types
            disruption = next(m for m in messages if m["type"] == "disruption_event")
            assert disruption["payload"]["severity"] in ("minor", "major", "critical")
            assert disruption["payload"]["freed_minutes"] == 15

            # Must contain agent_activity entries (from new improvements)
            assert "agent_activity" in types

            # Must end with updated_schedule
            assert types[-1] == "updated_schedule"

    def test_energy_update_broadcasts_to_ws(self, test_client):
        """POST /api/energy sends energy_update to WS clients."""
        with test_client.websocket_connect("/ws") as ws:
            # Consume initial schedule
            ws.receive_text()

            # Update energy via REST
            test_client.post("/api/energy", json={"level": 2})

            # Should receive energy_update WS message
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "energy_update"
            assert msg["payload"]["level"] == 2
            assert msg["payload"]["source"] == "user_reported"

    def test_plan_day_broadcasts_to_ws(self, test_client, fake_redis, make_task):
        """POST /api/schedule/plan-day broadcasts updated_schedule to WS."""
        # Seed tasks
        t = make_task(task_id="ws-plan-1", status=TaskStatus.BACKLOG)
        t.to_redis(fake_redis)

        with test_client.websocket_connect("/ws") as ws:
            ws.receive_text()  # consume initial

            test_client.post("/api/schedule/plan-day", json={"available_hours": 8})

            msg = json.loads(ws.receive_text())
            assert msg["type"] == "updated_schedule"
            assert "tasks" in msg["payload"]
