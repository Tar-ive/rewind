"""Reusable Chat Protocol factory for ASI:One discoverability.

Every Rewind agent implements Chat Protocol so it can be discovered
and queried through ASI:One Chat on the Fetch.ai ecosystem.
"""

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    EndSessionContent,
)


def create_chat_protocol(
    agent_name: str,
    description: str,
    handler_fn=None,
) -> Protocol:
    """Create a Chat Protocol instance for an agent.

    Args:
        agent_name: Display name for the agent.
        description: What the agent does (used for ASI:One ranking).
        handler_fn: Optional async function(ctx, sender, text) -> str
                    that processes chat messages and returns a response.
                    If None, returns a default description response.

    Returns:
        A Protocol instance ready to be included in an agent.
    """
    chat_proto = Protocol(name="chat", version="0.3.0")

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        # Acknowledge receipt
        await ctx.send(
            sender,
            ChatAcknowledgement(acknowledged_msg_id=msg.msg_id),
        )

        # Extract text from first content block
        text = ""
        for item in msg.content:
            if isinstance(item, TextContent):
                text = item.text
                break

        # Process via handler or return default
        if handler_fn:
            response_text = await handler_fn(ctx, sender, text)
        else:
            response_text = (
                f"I'm {agent_name}. {description} "
                "Send me a structured message via my protocols for full functionality."
            )

        # Send response + end session
        await ctx.send(
            sender,
            ChatMessage(
                msg_id=ctx.session,
                content=[TextContent(text=response_text)],
            ),
        )
        await ctx.send(
            sender,
            ChatMessage(
                msg_id=ctx.session,
                content=[EndSessionContent()],
            ),
        )

    return chat_proto
