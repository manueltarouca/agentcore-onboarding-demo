"""The agent as it runs on AgentCore Runtime.

Two actions, both in the same Runtime session:

    {"action": "start", "case_id": "..."}   as the relationship manager: steps 1 to 6, then waits
                                             (a low-risk case is approved by the agent and finishes here)
    {"action": "approve"}                   as the compliance officer: steps 7 to 10

And one for the client's chat, one message per call:

    {"action": "chat", "message": "..."}    as the client of one case; the conversation lives in Memory

Between the two calls the workflow object stays in this process. AgentCore Runtime keeps
each session in its own microVM, so the second call lands where the first one left off.
"""
import dataclasses
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from onboarding_demo.adapters.aws import aws_dependencies, client_chat
from onboarding_demo.agent.identity import caller_from_headers
from onboarding_demo.case import case_for_client, get_case
from onboarding_demo.workflow.events import event
from onboarding_demo.workflow.runner import Workflow

app = BedrockAgentCoreApp()
workflows: dict[str, Workflow] = {}


@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    try:
        caller = caller_from_headers(context.request_headers or {})
        action = payload.get("action")
        if action == "start":
            case = get_case(payload.get("case_id"))
            case = dataclasses.replace(case, registry_page_url=os.environ["REGISTRY_PAGE_URL"].rstrip("/") + "/" + case.registry_page)
            workflow = Workflow(case, aws_dependencies(caller.username, case.conversation), session_id=context.session_id)
            workflows[context.session_id] = workflow
            async for e in workflow.start(caller):
                yield e
        elif action == "approve":
            workflow = workflows.pop(context.session_id, None)
            if workflow is None:
                yield event("error", message="No paused case in this session")
                return
            async for e in workflow.approve(caller):
                yield e
        elif action == "chat":
            chat = client_chat(actor_id=caller.username, case_id=case_for_client(caller.username).case_id)
            async for e in chat.reply(caller, context.session_id, payload.get("message", "")):
                yield e
        else:
            yield event("error", message=f"Unknown action {action!r}")
    except Exception as error:  # report it to the UI instead of a silent broken stream
        yield event("error", message=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    app.run()
