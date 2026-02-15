"""GhostWorker Agent — Autonomous Task Execution via Composio MCP.

Receives DelegationTask messages from the Scheduler Kernel, uses Composio
MCP to draft actions (emails, Slack messages, LinkedIn posts, meeting
scheduling), stores drafts for user approval, and executes approved
actions. Fully autonomous uAgent deployable to Agentverse.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
from uagents import Agent, Context

from src.config.settings import (
    GHOST_WORKER_SEED,
    SCHEDULER_KERNEL_ADDRESS,
    COMPOSIO_API_KEY,
    COMPOSIO_USER_ID,
    REDIS_URL,
)
from src.models.messages import DelegationTask, TaskCompletion
from src.agents.protocols import create_chat_protocol

logger = logging.getLogger(__name__)


# ── Prompt Templates ─────────────────────────────────────────────────────
# Each template is parametric — populated entirely from DelegationTask.context.
# No hardcoded content; the agent adapts to whatever context the Kernel provides.

TASK_PROMPTS: Dict[str, str] = {
    "email_reply": (
        "Reply to the email thread.\n"
        "Recipient: {recipient}\n"
        "Subject: {subject}\n"
        "Original message context: {description}\n"
        "Tone: {tone}\n"
        "Write only the email body, nothing else. "
        "Match a professional, concise tone unless otherwise specified."
    ),
    "slack_message": (
        "Draft a Slack message for the channel #{channel}.\n"
        "Context: {description}\n"
        "Tone: {tone}\n"
        "Keep it conversational and brief. Write only the message text."
    ),
    "linkedin_post": (
        "Create a LinkedIn post about the following:\n"
        "{description}\n"
        "Tone: {tone}\n"
        "Professional tone, include relevant hashtags. "
        "Write only the post content."
    ),
    "meeting_reschedule": (
        "Reschedule the following meeting:\n"
        "Title: {title}\n"
        "Current details: {description}\n"
        "Constraints: {constraints}\n"
        "Draft a calendar invite message proposing new time slots. "
        "Be polite and professional."
    ),
    "cancel_appointment": (
        "Cancel the following appointment:\n"
        "Title: {title}\n"
        "Reason: {description}\n"
        "Draft a cancellation message. Be polite and offer to reschedule if appropriate."
    ),
    "doc_update": (
        "Update the following document/project status:\n"
        "Title: {title}\n"
        "Updates: {description}\n"
        "Write a concise status update."
    ),
}

TASK_SYSTEM_PROMPTS: Dict[str, str] = {
    "email_reply": (
        "You are an email assistant. Draft professional email replies "
        "matching the user's communication style. Output only the email body."
    ),
    "slack_message": (
        "You are a Slack messaging assistant. Draft brief, conversational "
        "messages appropriate for workplace channels. Output only the message."
    ),
    "linkedin_post": (
        "You are a LinkedIn content assistant. Create engaging professional "
        "posts with relevant hashtags. Output only the post content."
    ),
    "meeting_reschedule": (
        "You are a calendar assistant. Draft polite meeting reschedule "
        "proposals with alternative time slots. Output only the message."
    ),
    "cancel_appointment": (
        "You are a calendar assistant. Draft polite appointment cancellation "
        "messages. Output only the message."
    ),
    "doc_update": (
        "You are a documentation assistant. Write concise project status "
        "updates. Output only the update content."
    ),
}

# Default cost per task type (in FET)
TASK_COSTS: Dict[str, float] = {
    "email_reply": 0.001,
    "slack_message": 0.001,
    "linkedin_post": 0.001,
    "meeting_reschedule": 0.01,
    "cancel_appointment": 0.01,
    "doc_update": 0.001,
}

# How often the agent checks for approvals (seconds)
APPROVAL_POLL_INTERVAL = 5


# ── Agent Setup ──────────────────────────────────────────────────────────

_deploy_mode = os.getenv("AGENT_DEPLOY_MODE", "local")
_endpoint_base = os.getenv("AGENT_ENDPOINT_BASE", "http://localhost")

agent = Agent(
    name="ghost_worker",
    seed=GHOST_WORKER_SEED,
    port=8005,
    endpoint=[f"{_endpoint_base}:8005/submit"] if _deploy_mode == "local" else [],
    mailbox=True if _deploy_mode == "agentverse" else False,
)


# ── State & Dependencies ─────────────────────────────────────────────────

_state: Dict[str, Any] = {
    "redis": None,
    "orchestrator": None,
    "pubsub": None,
}


def _get_redis_client() -> redis.Redis:
    if _state["redis"] is None:
        _state["redis"] = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _state["redis"]


def _get_orchestrator():
    if _state["orchestrator"] is None:
        from src.composio.main import ComposioMCPOrchestrator
        _state["orchestrator"] = ComposioMCPOrchestrator(
            api_key=COMPOSIO_API_KEY,
            user_id=COMPOSIO_USER_ID,
        )
        _state["orchestrator"].initialize_session()
        logger.info("Composio MCP session initialized for GhostWorker")
    return _state["orchestrator"]


def _get_approval_pubsub() -> redis.client.PubSub:
    """Get or create a Redis pubsub subscription for approval messages."""
    if _state["pubsub"] is None:
        r = _get_redis_client()
        _state["pubsub"] = r.pubsub(ignore_subscribe_messages=True)
        _state["pubsub"].subscribe("ghostworker:approvals")
        logger.info("Subscribed to ghostworker:approvals channel")
    return _state["pubsub"]


# ── Draft Helpers ─────────────────────────────────────────────────────────


def _build_prompt(task_type: str, context: dict) -> str:
    """Build a Composio prompt from task type and context dict.

    Uses safe .get() with defaults so missing context keys don't break.
    """
    template = TASK_PROMPTS.get(task_type, TASK_PROMPTS.get("doc_update", ""))
    # Provide sensible defaults for all possible template keys
    params = {
        "recipient": context.get("recipient", "the recipient"),
        "subject": context.get("subject", ""),
        "description": context.get("description", context.get("title", "")),
        "tone": context.get("tone", "professional"),
        "channel": context.get("channel", "general"),
        "title": context.get("title", ""),
        "constraints": context.get("constraints", "find the best available time"),
    }
    return template.format(**params)


def _store_draft(
    draft_id: str,
    task: DelegationTask,
    body: str,
    cost_fet: float,
) -> dict:
    """Store a draft in Redis and publish event for server relay."""
    r = _get_redis_client()

    draft = {
        "id": draft_id,
        "task_id": task.task_id,
        "task_type": task.task_type,
        "body": body,
        "recipient": task.context.get("recipient", ""),
        "channel": task.context.get("channel", ""),
        "subject": task.context.get("subject", ""),
        "cost_fet": cost_fet,
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender_address": "",  # populated by handler with Kernel address
    }

    # Store draft as Redis hash
    r.hset(f"ghostworker:draft:{draft_id}", mapping=draft)
    # Add to pending set
    r.sadd("ghostworker:pending", draft_id)

    # Publish event for server to relay via WebSocket
    event = {
        "event": "draft_created",
        "draft_id": draft_id,
        "draft": draft,
    }
    r.publish("ghostworker:events", json.dumps(event))

    logger.info("Draft %s stored and published (task_type=%s)", draft_id, task.task_type)
    return draft


async def _execute_draft(draft_id: str, body_override: Optional[str] = None) -> dict:
    """Execute an approved draft via Composio MCP.

    Returns the execution result dict.
    """
    r = _get_redis_client()
    draft_data = r.hgetall(f"ghostworker:draft:{draft_id}")

    if not draft_data:
        logger.error("Draft %s not found in Redis", draft_id)
        return {"status": "failed", "error": "Draft not found"}

    task_type = draft_data.get("task_type", "")
    body = body_override or draft_data.get("body", "")

    # Build execution prompt based on task type
    execution_prompts = {
        "email_reply": (
            f"Send an email to {draft_data.get('recipient', '')} "
            f"with subject '{draft_data.get('subject', '')}' "
            f"and the following body:\n\n{body}"
        ),
        "slack_message": (
            f"Send a message to Slack channel #{draft_data.get('channel', 'general')} "
            f"with the following text:\n\n{body}"
        ),
        "linkedin_post": (
            f"Publish the following LinkedIn post:\n\n{body}"
        ),
        "meeting_reschedule": (
            f"Send a calendar invite/reschedule notification:\n\n{body}"
        ),
        "cancel_appointment": (
            f"Send the following cancellation message:\n\n{body}"
        ),
        "doc_update": (
            f"Update the document with:\n\n{body}"
        ),
    }

    prompt = execution_prompts.get(task_type, f"Execute: {body}")

    try:
        orchestrator = _get_orchestrator()
        responses = await orchestrator.execute_operation(
            prompt,
            system_context=f"Execute this {task_type} action. Do not draft — actually perform the action.",
            max_iterations=5,
        )
        result = {
            "status": "executed",
            "response": responses,
            "body": body,
        }
    except Exception as exc:
        logger.error("Composio execution failed for draft %s: %s", draft_id, exc)
        result = {
            "status": "failed",
            "error": str(exc),
        }

    # Update draft status in Redis
    r.hset(f"ghostworker:draft:{draft_id}", "status", result["status"])
    r.srem("ghostworker:pending", draft_id)

    # Publish execution event
    event = {
        "event": f"draft_{result['status']}",
        "draft_id": draft_id,
        "task_id": draft_data.get("task_id", ""),
        "result": result,
    }
    r.publish("ghostworker:events", json.dumps(event))

    return result


# ── Message Handlers ─────────────────────────────────────────────────────


@agent.on_message(DelegationTask)
async def handle_delegation(ctx: Context, sender: str, task: DelegationTask):
    """Handle a delegated task from Scheduler Kernel.

    Generates a draft via Composio MCP, stores it in Redis, and
    publishes an event for the frontend to display.
    """
    logger.info(
        "DelegationTask received: task_id=%s, type=%s, approval=%s",
        task.task_id, task.task_type, task.approval_required,
    )

    # Build prompt from context
    prompt = _build_prompt(task.task_type, task.context)
    system_prompt = TASK_SYSTEM_PROMPTS.get(
        task.task_type,
        "You are a task execution assistant. Complete the requested action."
    )

    # Generate draft via Composio MCP
    try:
        orchestrator = _get_orchestrator()
        responses = await orchestrator.execute_operation(
            prompt,
            system_context=system_prompt,
            max_iterations=5,
        )
        draft_body = "\n".join(responses) if responses else "(No content generated)"
    except Exception as exc:
        logger.error("Composio draft generation failed: %s", exc)
        draft_body = f"(Draft generation failed: {exc})"

    draft_id = f"draft-{uuid.uuid4().hex[:8]}"
    cost = min(TASK_COSTS.get(task.task_type, 0.001), task.max_cost_fet)

    if not task.approval_required:
        # Auto-execute without approval
        logger.info("Auto-executing task %s (approval not required)", task.task_id)
        result = await _execute_draft(draft_id, body_override=draft_body)
        completion = TaskCompletion(
            task_id=task.task_id,
            status=result.get("status", "failed"),
            result=result,
            cost_fet=cost,
        )
        if SCHEDULER_KERNEL_ADDRESS:
            await ctx.send(SCHEDULER_KERNEL_ADDRESS, completion)
        return

    # Store draft for user approval
    draft = _store_draft(draft_id, task, draft_body, cost)
    draft["sender_address"] = sender

    # Update Redis with sender for later TaskCompletion routing
    r = _get_redis_client()
    r.hset(f"ghostworker:draft:{draft_id}", "sender_address", sender)

    logger.info("Draft %s awaiting user approval", draft_id)


# ── Approval Polling ──────────────────────────────────────────────────────


@agent.on_interval(period=APPROVAL_POLL_INTERVAL)
async def poll_approvals(ctx: Context):
    """Check Redis pubsub for approval/rejection messages from the server."""
    pubsub = _get_approval_pubsub()

    # Non-blocking read of all pending messages
    while True:
        msg = pubsub.get_message()
        if msg is None:
            break
        if msg["type"] != "message":
            continue

        try:
            data = json.loads(msg["data"])
        except (json.JSONDecodeError, TypeError):
            continue

        action = data.get("action")
        draft_id = data.get("draft_id")

        if not draft_id:
            continue

        r = _get_redis_client()
        draft_data = r.hgetall(f"ghostworker:draft:{draft_id}")

        if not draft_data:
            logger.warning("Approval for unknown draft %s", draft_id)
            continue

        task_id = draft_data.get("task_id", "")
        task_type = draft_data.get("task_type", "")
        cost_fet = float(draft_data.get("cost_fet", 0.001))
        sender_address = draft_data.get("sender_address", SCHEDULER_KERNEL_ADDRESS)

        if action == "approve":
            logger.info("Draft %s approved — executing via Composio", draft_id)
            edited_body = data.get("edited_body")
            result = await _execute_draft(draft_id, body_override=edited_body)

            completion = TaskCompletion(
                task_id=task_id,
                status=result.get("status", "failed"),
                result=result,
                cost_fet=cost_fet,
            )
            if sender_address:
                await ctx.send(sender_address, completion)

        elif action == "reject":
            logger.info("Draft %s rejected", draft_id)
            r.hset(f"ghostworker:draft:{draft_id}", "status", "rejected")
            r.srem("ghostworker:pending", draft_id)

            # Publish rejection event
            event = {
                "event": "draft_rejected",
                "draft_id": draft_id,
                "task_id": task_id,
            }
            r.publish("ghostworker:events", json.dumps(event))

            completion = TaskCompletion(
                task_id=task_id,
                status="failed",
                result={"reason": "User rejected draft"},
                cost_fet=0.0,
            )
            if sender_address:
                await ctx.send(sender_address, completion)


# ── Startup ──────────────────────────────────────────────────────────────


@agent.on_event("startup")
async def on_startup(ctx: Context):
    """Initialize GhostWorker dependencies on startup."""
    logger.info("GhostWorker started. Address: %s", agent.address)

    # Initialize Composio session eagerly
    try:
        _get_orchestrator()
    except Exception as exc:
        logger.warning("Composio init deferred: %s", exc)

    # Initialize approval pubsub
    _get_approval_pubsub()

    # Check for any orphaned pending drafts
    r = _get_redis_client()
    pending = r.scard("ghostworker:pending")
    if pending:
        logger.info("%d pending drafts awaiting approval", pending)


# ── Chat Protocol ────────────────────────────────────────────────────────


async def _chat_handler(ctx: Context, sender: str, text: str) -> str:
    r = _get_redis_client()
    pending = r.scard("ghostworker:pending")
    return (
        f"I'm GhostWorker — I autonomously handle delegatable tasks like "
        f"email replies, Slack messages, LinkedIn posts, and meeting scheduling. "
        f"Currently {pending} draft(s) pending review."
    )


chat_proto = create_chat_protocol(
    "GhostWorker",
    "Autonomously executes delegatable tasks like email replies, Slack messages, "
    "LinkedIn posts, and meeting scheduling with user approval",
    _chat_handler,
)
agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent.run()
