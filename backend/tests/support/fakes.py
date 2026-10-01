"""In-memory test doubles for the AgentCore primitives. Used only by unit tests."""
import asyncio

from onboarding_demo import bank_tools
from onboarding_demo.case import LUSITANIA
from onboarding_demo.workflow.ownership_script import reference_script
from onboarding_demo.workflow.ports import (
    Caller, Dependencies, MemoryRecord, ModelReply, PageRead, PolicyDenied, RegistryEntry, RegistryUnavailable,
    SandboxRun, Score, ToolResult,
)


class FakeModel:
    script_override: str | None = None

    def __init__(self):
        self.prompts: list[str] = []

    async def ask(self, system: str, prompt: str) -> ModelReply:
        self.prompts.append(prompt)
        if "Python script" in prompt:
            text = self.script_override or reference_script(LUSITANIA.company)
        elif "compliance reviewer" in prompt:
            text = "Medium risk: beneficial owner Miguel Santos is a politically exposed person."
        else:
            text = "Please send the beneficial owner declaration and the manager ID documents."
        return ModelReply(text=text, input_tokens=len(prompt) // 4 + 60, output_tokens=len(text) // 4,
                          latency_ms=900, model_id="fake-sonnet")


class FakeMemory:
    def __init__(self, turns=LUSITANIA.conversation):
        self.turns = list(turns)

    async def conversation(self, session_id: str) -> list[tuple[str, str]]:
        return list(self.turns)

    async def save_turn(self, session_id: str, role: str, text: str) -> None:
        self.turns.append((role, text))

    async def long_term_records(self, actor_id: str) -> list[MemoryRecord]:
        return [
            MemoryRecord("User preference", "Prefers short answers with the missing items listed first."),
            MemoryRecord("Semantic", "Lusitania Holdings SGPS is a holding company registered in Lisbon."),
            MemoryRecord("Episodic", "For holding companies, asking for the shareholder structure first sped up approval."),
        ]


class FakeTools:
    """Mirrors the Cedar policies on the Gateway (infra/stack.py)."""

    STAFF_TOOLS = {"registry_lookup", "screen_person", "create_compliance_case"}

    async def call(self, name: str, arguments: dict, caller: Caller) -> ToolResult:
        staff = caller.role != "Client"
        if name == "approve_customer":
            allowed = caller.role == "Compliance" or (staff and arguments.get("risk") == "low")
        else:
            allowed = staff or name not in self.STAFF_TOOLS
        if not allowed:
            raise PolicyDenied(name, "Tool call not allowed due to policy enforcement")
        return ToolResult(name, arguments, bank_tools.TOOLS[name](**arguments))


class FakeChatModel:
    """Calls tools the way a model would for two kinds of question, then answers from the results."""

    def __init__(self):
        self.histories: list[list[tuple[str, str]]] = []

    async def converse(self, system: str, history, message: str, tools: list) -> ModelReply:
        self.histories.append(list(history))
        by_name = {t.__name__: t for t in tools}
        if "approve" in message.lower():
            result = await by_name["approve_customer"](risk="medium")
            text = ("I can't approve accounts myself: a person at the bank makes that decision."
                    if "error" in result else "Your account is approved.")
        else:
            status = await by_name["case_status"]()
            text = f"We still need: {', '.join(status['documents_needed'])}."
        return ModelReply(text=text, input_tokens=400, output_tokens=40, latency_ms=800, model_id="fake-sonnet")


class FakeBrowser:
    async def read(self, url: str) -> PageRead:
        return PageRead(url=url or "about:blank", title="Commercial Registry: 500000000",
                        text="Lusitania Holdings SGPS. Legal form: SGPS. Registered office: Lisbon. Status: Active.")


class FakeSandbox:
    """Runs the script locally in a subprocess. Only ever used with our own reference code."""

    async def run_python(self, code: str, files: dict[str, str]) -> SandboxRun:
        import os, subprocess, sys, tempfile

        with tempfile.TemporaryDirectory() as folder:
            for name, content in files.items():
                with open(os.path.join(folder, name), "w") as f:
                    f.write(content)
            done = await asyncio.to_thread(
                subprocess.run, [sys.executable, "-c", code], cwd=folder, capture_output=True, text=True, timeout=30
            )
        return SandboxRun(stdout=done.stdout, stderr=done.stderr)


class FakeEvaluator:
    async def evaluate(self, session_id: str) -> list[Score]:
        return [
            Score("Goal success", 1.0, "Case routed to compliance with beneficial owners identified."),
            Score("Tool selection", 0.9, "Right tools, one redundant lookup."),
            Score("Required documents requested", 1.0, "Asked only for the two missing documents."),
        ]


class FakeRegistry:
    denied = False

    async def publish(self, tool_name: str, description: str) -> RegistryEntry:
        if self.denied:
            raise RegistryUnavailable("AccessDeniedException: not authorized to perform CreateRegistry")
        return RegistryEntry(name=tool_name, status="Approved", record_id="rec-demo-0001")


def fake_dependencies() -> Dependencies:
    return Dependencies(
        model=FakeModel(), memory=FakeMemory(), tools=FakeTools(), browser=FakeBrowser(),
        sandbox=FakeSandbox(), evaluator=FakeEvaluator(), registry=FakeRegistry(),
    )
