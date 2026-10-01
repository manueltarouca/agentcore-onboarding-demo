"""AWS Lambda handler behind the AgentCore Gateway target "bank".

The Gateway turns each MCP tool call into a Lambda invocation: the tool arguments are the
event, and the tool name arrives in the client context as "<target>___<tool>".
"""
from onboarding_demo.bank_tools import TOOLS


def handler(event: dict, context) -> dict:
    full_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool = full_name.split("___", 1)[-1]
    if tool not in TOOLS:
        return {"error": f"Unknown tool {tool}"}
    return TOOLS[tool](**event)
