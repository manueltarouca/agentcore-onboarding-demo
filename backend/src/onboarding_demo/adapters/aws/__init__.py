"""Real AgentCore implementations of the workflow ports.

Each class wraps one primitive. Configuration comes from environment variables that the
CDK stack sets on the AgentCore Runtime (see infra/).
"""
import asyncio
import base64
import json
import os
import time
from datetime import datetime, timedelta, timezone

import boto3
import httpx
from botocore.exceptions import ClientError
from bedrock_agentcore.evaluation import fetch_spans_from_cloudwatch
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.tools.browser_client import BrowserClient
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from strands import Agent, tool
from strands.models import BedrockModel

from onboarding_demo.adapters.aws.naming import memory_actor_id
from onboarding_demo.workflow.ports import (
    Caller, Dependencies, MemoryRecord, ModelReply, PageRead, PolicyDenied, RegistryEntry,
    RegistryUnavailable, SandboxRun, Score, ToolResult,
)

REGION = os.environ.get("AWS_REGION", "us-west-2")


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable {name}")
    return value


class StrandsModel:
    """The model's reasoning runs as a Strands agent, so its spans are ones Evaluations can score."""

    def __init__(self, model_id: str):
        self.model_id = model_id

    async def ask(self, system: str, prompt: str) -> ModelReply:
        agent = Agent(model=BedrockModel(model_id=self.model_id, region_name=REGION),
                      system_prompt=system, callback_handler=None)
        started = time.monotonic()
        result = await agent.invoke_async(prompt)
        usage = result.metrics.accumulated_usage
        return ModelReply(
            text=str(result).strip(),
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            latency_ms=round((time.monotonic() - started) * 1000),
            model_id=self.model_id,
        )


class StrandsChatModel:
    """A Strands agent for one chat turn: the history from Memory, the tools from our Gateway calls."""

    def __init__(self, model_id: str):
        self.model_id = model_id

    async def converse(self, system: str, history: list[tuple[str, str]], message: str, tools: list) -> ModelReply:
        messages = [{"role": role, "content": [{"text": text}]} for role, text in history]
        agent = Agent(model=BedrockModel(model_id=self.model_id, region_name=REGION), system_prompt=system,
                      messages=messages, tools=[tool(t) for t in tools], callback_handler=None)
        started = time.monotonic()
        result = await agent.invoke_async(message)
        usage = result.metrics.accumulated_usage
        return ModelReply(text=str(result).strip(), input_tokens=usage.get("inputTokens", 0),
                          output_tokens=usage.get("outputTokens", 0),
                          latency_ms=round((time.monotonic() - started) * 1000), model_id=self.model_id)


class AgentCoreMemory:
    """Short-term memory: the conversation events of this session.
    Long-term memory: records the strategies extracted for this person, across sessions."""

    STRATEGY_NAMESPACES = {
        "User preference": "/onboarding/{actor}/preferences/",
        "Semantic": "/onboarding/{actor}/facts/",
        "Episodic": "/onboarding/{actor}/episodes/",
    }

    def __init__(self, memory_id: str, actor_id: str, seed: tuple[tuple[str, str], ...] = ()):
        self.client = MemoryClient(region_name=REGION)
        self.memory_id = memory_id
        self.actor_id = memory_actor_id(actor_id)
        self.seed = seed  # a case starts from what the relationship manager already said

    async def conversation(self, session_id: str) -> list[tuple[str, str]]:
        events = await asyncio.to_thread(self.client.list_events, memory_id=self.memory_id,
                                         actor_id=self.actor_id, session_id=session_id)
        if not events and self.seed:  # first visit: store what the relationship manager already told us
            for role, text in self.seed:
                await self.save_turn(session_id, role, text)
            events = await asyncio.to_thread(self.client.list_events, memory_id=self.memory_id,
                                             actor_id=self.actor_id, session_id=session_id)
        turns = []
        for e in sorted(events, key=lambda e: e["eventTimestamp"]):
            for item in e.get("payload", []):
                text = item.get("conversational", {}).get("content", {}).get("text")
                if text:
                    turns.append((item["conversational"]["role"].lower(), text))
        return turns

    async def save_turn(self, session_id: str, role: str, text: str) -> None:
        await asyncio.to_thread(self.client.create_event, memory_id=self.memory_id, actor_id=self.actor_id,
                                session_id=session_id, messages=[(text, role.upper())])

    async def long_term_records(self, actor_id: str) -> list[MemoryRecord]:
        records = []
        for strategy, template in self.STRATEGY_NAMESPACES.items():
            found = await asyncio.to_thread(
                self.client.retrieve_memories, memory_id=self.memory_id,
                namespace=template.format(actor=memory_actor_id(actor_id)), query="business customer onboarding", top_k=2)
            records += [MemoryRecord(strategy, r["content"]["text"]) for r in found]
        return records


class GatewayTools:
    """Calls tools on AgentCore Gateway over MCP (JSON-RPC over HTTPS) with the caller's token.

    The Gateway validates the token (Identity), checks Policy, then invokes the Lambda target.
    """

    def __init__(self, gateway_url: str, target_name: str):
        self.url = gateway_url
        self.target = target_name

    async def call(self, name: str, arguments: dict, caller: Caller) -> ToolResult:
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": f"{self.target}___{name}", "arguments": arguments}}
        async with httpx.AsyncClient(timeout=60) as http:
            response = await http.post(self.url, json=request,
                                       headers={"Authorization": f"Bearer {caller.token}"})
        body = response.json()
        error = body.get("error") or {}
        result = body.get("result") or {}
        text = " ".join(c.get("text", "") for c in result.get("content", []))
        message = error.get("message", "") or (text if result.get("isError") else "")
        if message:
            if "policy" in message.lower() or "not allowed" in message.lower():
                raise PolicyDenied(name, message)
            raise RuntimeError(f"Gateway error calling {name}: {message}")
        return ToolResult(name, arguments, json.loads(text))


class AgentCoreIdentity:
    """The agent's own identity. AgentCore Identity gets an OAuth token for the agent's Cognito app
    client (client credentials), using the workload token AgentCore Runtime gives each invocation."""

    NAME = "Onboarding agent"

    def __init__(self, provider_name: str, scope: str):
        self.provider_name = provider_name
        self.scope = scope

    async def caller(self) -> Caller:
        from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
        from bedrock_agentcore.services.identity import IdentityClient

        token = await IdentityClient(REGION).get_token(
            provider_name=self.provider_name, scopes=[self.scope], auth_flow="M2M",
            agent_identity_token=BedrockAgentCoreContext.get_workload_access_token())
        return Caller(name=self.NAME, role="Agent", token=token, username="onboarding-agent")


class AgentCoreBrowser:
    """A managed Chromium session in AgentCore Browser, driven over CDP with Playwright."""

    async def read(self, url: str) -> PageRead:
        from playwright.async_api import async_playwright

        client = BrowserClient(region=REGION)
        await asyncio.to_thread(client.start, session_timeout_seconds=300)
        try:
            ws_url, headers = client.generate_ws_headers()
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(ws_url, headers=headers)
                page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages \
                    else await browser.new_page()
                await page.goto(url, wait_until="networkidle")
                title = await page.title()
                text = await page.inner_text("body")
                screenshot = await page.screenshot(type="png")
                await browser.close()
            return PageRead(url=url, title=title, text=text, screenshot_png_base64=base64.b64encode(screenshot).decode())
        finally:
            await asyncio.to_thread(client.stop)


class AgentCoreSandbox:
    """Runs code in an AgentCore Code Interpreter session."""

    async def run_python(self, code: str, files: dict[str, str]) -> SandboxRun:
        return await asyncio.to_thread(self._run, code, files)

    def _run(self, code: str, files: dict[str, str]) -> SandboxRun:
        interpreter = CodeInterpreter(REGION)
        interpreter.start(session_timeout_seconds=300)
        try:
            for path, content in files.items():
                interpreter.upload_file(path, content)
            response = interpreter.execute_code(code)
            stdout, stderr = "", ""
            for item in response.get("stream", []):
                structured = item.get("result", {}).get("structuredContent", {})
                stdout += structured.get("stdout", "")
                stderr += structured.get("stderr", "")
            return SandboxRun(stdout=stdout, stderr=stderr)
        finally:
            interpreter.stop()


EVALUATOR_NAMES = {"Builtin.GoalSuccessRate": "Goal success", "Builtin.Helpfulness": "Helpfulness"}


class AgentCoreEvaluator:
    """Scores this session with AgentCore Evaluations, using the spans in CloudWatch."""

    def __init__(self, log_group: str, evaluator_ids: list[str], wait_seconds: int = 240):
        self.log_group = log_group
        self.evaluator_ids = evaluator_ids
        self.wait_seconds = wait_seconds
        self.client = boto3.client("bedrock-agentcore", region_name=REGION)

    async def evaluate(self, session_id: str) -> list[Score]:
        spans = await self._wait_for_spans(session_id)
        scores = []
        for evaluator_id in self.evaluator_ids:
            response = await asyncio.to_thread(self.client.evaluate, evaluatorId=evaluator_id,
                                               evaluationInput={"sessionSpans": spans})
            results = [r for r in response["evaluationResults"] if "value" in r]
            if results:
                value = sum(r["value"] for r in results) / len(results)
                scores.append(Score(EVALUATOR_NAMES.get(evaluator_id, evaluator_id), round(value, 2),
                                    results[-1].get("explanation", "")[:300]))
        return scores

    async def _wait_for_spans(self, session_id: str) -> list[dict]:
        """Telemetry reaches CloudWatch a minute or two after the calls happened."""
        deadline = time.monotonic() + self.wait_seconds
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        while True:
            spans = await asyncio.to_thread(fetch_spans_from_cloudwatch, session_id=session_id,
                                            event_log_group=self.log_group, start_time=start, region=REGION)
            if spans or time.monotonic() > deadline:
                return spans
            await asyncio.sleep(15)


class AgentCoreRegistry:
    """Publishes a tool to AWS Agent Registry so other teams can find and reuse it."""

    REGISTRY_NAME = "onboarding-tools"

    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    async def publish(self, tool_name: str, description: str) -> RegistryEntry:
        try:
            return await asyncio.to_thread(self._publish, tool_name, description)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            if code in ("AccessDeniedException", "UnauthorizedOperation"):
                raise RegistryUnavailable(f"{code}: {error.response['Error']['Message']}") from error
            raise

    def _publish(self, tool_name: str, description: str) -> RegistryEntry:
        registry_id = self._registry_id()
        record = self.client.create_registry_record(
            registryId=registry_id, name=tool_name, description=description, descriptorType="CUSTOM",
            descriptors={"custom": {"inlineContent": json.dumps(
                {"tool": tool_name, "gateway": self.gateway_url, "description": description})}},
        )
        return RegistryEntry(name=tool_name, status=record.get("status", "DRAFT"),
                             record_id=record.get("recordId", ""))

    def _registry_id(self) -> str:
        for registry in self.client.list_registries().get("registries", []):
            if registry.get("name") == self.REGISTRY_NAME:
                return registry["registryId"]
        return self.client.create_registry(name=self.REGISTRY_NAME, authorizerType="AWS_IAM",
                                           description="Tools for business onboarding agents")["registryId"]


def runtime_log_group(runtime_name: str) -> str:
    """CloudWatch log group where AgentCore Runtime writes this agent's spans."""
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    for runtime in control.list_agent_runtimes()["agentRuntimes"]:
        if runtime["agentRuntimeName"] == runtime_name:
            return f"/aws/bedrock-agentcore/runtimes/{runtime['agentRuntimeId']}-DEFAULT"
    raise RuntimeError(f"Runtime {runtime_name} not found")


def aws_dependencies(actor_id: str, conversation: tuple[tuple[str, str], ...] = ()) -> Dependencies:
    gateway_url = env("GATEWAY_URL").rstrip("/")
    if not gateway_url.endswith("/mcp"):
        gateway_url += "/mcp"
    return Dependencies(
        model=StrandsModel(os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-6")),
        memory=AgentCoreMemory(env("MEMORY_ID"), actor_id, seed=conversation),
        tools=GatewayTools(gateway_url, env("GATEWAY_TARGET")),
        browser=AgentCoreBrowser(),
        sandbox=AgentCoreSandbox(),
        evaluator=AgentCoreEvaluator(runtime_log_group(env("RUNTIME_NAME")), env("EVALUATOR_IDS").split(",")),
        registry=AgentCoreRegistry(gateway_url),
        identity=AgentCoreIdentity(env("AGENT_IDENTITY_PROVIDER"), env("AGENT_SCOPE")),
    )


def client_chat(actor_id: str, case_id: str):
    from onboarding_demo.workflow.chat import ClientChat

    gateway_url = env("GATEWAY_URL").rstrip("/")
    if not gateway_url.endswith("/mcp"):
        gateway_url += "/mcp"
    return ClientChat(
        model=StrandsChatModel(os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-6")),
        memory=AgentCoreMemory(env("MEMORY_ID"), actor_id),
        tools=GatewayTools(gateway_url, env("GATEWAY_TARGET")),
        case_id=case_id,
    )
