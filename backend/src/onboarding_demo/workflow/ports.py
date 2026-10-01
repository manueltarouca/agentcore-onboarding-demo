"""One small interface per AgentCore primitive.

The workflow only talks to these interfaces. `adapters/aws` implements them with real
AgentCore calls, `adapters/fake` with in-memory fakes for tests and offline replay.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Caller:
    """The signed-in person the agent acts for. `token` is their Cognito access token."""

    name: str
    role: str
    token: str
    username: str = ""  # Cognito username, also used as the Memory actor id


@dataclass(frozen=True)
class ModelReply:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model_id: str


@dataclass(frozen=True)
class ToolResult:
    tool: str
    arguments: dict
    output: dict


class PolicyDenied(Exception):
    def __init__(self, tool: str, reason: str):
        super().__init__(f"{tool} denied: {reason}")
        self.tool = tool
        self.reason = reason


@dataclass(frozen=True)
class PageRead:
    url: str
    title: str
    text: str
    screenshot_png_base64: str = ""


@dataclass(frozen=True)
class SandboxRun:
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class MemoryRecord:
    strategy: str
    text: str


@dataclass(frozen=True)
class Score:
    evaluator: str
    value: float
    explanation: str


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    status: str
    record_id: str


class Model(Protocol):
    async def ask(self, system: str, prompt: str) -> ModelReply: ...


class ChatModel(Protocol):
    """A model that holds a conversation and may call the given tools (async functions)."""

    async def converse(self, system: str, history: list[tuple[str, str]], message: str,
                       tools: list) -> ModelReply: ...


class Memory(Protocol):
    async def conversation(self, session_id: str) -> list[tuple[str, str]]: ...
    async def save_turn(self, session_id: str, role: str, text: str) -> None: ...
    async def long_term_records(self, actor_id: str) -> list[MemoryRecord]: ...


class Tools(Protocol):
    """Tools behind AgentCore Gateway, called with the caller's token.

    Raises PolicyDenied when AgentCore Policy blocks the call."""

    async def call(self, name: str, arguments: dict, caller: Caller) -> ToolResult: ...


class Browser(Protocol):
    async def read(self, url: str) -> PageRead: ...


class Sandbox(Protocol):
    async def run_python(self, code: str, files: dict[str, str]) -> SandboxRun: ...


class Evaluator(Protocol):
    async def evaluate(self, session_id: str) -> list[Score]: ...


class RegistryUnavailable(Exception):
    """The account does not allow AWS Agent Registry (for example a restricted sandbox account)."""


class AgentIdentity(Protocol):
    """The agent's own identity (AgentCore Identity), used when the agent acts for itself."""

    async def caller(self) -> Caller: ...


class Registry(Protocol):
    async def publish(self, tool_name: str, description: str) -> RegistryEntry: ...


@dataclass
class Dependencies:
    model: Model
    memory: Memory
    tools: Tools
    browser: Browser
    sandbox: Sandbox
    evaluator: Evaluator
    registry: Registry
    identity: AgentIdentity
    simulated: set[str] = field(default_factory=set)  # primitives that are not real AWS calls
