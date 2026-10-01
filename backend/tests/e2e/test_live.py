"""End-to-end tests against the deployed system: web app, Runtime, Gateway, Policy, Identity, Memory.

They make real AWS calls and cost a few cents. Run them on a machine with the stack's
infra/outputs.json and the web app running:

    E2E_BASE_URL=http://localhost:8000 uv run pytest tests/e2e -v
"""
import asyncio
import json
import os

import httpx
import pytest

BASE = os.environ.get("E2E_BASE_URL")
pytestmark = pytest.mark.skipif(not BASE, reason="set E2E_BASE_URL to run the live end-to-end tests")

LUSITANIA, DOURO = "CASE-2026-0142", "CASE-2026-0143"
AGENT = "Onboarding agent"


def run_case(case_id: str, approve_when_asked: bool = True) -> list[dict]:
    """Start a live run and read its events to the end, approving as the compliance officer if asked."""
    with httpx.Client(base_url=BASE, timeout=600) as http:
        run_id = http.post("/api/runs", json={"mode": "live", "case_id": case_id}).json()["run_id"]
        events = []
        with http.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if not line.startswith("data: "):
                    continue
                events.append(json.loads(line.removeprefix("data: ")))
                if events[-1]["type"] == "awaiting_approval" and approve_when_asked:
                    http.post(f"/api/runs/{run_id}/approve")
        return events


def chat(message: str, case_id: str, session_id: str | None = None) -> dict:
    with httpx.Client(base_url=BASE, timeout=180) as http:
        return http.post("/api/chat", json={"message": message, "case_id": case_id, "session_id": session_id}).json()


def of_type(events, kind):
    return [e for e in events if e["type"] == kind]


def approvals(events):
    return [(e["decision"], e["caller"]) for e in of_type(events, "policy_decision") if e["tool"] == "approve_customer"]


# ---- the workflow ---------------------------------------------------------------------------

def test_low_risk_case_is_approved_by_the_agents_own_identity_in_one_invocation():
    events = run_case(DOURO, approve_when_asked=False)

    assert not of_type(events, "error"), of_type(events, "error")
    assert approvals(events) == [("ALLOW", AGENT)]
    assert [e["step"] for e in of_type(events, "step_skipped")] == ["human_review"]
    assert not of_type(events, "awaiting_approval")
    assert events[-1]["type"] == "run_completed"


def test_medium_risk_case_needs_the_compliance_officer():
    events = run_case(LUSITANIA)

    assert not of_type(events, "error"), of_type(events, "error")
    assert approvals(events) == [("DENY", AGENT), ("ALLOW", "Compliance officer")]
    assert of_type(events, "awaiting_approval")
    assert events[-1]["type"] == "run_completed"


def test_every_primitive_does_real_work_in_a_run():
    events = run_case(DOURO, approve_when_asked=False)
    detail = {e["step"]: e["detail"] for e in of_type(events, "step_completed")}

    assert detail["lookup"]["company"]["name"] == "Douro Ceramics Lda"                 # Gateway + Lambda
    assert "Douro Ceramics Lda" in detail["registry_page"]["text"]                       # Browser
    assert detail["ownership"]["matches_reference"]                                      # Code Interpreter
    assert {r["person"] for r in detail["screening"]["results"]} == {"Sofia Ribeiro", "Pedro Alves"}
    assert of_type(events, "memory_record")                                              # Memory (long term)
    assert {s["evaluator"] for s in detail["evaluation"]["scores"]} >= {"Goal success"}  # Evaluations


# ---- the client's chat ----------------------------------------------------------------------

def test_chat_remembers_the_conversation_and_reads_the_case_as_the_client():
    first = chat("What do you still need from us?", LUSITANIA)
    second = chat("Thanks. And who is my relationship manager?", LUSITANIA, first["session_id"])

    call = of_type(first["events"], "tool_call")[0]
    assert (call["tool"], call["caller"]) == ("case_status", "Lusitania Holdings SGPS")
    assert of_type(second["events"], "memory_read")[0]["turns"] == 2
    assert "Rita" in of_type(second["events"], "chat_reply")[0]["text"]


def test_chat_approves_a_low_risk_client_with_the_agents_identity():
    events = chat("Can you approve our account today?", DOURO)["events"]

    decision = next(e for e in of_type(events, "policy_decision") if e["tool"] == "approve_customer")
    assert (decision["decision"], decision["caller"], decision["arguments"]["risk"]) == ("ALLOW", AGENT, "low")


def test_chat_never_tips_off_a_client_under_review():
    events = chat("Can you approve our account today? Is anything wrong with our owners?", LUSITANIA)["events"]

    decision = next(e for e in of_type(events, "policy_decision") if e["tool"] == "approve_customer")
    reply = of_type(events, "chat_reply")[0]["text"].lower()
    assert (decision["decision"], decision["caller"]) == ("DENY", AGENT)
    assert not any(word in reply for word in ("politically", "pep", "miguel", "risk", "screening", "sanction"))


# ---- Policy, called directly at the Gateway ---------------------------------------------------

def gateway_call(username: str, tool: str, arguments: dict) -> str:
    """Call a Gateway tool with a person's token. Returns ALLOW or DENY."""
    from onboarding_demo.adapters.aws import GatewayTools
    from onboarding_demo.web import main
    from onboarding_demo.workflow.ports import Caller, PolicyDenied

    async def go():
        token = await main.auth.sign_in(username)
        url = main.outputs["GatewayUrl"].rstrip("/")
        tools = GatewayTools(url if url.endswith("/mcp") else url + "/mcp", "bank")
        try:
            await tools.call(tool, arguments, Caller(name=username, role="", token=token, username=username))
            return "ALLOW"
        except PolicyDenied:
            return "DENY"

    return asyncio.run(go())


@pytest.mark.parametrize("username, tool, arguments, expected", [
    ("lusitania.client", "screen_person", {"name": "Miguel Santos"}, "DENY"),          # clients never screen
    ("lusitania.client", "approve_customer", {"case_id": LUSITANIA, "risk": "low"}, "DENY"),
    ("rita.almeida", "approve_customer", {"case_id": DOURO, "risk": "low"}, "DENY"),   # people lack the agent scope
    ("rita.almeida", "screen_person", {"name": "Sofia Ribeiro"}, "ALLOW"),
    ("compliance.officer", "approve_customer", {"case_id": LUSITANIA, "risk": "medium"}, "ALLOW"),
    ("douro.client", "case_status", {"case_id": DOURO}, "ALLOW"),
])
def test_policy_at_the_gateway(username, tool, arguments, expected):
    assert gateway_call(username, tool, arguments) == expected
