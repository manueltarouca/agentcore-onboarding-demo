from types import SimpleNamespace

from onboarding_demo.tools_lambda import handler


def gateway_context(tool: str):
    """AgentCore Gateway passes the tool name as <target>___<tool> in the client context."""
    return SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"bank___{tool}"}))


def test_routes_the_call_to_the_named_tool():
    result = handler({"company_number": "500000000"}, gateway_context("registry_lookup"))

    assert result["name"] == "Lusitania Holdings SGPS"


def test_screening_flags_a_politically_exposed_person():
    result = handler({"name": "Miguel Santos"}, gateway_context("screen_person"))

    assert result["pep"] is True


def test_unknown_tool_returns_an_error():
    assert "error" in handler({}, gateway_context("delete_everything"))
