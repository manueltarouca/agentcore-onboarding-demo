"""The client's chat with the bank's agent, one message at a time.

Each reply reads the conversation from Memory, lets the model call Gateway tools, and saves the
new turn. Reading the case and booking a call use the client's own token. Approval uses the
agent's own identity and the bank's risk assessment, so Policy approves a low-risk client and
refuses the rest, whatever the client or the model says.
"""
from collections.abc import AsyncIterator

from onboarding_demo.bank_tools import assessed_risk
from onboarding_demo.pricing import estimate_cost
from onboarding_demo.workflow.events import event
from onboarding_demo.workflow.ports import AgentIdentity, Caller, ChatModel, Memory, PolicyDenied, Tools

STEP = "chat"
SYSTEM = (
    "You are the business banking assistant of a bank, talking to a client company about its account "
    "application. Use the tools to answer. Be brief and friendly: plain text, at most three sentences, "
    "no markdown, no lists, no dashes. "
    "Never mention screening, risk ratings, politically exposed persons or internal reviews. "
    "If the client asks you to approve the account, call approve_customer: the bank's policy decides. "
    "If it is approved, say the account is approved. "
    "If it is not allowed, say that a person at the bank makes that decision."
)
DENIED = {"error": "Not allowed. A person at the bank makes this decision."}


class ClientChat:
    def __init__(self, model: ChatModel, memory: Memory, tools: Tools, case_id: str, identity: AgentIdentity):
        self.model = model
        self.memory = memory
        self.tools = tools
        self.case_id = case_id
        self.identity = identity

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

        async def call(name: str, arguments: dict, as_caller: Caller = caller) -> dict:
            try:
                result = await self.tools.call(name, arguments, as_caller)
            except PolicyDenied as denied:
                pending.append(event("policy_decision", step=STEP, tool=name, arguments=arguments,
                                     decision="DENY", reason=denied.reason, caller=as_caller.name))
                return DENIED
            pending.append(event("policy_decision", step=STEP, tool=name, arguments=arguments,
                                 decision="ALLOW", reason="", caller=as_caller.name))
            pending.append(event("tool_call", step=STEP, tool=name, arguments=arguments,
                                 output=result.output, caller=as_caller.name))
            return result.output

        async def case_status() -> dict:
            """Status of the client's account application and the documents the bank still needs."""
            return await call("case_status", {"case_id": case_id})

        async def book_callback(topic: str) -> dict:
            """Book a call with the client's relationship manager about a topic."""
            return await call("book_callback", {"case_id": case_id, "topic": topic})

        async def approve_customer() -> dict:
            """Ask the bank to approve the client's account. The bank's policy decides."""
            agent = await self.identity.caller()  # the agent's own identity, not the client's
            return await call("approve_customer", {"case_id": case_id, "risk": assessed_risk(case_id)}, agent)

        return [case_status, book_callback, approve_customer]
