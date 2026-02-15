"""Chat Protocol setup for ASI:One discoverability.

Every Rewind agent includes Chat Protocol so users can discover
and interact with them via ASI:One Chat.

Reference: https://github.com/fetchai/uAgents/blob/main/python/uagents-core/uagents_core/contrib/protocols/chat/__init__.py
"""

from datetime import datetime, timezone

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)


def create_chat_protocol(agent_name: str, handler_fn) -> Protocol:
    """Create a Chat Protocol instance for a Rewind agent.

    Args:
        agent_name: Name of the agent (for logging).
        handler_fn: Async function(ctx, sender, user_text) -> str
                    that processes user text and returns a response string.

    Returns:
        Protocol instance with ChatMessage and ChatAcknowledgement handlers.
    """
    chat_proto = Protocol(spec=chat_protocol_spec)

    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(f"[{agent_name}] Ack from {sender} for {msg.acknowledged_msg_id}")

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        # Send acknowledgement immediately
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )

        # Handle start session
        if any(isinstance(item, StartSessionContent) for item in msg.content):
            ctx.logger.info(f"[{agent_name}] Session started with {sender}")

        # Extract user text
        user_text = msg.text()
        if not user_text:
            return

        # Process via agent-specific handler
        response_text = await handler_fn(ctx, sender, user_text)

        # Send response
        response = ChatMessage(content=[TextContent(text=response_text)])
        await ctx.send(sender, response)

    return chat_proto