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
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"exec_no_composio","timestamp":int(_t.time()*1000),"location":"composio_service.py:_execute","message":"Composio not initialized","data":{"action":action},"hypothesisId":"B2"})+"\n")
            # #endregion
            return {"successful": False, "error": "Composio not initialized (missing API key)"}
        try:
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"exec_attempt","timestamp":int(_t.time()*1000),"location":"composio_service.py:_execute","message":"Executing Composio action","data":{"action":action,"user_id":self.user_id,"arg_keys":list(arguments.keys())},"hypothesisId":"B1"})+"\n")
            # #endregion
            result = self.composio.tools.execute(
                action,
                user_id=self.user_id,
                arguments=arguments,
            )
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"exec_success","timestamp":int(_t.time()*1000),"location":"composio_service.py:_execute","message":"Composio action succeeded","data":{"action":action,"result_type":type(result).__name__,"result_keys":list(result.keys()) if isinstance(result,dict) else None},"hypothesisId":"B1"})+"\n")
            # #endregion
            return result if isinstance(result, dict) else {"successful": True, "data": result}
        except Exception as exc:
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"exec_fail","timestamp":int(_t.time()*1000),"location":"composio_service.py:_execute","message":"Composio action FAILED","data":{"action":action,"error":str(exc),"error_type":type(exc).__name__},"hypothesisId":"B1"})+"\n")
            # #endregion
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
    # LinkedIn
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
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"oauth_initiate","timestamp":int(_t.time()*1000),"location":"composio_service.py:initiate_connection","message":"Initiating OAuth","data":{"toolkit":toolkit,"callback_url":callback_url,"auth_config_id":auth_config_id,"user_id":self.user_id},"hypothesisId":"A1,A2,A3,A4"})+"\n")
            # #endregion
            req = self.composio.connected_accounts.initiate(
                user_id=self.user_id,
                auth_config_id=auth_config_id,
                config={"auth_scheme": "OAUTH2"},
                callback_url=callback_url,
            )
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"oauth_initiate_ok","timestamp":int(_t.time()*1000),"location":"composio_service.py:initiate_connection","message":"OAuth initiate succeeded","data":{"toolkit":toolkit,"redirect_url":getattr(req,"redirect_url","?"),"request_id":getattr(req,"id","?"),"req_attrs":[a for a in dir(req) if not a.startswith("_")]},"hypothesisId":"A1,A4"})+"\n")
            # #endregion
            return {
                "successful": True,
                "redirect_url": req.redirect_url,
                "request_id": req.id,
            }
        except Exception as exc:
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"oauth_initiate_fail","timestamp":int(_t.time()*1000),"location":"composio_service.py:initiate_connection","message":"OAuth initiate FAILED","data":{"toolkit":toolkit,"error":str(exc),"error_type":type(exc).__name__},"hypothesisId":"A3"})+"\n")
            # #endregion
            logger.exception("OAuth initiation failed for %s", toolkit)
            return {"successful": False, "error": str(exc)}

    def check_connections(self) -> dict[str, Any]:
        """Check which toolkits have active connections for the current user."""
        if not self.composio:
            return {"connections": [], "error": "Composio not initialized"}

        try:
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"check_conn","timestamp":int(_t.time()*1000),"location":"composio_service.py:check_connections","message":"Checking connections","data":{"user_id":self.user_id},"hypothesisId":"A2"})+"\n")
            # #endregion
            response = self.composio.connected_accounts.list(
                user_ids=[self.user_id],
                statuses=["ACTIVE"],
            )
            # SDK v1.0.0-rc2 returns a paginated response that iterates as
            # key-value tuples: ('items', [...]), ('next_cursor', ...), etc.
            # Extract the actual Item list from the 'items' field.
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
                connections.append({
                    "id": getattr(acct, "id", ""),
                    "app": toolkit_slug,
                    "status": getattr(acct, "status", "UNKNOWN"),
                })
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"check_conn_result","timestamp":int(_t.time()*1000),"location":"composio_service.py:check_connections","message":"Connections result","data":{"count":len(connections),"connections":connections},"hypothesisId":"A2"})+"\n")
            # #endregion
            return {"successful": True, "connections": connections}
        except Exception as exc:
            # #region agent log
            import json as _j, time as _t; open("/Users/tarive/treehacks/rewind/.cursor/debug.log","a").write(_j.dumps({"id":"check_conn_fail","timestamp":int(_t.time()*1000),"location":"composio_service.py:check_connections","message":"Connection check FAILED","data":{"error":str(exc),"error_type":type(exc).__name__},"hypothesisId":"A2"})+"\n")
            # #endregion
            logger.exception("Connection status check failed")
            return {"successful": False, "connections": [], "error": str(exc)}


# ── Singleton for shared use across server + agents ───────────────────────

_instance: ComposioService | None = None


def get_composio_service() -> ComposioService:
    """Return a shared ComposioService singleton."""
    global _instance
    if _instance is None:
        _instance = ComposioService()
    return _instance
