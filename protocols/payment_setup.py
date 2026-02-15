"""Payment Protocol setup for GhostWorker monetization.

GhostWorker charges micro-fees for task execution using Fetch.ai's
Payment Protocol.

Reference: https://github.com/fetchai/uAgents/blob/main/python/uagents-core/uagents_core/contrib/protocols/payment/__init__.py
"""

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

# Pricing table
PRICING = {
    "email_reply": 0.001,
    "slack_message": 0.001,
    "doc_update": 0.001,
    "uber_book": 0.01,
    "cancel_appointment": 0.01,
    "meeting_reschedule": 0.01,
}


def create_payment_protocol() -> Protocol:
    """Create Payment Protocol for GhostWorker (seller role).

    Returns:
        Protocol instance handling CommitPayment and RejectPayment.
    """
    payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

    @payment_proto.on_message(CommitPayment)
    async def handle_commit(ctx: Context, sender: str, msg: CommitPayment):
        ctx.logger.info(
            f"Payment committed: {msg.funds.amount} {msg.funds.currency} "
            f"tx={msg.transaction_id}"
        )
        # Verify payment, then confirm completion
        await ctx.send(
            sender,
            CompletePayment(transaction_id=msg.transaction_id),
        )

    @payment_proto.on_message(RejectPayment)
    async def handle_reject(ctx: Context, sender: str, msg: RejectPayment):
        ctx.logger.warning(f"Payment rejected by {sender}: {msg.reason}")

    return payment_proto


def create_payment_request(task_type: str, recipient: str) -> RequestPayment:
    """Create a RequestPayment message for a given task type.

    Args:
        task_type: One of the PRICING keys.
        recipient: The wallet address to receive payment.

    Returns:
        RequestPayment message.
    """
    amount = PRICING.get(task_type, 0.001)
    return RequestPayment(
        accepted_funds=[
            Funds(amount=str(amount), currency="FET", payment_method="fet_direct")
        ],
        recipient=recipient,
        deadline_seconds=300,
        description=f"GhostWorker task: {task_type}",
    )