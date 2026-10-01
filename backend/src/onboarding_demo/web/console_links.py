"""Links from each primitive to the place it lives in the AWS console.

AgentCore links open the console section (as in its left-hand navigation); the demo's
resources are listed there. Cognito and Lambda link straight to the resource.
"""


def console_links(outputs: dict) -> dict[str, str]:
    region = outputs.get("Region", "us-west-2")
    console = f"https://{region}.console.aws.amazon.com"

    def agentcore(section: str) -> str:
        return f"{console}/bedrock-agentcore/{section}?region={region}"

    return {
        "Runtime": agentcore("agents"),
        "Memory": agentcore("memory"),
        "Gateway": agentcore("toolsAndGateways"),
        "Policy": agentcore("policy"),
        "Code Interpreter": agentcore("code"),
        "Browser": agentcore("browser"),
        "Evaluations": agentcore("evaluations"),
        "Agent Registry": agentcore("registry"),
        "Identity": f"{console}/cognito/v2/idp/user-pools/{outputs.get('UserPoolId', '')}/users?region={region}",
        "Observability": f"{console}/cloudwatch/home?region={region}#gen-ai-observability/agent-core",
        "Bank systems": f"{console}/lambda/home?region={region}#/functions/{outputs.get('ToolsFunctionName', '')}",
        "Registry page": outputs.get("RegistryPageUrl", ""),
    }
