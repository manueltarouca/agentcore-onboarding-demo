"""The onboarding workflow: ten steps, each handled by one AgentCore primitive.

It runs in two invocations of the same AgentCore Runtime session:

1. `start(relationship_manager)` runs steps 1 to 6 and stops when a human must decide.
2. `approve(compliance_officer)` resumes the same workflow object, which is still in
   the session's memory, and runs steps 7 to 10.

When Policy allows the agent's own approval (low risk), there is no human step: `start`
skips step 7 and finishes the run in the first invocation.

The steps always run in the same order so the class can follow them. Inside a step the
model does the reasoning and the primitive does the work.
"""
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from onboarding_demo.case import OnboardingCase
from onboarding_demo.domain.documents import missing_documents
from onboarding_demo.domain.ownership import beneficial_owners, effective_ownership, people_only
from onboarding_demo.domain.risk import ScreeningResult, classify
from onboarding_demo.pricing import estimate_cost
from onboarding_demo.workflow.events import event
from onboarding_demo.workflow.ownership_script import reference_script, shareholders_csv
from onboarding_demo.workflow.ports import (
    Caller, Dependencies, ModelReply, PolicyDenied, RegistryUnavailable,
)


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    primitive: str
    description: str


STEPS = (
    Step("intake", "Intake", "Memory", "Reads the conversation so far and asks only for what is missing"),
    Step("lookup", "Company lookup", "Gateway", "Calls the bank's registry system through an MCP tool"),
    Step("registry_page", "Registry page", "Browser", "Reads a website that has no API in a managed browser"),
    Step("ownership", "Ownership", "Code Interpreter", "The model writes Python; a sandbox runs it"),
    Step("screening", "Screening", "Gateway", "Screens each beneficial owner against PEP and sanctions lists"),
    Step("approval", "Approval attempt", "Policy", "The agent tries to approve; Cedar policy decides"),
    Step("human_review", "Human approval", "Identity", "A compliance officer approves with her own token"),
    Step("memory", "Long-term memory", "Memory", "Facts, preferences and lessons kept for next time"),
    Step("evaluation", "Evaluation", "Evaluations", "An LLM judge scores the session from its traces"),
    Step("registry", "Publish tool", "Agent Registry", "Publishes the tool so other teams can reuse it"),
)
FIRST_INVOCATION = STEPS[:6]
SECOND_INVOCATION = STEPS[6:]

SYSTEM_PROMPT = (
    "You are an onboarding assistant at a bank. You help a relationship manager open "
    "accounts for business customers. Be brief and factual."
)

def describe_steps() -> list[dict]:
    return [{"id": s.id, "label": s.label, "primitive": s.primitive, "description": s.description,
             "invocation": 1 if s in FIRST_INVOCATION else 2} for s in STEPS]


# Tools where we show the Policy decision even when it allows the call.
POLICY_GUARDED_TOOLS = {"approve_customer"}


class Workflow:
    def __init__(self, case: OnboardingCase, deps: Dependencies, session_id: str | None = None):
        self.case = case
        self.deps = deps
        self.session_id = session_id or f"session-{uuid.uuid4().hex}"
        self.state: dict = {}
        self._pending: list[dict] = []  # events produced inside a step, sent after it
        self._tokens = 0
        self._cost = 0.0
        self._tool_calls = 0

    # ---- the two invocations ---------------------------------------------------------

    async def start(self, caller: Caller) -> AsyncIterator[dict]:
        self.state["requested_by"] = caller
        yield event(
            "run_started",
            case_id=self.case.case_id,
            company=self.case.company,
            session_id=self.session_id,
            acting_for=caller.name,
            simulated=sorted(self.deps.simulated),
            steps=describe_steps(),
        )
        async for e in self._run_steps(FIRST_INVOCATION, caller):
            yield e
        if self.state.get("approved_by_agent"):  # Policy allowed it: no human needed
            yield event("step_skipped", step="human_review", reason=f"Risk {self.state['risk']}: approved by the agent")
            async for e in self._finish(SECOND_INVOCATION[1:], caller):
                yield e
            return
        yield event("awaiting_approval", step="human_review", case_id=self.case.case_id,
                    reason=f"Risk {self.state['risk']}: a compliance officer must decide")

    async def approve(self, caller: Caller) -> AsyncIterator[dict]:
        async for e in self._finish(SECOND_INVOCATION, caller):
            yield e

    async def _finish(self, steps, caller: Caller) -> AsyncIterator[dict]:
        async for e in self._run_steps(steps, caller):
            yield e
        yield event(
            "run_completed",
            totals={"tokens": self._tokens, "cost_usd": round(self._cost, 6), "tool_calls": self._tool_calls},
        )

    async def _run_steps(self, steps, caller: Caller) -> AsyncIterator[dict]:
        for step in steps:
            yield event("step_started", step=step.id)
            detail = await getattr(self, f"_{step.id}")(step, caller)
            for e in self._flush():
                yield e
            yield event("step_completed", step=step.id, detail=detail)

    # ---- helpers -----------------------------------------------------------------------

    def _flush(self) -> list[dict]:
        pending, self._pending = self._pending, []
        return pending

    async def _ask(self, step: Step, prompt: str) -> ModelReply:
        reply = await self.deps.model.ask(SYSTEM_PROMPT, prompt)
        cost = estimate_cost(reply.model_id, reply.input_tokens, reply.output_tokens)
        self._tokens += reply.input_tokens + reply.output_tokens
        self._cost += cost
        self._pending.append(event(
            "usage", step=step.id, model_id=reply.model_id, input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens, latency_ms=reply.latency_ms, cost_usd=cost,
        ))
        return reply

    async def _tool(self, step: Step, name: str, arguments: dict, caller: Caller) -> dict:
        """Call a Gateway tool as `caller`. Policy decisions are reported as events."""
        self._tool_calls += 1
        try:
            result = await self.deps.tools.call(name, arguments, caller)
        except PolicyDenied as denied:
            self._pending.append(event("policy_decision", step=step.id, tool=name, arguments=arguments,
                                       decision="DENY", reason=denied.reason, caller=caller.name))
            raise
        if name in POLICY_GUARDED_TOOLS:
            self._pending.append(event("policy_decision", step=step.id, tool=name, arguments=arguments,
                                       decision="ALLOW", reason="", caller=caller.name))
        self._pending.append(event("tool_call", step=step.id, tool=name, arguments=arguments,
                                   output=result.output, caller=caller.name))
        return result.output

    # ---- steps -------------------------------------------------------------------------

    async def _intake(self, step: Step, caller: Caller) -> dict:
        turns = await self.deps.memory.conversation(self.session_id)
        missing = missing_documents(list(self.case.documents_received))
        still = (f"Still missing: {', '.join(missing)}. Write a message to the relationship manager asking "
                 "only for the missing documents." if missing else
                 "Nothing is missing. Write a message to the relationship manager confirming the file is complete.")
        reply = await self._ask(
            step,
            f"The customer already sent: {', '.join(self.case.documents_received)}. {still} "
            "Plain text, at most two sentences, no greeting, no markdown.",
        )
        await self.deps.memory.save_turn(self.session_id, "assistant", reply.text)
        return {"remembered_turns": [t for _, t in turns], "missing": missing, "message": reply.text}

    async def _lookup(self, step: Step, caller: Caller) -> dict:
        company = await self._tool(step, "registry_lookup", {"company_number": self.case.company_number}, caller)
        return {"company": company}

    async def _registry_page(self, step: Step, caller: Caller) -> dict:
        page = await self.deps.browser.read(self.case.registry_page_url)
        return {"url": page.url, "title": page.title, "text": page.text[:600],
                "screenshot": page.screenshot_png_base64}

    async def _ownership(self, step: Step, caller: Caller) -> dict:
        reference = effective_ownership(list(self.case.holdings), self.case.company)
        reply = await self._ask(
            step,
            "Write a Python script that reads shareholders.csv (columns owner, owned, percent), "
            f"computes each person's effective ownership of '{self.case.company}' through every "
            "chain of companies, and prints the result as one JSON object on the last line. "
            "A person is an owner that does not appear in the 'owned' column; list only people. "
            "Round percentages to 2 decimals. Return only the code.",
        )
        code = _strip_code_fences(reply.text)
        files = {"shareholders.csv": shareholders_csv(self.case.holdings)}
        raw, used_fallback = await self._run_ownership(code, files)
        result = people_only(raw, list(self.case.holdings))  # companies in the chain are not owners
        owners = beneficial_owners(result)
        self.state["beneficial_owners"] = owners
        self.state["ownership"] = result
        return {"code": code, "ownership": result, "beneficial_owners": owners,
                "matches_reference": result == reference, "used_fallback": used_fallback}

    async def _run_ownership(self, code: str, files: dict) -> tuple[dict, bool]:
        try:
            run = await self.deps.sandbox.run_python(code, files)
            return json.loads(run.stdout.strip().splitlines()[-1]), False
        except (ValueError, IndexError):
            run = await self.deps.sandbox.run_python(reference_script(self.case.company), files)
            return json.loads(run.stdout.strip().splitlines()[-1]), True

    async def _screening(self, step: Step, caller: Caller) -> dict:
        results = []
        for person in self.state["beneficial_owners"]:
            out = await self._tool(step, "screen_person", {"name": person}, caller)
            results.append(ScreeningResult(person, pep=out["pep"], sanctioned=out["sanctioned"]))
        risk = classify(results)
        self.state["risk"] = str(risk)
        self.state["screening"] = results
        return {"results": [r.__dict__ for r in results], "risk": str(risk)}

    async def _approval(self, step: Step, caller: Caller) -> dict:
        reply = await self._ask(step, (
            f"Case {self.case.case_id}, {self.case.company}. Beneficial owners and screening: "
            f"{self._findings()}. Risk: {self.state['risk']}. Write one sentence for the compliance "
            "reviewer explaining the risk. Plain text."))
        arguments = {"case_id": self.case.case_id, "risk": self.state["risk"]}
        agent = await self.deps.identity.caller()  # its own identity, not the relationship manager's
        try:  # the agent's default is to approve; Policy decides whether it may
            await self._tool(step, "approve_customer", arguments, agent)
            self.state["approved_by_agent"] = True
            return {"decision": "ALLOW", "summary": reply.text}
        except PolicyDenied as denied:
            routed = await self._tool(step, "create_compliance_case",
                                      {"case_id": self.case.case_id, "reason": f"Risk {self.state['risk']}"}, caller)
            return {"decision": "DENY", "reason": denied.reason, "routed_to": routed, "summary": reply.text}

    def _findings(self) -> str:
        return "; ".join(
            f"{r.person} {self.state['ownership'][r.person]}%, "
            f"{'politically exposed person' if r.pep else 'clear'}{', sanctioned' if r.sanctioned else ''}"
            for r in self.state["screening"])

    async def _human_review(self, step: Step, caller: Caller) -> dict:
        arguments = {"case_id": self.case.case_id, "risk": self.state["risk"]}
        result = await self._tool(step, "approve_customer", arguments, caller)
        return {"approved_by": caller.name, "role": caller.role, "result": result}

    async def _memory(self, step: Step, caller: Caller) -> dict:
        requester = self.state["requested_by"]
        records = await self.deps.memory.long_term_records(requester.username or requester.name)
        for record in records:
            self._pending.append(event("memory_record", step=step.id, strategy=record.strategy, text=record.text))
        return {"records": [r.__dict__ for r in records]}

    async def _evaluation(self, step: Step, caller: Caller) -> dict:
        scores = await self.deps.evaluator.evaluate(self.session_id)
        return {"scores": [s.__dict__ for s in scores]}

    async def _registry(self, step: Step, caller: Caller) -> dict:
        try:
            entry = await self.deps.registry.publish(
                "registry_lookup", "Look up a company in the commercial registry by company number")
            return {"available": True, "entry": entry.__dict__}
        except RegistryUnavailable as unavailable:
            return {"available": False, "reason": str(unavailable)}


def _strip_code_fences(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines)
