"""The agent as it runs on AgentCore Runtime.

Two actions, both in the same Runtime session:

    {"action": "start"}    as the relationship manager: steps 1 to 6, then waits
    {"action": "approve"}  as the compliance officer: steps 7 to 10

Between the two calls the workflow object stays in this process. AgentCore Runtime keeps
each session in its own microVM, so the second call lands where the first one left off.
"""
import dataclasses
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from onboarding_demo.adapters.aws import aws_dependencies
from onboarding_demo.agent.identity import caller_from_headers
from onboarding_demo.case import LUSITANIA
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
            case = dataclasses.replace(LUSITANIA, registry_page_url=os.environ["REGISTRY_PAGE_URL"])
            workflow = Workflow(case, aws_dependencies(actor_id=caller.username), session_id=context.session_id)
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
        else:
            yield event("error", message=f"Unknown action {action!r}")
    except Exception as error:  # report it to the UI instead of a silent broken stream
        yield event("error", message=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    app.run()
