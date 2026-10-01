import base64
import json

from onboarding_demo.agent.identity import caller_from_headers


def token(claims: dict) -> str:
    encode = lambda part: base64.urlsafe_b64encode(json.dumps(part).encode()).decode().rstrip("=")
    return f"{encode({'alg': 'RS256'})}.{encode(claims)}.signature"


def test_relationship_manager_from_the_cognito_access_token():
    access = token({"username": "rita.almeida", "cognito:groups": ["relationship-managers"]})

    caller = caller_from_headers({"Authorization": f"Bearer {access}"})

    assert (caller.name, caller.role, caller.username) == ("Rita Almeida", "Relationship manager", "rita.almeida")
    assert caller.token == access


def test_compliance_role_comes_from_the_group_not_the_name():
    access = token({"username": "compliance.officer", "cognito:groups": ["compliance"]})

    caller = caller_from_headers({"authorization": f"Bearer {access}"})

    assert caller.role == "Compliance"
