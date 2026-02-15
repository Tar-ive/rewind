"""Composio Service — Direct SDK wrapper for deterministic tool execution.

No LLM in the loop.  Each method maps to a single Composio tool action,
called with explicit arguments.  Used by:

- FastAPI REST endpoints (email, calendar, auth, LinkedIn)
- Context Sentinel agent (calendar/email polling)
- Profiler Agent (LinkedIn profile enrichment)
- GhostWorker (draft execution)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from composio import Composio

from src.config.settings import (
    COMPOSIO_API_KEY,
    COMPOSIO_USER_ID,
    GMAIL_AUTH_CONFIG_ID,
    GOOGLE_CALENDAR_AUTH_CONFIG_ID,
    LINKEDIN_AUTH_CONFIG_ID,
    SLACK_AUTH_CONFIG_ID,
)

logger = logging.getLogger(__name__)

# ── Auth Config Mapping ──────────────────────────────────────────────────

TOOLKIT_AUTH_CONFIG = {
    "gmail": GMAIL_AUTH_CONFIG_ID,
    "calendar": GOOGLE_CALENDAR_AUTH_CONFIG_ID,
    "linkedin": LINKEDIN_AUTH_CONFIG_ID,
    "slack": SLACK_AUTH_CONFIG_ID,
}


class ComposioService:
    """Direct Composio SDK wrapper — every method is a single tool.execute() call."""

    def __init__(
        self,
        api_key: str | None = None,
        user_id: str | None = None,
    ):
        self.api_key = api_key or COMPOSIO_API_KEY
        self.user_id = user_id or COMPOSIO_USER_ID
        if not self.api_key:
            logger.warning("COMPOSIO_API_KEY not set — Composio calls will fail")
        self.composio = Composio(api_key=self.api_key) if self.api_key else None

        # Pre-load tool schemas so tools.execute() can find them.
        # SDK v1.0.0-rc2 requires schemas in _tool_schemas before execute().
        if self.composio:
            try:
                for toolkit in ("googlecalendar", "gmail", "linkedin"):
                    self.composio.tools.get(
                        user_id=self.user_id,
                        toolkits=[toolkit],
                    )
                logger.info("Composio tool schemas pre-loaded successfully")
            except Exception as exc:
                logger.warning("Failed to pre-load Composio tool schemas: %s", exc)

    # ── Helper ────────────────────────────────────────────────────────────

    def _execute(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a single Composio tool action."""
        if not self.composio:
            return {"successful": False, "error": "Composio not initialized (missing API key)"}
        try:
            result = self.composio.tools.execute(
                action,
                user_id=self.user_id,
                arguments=arguments,
                dangerously_skip_version_check=True,
            )
            return result if isinstance(result, dict) else {"successful": True, "data": result}
        except Exception as exc:
            logger.exception("Composio execute failed: %s", action)
            return {"successful": False, "error": str(exc)}

    # ══════════════════════════════════════════════════════════════════════
    # Gmail
    # ══════════════════════════════════════════════════════════════════════

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        is_html: bool = False,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Send an email via GMAIL_SEND_EMAIL."""
        args: dict[str, Any] = {
            "recipient_email": to,
            "subject": subject,
            "body": body,
            "is_html": is_html,
        }
        if cc:
            args["cc"] = cc
        if bcc:
            args["bcc"] = bcc
        return self._execute("GMAIL_SEND_EMAIL", args)

    def fetch_emails(
        self,
        query: str = "",
        max_results: int = 20,
        include_payload: bool = True,
    ) -> dict[str, Any]:
        """Fetch email list via GMAIL_FETCH_EMAILS."""
        return self._execute("GMAIL_FETCH_EMAILS", {
            "query": query,
            "max_results": max_results,
            "include_payload": include_payload,
        })

    def fetch_email_by_id(self, message_id: str) -> dict[str, Any]:
        """Fetch a single email by message ID."""
        return self._execute("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {
            "message_id": message_id,
        })

    def create_email_draft(
        self,
        to: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> dict[str, Any]:
        """Create an email draft via GMAIL_CREATE_EMAIL_DRAFT."""
        return self._execute("GMAIL_CREATE_EMAIL_DRAFT", {
            "recipient_email": to,
            "subject": subject,
            "body": body,
            "is_html": is_html,
        })

    # ══════════════════════════════════════════════════════════════════════
    # Google Calendar
    # ══════════════════════════════════════════════════════════════════════

    def list_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 250,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """List calendar events via GOOGLECALENDAR_EVENTS_LIST.

        Supports deep past/future with RFC 3339 timestamps.
        Defaults to today if no time range given.
        """
        now = datetime.now(timezone.utc)
        if not time_min:
            time_min = now.replace(hour=0, minute=0, second=0).isoformat()
        if not time_max:
            time_max = (now.replace(hour=23, minute=59, second=59)).isoformat()

        return self._execute("GOOGLECALENDAR_EVENTS_LIST", {
            "calendar_id": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
        })

    def create_event(
        self,
        summary: str,
        start_datetime: str,
        duration_hours: int = 0,
        duration_minutes: int = 30,
        description: str = "",
        attendees: list[str] | None = None,
        timezone_str: str = "America/Los_Angeles",
        calendar_id: str = "primary",
        create_meeting_room: bool = False,
    ) -> dict[str, Any]:
        """Create a calendar event via GOOGLECALENDAR_CREATE_EVENT."""
        args: dict[str, Any] = {
            "calendar_id": calendar_id,
            "summary": summary,
            "start_datetime": start_datetime,
            "event_duration_hour": duration_hours,
            "event_duration_minutes": duration_minutes,
            "timezone": timezone_str,
        }
        if description:
            args["description"] = description
        if attendees:
            args["attendees"] = attendees
        if create_meeting_room:
            args["create_meeting_room"] = True
        return self._execute("GOOGLECALENDAR_CREATE_EVENT", args)

    def find_event(
        self,
        query: str,
        time_min: str | None = None,
        time_max: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Search calendar events via GOOGLECALENDAR_FIND_EVENT."""
        now = datetime.now(timezone.utc)
        args: dict[str, Any] = {
            "calendar_id": calendar_id,
            "query": query,
        }
        if time_min:
            args["timeMin"] = time_min
        if time_max:
            args["timeMax"] = time_max
        return self._execute("GOOGLECALENDAR_FIND_EVENT", args)

    # ══════════════════════════════════════════════════════════════════════
    # Slack
    # ══════════════════════════════════════════════════════════════════════

    def send_slack_message(
        self,
        channel: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a Slack message via SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL."""
        return self._execute("SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL", {
            "channel": channel,
            "text": text,
        })

    # ══════════════════════════════════════════════════════════════════════
    # LinkedIn (placeholder — not connected)
    # ══════════════════════════════════════════════════════════════════════

    def get_linkedin_profile(self) -> dict[str, Any]:
        """Get authenticated user's LinkedIn profile via LINKEDIN_GET_MY_INFO."""
        return self._execute("LINKEDIN_GET_MY_INFO", {})

    # ══════════════════════════════════════════════════════════════════════
    # OAuth / Connection Management
    # ══════════════════════════════════════════════════════════════════════

    def initiate_connection(
        self,
        toolkit: str,
        callback_url: str = "http://localhost:3000/auth/callback",
    ) -> dict[str, Any]:
        """Initiate OAuth connection for a toolkit.

        Returns {'redirect_url': str, 'request_id': str} on success.
        """
        if not self.composio:
            return {"successful": False, "error": "Composio not initialized"}

        auth_config_id = TOOLKIT_AUTH_CONFIG.get(toolkit)
        if not auth_config_id:
            return {"successful": False, "error": f"Unknown toolkit: {toolkit}. Valid: {list(TOOLKIT_AUTH_CONFIG.keys())}"}

        try:
            req = self.composio.connected_accounts.initiate(
                user_id=self.user_id,
                auth_config_id=auth_config_id,
                config={"auth_scheme": "OAUTH2"},
                callback_url=callback_url,
                allow_multiple=True,
            )
            return {
                "successful": True,
                "redirect_url": req.redirect_url,
                "request_id": req.id,
            }
        except Exception as exc:
            logger.exception("OAuth initiation failed for %s", toolkit)
            return {"successful": False, "error": str(exc)}

    def check_connections(self) -> dict[str, Any]:
        """Check which toolkits have active connections for the current user."""
        if not self.composio:
            return {"connections": [], "error": "Composio not initialized"}

        try:
            response = self.composio.connected_accounts.list(
                user_ids=[self.user_id],
                statuses=["ACTIVE"],
            )
            items = []
            if hasattr(response, "items"):
                items = response.items
            else:
                for key, val in response:
                    if key == "items" and isinstance(val, list):
                        items = val
                        break
            connections = []
            for acct in items:
                toolkit_slug = ""
                if hasattr(acct, "toolkit") and hasattr(acct.toolkit, "slug"):
                    toolkit_slug = acct.toolkit.slug
                created = str(getattr(acct, "created_at", ""))
                connections.append({
                    "id": getattr(acct, "id", ""),
                    "app": toolkit_slug,
                    "status": getattr(acct, "status", "UNKNOWN"),
                    "created_at": created,
                })
            return {"successful": True, "connections": connections}
        except Exception as exc:
            logger.exception("Connection status check failed")
            return {"successful": False, "connections": [], "error": str(exc)}

    def disconnect_account(self, connection_id: str) -> dict[str, Any]:
        """Delete a connected account by its ID."""
        if not self.composio:
            return {"successful": False, "error": "Composio not initialized"}
        try:
            self.composio.connected_accounts.delete(connection_id)
            return {"successful": True}
        except Exception as exc:
            logger.exception("Failed to disconnect account %s", connection_id)
            return {"successful": False, "error": str(exc)}


# ── Singleton for shared use across server + agents ───────────────────────

_instance: ComposioService | None = None


def get_composio_service() -> ComposioService:
    """Return a shared ComposioService singleton."""
    global _instance
    if _instance is None:
        _instance = ComposioService()
    return _instance
