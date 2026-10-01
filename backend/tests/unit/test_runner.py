import asyncio

from onboarding_demo.case import LUSITANIA
from onboarding_demo.workflow.ports import Caller
from onboarding_demo.workflow.runner import STEPS, Workflow
from tests.support.fakes import fake_dependencies

RITA = Caller(name="Rita Almeida", role="Relationship manager", token="rita-token")
OFFICER = Caller(name="Compliance officer", role="Compliance", token="officer-token")


async def collect(stream) -> list[dict]:
    return [event async for event in stream]


def run_until_approval(workflow: Workflow) -> list[dict]:
    return asyncio.run(collect(workflow.start(RITA)))


def run_full(workflow: Workflow) -> list[dict]:
    async def both():
        first = await collect(workflow.start(RITA))
        second = await collect(workflow.approve(OFFICER))
        return first + second

    return asyncio.run(both())


def of_type(events, kind):
    return [e for e in events if e["type"] == kind]


def test_runs_every_step_in_order_and_finishes():
    events = run_full(Workflow(LUSITANIA, fake_dependencies()))

    assert events[0]["type"] == "run_started"
    assert [s["id"] for s in events[0]["steps"]] == [s.id for s in STEPS]
    assert [e["step"] for e in of_type(events, "step_completed")] == [s.id for s in STEPS]
    assert events[-1]["type"] == "run_completed"


def test_the_first_invocation_stops_and_waits_for_a_human():
    events = run_until_approval(Workflow(LUSITANIA, fake_dependencies()))

    assert events[-1]["type"] == "awaiting_approval"
    assert not of_type(events, "run_completed")


def test_policy_denies_the_agent_approving_a_medium_risk_customer():
    events = run_until_approval(Workflow(LUSITANIA, fake_dependencies()))

    decision = of_type(events, "policy_decision")[0]
    assert (decision["tool"], decision["decision"], decision["caller"]) == ("approve_customer", "DENY", "Rita Almeida")


def test_policy_allows_the_compliance_officer_to_approve():
    events = run_full(Workflow(LUSITANIA, fake_dependencies()))

    decision = of_type(events, "policy_decision")[-1]
    assert (decision["decision"], decision["caller"]) == ("ALLOW", "Compliance officer")
    review = next(e for e in of_type(events, "step_completed") if e["step"] == "human_review")
    assert review["detail"]["approved_by"] == "Compliance officer"


def test_tool_calls_carry_the_identity_of_the_caller():
    events = run_full(Workflow(LUSITANIA, fake_dependencies()))

    callers = {(e["tool"], e["caller"]) for e in of_type(events, "tool_call")}
    assert ("registry_lookup", "Rita Almeida") in callers
    assert ("approve_customer", "Compliance officer") in callers


def test_ownership_step_finds_the_beneficial_owners_and_checks_the_sandbox():
    events = run_full(Workflow(LUSITANIA, fake_dependencies()))

    ownership = next(e for e in of_type(events, "step_completed") if e["step"] == "ownership")
    assert ownership["detail"]["beneficial_owners"] == ["Ana Costa", "Miguel Santos"]
    assert ownership["detail"]["matches_reference"] is True


def test_token_usage_adds_up_to_the_run_total():
    events = run_full(Workflow(LUSITANIA, fake_dependencies()))

    used = sum(e["input_tokens"] + e["output_tokens"] for e in of_type(events, "usage"))
    assert used > 0
    assert events[-1]["totals"]["tokens"] == used


def test_registry_step_reports_when_the_account_does_not_allow_it():
    deps = fake_dependencies()
    deps.registry.denied = True
    events = run_full(Workflow(LUSITANIA, deps))

    registry = next(e for e in of_type(events, "step_completed") if e["step"] == "registry")
    assert registry["detail"]["available"] is False
    assert "AccessDenied" in registry["detail"]["reason"]
    assert events[-1]["type"] == "run_completed"


def test_companies_in_the_models_result_are_never_screened_as_people():
    deps = fake_dependencies()
    deps.model.script_override = (
        'import json; print(json.dumps({"Ana Costa": 40, "Tejo Capital": 45, "Miguel Santos": 31.5,'
        ' "Joao Pereira": 13.5, "Other shareholders": 15}))'
    )
    events = run_full(Workflow(LUSITANIA, deps))

    screened = [e["arguments"]["name"] for e in of_type(events, "tool_call") if e["tool"] == "screen_person"]
    assert screened == ["Ana Costa", "Miguel Santos"]


def test_the_agent_writes_a_risk_summary_for_the_reviewer_with_the_findings():
    deps = fake_dependencies()
    events = run_until_approval(Workflow(LUSITANIA, deps))

    approval = next(e for e in of_type(events, "step_completed") if e["step"] == "approval")
    assert approval["detail"]["summary"]
    prompt = deps.model.prompts[-1]
    assert "Miguel Santos" in prompt and "politically exposed" in prompt and "medium" in prompt
