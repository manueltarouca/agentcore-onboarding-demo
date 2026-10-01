"""The client's chat with the bank's agent, one message at a time.

Each reply reads the conversation from Memory, lets the model call Gateway tools with the
client's own token, and saves the new turn. Policy decides what the client's agent may do:
it can read the case status and book a call, but it can never approve the account.
"""
from collections.abc import AsyncIterator

from onboarding_demo.pricing import estimate_cost
from onboarding_demo.workflow.events import event
from onboarding_demo.workflow.ports import Caller, ChatModel, Memory, PolicyDenied, Tools

STEP = "chat"
SYSTEM = (
    "You are the business banking assistant of a bank, talking to a client company about its account "
    "application. Use the tools to answer. Be brief and friendly: plain text, at most three sentences. "
    "Never mention screening, risk ratings, politically exposed persons or internal reviews. "
    "If a tool is not allowed, say that a person at the bank makes that decision."
)
DENIED = {"error": "Not allowed. A person at the bank makes this decision."}


class ClientChat:
    def __init__(self, model: ChatModel, memory: Memory, tools: Tools, case_id: str):
        self.model = model
        self.memory = memory
        self.tools = tools
        self.case_id = case_id

    async def reply(self, caller: Caller, session_id: str, message: str) -> AsyncIterator[dict]:
        pending: list[dict] = []
        history = await self.memory.conversation(session_id)
        yield event("memory_read", step=STEP, turns=len(history))

        reply = await self.model.converse(SYSTEM, history, message, self._tools(caller, pending))
        for e in pending:
            yield e
        yield event("usage", step=STEP, model_id=reply.model_id, input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens, latency_ms=reply.latency_ms,
                    cost_usd=estimate_cost(reply.model_id, reply.input_tokens, reply.output_tokens))

        await self.memory.save_turn(session_id, "user", message)
        await self.memory.save_turn(session_id, "assistant", reply.text)
        yield event("memory_saved", step=STEP, turns=2)
        yield event("chat_reply", step=STEP, text=reply.text)

    def _tools(self, caller: Caller, pending: list[dict]) -> list:
        case_id = self.case_id

        async def call(name: str, arguments: dict) -> dict:
            try:
                result = await self.tools.call(name, arguments, caller)
            except PolicyDenied as denied:
                pending.append(event("policy_decision", step=STEP, tool=name, arguments=arguments,
                                     decision="DENY", reason=denied.reason, caller=caller.name))
                return DENIED
            pending.append(event("policy_decision", step=STEP, tool=name, arguments=arguments,
                                 decision="ALLOW", reason="", caller=caller.name))
            pending.append(event("tool_call", step=STEP, tool=name, arguments=arguments,
                                 output=result.output, caller=caller.name))
            return result.output

        async def case_status() -> dict:
            """Status of the client's account application and the documents the bank still needs."""
            return await call("case_status", {"case_id": case_id})

        async def book_callback(topic: str) -> dict:
            """Book a call with the client's relationship manager about a topic."""
            return await call("book_callback", {"case_id": case_id, "topic": topic})

        async def approve_customer(risk: str) -> dict:
            """Approve the client's account. Risk is the case's risk level: low, medium or high."""
            return await call("approve_customer", {"case_id": case_id, "risk": risk})

        return [case_status, book_callback, approve_customer]
