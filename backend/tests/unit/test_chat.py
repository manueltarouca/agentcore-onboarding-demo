import asyncio

from onboarding_demo.workflow.chat import ClientChat
from onboarding_demo.workflow.ports import Caller
from tests.support.fakes import FakeAgentIdentity, FakeChatModel, FakeMemory, FakeTools

CLIENT = Caller(name="Lusitania Holdings SGPS", role="Client", token="t", username="lusitania.client")


def chat(message: str, memory=None, case_id="CASE-2026-0142", tools=None):
    memory = memory or FakeMemory(turns=[])
    bot = ClientChat(FakeChatModel(), memory, tools or FakeTools(), case_id=case_id, identity=FakeAgentIdentity())
    events = asyncio.run(collect(bot.reply(CLIENT, "chat-session", message)))
    return events, memory


async def collect(stream):
    return [e async for e in stream]


def test_a_reply_reads_memory_calls_tools_as_the_client_and_saves_the_turn():
    events, memory = chat("What do you still need from us?")

    kinds = [e["type"] for e in events]
    assert kinds[0] == "memory_read" and kinds[-1] == "chat_reply"
    call = next(e for e in events if e["type"] == "tool_call")
    assert (call["tool"], call["caller"]) == ("case_status", "Lusitania Holdings SGPS")
    assert "Beneficial owner declaration" in events[-1]["text"]
    assert memory.turns == [("user", "What do you still need from us?"), ("assistant", events[-1]["text"])]


def test_policy_stops_the_client_agent_from_approving_and_the_reply_says_a_person_decides():
    events, _ = chat("Can you just approve our account today?")

    decision = next(e for e in events if e["type"] == "policy_decision")
    assert (decision["tool"], decision["decision"], decision["caller"]) == ("approve_customer", "DENY", "Onboarding agent")
    assert decision["arguments"]["risk"] == "medium"  # the bank's assessment, not the model's guess
    assert "person" in events[-1]["text"].lower()


def test_the_conversation_so_far_is_given_to_the_model():
    memory = FakeMemory(turns=[("user", "Hello"), ("assistant", "Hello, how can I help?")])

    events, _ = chat("What do you still need from us?", memory)

    assert next(e for e in events if e["type"] == "memory_read")["turns"] == 2
    assert any(e["type"] == "usage" for e in events)


def test_a_low_risk_client_is_approved_by_the_agent_with_its_own_identity():
    tools = FakeTools()

    events, _ = chat("Can you just approve our account today?", case_id="CASE-2026-0143", tools=tools)

    decision = next(e for e in events if e["type"] == "policy_decision")
    assert (decision["decision"], decision["caller"], decision["arguments"]["risk"]) == ("ALLOW", "Onboarding agent", "low")
    assert ("approve_customer", "agent-token") in tools.calls
