# From fetchai/uAgents adapter common patterns:
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import chat_protocol_spec, ChatMessage, ChatAcknowledgement

agent = Agent(name="my_agent", port=8001, seed="my_seed", mailbox=True)
chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def handle(ctx: Context, sender: str, msg: ChatMessage):
    # process message
    pass

agent.include(chat_proto, publish_manifest=True)
agent.run()