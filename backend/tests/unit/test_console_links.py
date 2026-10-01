from onboarding_demo.web.console_links import console_links

OUTPUTS = {
    "Region": "us-west-2", "RuntimeId": "onboarding_agent-abc", "MemoryId": "onboarding_memory-xyz",
    "GatewayId": "onboarding-gateway-123", "PolicyEngineId": "onboarding_policies-9",
    "UserPoolId": "us-west-2_AbC", "ToolsFunctionName": "onboarding-bank-tools",
    "RegistryPageUrl": "https://d123.cloudfront.net/",
}


def test_every_step_primitive_has_a_console_link():
    links = console_links(OUTPUTS)

    for primitive in ("Runtime", "Memory", "Gateway", "Policy", "Identity", "Observability", "Evaluations",
                      "Code Interpreter", "Browser", "Agent Registry"):
        assert links[primitive].startswith("https://"), primitive


def test_links_use_the_real_agentcore_console_sections():
    links = console_links(OUTPUTS)

    assert links["Runtime"] == "https://us-west-2.console.aws.amazon.com/bedrock-agentcore/agents?region=us-west-2"
    assert "/bedrock-agentcore/toolsAndGateways" in links["Gateway"]
    assert "/bedrock-agentcore/policy?" in links["Policy"]
    assert "/bedrock-agentcore/code?" in links["Code Interpreter"]
    assert "/bedrock-agentcore/browser?" in links["Browser"]
    assert "us-west-2_AbC" in links["Identity"]
    assert links["Registry page"] == "https://d123.cloudfront.net/"
