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


def test_case_status_tells_the_client_what_is_needed_but_not_the_risk():
    result = handler({"case_id": "CASE-2026-0142"}, gateway_context("case_status"))

    assert result["documents_needed"] == ["Beneficial owner declaration", "Manager ID documents"]
    assert "risk" not in str(result).lower() and "miguel" not in str(result).lower()


def test_book_callback_returns_a_reference():
    result = handler({"case_id": "CASE-2026-0142", "topic": "documents"}, gateway_context("book_callback"))

    assert result["reference"].startswith("CB-") and result["with"] == "Rita Almeida"
